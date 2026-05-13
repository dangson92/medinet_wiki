package main

import (
	"fmt"
	"os"

	"github.com/medinet/hub-all-backend/internal/pkg/hash"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: hashpw <password>")
		os.Exit(1)
	}
	h, err := hash.HashPassword(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
	fmt.Println(h)
}
