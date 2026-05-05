# DnD Helper — Mobile App

Expo (React Native) companion app for the DnD Helper Flask backend.

## Prerequisites

- [Node.js LTS](https://nodejs.org/) (v20+)
- [Expo Go](https://expo.dev/go) installed on your phone
- DnD Helper Flask server running on your PC

## Setup

```bash
# From the repo root
cd mobile
npm install
```

## Configure server URL

Edit `src/config.ts` and set `SERVER_URL` to your PC's **local IP address**:

```ts
// Find your PC's IP: run `ipconfig` in cmd and look for IPv4 Address
export const SERVER_URL = "http://192.168.1.42:5000";
```

> **Note:** The Flask server must be running in HTTP mode (not HTTPS) for local dev,
> since React Native rejects self-signed certificates. In `run.py`, temporarily pass
> `ssl_context=None` or `ssl_context='adhoc'` won't work either — just remove ssl_context
> for mobile testing.

## Run

```bash
npx expo start
```

Scan the QR code with Expo Go on your phone. Your phone must be on the **same Wi-Fi network** as your PC.

## Tips

- Long-press a tracker in the list to delete it.
- Tap the pencil icon ✏️ on a combatant to enter a custom roll.
- Natural 20s show in gold; natural 1s show in red.

## Tailscale (for remote access)

Install [Tailscale](https://tailscale.com/) on both PC and phone. Once connected,
use your PC's Tailscale IP (e.g. `100.x.x.x`) as the `SERVER_URL`. This lets
you access the server from anywhere without port forwarding.
