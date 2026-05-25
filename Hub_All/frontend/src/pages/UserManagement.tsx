import React, { useState, useEffect, useCallback } from 'react';
import { api, HubAPI, UserWithRolesAPI } from '../services/api';
import type { UserRole } from '../services/api';
import { cn, getHubUrl } from '../lib/utils';
import { Search, Plus, Shield, UserX, UserCheck, X, CheckCircle2, MoreVertical, Loader2, Building2, Info, KeyRound, Copy, Check, AlertTriangle, Trash2, RotateCcw } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Pagination from '../components/Pagination';
import { useAuth } from '../contexts/AuthContext';

// Local row state — KHÔNG dùng types.ts User.hubId vì giờ list view show all hub
// user thuộc (bỏ tab per-hub 2026-05-24). Giữ types.ts không touch để KHÔNG đụng
// 11 trang React khác consume User single-hub semantics.
interface UserRow {
  id: string;
  name: string;
  email: string;
  role: UserRole;                                    // 4 value users.role global (BE Phase 3 FE-04 ship)
  perHubRoles: { hubId: string; role: string }[];   // per-hub override migration 0006 (NULL = inherit global)
  hubIds: string[];                                  // hub membership từ user_hubs join
  createdAt: string;
  lastLogin: string;
  status: 'active' | 'disabled';
}

// Rank order admin > hub_admin > editor > viewer — dùng tính effective role cao
// nhất khi user có per-hub override (column "Quyền" reflect max thay vì luôn
// hiển thị users.role global, tránh confusion "đã đổi sang hub_admin nhưng vẫn
// thấy viewer" 2026-05-24).
const ROLE_RANK: Record<string, number> = { admin: 4, hub_admin: 3, editor: 2, viewer: 1 };

function effectiveRoleOf(row: UserRow): UserRole {
  const candidates = [row.role, ...row.perHubRoles.map(r => r.role)];
  let best: UserRole = 'viewer';
  let bestRank = 0;
  for (const c of candidates) {
    const r = ROLE_RANK[c] ?? 0;
    if (r > bestRank) {
      bestRank = r;
      best = c as UserRole;
    }
  }
  return best;
}

