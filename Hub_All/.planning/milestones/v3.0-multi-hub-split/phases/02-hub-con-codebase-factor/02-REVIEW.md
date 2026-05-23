---
phase: 02-hub-con-codebase-factor
reviewed: 2026-05-22T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - Hub_All/api/app/config.py
  - Hub_All/api/app/main.py
  - Hub_All/api/scripts/hub-add.sh
  - Hub_All/api/scripts/hub-init.sh
  - Hub_All/api/tests/integration/conftest.py
  - Hub_All/api/tests/integration/test_factor_hub_scoped.py
  - Hub_All/api/tests/unit/test_config_hub_name.py
  - Hub_All/api/tests/unit/test_config_hub_name_dynamic.py
  - Hub_All/api/tests/unit/test_main_factory.py
  - Hub_All/docker-compose.yml
  - Hub_All/docker-compose.override.yml.template
  - Hub_All/Makefile
  - Hub_All/api/Makefile
  - Hub_All/.gitignore
findings:
  critical: 0
  warning: 6
  info: 8
  total: 14
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-05-22
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Tóm tắt

Phase 2 ship 5 plan FACTOR-01..04 với chất lượng kỹ thuật cao: validator chain Settings (regex + reserved blacklist + DSN match) coverage tốt, test matrix endpoint hub-scoped/central-only đầy đủ, hub-add.sh có chain validation fail-fast pre-DB-create đúng spec threat model. Tuy nhiên review phát hiện **6 Warning** chủ yếu liên quan tới drift giữa các plan (conftest factory chưa cập nhật cho FACTOR-04, root Makefile path không bao quát cwd `Hub_All/`, template volume declaration thiếu, sed -i portability macOS) và **8 Info** về consistency/duplication có thể refactor.

Không có Critical — không có security vulnerability, không có data loss risk, không có broken main path. Tất cả issue ở mức bug edge-case + quality smell.

Trọng tâm cần xử lý sớm (cản trở vận hành thực tế FACTOR-04):
- **WR-01** `hub_app_factory` reject hub mới → mọi test integration mới sau Phase 2 viết theo FACTOR-04 sẽ chết.
- **WR-02** Root `Makefile` chạy `bash Hub_All/api/scripts/hub-add.sh` khi đang ở trong `Hub_All/` sẽ thất bại — vi phạm tài liệu help.
- **WR-03** Template không chứa `volumes:` top-level → `hub-add.sh` workaround sed-append cross-platform fragile + race khi append lần 2.

## Warnings

### WR-01: `hub_app_factory` hardcode 4 hub — chặn FACTOR-04 dynamic hub trong test integration

**File:** `Hub_All/api/tests/integration/conftest.py:600-605`

**Issue:** Factory fixture vẫn enforce whitelist Literal 4-hub gốc:
```python
if hub_name not in ("central", "yte", "duoc", "hcns"):
    raise ValueError(
        f"hub_name {hub_name!r} không thuộc Literal Settings.hub_name; "
        f"valid: central|yte|duoc|hcns"
    )
```
Sau Plan 02-05 FACTOR-04 đổi `Settings.hub_name` thành `str` + regex, fixture này contradictory với production code. Mọi test integration tương lai muốn verify dynamic hub (vd `phap_che`, `marketing`) sẽ raise ValueError ở fixture trước khi tới Settings validator. `_phase2_build_dsn()` cùng file đã sẵn sàng (dùng `f"medinet_hub_{hub_name}"` không hardcode whitelist) — chỉ guard này còn stale.

**Fix:**
```python
import re

_HUB_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,15}$")

def _factory(hub_name: str) -> Any:
    # Sync regex với Settings._validate_hub_name (Plan 02-05 FACTOR-04).
    # Reserved blacklist enforce qua Settings runtime — fixture không duplicate.
    if not _HUB_NAME_PATTERN.fullmatch(hub_name):
        raise ValueError(
            f"hub_name {hub_name!r} fail regex `^[a-z][a-z0-9_]{{0,15}}$` "
            f"(FACTOR-04 Plan 02-05)"
        )
    ...
```

---

### WR-02: Root `Hub_All/Makefile` `hub-add` target dùng path tuyệt đối relative — fail khi cwd = `Hub_All/`

