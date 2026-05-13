package storage

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// LocalStorage implements FileStorage using the local filesystem.
type LocalStorage struct {
	baseDir string
}

func NewLocal(baseDir string) *LocalStorage {
	return &LocalStorage{baseDir: baseDir}
}

func (l *LocalStorage) Upload(ctx context.Context, folder, filename string, reader io.Reader) (string, error) {
	dir := filepath.Join(l.baseDir, folder)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", fmt.Errorf("create dir: %w", err)
	}

	path := filepath.Join(dir, filename)
	f, err := os.Create(path)
	if err != nil {
		return "", fmt.Errorf("create file: %w", err)
	}
	defer f.Close()

	if _, err := io.Copy(f, reader); err != nil {
		return "", fmt.Errorf("write file: %w", err)
	}

	return path, nil
}

func (l *LocalStorage) Download(ctx context.Context, remoteID string) (io.ReadCloser, error) {
	f, err := os.Open(remoteID)
	if err != nil {
		return nil, fmt.Errorf("open file: %w", err)
	}
	return f, nil
}

func (l *LocalStorage) Delete(ctx context.Context, remoteID string) error {
	dir := filepath.Dir(remoteID)
	return os.RemoveAll(dir)
}

func (l *LocalStorage) GetURL(ctx context.Context, remoteID string) (string, error) {
	return "file://" + remoteID, nil
}
