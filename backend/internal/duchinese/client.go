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
	"strconv"
	"strings"
	"time"
)

const (
	baseURL       = "https://duchinese.net"
	mobileAPIURL  = "https://api.duchinese.app/api/v2"
	maxBodyBytes  = 10 << 20
	sessionCookie = "_reader-server_session"
)

var (
	ErrNotAuthenticated = errors.New("DuChinese session is missing or expired")
	ErrNoReaderData     = errors.New("lesson has no reader data")
)

type Session struct {
	Cookie string `json:"cookie"`
}

type MobileSession struct {
	UUID  string `json:"uuid"`
	Token string `json:"token"`
}

type Client struct {
	http        *http.Client
	sessionPath string
	session     Session
	mobile      MobileSession
	cacheDir    string
	entitledCRD map[string]string
}

func New(sessionPath string, additionalPaths ...string) (*Client, error) {
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
		cacheDir:    filepath.Join(filepath.Dir(sessionPath), "cache"),
		entitledCRD: make(map[string]string),
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
	if len(additionalPaths) > 1 && additionalPaths[1] != "" {
		c.cacheDir = additionalPaths[1]
	}
	if len(additionalPaths) > 0 {
		data, err := os.ReadFile(additionalPaths[0])
		if err != nil && !errors.Is(err, os.ErrNotExist) {
			return nil, fmt.Errorf("read mobile session: %w", err)
		}
		if err == nil {
			if err := json.Unmarshal(data, &c.mobile); err != nil {
				return nil, fmt.Errorf("parse mobile session: %w", err)
			}
			if c.mobile.UUID == "" || c.mobile.Token == "" {
				return nil, errors.New("mobile session has no UUID or token")
			}
		}
	}
	return c, nil
}

func (c *Client) Ready() bool {
	return c.session.Cookie != ""
}

func (c *Client) MobileReady() bool {
	return c.mobile.UUID != "" && c.mobile.Token != ""
}

func (c *Client) FinishedReadingStats(ids []string) (json.RawMessage, error) {
	if !c.MobileReady() {
		return nil, errors.New("mobile login required for reading statistics")
	}
	if len(ids) == 0 || len(ids) > 3 {
		return nil, errors.New("reading statistics require one to three lesson IDs")
	}
	for _, id := range ids {
		numericID, err := strconv.Atoi(id)
		if err != nil || numericID < 1 || strconv.Itoa(numericID) != id {
			return nil, errors.New("invalid lesson ID")
		}
	}
	u, _ := url.Parse(mobileAPIURL + "/statistics/finished_reading_chart_data")
	query := u.Query()
	query.Set("user[uuid]", c.mobile.UUID)
	query.Set("user[token]", c.mobile.Token)
	query.Set("read_document_ids", strings.Join(ids, ","))
	u.RawQuery = query.Encode()
	req, err := http.NewRequest(http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "duchinese-remarkable/0.1")
	res, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode == http.StatusUnauthorized {
		return nil, errors.New("mobile login expired")
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return nil, fmt.Errorf("reading statistics: HTTP %d", res.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(res.Body, maxBodyBytes+1))
	if err != nil {
		return nil, err
	}
	if len(body) > maxBodyBytes || !json.Valid(body) {
		return nil, errors.New("invalid reading statistics response")
	}
	return body, nil
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

func (c *Client) Saved(page int) (json.RawMessage, error) {
	u, _ := url.Parse(baseURL + "/lessons/saved.json")
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
	if cached, err := c.cachedCourse(path); err == nil {
		return cached, nil
	}
	return c.fetchCourse(path)
}

func (c *Client) fetchCourse(path string) (json.RawMessage, error) {
	u, err := allowedCourseURL(path)
	if err != nil {
		return nil, err
	}
	payload, requestErr := c.getJSON(u)
	if requestErr == nil {
		if err := c.cacheCourse(path, payload); err != nil {
			return nil, err
		}
		return payload, nil
	}
	if cached, err := c.cachedCourse(path); err == nil {
		return cached, nil
	}
	return nil, requestErr
}

func (c *Client) DownloadCourse(path string) (int, error) {
	payload, err := c.fetchCourse(path)
	if err != nil {
		payload, err = c.cachedCourse(path)
	}
	if err != nil {
		return 0, err
	}
	var course struct {
		Lessons []struct {
			Path   string `json:"path"`
			Locked bool   `json:"locked"`
		} `json:"lessons"`
	}
	if err := json.Unmarshal(payload, &course); err != nil {
		return 0, fmt.Errorf("course metadata: %w", err)
	}
	downloaded := 0
	var lastErr error
	for _, lesson := range course.Lessons {
		if lesson.Locked || lesson.Path == "" {
			continue
		}
		if _, err := c.OpenLesson(lesson.Path); err != nil {
			lastErr = err
			continue
		}
		downloaded++
	}
	if downloaded == 0 && lastErr != nil {
		return 0, lastErr
	}
	return downloaded, nil
}

func (c *Client) StudiedLessonIDs() (json.RawMessage, error) {
	body, _, err := c.get(baseURL + "/lessons")
	if err != nil {
		return nil, err
	}
	ids, err := extractWindowJSON(body, "studiedLessonIds")
	if err != nil || !json.Valid(ids) {
		return nil, errors.New("studied lesson IDs not found")
	}
	return ids, nil
}

func (c *Client) MarkStudied(id string) error {
	numericID, err := strconv.Atoi(id)
	if err != nil || numericID < 1 || strconv.Itoa(numericID) != id {
		return errors.New("invalid lesson ID")
	}
	page, _, err := c.get(baseURL + "/lessons")
	if err != nil {
		return err
	}
	csrfToken, err := extractMetaContent(page, "csrf-token")
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, baseURL+"/lessons/"+id+"/studied", nil)
	if err != nil {
		return err
	}
	req.Header.Set("Cookie", c.session.Cookie)
	req.Header.Set("X-CSRF-Token", csrfToken)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "duchinese-remarkable/0.1")
	res, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if err := c.rotate(res.Cookies()); err != nil {
		return err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return fmt.Errorf("mark studied: HTTP %d", res.StatusCode)
	}
	return nil
}

