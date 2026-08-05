package appload

import (
	"encoding/binary"
	"errors"
	"io"
	"net"
	"time"
)

const (
	MaxMessageSize  = 10 << 20
	NewCoordinator  = uint32(0xfffffffe)
	LostCoordinator = uint32(0xfffffffd)
	Terminate       = uint32(0xffffffff)
)

type Message struct {
	Type     uint32
	Contents []byte
}

type Connection struct {
	conn *net.UnixConn
}

func Dial(path string) (*Connection, error) {
	addr := &net.UnixAddr{Name: path, Net: "unixpacket"}
	deadline := time.Now().Add(5 * time.Second)
	var lastErr error
	for time.Now().Before(deadline) {
		conn, err := net.DialUnix("unixpacket", nil, addr)
		if err == nil {
			return &Connection{conn: conn}, nil
		}
		lastErr = err
		time.Sleep(50 * time.Millisecond)
	}
	return nil, lastErr
}

func (c *Connection) Close() error { return c.conn.Close() }

func (c *Connection) Receive() (Message, error) {
	header := make([]byte, 8)
	n, err := c.conn.Read(header)
	if err != nil {
		return Message{}, err
	}
	if n != len(header) {
		return Message{}, io.ErrUnexpectedEOF
	}
	typ := binary.LittleEndian.Uint32(header[:4])
	length := binary.LittleEndian.Uint32(header[4:])
	if length > MaxMessageSize {
		return Message{}, errors.New("AppLoad message exceeds 10 MiB")
	}
	body := make([]byte, length)
	if length > 0 {
		n, err = c.conn.Read(body)
		if err != nil {
			return Message{}, err
		}
		if n != len(body) {
			return Message{}, io.ErrUnexpectedEOF
		}
	}
	return Message{Type: typ, Contents: body}, nil
}

func (c *Connection) Send(typ uint32, contents []byte) error {
	if len(contents) > MaxMessageSize {
		return errors.New("AppLoad message exceeds 10 MiB")
	}
	header := make([]byte, 8)
	binary.LittleEndian.PutUint32(header[:4], typ)
	binary.LittleEndian.PutUint32(header[4:], uint32(len(contents)))
	if _, err := c.conn.Write(header); err != nil {
		return err
	}
	if len(contents) > 0 {
		_, err := c.conn.Write(contents)
		return err
	}
	return nil
}
