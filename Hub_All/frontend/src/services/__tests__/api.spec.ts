// Phase 5 PROXY-02 unit test — prefix detect module-level compute
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-02-01
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md §"Implementation Decisions B1" (D-V3-Phase5-B1 LOCKED)

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Helper — reset module state + re-import api.ts với mock window.location
async function reimportApi(opts: {
  pathname: string;
  hubConfig?: { allowlist: readonly string[]; current?: string };
}) {
  // Reset modules để force re-evaluate module-level compute
  vi.resetModules();

  // Mock window.location.pathname via Object.defineProperty (jsdom)
  Object.defineProperty(window, 'location', {
    value: {
      ...window.location,
      pathname: opts.pathname,
      href: `http://localhost${opts.pathname}`,
      origin: 'http://localhost',
    },
    writable: true,
  });

  // Mock window.__HUB_CONFIG__ if provided
  if (opts.hubConfig) {
    (window as unknown as { __HUB_CONFIG__: typeof opts.hubConfig }).__HUB_CONFIG__ = opts.hubConfig;
  } else {
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
  }

  return await import('../api');
}

describe('Phase 5 PROXY-02 — api.ts prefix detect', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
  });

  it('Test 1: central root pathname `/` → PREFIX=null, API_BASE=/api, APP_BASE=empty, CURRENT_HUB=central', async () => {
    const mod = await reimportApi({ pathname: '/' });
    expect(mod.PREFIX).toBeNull();
    expect(mod.API_BASE).toBe('/api');
    expect(mod.APP_BASE).toBe('');
    expect(mod.CURRENT_HUB).toBe('central');
  });

  it('Test 2: hub prefix `/yte/dashboard` → PREFIX=yte, API_BASE=/yte/api, APP_BASE=/yte, CURRENT_HUB=yte', async () => {
    const mod = await reimportApi({ pathname: '/yte/dashboard' });
    expect(mod.PREFIX).toBe('yte');
    expect(mod.API_BASE).toBe('/yte/api');
    expect(mod.APP_BASE).toBe('/yte');
    expect(mod.CURRENT_HUB).toBe('yte');
  });

  it('Test 3: trailing slash `/duoc/` → PREFIX=duoc (filter(Boolean) drop empty)', async () => {
    const mod = await reimportApi({ pathname: '/duoc/' });
    expect(mod.PREFIX).toBe('duoc');
    expect(mod.APP_BASE).toBe('/duoc');
  });

  it('Test 4: unknown hub `/unknown_hub/x` → PREFIX=null (T-5-02 fallback central — FE allowlist UX only)', async () => {
    const mod = await reimportApi({ pathname: '/unknown_hub/x' });
    expect(mod.PREFIX).toBeNull();
    expect(mod.API_BASE).toBe('/api');
    expect(mod.CURRENT_HUB).toBe('central');
  });

  it('Test 5: runtime __HUB_CONFIG__ override fallback hardcode', async () => {
    const mod = await reimportApi({
      pathname: '/custom_hub/dashboard',
      hubConfig: { allowlist: ['yte', 'custom_hub'] },
    });
    expect(mod.PREFIX).toBe('custom_hub');
    expect(mod.APP_BASE).toBe('/custom_hub');
  });

  it('Test 6: runtime config absent → fallback hardcode [yte, duoc, hcns] still detect yte', async () => {
    const mod = await reimportApi({ pathname: '/yte/profile' });
    expect(mod.PREFIX).toBe('yte');
  });

  it('Test 7: hcns hub (fallback hardcode) → PREFIX=hcns', async () => {
    const mod = await reimportApi({ pathname: '/hcns/' });
    expect(mod.PREFIX).toBe('hcns');
  });
});

