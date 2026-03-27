# DnDHelper
This is a D&D helper that is useful for both players and DMs keep track of things and better role play their characters

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

## User Roles

| Role | Access |
|---|---|
| **Player** | Login, dashboard |
| **DM** | Login, dashboard, DM Panel |

Register with the DM role requires the DM secret passphrase set in `app.py`.