**File:** `Hub_All/Makefile:110`

**Issue:**
```makefile
hub-add:
	@if [ -z "$(HUB)" ]; then echo "Usage: make hub-add HUB=<name> [PORT=<port>]"; exit 2; fi
	@bash Hub_All/api/scripts/hub-add.sh $(HUB) $(PORT)
```

Makefile này nằm **trong** `Hub_All/` nên khi operator `cd Hub_All && make hub-add HUB=foo`, bash sẽ tìm `Hub_All/api/scripts/hub-add.sh` từ cwd hiện tại `Hub_All/` → path resolve thành `Hub_All/Hub_All/api/scripts/hub-add.sh` → "No such file or directory". Đối chiếu `hub-init` target (line 91) dùng `$(MAKE) -C api hub-init` proxy đúng — inconsistent.

**Fix:**
```makefile
hub-add:
	@if [ -z "$(HUB)" ]; then echo "Usage: make hub-add HUB=<name> [PORT=<port>]"; exit 2; fi
	$(MAKE) -C api hub-add HUB=$(HUB) PORT=$(PORT)
```
Hoặc nếu giữ direct bash call:
```makefile
	@bash api/scripts/hub-add.sh $(HUB) $(PORT)
```

---

### WR-03: Template `docker-compose.override.yml.template` không có `volumes:` top-level → workaround sed cross-platform fragile

**File:** `Hub_All/docker-compose.override.yml.template:1-40` và `Hub_All/api/scripts/hub-add.sh:192-204`

**Issue:** Template chỉ chứa service block, để `hub-add.sh` phải tự inject `volumes:` section sau service append:
```bash
if ! grep -q "^volumes:" "$OVERRIDE_PATH"; then
    cat >> "$OVERRIDE_PATH" <<EOF
volumes:
  medinet_cocoindex_$HUB:
EOF
else
    sed -i.bak "/^volumes:/a\\
  medinet_cocoindex_$HUB:
" "$OVERRIDE_PATH" && rm -f "${OVERRIDE_PATH}.bak"
fi
```

Vấn đề:
1. **macOS BSD sed vs GNU sed**: `sed -i.bak "/.../a\\..."` cú pháp append với backslash-newline khác biệt giữa BSD (macOS default) và GNU. Trên macOS, dòng "  medinet_cocoindex_$HUB:" có thể bị append làm 1 line liền không xuống dòng đúng. Plan đặt expected operator-local dev — bao gồm macOS dev. Hiện `set -euo pipefail` + cuối có `docker compose config --quiet` verify → có catch, nhưng error message khi fail không chỉ rõ root cause.
2. **Race append volumes lần 2**: Lần 1 append volume sau service block ở giữa file qua heredoc. Lần 2 dùng sed insert ngay sau marker `^volumes:` → thứ tự volume không deterministic (last-added at top).
3. **Service block append không có separator newline** — heredoc đầu file đặt header `services:` nhưng template sau đó bắt đầu thẳng `  python-api-{{HUB}}:` không có dòng trống. Append lần 2-N sẽ dính sát service trước đó.

**Fix:** Đơn giản hoá — template chứa LUÔN khối volumes (rỗng hoặc với 1 entry), script duy nhất append:
```yaml
# docker-compose.override.yml.template
  python-api-{{HUB}}:
    ...

volumes:
  medinet_cocoindex_{{HUB}}:
```

Hub-add.sh:
- Lần 1: heredoc header `services:` + nguyên template (cả service + volumes).
- Lần 2+: Tách template thành 2 phần (service block + volume line), append service vào trước marker `^volumes:`, append volume line sau marker — chỉ dùng `awk` hoặc python3 inline (portable hơn `sed -i.bak`).

Hoặc đơn giản hơn: bỏ workaround sed, mỗi lần append cả block đầy đủ (`volumes:` declaration trong service block với scope nội bộ docker compose không cho phép → vẫn phải top-level). Cách an toàn:
```bash
# Append service block
sed "s/{{HUB}}/$HUB/g; s/{{PORT}}/$PORT/g" "$SERVICE_TEMPLATE" >> "$OVERRIDE_PATH"

# Append volume top-level — dùng python3 portable thay sed -i
python3 - <<PYEOF
from pathlib import Path
p = Path("$OVERRIDE_PATH")
text = p.read_text()
vol_line = "  medinet_cocoindex_$HUB:\n"
if "\nvolumes:\n" in text or text.startswith("volumes:\n"):
    # Insert sau marker
    text = text.replace("volumes:\n", "volumes:\n" + vol_line, 1)
else:
    text = text.rstrip() + "\n\nvolumes:\n" + vol_line
p.write_text(text)
PYEOF
```

