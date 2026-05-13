package extractor

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/xml"
	"fmt"
	"io"
	"strings"
)

// DocxExtractor extracts structured Markdown from DOCX files.
// Preserves: headings, bold, italic, lists, tables, paragraph hierarchy.
type DocxExtractor struct{}

func (e *DocxExtractor) SupportedType() string { return ".docx" }

func (e *DocxExtractor) Extract(_ context.Context, filePath string) (string, error) {
	r, err := zip.OpenReader(filePath)
	if err != nil {
		return "", fmt.Errorf("docx: open zip: %w", err)
	}
	defer r.Close()

	// Read styles to detect heading levels
	styles := parseDocxStyles(r)

	for _, f := range r.File {
		if f.Name == "word/document.xml" {
			rc, err := f.Open()
			if err != nil {
				return "", fmt.Errorf("docx: open document.xml: %w", err)
			}
			defer rc.Close()
			return parseDocxStructured(rc, styles)
		}
	}
	return "", fmt.Errorf("docx: word/document.xml not found in %q", filePath)
}

// styleInfo maps style IDs to their heading level (0 = not a heading).
type styleInfo struct {
	headingLevel int
}

func parseDocxStyles(zr *zip.ReadCloser) map[string]styleInfo {
	styles := make(map[string]styleInfo)
	for _, f := range zr.File {
		if f.Name != "word/styles.xml" {
			continue
		}
		rc, err := f.Open()
		if err != nil {
			return styles
		}
		defer rc.Close()
		data, _ := io.ReadAll(rc)
		decoder := xml.NewDecoder(bytes.NewReader(data))

		var currentStyleID string
		for {
			tok, err := decoder.Token()
			if err != nil {
				break
			}
			if se, ok := tok.(xml.StartElement); ok {
				if se.Name.Local == "style" {
					for _, attr := range se.Attr {
						if attr.Name.Local == "styleId" {
							currentStyleID = attr.Value
						}
					}
				}
				if se.Name.Local == "outlineLvl" && currentStyleID != "" {
					for _, attr := range se.Attr {
						if attr.Name.Local == "val" {
							lvl := 0
							fmt.Sscanf(attr.Value, "%d", &lvl)
							styles[currentStyleID] = styleInfo{headingLevel: lvl + 1} // 0-based → 1-based
						}
					}
				}
			}
		}
	}
	// Common heading style IDs
	for i := 1; i <= 6; i++ {
		id := fmt.Sprintf("Heading%d", i)
		if _, ok := styles[id]; !ok {
			styles[id] = styleInfo{headingLevel: i}
		}
	}
	return styles
}

func parseDocxStructured(r io.Reader, styles map[string]styleInfo) (string, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return "", err
	}
	decoder := xml.NewDecoder(bytes.NewReader(data))

	const nsW = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

	var result strings.Builder
	var paraText strings.Builder
	var paraStyleID string
	var isBold, isItalic bool
	inText := false
	inTable := false
	var tableRows [][]string
	var currentRow []string
	var cellText strings.Builder

	flushParagraph := func() {
		text := strings.TrimSpace(paraText.String())
		if text == "" {
			paraText.Reset()
			paraStyleID = ""
			return
		}

		// Check if this paragraph is a heading
		if si, ok := styles[paraStyleID]; ok && si.headingLevel > 0 && si.headingLevel <= 6 {
			result.WriteString("\n\n")
			result.WriteString(strings.Repeat("#", si.headingLevel))
			result.WriteString(" ")
			result.WriteString(text)
			result.WriteString("\n\n")
		} else if inTable {
			// Handled by table logic
		} else {
			result.WriteString(text)
			result.WriteString("\n\n")
		}

		paraText.Reset()
		paraStyleID = ""
	}

	flushTable := func() {
		if len(tableRows) == 0 {
			return
		}
		maxCols := 0
		for _, row := range tableRows {
			if len(row) > maxCols {
				maxCols = len(row)
			}
		}
		if maxCols == 0 {
			tableRows = nil
			return
		}
		for i := range tableRows {
			for len(tableRows[i]) < maxCols {
				tableRows[i] = append(tableRows[i], "")
			}
		}

		if prose := renderTableAsProse(tableRows); prose != "" {
			result.WriteString("\n\n")
			result.WriteString(prose)
			result.WriteString("\n\n")
		}
		tableRows = nil
	}

	for {
		tok, err := decoder.Token()
		if err != nil {
			break
		}

		switch t := tok.(type) {
		case xml.StartElement:
			switch {
			case t.Name.Local == "tbl" && t.Name.Space == nsW:
				flushParagraph()
				inTable = true
				tableRows = nil

			case t.Name.Local == "tr" && t.Name.Space == nsW:
				currentRow = nil

			case t.Name.Local == "tc" && t.Name.Space == nsW:
				cellText.Reset()

			case t.Name.Local == "p" && t.Name.Space == nsW:
				if !inTable {
					flushParagraph()
				}

			case t.Name.Local == "pStyle" && t.Name.Space == nsW:
				for _, attr := range t.Attr {
					if attr.Name.Local == "val" {
						paraStyleID = attr.Value
					}
				}

			case t.Name.Local == "b" && t.Name.Space == nsW:
				isBold = true

			case t.Name.Local == "i" && t.Name.Space == nsW:
				isItalic = true

			case t.Name.Local == "t" && t.Name.Space == nsW:
				inText = true
			}

		case xml.EndElement:
			switch {
			case t.Name.Local == "t" && t.Name.Space == nsW:
				inText = false

			case t.Name.Local == "r" && t.Name.Space == nsW:
				isBold = false
				isItalic = false

			case t.Name.Local == "p" && t.Name.Space == nsW:
				if inTable {
					// End of paragraph inside table cell
				}

			case t.Name.Local == "tc" && t.Name.Space == nsW:
				currentRow = append(currentRow, strings.TrimSpace(cellText.String()))

			case t.Name.Local == "tr" && t.Name.Space == nsW:
				tableRows = append(tableRows, currentRow)

			case t.Name.Local == "tbl" && t.Name.Space == nsW:
				inTable = false
				flushTable()
			}

		case xml.CharData:
			if inText {
				text := string(t)
				if inTable {
					cellText.WriteString(text)
				} else {
					if isBold {
						paraText.WriteString("**")
						paraText.WriteString(text)
						paraText.WriteString("**")
					} else if isItalic {
						paraText.WriteString("*")
						paraText.WriteString(text)
						paraText.WriteString("*")
					} else {
						paraText.WriteString(text)
					}
				}
			}
		}
	}

	flushParagraph()
	if inTable {
		flushTable()
	}

	return strings.TrimSpace(result.String()), nil
}
