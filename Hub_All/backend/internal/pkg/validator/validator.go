package validator

import (
	"fmt"
	"net/mail"
	"strings"
	"unicode"
)

// ValidateEmail checks if the email is valid.
func ValidateEmail(email string) error {
	if email == "" {
		return fmt.Errorf("email is required")
	}
	if _, err := mail.ParseAddress(email); err != nil {
		return fmt.Errorf("invalid email format")
	}
	return nil
}

// ValidatePassword checks password strength:
// - At least 8 characters
// - At least 1 uppercase, 1 lowercase, 1 digit, 1 special char
func ValidatePassword(password string) error {
	if len(password) < 8 {
		return fmt.Errorf("password must be at least 8 characters")
	}

	var hasUpper, hasLower, hasDigit, hasSpecial bool
	for _, c := range password {
		switch {
		case unicode.IsUpper(c):
			hasUpper = true
		case unicode.IsLower(c):
			hasLower = true
		case unicode.IsDigit(c):
			hasDigit = true
		case unicode.IsPunct(c) || unicode.IsSymbol(c):
			hasSpecial = true
		}
	}

	if !hasUpper {
		return fmt.Errorf("password must contain at least 1 uppercase letter")
	}
	if !hasLower {
		return fmt.Errorf("password must contain at least 1 lowercase letter")
	}
	if !hasDigit {
		return fmt.Errorf("password must contain at least 1 digit")
	}
	if !hasSpecial {
		return fmt.Errorf("password must contain at least 1 special character")
	}

	return nil
}

// ValidateRequired checks that a string field is not empty.
func ValidateRequired(field, name string) error {
	if strings.TrimSpace(field) == "" {
		return fmt.Errorf("%s is required", name)
	}
	return nil
}

// ValidateMaxLength checks that a string field does not exceed max length.
func ValidateMaxLength(field, name string, max int) error {
	if len(field) > max {
		return fmt.Errorf("%s must be at most %d characters", name, max)
	}
	return nil
}

// ValidateHubCode checks that hub code is valid (alphanumeric + underscore, lowercase).
func ValidateHubCode(code string) error {
	if code == "" {
		return fmt.Errorf("hub code is required")
	}
	if len(code) > 50 {
		return fmt.Errorf("hub code must be at most 50 characters")
	}
	for _, c := range code {
		if !unicode.IsLower(c) && !unicode.IsDigit(c) && c != '_' {
			return fmt.Errorf("hub code must contain only lowercase letters, digits, and underscores")
		}
	}
	return nil
}
