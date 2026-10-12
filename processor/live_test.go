package main

import (
	"context"
	"encoding/json"
	"os"
	"testing"
)

// Explicit opt-in only: uses paid cloud APIs and a caller-selected PDF page.
func TestLiveCloud(t *testing.T) {
	keyPath, pdfPath := os.Getenv("PROCESSOR_TEST_CREDENTIALS"), os.Getenv("PROCESSOR_TEST_PDF")
	if keyPath == "" || pdfPath == "" {
		t.Skip("live cloud test not requested")
	}
	keyData, err := os.ReadFile(keyPath)
	if err != nil {
		t.Fatal(err)
	}
	var keys Credentials
	if err = json.Unmarshal(keyData, &keys); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(pdfPath)
	if err != nil {
		t.Fatal(err)
	}
	c := newCloud(keys)
	defer c.CloseSession()
	var source Source
	if cached := os.Getenv("PROCESSOR_TEST_VISION_RESPONSE"); cached != "" {
		raw, readErr := os.ReadFile(cached)
		if readErr != nil {
			t.Fatal(readErr)
		}
		var response struct {
			Responses []struct{ Responses []VisionResult }
		}
		if err = json.Unmarshal(raw, &response); err != nil {
			t.Fatal(err)
		}
		source, err = visionSource(response.Responses[0].Responses[0].Annotation.Pages[0])
	} else {
		source, err = c.OCR(context.Background(), data)
	}
	if err != nil {
		t.Fatal(err)
	}
	if len(source.Characters) == 0 {
		t.Fatal("no Chinese recognized")
	}
	page, err := c.Annotate(context.Background(), source)
	if err != nil {
		t.Fatal(err)
	}
	if len(page.Words) == 0 || len(page.Sentences) == 0 {
		t.Fatal("empty annotation")
	}
	t.Logf("Live OCR and annotation: %d characters, %d words, %d translated segments", len(source.Characters), len(page.Words), len(page.Sentences))
	if out := os.Getenv("PROCESSOR_TEST_OUTPUT"); out != "" {
		if err := atomicJSON(out, page); err != nil {
			t.Fatal(err)
		}
	}
}
