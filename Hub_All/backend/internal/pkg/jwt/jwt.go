package jwt

import (
	"crypto/rsa"
	"fmt"
	"os"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

type Claims struct {
	jwt.RegisteredClaims
	Email     string `json:"email"`
	Name      string `json:"name"`
	HubID     string `json:"hub_id,omitempty"`
	Role      string `json:"role"`
	Subdomain string `json:"subdomain,omitempty"`
	TokenType string `json:"token_type"` // "access" or "refresh"
}

type TokenPair struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresAt    int64  `json:"expires_at"`
}

type Manager struct {
	privateKey      *rsa.PrivateKey
	publicKey       *rsa.PublicKey
	accessTokenTTL  time.Duration
	refreshTokenTTL time.Duration
}

func NewManager(privatePath, publicPath string, accessTTL, refreshTTL time.Duration) (*Manager, error) {
	privBytes, err := os.ReadFile(privatePath)
	if err != nil {
		return nil, fmt.Errorf("read private key: %w", err)
	}

	privKey, err := jwt.ParseRSAPrivateKeyFromPEM(privBytes)
	if err != nil {
		return nil, fmt.Errorf("parse private key: %w", err)
	}

	pubBytes, err := os.ReadFile(publicPath)
	if err != nil {
		return nil, fmt.Errorf("read public key: %w", err)
	}

	pubKey, err := jwt.ParseRSAPublicKeyFromPEM(pubBytes)
	if err != nil {
		return nil, fmt.Errorf("parse public key: %w", err)
	}

	return &Manager{
		privateKey:      privKey,
		publicKey:       pubKey,
		accessTokenTTL:  accessTTL,
		refreshTokenTTL: refreshTTL,
	}, nil
}

// NewManagerWithKeys khởi tạo Manager trực tiếp từ cặp khóa RSA in-memory
// (KHÔNG đọc file). Dùng cho integration test (Plan 04-04 W5) — sinh khóa
// runtime qua `rsa.GenerateKey` rồi sign JWT thật cho admin role; production
// không gọi method này (luôn dùng `NewManager` từ file PEM).
func NewManagerWithKeys(privateKey *rsa.PrivateKey, publicKey *rsa.PublicKey, accessTTL, refreshTTL time.Duration) *Manager {
	return &Manager{
		privateKey:      privateKey,
		publicKey:       publicKey,
		accessTokenTTL:  accessTTL,
		refreshTokenTTL: refreshTTL,
	}
}

func (m *Manager) GenerateTokenPair(userID, email, name, hubID, role, subdomain string) (*TokenPair, error) {
	now := time.Now()

	// Access Token
	accessJTI := uuid.New().String()
	accessClaims := Claims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID,
			ExpiresAt: jwt.NewNumericDate(now.Add(m.accessTokenTTL)),
			IssuedAt:  jwt.NewNumericDate(now),
			ID:        accessJTI,
			Issuer:    "medinet-wiki",
		},
		Email:     email,
		Name:      name,
		HubID:     hubID,
		Role:      role,
		Subdomain: subdomain,
		TokenType: "access",
	}

	accessToken, err := jwt.NewWithClaims(jwt.SigningMethodRS256, accessClaims).SignedString(m.privateKey)
	if err != nil {
		return nil, fmt.Errorf("sign access token: %w", err)
	}

	// Refresh Token
	refreshJTI := uuid.New().String()
	refreshClaims := Claims{
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID,
			ExpiresAt: jwt.NewNumericDate(now.Add(m.refreshTokenTTL)),
			IssuedAt:  jwt.NewNumericDate(now),
			ID:        refreshJTI,
			Issuer:    "medinet-wiki",
		},
		Email:     email,
		Name:      name,
		TokenType: "refresh",
	}

	refreshToken, err := jwt.NewWithClaims(jwt.SigningMethodRS256, refreshClaims).SignedString(m.privateKey)
	if err != nil {
		return nil, fmt.Errorf("sign refresh token: %w", err)
	}

	return &TokenPair{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		ExpiresAt:    now.Add(m.accessTokenTTL).Unix(),
	}, nil
}

func (m *Manager) VerifyToken(tokenStr string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &Claims{}, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return m.publicKey, nil
	})
	if err != nil {
		return nil, fmt.Errorf("parse token: %w", err)
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, fmt.Errorf("invalid token claims")
	}

	return claims, nil
}

func (m *Manager) AccessTokenTTL() time.Duration {
	return m.accessTokenTTL
}

func (m *Manager) RefreshTokenTTL() time.Duration {
	return m.refreshTokenTTL
}
