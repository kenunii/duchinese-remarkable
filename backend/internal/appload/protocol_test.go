package appload

import (
	"net"
	"path/filepath"
	"testing"
	"time"
)

func TestDialWaitsForAppLoadSocket(t *testing.T) {
	path := filepath.Join(t.TempDir(), "delayed.sock")
	accepted := make(chan error, 1)
	go func() {
		time.Sleep(150 * time.Millisecond)
		listener, err := net.ListenUnix("unixpacket", &net.UnixAddr{Name: path, Net: "unixpacket"})
		if err != nil {
			accepted <- err
			return
		}
		defer listener.Close()
		connection, err := listener.AcceptUnix()
		if err == nil {
			err = connection.Close()
		}
		accepted <- err
	}()

	connection, err := Dial(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := connection.Close(); err != nil {
		t.Fatal(err)
	}
	if err := <-accepted; err != nil {
		t.Fatal(err)
	}
}
