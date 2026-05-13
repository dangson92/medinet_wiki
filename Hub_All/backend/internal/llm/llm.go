package llm

import "context"

// LLM is the interface for language model providers.
type LLM interface {
	// Generate sends a prompt and returns the generated text.
	Generate(ctx context.Context, prompt string) (string, error)
	// Name returns the provider/model name.
	Name() string
}

// FallbackLLM tries primary LLM first, falls back to secondary on error.
type FallbackLLM struct {
	Primary   LLM
	Secondary LLM
}

func (f *FallbackLLM) Generate(ctx context.Context, prompt string) (string, error) {
	result, err := f.Primary.Generate(ctx, prompt)
	if err == nil {
		return result, nil
	}
	if f.Secondary != nil {
		return f.Secondary.Generate(ctx, prompt)
	}
	return "", err
}

func (f *FallbackLLM) Name() string {
	return f.Primary.Name() + " (fallback: " + f.Secondary.Name() + ")"
}
