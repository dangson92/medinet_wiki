package storage

import (
	"context"
	"fmt"
	"io"

	"google.golang.org/api/drive/v3"
	"google.golang.org/api/option"
)

// GDriveStorage implements FileStorage using Google Drive API with a Service Account.
type GDriveStorage struct {
	service  *drive.Service
	rootFolder string // Parent folder ID where all files are stored
}

// NewGDrive creates a Google Drive storage client.
// credentialsFile: path to service account JSON key
// rootFolderID: Google Drive folder ID to store files in
func NewGDrive(credentialsFile, rootFolderID string) (*GDriveStorage, error) {
	ctx := context.Background()
	srv, err := drive.NewService(ctx, option.WithCredentialsFile(credentialsFile))
	if err != nil {
		return nil, fmt.Errorf("create drive service: %w", err)
	}

	return &GDriveStorage{
		service:    srv,
		rootFolder: rootFolderID,
	}, nil
}

// Upload stores a file in Google Drive under rootFolder/folder/filename.
// Returns the Google Drive file ID.
func (g *GDriveStorage) Upload(ctx context.Context, folder, filename string, reader io.Reader) (string, error) {
	// Find or create the sub-folder
	folderID, err := g.findOrCreateFolder(ctx, folder, g.rootFolder)
	if err != nil {
		return "", fmt.Errorf("find/create folder %q: %w", folder, err)
	}

	// Upload file
	file := &drive.File{
		Name:    filename,
		Parents: []string{folderID},
	}

	created, err := g.service.Files.Create(file).
		Context(ctx).
		Media(reader).
		Fields("id").
		Do()
	if err != nil {
		return "", fmt.Errorf("upload file: %w", err)
	}

	return created.Id, nil
}

// Download returns a reader for a file stored in Google Drive.
func (g *GDriveStorage) Download(ctx context.Context, remoteID string) (io.ReadCloser, error) {
	resp, err := g.service.Files.Get(remoteID).Context(ctx).Download()
	if err != nil {
		return nil, fmt.Errorf("download file: %w", err)
	}
	return resp.Body, nil
}

// Delete removes a file from Google Drive.
func (g *GDriveStorage) Delete(ctx context.Context, remoteID string) error {
	if err := g.service.Files.Delete(remoteID).Context(ctx).Do(); err != nil {
		return fmt.Errorf("delete file: %w", err)
	}
	return nil
}

// GetURL returns a web view URL for the file.
func (g *GDriveStorage) GetURL(ctx context.Context, remoteID string) (string, error) {
	file, err := g.service.Files.Get(remoteID).Context(ctx).Fields("webViewLink").Do()
	if err != nil {
		return "", fmt.Errorf("get file URL: %w", err)
	}
	return file.WebViewLink, nil
}

// findOrCreateFolder finds a folder by name under parent, or creates it.
func (g *GDriveStorage) findOrCreateFolder(ctx context.Context, name, parentID string) (string, error) {
	// Search for existing folder
	q := fmt.Sprintf("name='%s' and '%s' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false", name, parentID)
	list, err := g.service.Files.List().Context(ctx).Q(q).Fields("files(id)").PageSize(1).Do()
	if err != nil {
		return "", fmt.Errorf("search folder: %w", err)
	}
	if len(list.Files) > 0 {
		return list.Files[0].Id, nil
	}

	// Create new folder
	folder := &drive.File{
		Name:     name,
		MimeType: "application/vnd.google-apps.folder",
		Parents:  []string{parentID},
	}
	created, err := g.service.Files.Create(folder).Context(ctx).Fields("id").Do()
	if err != nil {
		return "", fmt.Errorf("create folder: %w", err)
	}
	return created.Id, nil
}