---

### WR-04: `hub-init.sh` interpolate `$DB_NAME` trực tiếp vào SQL — relies on regex sanitization upstream

**File:** `Hub_All/api/scripts/hub-init.sh:54-66`

**Issue:**
```bash
psql -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d postgres \
    -c "CREATE DATABASE $DB_NAME OWNER $PGUSER_EFFECTIVE;"
```
`$DB_NAME = "medinet_hub_$HUB"`. Vì regex `^[a-z][a-z0-9_]{0,15}$` đã enforce ở line 42, không thể inject `;DROP TABLE...` qua `$HUB`. Tuy nhiên:
1. **PGUSER_EFFECTIVE từ env NOT validated** (line 48 `${PGUSER:-medinet}`). Nếu operator set `PGUSER='medinet; DROP DATABASE medinet_central; --'` rồi chạy script → SQL injection. Operator-controlled env nên scope threat thấp, nhưng vẫn cần defensive.
2. **`exists` check** dùng heredoc `-c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'"` — single quote literal an toàn với regex-validated DB_NAME.
3. **HEREDOC SQL block** (line 70-75) lặp `_hnsw_dim_check` table name hardcoded — không inject risk.

**Fix:** Validate `PGUSER` cùng regex hoặc dùng quoted identifier:
```bash
# Defensive — validate PGUSER format (Postgres identifier safe)
if ! [[ "$PGUSER_EFFECTIVE" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "[hub-init] ERROR: PGUSER '$PGUSER_EFFECTIVE' invalid format."
    exit 2
fi
```
Hoặc dùng `psql` `--set` parameter:
```bash
psql -v ON_ERROR_STOP=1 -v "db_name=$DB_NAME" -U "$PGUSER_EFFECTIVE" -d postgres \
    -c "CREATE DATABASE :\"db_name\" OWNER :\"db_user\";"
```
(yêu cầu cả OWNER pass qua `-v db_user`.)

---

### WR-05: `hub-add.sh` port detection regex chỉ match quoted `"NNNN:8080"` — bỏ sót YAML port không quote

**File:** `Hub_All/api/scripts/hub-add.sh:128-145`

**Issue:**
```bash
while IFS= read -r line; do
    if [[ "$line" =~ \"([0-9]{4,5}):8080\" ]]; then
        port="${BASH_REMATCH[1]}"
        ...
    fi
done < <(cat "$BASE_PATH" "$OVERRIDE_PATH" 2>/dev/null || true)
```

Base file hiện tại quote tất cả port (`"8180:8080"` line 105/132/159/186) — OK. Nhưng:
1. YAML port spec cũng accept không quote (`- 8180:8080`) → operator edit `docker-compose.override.yml` thủ công có thể bỏ quote → auto-detect bỏ qua port, gây port conflict không bắt được.
2. Conflict check line 155/159 cũng dùng `"${PORT}:8080"` literal → cùng vấn đề.
3. Fallback `MAX_PORT=0` → `PORT=8184` (line 141): hardcode 8184 không robust. Nếu base file thay đổi (vd central đổi sang 8190) thì fallback vẫn `8184` → conflict nếu base có 8184 mà chưa quoted.

**Fix:** Regex lỏng để match cả quoted/unquoted (chỉ accept dạng map host:container):
```bash
if [[ "$line" =~ [\"\']?([0-9]{4,5})[\"\']?:8080[\"\']? ]]; then
```
Và conflict check tương ứng:
```bash
if grep -qE "[\"\']?${PORT}:8080[\"\']?" "$BASE_PATH" 2>/dev/null; then
```
Fallback dùng template port + 1 thay vì hardcode 8184.

---

### WR-06: `_validate_hub_name` không reject hub_name kết thúc bằng underscore — Postgres identifier OK nhưng confusing

