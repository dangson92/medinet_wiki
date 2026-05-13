package extractor

import (
	"context"
	"fmt"
	"os"
	"regexp"
	"strings"
)

// HTMLExtractor handles HTML files by stripping tags to extract plain text.
type HTMLExtractor struct{}

func (e *HTMLExtractor) SupportedType() string {
	return ".html"
}

var (
	// reScript removes <script>...</script> blocks.
	reScript = regexp.MustCompile(`(?is)<script[^>]*>.*?</script>`)
	// reStyle removes <style>...</style> blocks.
	reStyle = regexp.MustCompile(`(?is)<style[^>]*>.*?</style>`)
	// reBlockTag replaces block-level closing tags with newlines.
	reBlockTag = regexp.MustCompile(`(?i)</(?:p|div|br|h[1-6]|li|tr|blockquote|section|article|header|footer)>`)
	// reTag removes all remaining HTML tags.
	reTag = regexp.MustCompile(`<[^>]+>`)
	// reMultiNewline collapses multiple blank lines.
	reMultiNewline = regexp.MustCompile(`\n{3,}`)
	// reHTMLEntity handles common HTML entities.
	htmlEntities = strings.NewReplacer(
		"&amp;", "&",
		"&lt;", "<",
		"&gt;", ">",
		"&quot;", `"`,
		"&#39;", "'",
		"&apos;", "'",
		"&nbsp;", " ",
	)
)

func (e *HTMLExtractor) Extract(_ context.Context, filePath string) (string, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return "", fmt.Errorf("html extractor: failed to read %q: %w", filePath, err)
	}

	text := string(data)

	// Remove script and style blocks.
	text = reScript.ReplaceAllString(text, "")
	text = reStyle.ReplaceAllString(text, "")

	// Replace block-level closing tags with newlines.
	text = reBlockTag.ReplaceAllString(text, "\n")

	// Strip all remaining tags.
	text = reTag.ReplaceAllString(text, "")

	// Decode common HTML entities.
	text = htmlEntities.Replace(text)

	// Collapse excessive blank lines and trim.
	text = reMultiNewline.ReplaceAllString(text, "\n\n")
	text = strings.TrimSpace(text)

	return text, nil
}
