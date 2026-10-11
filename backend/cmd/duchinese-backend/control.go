package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"syscall"
	"time"
)

type exitRequest struct {
	PID int `json:"pid"`
}
type exitReply struct {
	Accepted bool   `json:"accepted"`
	Error    string `json:"error,omitempty"`
}

// This endpoint asks the frontend to use AppLoad's own terminate action.
// It never sends a process signal or stops xochitl.
func serveExitControl(path string, pid int, requestExit func() error) (net.Listener, error) {
	listener, err := net.Listen("unix", path)
	if errors.Is(err, syscall.EADDRINUSE) {
		probe, probeErr := net.DialTimeout("unix", path, time.Second)
		if probeErr == nil {
			probe.Close()
			return nil, fmt.Errorf("exit control already in use")
		}
		if errors.Is(probeErr, syscall.ECONNREFUSED) {
			if removeErr := os.Remove(path); removeErr != nil {
				return nil, removeErr
			}
			listener, err = net.Listen("unix", path)
		}
	}
	if err != nil {
		return nil, err
	}
	if err := os.Chmod(path, 0o600); err != nil {
		listener.Close()
		return nil, err
	}
	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			func() {
				defer conn.Close()
				conn.SetDeadline(time.Now().Add(3 * time.Second))
				var request exitRequest
				if json.NewDecoder(conn).Decode(&request) != nil {
					return
				}
				reply := exitReply{}
				if request.PID != pid {
					reply.Error = "backend PID changed; exit refused"
				} else if err := requestExit(); err != nil {
					reply.Error = err.Error()
				} else {
					reply.Accepted = true
				}
				_ = json.NewEncoder(conn).Encode(reply)
			}()
		}
	}()
	return listener, nil
}

func requestControlledExit(path string, pid int) error {
	conn, err := net.DialTimeout("unix", path, time.Second)
	if err != nil {
		return fmt.Errorf("running backend has no exit control: %w", err)
	}
	defer conn.Close()
	conn.SetDeadline(time.Now().Add(3 * time.Second))
	if err := json.NewEncoder(conn).Encode(exitRequest{PID: pid}); err != nil {
		return err
	}
	var reply exitReply
	if err := json.NewDecoder(conn).Decode(&reply); err != nil {
		return err
	}
	if !reply.Accepted {
		return fmt.Errorf("exit request refused: %s", reply.Error)
	}
	return nil
}
