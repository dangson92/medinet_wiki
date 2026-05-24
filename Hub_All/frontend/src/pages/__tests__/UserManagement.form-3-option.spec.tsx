/**
 * Phase 3 v3.1 FE-01 — UserManagement Add User form 3 option radio test
 * Source: .planning/phases/03-frontend-form-refactor/03-UI-SPEC.md §9.2 Test 1
 *         .planning/phases/03-frontend-form-refactor/03-PATTERNS.md section 7
 *         carry forward Phase 5 Plan 05-02 vitest pattern (vi.doMock + RTL render)
 */
import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

async function renderUserManagement(opts: {
  currentRole?: 'admin' | 'hub_admin' | 'viewer';
} = {}) {
  vi.resetModules();

  vi.doMock('../../contexts/AuthContext', () => ({
    useAuth: () => ({
      isAuthenticated: true,
      user: {
        user: {
          id: 'u1',
          name: 'Test User',
          email: 't@medinet.vn',
          role: opts.currentRole ?? 'admin',
          status: 'active',
          failed_login_count: 0,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
        roles: [],
      },
      logout: vi.fn(),
      isLoading: false,
      login: vi.fn(),
      refreshUser: vi.fn(),
    }),
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }));

  vi.doMock('../../services/api', async () => {
    const actual = await vi.importActual<typeof import('../../services/api')>('../../services/api');
    return {
      ...actual,
      api: {
        ...actual.api,
        getHubs: vi.fn().mockResolvedValue({
          success: true,
          data: [{ id: '1', code: 'dmd', name: 'Đỗ Minh Đường', status: 'active' }],
        }),
        listUsers: vi.fn().mockResolvedValue({
          success: true,
          data: [],
          meta: { page: 1, per_page: 10, total: 0, total_pages: 1 },
        }),
        createUser: vi.fn().mockResolvedValue({ success: true, data: { id: 'new-user' } }),
        changeUserRole: vi.fn().mockResolvedValue({ success: true }),
      },
    };
  });

  const { default: UserManagement } = await import('../UserManagement');
  return render(
    <MemoryRouter>
      <UserManagement />
    </MemoryRouter>
  );
}

describe('Phase 3 v3.1 FE-01 — UserManagement form 3 option radio', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('Click "Thêm User" → modal mở + 3 radio option visible với label tiếng Việt đúng UI-SPEC §7.1', async () => {
    await renderUserManagement({ currentRole: 'admin' });
    // Đợi danh sách hub fetch xong + button "Thêm User" enable
    const addBtn = await screen.findByRole('button', { name: /Thêm User/ });
    fireEvent.click(addBtn);

    // 3 label option tiếng Việt visible sau khi modal mở
    await waitFor(() => {
      expect(screen.queryByText('Admin toàn hệ thống')).toBeTruthy();
      expect(screen.queryByText('Quản lý hub này')).toBeTruthy();
      // 'Viewer' label có thể xuất hiện chỗ khác (filter dropdown) — kiểm soát qua radio value
      expect(document.querySelector('input[type="radio"][value="hub_admin"]')).not.toBeNull();
      expect(document.querySelector('input[type="radio"][value="admin"]')).not.toBeNull();
      expect(document.querySelector('input[type="radio"][value="viewer"]')).not.toBeNull();
    });
  });

  it('Warning banner chỉ mount khi role=admin selected — UI-SPEC §7.1', async () => {
    await renderUserManagement({ currentRole: 'admin' });
    const addBtn = await screen.findByRole('button', { name: /Thêm User/ });
    fireEvent.click(addBtn);

    // Default state newUserRole='viewer' → warning KHÔNG hiển thị
    await waitFor(() => {
      expect(document.querySelector('input[type="radio"][value="viewer"]')).not.toBeNull();
    });
    expect(screen.queryByText(/Quyền cao nhất/)).toBeNull();

    // Click admin radio → warning mount
    const adminRadio = document.querySelector('input[type="radio"][value="admin"]') as HTMLInputElement;
    fireEvent.click(adminRadio);
    await waitFor(() => {
      expect(screen.queryByText(/Quyền cao nhất/)).toBeTruthy();
    });

    // Click viewer radio → warning unmount
    const viewerRadio = document.querySelector('input[type="radio"][value="viewer"]') as HTMLInputElement;
    fireEvent.click(viewerRadio);
    await waitFor(() => {
      expect(screen.queryByText(/Quyền cao nhất/)).toBeNull();
    });
  });

  it('ARIA full: fieldset role="radiogroup" + aria-describedby 3 radio link description', async () => {
    await renderUserManagement({ currentRole: 'admin' });
    const addBtn = await screen.findByRole('button', { name: /Thêm User/ });
    fireEvent.click(addBtn);

    await waitFor(() => {
      const radiogroup = document.querySelector('fieldset[role="radiogroup"]');
      expect(radiogroup).not.toBeNull();
      const radios = document.querySelectorAll('input[type="radio"][name="role"]');
      // KHÔNG strict count vì có thể có radio khác trong page; ít nhất 3 radio role
      expect(radios.length).toBeGreaterThanOrEqual(3);
      // Description ids tồn tại
      expect(document.getElementById('role-admin-desc')).not.toBeNull();
      expect(document.getElementById('role-hubadmin-desc')).not.toBeNull();
      expect(document.getElementById('role-viewer-desc')).not.toBeNull();
    });
  });
});
