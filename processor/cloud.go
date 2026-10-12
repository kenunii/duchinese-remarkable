package main

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
	"unicode"
)

//go:embed prompt.txt
var annotationPrompt string

type Credentials struct {
	VPN      *VPNConfig `json:"vpn,omitempty"`
	Vision   string     `json:"vision_api_key"`
	DeepSeek string     `json:"deepseek_api_key"`
}
type Cloud struct {
	Keys   Credentials
	Client *http.Client
	VPN    *VPN
}

func newCloud(keys Credentials) *Cloud {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	cloud := &Cloud{Keys: keys, Client: &http.Client{Transport: transport, Timeout: 16 * time.Minute, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }}}
	if keys.VPN != nil {
		cloud.VPN = newVPN(*keys.VPN)
		transport.Proxy = http.ProxyURL(&url.URL{Scheme: "socks5", Host: vpnProxyAddress})
	}
	return cloud
}

// Called for every job exit, including errors/panics. Cached reads never start VPN.
func (c *Cloud) CloseSession() {
	c.Client.CloseIdleConnections()
	if c.VPN != nil {
		c.VPN.close()
	}
}
func (c *Cloud) post(ctx context.Context, url string, body any, header, key string, output any) error {
	if c.VPN != nil {
		if err := c.VPN.ensure(ctx); err != nil {
			return err
		}
	}
	data, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set(header, key)
	res, err := c.Client.Do(req)
	if err != nil {
		return fmt.Errorf("cloud connection failed; retry from the menu")
	}
	defer res.Body.Close()
	if res.StatusCode != 200 {
		return fmt.Errorf("cloud request returned HTTP %d", res.StatusCode)
	}
	return json.NewDecoder(io.LimitReader(res.Body, 32<<20)).Decode(output)
}

type Vertex struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}
type Polygon struct {
	Vertices   []Vertex `json:"vertices"`
	Normalized []Vertex `json:"normalizedVertices"`
}
type Symbol struct {
	Text     string  `json:"text"`
	Bounding Polygon `json:"boundingBox"`
}
type VisionWord struct {
	Symbols  []Symbol `json:"symbols"`
	Bounding Polygon  `json:"boundingBox"`
}
type VisionPage struct {
	Width  float64 `json:"width"`
	Height float64 `json:"height"`
	Blocks []struct {
		Paragraphs []struct {
			Words []VisionWord `json:"words"`
		} `json:"paragraphs"`
	} `json:"blocks"`
}
type VisionResult struct {
	Error      json.RawMessage `json:"error"`
	Annotation struct {
		Pages []VisionPage `json:"pages"`
	} `json:"fullTextAnnotation"`
}

// The PDF endpoint omits symbol rectangles. Interpolate within each OCR word,
// never within a paragraph: a wrapped sentence must keep separate row boxes.
// Exact symbol boxes, when provided, always take precedence.
func locatedSymbols(word VisionWord) []Symbol {
	vertices, normalized := word.Bounding.Normalized, true
	if len(vertices) != 4 {
		vertices, normalized = word.Bounding.Vertices, false
	}
	if len(vertices) != 4 {
		return word.Symbols
	}
	weights := make([]float64, len(word.Symbols))
	total := 0.0
	for i, symbol := range word.Symbols {
		for _, r := range symbol.Text {
			if unicode.Is(unicode.Han, r) || r >= 0x3000 {
				weights[i] += 2
			} else {
				weights[i]++
			}
		}
		total += weights[i]
	}
	if total == 0 {
		return word.Symbols
	}
	mix := func(a, b Vertex, t float64) Vertex { return Vertex{a.X + (b.X-a.X)*t, a.Y + (b.Y-a.Y)*t} }
	result := append([]Symbol(nil), word.Symbols...)
	start := 0.0
	for i := range result {
		end := start + weights[i]/total
		if len(result[i].Bounding.Normalized) == 0 && len(result[i].Bounding.Vertices) == 0 {
			box := []Vertex{mix(vertices[0], vertices[1], start), mix(vertices[0], vertices[1], end), mix(vertices[3], vertices[2], end), mix(vertices[3], vertices[2], start)}
			if normalized {
				result[i].Bounding.Normalized = box
			} else {
				result[i].Bounding.Vertices = box
			}
		}
		start = end
	}
	return result
}

