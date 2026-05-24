/**
 * Phase 3 v3.1 FE-02 — Layout sidebar hub switcher filter test
 * Source: .planning/phases/03-frontend-form-refactor/03-UI-SPEC.md §9.2 Test 2
 *         .planning/phases/03-frontend-form-refactor/03-PATTERNS.md section 8
 *         carry forward Phase 5 Layout.spec.tsx renderLayoutWithCurrentHub helper
 */
import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const MOCK_HUBS = [
  { id: 'c', code: 'central', name: 'Trung tâm', status: 'active' },
  { id: '1', code: 'dmd', name: 'Đỗ Minh Đường', status: 'active' },
  { id: '2', code: 'tdt', name: 'Thuốc Dân Tộc', status: 'active' },
];

async function renderLayoutWithUser(opts: {
  currentRole: 'admin' | 'hub_admin' | 'viewer';
  userHubIds: string[];
}) {
  vi.resetModules();
  // window.location pathname for CURRENT_HUB resolve
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      pathname: '/',
      href: 'http://localhost/',
      origin: 'http://localhost',
    },
    writable: true,
  });

  vi.doMock('../contexts/AuthContext', () => ({
    useAuth: () => ({
      isAuthenticated: true,
      user: {
        user: {
          id: 'u1',
          name: 'Test User',
          email: 't@medinet.vn',
          role: opts.currentRole,
          status: 'active',
          failed_login_count: 0,
          created_at: '2026-01-01',
          updated_at: '2026-01-01',
        },
        roles: opts.userHubIds.map((hid) => ({ user_id: 'u1', hub_id: hid, role: opts.currentRole })),
      },
      logout: vi.fn(),
      isLoading: false,
      login: vi.fn(),
      refreshUser: vi.fn(),
    }),
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }));

  vi.doMock('../contexts/ThemeContext', () => ({
    useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }),
    ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }));

  vi.doMock('../components/GeminiAssistant', () => ({ default: () => null }));

  vi.doMock('../services/api', async () => {
    const actual = await vi.importActual<typeof import('../services/api')>('../services/api');
    return {
      ...actual,
      api: { ...actual.api, getHubs: vi.fn().mockResolvedValue({ success: true, data: MOCK_HUBS }) },
    };
  });

  const { default: Layout } = await import('../Layout');
  return render(<MemoryRouter><Layout /></MemoryRouter>);
}

describe('Phase 3 v3.1 FE-02 — Layout sidebar hub switcher filter', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
  });

  it('super admin → switcher show ALL hub (central + dmd + tdt)', async () => {
    await renderLayoutWithUser({ currentRole: 'admin', userHubIds: [] });
    await waitFor(() => {
      expect(screen.queryByLabelText(/Chọn hub đang xem/)).toBeTruthy();
    });
    const options = document.querySelectorAll('#hub-switcher option');
    const optionValues = Array.from(options).map((o) => (o as HTMLOptionElement).value);
    expect(optionValues).toContain('central');
    expect(optionValues).toContain('dmd');
    expect(optionValues).toContain('tdt');
  });

  it('hub_admin dmd → switcher CHỈ show dmd (filter central + tdt)', async () => {
    await renderLayoutWithUser({ currentRole: 'hub_admin', userHubIds: ['1'] });
    await waitFor(() => {
      expect(screen.queryByLabelText(/Chọn hub đang xem/)).toBeTruthy();
    });
    const options = document.querySelectorAll('#hub-switcher option');
    const optionValues = Array.from(options).map((o) => (o as HTMLOptionElement).value);
    expect(optionValues).toContain('dmd');
    expect(optionValues).not.toContain('central');
    expect(optionValues).not.toContain('tdt');
  });

  it('viewer với userHubIds=[] → empty state "Bạn chưa được gán hub nào — liên hệ admin."', async () => {
    await renderLayoutWithUser({ currentRole: 'viewer', userHubIds: [] });
    await waitFor(() => {
      expect(screen.queryByText(/Bạn chưa được gán hub nào/)).toBeTruthy();
    });
  });
});
