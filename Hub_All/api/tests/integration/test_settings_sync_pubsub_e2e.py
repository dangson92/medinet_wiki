"""Phase 6 Plan 06-04 — (Optional) Real Redis pub/sub e2e test.

Defer Phase 7 MIGRATE-05 nếu fakeredis-py KHÔNG support async pubsub.listen()
đúng (real testcontainer Redis cần Docker runtime — defer phase 7 full E2E
golden path 3 hub + central + JWT SSO + cross-hub search live).

Plan 06-04 Task 1 lifespan + Plan 06-02 subscriber unit test cover semantic:
- Plan 06-02 `test_settings_sync_subscriber.py`: 11 unit test mock redis pubsub
  verify 3-branch flush (rag_config + hub_registry + apikey) + reconnect retry
  + CancelledError graceful — đã cover subscriber loop logic.
- Plan 06-04 `test_settings_sync_lifespan_integration.py`: 6 integration test
  ASGI lifespan verify state populate + escape hatch + shutdown graceful +
  fail-loud + central skip — đã cover wiring lifespan ↔ subscriber.

Placeholder structure khi enable Phase 7 testcontainer Redis fixture:

  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_central_publish_invalidates_yte_cache(real_redis):
      # spawn 2 LifespanManager (central + yte) share real_redis fixture
      # central PUT /api/rag-config → assert yte app.state.redis.get(
      #     "settings:rag_config:yte") is None trong < 2s (subscriber flush)

  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_central_publish_invalidates_yte_hub_registry(real_redis):
      # Publish manual redis.publish("settings:invalidate", json) →
      # assert yte cache "settings:hub_registry" deleted
"""
import pytest

pytest.skip(
    "Phase 6 e2e pub/sub test defer Phase 7 MIGRATE-05 full E2E real Redis fixture. "
    "Plan 06-04 lifespan integration test + Plan 06-02 subscriber unit test "
    "cover semantic. fakeredis-py async pubsub.listen() KHÔNG yield message reliable.",
    allow_module_level=True,
)
