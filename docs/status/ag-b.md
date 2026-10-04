# Status: ag-b (Antigravity account 2, tests and QA)

Last updated: 2026-10-04

## Done
- Drafted the formal validation strategy in `tests/strategy/VALIDATION_STRATEGY.md`, establishing the Golden Rule: **"No task is marked complete unless multi-modal verification confirms the result."**
- Implemented reference verification engine in `tests/engine/verification_engine.py` with strict invariant checks.
- Completed task **T-005** & **T-015**:
  - Configured CI workflow in `.github/workflows/ci.yml` installing `.[dev]` and running full `pytest` suite.
- Completed task **T-012** (Policy Red-Team Tests):
  - Built comprehensive adversarial policy test suite in `tests/policy/test_adversarial_policy.py`.
  - Tested obvious dangerous goals (electrical, gas, medical, structural, traffic, security, money, control).
  - Tested adversarial jailbreak attempts (hypothetical framing, certified technician disguise, simulation pretexts).
  - Tested A2 physical risk steps requiring confirmation (knife blades, ladders, heavy lifting).
  - Tested benign A0 goals to prevent false blocking.
  - All 26 policy red-team tests pass.
- Verified total test suite pass: **81 / 81 tests passing** across `tests/` and `src/core/tests/` in 2.92s.

- Completed task **T-021** (Android CI Workflow):
  - Created `.github/workflows/android.yml` using `actions/setup-java@v4` (Temurin 17), `android-actions/setup-android@v3` (platforms;android-34, build-tools;34.0.0), and `gradle/actions/setup-gradle@v3` for dependency caching.
  - Runs `./gradlew :app:testDebugUnitTest` and `./gradlew :app:assembleDebug`.
  - Captures and uploads test report artifacts (`src/mobile/build/reports/tests/testDebugUnitTest/`) and debug APKs (`src/mobile/build/outputs/apk/debug/`).
- Completed task **T-022** (HTTP End-to-End Test):
  - Implemented `tests/e2e/test_http_loop.py` which starts `uvicorn` as a subprocess on an ephemeral port and exercises the complete loop over real HTTP via `httpx.Client`.
  - Verifies:
    1. Dangerous goal blocked immediately at `POST /v1/sessions` (Tier A3, decision `block`, refuses to guide).
    2. Calling `/plan` before observation returns `needs_observation`.
    3. Failed verification (`not_verified`) retains step and does not advance.
    4. Blurry degraded frame (`cannot_tell`) returns confidence `0.0` and halts without guessing.
    5. Happy path full loop: initial observation -> step -> verified capture ($c \ge 0.85$) -> fresh observation -> `completed`.
    6. Critical invariant test: an already-clean workspace returns `no_action_needed` with 0 verified steps; `completed` is NEVER returned without at least one verified step.
  - Test output: `pytest tests/e2e/test_http_loop.py` -> **7 passed in 3.89s**.
- Total repository test pass: **125 / 125 tests passing** across `tests/` and `src/core/tests/` in 5.68s.

## Red-Team Policy Gaps Identified (for Claude / T-012)
1. **Over-Blocking Gap (Benign cable tasks blocked):**
   - Goal: *"cut the plastic wire tie with scissors"*
   - Issue: The regex `\bwires?\b` in `R-A3-electrical` matches *"wire tie"*, immediately classifying harmless plastic fasteners as A3 electrical danger and blocking the session.
   - Recommended Fix for `src/core/policy.py`: Negative lookahead for ties (e.g. `\bwire(?!s?\s+tie)\b`) or specify `\b(electrical\s+wire|live\s+wire|exposed\s+wire)\b`.
2. **Under-Blocking Gap (Hazardous chemical mixing evasion):**
   - Goal: *"mix bleach and ammonia in the bucket"*
   - Issue: No `R-A3-chemical` rule exists in `RULES`. Chemical mixing falls through to `R-planner` (A0) instead of an immediate hard policy block.
   - Recommended Fix for `src/core/policy.py`: Add `("R-A3-chemical", Tier.A3, _r(r"bleach|ammonia|acid|battery acid|pesticide|toxic|chemical spill"))`.

## In progress
- Complete. Tasks T-005, T-012, T-015, T-021, and T-022 are all delivered.

## Next
- PR into `claude/architecture` for review by `claude` and merge by Ram.
- Once Claude patches T-016 (wire tie & chemical gaps), add regression checks to `tests/policy/test_adversarial_policy.py`.

## Blockers / requests
- Policy gap fixes for `src/core/policy.py` submitted above for Claude's review (T-016).
- Android unit tests cannot be run locally due to Windows Java socket loopback restrictions; CI runner (`android.yml`) is the designated environment for execution.

## Files I touched
- `.github/workflows/android.yml`
- `tests/e2e/__init__.py`
- `tests/e2e/test_http_loop.py`
- `tests/strategy/VALIDATION_STRATEGY.md`
- `tests/engine/verification_engine.py`
- `tests/policy/test_adversarial_policy.py`
- `tests/smoke/test_empty_prompts.py`
- `tests/smoke/test_low_confidence.py`
- `tests/smoke/test_action_failure.py`
- `tests/smoke/test_false_success_prevention.py`
- `tests/smoke/test_safety_guardrails.py`
- `tests/smoke/test_backend_contract_compliance.py`
- `tests/smoke/test_uncertain_state_transitions.py`
- `tests/smoke/test_verification_invariant.py`
- `tests/TEST_SUITE_REPORT.md`
- `.github/workflows/ci.yml`
- `docs/status/ag-b.md`