**File:** `Hub_All/api/app/config.py:175`

**Issue:** Regex `^[a-z][a-z0-9_]{0,15}$` cho phép `hub_` (kết thúc underscore) hoặc `__` consecutive underscore. DB name kết quả `medinet_hub_hub_` hoặc `medinet_hub_a__b` về kỹ thuật Postgres OK nhưng vi phạm convention identifier sạch + dễ gây confusion khi grep log. Plan 02-05 docstring viết "lowercase a-z first char" nhưng không nói gì về trailing underscore.

`test_accept_dynamic_hub_names` parametrize `["phap_che", "marketing", "dev_test"]` — không cover edge case `hub_` (trailing _) → KHÔNG có test verify behavior này.

**Fix:** Lựa chọn 1 trong 2:
- (a) Refine regex để reject trailing underscore + consecutive underscore:
  ```python
  re.fullmatch(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", v)
  ```
  + verify max length separately. Pattern này yêu cầu `_` luôn đi kèm letter/digit trước và sau.
- (b) Document explicitly trailing underscore là intentional accept, thêm test case xác nhận:
  ```python
  def test_accept_trailing_underscore_ok(monkeypatch):
      # Trailing underscore: Postgres identifier valid, accept theo regex hiện tại
      _set_env(monkeypatch, hub_name="hub_", database_url="...")
      s = Settings()
      assert s.hub_name == "hub_"
  ```

Khuyến nghị (a) — match Postgres convention (snake_case word boundary).

## Info

### IN-01: Drift docstring `_validate_hub_name` — comment Plan note nói "max 16 char total" nhưng regex `{0,15}` cho phép cả empty body (min total = 1 char)

**File:** `Hub_All/api/app/config.py:147-186`

**Issue:** Docstring trong validator (line 152-156):
> body 0-15 char a-z0-9 underscore
> max total = 16 char

Plan 02-05 frontmatter `must_haves.truths` line 38 viết regex `^[a-z][a-z0-9_]{1,15}$` (min body 1, total 2-16). Implementation thực tế `{0,15}` (total 1-16) → khác plan. Test `test_accept_single_char_hub` confirm implementation đúng intention (cho phép 1-char), nhưng plan metadata stale.

**Fix:** Sync plan frontmatter regex (cập nhật `02-05-SUMMARY.md` nếu chưa đồng nhất) hoặc thêm 1 dòng test xác nhận expected behavior:
```python
# Đã có test_accept_single_char_hub — confirm intention {0,15} không phải {1,15}.
```
Tài liệu trong plan-level note cần cập nhật sang `{0,15}`.

---

### IN-02: `docker-compose.yml` lặp `environment:` + `volumes:` block giữa 4 service — YAML anchor `<<: *api-template` không có effect

**File:** `Hub_All/docker-compose.yml:83-186`

**Issue:** Comment ở line 6-12 chỉ rõ "docker compose YAML merge key `<<:` KHÔNG merge dict lồng cấp 2" → mỗi service viết lại đầy đủ `environment` + `volumes`. Kết quả: anchor `&api-template` (line 13) chỉ còn merge `build` + `env_file` + `depends_on` + `networks` (4 key gốc). 4 service hiện copy-paste 14 dòng environment + 3 dòng volumes → 68 dòng duplicate. Maintain (sửa 1 env var cho 4 service) phải sửa 4 nơi.

**Fix:** Lựa chọn:
- (a) Loại bỏ template anchor hoàn toàn — pure verbose nhưng đỡ misleading.
- (b) Dùng YAML `extra-hosts` + bash script generate compose từ template (giống `hub-add.sh` model). Đẩy 4 hub gốc về cùng workflow `make hub-add central|yte|duoc|hcns` ở first-time bootstrap.
- (c) Chuyển sang docker compose `extends:` (deprecated v3 nhưng vẫn work) hoặc dùng `x-` extension với explicit alias merge từng dict.

Phase 2 đang LOCK — fix này defer Phase 6+ khi `hub_registry` table thay thế env-driven.

---

### IN-03: `hub-init.sh` comment outdated về `_VALID_HUBS` Literal

**File:** `Hub_All/api/scripts/hub-init.sh:24-30`

