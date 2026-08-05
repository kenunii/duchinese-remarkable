package duchinese

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/url"
	"strings"
)

func lessonKey(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	return u.Path
}

func allowedLessonURL(path string) (string, error) {
	u, err := absoluteDuChineseURL(path)
	if err != nil {
		return "", err
	}
	if !strings.HasPrefix(u.Path, "/lessons/") {
		return "", errors.New("refusing non-DuChinese lesson URL")
	}
	return u.String(), nil
}

func allowedCourseURL(path string) (string, error) {
	u, err := absoluteDuChineseURL(path)
	if err != nil {
		return "", err
	}
	if !strings.HasPrefix(u.Path, "/lessons/courses/") || !strings.HasSuffix(u.Path, "/lessons.json") {
		return "", errors.New("refusing non-DuChinese course URL")
	}
	return u.String(), nil
}

func absoluteDuChineseURL(path string) (*url.URL, error) {
	u, err := url.Parse(path)
	if err != nil {
		return nil, err
	}
	if !u.IsAbs() {
		u, err = url.Parse(baseURL + "/" + strings.TrimLeft(path, "/"))
		if err != nil {
			return nil, err
		}
	}
	if u.Scheme != "https" || u.Host != "duchinese.net" {
		return nil, errors.New("refusing non-DuChinese URL")
	}
	return u, nil
}

func validateAssetURL(rawURL, suffix string) error {
	u, err := url.Parse(rawURL)
	if err != nil {
		return err
	}
	if u.Scheme != "https" || u.Host != "static.duchinese.net" || !strings.HasSuffix(u.Path, suffix) {
		return errors.New("refusing unexpected asset URL")
	}
	return nil
}

func extractWindowJSON(document []byte, name string) (json.RawMessage, error) {
	marker := []byte("window." + name)
	start := bytes.Index(document, marker)
	if start < 0 {
		return nil, errors.New("window data not found")
	}
	start += len(marker)
	equal := bytes.IndexByte(document[start:], '=')
	if equal < 0 {
		return nil, errors.New("window assignment not found")
	}
	data := bytes.TrimSpace(document[start+equal+1:])
	var value json.RawMessage
	decoder := json.NewDecoder(bytes.NewReader(data))
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	return value, nil
}

func extractMetaContent(document []byte, name string) (string, error) {
	marker := []byte(`name="` + name + `"`)
	start := bytes.Index(document, marker)
	if start < 0 {
		return "", errors.New("meta tag not found")
	}
	tagStart := bytes.LastIndex(document[:start], []byte("<meta"))
	tagEndRelative := bytes.IndexByte(document[start:], '>')
	if tagStart < 0 || tagEndRelative < 0 {
		return "", errors.New("invalid meta tag")
	}
	tag := document[tagStart : start+tagEndRelative]
	contentMarker := []byte(`content="`)
	contentStart := bytes.Index(tag, contentMarker)
	if contentStart < 0 {
		return "", errors.New("meta content not found")
	}
	contentStart += len(contentMarker)
	contentEnd := bytes.IndexByte(tag[contentStart:], '"')
	if contentEnd < 0 {
		return "", errors.New("invalid meta content")
	}
	return string(tag[contentStart : contentStart+contentEnd]), nil
}
