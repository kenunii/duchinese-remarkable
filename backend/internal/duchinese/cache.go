package duchinese

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

type lessonCache struct {
	Path    string          `json:"path"`
	Lesson  json.RawMessage `json:"lesson,omitempty"`
	Payload json.RawMessage `json:"payload"`
}

func cacheName(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:]) + ".json"
}

func saveCache(path string, value any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".cache-*")
	if err != nil {
		return err
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)
	if err := temporary.Chmod(0o600); err != nil {
		temporary.Close()
		return err
	}
	if _, err := temporary.Write(append(data, '\n')); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(temporaryPath, path)
}

func loadCache(path string, target any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, target)
}

func (c *Client) lessonCachePath(path string) string {
	return filepath.Join(c.cacheDir, "lessons", cacheName(path))
}

func (c *Client) courseCachePath(path string) string {
	return filepath.Join(c.cacheDir, "courses", cacheName(path))
}

func (c *Client) cacheLesson(path string, payload json.RawMessage) error {
	var opened struct {
		Lesson json.RawMessage `json:"lesson"`
	}
	_ = json.Unmarshal(payload, &opened)
	return saveCache(c.lessonCachePath(path), lessonCache{Path: path, Lesson: opened.Lesson, Payload: payload})
}

func (c *Client) cachedLesson(path string) (json.RawMessage, error) {
	var cached lessonCache
	if err := loadCache(c.lessonCachePath(path), &cached); err != nil {
		return c.cachedLessonByPath(path)
	}
	if !json.Valid(cached.Payload) {
		return c.cachedLessonByPath(path)
	}
	return cached.Payload, nil
}

func (c *Client) cachedLessonByPath(path string) (json.RawMessage, error) {
	files, err := filepath.Glob(filepath.Join(c.cacheDir, "lessons", "*.json"))
	if err != nil {
		return nil, err
	}
	wanted := lessonKey(path)
	if wanted == "" {
		return nil, ErrNoReaderData
	}
	for _, file := range files {
		var cached lessonCache
		if loadCache(file, &cached) != nil || lessonKey(cached.Path) != wanted || !json.Valid(cached.Payload) {
			continue
		}
		// Remember the alternate URL so future opens take the direct cache path.
		if err := c.cacheLesson(path, cached.Payload); err != nil {
			return nil, err
		}
		return cached.Payload, nil
	}
	return nil, ErrNoReaderData
}

func (c *Client) cacheCourse(path string, payload json.RawMessage) error {
	return saveCache(c.courseCachePath(path), payload)
}

func (c *Client) cachedCourse(path string) (json.RawMessage, error) {
	var payload json.RawMessage
	if err := loadCache(c.courseCachePath(path), &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func (c *Client) CourseDownloaded(path string) bool {
	complete, _ := c.CourseCacheStatus(path)
	return complete
}

func (c *Client) CourseCacheStatus(path string) (bool, []string) {
	payload, err := c.cachedCourse(path)
	if err != nil {
		return false, nil
	}
	var course struct {
		Lessons []struct {
			Path   string `json:"path"`
			Locked bool   `json:"locked"`
		} `json:"lessons"`
	}
	if json.Unmarshal(payload, &course) != nil {
		return false, nil
	}
	available := 0
	cachedPaths := make([]string, 0, len(course.Lessons))
	var cachedKeys map[string]bool
	for _, lesson := range course.Lessons {
		if lesson.Locked || lesson.Path == "" {
			continue
		}
		available++
		var cached lessonCache
		if loadCache(c.lessonCachePath(lesson.Path), &cached) == nil && json.Valid(cached.Payload) {
			cachedPaths = append(cachedPaths, lesson.Path)
			continue
		}
		if cachedKeys == nil {
			cachedKeys = c.cachedLessonKeys()
		}
		if cachedKeys[lessonKey(lesson.Path)] {
			cachedPaths = append(cachedPaths, lesson.Path)
		}
	}
	return available > 0 && len(cachedPaths) == available, cachedPaths
}

func (c *Client) cachedLessonKeys() map[string]bool {
	keys := make(map[string]bool)
	files, err := filepath.Glob(filepath.Join(c.cacheDir, "lessons", "*.json"))
	if err != nil {
		return keys
	}
	for _, file := range files {
		var cached lessonCache
		if loadCache(file, &cached) == nil && cached.Path != "" && json.Valid(cached.Payload) {
			keys[lessonKey(cached.Path)] = true
		}
	}
	return keys
}

func (c *Client) Downloaded() (json.RawMessage, error) {
	lessonFiles, err := filepath.Glob(filepath.Join(c.cacheDir, "lessons", "*.json"))
	if err != nil {
		return nil, err
	}
	downloadedPaths := make(map[string]bool, len(lessonFiles))
	for _, file := range lessonFiles {
		var cached lessonCache
		if loadCache(file, &cached) == nil && cached.Path != "" && json.Valid(cached.Payload) {
			downloadedPaths[cached.Path] = true
		}
	}

	courseFiles, err := filepath.Glob(filepath.Join(c.cacheDir, "courses", "*.json"))
	if err != nil {
		return nil, err
	}
	courses := make([]map[string]any, 0, len(courseFiles))
	for _, file := range courseFiles {
		var cached struct {
			Lessons []struct {
				Path       string          `json:"path"`
				Locked     bool            `json:"locked"`
				CoursePath string          `json:"course_path"`
				Course     json.RawMessage `json:"course"`
			} `json:"lessons"`
		}
		if loadCache(file, &cached) != nil || len(cached.Lessons) == 0 {
			continue
		}
		complete := true
		available := 0
		for _, lesson := range cached.Lessons {
			if lesson.Locked || lesson.Path == "" {
				continue
			}
			available++
			if !downloadedPaths[lesson.Path] {
				complete = false
				break
			}
		}
		if !complete || available == 0 {
			continue
		}
		var course map[string]any
		if json.Unmarshal(cached.Lessons[0].Course, &course) != nil || course == nil {
			continue
		}
		coursePath := cached.Lessons[0].CoursePath
		if coursePath != "" {
			course["lessons_url"] = coursePath + "/lessons.json"
		}
		courses = append(courses, course)
	}
	sort.SliceStable(courses, func(i, j int) bool {
		return fmt.Sprint(courses[i]["title"]) < fmt.Sprint(courses[j]["title"])
	})
	return json.Marshal(map[string]any{"courses": courses})
}

func (c *Client) DownloadedCount() int {
	payload, err := c.Downloaded()
	if err != nil {
		return 0
	}
	var listing struct {
		Courses []json.RawMessage `json:"courses"`
	}
	if json.Unmarshal(payload, &listing) != nil {
		return 0
	}
	return len(listing.Courses)
}