**Issue:** Comment line 24-30:
> Note: KHONG validate hub_name in _VALID_HUBS hardcoded - script nay cho phep them hub MOI (vd "phap_che", "marketing"). Validation xay ra o Settings layer (Plan 02) - neu hub moi chua co trong Literal, Settings se raise ValueError o deploy time. De chuyen hub moi vao production, dev phai:
>   1. Chay script nay tao DB
>   2. Update Literal trong app/config.py + Plan 03 env.py + Plan 04 flow.py

Sau Plan 02-05 FACTOR-04, `Settings.hub_name` không còn là Literal — operator thêm hub mới KHÔNG cần update `app/config.py`. Comment cũ này misleading reader.

**Fix:**
```bash
# Note: hub_name validate qua regex `^[a-z][a-z0-9_]{0,15}$` + reserved
# blacklist (sync Settings._validate_hub_name Plan 02-05 FACTOR-04). Hub
# moi (vd "phap_che", "marketing") chay qua `make hub-add HUB=<name>` se
# wrap script nay + sinh compose service block. KHONG con can update
# Literal trong app/config.py sau Plan 02-05.
```

---

### IN-04: `Hub_All/Makefile` help text outdated — vẫn nhắc `python-api` (M2 single service) trong `logs` target

**File:** `Hub_All/Makefile:22-25, 61`

**Issue:**
```makefile
@echo "Docker compose (3-service: postgres + redis + python-api):"
@echo "  up                      - docker compose up -d (postgres + redis + python-api)"
@echo "  logs                    - docker compose logs -f python-api"
```
Sau Plan 02-02, compose có 4 service `python-api-central|yte|duoc|hcns` + `mcp_service` + `caddy`. Target `logs` line 61 `docker compose logs -f python-api` sẽ fail "no such service: python-api".

**Fix:**
```makefile
@echo "Docker compose (4 API service: central/yte/duoc/hcns + postgres + redis + mcp + caddy):"
@echo "  up                      - docker compose up -d"
@echo "  logs HUB=<name>         - docker compose logs -f python-api-<name>"

logs:
	@if [ -z "$(HUB)" ]; then \
	    docker compose logs -f python-api-central python-api-yte python-api-duoc python-api-hcns; \
	else \
	    docker compose logs -f python-api-$(HUB); \
	fi
```

---

### IN-05: `Settings` field `app_port = 8180` không khớp container port 8080

**File:** `Hub_All/api/app/config.py:52` và `Hub_All/docker-compose.yml:105`

**Issue:** `Settings.app_port: int = 8180` comment "frontend api.ts hardcode (Hyper-V excluded range)". Tuy nhiên docker-compose map `"8180:8080"` — container listen 8080 (uvicorn default trong `api/Makefile:16` dùng `--port 8180` chỉ cho native run). Container Dockerfile (chưa review) bind 8080. Setting `app_port` không được consume bất kỳ đâu trong `main.py` (uvicorn boot qua CLI flag, không đọc `settings.app_port`). Trường này là dead config + naming confusing.

**Fix:** Xoá field nếu không dùng, hoặc rename `frontend_api_port_documented` để rõ purpose là tham chiếu doc, không driver runtime. Defer cho Phase 6 settings cleanup — không block Phase 2.

---

### IN-06: `hub-add.sh` step (7c) `docker compose config` verify đặt sau khi đã append vào file → khó rollback

**File:** `Hub_All/api/scripts/hub-add.sh:206-214`

**Issue:** Step verify chạy SAU khi đã sed-append xong cả service block + volume. Nếu verify fail (vd YAML syntax broken do template lỗi), file `docker-compose.override.yml` đã bị mutate → message instruct "Xoa thu cong block python-api-$HUB neu can rollback" → đẩy gánh nặng cleanup cho operator. Cũng KHÔNG rollback DB đã CREATE trong step 7a (hub-init.sh thành công trước đó).

