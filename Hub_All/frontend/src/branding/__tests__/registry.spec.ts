// Phase 5 PROXY-04 unit test — branding registry behavior
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-03-01..03
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §1.1 + §1.5
//
// Coverage:
//   - 4 hub config getBranding('central'|'yte'|'duoc'|'hcns') return shape khớp
//   - Fallback central cho unknown / empty / path-traversal-like input
//   - getContrastTextColor 4 themeColor + defensive fallback
//   - BrandingConfig shape regex T-5-03 mitigation (logo path locked schema)

import { describe, it, expect } from 'vitest';
import { getBranding, getContrastTextColor, type BrandingConfig } from '../index';

describe('Phase 5 PROXY-04 — branding registry', () => {
  describe('getBranding() — 4 hub initial', () => {
    it('returns Medinet central config for hub="central"', () => {
      const cfg = getBranding('central');
      expect(cfg.title).toBe('Medinet Wiki');
      expect(cfg.tagline).toBe('Tri thức nội bộ Medinet');
      expect(cfg.themeColor).toBe('#6366f1');
      expect(cfg.logo).toBe('/logo-medinet-wiki-main.png');
    });

    it('returns yte config for hub="yte" (emerald #10b981)', () => {
      const cfg = getBranding('yte');
      expect(cfg.title).toBe('Hub Y tế Medinet');
      expect(cfg.tagline).toBe('Tri thức y tế cho mọi nhân viên');
      expect(cfg.themeColor).toBe('#10b981');
      expect(cfg.logo).toBe('/branding/yte/logo.svg');
    });

    it('returns duoc config for hub="duoc" (sky #0ea5e9)', () => {
      const cfg = getBranding('duoc');
      expect(cfg.title).toBe('Hub Dược Medinet');
      expect(cfg.tagline).toBe('Hướng dẫn dược lâm sàng');
      expect(cfg.themeColor).toBe('#0ea5e9');
      expect(cfg.logo).toBe('/branding/duoc/logo.svg');
    });

    it('returns hcns config for hub="hcns" (amber #f59e0b)', () => {
      const cfg = getBranding('hcns');
      expect(cfg.title).toBe('Hub HCNS Medinet');
      expect(cfg.tagline).toBe('Chính sách nhân sự Medinet');
      expect(cfg.themeColor).toBe('#f59e0b');
      expect(cfg.logo).toBe('/branding/hcns/logo.svg');
    });
  });

  describe('getBranding() — fallback behavior', () => {
    it('fallbacks to central for unknown hub "phap_che"', () => {
      const cfg = getBranding('phap_che');
      expect(cfg.title).toBe('Medinet Wiki');
      expect(cfg.themeColor).toBe('#6366f1');
    });

    it('fallbacks to central for empty string ""', () => {
      const cfg = getBranding('');
      expect(cfg.title).toBe('Medinet Wiki');
    });

    it('fallbacks to central for hub with special chars (T-5-03 path traversal mitigation)', () => {
      // Regex constrain ^[a-z][a-z0-9_]{0,15}$ — ../, /, etc rejected by registry build regex
      const cfg = getBranding('../etc/passwd');
      expect(cfg.title).toBe('Medinet Wiki');
    });
  });

  describe('getContrastTextColor() — WCAG 1.4.11 mitigation', () => {
    it('returns "white" for indigo central #6366f1 (luminance ~0.44)', () => {
      expect(getContrastTextColor('#6366f1')).toBe('white');
    });

    it('returns "white" for emerald yte #10b981 (luminance ~0.57 ≤ 0.6 threshold)', () => {
      expect(getContrastTextColor('#10b981')).toBe('white');
    });

    it('returns "white" for sky duoc #0ea5e9 (luminance ~0.58 ≤ 0.6 threshold)', () => {
      expect(getContrastTextColor('#0ea5e9')).toBe('white');
    });

    it('returns "slate-900" for amber hcns #f59e0b (luminance ~0.65 > 0.6 threshold)', () => {
      expect(getContrastTextColor('#f59e0b')).toBe('slate-900');
    });

    it('defensive fallback "white" for malformed hex', () => {
      expect(getContrastTextColor('not-a-hex')).toBe('white');
      expect(getContrastTextColor('#abc')).toBe('white'); // 3-char hex not supported
    });
  });

  describe('BrandingConfig type shape', () => {
    it('all 4 hub configs have required fields (logo + title + tagline + themeColor)', () => {
      const hubs = ['central', 'yte', 'duoc', 'hcns'];
      for (const hub of hubs) {
        const cfg: BrandingConfig = getBranding(hub);
        // T-5-03 mitigation: logo path locked schema — per-hub SVG OR central wordmark PNG
        expect(cfg.logo).toMatch(/^\/(branding\/[a-z][a-z0-9_]*\/logo\.svg|logo-medinet-wiki-main\.png)$/);
        expect(cfg.title.length).toBeGreaterThan(0);
        expect(cfg.title.length).toBeLessThanOrEqual(24);
        expect(cfg.tagline.length).toBeLessThanOrEqual(48);
        expect(cfg.themeColor).toMatch(/^#[0-9a-f]{6}$/i);
      }
    });
  });
});
