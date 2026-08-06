package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/kenunii/duchinese-remarkable/backend/internal/appload"
	"github.com/kenunii/duchinese-remarkable/backend/internal/duchinese"
	"github.com/kenunii/duchinese-remarkable/backend/internal/progress"
)

const (
	requestBootstrap   = uint32(1)
	requestTop         = uint32(2)
	requestLatest      = uint32(3)
	requestSearch      = uint32(4)
	requestLesson      = uint32(5)
	requestCourse      = uint32(6)
	requestProgress    = uint32(7)
	requestStudied     = uint32(8)
	requestMarkRead    = uint32(9)
	requestSettings    = uint32(10)
	requestFinishStats = uint32(11)
	requestSaved       = uint32(12)
	requestDownload    = uint32(13)
	requestDownloaded  = uint32(14)

	responseState    = uint32(101)
	responseData     = uint32(102)
	responseProgress = uint32(103)
	responseError    = uint32(199)
)

type request struct {
	Query        string `json:"query"`
	Page         int    `json:"page"`
	Position     int    `json:"position"`
	Path         string `json:"path"`
	Title        string `json:"title"`
	Level        string `json:"level"`
	Completed    bool   `json:"completed"`
	ID           string `json:"id"`
	CoursePath   string `json:"course_path"`
	CourseTitle  string `json:"course_title"`
	ChapterLabel string `json:"chapter_label"`
}

func main() {
	if len(os.Args) != 2 {
		log.Fatal("usage: duchinese-backend <AppLoad socket>")
	}
	home, err := os.UserHomeDir()
	if err != nil {
		log.Fatal(err)
	}
	configDir := filepath.Join(home, ".config", "duchinese-remarkable")
	client, err := duchinese.New(
		filepath.Join(configDir, "session.json"),
		filepath.Join(configDir, "mobile-session.json"),
	)
	if err != nil {
		log.Fatal(err)
	}
	progressStore, err := progress.Open(filepath.Join(configDir, "progress.json"))
	if err != nil {
		log.Fatal(err)
	}
	conn, err := appload.Dial(os.Args[1])
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	for {
		message, err := conn.Receive()
		if err != nil {
			return
		}
		if message.Type == appload.Terminate {
			return
		}
		if message.Type == appload.NewCoordinator || message.Type == appload.LostCoordinator {
			continue
		}
		if err := handle(conn, client, progressStore, message); err != nil {
			sendError(conn, err)
		}
	}
}

