# MIRROR: Multimodal Interactive Reality Reasoning & Observation Routine

[![Backend Tests](https://img.shields.io/badge/backend%20tests-81%20passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-Android%20%7C%20FastAPI-orange.svg)]()
[![Integrity](https://img.shields.io/badge/unverified%20claims-zero-red.svg)]()

> **The One Rule of MIRROR:**  
> **MIRROR must never claim success without verification.** A physical action is verified *only* when fresh sensor observations confirm the required state change with calibrated confidence $\ge 0.85$. If sensor frames are blurry, dark, occluded, or ungrounded, the system halts with `cannot_tell` rather than hallucinating success.

---

## 1. What is MIRROR?

MIRROR is a safety-first, phone-grounded AI assistant designed to help people navigate unfamiliar physical environments—tidying a workspace, preparing a kitchen counter, inspecting a room, or setting up equipment.

Unlike conventional conversational AI assistants that output multi-step instructions blindly, MIRROR operates in a **strictly verified, closed physical loop**:
1. It ingests a natural-language goal and filters it through a deterministic **Policy Gate** (`PolicyGate`).
2. It captures real-world camera frames and identifies visible physical objects and anchors.
3. It generates **exactly one grounded step at a time**.
4. The user performs the action.
5. The camera captures fresh post-action frames.
6. The **Verification Engine** compares before and after evidence. A step passes *only* if required evidence is visibly present with confidence $\ge 0.85$.
7. The loop repeats until the backend confirms the space is fully prepared (`completed`).

---

## 2. The 7-Stage Verification Loop

```mermaid
flowchart TD
    A["1. User Submits Goal"] --> B{"2. PolicyGate Pre-Screen"}
    B -- Tier A3 Refusal --> R["Halt & Warn User (Electrical / Structural Hazard)"]
    B -- Tier A2 Confirm --> C["Request User Confirmation"]
    B -- Tier A0/A1 Allowed --> D["3. Multi-Frame Camera Observation"]
    C --> D
    D --> E{"Frame Quality Check"}
    E -- Blurry / Dark --> F["Prompt User: Retake Photo"]
    F --> D
    E -- Clear View --> G["4. Grounded One-Step Plan"]
    G --> H["5. Human Physical Execution"]
    H --> I["6. Post-Action Camera Capture"]
    I --> J{"7. Verification Engine"}
    J -- "cannot_tell (blurry / unanchored)" --> K["UNCERTAIN_REVIEW: Re-aim / steady camera"]
    J -- "not_verified (cup still there)" --> L["Retain Step: Action not confirmed"]
    J -- "verified (conf >= 0.85)" --> M{"All Goals Met?"}
    M -- More Steps --> G
    M -- All Clean --> N["Mission Completed (Empirically Verified)"]
    K --> I
    L --> H
```

---

## 3. Safety Architecture & Policy Tiers

MIRROR governs physical safety through a deterministic, regex-based policy gate (`src/core/policy.py`) before any model call or physical action is planned:

| Tier | Name | Behavioral Constraint | Example Tasks |
|---|---|---|---|
| **A0** | Pure Information | Autonomous advice; no physical state modification. | "How much light is in this room?" |
| **A1** | Reversible Physical | Simple reversible tidying; low kinetic risk. | "Move coffee cup off desk", "Tidy notebooks" |
| **A2** | Human Confirmation | Moderate hazard; requires explicit confirmation dialog. | "Switch off hot stove burner before food prep" |
| **A3** | Default Deny (Refusal) | Hard refusal; never guided; directs to professional. | "Fix loose wall socket wiring", "Chemical handling" |

---

## 4. Running the Project

### Prerequisites
- Python 3.11+ (tested on Python 3.13)
- Android Studio / JDK 17 (for mobile app build)

### A. Python Backend & Test Suite

1. **Activate Virtual Environment & Install Dependencies:**
   ```bash
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   ```

2. **Run Pytest Suite (81 Backend Tests):**
   ```bash
   python -m pytest
   ```
   *Verifies policy gate rules, loop state transitions, false success prevention, low-confidence rejection, and API contracts.*

3. **Start the FastAPI Backend:**
   ```bash
   python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *Endpoints: `GET /v1/health`, `POST /v1/sessions`, `POST /v1/sessions/{id}/observe`, `POST /v1/sessions/{id}/plan`, `POST /v1/sessions/{id}/verify`.*

4. **Run the Interactive Demo Client:**
   ```bash
   python tools/demo_client.py --url http://127.0.0.1:8000 --goal "get my desk ready to study"
   ```

### B. Standalone Web & UI Preview

To inspect the user interface and screen flow in any browser without Android Studio:
```bash
python -m http.server 8080
```
Open `http://localhost:8080/src/ui/web_preview/index.html` or `http://localhost:8080/public/index.html`.

### C. Android App Build

The Android client is built with Kotlin 2.0 and Jetpack Compose (`app/` module):
```bash
# In project root:
./gradlew :app:assembleDebug
./gradlew :app:testDebugUnitTest
```

#### Windows Development Note:
If you encounter `java.io.IOException: Unable to establish loopback connection` during Gradle runs on Windows (due to short paths or spaces in `C:\Users\...`), set a clean temp directory:
```bash
mkdir C:\mirror-tmp
$env:GRADLE_OPTS="-Xmx2g -Dfile.encoding=UTF-8 -Djdk.net.unixdomain.tmpdir=C:/mirror-tmp"
.\gradlew :app:testDebugUnitTest --no-daemon
```

---

## 5. Honest Validation Status & Known Limitations

Per the project integrity rules in `AGENTS.md` and [`docs/architecture/VALIDATION.md`](docs/architecture/VALIDATION.md), nothing is estimated or exaggerated:

### Verified Facts
- **81 / 81 backend tests pass** (`python -m pytest`), verifying the policy gate, loop invariants, schema compliance, and false success prevention.
- **Full HTTP loop verified**: Verified over real HTTP using `uvicorn` and the test client (refusal on electrical hazard, `needs_observation` before capture, `not_verified` on missing evidence, `cannot_tell` on blur, and `completed` after verified action).
- **Kotlin source compiles**: `src/ui/screens/` and Compose components compile with JDK 17 / AGP 8.5.2 after fixing `CameraViewScreen.kt:171`.

### Explicit Limitations (Marked UNVERIFIED)
- **Real Vision Model Not Called in Production:** The backend currently defaults to `FakeModelClient` for deterministic test isolation. `AnthropicModelClient` exists in `src/core/model_client.py` and is unit-tested against mocked transport, but has **not** been exercised with a live API key in this repo.
- **Android Unit Tests Not Run Locally:** Android unit tests (`MissionControllerTest`, `ParsingAndMetricsTest`) could not be run on the local development machine due to a Windows loopback socket restriction in Java. They are verified on GitHub Actions CI runners (`.github/workflows/android.yml`).
- **No Physical Phone Deployment:** No APK has been installed or exercised on physical phone hardware. CameraX captures and hardware sensor bindings are unexercised on physical silicon.
- **Planner is a Rule Template:** The current action planner uses a deterministic rule template for study/kitchen spaces; it is not yet an unconstrained agentic LLM planner.

---

## 6. Multi-Seat AI Development Model

MIRROR is developed through a structured multi-agent pair programming model with strictly segregated seats and lanes (`AGENTS.md`):

| Seat | Role | Lane / Deliverables |
|---|---|---|
| `claude` | Lead Engineer | Architecture, core logic, safety policy, PR code reviews. |
| `ag-a` | Frontend & UI | Jetpack Compose screens, UI flow, web preview, decoupling. |
| `ag-b` | QA & Reliability | Smoke test suites, CI workflows (`android.yml`), E2E HTTP loop tests. |
| `ag-c` | Reserve Support | Bounded database logging (`src/core/session_log.py`). |
| `studio-a` | Research & Datasets | Literature review, benchmark scenes (`data/scenes.json`), perception prompts. |
| `studio-b` | Docs & Presentation | `README.md`, report outline, demo script, presentation deck. |
| `copilot` | Standalone Tools | Interactive CLI client (`tools/demo_client.py`). |

---

## 7. Repository Structure

```
├── .github/workflows/     # CI automation (Android build & test pipeline)
├── contracts/             # JSON schemas for sessions, observations, plans, verifications
├── data/                  # Standardized physical verification benchmark (12 scenes)
│   ├── scenes.json        # Machine-readable benchmark scenes (all marked sample)
│   └── scenes.md          # Human-readable benchmark documentation and taxonomy
├── db/                    # SQLite database schema (schema.sql)
├── docs/                  # Architecture, decisions, tasks, status, and reports
│   ├── architecture/      # System design, verification engine, safety policy
│   ├── report/            # Academic report outline and 3-minute demo script
│   ├── slides/            # 8-slide presentation deck outline
│   └── status/            # Individual status handoff files for each seat
├── prompts/               # Calibrated VLM perception prompt specifications
├── research/              # Literature citations (sources.md) and empirical plan (PLAN.md)
├── src/
│   ├── api/               # FastAPI HTTP routing (/v1/sessions)
│   ├── core/              # Engine, PolicyGate, Verifier, ModelClient, Models
│   ├── mobile/            # Android CameraX, OkHttp, and controller implementation
│   └── ui/                # Jetpack Compose UI screens, components, theme, web preview
└── tools/                 # Standalone demo client (demo_client.py)
```

---

## 8. License & Attribution

Distributed under the MIT License. Created by Ram Nivas with multi-agent AI pair programming assistance. All AI contributions and benchmark samples are disclosed honestly in accordance with coursework and open-source publication standards.
