# DnDHelper
A D&D companion web app for both players and Dungeon Masters to keep track of things and better role-play their characters.

## Running the Web App

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Start the server:**
```bash
python app.py
```

The app will be available at http://localhost:5000

To make it accessible on your local network, the server already binds to `0.0.0.0` — other devices on the same network can reach it via your machine's IP address on port 5000.

## Configuration

Edit `app.py` to change these settings before deploying:

| Setting | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-...` | **Change this** to a random string for security |
| `DM_SECRET` | `dungeon-master` | Passphrase required to register as a DM. Set to `None` to disable. |
| `SOUNDBOARD_UPLOAD_ROOT` | `uploads/soundboard/` | Directory where audio files are stored on disk |
| `MAX_CONTENT_LENGTH` | `10 MB` | Maximum audio file size per upload request |

## User Roles

| Role | Access |
|---|---|
| **Player** | Login, dashboard, soundboard |
| **DM** | Login, dashboard, DM Panel, soundboard |

Registering with the DM role requires the DM secret passphrase set in `app.py`.

## Features

### Soundboard
Each user has a personal soundboard — persistent across sessions and devices as long as they are logged in.

- **Record** — capture audio directly in the browser (uses the microphone), preview the recording, then save it with a custom name
- **Upload** — upload one or more audio files (mp3, wav, ogg, webm, m4a, aac · max 10 MB each); name each clip individually
- **Play / Stop** — click any soundboard button to play; clicking again or playing a different sound stops it
- **Rename** — edit a sound's display name in place
- **Download** — download the raw audio file for further editing
- **Delete** — permanently removes the sound from your board and disk
- **Share** — send a sound to another user by their username; the recipient gets a request they can accept or decline. Accepted sounds are copied independently to their soundboard

Audio files are stored in `uploads/soundboard/<user_id>/` on the server.

### Session Transcription Prerequisites
If you use session transcription (Whisper + speaker diarization), you need both Python packages and system audio tools.

- Install Python dependencies: `pip install -r requirements.txt`
- Install ffmpeg (includes ffprobe):
	- Windows (winget): `winget install --id Gyan.FFmpeg -e`
- After installing ffmpeg on Windows, restart your terminal (or VS Code) so PATH updates are picked up.