func symbolBox(symbol Symbol, w, h float64) (Box, error) {
	vertices := symbol.Bounding.Normalized
	normalized := len(vertices) > 0
	if !normalized {
		vertices = symbol.Bounding.Vertices
	}
	if len(vertices) < 4 {
		return Box{}, fmt.Errorf("OCR character has no bounding box")
	}
	left, top, right, bottom := math.Inf(1), math.Inf(1), math.Inf(-1), math.Inf(-1)
	for _, v := range vertices {
		x, y := v.X, v.Y
		if !normalized {
			x /= w
			y /= h
		}
		left = math.Min(left, x)
		right = math.Max(right, x)
		top = math.Min(top, y)
		bottom = math.Max(bottom, y)
	}
	left = math.Max(0, left)
	top = math.Max(0, top)
	right = math.Min(1, right)
	bottom = math.Min(1, bottom)
	if !(right > left && bottom > top) {
		return Box{}, fmt.Errorf("OCR character has an empty box")
	}
	// Fixed source scale keeps native tap tolerance consistent with raster imports.
	scale := 2000.0
	return Box{left * scale, top * scale * h / w, (right - left) * scale, (bottom - top) * scale * h / w}, nil
}
func visionSource(page VisionPage) (Source, error) {
	if page.Width <= 0 || page.Height <= 0 {
		return Source{}, fmt.Errorf("OCR page has invalid dimensions")
	}
	source := Source{Width: 2000, Height: 2000 * page.Height / page.Width}
	paragraphs := [][]Character{}
	for _, block := range page.Blocks {
		for _, paragraph := range block.Paragraphs {
			chars := []Character{}
			for _, word := range paragraph.Words {
				for _, symbol := range locatedSymbols(word) {
					if strings.TrimSpace(symbol.Text) == "" {
						continue
					}
					box, err := symbolBox(symbol, page.Width, page.Height)
					if err != nil {
						return source, err
					}
					for _, r := range symbol.Text {
						if !unicode.IsSpace(r) {
							chars = append(chars, Character{Text: string(r), Box: box})
						}
					}
				}
			}
			if len(chars) > 0 {
				paragraphs = append(paragraphs, chars)
			}
		}
	}
	textOf := func(chars []Character) string {
		var b strings.Builder
		for _, c := range chars {
			b.WriteString(c.Text)
		}
		return b.String()
	}
	spatial := false
	previous := -1.0
	for _, chars := range paragraphs {
		if !hasHan(textOf(chars)) {
			continue
		}
		top := chars[0].Box[1]
		for _, c := range chars {
			top = math.Min(top, c.Box[1])
		}
		if previous >= 0 && top < previous-math.Max(25, source.Height*.015) {
			spatial = true
		}
		previous = top
	}
	if spatial {
		all := []Character{}
		for _, chars := range paragraphs {
			all = append(all, chars...)
		}
		sort.SliceStable(all, func(i, j int) bool { return all[i].Box[1]+all[i].Box[3]/2 < all[j].Box[1]+all[j].Box[3]/2 })
		rows := [][]Character{}
		for _, c := range all {
			if len(rows) > 0 {
				r := rows[len(rows)-1]
				a := r[0].Box
				if math.Abs(a[1]+a[3]/2-c.Box[1]-c.Box[3]/2) <= math.Min(a[3], c.Box[3])*.4 {
					rows[len(rows)-1] = append(r, c)
					continue
				}
			}
			rows = append(rows, []Character{c})
		}
		paragraphs = nil
		for _, row := range rows {
			sort.SliceStable(row, func(i, j int) bool { return row[i].Box[0] < row[j].Box[0] })
			start := 0
			for j := 1; j < len(row); j++ {
				if gap(row[j-1].Box, row[j].Box) {
					paragraphs = append(paragraphs, row[start:j])
					start = j
				}
			}
			paragraphs = append(paragraphs, row[start:])
		}
	}
	for _, chars := range paragraphs {
		if !hasHan(textOf(chars)) {
			continue
		}
		line := len(source.Lines)
		parts := []string{""}
		for i, c := range chars {
			if i > 0 && gap(chars[i-1].Box, c.Box) {
				parts = append(parts, "")
			}
			parts[len(parts)-1] += c.Text
			c.Line = line
			source.Characters = append(source.Characters, c)
		}
		source.Lines = append(source.Lines, InputLine{fmt.Sprintf("L%d", line+1), parts})
	}
	return source, nil
}
func hasAPIError(value json.RawMessage) bool {
	return len(value) > 0 && string(value) != "null"
}

