package duchinese

import "testing"

func TestParseRemoteContinueReadingUsesLatestActiveCourseSession(t *testing.T) {
	payload := []byte(`{
  "study_sessions": [
    {
      "document_type": "lesson",
      "document_id": "10",
      "course_document_index": 0,
      "start_time": 2.5,
      "changed_at": "2026-08-01T10:00:00Z",
      "studied_at": "2026-08-01T10:00:00Z",
      "is_deleted": false,
      "document": {"id": 10, "title": "Older", "level": "newbie"}
    },
    {
      "document_type": "course",
      "document_id": "20",
      "course_document_index": 1,
      "start_time": 42.25,
      "changed_at": "2026-08-02T10:00:00Z",
      "studied_at": "2026-08-02T10:00:00Z",
      "is_deleted": false,
      "document": {
        "id": 20,
        "title": "Course title",
        "path": "/lessons/courses/20-course-title",
        "levels": ["intermediate"],
        "documents": [
          {"id": 201, "title": "One", "level": "intermediate"},
          {"id": 202, "title": "Two", "level": "intermediate"}
        ]
      }
    },
    {
      "document_type": "lesson",
      "document_id": "30",
      "changed_at": "2026-08-03T10:00:00Z",
      "studied_at": "2026-08-03T10:00:00Z",
      "is_deleted": true,
      "document": {"id": 30, "title": "Deleted"}
    }
  ]
}`)

	got, err := parseRemoteContinueReading(payload)
	if err != nil {
		t.Fatal(err)
	}
	if got == nil {
		t.Fatal("expected a continue-reading entry")
	}
	if got.ID != "202" || got.Path != "/lessons/202" || got.Title != "Two" {
		t.Fatalf("unexpected selected lesson: %+v", got)
	}
	if got.CoursePath != "/lessons/courses/20-course-title/lessons.json" || got.CourseTitle != "Course title" {
		t.Fatalf("unexpected course metadata: %+v", got)
	}
	if got.ChapterLabel != "Chapter 2" || got.StartTime != 42.25 {
		t.Fatalf("unexpected resume metadata: %+v", got)
	}
}

func TestParseRemoteContinueReadingWithoutActiveSession(t *testing.T) {
	got, err := parseRemoteContinueReading([]byte(`{"study_sessions":[{"document_id":"1","is_deleted":true}]}`))
	if err != nil {
		t.Fatal(err)
	}
	if got != nil {
		t.Fatalf("got %+v, want nil", got)
	}
}
