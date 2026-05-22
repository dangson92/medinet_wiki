// Phase 5 PROXY-04 — Per-hub branding registry (D-V3-Phase5-D1 LOCKED)
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md §"Decisions D"
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §1
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md Pattern 5

// Type contract — UI-SPEC §1.1 LOCKED
export interface BrandingConfig {
  readonly logo: string;       // Public asset absolute path '/branding/<hub>/logo.svg'
  readonly title: string;      // VN hub title (≤ 24 chars — sidebar truncate max-w-[160px])
  readonly tagline: string;    // VN subtitle (≤ 48 chars — Login hero column)
  readonly themeColor: string; // Hex 7 chars '#xxxxxx' — dùng làm CSS variable --hub-theme
}

// Vite eager glob — compile-time scan + bundle TẤT CẢ branding modules.
// Eager mode → static imports inlined, KHÔNG lazy chunk, KHÔNG async penalty.
// Reference: https://vite.dev/guide/features.html#glob-import
const modules = import.meta.glob<{ branding: BrandingConfig }>('./*/index.ts', {
  eager: true,
});

// Build registry keyed by hub name. Path pattern './<hub>/index.ts'
// Regex constrain: hub name match Settings format ^[a-z][a-z0-9_]{0,15}$ (Plan 02-05 FACTOR-04)
// T-5-03 mitigation: path schema locked — KHÔNG accept user input cho asset path
const registry: Record<string, BrandingConfig> = {};
for (const path in modules) {
  const match = path.match(/^\.\/([a-z][a-z0-9_]{0,15})\/index\.ts$/);
  if (match) {
    registry[match[1]] = modules[path].branding;
  }
}

// Fallback Medinet central (M2 brand) — silent fallback per UI-SPEC §1.1
const FALLBACK: BrandingConfig = registry['central'] ?? {
  logo: '/branding/central/logo.svg',
  title: 'Medinet Wiki',
  tagline: 'Tri thức nội bộ Medinet',
  themeColor: '#6366f1', // indigo-500 M2 brand
};

/**
 * Trả về branding config cho hub. Fallback silent về central nếu hub không có.
 *
 * @param hub - hub name (vd 'yte', 'central', hoặc 'unknown')
 * @returns BrandingConfig (luôn defined — fallback central)
 */
export function getBranding(hub: string): BrandingConfig {
  const cfg = registry[hub];
  if (cfg) return cfg;
  // Dev-only warning, silent UX cho user (UI-SPEC §1.1 fallback contract)
  if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) {
    console.warn(`[branding] Unknown hub "${hub}" — fallback to central`);
  }
  return FALLBACK;
}

/**
 * Helper WCAG mitigation — return 'white' | 'slate-900' dựa trên relative luminance.
 *
 * hcns amber #f59e0b vs white = 2.07:1 → FAIL WCAG 1.4.11 (3:1 cho UI icon).
 * Sử dụng cho sidebar logo icon + Login submit button text khi themeColor light.
 *
 * Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §1.5
 *
 * @param themeColor - hex string '#xxxxxx'
 * @returns 'white' nếu themeColor đủ tối (luminance ≤ 0.55), else 'slate-900'
 */
export function getContrastTextColor(themeColor: string): 'white' | 'slate-900' {
  // Strip '#' + parse RGB 6 hex digits
  const hex = themeColor.replace(/^#/, '');
  if (hex.length !== 6) return 'white'; // defensive fallback

  const r = parseInt(hex.slice(0, 2), 16) / 255;
  const g = parseInt(hex.slice(2, 4), 16) / 255;
  const b = parseInt(hex.slice(4, 6), 16) / 255;

  // Relative luminance (sRGB) — simplified linear approx, đủ accuracy cho threshold 0.55
  // Reference: https://www.w3.org/TR/WCAG21/#dfn-relative-luminance (full version uses gamma correction)
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;

  return luminance > 0.55 ? 'slate-900' : 'white';
}

// Export registry cho test introspection (KHÔNG dùng ở production component)
export const _registry_internal_for_test = registry;