func (c *Cloud) OCR(ctx context.Context, pdf []byte) (Source, error) {
	if len(pdf) > 7_000_000 {
		return Source{}, fmt.Errorf("single PDF page exceeds the inline cloud limit")
	}
	body := map[string]any{"requests": []any{map[string]any{"inputConfig": map[string]any{"mimeType": "application/pdf", "content": base64.StdEncoding.EncodeToString(pdf)}, "features": []any{map[string]string{"type": "DOCUMENT_TEXT_DETECTION"}}, "pages": []int{1}}}}
	var response struct {
		Responses []struct {
			Error     json.RawMessage `json:"error"`
			Responses []VisionResult  `json:"responses"`
		} `json:"responses"`
	}
	if err := c.post(ctx, "https://vision.googleapis.com/v1/files:annotate", body, "x-goog-api-key", c.Keys.Vision, &response); err != nil {
		return Source{}, err
	}
	if len(response.Responses) != 1 || hasAPIError(response.Responses[0].Error) || len(response.Responses[0].Responses) != 1 {
		return Source{}, fmt.Errorf("cloud OCR did not return the requested page")
	}
	result := response.Responses[0].Responses[0]
	if !hasAPIError(result.Error) && len(result.Annotation.Pages) == 0 {
		// Vision omits fullTextAnnotation for a blank page. There are no hit boxes
		// to map, so a neutral empty canvas is sufficient for its cached result.
		return Source{Width: 2000, Height: 2000}, nil
	}
	if hasAPIError(result.Error) || len(result.Annotation.Pages) != 1 {
		return Source{}, fmt.Errorf("cloud OCR returned an invalid page")
	}
	return visionSource(result.Annotation.Pages[0])
}
func (c *Cloud) Annotate(ctx context.Context, source Source) (Page, error) {
	if len(source.Characters) == 0 {
		return Page{source.Width, source.Height, Box{0, 0, source.Width, source.Height}, []Word{}, []Sentence{}}, nil
	}
	payload, _ := json.Marshal(map[string]any{"lines": source.Lines, "allowed_confusable_groups": confusables})
	body := map[string]any{"model": "deepseek-flash", "messages": []any{map[string]string{"role": "system", "content": annotationPrompt}, map[string]string{"role": "user", "content": string(payload)}}, "response_format": map[string]string{"type": "json_object"}, "stream": false, "thinking": map[string]string{"type": "enabled"}, "max_tokens": 48000, "temperature": 0}
	var response struct {
		Choices []struct {
			Finish  string `json:"finish_reason"`
			Message struct {
				Content string `json:"content"`
				Refusal any    `json:"refusal"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := c.post(ctx, "https://api.deepseek.com/chat/completions", body, "Authorization", "Bearer "+c.Keys.DeepSeek, &response); err != nil {
		return Page{}, err
	}
	if len(response.Choices) != 1 || response.Choices[0].Finish != "stop" || response.Choices[0].Message.Refusal != nil {
		return Page{}, fmt.Errorf("annotation was incomplete or refused")
	}
	return compile(source, response.Choices[0].Message.Content)
}
