package main

import (
	"context"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestVPNHelper(t *testing.T) {
	mode := os.Getenv("DUCHINESE_TEST_VPN_HELPER")
	if mode == "" {
		return
	}
	password, _ := io.ReadAll(os.Stdin)
	if string(password) != "test-secret\n" {
		os.Exit(3)
	}
	if mode == "fail" {
		os.Exit(2)
	}
	if mode == "hang" {
		time.Sleep(time.Minute)
		os.Exit(0)
	}
	listener, err := net.Listen("tcp", os.Getenv("DUCHINESE_TEST_VPN_ADDRESS"))
	if err != nil {
		os.Exit(4)
	}
	for {
		c, err := listener.Accept()
		if err != nil {
			os.Exit(0)
		}
		c.Close()
	}
}
func testVPN(t *testing.T, mode string) (*VPN, *int) {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	address := listener.Addr().String()
	listener.Close()
	v := newVPN(VPNConfig{Server: "https://vpn.example.invalid", Username: "test", Password: "test-secret"})
	v.address = address
	v.timeout = 5 * time.Second
	starts := new(int)
	v.command = func() *exec.Cmd {
		*starts++
		cmd := exec.Command(os.Args[0], "-test.run=^TestVPNHelper$")
		cmd.Env = append(os.Environ(), "DUCHINESE_TEST_VPN_HELPER="+mode, "DUCHINESE_TEST_VPN_ADDRESS="+address)
		return cmd
	}
	t.Cleanup(v.close)
	return v, starts
}
func TestVPNStartsLazilyAndStops(t *testing.T) {
	v, starts := testVPN(t, "ready")
	if *starts != 0 {
		t.Fatal("VPN started without request")
	}
	for range 2 {
		if err := v.ensure(context.Background()); err != nil {
			t.Fatal(err)
		}
	}
	if *starts != 1 {
		t.Fatal("VPN reconnected between requests")
	}
	v.close()
	if c, err := net.DialTimeout("tcp", v.address, 100*time.Millisecond); err == nil {
		c.Close()
		t.Fatal("VPN proxy survived completion")
	}
	if err := v.ensure(context.Background()); err != nil {
		t.Fatal(err)
	}
	if *starts != 2 {
		t.Fatal("new job did not start a fresh connection")
	}
}
func TestVPNFailureAndTimeoutCleanUp(t *testing.T) {
	for _, mode := range []string{"fail", "hang"} {
		t.Run(mode, func(t *testing.T) {
			v, _ := testVPN(t, mode)
			v.timeout = 200 * time.Millisecond
			err := v.ensure(context.Background())
			if err == nil || strings.Contains(err.Error(), v.config.Password) || v.cmd != nil {
				t.Fatalf("bad failure cleanup: %v", err)
			}
		})
	}
}
func TestProcessingVPNCacheAndErrorLifecycle(t *testing.T) {
	for _, fail := range []bool{false, true} {
		name := "success"
		if fail {
			name = "error"
		}
		t.Run(name, func(t *testing.T) {
			vpn, starts := testVPN(t, "ready")
			cloud := newCloud(Credentials{})
			cloud.VPN = vpn
			var calls atomic.Int32
			cloud.Client.Transport = roundTrip(func(_ *http.Request) (*http.Response, error) {
				calls.Add(1)
				code := 200
				if fail {
					code = 503
				}
				return &http.Response{StatusCode: code, Body: io.NopCloser(strings.NewReader(`{"responses":[{"responses":[{}]}]}`))}, nil
			})
			docs := t.TempDir()
			os.WriteFile(filepath.Join(docs, testID+".pdf"), testPDF(), 0600)
			manager, _ := newManager(docs, t.TempDir(), cloud)
			if _, err := manager.start(testID); err != nil {
				t.Fatal(err)
			}
			status := waitJob(t, manager)
			if (status.State == "error") != fail || vpn.cmd != nil || *starts != 1 {
				t.Fatalf("VPN job lifecycle failed: %+v", status)
			}
			if !fail {
				if _, err := manager.start(testID); err != nil {
					t.Fatal(err)
				}
				waitJob(t, manager)
				if *starts != 1 || calls.Load() != 2 {
					t.Fatal("cached pages connected to VPN or cloud")
				}
			}
		})
	}
}
