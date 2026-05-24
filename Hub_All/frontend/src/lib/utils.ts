import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getHubUrl(code: string | undefined | null): string {
  const host = typeof window !== 'undefined' && window.location?.host
    ? window.location.host
    : 'wiki.medinet.vn';
  if (!code) return host;
  return code === 'central' ? host : `${host}/${code}`;
}
