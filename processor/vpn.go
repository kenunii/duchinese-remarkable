package main

import (
	"context"
	"fmt"
	"net"
	"os/exec"
	"strings"
	"sync"
	"syscall"
	"time"
)

const vpnProxyAddress = "127.0.0.1:1087"
const vpnRuntime = "/home/root/.local/lib/duchinese-vpn/"

type VPNConfig struct {
	Server    string `json:"server"`
	Username  string `json:"username"`
	Password  string `json:"password"`
	AuthGroup string `json:"authgroup,omitempty"`
}

// VPN owns a foreground OpenConnect process and its userspace SOCKS helper.
// It never creates a TUN interface or changes system routing/DNS.
type VPN struct {
	config  VPNConfig
	command func() *exec.Cmd
	address string
	timeout time.Duration
	mu      sync.Mutex
	cmd     *exec.Cmd
	done    chan struct{}
}

func newVPN(config VPNConfig) *VPN {
	v := &VPN{config: config, address: vpnProxyAddress, timeout: 45 * time.Second}
	v.command = func() *exec.Cmd {
		args := []string{"--protocol=anyconnect", "--non-inter", "--passwd-on-stdin", "--no-proxy",
			"--user=" + config.Username, "--script-tun", "--script=" + vpnRuntime + "proxy-script",
			"--cafile=/etc/ssl/certs/ca-certificates.crt", "--reconnect-timeout=15"}
		if config.AuthGroup != "" {
			args = append(args, "--authgroup="+config.AuthGroup)
		}
		args = append(args, config.Server)
		return exec.Command(vpnRuntime+"openconnect", args...)
	}
	return v
}

func (v *VPN) ensure(ctx context.Context) error {
	v.mu.Lock()
	defer v.mu.Unlock()
	if v.cmd != nil {
		select {
		case <-v.done:
			v.stopLocked()
			return fmt.Errorf("VPN connection ended; resume processing to reconnect")
		default:
			return nil
		}
	}
	if v.config.Server == "" || v.config.Username == "" || v.config.Password == "" || strings.ContainsAny(v.config.Password, "\r\n") {
		return fmt.Errorf("VPN configuration is incomplete or invalid")
	}
	// Do not silently use an unrelated listener on the configured proxy port.
	probe, err := net.Listen("tcp", v.address)
	if err != nil {
		return fmt.Errorf("local VPN proxy port is already in use")
	}
	probe.Close()
	cmd := v.command()
	cmd.Stdin = strings.NewReader(v.config.Password + "\n")
	// Passwords go through stdin; provider output may contain account details.
	// Leave stdout/stderr disconnected rather than exposing them to app logs.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true, Pdeathsig: syscall.SIGTERM}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("VPN runtime is missing or cannot start")
	}
	v.cmd = cmd
	v.done = make(chan struct{})
	done := v.done
	go func() { _ = cmd.Wait(); close(done) }()
	timeout := time.NewTimer(v.timeout)
	defer timeout.Stop()
	tick := time.NewTicker(100 * time.Millisecond)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			v.stopLocked()
			return ctx.Err()
		case <-timeout.C:
			v.stopLocked()
			return fmt.Errorf("VPN connection timed out; check network access")
		case <-done:
			v.stopLocked()
			return fmt.Errorf("VPN login failed; check credentials and network access")
		case <-tick.C:
			connection, err := net.DialTimeout("tcp", v.address, 200*time.Millisecond)
			if err == nil {
				connection.Close()
				return nil
			}
		}
	}
}

func (v *VPN) stopLocked() {
	if v.cmd == nil {
		return
	}
	_ = syscall.Kill(-v.cmd.Process.Pid, syscall.SIGTERM)
	select {
	case <-v.done:
	case <-time.After(3 * time.Second):
		_ = syscall.Kill(-v.cmd.Process.Pid, syscall.SIGKILL)
		<-v.done
	}
	// Also clean up a helper that outlived the OpenConnect parent.
	_ = syscall.Kill(-v.cmd.Process.Pid, syscall.SIGKILL)
	v.cmd = nil
	v.done = nil
}
func (v *VPN) close() {
	v.mu.Lock()
	defer v.mu.Unlock()
	v.stopLocked()
}
