package main

import (
	"errors"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
)

func TestExitControlChecksPIDAndRequestsAppExit(t *testing.T) {
	path := filepath.Join(t.TempDir(), "control.sock")
	var calls atomic.Int32
	listener, err := serveExitControl(path, 42, func() error { calls.Add(1); return nil })
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	info, err := os.Stat(path)
	if err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("control permissions: %v, %v", info, err)
	}
	if err := requestControlledExit(path, 43); err == nil {
		t.Fatal("accepted a different process")
	}
	if calls.Load() != 0 {
		t.Fatal("wrong PID caused exit")
	}
	if err := requestControlledExit(path, 42); err != nil {
		t.Fatal(err)
	}
	if calls.Load() != 1 {
		t.Fatalf("exit requests = %d", calls.Load())
	}
}

func TestExitControlLeavesExistingListenerAlone(t *testing.T) {
	path := filepath.Join(t.TempDir(), "control.sock")
	listener, err := serveExitControl(path, 42, func() error { return nil })
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	if second, err := serveExitControl(path, 43, func() error { return nil }); err == nil {
		second.Close()
		t.Fatal("replaced a live control endpoint")
	}
	if err := requestControlledExit(path, 42); err != nil {
		t.Fatal(err)
	}
}

func TestExitControlReportsUnavailableFrontend(t *testing.T) {
	path := filepath.Join(t.TempDir(), "control.sock")
	listener, err := serveExitControl(path, 42, func() error { return errors.New("frontend disconnected") })
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	if err := requestControlledExit(path, 42); err == nil {
		t.Fatal("claimed success when frontend could not be contacted")
	}
}
