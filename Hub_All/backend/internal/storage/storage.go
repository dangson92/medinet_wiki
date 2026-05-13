package storage

import (
	"context"
	"io"
)

// FileStorage is the interface for file storage backends.
type FileStorage interface {
	// Upload stores a file and returns its remote path/ID.
	Upload(ctx context.Context, folder, filename string, reader io.Reader) (remoteID string, err error)

	// Download returns a reader for the file content.
	Download(ctx context.Context, remoteID string) (io.ReadCloser, error)

	// Delete removes a file from storage.
	Delete(ctx context.Context, remoteID string) error

	// GetURL returns a viewable/download URL for the file (if supported).
	GetURL(ctx context.Context, remoteID string) (string, error)
}
