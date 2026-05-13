package main

import (
	"fmt"

	"github.com/medinet/hub-all-backend/internal/rag/chunker"
)

func main() {
	samples := []struct {
		name string
		text string
	}{
		{"Short VN", "Tri thức chính trị là gì"},
		{"Medium VN", "Phác đồ trị đau dạ dày bằng bài thuốc Bình Vị Tán kết hợp châm cứu các huyệt Trung Quản"},
		{"Long VN", "Tri thức chính trị là một trong những nền tảng cốt lõi của một xã hội dân chủ, văn minh và phát triển bền vững. Bài báo này phân tích khái niệm tri thức chính trị, vai trò của nó trong đời sống công dân, cũng như những thách thức và cơ hội trong việc nâng cao tri thức chính trị ở Việt Nam."},
		{"English", "The quick brown fox jumps over the lazy dog. This is a sample English sentence for token counting comparison."},
	}

	for _, s := range samples {
		tokens := chunker.CountTokens(s.text)
		chars := len([]rune(s.text))
		words := 0
		inWord := false
		for _, r := range s.text {
			if r == ' ' || r == '\n' {
				if inWord { words++; inWord = false }
			} else {
				inWord = true
			}
		}
		if inWord { words++ }

		fmt.Printf("%-12s | %3d chars | %2d words | %3d tokens (tiktoken) | ratio: %.1f chars/token\n",
			s.name, chars, words, tokens, float64(chars)/float64(tokens))
	}

	fmt.Printf("\nTokensToChars(512) = %d chars\n", chunker.TokensToChars(512))
	fmt.Printf("TokensToChars(50)  = %d chars\n", chunker.TokensToChars(50))
}