func (c *Client) OpenLesson(path string, persistedReaderURL ...string) (json.RawMessage, error) {
	if cached, err := c.cachedLesson(path); err == nil {
		return cached, nil
	}
	payload, err := c.openLessonOnline(path, persistedReaderURL...)
	if err == nil {
		if cacheErr := c.cacheLesson(path, payload); cacheErr != nil {
			return nil, cacheErr
		}
		return payload, nil
	}
	if cached, cacheErr := c.cachedLesson(path); cacheErr == nil {
		return cached, nil
	}
	return nil, err
}

func (c *Client) openLessonOnline(path string, persistedReaderURL ...string) (json.RawMessage, error) {
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
	if metadata.Locked {
		return nil, errors.New("lesson is locked")
	}
	if metadata.CRDURL == "" {
		metadata.CRDURL = c.entitledCRD[lessonKey(lessonURL)]
	}
	if metadata.CRDURL == "" && len(persistedReaderURL) > 0 {
		metadata.CRDURL = persistedReaderURL[0]
	}
	if metadata.CRDURL == "" {
		return nil, ErrNoReaderData
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
	out.WriteString(`,"reader_url":`)
	encodedReaderURL, _ := json.Marshal(metadata.CRDURL)
	out.Write(encodedReaderURL)
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
	c.rememberEntitledReaders(body)
	return body, nil
}

func (c *Client) rememberEntitledReaders(body []byte) {
	var value any
	if json.Unmarshal(body, &value) != nil {
		return
	}
	var visit func(any)
	visit = func(current any) {
		switch typed := current.(type) {
		case []any:
			for _, item := range typed {
				visit(item)
			}
		case map[string]any:
			path, _ := typed["path"].(string)
			crdURL, _ := typed["crd_url"].(string)
			locked, hasLocked := typed["locked"].(bool)
			if path != "" && crdURL != "" && hasLocked && !locked && validateAssetURL(crdURL, ".crd") == nil {
				if allowed, err := allowedLessonURL(path); err == nil {
					c.entitledCRD[lessonKey(allowed)] = crdURL
				}
			}
			for _, item := range typed {
				visit(item)
			}
		}
	}
	visit(value)
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