**Fix:** Pattern atomic write:
```bash
# Step 7b: Generate vào temp file, verify, rồi atomic mv
TEMP_OVERRIDE=$(mktemp)
cp "$OVERRIDE_PATH" "$TEMP_OVERRIDE" 2>/dev/null || true
# Apply changes vào $TEMP_OVERRIDE thay vì $OVERRIDE_PATH
# ...
mv "$OVERRIDE_PATH" "$OVERRIDE_PATH.backup-$(date +%s)"
mv "$TEMP_OVERRIDE" "$OVERRIDE_PATH"

# Step 7c verify
if ! docker compose config --quiet 2>&1; then
    mv "$OVERRIDE_PATH.backup-..." "$OVERRIDE_PATH"  # restore
    exit 3
fi
```

Tradeoff: DB cleanup vẫn cần manual (`DROP DATABASE medinet_hub_<HUB>`) — script Phase 2 chấp nhận.

---

### IN-07: `test_factor_hub_scoped.py` `_dispatch` method mapping incomplete — bug nếu thêm endpoint method HEAD/OPTIONS

**File:** `Hub_All/api/tests/integration/test_factor_hub_scoped.py:93-106`

**Issue:** Helper chỉ support 5 method (GET/POST/PATCH/DELETE/PUT), raise `ValueError` cho method khác. Hiện endpoint matrix không có HEAD/OPTIONS nên OK, nhưng tương lai nếu Plan 4+ add WebSocket / SSE endpoint, test này im lặng skip (assert path mount), tạo blind spot.

**Fix:**
```python
def _dispatch(client: TestClient, method: str, path: str) -> Any:
    method_lower = method.lower()
    if method_lower in ("get", "delete", "head", "options"):
        return getattr(client, method_lower)(path)
    if method_lower in ("post", "patch", "put"):
        return getattr(client, method_lower)(path, json={})
    raise ValueError(f"Method không support: {method}")
```

---

### IN-08: `conftest.py` `_factory` chứa block `_db_session._engine = None` access private attribute

**File:** `Hub_All/api/tests/integration/conftest.py:641-645`

**Issue:**
```python
from app.db import session as _db_session
_db_session._engine = None
_db_session._session_factory = None
```

Direct mutate module private attribute (leading underscore). Comment giải thích lý do (test prev fail không chạy lifespan shutdown → engine bound vào dead loop). Pattern này đúng intent nhưng fragile — nếu `app.db.session` refactor đổi tên global, fixture fail im lặng.

**Fix:** Cung cấp public helper trong `app.db.session`:
```python
# app/db/session.py
def reset_engine_for_test() -> None:
    """Force reset module-global engine — TEST ONLY. Defensive cleanup khi
    test prev fail không chạy dispose_engine() qua lifespan."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
```
Sau đó conftest gọi `_db_session.reset_engine_for_test()` — public contract, refactor-safe.

Pattern này cũng đã có sẵn cho `audit_service.reset_queue()` (line 633) — consistent style.

---

## Tổng kết findings

| Severity | Count | Files affected |
|----------|-------|----------------|
| Critical | 0 | — |
| Warning  | 6 | conftest.py, Makefile (root), override.yml.template + hub-add.sh, hub-init.sh, hub-add.sh, config.py |
| Info     | 8 | config.py (×2), hub-init.sh, Makefile, docker-compose.yml, hub-add.sh, test_factor_hub_scoped.py, conftest.py |
| **Total**| **14** | 9 unique files |

5 file KHÔNG có finding nào: `Hub_All/api/app/main.py`, `Hub_All/api/Makefile`, `Hub_All/.gitignore`, `Hub_All/api/tests/unit/test_config_hub_name.py`, `Hub_All/api/tests/unit/test_config_hub_name_dynamic.py`, `Hub_All/api/tests/unit/test_main_factory.py`.

**Note `app/main.py`:** Phase 2 chỉ thêm conditional router mount (line 416-443) + Starlette 404 envelope handler (line 510-549). Cả 2 block code clean, có comment trace decision (D-V3-Phase2-E), exception handler đúng pattern Starlette base class. Lifespan + middleware order không đổi từ Phase 1. KHÔNG flag.

**Note unit test 3 file:** Coverage tốt — scenario regression 4 hub gốc + dynamic 3 hub mới + 10 reject pattern + 6 reserved + 2 edge case (single char + max 16 char). Test naming + parametrize rõ ràng. Chỉ thiếu coverage edge case underscore convention (xem WR-06).

---

_Reviewed: 2026-05-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
