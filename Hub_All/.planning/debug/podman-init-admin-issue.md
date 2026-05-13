---
slug: podman-init-admin-issue
status: deferred
trigger: "podman machine init failing on Windows 10 Pro from non-elevated Git Bash shell"
created: 2026-04-29
updated: 2026-04-29
deferred_reason: "Sau 3h fight infra (Docker Desktop crash → Podman init hang → WSL install/import stuck), user chọn skip smoke runtime Phase 2 + ưu tiên flow phát triển Phase 3. Khi nào user rảnh: reboot Windows + wsl --import + Docker install."
deferred_resume_steps: |
  1. Reboot Windows (clear WSL stuck state).
  2. PowerShell admin: `wsl --import Ubuntu C:\WSL\Ubuntu C:\Users\PC\ubuntu-rootfs\extracted\install.tar.gz --version 2`
  3. Trong Ubuntu (`wsl -d Ubuntu`), cài Docker Engine native (xem instructions cũ).
  4. Build + smoke 5 SC theo `docling-pipeline/README.md` mục 6.
---

# Debug: Podman init admin issue trên Windows 10 Pro

## Symptoms

**Expected behavior:** `podman machine init` từ Git Bash (non-elevated) tạo được Linux VM (WSL2 hoặc Hyper-V backend), `podman machine start` boot OK, sau đó `podman compose build` work.

**Actual behavior:**
- WSL provider (default): `podman machine init` hang silent ~3-15 phút, KHÔNG có output sau banner đầu, KHÔNG tạo cache, KHÔNG có WSL distro nào được register. Process vẫn alive nhưng 0 activity quan sát được.
- Hyper-V provider (`CONTAINERS_MACHINE_PROVIDER=hyperv`): fail loud `Error: hyperv machines require admin authority` (exit 125).

**Error messages:**
```
# Hyper-V
Error: hyperv machines require admin authority

# WSL — không có error, chỉ banner:
time="2026-04-29T15:02:34+07:00" level=info msg="podman.exe filtering at log level info"
(rồi hang vô tận)
```

**Timeline:** Lần đầu setup. Trước đó dùng Docker Desktop nhưng đã uninstall (folder `tmp-delete`). Cài Podman Desktop GUI nhưng không cài CLI engine. Tự download Podman 5.3.1 standalone về `~/podman/`.

**Reproduction:**
```bash
export PATH="$HOME/podman/podman-5.3.1/usr/bin:$PATH"
# WSL hang:
podman machine init
# Hyper-V fail:
CONTAINERS_MACHINE_PROVIDER=hyperv podman machine init
```

## Environment

