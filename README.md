# NOVA — Cognitive Companion (Hands-Free Autonomy)

NOVA is a cognitive companion built for hands-free use: a voice-operated app
(React Native / Expo) with a local FastAPI brain (goal engine, memory, tools,
confirmations, self-healing, model management) that runs on your phone via Termux
or any machine on the same Wi-Fi.

**Moin (the user) cannot use his hands.** There are NO buttons, NO text inputs,
NO gestures, NO toggles. Everything is voice: wake word, commands, confirmations,
settings, and spoken output. The screen is passive (Orb + last exchange, readable
but never required). Vibration gives non-visual feedback.

```
nova/
├── backend/                  FastAPI brain (runs in Termux or Docker)
├── mobile/                   Expo app (Android APK via EAS build)
├── .github/workflows/        CI/CD: builds APK on push to main
└── README.md
```

## Architecture

```
Voice (phone)  -->  Wake word "Nova" → 30s listening window  -->  ws://<IP>:8000/ws
                                                                  -->  Kernel
                                                                     ├─ GoalEngine (intent regex)
                                                                     ├─ MemoryEngine (sessions in ~/.nova_memory)
                                                                     ├─ ToolEngine (shell/file + WhatsApp/SMS/media intents)
                                                                     ├─ ModelManager (HF model download/load/switch)
                                                                     ├─ BrowserEngine (search / read page / download)
                                                                     ├─ Confirmation loop (YES/NO for sensitive actions)
                                                                     └─ Guardian (tamper check + health check + auto-heal)
```

### Autonomy (Phase 7)

- **Model management** — `list models`, `download model <name>` (or `download <name>
  from hugging face`) with live progress spoken as status, `switch to <model>`,
  `unload model <name>`, `api connect/disconnect`. Downloaded models live in
  `~/.nova_models` (HF repos: DeepSeek-R1, Qwen2.5-0.5B, sshleifer/tiny-gpt2, …).
- **Sessions** — `new session` keeps only long-term memory (role `memory`/`settings`);
  chat context and command history reset. Session id persists across app restarts.
- **WhatsApp / SMS** — `whatsapp <contact> [bhejo ki <message>]` previews the message
  and asks for confirmation; NOVA remembers contacts via `remember <name> <number>`.
  If WhatsApp is unavailable she offers SMS; if Termux API is missing she says so honestly.
- **Media** — `youtube pe <x> lagao`, `netflix pe <x> kholo`, `play <x>` (remembers
  your YouTube/Netflix preference in settings).
- **Web** — `search <query>` (DuckDuckGo + HTML fallback), `read page <url>`,
  `download file <url>` (saved to `~/.nova_workspace`).
- **Self-healing** — Guardian checks watched core files at every boot plus a 6-hour
  health loop (heals missing dirs, reports unrepairable issues honestly over WS as a
  `notice`). `health check` runs it on demand.
- **Initiative & empathy** — after a task NOVA asks *"Kuch aur karun?"*; after 3
  failures she switches to the Phoenix tone (*"Main hoon na…"*); on your phone, if
  she's idle for 60s after a task she checks in: *"Boss, kuch aur help chahiye?"*

The **Guardian** hashes `kernel.py`, `goal_engine.py` and `adapters/base.py` on first
boot (stored in `~/.nova_guardian/manifest.json`). On every boot it verifies them; if a
watched core file changed, NOVA refuses to boot. The autonomy update changed
`kernel.py` and the Guardian itself — on first boot after updating, reset the manifest once:

```bash
rm -rf ~/.nova_guardian
```

## 1. Run the Backend in Termux

```bash
pkg update && pkg install python termux-api
pip install -r backend/requirements.txt

cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run inside Docker instead:

```bash
docker build -t nova-backend backend
docker run -p 8000:8000 nova-backend
```

### Test the WebSocket

```bash
pip install websockets
python - <<'EOF'
import asyncio, websockets, json

