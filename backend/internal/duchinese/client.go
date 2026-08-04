package duchinese

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const (
	baseURL       = "https://duchinese.net"
	maxBodyBytes  = 10 << 20
	sessionCookie = "_reader-server_session"
)

var ErrNotAuthenticated = errors.New("DuChinese session is missing or expired")

type Session struct {
	Cookie string `json:"cookie"`
}

type Client struct {
	http        *http.Client
	sessionPath string
	session     Session
}

func New(sessionPath string) (*Client, error) {
	c := &Client{
		http: &http.Client{
			Timeout: 30 * time.Second,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				if len(via) >= 5 {
					return errors.New("too many redirects")
				}
				return nil
			},
		},
		sessionPath: sessionPath,
	}
	data, err := os.ReadFile(sessionPath)
	if errors.Is(err, os.ErrNotExist) {
		return c, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read session: %w", err)
	}
	if err := json.Unmarshal(data, &c.session); err != nil {
		return nil, fmt.Errorf("parse session: %w", err)
	}
	if !strings.HasPrefix(c.session.Cookie, sessionCookie+"=") {
		return nil, errors.New("session file has no DuChinese session cookie")
	}
	return c, nil
}

func (c *Client) Ready() bool {
	return c.session.Cookie != ""
}

func (c *Client) Top() (json.RawMessage, error) {
	return c.getJSON(baseURL + "/lessons/top.json")
}

func (c *Client) Latest(page int) (json.RawMessage, error) {
	u, _ := url.Parse(baseURL + "/lessons/latest.json")
	if page > 1 {
		q := u.Query()
		q.Set("page", fmt.Sprint(page))
		u.RawQuery = q.Encode()
	}
	return c.getJSON(u.String())
}

func (c *Client) Search(query string, page int) (json.RawMessage, error) {
	u, _ := url.Parse(baseURL + "/lessons/search.json")
	q := u.Query()
	q.Set("q", strings.TrimSpace(query))
	if page > 1 {
		q.Set("page", fmt.Sprint(page))
	}
	u.RawQuery = q.Encode()
	return c.getJSON(u.String())
}

func (c *Client) Course(path string) (json.RawMessage, error) {
	u, err := allowedCourseURL(path)
	if err != nil {
		return nil, err
	}
	return c.getJSON(u)
}

func (c *Client) OpenLesson(path string) (json.RawMessage, error) {
	lessonURL, err := allowedLessonURL(path)
	if err != nil {
		return nil, err
	}
	body, _, err := c.get(lessonURL)
	if err != nil {
		return nil, err
	}
	lesson, err := extractWindowJSON(body, "lesson")
	if err != nil {
		return nil, fmt.Errorf("lesson metadata: %w", err)
	}
	var metadata struct {
		Locked bool   `json:"locked"`
		CRDURL string `json:"crd_url"`
	}
	if err := json.Unmarshal(lesson, &metadata); err != nil {
		return nil, fmt.Errorf("lesson metadata shape: %w", err)
	}
	if metadata.Locked || metadata.CRDURL == "" {
		return nil, errors.New("lesson is locked or has no reader data")
	}
	if err := validateAssetURL(metadata.CRDURL, ".crd"); err != nil {
		return nil, err
	}
	reader, _, err := c.get(metadata.CRDURL)
	if err != nil {
		return nil, fmt.Errorf("reader data: %w", err)
	}
	if !json.Valid(reader) {
		return nil, errors.New("reader data is not JSON")
	}
	var out bytes.Buffer
	out.WriteString(`{"lesson":`)
	out.Write(lesson)
	out.WriteString(`,"reader":`)
	out.Write(reader)
	out.WriteByte('}')
	return out.Bytes(), nil
}

func (c *Client) getJSON(rawURL string) (json.RawMessage, error) {
	body, contentType, err := c.get(rawURL)
	if err != nil {
		return nil, err
	}
	if !strings.Contains(contentType, "json") || !json.Valid(body) {
		return nil, errors.New("server returned non-JSON data")
	}
	return body, nil
}

