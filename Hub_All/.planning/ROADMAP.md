  5. ~~Xóa backend/ + tag m1-go-archived~~ ĐÃ THỰC HIỆN 2026-05-14 (commit `72f18ef` parent). Còn lại: verify `docker compose up` lên healthy 3-service (postgres + redis + python-api) không reference Go.

**Plans:** 4 plans (4 waves)
- [ ] 08-01-PLAN.md — Contract diff: trích endpoint api.ts vs router FastAPI vs Go signature + báo cáo phân loại gap (Wave 1, COMPAT-01 / SC3)
- [ ] 08-02-PLAN.md — Fix gap api-side: map port 8180 + router /api/ai/chat cho GeminiAssistant + CORS dev origin (Wave 2, COMPAT-01 / SC1+SC5)
- [ ] 08-03-PLAN.md — Test suite tự động: golden path API end-to-end + Vietnamese filename UTF-8 (Wave 3, COMPAT-01 / SC2+SC4)
- [ ] 08-04-PLAN.md — Boot stack script + checkpoint human-verify 11 trang React + golden path browser + biên bản UAT (Wave 4, COMPAT-01 / SC1+SC2+SC5)
**UI hint:** yes

---