async def main():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        await ws.send(json.dumps({"type": "voice_text", "payload": "run command echo hi"}))
        print(await ws.recv())  # confirmation request
        await ws.send(json.dumps({"type": "voice_text", "payload": "yes"}))
        print(await ws.recv())  # result

asyncio.run(main())
EOF
```

## 2. Run the Mobile App (dev)

```bash
cd mobile
npm install
npx expo start
```

Scan the QR with Expo Go (or install the APK from Releases). NOVA automatically
discovers the backend by scanning the local network. If discovery fails she says:
*"Captain, I can't find the backend. Please ask Suhail or Qureshi to type the IP on
my behalf."* — or just say **"Nova, set ip to 192.168.1.100"**.

The only hands-on step in the entire flow is opening the app once. Everything after
that is voice.

## 3. Release Checklist

Before the first release, three manual steps are required (everything else is
automated).

### 3a. Point the app at your GitHub repo

Replace `YOUR_USERNAME` with your GitHub username in **both** files:

- `mobile/services/downloads.js` — `GITHUB_RELEASE_URL` (AI Brain modules)
- `mobile/services/update.js` — `GITHUB_REPO` (update checks)

### 3b. Publish the AI Brain modules

The app self-installs three modules from the **latest GitHub Release** (as assets
`python-runtime.tar.gz`, `airllm-core.tar.gz`, `model-weights.tar.gz`). They must
be built on the phone (Termux, aarch64) and uploaded to the same Release as the
APK. On the phone:

```bash
# inside Termux (or the device where the backend will run)
tar czf python-runtime.tar.gz  $(which python) $(python -c "import sys; print(sys.prefix)")
tar czf airllm-core.tar.gz      <airllm install dir>
tar czf model-weights.tar.gz    ~/.nova_models
sha256sum python-runtime.tar.gz airllm-core.tar.gz model-weights.tar.gz
```

Put the three real SHA-256 values into `BRAIN_MODULES` in
`mobile/services/downloads.js` (replacing `REPLACE_WITH_SHA256_OF_*`) and upload
the archives as assets of the Release created by the workflow (or attach them in
the same run by extending the workflow). If a module fails verification, NOVA
deletes it and says so honestly — she never extracts an unverified module.

### 3c. Build and publish the APK

1. Create an Expo account and run `npx eas login` (once, locally).
2. Add `EXPO_TOKEN` to the repo's GitHub Secrets (Settings → Secrets → Actions).
3. Commit and push to `main`:

```bash
git add -A
git commit -m "NOVA v1.0: offline-first hands-free companion"
git remote add origin https://github.com/<username>/nova.git
git push -u origin main
```

The workflow builds `mobile/` with `eas build --platform android --profile
preview` (APK, installable), downloads the artifact, and uploads it to a GitHub
Release tagged `v<version>` (from `mobile/app.json`, e.g. `v1.0.0`). The APK
lands at **https://github.com/<username>/nova/releases/latest**.

> **Important:** the autonomy update changed `kernel.py`, so on first boot of the
> new build, reset the Guardian manifest once:
> `rm -rf ~/.nova_guardian` (Termux). Then just say *"Nova, update check"* on
> future versions.

No Play Store. NOVA is distributed exclusively through GitHub Releases.

## 4. Install on Android (first launch)

1. Download `nova.apk` from the GitHub Release.
2. Android will ask to allow "Install unknown apps" — allow it for your browser
   or file manager (Settings → Apps → Special access → Install unknown apps).
3. Open the APK and install.
4. On first launch NOVA asks (by voice) for permissions: microphone, notifications,
   and **All files access** (`MANAGE_EXTERNAL_STORAGE`). If she needs storage she
   says: *"NOVA needs storage access to create folders and manage files for you,
   Captain."* and opens the system settings for you.
5. NOVA discovers the Python backend on your phone (Termux: `python -m uvicorn
   app.main:app --host 127.0.0.1 --port 8000`) or on the same Wi-Fi. If the heavy
   AI Brain (Python runtime + models, ~1.5 GB) is not installed yet, she asks:
   *"Captain, AI Brain download karna padega. Karun?"* — say **"Haan"** and she
   downloads, verifies SHA-256 and extracts the modules automatically (resumable,
   progress spoken at every 25%).

## Hands-Free Usage

1. Say **"Nova"** (wake word) → *"Listening, Captain."*
2. Give commands; the 30-second window accepts multiple commands without re-waking.
3. Sensitive actions (shell, delete, WhatsApp, clear history) ask:
   *"Captain, confirm: …? Say YES or NO."* — only a clear YES executes.
4. After 30 seconds of silence: *"Going idle, Captain. Say 'Hey Nova' to wake me up."*

### Voice Commands

| You say                        | NOVA does                                    |
| ------------------------------ | -------------------------------------------- |
| `Nova` (wake word)             | *"Listening, Captain."* — 30s listening      |
| `recent files`                 | lists files in `~/.nova_workspace`           |
| `open file notes.txt`          | prints the file                              |
| `run command echo hi`          | asks YES/NO, then runs it via shell          |
| `delete file notes.txt`        | asks YES/NO, then deletes it                 |
| `remember my name is Moin`     | stores it in `~/.nova_memory`                |
| `history`                      | reads the last 5 commands aloud              |
| `repeat last`                  | asks "Should I run it again?" (YES/NO)       |
| `clear history`                | asks YES/NO, then clears command history     |
| `dark mode on/off`             | confirms: *"Dark mode activated, Captain."*  |
| `increase/decrease font size`  | confirms the change, scales on-screen text   |
| `switch to local model`        | uses the local (mock) model                  |
| `connect to cloud`             | switches mode to cloud                       |
| `list models`                  | lists available models (deepseek v4, qwen, tiny, mistral) |
| `download deepseek v4`         | downloads + loads DeepSeek (progress spoken)  |
| `download model tiny`          | downloads + loads a model (real HF download, progress spoken) |
| `switch to qwen`               | loads a downloaded model, unloads the old one |
| `unload model tiny`            | frees memory of a loaded model               |
| `api connect / disconnect`     | connects/disconnects the LLM API             |
| `new session`                  | fresh session; long-term memory kept         |
| `whatsapp Moin bhejo ki milte hain` | previews msg, YES to send (remembers contacts) |
| `Qureshi ko whatsapp kar`     | same flow, contact-first phrasing             |
| `remember Moin 9876543210`     | stores a WhatsApp/SMS contact                |
| `youtube pe sad song lagao`    | opens YouTube (fallback: search offer)       |
| `netflix pe film kholo`        | opens Netflix                                |
| `play movie`                   | asks YouTube or Netflix, remembers choice    |
| `search quantum computing`     | DuckDuckGo web search, result read aloud     |
| `read page example.com`        | reads the page text aloud                    |
| `download file <url>`          | saves the file to ~/.nova_workspace          |
| `health check`                 | runs Guardian health check + auto-heal       |
| `set ip to 192.168.1.100`      | sets backend IP by voice (works offline)     |
| anything else                  | model reply (local mock or loaded model)     |

### Feedback & Error Recovery

- Task start: 100 ms vibration + *"Working on it, Captain."*
- Success: double vibration + *"Done, Captain."*-style spoken result
- Failure: 500 ms vibration + *"Sorry, Captain. Let me try again."* (auto-retries once)
- Not understood: *"I didn't quite catch that, Captain. Can you repeat?"* — after
  3 misses: *"My ears are failing me today. Let me reset."* (voice engine re-init)
- Unclear YES/NO: *"I didn't catch that. Say YES or NO, Captain."*

### Orb states (passive visual feedback)

| State      | Orb            |
| ---------- | -------------- |
| boot       | dim blue       |
| idle       | muted steel    |
| listening  | bright cyan    |
| thinking   | purple         |
| speaking   | green          |
