# SportsAnalyzer Stake Helper (Chrome extension)

Connects your **own logged-in Stake tab** to the local SportsAnalyzer app, so bets go out from
your real browser session. Nothing is installed from the internet: you load this folder directly.

## Install (once)
1. Open `chrome://extensions` in Chrome.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and choose this `extension` folder.
4. Pin "SportsAnalyzer Stake Helper" from the puzzle-piece menu if you want to see its status.

The local app (API on port 8000) must be running.

## What it does
- **Always:** every 5 s it tells the app it's connected and reports your Stake balance.
- **Learn mode (switch on the dashboard):** copies the *body* of Stake's own requests (operation
  name, query, variables) and the markets shown on the page. Request headers, which hold your
  login token, are never read.
- **Execution (switch on the dashboard, off by default):** asks the app for the next bet **you
  approved**, and places it from your Stake tab. The app re-checks every limit first:
  ₹1 per bet, ₹20 total, 10 bets a day (change them in `.env`).

## What it never does
- Place a bet you didn't approve, or anything while Execution is off.
- Send anything anywhere except `http://127.0.0.1:8000` (your own computer).
- Bypass Cloudflare or other site protections: it runs inside the real Stake page like you do.

To remove it: `chrome://extensions` → SportsAnalyzer Stake Helper → **Remove**.
