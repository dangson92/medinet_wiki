// Phase 5 PROXY-02 + PROXY-04 unit test — Login 4 state machine + T-5-04 mitigation
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-04-01
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §2

import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock react-router useSearchParams — dynamic per test via window.location.search
async function renderLoginAtUrl(opts: { pathname: string; search?: string }) {
  vi.resetModules();
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      pathname: opts.pathname,
      search: opts.search ?? '',
      href: `http://localhost${opts.pathname}${opts.search ?? ''}`,
      origin: 'http://localhost',
      replace: vi.fn(), // spy on window.location.replace
    },
    writable: true,
  });

  // Mock AuthContext - login function returns success
  vi.doMock('../../contexts/AuthContext', () => ({
    useAuth: () => ({
      login: vi.fn().mockResolvedValue({ success: true }),
      isLoading: false,
      isAuthenticated: false,
      logout: vi.fn(),
      refreshUser: vi.fn(),
      user: null,
    }),
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }));

  const { default: Login } = await import('../Login');
  return render(
    <MemoryRouter initialEntries={[`${opts.pathname}${opts.search ?? ''}`]}>
      <Login />
    </MemoryRouter>
  );
}

describe('Phase 5 — Login.tsx UX state machine', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
    localStorage.clear();
  });

  it('State A: central no-return → render Medinet central branding', async () => {
    await renderLoginAtUrl({ pathname: '/login' });
    await waitFor(() => {
      expect(screen.queryAllByText(/Medinet Wiki/i).length).toBeGreaterThan(0);
    });
  });

  it('State B: central with valid return=/yte → render yte branding + chip', async () => {
    await renderLoginAtUrl({ pathname: '/login', search: '?return=/yte' });
    await waitFor(() => {
      expect(screen.queryAllByText(/Hub Y tế Medinet/i).length).toBeGreaterThan(0);
      expect(screen.queryByText(/Sau đăng nhập sẽ vào/i)).toBeInTheDocument();
    });
  });

  it('State D: invalid return=/INVALID_HUB → silent fallback central + no chip', async () => {
    await renderLoginAtUrl({ pathname: '/login', search: '?return=/INVALID_HUB' });
    await waitFor(() => {
      expect(screen.queryAllByText(/Medinet Wiki/i).length).toBeGreaterThan(0);
      expect(screen.queryByText(/Sau đăng nhập sẽ vào/i)).not.toBeInTheDocument();
    });
  });

  it('T-5-04: return=//evil.com (absolute URL injection) → rejected, central fallback', async () => {
    await renderLoginAtUrl({ pathname: '/login', search: '?return=//evil.com' });
    await waitFor(() => {
      expect(screen.queryAllByText(/Medinet Wiki/i).length).toBeGreaterThan(0);
      expect(screen.queryByText(/Sau đăng nhập sẽ vào/i)).not.toBeInTheDocument();
    });
  });

  it('T-5-04: return=/postgres (reserved name) → rejected (not in KNOWN_HUBS), central fallback', async () => {
    await renderLoginAtUrl({ pathname: '/login', search: '?return=/postgres' });
    await waitFor(() => {
      expect(screen.queryAllByText(/Medinet Wiki/i).length).toBeGreaterThan(0);
      expect(screen.queryByText(/Sau đăng nhập sẽ vào/i)).not.toBeInTheDocument();
    });
  });

  it('State C placeholder: hub con direct visit useEffect triggers window.location.replace OR skeleton renders', async () => {
    // Note: jsdom KHÔNG fully simulate window.location.pathname trong React-router context;
    // testing useEffect side-effect spy on window.location.replace mock.
    // Full state-C test reality verify ở manual smoke Plan 05-06.
    await renderLoginAtUrl({ pathname: '/yte/login' });
    // Either redirect was scheduled (CURRENT_HUB !== 'central' branch) OR skeleton text exists
    await waitFor(() => {
      const replaceMock = window.location.replace as ReturnType<typeof vi.fn>;
      const hasRedirect = replaceMock.mock?.calls?.length > 0;
      const hasSkeleton = !!screen.queryByText(/Đang chuyển đến trang đăng nhập trung tâm/i);
      // In jsdom, CURRENT_HUB derives from window.location.pathname which may be /yte/login
      // → useEffect would call replace AND skeleton renders before redirect resolves.
      // Either branch satisfies — both indicate State C handling.
      expect(hasRedirect || hasSkeleton).toBe(true);
    });
  });
});
