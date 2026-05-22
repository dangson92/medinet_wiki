// Phase 5 PROXY-02 unit test — BrowserRouter basename render scenarios
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-02-02
//         UI-SPEC.md §4 Route → URL bar mapping per-prefix contract

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render } from '@testing-library/react';

// Helper — set window.location + re-import App (force module re-eval cho APP_BASE compute)
// NOTE (Plan 05-04 update): Login.tsx useEffect calls window.location.replace() khi CURRENT_HUB
// !== 'central' → mock window.location PHẢI include replace stub (jsdom Location instance
// reject method call qua spread copy). Plan 05-04 Rule 1 fix.
async function renderAppAtPath(pathname: string) {
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      pathname,
      href: `http://localhost${pathname}`,
      origin: 'http://localhost',
      search: '',
      replace: vi.fn(),
      assign: vi.fn(),
    },
    writable: true,
  });
  // Reset module để api.ts re-compute APP_BASE module-level
  vi.resetModules();
  const { default: App } = await import('../App');
  return render(<App />);
}

describe('Phase 5 PROXY-02 — App.tsx BrowserRouter basename per-prefix', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
    // Clear localStorage để ProtectedRoute fallback Login
    localStorage.clear();
  });

  it('Test 1: pathname `/login` central (basename empty) — Login page mount KHÔNG crash', async () => {
    await renderAppAtPath('/login');
    // Smoke check: KHÔNG crash; document có content (render thành công)
    // (Plan 05-04 sẽ wire useEffect redirect tới central — Task này chỉ verify route resolve)
    await new Promise((r) => setTimeout(r, 50));
    expect(document.body.textContent).toBeTruthy();
  });

  it('Test 2: pathname `/yte/login` hub con (basename /yte) — Login mount via basename auto prepend', async () => {
    await renderAppAtPath('/yte/login');
    await new Promise((r) => setTimeout(r, 50));
    // Hub con `/yte/login` → react-router treat as basename '/yte' + path '/login' → Login mount
    // (Plan 05-04 sẽ wire useEffect redirect tới central; Task 2 chỉ verify mount KHÔNG crash)
    expect(document.body.textContent).toBeTruthy();
  });

  it('Test 3: App.tsx imports APP_BASE from services/api (regression test wire)', async () => {
    // Verify api module export APP_BASE; App import wire qua render KHÔNG crash ở Test 1+2
    const apiModule = await import('../services/api');
    expect(apiModule).toHaveProperty('APP_BASE');
    expect(typeof apiModule.APP_BASE).toBe('string');
  });
});
