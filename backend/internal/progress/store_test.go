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

func TestRecentCompletedIDsAreChronological(t *testing.T) {
	store := &Store{state: State{Entries: map[string]Entry{
		"one":   {ID: "1", Completed: true, UpdatedAt: "2026-01-01T10:00:00Z"},
		"two":   {ID: "2", Completed: true, UpdatedAt: "2026-01-02T10:00:00Z"},
		"three": {ID: "3", Completed: true, UpdatedAt: "2026-01-03T10:00:00Z"},
		"four":  {ID: "4", Completed: true, UpdatedAt: "2026-01-04T10:00:00Z"},
		"open":  {ID: "5", Completed: false, UpdatedAt: "2026-01-05T10:00:00Z"},
	}}}
	got := store.RecentCompletedIDs(3)
	want := []string{"2", "3", "4"}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("RecentCompletedIDs() = %v, want %v", got, want)
		}
	}
}

func TestPendingStudiedRoundTripAndDeduplication(t *testing.T) {
	path := filepath.Join(t.TempDir(), "progress.json")
	store, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := store.QueueStudied("42"); err != nil {
		t.Fatal(err)
	}
	if err := store.QueueStudied("42"); err != nil {
		t.Fatal(err)
	}
	if err := store.QueueStudied("43"); err != nil {
		t.Fatal(err)
	}
	if err := store.SetStudiedIDs([]string{"10", "11", "10"}); err != nil {
		t.Fatal(err)
	}
	if err := store.RememberStudied("12"); err != nil {
		t.Fatal(err)
	}
	reloaded, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	got := reloaded.PendingStudiedIDs()
	if len(got) != 2 || got[0] != "42" || got[1] != "43" {
		t.Fatalf("pending studied = %v, want [42 43]", got)
	}
	if got := reloaded.State().StudiedIDs; len(got) != 3 || got[0] != "10" || got[2] != "12" {
		t.Fatalf("studied snapshot = %v, want [10 11 12]", got)
	}
	if err := reloaded.ResolveStudied("42"); err != nil {
		t.Fatal(err)
	}
	if got := reloaded.PendingStudiedIDs(); len(got) != 1 || got[0] != "43" {
		t.Fatalf("pending studied after resolve = %v, want [43]", got)
	}
}
