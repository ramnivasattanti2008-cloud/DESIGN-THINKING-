# Status: ag-a (Antigravity account 1, frontend and UI)

Last updated: 2026-10-04

## Done
- **Task T-020 (UI cleanup & decoupling) completed & merged in PR #8**.
- **Task T-033 (Round 3 UI Components) completed in PR #9 (`ag-a/ui-components`)**:
  - Implemented 5 themed Compose components: `ExecutingScreen.kt`, `CompletedScreen.kt`, `PhotoConsentDialog.kt`, `ServerSettingsDialog.kt`, and `NoticeBanner.kt`.
  - Android CI verified green on GitHub Actions.
- **Task T-035 (Feature-Rich Web Studio & Live Gemini Multimodal Vision)** on branch `ag-a/live-web-studio`:
  - Upgraded `src/ui/web_preview/index.html` and `public/index.html` into a full-featured real-time Interactive Vision Studio:
    1. **Live Camera & Webcam Stream**: Real-time video preview with device switcher (front/back camera) and frame snapshot capture.
    2. **Image File Drag-and-Drop & File Picker**: Upload desk, room, or counter images directly for immediate scene analysis.
    3. **Real Gemini Integration**: Connected to live backend using Google AI Studio Gemini API (`gemini-3.5-flash-lite`), measuring real round-trip latencies (~2.0s).
    4. **Perception Visualizer**: Displays detected objects with exact labels, confidence meters, and spatial anchors.
    5. **Hands-free Voice Guidance (TTS)**: Web Speech API synthesis voicing instructions and safety confirmations out loud.
    6. **Interactive Goal Presets**: One-click selection for study desk setup, kitchen counter cooking, cable management, room tidy, and missing object search.
    7. **Safety Policy Indicator**: Visual indicator displaying policy verification status (blocked/allowed), ensuring dangerous tasks are refused.
    8. **Audit Trail & JSON Exporter**: Full transparency panel displaying the audit sink log in real-time, with single-click JSON download for review.
    9. **Live Latency & Health Indicator**: Real-time ping checking backend connection status (`http://127.0.0.1:8000/v1/health` or mobile Wi-Fi `http://172.20.244.128:8000/v1/health`).
  - Started background preview server on `http://localhost:8080` (and `http://172.20.244.128:8080`).

## Half done
- None.

## Next
- Claude review of PR #9 (`ag-a/ui-components`) and PR `ag-a/live-web-studio`.
- Ram merge into `main` after review.

## Blockers / requests
- **Request for `claude` (Core Parser)**:
  In `src/core/model_client.py:140-145`, `parse_observations` regex looks for `\{.*\}` and expects `data["objects"]`. When Gemini outputs a top-level JSON array `[{"label": "...", ...}]` without a wrapping `{"objects": ...}` dictionary, `parse_observations` raises `KeyError: 'objects'`. Please update `parse_observations` to support:
  `raw_objs = data if isinstance(data, list) else data.get("objects", [])`
- **Secrets safety check**: `.env` holds the Google AI Studio key (`AQ.Ab...`) and is verified to be in `.gitignore`. No keys are in git tracked files.

## Files touched
- `src/ui/web_preview/index.html`
- `public/index.html`
- `docs/status/ag-a.md`

