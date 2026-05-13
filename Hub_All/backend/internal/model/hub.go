package model

import (
	"time"

	"github.com/google/uuid"
)

type Hub struct {
	ID                uuid.UUID  `json:"id"`
	Name              string     `json:"name"`
	Code              string     `json:"code"`
	Subdomain         string     `json:"subdomain"`
	Description       *string    `json:"description,omitempty"`
	DBHost            *string    `json:"db_host,omitempty"`
	DBPort            int        `json:"db_port"`
	DBName            *string    `json:"db_name,omitempty"`
	DBUser            *string    `json:"db_user,omitempty"`
	DBPasswordEnc     *string    `json:"-"` // never expose
	ChromaCollection  string     `json:"chroma_collection"`
	Status            string     `json:"status"`
	CreatedAt         time.Time  `json:"created_at"`
	UpdatedAt         time.Time  `json:"updated_at"`
}

type CreateHubRequest struct {
	Name             string  `json:"name" binding:"required"`
	Code             string  `json:"code" binding:"required"`
	Subdomain        string  `json:"subdomain" binding:"required"`
	Description      *string `json:"description"`
	DBHost           *string `json:"db_host"`
	DBPort           int     `json:"db_port"`
	DBName           *string `json:"db_name"`
	DBUser           *string `json:"db_user"`
	DBPassword       *string `json:"db_password"`
	ChromaCollection string  `json:"chroma_collection" binding:"required"`
}

type UpdateHubRequest struct {
	Name        *string `json:"name"`
	Description *string `json:"description"`
	DBHost      *string `json:"db_host"`
	DBPort      *int    `json:"db_port"`
	DBName      *string `json:"db_name"`
	DBUser      *string `json:"db_user"`
	DBPassword  *string `json:"db_password"`
}

type UpdateHubStatusRequest struct {
	Status string `json:"status" binding:"required"`
}
