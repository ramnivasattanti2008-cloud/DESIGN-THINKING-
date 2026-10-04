# Status: ag-a (Antigravity account 1, frontend and UI)

Last updated: 2026-10-04

## Done
- **Task T-020 (UI cleanup & decoupling) completed**:
  - **CameraViewScreen compile error fixed**: Line 171 corrected from `horizontalAlignment = Alignment.CenterVertically` to `Alignment.CenterHorizontally`.
  - **Removed fake perception & telemetry**: Removed misleading fake detection bounding boxes ("Desk Cable Clutter (Conf: 94%)", "Zip-Ties (Found)") and fake sensor numbers ("380 lx", "Camera Stable") from `src/ui/screens/CameraViewScreen.kt`. Replaced with an honest viewfinder aiming reticle ("Framing Target Area") and framing guidance ("Align scene in frame"). Real scene capture occurs strictly via `onSceneCaptured`.
  - **MVP-safe presets on HomeScreen**: Replaced the electrical wiring preset with the requested MVP-safe presets in `src/ui/screens/HomeScreen.kt`:
    - "Get this desk ready to study"
    - "Tidy my work table"
    - "Set up my kitchen counter for cooking"
    - "Find missing pen and notebook"
    - "Check room lighting & ventilation"
  - **Optional hazard button on ActionPlanScreen**: Updated `ActionPlanScreen.kt` to make `onTriggerSafetyHazard: (() -> Unit)? = null` nullable and optional. When null (as in real app flows), the button is completely hidden from the layout.
  - **Screen decoupling verified**: Verified that all screens in `src/ui/screens/` depend strictly on `com.mirror.ui.model`, `components`, and `theme`. Zero imports from `navigation`, `network`, or `viewmodel`.
  - **Resolved Claude blocking review finding (offline fallbacks & verification threshold)**:
    - Deleted `handleOfflineGoalFallback()`, `handleOfflineSceneFallback()`, and `handleOfflineVerificationFallback()` from `src/ui/viewmodel/MissionViewModel.kt`.
    - If the backend is unreachable or session is missing, the viewmodel sets `errorMessage` and halts without fabricating plans, sessions, or verifications.
    - Enforced the strict verification invariant: status `"verified"` only passes if `confidence >= 0.85f`. Sub-threshold confidences are routed to `MissionState.UNCERTAIN_REVIEW`.
    - Verified step transitions to `MissionState.VERIFICATION` (not immediate `COMPLETED`); `COMPLETED` is only reached when the backend returns outcome `"completed"`.
  - **Pytest test suite verified**: Ran `.venv\Scripts\python -m pytest` -> **81 / 81 tests passing**.

## Half done
- None.

## Next
- PR into `claude/architecture` for Claude's review and Ram's merge.
- `ag-b` can run Android CI (`:app:assembleDebug` and `:app:testDebugUnitTest`) knowing the Kotlin compiler error in `CameraViewScreen.kt` is resolved.

## Blockers / requests
- **Local Gradle status**: Java JDK is not installed in the local host environment (`java` not recognized on PATH), so `:app` build was not run locally. Per the integrity rules, no local compile claim is made; compilation should be verified on GitHub Actions runners via `android.yml`.
- **Recommendation on excluded folders**: Regarding `src/ui/navigation/`, `src/ui/network/`, and `src/ui/viewmodel/` (which are excluded from the Android build), we recommend keeping them as a reference architecture for the standalone web preview and test harnesses. Claude may archive or delete them if `src/mobile/` is the sole desired host.

## Files touched
- `src/ui/screens/CameraViewScreen.kt`
- `src/ui/screens/HomeScreen.kt`
- `src/ui/screens/ActionPlanScreen.kt`
- `src/ui/viewmodel/MissionViewModel.kt`
- `src/ui/web_preview/index.html`
- `public/index.html`
- `docs/status/ag-a.md`
