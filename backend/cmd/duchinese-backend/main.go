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
)

const (
	requestBootstrap = uint32(1)
	requestTop       = uint32(2)
	requestLatest    = uint32(3)
	requestSearch    = uint32(4)
	requestLesson    = uint32(5)
	requestCourse    = uint32(6)

	responseState = uint32(101)
	responseData  = uint32(102)
	responseError = uint32(199)
)

type request struct {
	Query string `json:"query"`
	Page  int    `json:"page"`
	Path  string `json:"path"`
}

func main() {
	if len(os.Args) != 2 {
		log.Fatal("usage: duchinese-backend <AppLoad socket>")
	}
	home, err := os.UserHomeDir()
	if err != nil {
		log.Fatal(err)
	}
	client, err := duchinese.New(filepath.Join(home, ".config", "duchinese-remarkable", "session.json"))
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
		if message.Type == appload.NewCoordinator {
			continue
		}
		if err := handle(conn, client, message); err != nil {
			sendError(conn, err)
		}
	}
}

func handle(conn *appload.Connection, client *duchinese.Client, message appload.Message) error {
	var req request
	if len(message.Contents) > 0 {
		if err := json.Unmarshal(message.Contents, &req); err != nil {
			return fmt.Errorf("invalid request: %w", err)
		}
	}
	if req.Page < 1 {
		req.Page = 1
	}
	switch message.Type {
	case requestBootstrap:
		return sendJSON(conn, responseState, map[string]any{"authenticated": client.Ready()})
	case requestTop:
		payload, err := client.Top()
		return sendRaw(conn, "top", payload, err)
	case requestLatest:
		payload, err := client.Latest(req.Page)
		return sendRaw(conn, "latest", payload, err)
	case requestSearch:
		payload, err := client.Search(req.Query, req.Page)
		return sendRaw(conn, "search", payload, err)
	case requestLesson:
		payload, err := client.OpenLesson(req.Path)
		return sendRaw(conn, "lesson", payload, err)
	case requestCourse:
		payload, err := client.Course(req.Path)
		return sendRaw(conn, "course", payload, err)
	default:
		return errors.New("unknown request")
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
