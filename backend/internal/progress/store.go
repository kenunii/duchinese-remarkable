package progress

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"time"
)

type Entry struct {
	Path         string `json:"path"`
	ID           string `json:"id,omitempty"`
	Title        string `json:"title"`
	Level        string `json:"level,omitempty"`
	Page         int    `json:"page"`
	Position     int    `json:"position"`
	Completed    bool   `json:"completed"`
	UpdatedAt    string `json:"updated_at"`
	ReaderURL    string `json:"reader_url,omitempty"`
	CoursePath   string `json:"course_path,omitempty"`
	CourseTitle  string `json:"course_title,omitempty"`
	ChapterLabel string `json:"chapter_label,omitempty"`
}

type State struct {
	Last           *Entry           `json:"last,omitempty"`
	Entries        map[string]Entry `json:"entries"`
	LevelFilter    string           `json:"level_filter,omitempty"`
	PendingStudied []string         `json:"pending_studied,omitempty"`
	StudiedIDs     []string         `json:"studied_ids,omitempty"`
}

type Store struct {
	path  string
	state State
}

func Open(path string) (*Store, error) {
	store := &Store{path: path, state: State{Entries: make(map[string]Entry)}}
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return store, nil
	}
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(data, &store.state); err != nil {
		return nil, err
	}
	if store.state.Entries == nil {
		store.state.Entries = make(map[string]Entry)
	}
	return store, nil
}

func (s *Store) State() State { return s.state }

func (s *Store) Update(entry Entry) (State, error) {
	if existing, ok := s.state.Entries[entry.Path]; ok {
		if entry.ReaderURL == "" {
			entry.ReaderURL = existing.ReaderURL
		}
		if entry.ID == "" {
			entry.ID = existing.ID
		}
		if entry.CoursePath == "" {
			entry.CoursePath = existing.CoursePath
		}
		if entry.CourseTitle == "" {
			entry.CourseTitle = existing.CourseTitle
		}
		if entry.ChapterLabel == "" {
			entry.ChapterLabel = existing.ChapterLabel
		}
	}
	entry.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	s.state.Entries[entry.Path] = entry
	s.state.Last = &entry
	return s.state, s.save()
}

func (s *Store) Entry(path string) (Entry, bool) {
	entry, ok := s.state.Entries[path]
	return entry, ok
}

func (s *Store) RecentCompletedIDs(limit int) []string {
	entries := make([]Entry, 0, len(s.state.Entries))
	for _, entry := range s.state.Entries {
		if entry.Completed && entry.ID != "" {
			entries = append(entries, entry)
		}
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].UpdatedAt > entries[j].UpdatedAt })
	if limit > len(entries) {
		limit = len(entries)
	}
	if limit < 0 {
		limit = 0
	}
	ids := make([]string, limit)
	for i := 0; i < limit; i++ {
		ids[limit-1-i] = entries[i].ID
	}
	return ids
}

func (s *Store) RememberReader(path, readerURL string) error {
	entry := s.state.Entries[path]
	entry.Path = path
	entry.ReaderURL = readerURL
	s.state.Entries[path] = entry
	return s.save()
}

func (s *Store) SetLevelFilter(level string) (State, error) {
	s.state.LevelFilter = level
	return s.state, s.save()
}

func (s *Store) QueueStudied(id string) error {
	if id == "" {
		return nil
	}
	for _, pending := range s.state.PendingStudied {
		if pending == id {
			return nil
		}
	}
	s.state.PendingStudied = append(s.state.PendingStudied, id)
	return s.save()
}

func (s *Store) PendingStudiedIDs() []string {
	return append([]string(nil), s.state.PendingStudied...)
}

func (s *Store) ResolveStudied(id string) error {
	pending := s.state.PendingStudied[:0]
	for _, queued := range s.state.PendingStudied {
		if queued != id {
			pending = append(pending, queued)
		}
	}
	if len(pending) == len(s.state.PendingStudied) {
		return nil
	}
	s.state.PendingStudied = pending
	return s.save()
}

func (s *Store) SetStudiedIDs(ids []string) error {
	seen := make(map[string]bool, len(ids))
	s.state.StudiedIDs = s.state.StudiedIDs[:0]
	for _, id := range ids {
		if id != "" && !seen[id] {
			s.state.StudiedIDs = append(s.state.StudiedIDs, id)
			seen[id] = true
		}
	}
	return s.save()
}

func (s *Store) RememberStudied(id string) error {
	for _, studied := range s.state.StudiedIDs {
		if studied == id {
			return nil
		}
	}
	s.state.StudiedIDs = append(s.state.StudiedIDs, id)
	return s.save()
}

func (s *Store) save() error {
	if err := os.MkdirAll(filepath.Dir(s.path), 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(s.state, "", "  ")
	if err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(s.path), ".progress-*")
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
	return os.Rename(temporaryPath, s.path)
}
