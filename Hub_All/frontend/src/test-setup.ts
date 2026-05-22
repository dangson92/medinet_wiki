// Phase 5 Wave 0 — vitest + RTL + jest-dom setup
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-02-PLAN.md Task 0
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Cleanup DOM sau mỗi test (RTL recommended pattern)
afterEach(() => {
  cleanup();
});
