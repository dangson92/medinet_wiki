// Phase 5 PROXY-02 unit test — prefix detect module-level compute
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-02-01
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md §"Implementation Decisions B1" (D-V3-Phase5-B1 LOCKED)

import { describe, it, expect, beforeEach, vi } from 'vitest';

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