func handle(conn *appload.Connection, client *duchinese.Client, progressStore *progress.Store, message appload.Message) error {
	var req request
	if len(message.Contents) > 0 {
		if err := json.Unmarshal(message.Contents, &req); err != nil {
			return fmt.Errorf("invalid request: %w", err)
		}
	}
	switch message.Type {
	case requestBootstrap:
		return sendJSON(conn, responseState, map[string]any{
			"authenticated": client.Ready(), "mobile_authenticated": client.MobileReady(),
			"progress": progressStore.State(), "downloaded_count": client.DownloadedCount(),
		})
	case requestTop:
		payload, err := client.Top()
		return sendRaw(conn, "top", payload, err)
	case requestLatest:
		payload, err := client.Latest(max(1, req.Page))
		return sendRaw(conn, "latest", payload, err)
	case requestSaved:
		payload, err := client.Saved(max(1, req.Page))
		return sendRaw(conn, "saved", payload, err)
	case requestDownloaded:
		payload, err := client.Downloaded()
		return sendRaw(conn, "downloaded", payload, err)
	case requestDownload:
		if req.Path == "" {
			return errors.New("course download requires a path")
		}
		count, err := client.DownloadCourse(req.Path)
		if err != nil {
			return err
		}
		if studied, studiedErr := client.StudiedLessonIDs(); studiedErr == nil {
			_ = progressStore.SetStudiedIDs(studiedStrings(studied))
		}
		return sendJSON(conn, responseData, map[string]any{
			"kind": "download_course", "payload": map[string]int{"count": count},
		})
	case requestSearch:
		payload, err := client.Search(req.Query, max(1, req.Page))
		return sendRaw(conn, "search", payload, err)
	case requestLesson:
		var persistedReaderURL string
		progressEntry, hasProgress := progressStore.Entry(req.Path)
		if hasProgress {
			persistedReaderURL = progressEntry.ReaderURL
		}
		payload, err := client.OpenLesson(req.Path, persistedReaderURL)
		if errors.Is(err, duchinese.ErrNoReaderData) && hasProgress && progressEntry.Title != "" {
			if _, searchErr := client.Search(progressEntry.Title, 1); searchErr == nil {
				payload, err = client.OpenLesson(req.Path)
			}
		}
		if err == nil {
			var opened struct {
				ReaderURL string `json:"reader_url"`
			}
			if json.Unmarshal(payload, &opened) == nil && opened.ReaderURL != "" {
				if rememberErr := progressStore.RememberReader(req.Path, opened.ReaderURL); rememberErr != nil {
					return rememberErr
				}
			}
		}
		return sendRaw(conn, "lesson", payload, err)
	case requestCourse:
		payload, err := client.Course(req.Path)
		return sendRaw(conn, "course", payload, err)
	case requestProgress:
		if req.Path == "" || req.Title == "" {
			return errors.New("progress requires a lesson path and title")
		}
		state, err := progressStore.Update(progress.Entry{
			Path: req.Path, ID: req.ID, Title: req.Title, Level: req.Level,
			CoursePath: req.CoursePath, CourseTitle: req.CourseTitle, ChapterLabel: req.ChapterLabel,
			Page: req.Page, Position: req.Position, Completed: req.Completed,
		})
		if err != nil {
			return err
		}
		return sendJSON(conn, responseProgress, state)
	case requestStudied:
		payload, err := client.StudiedLessonIDs()
		if err != nil {
			return err
		}
		pending := progressStore.PendingStudiedIDs()
		for _, id := range pending {
			if client.MarkStudied(id) == nil {
				if err := progressStore.ResolveStudied(id); err != nil {
					return err
				}
			}
		}
		payload = mergeStudied(payload, pending)
		if err := progressStore.SetStudiedIDs(studiedStrings(payload)); err != nil {
			return err
		}
		return sendRaw(conn, "studied", payload, nil)
	case requestMarkRead:
		if err := client.MarkStudied(req.ID); err != nil {
			if queueErr := progressStore.QueueStudied(req.ID); queueErr != nil {
				return queueErr
			}
		} else if err := progressStore.ResolveStudied(req.ID); err != nil {
			return err
		}
		if err := progressStore.RememberStudied(req.ID); err != nil {
			return err
		}
		return sendJSON(conn, responseProgress, map[string]any{"studied_id": req.ID, "progress": progressStore.State(), "pending_sync": contains(progressStore.PendingStudiedIDs(), req.ID)})
	case requestSettings:
		if !validLevelFilter(req.Level) {
			return errors.New("invalid level filter")
		}
		state, err := progressStore.SetLevelFilter(req.Level)
		if err != nil {
			return err
		}
		return sendJSON(conn, responseProgress, state)
	case requestFinishStats:
		if req.ID == "" {
			return errors.New("reading statistics require a lesson ID")
		}
		if !req.Completed {
			if err := client.MarkStudied(req.ID); err != nil {
				if queueErr := progressStore.QueueStudied(req.ID); queueErr != nil {
					return queueErr
				}
				return sendJSON(conn, responseData, map[string]any{
					"kind": "finish_stats", "payload": map[string]any{
						"chart_data": []any{}, "new_words": []any{}, "learned_words": []any{},
						"new_count": -1, "learned_count": -1, "pending_sync": true,
					},
				})
			}
			if err := progressStore.ResolveStudied(req.ID); err != nil {
				return err
			}
			if err := progressStore.RememberStudied(req.ID); err != nil {
				return err
			}
		}
		ids := progressStore.RecentCompletedIDs(3)
		if len(ids) == 0 {
			ids = []string{req.ID}
		}
		payload, err := client.FinishedReadingStats(ids)
		if err != nil {
			return sendJSON(conn, responseData, map[string]any{
				"kind": "finish_stats", "payload": map[string]any{
					"chart_data": []any{}, "new_words": []any{}, "learned_words": []any{},
					"new_count": -1, "learned_count": -1, "stats_unavailable": true,
				},
			})
		}
		return sendRaw(conn, "finish_stats", payload, nil)
	default:
		return errors.New("unknown request")
	}
}

func mergeStudied(payload json.RawMessage, pending []string) json.RawMessage {
	var ids []any
	if json.Unmarshal(payload, &ids) != nil {
		return payload
	}
	seen := make(map[string]bool, len(ids)+len(pending))
	for _, id := range ids {
		seen[fmt.Sprint(id)] = true
	}
	for _, id := range pending {
		if !seen[id] {
			ids = append(ids, id)
			seen[id] = true
		}
	}
	merged, err := json.Marshal(ids)
	if err != nil {
		return payload
	}
	return merged
}

func contains(values []string, wanted string) bool {
	for _, value := range values {
		if value == wanted {
			return true
		}
	}
	return false
}

func studiedStrings(payload json.RawMessage) []string {
	var values []any
	if json.Unmarshal(payload, &values) != nil {
		return nil
	}
	ids := make([]string, 0, len(values))
	for _, value := range values {
		id := fmt.Sprint(value)
		if id != "" {
			ids = append(ids, id)
		}
	}
	return ids
}

func validLevelFilter(level string) bool {
	switch level {
	case "", "newbie", "elementary", "intermediate", "upper intermediate", "advanced", "master":
		return true
	default:
		return false
	}
}

func sendRaw(conn *appload.Connection, kind string, payload json.RawMessage, err error) error {
	if err != nil {
		return err
	}
	message := append([]byte(`{"kind":`+fmt.Sprintf("%q", kind)+`,"payload":`), payload...)
	message = append(message, '}')
	return conn.Send(responseData, message)
}

func sendJSON(conn *appload.Connection, typ uint32, value any) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return conn.Send(typ, data)
}

func sendError(conn *appload.Connection, err error) {
	code := "request_failed"
	if errors.Is(err, duchinese.ErrNotAuthenticated) {
		code = "not_authenticated"
	}
	_ = sendJSON(conn, responseError, map[string]string{"code": code, "message": err.Error()})
}
