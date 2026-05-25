// Phase 5 PROXY-04 unit test — Layout sidebar branding render
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-04-02
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §3

import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

async function renderLayoutWithCurrentHub(hub: string) {
  vi.resetModules();
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      pathname: hub === 'central' ? '/' : `/${hub}/`,
      href: `http://localhost/${hub === 'central' ? '' : hub + '/'}`,
      origin: 'http://localhost',
    },
    writable: true,
  });

  vi.doMock('../contexts/AuthContext', () => ({
    useAuth: () => ({
      isAuthenticated: true,
      user: { user: { id: 'u1', name: 'Test User', email: 'test@medinet.vn' }, roles: [] },
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

  // Plan 03-03 v3.1 Phase 3 FE-02 — HubSwitcher mới gọi api.getHubs khi mount Layout
  // Mock api.getHubs để tránh unhandled fetch (jsdom KHÔNG resolve relative URL `/yte/api/hubs`).
  // CURRENT_HUB const phải re-export đúng (services/api line 46 compute từ window.location).
  vi.doMock('../services/api', async () => {
    const actual = await vi.importActual<typeof import('../services/api')>('../services/api');
    return {
      ...actual,
      api: { ...actual.api, getHubs: vi.fn().mockResolvedValue({ success: true, data: [] }) },
    };
  });

  const { default: Layout } = await import('../Layout');
  return render(
    <MemoryRouter>
      <Layout />
    </MemoryRouter>
  );
}

describe('Phase 5 PROXY-04 — Layout sidebar branding', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
  });

  it('CURRENT_HUB=central → renders "Medinet Wiki" title in sidebar', async () => {
    await renderLayoutWithCurrentHub('central');
    expect(screen.queryByText(/Medinet Wiki/i)).toBeInTheDocument();
  });

  it('CURRENT_HUB=yte → renders "Hub Y tế Medinet" title in sidebar', async () => {
    await renderLayoutWithCurrentHub('yte');
    expect(screen.queryByText(/Hub Y tế Medinet/i)).toBeInTheDocument();
  });

  it('CURRENT_HUB=duoc → renders "Hub Dược Medinet" title in sidebar', async () => {
    await renderLayoutWithCurrentHub('duoc');
    expect(screen.queryByText(/Hub Dược Medinet/i)).toBeInTheDocument();
  });

  it('Logo img src matches /branding/<hub>/logo.svg schema', async () => {
    await renderLayoutWithCurrentHub('yte');
    const logo = document.querySelector('img[src*="/branding/"]');
    expect(logo).not.toBeNull();
    expect((logo as HTMLImageElement).src).toMatch(/\/branding\/yte\/logo\.svg$/);
  });
});