func (c *Client) get(rawURL string) ([]byte, string, error) {
	if !c.Ready() {
		return nil, "", ErrNotAuthenticated
	}
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return nil, "", err
	}
	req.Header.Set("User-Agent", "duchinese-remarkable/0.1")
	req.Header.Set("Accept", "application/json,text/html;q=0.9,*/*;q=0.5")
	if req.URL.Host == "duchinese.net" {
		req.Header.Set("Cookie", c.session.Cookie)
	}
	res, err := c.http.Do(req)
	if err != nil {
		return nil, "", err
	}
	defer res.Body.Close()
	if req.URL.Host == "duchinese.net" {
		if err := c.rotate(res.Cookies()); err != nil {
			return nil, "", err
		}
	}
	if res.StatusCode == http.StatusUnauthorized || strings.Contains(res.Request.URL.Path, "/accounts/sign_in") {
		return nil, "", ErrNotAuthenticated
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return nil, "", fmt.Errorf("HTTP %d", res.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(res.Body, maxBodyBytes+1))
	if err != nil {
		return nil, "", err
	}
	if len(body) > maxBodyBytes {
		return nil, "", errors.New("response exceeds 10 MiB")
	}
	return body, res.Header.Get("Content-Type"), nil
}

func (c *Client) rotate(cookies []*http.Cookie) error {
	for _, cookie := range cookies {
		if cookie.Name != sessionCookie || cookie.Value == "" {
			continue
		}
		updated := sessionCookie + "=" + cookie.Value
		if updated == c.session.Cookie {
			return nil
		}
		c.session.Cookie = updated
		return saveSession(c.sessionPath, c.session)
	}
	return nil
}

func saveSession(path string, session Session) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	data, err := json.Marshal(session)
	if err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".session-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(0o600); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(append(data, '\n')); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

func allowedLessonURL(path string) (string, error) {
	u, err := url.Parse(path)
	if err != nil {
		return "", err
	}
	if !u.IsAbs() {
		u, err = url.Parse(baseURL + "/" + strings.TrimLeft(path, "/"))
		if err != nil {
			return "", err
		}
	}
	if u.Scheme != "https" || u.Host != "duchinese.net" || !strings.HasPrefix(u.Path, "/lessons/") {
		return "", errors.New("refusing non-DuChinese lesson URL")
	}
	return u.String(), nil
}

func allowedCourseURL(path string) (string, error) {
	u, err := url.Parse(path)
	if err != nil {
		return "", err
	}
	if !u.IsAbs() {
		u, err = url.Parse(baseURL + "/" + strings.TrimLeft(path, "/"))
		if err != nil {
			return "", err
		}
	}
	if u.Scheme != "https" || u.Host != "duchinese.net" ||
		!strings.HasPrefix(u.Path, "/lessons/courses/") || !strings.HasSuffix(u.Path, "/lessons.json") {
		return "", errors.New("refusing non-DuChinese course URL")
	}
	return u.String(), nil
}

func validateAssetURL(rawURL, suffix string) error {
	u, err := url.Parse(rawURL)
	if err != nil {
		return err
	}
	if u.Scheme != "https" || u.Host != "static.duchinese.net" || !strings.HasSuffix(u.Path, suffix) {
		return errors.New("refusing unexpected asset URL")
	}
	return nil
}

func extractWindowJSON(document []byte, name string) (json.RawMessage, error) {
	marker := []byte("window." + name)
	start := bytes.Index(document, marker)
	if start < 0 {
		return nil, errors.New("window data not found")
	}
	start += len(marker)
	equal := bytes.IndexByte(document[start:], '=')
	if equal < 0 {
		return nil, errors.New("window assignment not found")
	}
	data := bytes.TrimSpace(document[start+equal+1:])
	var value json.RawMessage
	decoder := json.NewDecoder(bytes.NewReader(data))
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	return value, nil
}
