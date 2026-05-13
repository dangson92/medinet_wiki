package main

import (
	"context"
	"fmt"
	"os"
	"strings"
	"github.com/medinet/hub-all-backend/internal/rag/extractor"
)

func main() {
	path := "d:/ChuongNV_Medinet/AI/medinet_wiki/Hub_All/file_test/tri_thuc_chinh_tri.pdf"
	if len(os.Args) > 1 { path = os.Args[1] }
	ext, _ := extractor.ForType("pdf")
	text, _ := ext.Extract(context.Background(), path)
	
	// Find "cốt" in raw text
	idx := strings.Index(text, "cốt")
	if idx >= 0 {
		start := idx
		end := idx + 30
		if end > len(text) { end = len(text) }
		fmt.Printf("RAW around 'cốt': [%s]\n", text[start:end])
		// Show hex
		for i := start; i < end && i < len(text); i++ {
			fmt.Printf("%02x ", text[i])
		}
		fmt.Println()
	}
}
