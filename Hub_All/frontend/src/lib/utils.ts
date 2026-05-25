import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getHubUrl(code: string | undefined | null): string {
  // Host runtime từ window.location — Vite SPA luôn chạy browser, vitest jsdom
  // cũng cung cấp window.location. KHÔNG fallback hardcode domain.
  const host = window.location.host;
  if (!code) return host;
  return code === 'central' ? host : `${host}/${code}`;
}