- OS: Windows 10 Pro (build 19045.6466)
- Shell: Git Bash (`/usr/bin/bash`) — non-elevated user `PC`
- Podman: 5.3.1 standalone (download từ GitHub releases)
- WSL: v2.4.13 kernel có sẵn nhưng KHÔNG có Linux distro nào registered (`wsl -l -q` empty)
- Hyper-V: vmcompute service Running ✅
- Docker Desktop: đã uninstall (folder `C:\Program Files\Docker\Docker\` chỉ còn `tmp-delete`)
- Podman Desktop GUI: cài tại `C:\Program Files\Podman Desktop\` nhưng wizard chưa setup engine

## Goal

Tìm cách init + start podman machine **mà KHÔNG cần user mở shell admin riêng** — vì Claude (agent này) chỉ có non-elevated Git Bash, không thể trigger UAC popup.

## Current Focus

**hypothesis:** WSL provider hang vì cần `wsl --import` (admin) để tạo distro `podman-machine-default` lần đầu — không có UAC popup hiện ra cho non-elevated shell, nó silent hang đợi mãi.

**test:** Verify WSL distro được tạo bằng cách check `wsl -l -v` ngay sau init start. Hoặc xem podman trace có gọi `wsl --import` không.

**expecting:** Log line `wsl --import podman-machine-default ...` trong podman trace, và return code admin denial.

**next_action:** Spawn gsd-debugger để thử các workaround:
1. Pre-import WSL distro non-admin nếu có cách (có flag `--system` không?)
2. Sửa Windows policy cho user thường được wsl --import
3. Bypass podman machine — dùng `wsl --install Ubuntu` user-level rồi cài Docker engine trong đó
4. Hoặc xác nhận chắc chắn: phải có admin shell duy nhất

## Evidence

- timestamp: 2026-04-29T14:44 — `podman machine list` empty trước init.
- timestamp: 2026-04-29T14:44 — `podman machine init --cpus 4 --memory 8192 --disk-size 60` started, 0 byte output sau 14 phút.
- timestamp: 2026-04-29T14:58 — `tasklist` confirm `podman.exe` PID 33136 STILL RUNNING với cmdline `machine init --cpus 4 --memory 8192 --disk-size 60`. Cache `~/.local/share/containers/podman/` 0 bytes. Temp dir `/c/Users/PC/AppData/Local/Temp/podman/` exists nhưng 0 bytes.
- timestamp: 2026-04-29T15:01 — `podman info` show `provider: wsl, version: 5.3.1`. Network test `curl github.com` OK (HTTP 200, 1.1s).
- timestamp: 2026-04-29T15:01 — `wsl -l -v` từ Git Bash hang vô tận (không in distro list). `wsl --version` OK trước đó (v2.4.13).
- timestamp: 2026-04-29T15:13 — `CONTAINERS_MACHINE_PROVIDER=hyperv podman machine init` exit 125 với rõ ràng `Error: hyperv machines require admin authority`.
- timestamp: 2026-04-29T15:13 — Hyper-V `vmcompute` service Running.

## Eliminated

- Network blocked → eliminated by curl github.com test (HTTP 200, 1.1s).
- Podman binary corrupt → eliminated by `podman --version` work, `podman info` work.

## Evidence (bổ sung phase 2)

- timestamp: 2026-04-29T15:35 — Web search xác nhận: Podman trên Windows tự re-exec với flag ẩn `--reexec` để escalate quyền qua UAC khi `podman machine init` chạy từ shell non-admin (containers/podman issues #25523, #17232, #22994, #25723).
- timestamp: 2026-04-29T15:35 — Trên Hyper-V: mỗi lần `podman machine init|start|stop|reset` đều cần admin privileges để ghi `HKLM` registry (issue #23578, #25038). WSL backend: chỉ `init` cần admin, `start` sau đó không cần.
- timestamp: 2026-04-29T15:36 — Wsl `-l -v` hang từ Git Bash do WSL output UTF-16 LE không flush qua MSYS pty — KHÔNG phải WSL bị broken. Confirm bằng `cmd.exe /c "wsl --list --online"` exit 0 OK.
- timestamp: 2026-04-29T15:36 — `wsl.exe` binary hợp lệ tại `C:\Windows\System32\wsl.exe`.

## Eliminated (bổ sung)

- hypothesis: "WSL kernel hỏng / wsl.exe missing"
  evidence: `where wsl` trả về `C:\Windows\System32\wsl.exe`; `wsl --list --online` qua cmd exit 0.
  timestamp: 2026-04-29T15:36

- hypothesis: "Network / proxy block image pull"
  evidence: hang xảy ra TRƯỚC bất kỳ HTTP request nào (cache thư mục 0 byte, 0 traffic), curl github.com OK.
  timestamp: 2026-04-29T15:36

## Resolution

**root_cause:**
Podman 5.3.1 trên Windows khi `podman machine init` chạy từ shell non-elevated sẽ tự re-exec chính nó qua cơ chế UAC bằng flag ẩn `--reexec`. Từ Git Bash (MSYS pty không có console parent thông thường), Windows không hiển thị được UAC popup → process cha bị treo silent vô hạn chờ UAC response không bao giờ tới. Đây là known design choice của Podman (containers/podman #17232, #22994, #25723), KHÔNG phải bug môi trường máy user.

**workaround ranking:**

| Hạng | Workaround | Effort admin | Success | Maintenance |
|---|---|---|---|---|
| 1 | **B** — User tự mở 1 PowerShell admin, chạy `podman machine init` rồi đóng. Sau đó agent `podman machine start` + dùng non-admin (WSL backend không cần admin sau init). | 1 lệnh admin duy nhất | ~95% | Một lần |
| 2 | **A** — Admin chạy `wsl --install -d Ubuntu --no-launch` 1 lần, reboot, rồi non-admin `podman machine init`. | 1 lệnh admin + reboot | ~80% (vẫn có thể trigger reexec) | Một lần |
| 3 | **D** — Bỏ podman cho M1 phase 2, chạy `docling-pipeline` qua Python venv local. Defer container smoke test sang manual run. | 0 admin | 100% (nhưng không có container test) | Defer |
| 4 | **C** — Hyper-V provider | Mỗi lần `start/stop` đều admin | Cao nhưng phiền | Lặp lại |

**recommended:** Workaround **B**. Lý do: chỉ 1 lệnh admin duy nhất, WSL backend cho phép `start` non-admin, không bị regression mỗi lần restart, không cần reboot, không tốn slot WSL distro thêm.

**fix (cho user):**
1. User click chuột phải Windows Terminal hoặc PowerShell → "Run as administrator".
2. Trong shell admin chạy đúng 2 lệnh:
   ```powershell
   $env:PATH = "$HOME\podman\podman-5.3.1\usr\bin;" + $env:PATH
   podman machine init --cpus 4 --memory 8192 --disk-size 60
   ```
3. Đợi init xong (~3-5 phút, có log thực sự — sẽ pull Fedora OS image). Đóng shell admin.
4. Báo agent. Agent sẽ chạy non-admin: `podman machine start`, rồi `podman compose build` v.v. — KHÔNG cần admin nữa.

**verification (sẽ test sau khi user xong bước 1-3):**
- `podman machine list` từ Git Bash non-admin show machine `podman-machine-default` status `Stopped`.
- `podman machine start` thành công non-admin (exit 0, machine status `Running`).
- `podman info` show `host.os: linux` non-admin.

**files_changed:** [] (diagnose-only mode, không sửa code)

