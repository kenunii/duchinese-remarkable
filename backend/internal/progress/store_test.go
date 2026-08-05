package progress

import (
	"os"
	"path/filepath"
	"testing"
)

func TestProgressRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config", "progress.json")
	store, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	want := Entry{Path: "/lessons/1-example", Title: "Example", Page: 2, Completed: true,
		CoursePath: "/lessons/courses/1-example/lessons.json", CourseTitle: "Example Course",
		ChapterLabel: "Chapter 2"}
	if err := store.RememberReader(want.Path, "https://static.duchinese.net/documents/1/data.crd"); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Update(want); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Update(Entry{Path: want.Path, Title: want.Title,
		ReaderURL: "https://static.duchinese.net/documents/1/new.crd"}); err != nil {
		t.Fatal(err)
	}
	if got := store.State().Entries[want.Path]; got.CoursePath != want.CoursePath ||
		got.CourseTitle != want.CourseTitle || got.ChapterLabel != want.ChapterLabel {
		t.Fatalf("metadata was not preserved with an explicit reader URL: %+v", got)
	}
	if _, err := store.Update(want); err != nil {
		t.Fatal(err)
	}
	if _, err := store.SetLevelFilter("intermediate"); err != nil {
		t.Fatal(err)
	}
	reloaded, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	got := reloaded.State().Entries[want.Path]
	if got.Title != want.Title || got.Page != want.Page || !got.Completed {
		t.Fatalf("unexpected progress: %+v", got)
	}
	if got.ReaderURL == "" {
		t.Fatal("reader URL was not preserved by progress update")
	}
	if got.CoursePath != want.CoursePath {
		t.Fatalf("course path is %q, want %q", got.CoursePath, want.CoursePath)
	}
	if got.CourseTitle != want.CourseTitle {
		t.Fatalf("course title is %q, want %q", got.CourseTitle, want.CourseTitle)
	}
	if got.ChapterLabel != want.ChapterLabel {
		t.Fatalf("chapter label is %q, want %q", got.ChapterLabel, want.ChapterLabel)
	}
	if reloaded.State().LevelFilter != "intermediate" {
		t.Fatalf("level filter is %q, want intermediate", reloaded.State().LevelFilter)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("progress mode is %o, want 600", info.Mode().Perm())
	}
}
