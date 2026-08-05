package duchinese

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestExtractWindowJSON(t *testing.T) {
	document := []byte(`<script>window.lesson = {"title":"测试","locked":false}; window.other = 1</script>`)
	got, err := extractWindowJSON(document, "lesson")
	if err != nil {
		t.Fatal(err)
	}
	var value map[string]any
	if err := json.Unmarshal(got, &value); err != nil {
		t.Fatalf("invalid extracted JSON: %v", err)
	}
	if value["title"] != "测试" {
		t.Fatalf("unexpected title: %v", value["title"])
	}
}

func TestURLAllowLists(t *testing.T) {
	if _, err := allowedLessonURL("/lessons/123-example"); err != nil {
		t.Fatal(err)
	}
	if _, err := allowedCourseURL("/lessons/courses/123-example/lessons.json"); err != nil {
		t.Fatal(err)
	}
	for _, path := range []string{
		"https://example.com/lessons/123",
		"http://duchinese.net/lessons/123",
		"https://duchinese.net/accounts/profile",
	} {
		if _, err := allowedLessonURL(path); err == nil {
			t.Fatalf("allowed unsafe URL %q", path)
		}
	}
}

func TestSaveSessionPermissions(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config", "session.json")
	if err := saveSession(path, Session{Cookie: sessionCookie + "=secret"}); err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("session mode is %o, want 600", info.Mode().Perm())
	}
}

func TestRememberEntitledReaders(t *testing.T) {
	c := &Client{entitledCRD: make(map[string]string)}
	c.rememberEntitledReaders([]byte(`{"lessons":[
        {"path":"/lessons/1-example?from=course","locked":false,"crd_url":"https://static.duchinese.net/documents/1/data.crd"},
        {"path":"/lessons/2-locked","locked":true,"crd_url":"https://static.duchinese.net/documents/2/data.crd"}
    ]}`))
	if got := c.entitledCRD["/lessons/1-example"]; got == "" {
		t.Fatal("unlocked reader was not remembered")
	}
	if got := c.entitledCRD["/lessons/2-locked"]; got != "" {
		t.Fatal("locked reader was remembered")
	}
}

func TestExtractMetaContent(t *testing.T) {
	document := []byte(`<html><head><meta content="token-value" name="csrf-token"></head></html>`)
	got, err := extractMetaContent(document, "csrf-token")
	if err != nil {
		t.Fatal(err)
	}
	if got != "token-value" {
		t.Fatalf("got %q", got)
	}
}
