package duchinese

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestLessonCacheRoundTrip(t *testing.T) {
	client := &Client{cacheDir: t.TempDir()}
	payload := json.RawMessage(`{"lesson":{"id":42,"title":"Cached chapter","path":"/lessons/42-cached"},"reader":{"words":[]}}`)
	if err := client.cacheLesson("/lessons/42-cached", payload); err != nil {
		t.Fatal(err)
	}
	got, err := client.cachedLesson("/lessons/42-cached")
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(payload) {
		t.Fatalf("cached payload = %s, want %s", got, payload)
	}
	info, err := os.Stat(filepath.Join(client.cacheDir, "lessons", cacheName("/lessons/42-cached")))
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("cache mode = %o, want 600", info.Mode().Perm())
	}
}

func TestDownloadedSkipsCorruptCache(t *testing.T) {
	client := &Client{cacheDir: t.TempDir()}
	dir := filepath.Join(client.cacheDir, "lessons")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "broken.json"), []byte("broken"), 0o600); err != nil {
		t.Fatal(err)
	}
	listing, err := client.Downloaded()
	if err != nil {
		t.Fatal(err)
	}
	if string(listing) != `{"courses":[]}` {
		t.Fatalf("downloaded listing = %s, want empty", listing)
	}
}

func TestDownloadedUsesCourseMetadataWhenReaderHasNoLesson(t *testing.T) {
	client := &Client{cacheDir: t.TempDir()}
	path := "/lessons/42-cached?from=course"
	if err := client.cacheLesson(path, json.RawMessage(`{"lesson":null,"reader":{"words":[]}}`)); err != nil {
		t.Fatal(err)
	}
	course := json.RawMessage(`{"lessons":[{"id":"42","title":"Cached chapter","path":"/lessons/42-cached?from=course","course_path":"/lessons/courses/7-cached","course":{"id":7,"title":"Cached course","lessons_url":"ignored"}}]}`)
	if err := client.cacheCourse("/courses/cached/lessons.json", course); err != nil {
		t.Fatal(err)
	}
	listing, err := client.Downloaded()
	if err != nil {
		t.Fatal(err)
	}
	var decoded struct {
		Courses []struct {
			ID         int    `json:"id"`
			LessonsURL string `json:"lessons_url"`
		} `json:"courses"`
	}
	if err := json.Unmarshal(listing, &decoded); err != nil {
		t.Fatal(err)
	}
	if len(decoded.Courses) != 1 || decoded.Courses[0].ID != 7 ||
		decoded.Courses[0].LessonsURL != "/lessons/courses/7-cached/lessons.json" {
		t.Fatalf("downloaded listing = %s", listing)
	}
}

func TestDownloadedHidesIncompleteCourse(t *testing.T) {
	client := &Client{cacheDir: t.TempDir()}
	if err := client.cacheLesson("/lessons/1", json.RawMessage(`{"reader":{"words":[]}}`)); err != nil {
		t.Fatal(err)
	}
	course := json.RawMessage(`{"lessons":[
		{"path":"/lessons/1","course":{"id":7,"title":"Incomplete"}},
		{"path":"/lessons/2","course":{"id":7,"title":"Incomplete"}}
	]}`)
	if err := client.cacheCourse("/courses/incomplete/lessons.json", course); err != nil {
		t.Fatal(err)
	}
	listing, err := client.Downloaded()
	if err != nil {
		t.Fatal(err)
	}
	if string(listing) != `{"courses":[]}` {
		t.Fatalf("downloaded listing = %s, want empty", listing)
	}
}
