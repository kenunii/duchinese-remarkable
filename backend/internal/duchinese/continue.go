package duchinese

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const continueReadingTimeout = 15 * time.Second

// ContinueReading describes the most recently changed, unfinished study
// session synced by the official apps. StartTime is the narration position in
// seconds and can be mapped to a word through a lesson's syllable_times.
type ContinueReading struct {
	Path         string  `json:"path"`
	ID           string  `json:"id"`
	Title        string  `json:"title"`
	Level        string  `json:"level,omitempty"`
	CoursePath   string  `json:"course_path,omitempty"`
	CourseTitle  string  `json:"course_title,omitempty"`
	ChapterLabel string  `json:"chapter_label,omitempty"`
	StartTime    float64 `json:"start_time,omitempty"`
	UpdatedAt    string  `json:"updated_at,omitempty"`
}

type mobileSyncDocument struct {
	ID        json.RawMessage      `json:"id"`
	Title     string               `json:"title"`
	Path      string               `json:"path"`
	Level     string               `json:"level"`
	Levels    []string             `json:"levels"`
	Documents []mobileSyncDocument `json:"documents"`
}

type mobileStudySession struct {
	DocumentType        string             `json:"document_type"`
	DocumentID          string             `json:"document_id"`
	CourseDocumentIndex int                `json:"course_document_index"`
	StartTime           float64            `json:"start_time"`
	ChangedAt           string             `json:"changed_at"`
	StudiedAt           string             `json:"studied_at"`
	Deleted             bool               `json:"is_deleted"`
	Document            mobileSyncDocument `json:"document"`
}

func (c *Client) RemoteContinueReading() (*ContinueReading, error) {
	if !c.MobileReady() {
		return nil, errors.New("mobile login required for continue reading")
	}
	payload, err := json.Marshal(map[string]any{
		"user": map[string]string{
			"uuid":  c.mobile.UUID,
			"token": c.mobile.Token,
		},
		"force_full_sync": "true",
		"study_sessions":  []any{},
		"time":            time.Now().Unix(),
	})
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(context.Background(), continueReadingTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodPut, mobileAPIURL+"/sync", bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")
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
		return nil, fmt.Errorf("continue reading sync: HTTP %d", res.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(res.Body, maxBodyBytes+1))
	if err != nil {
		return nil, err
	}
	if len(body) > maxBodyBytes {
		return nil, errors.New("continue reading sync response exceeds 10 MiB")
	}
	return parseRemoteContinueReading(body)
}

func parseRemoteContinueReading(body []byte) (*ContinueReading, error) {
	var response struct {
		StudySessions []mobileStudySession `json:"study_sessions"`
	}
	if err := json.Unmarshal(body, &response); err != nil {
		return nil, errors.New("invalid continue reading sync response")
	}
	var latest *mobileStudySession
	for index := range response.StudySessions {
		session := &response.StudySessions[index]
		if session.Deleted || session.DocumentID == "" {
			continue
		}
		if latest == nil || sessionAfter(session, latest) {
			latest = session
		}
	}
	if latest == nil {
		return nil, nil
	}

	lesson := latest.Document
	result := &ContinueReading{
		ID:        latest.DocumentID,
		Path:      "/lessons/" + latest.DocumentID,
		Title:     lesson.Title,
		Level:     lesson.Level,
		StartTime: latest.StartTime,
		UpdatedAt: latest.ChangedAt,
	}
	if latest.DocumentType == "course" {
		course := latest.Document
		result.CourseTitle = course.Title
		result.CoursePath = courseLessonsPath(course.Path)
		chapterIndex := latest.CourseDocumentIndex
		if chapterIndex >= 0 && chapterIndex < len(course.Documents) {
			lesson = course.Documents[chapterIndex]
			if id := rawID(lesson.ID); id != "" {
				result.ID = id
				result.Path = "/lessons/" + id
			}
			result.Title = lesson.Title
			result.Level = lesson.Level
		}
		if result.Level == "" && len(course.Levels) > 0 {
			result.Level = course.Levels[0]
		}
		result.ChapterLabel = fmt.Sprintf("Chapter %d", chapterIndex+1)
	}
	if result.Title == "" {
		result.Title = result.CourseTitle
	}
	return result, nil
}

func sessionAfter(left, right *mobileStudySession) bool {
	if left.StudiedAt != "" && right.StudiedAt != "" && left.StudiedAt != right.StudiedAt {
		return timestampAfter(left.StudiedAt, right.StudiedAt)
	}
	return timestampAfter(left.ChangedAt, right.ChangedAt)
}

func rawID(value json.RawMessage) string {
	value = bytes.TrimSpace(value)
	if len(value) == 0 || bytes.Equal(value, []byte("null")) {
		return ""
	}
	if value[0] == '"' {
		var text string
		if json.Unmarshal(value, &text) == nil {
			return text
		}
		return ""
	}
	return string(value)
}

func courseLessonsPath(path string) string {
	path = strings.TrimSuffix(path, "/")
	if path == "" {
		return ""
	}
	if strings.HasSuffix(path, "/lessons.json") {
		return path
	}
	return path + "/lessons.json"
}

func timestampAfter(left, right string) bool {
	leftTime, leftErr := time.Parse(time.RFC3339Nano, left)
	rightTime, rightErr := time.Parse(time.RFC3339Nano, right)
	if leftErr == nil && rightErr == nil {
		return leftTime.After(rightTime)
	}
	return left > right
}