const UserManagement = () => {
  const { user: currentUser } = useAuth();
  const [hubs, setHubs] = useState<HubAPI[]>([]);
  // hubFilter state — thay activeTab tab navigation (2026-05-24 UI redesign).
  // Super admin: 'all' default, có thể lọc theo từng hub. Hub_admin: BE 400
  // HUB_ID_REQUIRED nếu thiếu hub_id query → mặc định first managed hub.
  const [hubFilter, setHubFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isDisableDialogOpen, setIsDisableDialogOpen] = useState(false);
  const [isManageHubModalOpen, setIsManageHubModalOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [deleteConfirmEmail, setDeleteConfirmEmail] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [actionMenuId, setActionMenuId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Reset password modal state — show password tạm 1 lần sau khi BE sinh.
  // BE tự gửi email cho user nếu admin đã cấu hình SMTP ở Settings → Thông báo;
  // modal vẫn hiển thị password làm backup admin copy gửi tay khi cần.
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false);
  const [resetTargetUser, setResetTargetUser] = useState<UserRow | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetCredentials, setResetCredentials] = useState<{
    name: string;
    email: string;
    password: string;
  } | null>(null);
  const [resetPasswordCopied, setResetPasswordCopied] = useState(false);

  const [users, setUsers] = useState<UserRow[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Add modal form state — multi-hub picker + 1 role chung (M2 schema: users.role
  // là role GLOBAL, áp cho mọi hub user thuộc về; role per-hub defer v4.0).
  const [newUserName, setNewUserName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserRole, setNewUserRole] = useState<UserRole>('viewer');
  const [newUserHubIds, setNewUserHubIds] = useState<Set<string>>(new Set());
  const [addError, setAddError] = useState<string | null>(null);

  // Manage-hub modal state — đổi role global + thêm hub user chưa thuộc.
  // Gỡ user khỏi hub yêu cầu backend mới (DELETE /api/users/:id/hub/:hub_id) — defer.
  const [manageDetail, setManageDetail] = useState<UserWithRolesAPI | null>(null);
  const [manageRole, setManageRole] = useState<UserRole>('viewer');
  const [manageHubIds, setManageHubIds] = useState<Set<string>>(new Set());
  const [manageLoading, setManageLoading] = useState(false);
  const [manageError, setManageError] = useState<string | null>(null);

  // Show-password-one-time modal — sau khi tạo user xong, hiển thị password tạm
  // làm backup cho admin. BE tự gửi welcome email với password này nếu admin đã
  // cấu hình SMTP ở Settings → Thông báo (fail-quiet, KHÔNG block create thành
  // công). Backend hash argon2 — KHÔNG lưu plaintext.
  const [createdCredentials, setCreatedCredentials] = useState<{
    name: string;
    email: string;
    password: string;
    hubNames: string[];
  } | null>(null);
  const [passwordCopied, setPasswordCopied] = useState(false);

  const activeHubs = hubs.filter(h => h.status === 'active');

  // Super admin = users.role='admin' global → bypass hub scope; còn lại
  // hub_admin/editor/viewer scope theo user_hubs membership.
  const isSuperAdmin = currentUser?.user.role === 'admin';
  const myHubIds = currentUser?.roles?.map(r => r.hub_id) ?? [];
  // Hub options available for filter dropdown — super sees all, hub_admin
  // chỉ thấy hub mình được gán quyền (Layout HubSwitcher pattern Plan 03-03).
  const filterableHubs = isSuperAdmin
    ? activeHubs
    : activeHubs.filter(h => myHubIds.includes(h.id));

  // Fetch hubs on mount + set default hubFilter cho hub_admin (BE 400
  // HUB_ID_REQUIRED nếu non-super-admin thiếu hub_id query — Plan 02-03).
  useEffect(() => {
    const fetchHubs = async () => {
      try {
        const res = await api.getHubs();
        if (res.success && res.data) {
          setHubs(res.data);
          // Default cho hub_admin: pick first managed hub. Super admin giữ 'all'.
          if (currentUser && currentUser.user.role !== 'admin' && hubFilter === 'all') {
            const myFirstHub = res.data.find(
              h => h.status === 'active' && (currentUser.roles?.some(r => r.hub_id === h.id) ?? false),
            );
            if (myFirstHub) setHubFilter(myFirstHub.id);
          }
        }
      } catch (err) {
        console.error('Failed to fetch hubs:', err);
      }
    };
    fetchHubs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser?.user.id]);

  // Map API user → UserRow. Role lấy từ users.role global (BE Phase 3 ship
  // UserAPI.role 4 value — KHÔNG còn clamp về 'admin' | 'viewer' như cũ).
  // hubIds + perHubRoles trả về full list từ user_hubs join để render cột Hub.
  const mapUser = useCallback((item: UserWithRolesAPI): UserRow => {
    return {
      id: item.user.id,
      name: item.user.name,
      email: item.user.email,
      role: (item.user.role ?? 'viewer') as UserRole,
      perHubRoles: item.roles.map(r => ({ hubId: r.hub_id, role: r.role })),
      hubIds: item.roles.map(r => r.hub_id),
      createdAt: new Date(item.user.created_at).toLocaleDateString('vi-VN'),
      lastLogin: item.user.updated_at ? new Date(item.user.updated_at).toLocaleDateString('vi-VN') : 'Chưa đăng nhập',
      status: item.user.status as 'active' | 'disabled',
    };
  }, []);

  // Fetch users — hub filter logic (2026-05-24 UI redesign bỏ tab):
  // - Super admin + hubFilter='all' → KHÔNG truyền hub_id (BE list any).
  // - hubFilter='<hubId>' → truyền hub_id query (BE filter user_hubs join).
  // - Hub_admin + hubFilter='all' (edge case, default đã set first managed
  //   hub ở fetchHubs) → BE return 400 HUB_ID_REQUIRED.
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {
        page: currentPage,
        per_page: itemsPerPage,
      };
      if (hubFilter !== 'all') params.hub_id = hubFilter;
      if (searchQuery) params.search = searchQuery;
      if (roleFilter !== 'all') params.role = roleFilter;

      const res = await api.getUsers(params);
      if (res.success && res.data) {
        setUsers(res.data.map(u => mapUser(u)));
        if (res.meta) {
          setTotalItems(res.meta.total);
          setTotalPages(res.meta.total_pages);
        } else {
          setTotalItems(res.data.length);
          setTotalPages(Math.ceil(res.data.length / itemsPerPage));
        }
      } else {
        setUsers([]);
        setTotalItems(0);
        setTotalPages(1);
      }
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setLoading(false);
    }
  }, [hubFilter, searchQuery, roleFilter, currentPage, mapUser]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1);
  };

  const handleRoleFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setRoleFilter(e.target.value);
    setCurrentPage(1);
  };

  const handleHubFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setHubFilter(e.target.value);
    setCurrentPage(1);
  };

  // Mở modal "Quản lý hub & quyền" — fetch full user detail (cần roles[] đầy đủ
  // vì bảng list chỉ map role trong hub đang xem, không có hub thành viên khác).
  const handleOpenManageHub = async (user: UserRow) => {
    if (manageLoading) return;
    setActionMenuId(null);
    setSelectedUser(user);
    setIsManageHubModalOpen(true);
    setManageDetail(null);
    setManageError(null);
    setManageLoading(true);
    try {
      const res = await api.getUser(user.id);
      if (res.success && res.data) {
        setManageDetail(res.data);
        const existingHubIds = new Set(res.data.roles.map(r => r.hub_id));
        setManageHubIds(existingHubIds);
        // Bug fix 2026-05-24: phiên bản cũ clamp role về 'admin' | 'viewer' →
        // sau khi BE fix _build_user_with_roles trả per-hub override, role
        // thực 'hub_admin'/'editor' rơi vào fallback 'viewer' (radio sai).
        // Pick effective max rank: per-hub override (`roles[].role` đã coalesce
        // qua users.role global) OR users.role global trực tiếp. Match thứ tự
        // ROLE_RANK admin > hub_admin > editor > viewer.
        const candidates = [
          res.data.user.role,
          ...res.data.roles.map(r => r.role),
        ];
        let bestRole: UserRole = 'viewer';
        let bestRank = 0;
        for (const c of candidates) {
          const r = ROLE_RANK[c] ?? 0;
          if (r > bestRank) {
            bestRank = r;
            bestRole = c as UserRole;
          }
        }
        setManageRole(bestRole);
      } else {
        setManageError(res.error?.message ?? 'Không tải được thông tin user');
      }
    } catch (err) {
      console.error('Failed to fetch user detail:', err);
      setManageError('Lỗi kết nối — không tải được thông tin user');
    } finally {
      setManageLoading(false);
    }
  };

  const handleSubmitManageHub = async () => {
    if (!manageDetail || actionLoading) return;
    const existingHubIds = new Set(manageDetail.roles.map(r => r.hub_id));
    const toAddHubIds = Array.from(manageHubIds).filter(h => !existingHubIds.has(h));
    // Bug fix 2026-05-24: tính effective role hiện tại (max rank) thay vì
    // clamp 'admin' | 'viewer'. Đặt user 'hub_admin' rồi mở lại modal phải
    // detect chính xác role hiện tại để biết có cần PATCH /role hay không.
    const currentCandidates = [
      manageDetail.user.role,
      ...manageDetail.roles.map(r => r.role),
    ];
    let currentRole: UserRole = 'viewer';
    let currentRank = 0;
    for (const c of currentCandidates) {
      const r = ROLE_RANK[c] ?? 0;
      if (r > currentRank) {
        currentRank = r;
        currentRole = c as UserRole;
      }
    }
    const roleChanged = manageRole !== currentRole;

    if (!roleChanged && toAddHubIds.length === 0) {
      setIsManageHubModalOpen(false);
      return;
    }
    if (manageHubIds.size === 0) {
      setManageError('User phải thuộc ít nhất 1 hub.');
      return;
    }

    setActionLoading(true);
    setManageError(null);
    try {
      // PATCH /api/users/:id/role làm 2 việc: UPDATE users.role global + INSERT
      // user_hubs ON CONFLICT DO NOTHING. Mỗi hub mới cần 1 call. Nếu chỉ đổi role
      // không thêm hub, dùng hub đầu tiên user đã thuộc làm anchor.
      const targetHubs = toAddHubIds.length > 0
        ? toAddHubIds
        : [manageDetail.roles[0]!.hub_id];
      const results = await Promise.all(
        targetHubs.map(hubId =>
          api.changeUserRole(manageDetail.user.id, hubId, manageRole),
        ),
      );
      const failed = results.filter(r => !r.success);
      if (failed.length > 0) {
        const code = failed[0].error?.code;
        let msg = `${failed.length}/${results.length} cập nhật thất bại.`;
        // Plan 03-03 v3.1 Phase 3 FE-03 — switch BE envelope code Phase 2 v3.1 Manage modal context
        // Source: .planning/phases/02-backend-rbac-enforcement/02-CONTEXT.md envelope spec
        //         .planning/phases/03-frontend-form-refactor/03-UI-SPEC.md §7.4 toast copy tiếng Việt
        switch (code) {
          case 'HUB_ADMIN_REQUIRED':
            msg = 'Bạn không có quyền gán role này. Liên hệ Super Admin.';
            break;
          case 'CROSS_HUB_USER_DELETE_DENIED':
            msg = 'Không thể xóa user thuộc nhiều hub. Liên hệ Super Admin để xử lý.';
            break;
          case 'FORBIDDEN':
            msg = 'Bạn không có quyền thực hiện thao tác này.';
            break;
        }
        setManageError(msg);
      } else {
        setIsManageHubModalOpen(false);
        fetchUsers();
      }
    } catch (err) {
      console.error('Failed to update hub assignments:', err);
      setManageError('Lỗi kết nối — vui lòng thử lại.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisableUser = async () => {
    if (!selectedUser || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.changeUserStatus(selectedUser.id, 'disabled');
      if (res.success) {
        setIsDisableDialogOpen(false);
        fetchUsers();
      }
    } catch (err) {
      console.error('Failed to disable user:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenDelete = (user: UserRow) => {
    setActionMenuId(null);
    setSelectedUser(user);
    setDeleteConfirmEmail('');
    setDeleteError(null);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteUser = async () => {
    if (!selectedUser || actionLoading) return;
    if (deleteConfirmEmail.trim().toLowerCase() !== selectedUser.email.toLowerCase()) {
      setDeleteError('Email xác nhận không khớp.');
      return;
    }
    setActionLoading(true);
    setDeleteError(null);
    try {
      const res = await api.deleteUser(selectedUser.id);
      if (res.success) {
        setIsDeleteDialogOpen(false);
        setSelectedUser(null);
        setDeleteConfirmEmail('');
        fetchUsers();
      } else {
        const code = res.error?.code;
        const msg = res.error?.message ?? 'Xoá user thất bại.';
        if (code === 'LAST_ADMIN') {
          setDeleteError(`${msg} Hãy tạo admin khác trước.`);
        } else if (code === 'CANNOT_DELETE_SELF') {
          setDeleteError('Không thể tự xoá tài khoản của chính mình.');
        } else {
          setDeleteError(msg);
        }
      }
    } catch (err) {
      console.error('Failed to delete user:', err);
      setDeleteError('Lỗi kết nối — vui lòng thử lại.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleEnableUser = async (user: UserRow) => {
    if (actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.changeUserStatus(user.id, 'active');
      if (res.success) {
        setActionMenuId(null);
        fetchUsers();
      }
    } catch (err) {
      console.error('Failed to enable user:', err);
    } finally {
      setActionLoading(false);
    }
  };

  // Reset password — mở dialog confirm + POST /api/users/:id/reset-password.
  // BE sinh password tạm 14 char ~83 bits entropy + UPDATE users.password_hash
  // argon2 + audit non-blocking + trả plaintext 1 lần + tự gửi email cho target
  // user nếu admin đã cấu hình SMTP ở Settings → Thông báo. Đóng modal = mất
  // password, phải reset lại (BE KHÔNG lưu plaintext anywhere).
  const handleOpenReset = (user: UserRow) => {
    setActionMenuId(null);
    setResetTargetUser(user);
    setResetError(null);
    setResetCredentials(null);
    setResetPasswordCopied(false);
    setIsResetDialogOpen(true);
  };

  const handleResetPassword = async () => {
    if (!resetTargetUser || actionLoading) return;
    setActionLoading(true);
    setResetError(null);
    try {
      const res = await api.resetUserPassword(resetTargetUser.id);
      if (res.success && res.data?.password) {
        setResetCredentials({
          name: resetTargetUser.name,
          email: resetTargetUser.email,
          password: res.data.password,
        });
        setIsResetDialogOpen(false);
      } else {
        const code = res.error?.code;
        let msg = res.error?.message ?? 'Reset mật khẩu thất bại.';
        if (code === 'FORBIDDEN') {
          msg = 'Bạn không có quyền reset mật khẩu (chỉ Super Admin).';
        } else if (code === 'NOT_FOUND') {
          msg = 'User không tồn tại — có thể đã bị xoá.';
        }
        setResetError(msg);
      }
    } catch (err) {
      console.error('Failed to reset password:', err);
      setResetError('Lỗi kết nối — vui lòng thử lại.');
    } finally {
      setActionLoading(false);
    }
  };

  // Sinh password tạm 14 char (~83 bits entropy) — bộ ký tự a-z A-Z 0-9 loại trừ
  // 0/O/1/I/l dễ nhầm khi đọc/gõ tay. crypto.getRandomValues = CSPRNG (KHÔNG dùng
  // Math.random — yếu cho credential).
  const generateTempPassword = (): string => {
    const charset = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
    const bytes = new Uint8Array(14);
    crypto.getRandomValues(bytes);
    let out = '';
    for (let i = 0; i < bytes.length; i++) {
      out += charset[bytes[i] % charset.length];
    }
    return out;
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setPasswordCopied(true);
      setTimeout(() => setPasswordCopied(false), 2000);
    } catch (err) {
      console.error('Clipboard copy failed:', err);
    }
  };

  const resetAddModal = () => {
    setNewUserName('');
    setNewUserEmail('');
    setNewUserRole('viewer');
    setNewUserHubIds(new Set());
    setAddError(null);
  };

  // Prefill hub đang lọc khi mở modal (admin thường tạo user cho hub đang xem).
  // Nếu filter 'all' (super admin) → để rỗng, admin tự chọn checkbox; nếu filter
  // theo 1 hub cụ thể → prefill hub đó.
  const handleOpenAddModal = () => {
    resetAddModal();
    setNewUserHubIds(hubFilter !== 'all' ? new Set([hubFilter]) : new Set());
    setIsAddModalOpen(true);
  };

  const toggleNewUserHub = (hubId: string) => {
    setNewUserHubIds(prev => {
      const next = new Set(prev);
      if (next.has(hubId)) next.delete(hubId);
      else next.add(hubId);
      return next;
    });
    setAddError(null);
  };

  const handleCreateUser = async () => {
    if (actionLoading) return;
    if (!newUserName.trim()) {
      setAddError('Vui lòng nhập tên đầy đủ.');
      return;
    }
    if (!newUserEmail.trim()) {
      setAddError('Vui lòng nhập email.');
      return;
    }
    if (newUserHubIds.size === 0) {
      setAddError('Vui lòng chọn ít nhất 1 hub.');
      return;
    }

    setActionLoading(true);
    setAddError(null);
    const hubIds = Array.from(newUserHubIds);
    const tempPassword = generateTempPassword();
    const submittedName = newUserName.trim();
    const submittedEmail = newUserEmail.trim();
    try {
      // POST /api/users tạo user + INSERT user_hubs cho hub_id đầu tiên.
      const createRes = await api.createUser({
        name: submittedName,
        email: submittedEmail,
        password: tempPassword,
        hub_id: hubIds[0]!,
        role: newUserRole,
      });
      if (!createRes.success || !createRes.data) {
        const code = createRes.error?.code;
        let msg = createRes.error?.message ?? 'Tạo user thất bại.';
        // Plan 03-02 v3.1 Phase 3 FE-01 — switch BE envelope code Phase 2 v3.1 (Plan 02-01..04 ship)
        // Source: .planning/phases/02-backend-rbac-enforcement/02-CONTEXT.md envelope spec
        //         .planning/phases/03-frontend-form-refactor/03-UI-SPEC.md §7.4 toast copy tiếng Việt
        switch (code) {
          case 'HUB_ADMIN_REQUIRED':
            msg = 'Bạn không có quyền tạo user với role Admin toàn hệ thống. Liên hệ Super Admin.';
            break;
          case 'HUB_ID_REQUIRED':
            msg = 'Vui lòng chọn hub trước khi tạo user.';
            break;
          case 'AUTH_STATE_INCONSISTENT':
            msg = 'Lỗi hệ thống xác thực — liên hệ admin. Mã: AUTH_STATE_INCONSISTENT';
            break;
          case 'FORBIDDEN':
            msg = 'Bạn không có quyền thực hiện thao tác này.';
            break;
          case 'EMAIL_CONFLICT': {
            // Backend enrich 409 với details để FE biết user đã thuộc hub nào
            // (bug fix: tạo trùng email với user ở hub khác → filter hub_id
            // giấu user khỏi danh sách → admin bối rối "đã có nhưng không thấy").
            const details = createRes.error?.details as
              | {
                  existing_hub_codes?: string[];
                  in_target_hub?: boolean;
                  exists_in_other_hub?: boolean;
                }
              | undefined;
            const targetHubName = hubs.find(h => h.id === hubIds[0])?.name ?? 'hub này';
            if (details?.in_target_hub) {
              msg = `Email ${submittedEmail} đã tồn tại trong ${targetHubName}.`;
            } else if (Array.isArray(details?.existing_hub_codes) && details.existing_hub_codes.length > 0) {
              // Super admin scope — show hub codes user đang thuộc.
              const hubNames = details.existing_hub_codes
                .map(code => hubs.find(h => h.code === code)?.name ?? code)
                .join(', ');
              msg = `Email ${submittedEmail} đã tồn tại ở hub: ${hubNames}. Mở trang Users của hub đó để dùng "Quản lý hub & quyền" gán thêm ${targetHubName}.`;
            } else if (details?.existing_hub_codes?.length === 0) {
              // Super admin — user orphan (KHÔNG thuộc hub nào).
              msg = `Email ${submittedEmail} đã tồn tại nhưng KHÔNG thuộc hub nào (orphan). Liên hệ DBA hoặc xoá user qua psql.`;
            } else if (details?.exists_in_other_hub) {
              // Hub_admin scope — KHÔNG biết hub nào (masked).
              msg = `Email ${submittedEmail} đã tồn tại ở hub khác. Liên hệ Super Admin để gán vào ${targetHubName}.`;
            } else {
              msg = `Email ${submittedEmail} đã tồn tại.`;
            }
            break;
          }
        }
        setAddError(msg);
        return;
      }
      const createdId = createRes.data.id;
      // Các hub còn lại thêm qua PATCH /api/users/:id/role (cùng role global).
      const extraHubIds = hubIds.slice(1);
      let partialFailMsg: string | null = null;
      if (extraHubIds.length > 0) {
        const patchResults = await Promise.all(
          extraHubIds.map(hubId =>
            api.changeUserRole(createdId, hubId, newUserRole),
          ),
        );
        const failed = patchResults.filter(r => !r.success);
        if (failed.length > 0) {
          partialFailMsg = `${failed.length}/${extraHubIds.length} hub gán thất bại — kiểm tra trong "Quản lý hub".`;
        }
      }
      const hubNames = hubIds
        .map(id => hubs.find(h => h.id === id)?.name ?? id)
        .filter(Boolean);
      setCreatedCredentials({
        name: submittedName,
        email: submittedEmail,
        password: tempPassword,
        hubNames,
      });
      setPasswordCopied(false);
      setIsAddModalOpen(false);
      resetAddModal();
      fetchUsers();
      if (partialFailMsg) {
        // Vẫn show credentials nhưng note partial fail qua addError persist
        // (sẽ thấy khi mở lại Thêm User). Đủ visibility mà không block flow.
        setAddError(partialFailMsg);
      }
    } catch (err) {
      console.error('Failed to create user:', err);
      setAddError('Lỗi kết nối — vui lòng thử lại.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 2026-05-24 UI redesign — bỏ tab navigation per-hub, gộp all hub vào 1
          màn hình + filter dropdown + cột Hub trong bảng. Trước đây mỗi hub 1 tab
          force admin click qua-lại; với user thuộc nhiều hub trùng email gây
          confusion "đã tồn tại nhưng không thấy". */}
      <div className="flex flex-col lg:flex-row justify-between gap-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1 max-w-4xl">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" size={16} />
            <input
              type="text"
              placeholder="Tìm theo tên hoặc email..."
              value={searchQuery}
              onChange={handleSearchChange}
              className="input-field w-full pl-10"
            />
          </div>
          <select
            value={hubFilter}
            onChange={handleHubFilterChange}
            className="input-field min-w-[160px]"
            aria-label="Lọc theo hub"
          >
            {/* Super admin được chọn 'Tất cả hub'; hub_admin BUỘC chọn 1 hub
                (BE 400 HUB_ID_REQUIRED — Plan 02-03 DEP-03). */}
            {isSuperAdmin && <option value="all">Tất cả hub</option>}
            {filterableHubs.map(hub => (
              <option key={hub.id} value={hub.id}>{hub.name}</option>
            ))}
          </select>
          <select
            value={roleFilter}
            onChange={handleRoleFilterChange}
            className="input-field min-w-[140px]"
            aria-label="Lọc theo quyền"
          >
            <option value="all">Tất cả quyền</option>
            <option value="admin">Admin</option>
            <option value="hub_admin">Hub Admin</option>
            <option value="editor">Editor</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
        <button
          onClick={handleOpenAddModal}
          className="btn-primary shrink-0"
        >
          <Plus size={18} /> Thêm User
        </button>
      </div>

      <div className="glass-card">
        <div className="">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="animate-spin text-accent" size={28} />
            </div>
          ) : (
          <table className="w-full text-left border-collapse min-w-[860px]">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Tên</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Email</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Quyền</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Hub thành viên</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Ngày tạo</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Đăng nhập cuối</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Trạng thái</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {users.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="px-5 py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                    Không có user phù hợp với bộ lọc.
                  </td>
                </tr>
              )}
              {users.map((user) => {
                const effective = effectiveRoleOf(user);
                const hasPerHubOverride = user.perHubRoles.some(r => r.role !== user.role);
                return (
                <tr key={user.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors group">
                  <td className="px-5 py-4">
                    <span className="font-semibold text-sm text-slate-900 dark:text-white">{user.name}</span>
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300">{user.email}</td>
                  <td className="px-5 py-4">
                    <div className="flex flex-col gap-1">
                      <span
                        title={
                          hasPerHubOverride
                            ? `Quyền cao nhất (mặc định ${user.role} + override per-hub). Chi tiết xem cột Hub.`
                            : `Quyền: ${effective}`
                        }
                        className={cn(
                          "inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap w-fit",
                          effective === 'admin' && "bg-slate-800 text-white",
                          effective === 'hub_admin' && "bg-brand-indigo/10 text-brand-indigo dark:text-brand-indigo/90 border border-brand-indigo/30",
                          effective === 'editor' && "bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300",
                          effective === 'viewer' && "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300",
                        )}
                      >
                        {effective === 'hub_admin' ? 'hub admin' : effective}
                      </span>
                      {hasPerHubOverride && (
                        <span className="text-[10px] text-slate-400 dark:text-slate-500 italic">
                          mặc định: {user.role === 'hub_admin' ? 'hub admin' : user.role}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    {/* Render badge mỗi hub user thuộc về. Nếu user có per-hub override
                        role='hub_admin' khác users.role global, hiển thị icon shield bên cạnh
                        hub name. */}
                    <div className="flex flex-wrap gap-1 max-w-[260px]">
                      {user.hubIds.length === 0 ? (
                        <span className="text-[10px] text-slate-400 italic">orphan</span>
                      ) : (
                        user.hubIds.map(hId => {
                          const hub = hubs.find(h => h.id === hId);
                          const override = user.perHubRoles.find(r => r.hubId === hId);
                          const isHubAdminHere = override?.role === 'hub_admin';
                          return (
                            <span
                              key={hId}
                              className={cn(
                                "inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap",
                                isHubAdminHere
                                  ? "bg-brand-indigo/10 text-brand-indigo dark:text-brand-indigo/90 border border-brand-indigo/30"
                                  : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300",
                              )}
                              title={isHubAdminHere ? `Hub admin tại ${hub?.name ?? hId}` : hub?.name ?? hId}
                            >
                              {isHubAdminHere && <Shield size={10} />}
                              {hub?.name ?? hId.slice(0, 8)}
                            </span>
                          );
                        })
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{user.createdAt}</td>
                  <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{user.lastLogin}</td>
                  <td className="px-5 py-4">
                    <span className={cn(
                      "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                      user.status === 'active' ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
                    )}>
                      {user.status === 'active' ? 'Hoạt động' : 'Đã vô hiệu'}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right">
                    <div className="relative inline-flex">
                      <button
                        onClick={() => setActionMenuId(actionMenuId === user.id ? null : user.id)}
                        className={cn(
                          "p-1.5 rounded-lg transition-colors text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700",
                          actionMenuId === user.id && "text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-700"
                        )}
                      >
                        <MoreVertical size={16} />
                      </button>
                      <AnimatePresence>
                        {actionMenuId === user.id && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={() => setActionMenuId(null)} />
                            <motion.div
                              initial={{ opacity: 0, scale: 0.95, y: -4 }}
                              animate={{ opacity: 1, scale: 1, y: 0 }}
                              exit={{ opacity: 0, scale: 0.95, y: -4 }}
                              className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg z-50 overflow-hidden py-1"
                            >
                              <button
                                onClick={() => handleOpenManageHub(user)}
                                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                              >
                                <Building2 size={14} className="text-accent" />
                                Quản lý hub & quyền
                              </button>
                              {user.status === 'active' ? (
                                <button
                                  onClick={() => {
                                    setSelectedUser(user);
                                    setIsDisableDialogOpen(true);
                                    setActionMenuId(null);
                                  }}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-danger hover:bg-danger/5 transition-colors"
                                >
                                  <UserX size={14} />
                                  Vô hiệu hóa
                                </button>
                              ) : (
                                <button
                                  onClick={() => {
                                    handleEnableUser(user);
                                  }}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-success hover:bg-success/5 transition-colors"
                                >
                                  <UserCheck size={14} />
                                  Kích hoạt lại
                                </button>
                              )}
                              {/* Reset password — chỉ super admin (BE require_role
                                  'admin' Plan 02-03). FE hide button cho hub_admin
                                  thay vì cho click rồi BE 403 — UX cleaner. */}
                              {isSuperAdmin && currentUser?.user.id !== user.id && (
                                <button
                                  onClick={() => handleOpenReset(user)}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors"
                                >
                                  <RotateCcw size={14} />
                                  Cấp lại mật khẩu
                                </button>
                              )}
                              {currentUser?.user.id !== user.id && (
                                <>
                                  <div className="my-1 border-t border-slate-100 dark:border-slate-700" />
                                  <button
                                    onClick={() => handleOpenDelete(user)}
                                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-danger hover:bg-danger/10 transition-colors"
                                  >
                                    <Trash2 size={14} />
                                    Xoá vĩnh viễn
                                  </button>
                                </>
                              )}
                            </motion.div>
                          </>
                        )}
                      </AnimatePresence>
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
          )}
        </div>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={totalItems}
          itemsPerPage={itemsPerPage}
        />
      </div>

      <AnimatePresence>
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => { setIsAddModalOpen(false); resetAddModal(); }}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden max-h-[90vh] flex flex-col"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center shrink-0">
                <h3 className="text-lg font-semibold">Thêm user mới</h3>
                <button onClick={() => { setIsAddModalOpen(false); resetAddModal(); }} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500"><X size={20} /></button>
              </div>
              <div className="p-6 space-y-4 overflow-y-auto">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Tên đầy đủ</label>
                  <input type="text" placeholder="Nguyễn Văn A" className="input-field w-full" value={newUserName} onChange={e => { setNewUserName(e.target.value); setAddError(null); }} />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Email</label>
                  <input type="email" placeholder="nva@medinet.vn" className="input-field w-full" value={newUserEmail} onChange={e => { setNewUserEmail(e.target.value); setAddError(null); }} />
                </div>
                {/* Plan 03-02 v3.1 Phase 3 FE-01 — Form 3 option radio + warning banner conditional */}
                {/* Source: .planning/phases/03-frontend-form-refactor/03-UI-SPEC.md §6.1 + §7.1 + §8.1 */}
                <div className="space-y-1.5">
                  <fieldset role="radiogroup" aria-labelledby="role-group-label" className="space-y-2">
                    <legend id="role-group-label" className="text-sm font-medium text-slate-600 dark:text-slate-300">
                      Quyền <span className="text-danger">*</span>
                    </legend>

                    {/* Option 1: Admin toàn hệ thống */}
                    <label className="flex items-start gap-2.5 p-2.5 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 rounded-md">
                      <input
                        type="radio"
                        name="role"
                        value="admin"
                        checked={newUserRole === 'admin'}
                        onChange={() => setNewUserRole('admin')}
                        aria-describedby="role-admin-desc"
                        className="mt-1 text-accent focus:ring-accent"
                      />
                      <div>
                        <div className="text-sm font-medium text-slate-700 dark:text-slate-200">Admin toàn hệ thống</div>
                        <div id="role-admin-desc" className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                          Có thể quản lý tất cả hub, user, settings. Cảnh báo: gán cho user TIN CẬY.
                        </div>
                      </div>
                    </label>

                    {/* Option 2: Quản lý hub này (hub_admin) */}
                    <label className="flex items-start gap-2.5 p-2.5 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 rounded-md">
                      <input
                        type="radio"
                        name="role"
                        value="hub_admin"
                        checked={newUserRole === 'hub_admin'}
                        onChange={() => setNewUserRole('hub_admin')}
                        aria-describedby="role-hubadmin-desc"
                        className="mt-1 text-accent focus:ring-accent"
                      />
                      <div>
                        <div className="text-sm font-medium text-slate-700 dark:text-slate-200">Quản lý hub này</div>
                        <div id="role-hubadmin-desc" className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                          Quản lý user + document trong hub được chỉ định. KHÔNG vào hub khác.
                        </div>
                      </div>
                    </label>

                    {/* Option 3: Viewer (default) */}
                    <label className="flex items-start gap-2.5 p-2.5 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 rounded-md">
                      <input
                        type="radio"
                        name="role"
                        value="viewer"
                        checked={newUserRole === 'viewer'}
                        onChange={() => setNewUserRole('viewer')}
                        aria-describedby="role-viewer-desc"
                        className="mt-1 text-accent focus:ring-accent"
                      />
                      <div>
                        <div className="text-sm font-medium text-slate-700 dark:text-slate-200">Viewer</div>
                        <div id="role-viewer-desc" className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                          Xem document + search trong hub được gán. KHÔNG quản lý user.
                        </div>
                      </div>
                    </label>

                    {/* Warning banner — chỉ mount khi admin selected */}
                    {newUserRole === 'admin' && (
                      <div
                        role="alert"
                        aria-live="polite"
                        className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-md p-3 mt-2 text-sm font-medium dark:bg-yellow-900/20 dark:border-yellow-800 dark:text-yellow-200"
                      >
                        ⚠  Quyền cao nhất — quản lý toàn bộ hệ thống
                      </div>
                    )}
                  </fieldset>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-300">
                      Hub thành viên <span className="text-danger">*</span>
                    </label>
                    <span className="text-[11px] text-slate-400">
                      Đã chọn {newUserHubIds.size}/{activeHubs.length}
                    </span>
                  </div>
                  <div className="border border-slate-200 dark:border-slate-700 rounded-xl divide-y divide-slate-100 dark:divide-slate-700 max-h-56 overflow-y-auto">
                    {activeHubs.length === 0 ? (
                      <p className="px-3 py-4 text-xs text-slate-400 text-center">Chưa có hub active.</p>
                    ) : (
                      activeHubs.map(hub => {
                        const checked = newUserHubIds.has(hub.id);
                        return (
                          <label
                            key={hub.id}
                            className={cn(
                              'flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors',
                              checked
                                ? 'bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08]'
                                : 'hover:bg-slate-50 dark:hover:bg-slate-700/50',
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleNewUserHub(hub.id)}
                              className="w-4 h-4 rounded text-brand-indigo focus:ring-brand-indigo"
                            />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{hub.name}</p>
                              <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">{hub.code}</p>
                            </div>
                          </label>
                        );
                      })
                    )}
                  </div>
                </div>
                <div className="flex items-start gap-2 text-[11px] text-slate-500 dark:text-slate-400 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-900/30 px-3 py-2 rounded-lg">
                  <Info size={14} className="shrink-0 mt-0.5 text-amber-600 dark:text-amber-500" />
                  <span>
                    Hệ thống sẽ tự động <b>gửi email welcome</b> tới user nếu đã cấu hình SMTP ở <b>Settings → Thông báo</b>. Mật khẩu tạm vẫn hiển thị 1 lần làm backup — copy nếu cần gửi tay.
                  </span>
                </div>
                {addError && (
                  <p className="text-xs text-danger bg-danger/10 px-3 py-2 rounded-lg">{addError}</p>
                )}
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50 shrink-0">
                <button onClick={() => { setIsAddModalOpen(false); resetAddModal(); }} className="btn-ghost">Hủy</button>
                <button onClick={handleCreateUser} disabled={actionLoading} className="btn-primary">
                  {actionLoading ? <Loader2 size={16} className="animate-spin" /> : null}
                  Tạo & Sinh Mật Khẩu Tạm
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {createdCredentials && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center text-success shrink-0">
                  <CheckCircle2 size={20} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold">Tạo user thành công</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{createdCredentials.email}</p>
                </div>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900/40 px-3 py-2.5 rounded-lg">
                  <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold">Mật khẩu CHỈ hiện 1 lần</p>
                    <p>Email welcome đã được gửi tự động nếu SMTP đã cấu hình ở <b>Settings → Thông báo</b>. Mật khẩu bên dưới là bản backup — copy nếu cần gửi tay. Đóng modal này = mất mật khẩu, phải reset.</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">User</label>
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{createdCredentials.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{createdCredentials.email}</p>
                    <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1.5">
                      Hub: <span className="text-slate-600 dark:text-slate-300">{createdCredentials.hubNames.join(', ')}</span>
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
                    <KeyRound size={12} /> Mật khẩu tạm thời
                  </label>
                  <div className="flex items-stretch gap-2">
                    <code className="flex-1 px-3 py-2.5 rounded-lg bg-slate-900 dark:bg-slate-950 text-emerald-300 font-mono text-sm tracking-wider select-all break-all">
                      {createdCredentials.password}
                    </code>
                    <button
                      onClick={() => copyToClipboard(createdCredentials.password)}
                      className={cn(
                        'shrink-0 px-3 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5',
                        passwordCopied
                          ? 'bg-success/10 text-success border border-success/30'
                          : 'bg-brand-indigo text-white hover:bg-brand-indigo/90',
                      )}
                    >
                      {passwordCopied ? <Check size={16} /> : <Copy size={16} />}
                      {passwordCopied ? 'Đã copy' : 'Copy'}
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-400 dark:text-slate-500">
                    Đăng nhập tại {getHubUrl(hubs.find(h => h.name === createdCredentials.hubNames[0])?.code)}
                  </p>
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button
                  onClick={() => {
                    setCreatedCredentials(null);
                    setPasswordCopied(false);
                  }}
                  className="btn-primary"
                >
                  Đã ghi nhận, đóng
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {isDisableDialogOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => setIsDisableDialogOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-sm glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Vô hiệu hóa tài khoản?</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                  Vô hiệu hóa tài khoản <span className="font-bold text-slate-700 dark:text-slate-200">{selectedUser?.name}</span>? User sẽ không thể đăng nhập Hub này, dữ liệu giữ nguyên.
                </p>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => setIsDisableDialogOpen(false)} className="btn-ghost">Hủy</button>
                <button onClick={handleDisableUser} disabled={actionLoading} className="btn-primary !bg-danger !shadow-none hover:!bg-danger/90">
                  {actionLoading ? <Loader2 size={16} className="animate-spin mr-1" /> : null}
                  Vô hiệu hóa
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {isDeleteDialogOpen && selectedUser && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => !actionLoading && setIsDeleteDialogOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-danger/10 flex items-center justify-center text-danger shrink-0">
                  <Trash2 size={20} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold">Xoá vĩnh viễn user?</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{selectedUser.email}</p>
                </div>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-start gap-2 text-xs text-danger bg-danger/10 border border-danger/20 px-3 py-2.5 rounded-lg">
                  <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold">Hành động không thể hoàn tác</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>User bị logout ngay (refresh token xoá)</li>
                      <li>Gỡ khỏi tất cả hub thành viên</li>
                      <li>Documents user đã upload <b>giữ lại</b> nhưng mất tên owner</li>
                      <li>Audit log lưu trail user.delete</li>
                    </ul>
                    <p className="pt-1">Nếu chỉ muốn chặn đăng nhập tạm thời, dùng <b>Vô hiệu hoá</b> thay vì xoá.</p>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
                    Gõ <code className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-danger font-mono">{selectedUser.email}</code> để xác nhận
                  </label>
                  <input
                    type="text"
                    autoFocus
                    autoComplete="off"
                    value={deleteConfirmEmail}
                    onChange={e => { setDeleteConfirmEmail(e.target.value); setDeleteError(null); }}
                    placeholder={selectedUser.email}
                    className="input-field w-full font-mono text-sm"
                    disabled={actionLoading}
                  />
                </div>

                {deleteError && (
                  <p className="text-xs text-danger bg-danger/10 px-3 py-2 rounded-lg">{deleteError}</p>
                )}
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button
                  onClick={() => setIsDeleteDialogOpen(false)}
                  disabled={actionLoading}
                  className="btn-ghost"
                >
                  Hủy
                </button>
                <button
                  onClick={handleDeleteUser}
                  disabled={
                    actionLoading ||
                    deleteConfirmEmail.trim().toLowerCase() !== selectedUser.email.toLowerCase()
                  }
                  className="btn-primary !bg-danger !shadow-none hover:!bg-danger/90 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {actionLoading ? <Loader2 size={16} className="animate-spin mr-1" /> : <Trash2 size={14} className="mr-1" />}
                  Xoá vĩnh viễn
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {isManageHubModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => setIsManageHubModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden max-h-[90vh] flex flex-col"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center shrink-0">
                <h3 className="text-lg font-semibold">Quản lý hub & quyền</h3>
                <button onClick={() => setIsManageHubModalOpen(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500"><X size={20} /></button>
              </div>
              <div className="p-6 space-y-5 overflow-y-auto">
                <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
                  <div className="w-12 h-12 rounded-full bg-brand-indigo/10 flex items-center justify-center text-brand-indigo">
                    <Shield size={24} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{selectedUser?.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{selectedUser?.email}</p>
                  </div>
                </div>

                {manageLoading ? (
                  <div className="flex items-center justify-center py-10">
                    <Loader2 className="animate-spin text-accent" size={24} />
                  </div>
                ) : manageDetail ? (
                  <>
                    {/* Plan 03-03 v3.1 Phase 3 FE-03 — Manage modal 3 option + DISABLED Admin cho hub_admin (defense in depth) */}
                    {/* Source: .planning/phases/03-frontend-form-refactor/03-UI-SPEC.md §6.3 + §7.3 + §8.1 */}
                    {(() => {
                      const currentRoleInline: UserRole = (currentUser?.user?.role as UserRole) ?? 'viewer';
                      const isCurrentSuper = currentRoleInline === 'admin';

                      return (
                        <div className="space-y-3">
                          <label className="text-sm font-medium text-slate-600 dark:text-slate-300">
                            Quyền <span className="text-[11px] font-normal text-slate-400">(áp cho tất cả hub user thuộc về)</span>
                          </label>
                          <div className="grid grid-cols-1 gap-2">
                            {/* Option 1: Admin toàn hệ thống — DISABLED nếu hub_admin (FE-03 defense in depth, BE Plan 02-03 T-02-02-E authoritative) */}
                            <button
                              onClick={() => isCurrentSuper && setManageRole('admin')}
                              disabled={!isCurrentSuper}
                              aria-disabled={!isCurrentSuper}
                              title={!isCurrentSuper ? 'Cần Admin toàn hệ thống' : undefined}
                              aria-describedby={!isCurrentSuper ? 'manage-admin-tooltip-desc' : undefined}
                              className={cn(
                                'flex items-center justify-between p-3 rounded-xl border transition-all text-left',
                                manageRole === 'admin'
                                  ? 'border-brand-indigo bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08] ring-1 ring-brand-indigo'
                                  : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-slate-800',
                                !isCurrentSuper && 'opacity-50 cursor-not-allowed hover:border-slate-200 dark:hover:border-slate-700',
                              )}
                            >
                              <div>
                                <p className="text-sm font-bold text-slate-900 dark:text-white">Admin toàn hệ thống</p>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Toàn quyền quản lý Hub, User và Tài liệu.</p>
                              </div>
                              {manageRole === 'admin' && <div className="w-5 h-5 rounded-full bg-brand-indigo flex items-center justify-center text-white"><CheckCircle2 size={12} /></div>}
                            </button>

                            {/* Option 2: Quản lý hub này (hub_admin) — luôn enable */}
                            <button
                              onClick={() => setManageRole('hub_admin')}
                              className={cn(
                                'flex items-center justify-between p-3 rounded-xl border transition-all text-left',
                                manageRole === 'hub_admin'
                                  ? 'border-brand-indigo bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08] ring-1 ring-brand-indigo'
                                  : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-slate-800',
                              )}
                            >
                              <div>
                                <p className="text-sm font-bold text-slate-900 dark:text-white">Quản lý hub này</p>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Quản lý user + document trong hub được chỉ định.</p>
                              </div>
                              {manageRole === 'hub_admin' && <div className="w-5 h-5 rounded-full bg-brand-indigo flex items-center justify-center text-white"><CheckCircle2 size={12} /></div>}
                            </button>

                            {/* Option 3: Viewer */}
                            <button
                              onClick={() => setManageRole('viewer')}
                              className={cn(
                                'flex items-center justify-between p-3 rounded-xl border transition-all text-left',
                                manageRole === 'viewer'
                                  ? 'border-brand-indigo bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08] ring-1 ring-brand-indigo'
                                  : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-slate-800',
                              )}
                            >
                              <div>
                                <p className="text-sm font-bold text-slate-900 dark:text-white">Viewer</p>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Xem document + search trong hub được gán.</p>
                              </div>
                              {manageRole === 'viewer' && <div className="w-5 h-5 rounded-full bg-brand-indigo flex items-center justify-center text-white"><CheckCircle2 size={12} /></div>}
                            </button>
                          </div>

                          {/* a11y: hidden helper text linked via aria-describedby (UI-SPEC §8.1) */}
                          {!isCurrentSuper && (
                            <p id="manage-admin-tooltip-desc" className="sr-only">
                              Tùy chọn này yêu cầu quyền Admin toàn hệ thống.
                            </p>
                          )}
                        </div>
                      );
                    })()}

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Hub thành viên</label>
                        <span className="text-[11px] text-slate-400">{manageHubIds.size}/{activeHubs.length}</span>
                      </div>
                      <div className="border border-slate-200 dark:border-slate-700 rounded-xl divide-y divide-slate-100 dark:divide-slate-700 max-h-56 overflow-y-auto">
                        {activeHubs.length === 0 ? (
                          <p className="px-3 py-4 text-xs text-slate-400 text-center">Chưa có hub active.</p>
                        ) : (
                          activeHubs.map(hub => {
                            const existingHubIds = new Set(manageDetail.roles.map(r => r.hub_id));
                            const wasAssigned = existingHubIds.has(hub.id);
                            const checked = manageHubIds.has(hub.id);
                            return (
                              <label
                                key={hub.id}
                                className={cn(
                                  'flex items-center gap-3 px-3 py-2.5 transition-colors',
                                  wasAssigned ? 'cursor-not-allowed opacity-90' : 'cursor-pointer',
                                  checked && !wasAssigned && 'bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08]',
                                  !wasAssigned && 'hover:bg-slate-50 dark:hover:bg-slate-700/50',
                                )}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  disabled={wasAssigned}
                                  onChange={() => {
                                    if (wasAssigned) return;
                                    setManageHubIds(prev => {
                                      const next = new Set(prev);
                                      if (next.has(hub.id)) next.delete(hub.id);
                                      else next.add(hub.id);
                                      return next;
                                    });
                                    setManageError(null);
                                  }}
                                  className="w-4 h-4 rounded text-brand-indigo focus:ring-brand-indigo disabled:opacity-50"
                                />
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{hub.name}</p>
                                  <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">{hub.code}</p>
                                </div>
                                {wasAssigned && (
                                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-success/10 text-success shrink-0">
                                    Đã gán
                                  </span>
                                )}
                              </label>
                            );
                          })
                        )}
                      </div>
                      <p className="flex items-start gap-1.5 text-[11px] text-slate-400 dark:text-slate-500 italic">
                        <Info size={12} className="shrink-0 mt-0.5" />
                        <span>Có thể thêm hub mới. Gỡ user khỏi hub đã gán cần backend mới — defer v4.0.</span>
                      </p>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-danger text-center py-6">{manageError ?? 'Không tải được thông tin user.'}</p>
                )}

                {manageError && manageDetail && (
                  <p className="text-xs text-danger bg-danger/10 px-3 py-2 rounded-lg">{manageError}</p>
                )}
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50 shrink-0">
                <button onClick={() => setIsManageHubModalOpen(false)} className="btn-ghost">Hủy</button>
                <button onClick={handleSubmitManageHub} disabled={actionLoading || manageLoading || !manageDetail} className="btn-primary">
                  {actionLoading ? <Loader2 size={16} className="animate-spin mr-1" /> : null}
                  Lưu thay đổi
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {/* Reset password confirm dialog — admin xác nhận trước khi BE sinh
            password mới (irreversible: password cũ bị hash mới ghi đè + user
            phải re-login). */}
        {isResetDialogOpen && resetTargetUser && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => !actionLoading && setIsResetDialogOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center text-amber-700 dark:text-amber-400 shrink-0">
                  <RotateCcw size={20} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold">Cấp lại mật khẩu?</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{resetTargetUser.email}</p>
                </div>
              </div>
              <div className="p-6 space-y-3">
                <div className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900/40 px-3 py-2.5 rounded-lg">
                  <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold">Hành động không thể hoàn tác</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>Mật khẩu cũ của <b>{resetTargetUser.name}</b> mất hiệu lực ngay</li>
                      <li>Hệ thống sinh mật khẩu mới + hiển thị 1 lần cho admin copy</li>
                      <li>Hệ thống tự gửi email cho user nếu SMTP đã cấu hình ở <b>Settings → Thông báo</b></li>
                    </ul>
                  </div>
                </div>
                {resetError && (
                  <p className="text-xs text-danger bg-danger/10 px-3 py-2 rounded-lg">{resetError}</p>
                )}
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button
                  onClick={() => setIsResetDialogOpen(false)}
                  disabled={actionLoading}
                  className="btn-ghost"
                >
                  Hủy
                </button>
                <button
                  onClick={handleResetPassword}
                  disabled={actionLoading}
                  className="btn-primary !bg-amber-600 !shadow-none hover:!bg-amber-700"
                >
                  {actionLoading ? <Loader2 size={16} className="animate-spin mr-1" /> : <RotateCcw size={14} className="mr-1" />}
                  Sinh mật khẩu mới
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {/* Show-password-one-time modal sau khi reset thành công — pattern same
            với create user. BE tự gửi email cho user nếu SMTP đã cấu hình; modal
            là bản backup admin copy gửi tay khi cần. Đóng modal → password biến
            mất khỏi state FE, BE KHÔNG lưu plaintext anywhere. */}
        {resetCredentials && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center text-success shrink-0">
                  <CheckCircle2 size={20} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold">Mật khẩu mới đã sinh</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{resetCredentials.email}</p>
                </div>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900/40 px-3 py-2.5 rounded-lg">
                  <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold">Mật khẩu CHỈ hiện 1 lần</p>
                    <p>Email với mật khẩu mới đã được gửi tự động nếu SMTP đã cấu hình ở <b>Settings → Thông báo</b>. Mật khẩu bên dưới là bản backup — copy nếu cần gửi tay. Đóng modal này = mất mật khẩu, phải reset lại.</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">User</label>
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{resetCredentials.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{resetCredentials.email}</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
                    <KeyRound size={12} /> Mật khẩu mới
                  </label>
                  <div className="flex items-stretch gap-2">
                    <code className="flex-1 px-3 py-2.5 rounded-lg bg-slate-900 dark:bg-slate-950 text-emerald-300 font-mono text-sm tracking-wider select-all break-all">
                      {resetCredentials.password}
                    </code>
                    <button
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(resetCredentials.password);
                          setResetPasswordCopied(true);
                          setTimeout(() => setResetPasswordCopied(false), 2000);
                        } catch (err) {
                          console.error('Clipboard copy failed:', err);
                        }
                      }}
                      className={cn(
                        'shrink-0 px-3 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5',
                        resetPasswordCopied
                          ? 'bg-success/10 text-success border border-success/30'
                          : 'bg-brand-indigo text-white hover:bg-brand-indigo/90',
                      )}
                    >
                      {resetPasswordCopied ? <Check size={16} /> : <Copy size={16} />}
                      {resetPasswordCopied ? 'Đã copy' : 'Copy'}
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-400 dark:text-slate-500">
                    Đăng nhập tại {getHubUrl(hubs.find(h => resetTargetUser?.hubIds.includes(h.id))?.code)}
                  </p>
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button
                  onClick={() => {
                    setResetCredentials(null);
                    setResetTargetUser(null);
                    setResetPasswordCopied(false);
                  }}
                  className="btn-primary"
                >
                  Đã ghi nhận, đóng
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default UserManagement;
