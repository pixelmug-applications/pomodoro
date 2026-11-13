# Pomodoro Timer

Pomodoro Timer is a complete PixelMug application. Configure focus sessions, breaks, cycle count, and alert sounds in the WebApp, then sync the settings to PixelMug. The device runs the timer locally and responds to its physical controls.

## Project layout

- `bot/` — Bubble bot that opens the WebApp and binds a PixelMug.
- `webapp/` — Vue WebApp for setup and BLE synchronization.
- `mpy/` — MicroPython MPS application for the local timer.

## Run in PixelMug Studio

Open this folder in Studio and build the WebApp and Bot. Studio supplies `BOT_TOKEN`, `BOT_API_BASE_URL`, `STUDIO_WEBAPP_URL`, `STUDIO_MPS_ID`, and `STUDIO_MPS_VERSION` when the Bot runs. The WebApp and MPS use BLE app ID `Pomodoro` and version `1.0.0`.

For local development, install dependencies at the project root and in `webapp`, then run `npm run build` before starting the Bot.
