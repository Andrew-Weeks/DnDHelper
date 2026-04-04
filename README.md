# DnDHelper

A D&D companion web app for players and Dungeon Masters — soundboard, spellbook, campaign management, session recording, and AI-powered transcript analysis.

## Quick Start

**1. Create and activate a virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Generate a self-signed SSL certificate** (required — the app runs over HTTPS)
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```
Place `cert.pem` and `key.pem` in the project root.

**4. Set environment variables** (see [Configuration](#configuration) below)

**5. Run the server**
```bash
python run.py
```

The app will be available at **https://localhost:5000**

> Your browser will warn about the self-signed certificate — click through to proceed. The HTTPS requirement exists because browser microphone access (used for live session recording) requires a secure context.

To reach the app from other devices on your local network, use your machine's IP address: `https://192.168.x.x:5000`

---

## Configuration

All settings are read from environment variables. The easiest approach is to create a `.env` file and load it before starting, or set them directly in your shell.

| Environment Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-...` | **Change this** — random string used to sign sessions |
| `DM_SECRET` | `dungeon-master` | Passphrase required to register as DM. Remove to allow anyone. |
| `DEV_SECRET` | `developer-mode` | Passphrase required to register as Developer. |
| `HF_AUTH_TOKEN` | _(empty)_ | HuggingFace token — required for speaker diarization (pyannote) |
| `WHISPER_MODEL_SIZE` | `base` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `ANTHROPIC_API_KEY` | _(empty)_ | Anthropic API key — required for session analysis (summary, NPC tracker, etc.) |
| `ANALYSIS_MODEL` | `claude-haiku-4-5-20251001` | Claude model used for analysis passes |

To change `SECRET_KEY`, `DM_SECRET`, or `DEV_SECRET`, edit [config.py](config.py) directly.

### Getting a HuggingFace token
1. Create a free account at [huggingface.co](https://huggingface.co)
2. Accept the terms for [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
3. Generate an access token at huggingface.co → Settings → Access Tokens
4. Set it as `HF_AUTH_TOKEN`

### Getting an Anthropic API key
1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Create an API key under API Keys
3. Set it as `ANTHROPIC_API_KEY`

---

## Prerequisites for Session Features

Session recording, transcription, and analysis have extra dependencies beyond `requirements.txt`.

### ffmpeg (required for transcription)
Used to convert uploaded/recorded audio to WAV before Whisper processes it.

```bash
# Windows (winget)
winget install --id Gyan.FFmpeg -e

# macOS (Homebrew)
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

After installing on Windows, restart your terminal so PATH is updated.

### PyTorch
`torch` is listed in `requirements.txt` but the right version depends on your hardware. If transcription is slow or fails, install the appropriate build from [pytorch.org](https://pytorch.org/get-started/locally/).

---

## User Roles

| Role | Access |
|---|---|
| **Player** | Dashboard, soundboard, spellbook, campaign membership |
| **DM** | Everything above + DM Panel, create campaigns, record/upload sessions, run analysis |
| **Developer** | Dashboard, soundboard, suggestions inbox |

Register with the DM or Developer role by entering the corresponding secret passphrase on the registration page.

---

## Features

### Soundboard
Each account supports multiple character soundboards.

- **Characters** — create multiple characters and switch between their boards
- **Record** — capture audio in-browser, preview, then save with a custom name
- **Upload** — upload mp3, wav, ogg, webm, m4a, aac (max 200 MB)
- **Play / Stop / Rename / Download / Delete**
- **Share** — send a sound to another user by username; they accept or decline

Audio stored in `uploads/soundboard/characters/<id>/`.

### Character Spellbook
Each character has a spellbook on the soundboard page.

- **SRD sync** — import all 5e SRD spells from Open5e
- **Add by level** — pick level, select from dropdown, add to character
- **Custom spells** — enter homebrew or 2024 spell text manually
- **Known spells panel** — review and remove spells per character

### Campaigns & Sessions

DMs can create campaigns, invite players, and manage session recordings.

**Campaign flow:**
1. DM creates a campaign and invites players by username
2. Players accept the invite from their campaign list
3. DM records or uploads sessions

**Session recording / upload:**
- **Record live** — browser-based recording (requires HTTPS + mic permission)
- **Upload existing file** — supports mp3, wav, m4a, ogg, flac, aac, mp4, webm

**Transcription** (requires `HF_AUTH_TOKEN` + ffmpeg):
- Click **Process Transcript** on a session to start Whisper + pyannote diarization
- Runs locally in a background thread — no audio sent externally
- After processing, the DM maps speaker labels (SPEAKER_00 etc.) to player names

**Session Analysis** (requires `ANTHROPIC_API_KEY`):
After transcription completes, click **Run Analysis** to kick off four concurrent passes:

| Analysis | What it produces |
|---|---|
| Summary | Narrative paragraph summary of session events |
| In / Out of Character | Transcript coloured by IC vs OOC speech; OOC segments are dimmed |
| Combat Timeline | Each combat encounter with start/end timestamps and a description |
| NPC Tracker | Every NPC mentioned — name, first appearance timestamp, session notes |

Results appear as links on the session page as each pass completes. Analysis uses `claude-haiku-4-5` by default (~$0.10–0.30 per session depending on length).

### Friends
Players can send and accept friend requests from the Friends page. Required before sharing soundboard items.

### Suggestions
Any authenticated user can submit feature suggestions. Developer accounts can view the inbox, assign suggestions, and update their status (New → Reviewing → Planned → Done).

---

## Project Structure

```
DnDHelper/
├── run.py                  # Entry point
├── config.py               # App configuration
├── requirements.txt
├── cert.pem / key.pem      # SSL certificate (not in git)
├── app/
│   ├── __init__.py         # App factory
│   ├── models.py           # SQLAlchemy models
│   ├── extensions.py       # db, login_manager
│   ├── decorators.py       # role_required
│   ├── blueprints/
│   │   ├── auth.py
│   │   ├── main.py
│   │   ├── soundboard.py
│   │   ├── campaign.py
│   │   ├── friends.py
│   │   └── suggestions.py
│   ├── services/
│   │   ├── transcription.py  # Whisper + pyannote pipeline
│   │   ├── analysis.py       # Claude API analysis pipeline
│   │   └── spell_sync.py     # Open5e SRD import
│   └── templates/
│       └── campaign/
│           ├── session_new.html
│           ├── session_view.html
│           ├── analysis_summary.html
│           ├── analysis_ic_ooc.html
│           ├── analysis_combat_phases.html
│           └── analysis_npcs.html
└── uploads/                # Created automatically, not in git
    ├── soundboard/
    ├── sessions/
    └── voice_samples/
```
