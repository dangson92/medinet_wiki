package extractor

import (
	"archive/zip"
	"context"
	"encoding/xml"
	"fmt"
	"io"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// PptxExtractor extracts structured Markdown from PPTX files.
// Each slide becomes a section with slide number and title context.
type PptxExtractor struct{}

func (e *PptxExtractor) SupportedType() string { return ".pptx" }

var slideFilePattern = regexp.MustCompile(`^ppt/slides/slide(\d+)\.xml$`)

func (e *PptxExtractor) Extract(_ context.Context, filePath string) (string, error) {
	r, err := zip.OpenReader(filePath)
	if err != nil {
		return "", fmt.Errorf("pptx: open zip: %w", err)
	}
	defer r.Close()

	type slideEntry struct {
		number int
		file   *zip.File
	}
	var slides []slideEntry
	for _, f := range r.File {
		matches := slideFilePattern.FindStringSubmatch(f.Name)
		if matches != nil {
			num, _ := strconv.Atoi(matches[1])
			slides = append(slides, slideEntry{number: num, file: f})
		}
	}
	sort.Slice(slides, func(i, j int) bool { return slides[i].number < slides[j].number })

	var result strings.Builder
	totalSlides := len(slides)

	for _, s := range slides {
		rc, err := s.file.Open()
		if err != nil {
			continue
		}
		texts := parsePptxParagraphs(rc)
		rc.Close()

		if len(texts) == 0 {
			continue
		}

		// First non-empty text = slide title
		title := texts[0]
		body := texts[1:]

		result.WriteString(fmt.Sprintf("## Slide %d/%d: %s\n\n", s.number, totalSlides, title))
		for _, t := range body {
			t = strings.TrimSpace(t)
			if t != "" {
				result.WriteString(t)
				result.WriteString("\n\n")
			}
		}
	}

	text := strings.TrimSpace(result.String())
	if text == "" {
		return "", fmt.Errorf("pptx: no text extracted from %q", filePath)
	}
	return text, nil
}

func parsePptxParagraphs(r io.Reader) []string {
	decoder := xml.NewDecoder(r)
	const nsA = "http://schemas.openxmlformats.org/drawingml/2006/main"

	var paragraphs []string
	var current strings.Builder
	inText := false

	for {
		tok, err := decoder.Token()
		if err != nil {
			break
		}
		switch t := tok.(type) {
		case xml.StartElement:
			if t.Name.Local == "p" && t.Name.Space == nsA {
				if current.Len() > 0 {
					paragraphs = append(paragraphs, current.String())
					current.Reset()
				}
			}
			if t.Name.Local == "t" && t.Name.Space == nsA {
				inText = true
			}
		case xml.EndElement:
			if t.Name.Local == "t" && t.Name.Space == nsA {
				inText = false
			}
		case xml.CharData:
			if inText {
				current.Write(t)
			}
		}
	}
	if current.Len() > 0 {
		paragraphs = append(paragraphs, current.String())
	}
	return paragraphs
}