// Phase 5 PROXY-02 — api.crossHubSearch ABSOLUTE path override
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-04-03
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §5.1
describe('Phase 5 PROXY-02 — api.crossHubSearch ABSOLUTE path override', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
  });

  it('Test 8: crossHubSearch fetches ABSOLUTE /api/search/cross-hub (NOT ${API_BASE}/search/cross-hub)', async () => {
    // Mock window.location to hub con yte → API_BASE would be /yte/api
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        pathname: '/yte/dashboard',
        href: 'http://localhost/yte/dashboard',
        origin: 'http://localhost',
      },
      writable: true,
    });

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      status: 200,
      json: async () => ({ success: true, data: { results: [], total_hubs_searched: 0, query_time_ms: 10, cache_hit: false } }),
    } as Response);

    vi.resetModules();
    const { api } = await import('../api');
    await api.crossHubSearch({ query: 'test', hub_ids: ['yte'] });

    expect(fetchSpy).toHaveBeenCalled();
    const calledUrl = fetchSpy.mock.calls[0][0];
    // Critical assertion: absolute path /api/search/cross-hub (NOT /yte/api/search/cross-hub)
    expect(calledUrl).toBe('/api/search/cross-hub');
    expect(String(calledUrl)).not.toMatch(/^\/yte\//);

    fetchSpy.mockRestore();
  });

  it('Test 9: crossHubSearch attaches Bearer token if access_token in localStorage', async () => {
    localStorage.setItem('access_token', 'fake-jwt-token');

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      status: 200,
      json: async () => ({ success: true }),
    } as Response);

    vi.resetModules();
    const { api } = await import('../api');
    await api.crossHubSearch({ query: 'test' });

    const fetchOptions = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((fetchOptions.headers as Record<string, string>)['Authorization']).toBe('Bearer fake-jwt-token');

    fetchSpy.mockRestore();
    localStorage.removeItem('access_token');
  });
});

// Phase 5 D-V3-Phase5-C4 — api.tryRefresh redirect: follow audit (B-02 fix)
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-04-PLAN.md Task 4
//         .planning/phases/03-auth-sso-hub-ids-jwt/03-04-PLAN.md (SSO-02 307 RedirectResponse)
//         RFC 7231 §6.4.7 — 307 MUST preserve POST + body
describe('Phase 5 D-V3-Phase5-C4 — api.tryRefresh redirect: follow audit', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as unknown as { __HUB_CONFIG__?: unknown }).__HUB_CONFIG__;
    localStorage.setItem('access_token', 'fake-access-token');
    localStorage.setItem('refresh_token', 'fake-refresh-token');
  });

  afterEach(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  });

  it('Test 10: tryRefresh() fetch is called with explicit `redirect: "follow"` option', async () => {
    // Mock to hub con yte → tryRefresh would POST /yte/api/auth/refresh → backend 307 → central
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        pathname: '/yte/dashboard',
        href: 'http://localhost/yte/dashboard',
        origin: 'http://localhost',
      },
      writable: true,
    });

    const fetchSpy = vi.spyOn(global, 'fetch');

    // First call from request() returns 401 → triggers tryRefresh
    fetchSpy.mockResolvedValueOnce({
      status: 401,
      json: async () => ({ success: false }),
    } as Response);
    // Second call is tryRefresh() to /api/auth/refresh — return 200 with new tokens
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: { access_token: 'new-access', refresh_token: 'new-refresh' },
      }),
    } as Response);
    // Third call is retry of original request after refresh — return 200
    fetchSpy.mockResolvedValueOnce({
      status: 200,
      json: async () => ({ success: true }),
    } as Response);

    vi.resetModules();
    const { api } = await import('../api');

    // Trigger via any authenticated call — first hits 401, triggers tryRefresh
    try {
      await api.me();
    } catch {
      // ignore; we only care about fetch call assertion
    }

    // Assert: at least one fetch call to /api/auth/refresh had redirect: 'follow'
    const refreshCall = fetchSpy.mock.calls.find((call) =>
      String(call[0]).includes('/api/auth/refresh')
    );
    expect(refreshCall).toBeDefined();
    expect(refreshCall![1]).toEqual(
      expect.objectContaining({ redirect: 'follow' })
    );

    fetchSpy.mockRestore();
  });

  it('Test 11: api.ts source contains `redirect: "follow"` in tryRefresh region (regex grep equivalent)', async () => {
    // Smoke regression — verify code-level presence via source string match.
    // Equivalent to: grep -qE "redirect:\s*['\"]follow['\"]" src/services/api.ts
    const fs = await import('node:fs/promises');
    const path = await import('node:path');
    // Resolve relative to test file location
    const apiSourcePath = path.resolve(__dirname, '../api.ts');
    const src = await fs.readFile(apiSourcePath, 'utf-8');
    expect(src).toMatch(/redirect:\s*['"]follow['"]/);
    // Also assert the D-V3-Phase5-C4 reference comment exists
    expect(src).toMatch(/D-V3-Phase5-C4/);
    expect(src).toMatch(/preserve POST body through 307 redirect/);
  });
});
