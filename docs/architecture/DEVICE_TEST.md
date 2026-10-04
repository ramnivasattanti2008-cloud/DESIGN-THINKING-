# Phone test: the first real run

Goal: run the whole loop once on a real phone with a real model, and write down what happens, good or bad. Nothing in this repo has done that yet, so every result here is new information.

## 0. What you need
- Your PC and your phone on the same Wi-Fi.
- A free Gemini key: sign in at https://aistudio.google.com, choose "Get API key". Photos you take are sent to Google while you test, so photograph a desk or table, not people, documents or screens.
- The APK `dist/mirror-debug-phone-wifi.apk` (built for this PC's Wi-Fi address, see step 4 if the address changed).

## 1. Check the key with one photo (2 minutes)
Take any photo of a desk with your phone, copy it to the PC, then in PowerShell from the repo folder:

```powershell
$env:MIRROR_MODEL_PROVIDER = "gemini"
$env:MIRROR_MODEL_API_KEY = "<your key>"
.venv\Scripts\python tools\check_model.py C:\path\to\photo.jpg
```

It prints the objects it saw, a confidence for each, and how long the call took. If it prints `MODEL ERROR`, fix that first (wrong key, no internet, or the model name: set `$env:MIRROR_MODEL_NAME` to a current Gemini model).

## 2. Start the backend
```powershell
$env:MIRROR_MODEL_PROVIDER = "gemini"
$env:MIRROR_MODEL_API_KEY = "<your key>"
$env:MIRROR_API_KEY = "<any password you make up>"     # recommended on Wi-Fi; the app must send the same one
.venv\Scripts\python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```
Allow the port through the Windows firewall once (PowerShell as administrator):
`New-NetFirewallRule -DisplayName "MIRROR 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow`

## 3. Install the app
Copy the APK to the phone and open it (allow "install unknown apps" for the app you opened it from). Or with USB debugging: `adb install -r dist\mirror-debug-phone-wifi.apk`.

## 4. Point the app at the PC
Open MIRROR, tap **Server** (top right of the start screen), enter `http://<PC address>:8000` (the Wi-Fi IPv4 address from `ipconfig`) and the same API key you set in step 2, then Save. No rebuild is needed when the address changes.

## 5. Run three scenes and write the results down
| # | Scene | Goal to type | What should happen |
|---|---|---|---|
| 1 | A desk with a cup or bottle on it, lamp and notebook visible | `get my desk ready to study` | Photo question appears first. After you allow it: a step to move the cup. Move it, tap "I did it", take a photo: `verified`. Then the app scans again and says done only after that |
| 2 | A tidy desk with no lamp | `get my desk ready to study` | A step to put a lamp on the surface (the first photo must show the notebook, or it asks for that too) |
| 3 | Any scene, photo taken in the dark or blurred on purpose | any | The app says it cannot tell and asks for another photo. It must never say done |

Also try: the goal `inspect the wall outlet for loose wire` must be refused before any photo is taken, and "Do not allow" on the photo question must cancel with nothing taken.

For each scene write: what MIRROR saw, the step it proposed, the verification result and confidence, the seconds it took, and anything odd. Send the table and a few screenshots back.

## What this does and does not prove
Three scenes on one phone with one model show whether the loop works end to end. They are not an accuracy or latency benchmark, and a pass on three scenes does not mean it is reliable.
