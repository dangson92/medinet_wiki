// Phase 5 PROXY-04 — Hub HCNS (Hành chính Nhân sự) Medinet branding
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md §"Specific Ideas"
//         HR = warm amber semantic
// WCAG note: amber #f59e0b vs white = 2.07:1 FAIL — UI-SPEC §1.5 getContrastTextColor return 'slate-900'
export const branding = {
  logo: '/branding/hcns/logo.svg',
  title: 'Hub HCNS Medinet',
  tagline: 'Chính sách nhân sự Medinet',
  themeColor: '#f59e0b', // amber-500
} as const;
