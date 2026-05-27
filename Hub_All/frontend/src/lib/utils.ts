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

// Trả tên hiển thị "Trang bị ảnh hưởng" trên Audit Log + Dashboard recent activity.
// Ưu tiên field tên người-đọc-được trong payload BE emit; fallback UUID shortened
// nếu target là UUID, ngược lại trả nguyên target.
//
// BE emit payload theo action:
//   document_delete                          : { document_name }
//   document.version.create / restore        : { document_id, version_number, ... }
//   user.create                              : { email, role, actor_role, actor_hub_id }
//   user.delete                              : { deleted_email, deleted_role, ... }
//   hub.create / update / update_status      : { code, name, actor_role, ... }
//   migration.role_seed                      : { migration_revision, ... } (KHÔNG có name)
export function extractAuditTargetName(target: string, payload: unknown): string {
  if (payload && typeof payload === 'object') {
    const p = payload as Record<string, unknown>;
    const nameKeys = [
      'document_name', 'user_name', 'hub_name',
      'deleted_email', 'email',
      'name', 'title', 'filename', 'target_name', 'code',
    ];
    for (const k of nameKeys) {
      if (typeof p[k] === 'string' && p[k]) return p[k] as string;
    }
  }
  if (target && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(target)) {
    return `${target.slice(0, 8)}…${target.slice(-4)}`;
  }
  return target;
}
