# Running MIRROR (backend + Android app)

## Backend

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Windows; use .venv/bin/python on macOS/Linux
.venv/Scripts/python -m pytest                        # backend tests
.venv/Scripts/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Providers (env, see `.env.example`):
- `MIRROR_MODEL_PROVIDER=fake` (default): reads labels from test input. No real perception.
- `MIRROR_MODEL_PROVIDER=anthropic` with `MIRROR_MODEL_API_KEY` set: real vision calls. Not yet exercised against the live API.

## Production hardening (backend)

Configured by environment variables, safe by default (code: `src/api/security.py`):

| Variable | Meaning |
|---|---|
| `MIRROR_ENV=production` | A missing `MIRROR_API_KEY` becomes a startup error instead of a silently open server |
| `MIRROR_API_KEY` | When set, every route except `/v1/health` needs it (`X-API-Key` header or `Authorization: Bearer ...`). Unset means an open development server and a warning in the log |
| `MIRROR_RATE_LIMIT_PER_MINUTE` | Per client, default 60. `0` switches it off (the test suite does this) |
| `MIRROR_TRUST_PROXY=1` | Take the client address from `X-Forwarded-For`. Only behind a proxy you control, otherwise clients can fake their address |
| `MIRROR_MAX_BODY_BYTES` | Request size limit, default 8 MiB (a photo is a few hundred KiB) |
| `MIRROR_MAX_SESSIONS` | Sessions kept in memory, default 1000 (the oldest is dropped) |
| `MIRROR_ALLOWED_ORIGINS` | Comma separated browser origins. Empty (default) means no CORS headers; a native app does not need them |
| `MIRROR_SESSION_DB` | SQLite path for the optional audit log (no photos are ever written) |

HTTPS for local or LAN testing: `python tools/run_secure_server.py` (generates a self-signed development certificate into the git-ignored `certs/`; needs the `cryptography` package from the dev extras). A real deployment should terminate TLS at a proper proxy or host with a real certificate.

The Android debug build can send the key: `./gradlew :app:assembleDebug -PmirrorApiKey=<key>`. A key baked into an APK can be extracted, so this is for development only; a shipped app needs per-user sign-in.

## Android app

One Gradle module (`:app`) built from `src/mobile` (integration, owned by `claude`) plus `src/ui` (screens, owned by `ag-a`, compiled unchanged).

Needs JDK 17 and the Android SDK (platform 34, build-tools 34.0.0). Put the SDK path in `local.properties` (`sdk.dir=...`, git-ignored).

```bash
./gradlew :app:testDebugUnitTest          # JVM unit tests (controller, adapter, parsing, metrics)
./gradlew :app:assembleDebug              # debug APK
```

Backend address is baked in at build time:
- Emulator: default `http://10.0.2.2:8000`.
- Real phone on the same Wi-Fi: `./gradlew :app:assembleDebug -PmirrorBackendUrl=http://<your-pc-lan-ip>:8000`, and allow port 8000 through the PC firewall.

Debug builds allow plain http for this; release builds should use https.

## Troubleshooting (Windows)

**`java.io.IOException: Unable to establish loopback connection` (cause `Invalid argument: connect`)** while Gradle runs. Seen on the dev PC: Java's internal pipe uses Unix-domain sockets in the temp folder, and that fails when the temp path is an 8.3 short name such as `C:\Users\RAMNIV~1\...` (user folder with a space). Plain network sockets are fine, so the Python backend is unaffected. Fix: point every Java process at a folder with no spaces.

```bash
mkdir /c/mirror-tmp
export JAVA_TOOL_OPTIONS="-Djdk.net.unixdomain.tmpdir=C:/mirror-tmp"
export GRADLE_OPTS="-Xmx2g -Dfile.encoding=UTF-8"
./gradlew :app:testDebugUnitTest --no-daemon
```

`JAVA_TOOL_OPTIONS` matters: Gradle's compiler worker is a separate JVM and does not inherit `GRADLE_OPTS`. If Gradle forks a daemon that dies ("first result from the daemon was empty"), remove the `org.gradle.jvmargs` line locally so it runs in-process. For Android Studio, put `-Djdk.net.unixdomain.tmpdir=C:/mirror-tmp` in `~/.gradle/gradle.properties` under `org.gradle.jvmargs` (not the repo file; the path is machine specific).

## The loop in the app

`HOME` goal -> `CAMERA` real photo -> backend `observe` + `plan` -> `SUMMARY` -> `PLAN` -> `EXECUTING` (person does the step) -> real photo -> backend `verify` -> `VERIFICATION` -> accept (only if verified with confidence >= 0.85) -> next plan, until the backend reports `completed`.

## Success rules (enforced in both layers)

1. A step passes only when the backend status is `verified` and confidence >= 0.85. The backend itself downgrades a lower-confidence `verified` to `cannot_tell`, and the app checks again. `not_verified`, `cannot_tell` and any unknown status never pass.
2. The mission screen "Done and verified" is reachable only from a backend `completed` outcome, which needs at least one verified step and a fresh scan with nothing left to do.
3. "Nothing to change" is reported as such, never as success.
4. Unsafe goals are refused before any scan. Hazards seen in the scene stop the flow; there is no override.
5. Server, model or camera failures show a message and change no state toward success.
6. No photo is taken or sent until the person allows it for the task (a dialog appears before the camera opens). Declining cancels the task with nothing taken or sent; the next task asks again.

## Known limits

- The planner is a rule template (study / work / cook plus clutter and hazards), not a model. With the Anthropic provider only perception is real.
- `ag-a`'s camera screen draws a simulated HUD (sample boxes, sample sensor numbers). The photo MIRROR actually sends is a separate real capture. Their screens are unchanged.
- Blur and brightness thresholds, the confidence formula and the 0.85 bar are heuristics, not calibrated.
