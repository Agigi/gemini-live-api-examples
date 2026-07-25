# Gemini Live API - Vanilla JS (No google-genai SDK)

WebSocket web application for Google's Gemini Live API with real-time audio, video, and text streaming, operating **without any dependency on the `google-genai` Python SDK**.

## Background & Evolution

This project evolved from [`gemini-live-ephemeral-tokens-websocket`](../gemini-live-ephemeral-tokens-websocket/):

* **Original Approach (`gemini-live-ephemeral-tokens-websocket`)**:
  The Python backend imports the `google-genai` SDK and uses `GEMINI_API_KEY` to request short-lived (ephemeral) tokens via `/api/token`. The frontend then uses these tokens to establish WebSocket connections.
* **Evolved Approach (`gemini-live-api-key-websocket-no-genai`)**:
  Authentication is moved to the client side—the user inputs their Gemini API Key directly into the browser UI. The browser establishes a direct WebSocket connection to `generativelanguage.googleapis.com` using `?key=YOUR_API_KEY`.
* **Zero SDK Overhead**:
  Because authentication and WebSocket streaming occur entirely within the browser, the Python backend server (`server.py`) is simplified into a lightweight static HTTP file server. The `google-genai` Python SDK dependency is completely removed.

## Features

- **Direct Browser-to-API WebSocket Connection**: Low-latency, real-time bidirectional audio/video/text streaming directly from the browser to Gemini Live API (`BidiGenerateContent`).
- **Zero Backend SDK Dependency**: Python backend requires no Google GenAI SDK or environment variables, functioning purely as a static web host (`aiohttp`).
- **UI API Key Authentication**: Easily enter and test Gemini API Keys directly in the web UI.
- **Multimodal Support**: Audio input/output, camera video streaming, and screen sharing.
- **Rich Configuration Options**:
  - Expanded Voice Choices: `Puck`, `Charon`, `Kore`, `Fenrir`, `Aoede`, `Zephyr`, `Leda`, `Orus`.
  - System instructions, temperature, activity detection, and sensitivity controls.
- **Tools & Grounding**: Supports custom frontend tools (Alert box, CSS style injector) and Google Search grounding.

## Quick Start

### 1. Install Minimal Dependencies

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

*(Only `aiohttp` is required for hosting static files)*

### 2. Start Server & Launch App

```bash
python server.py
```

1. Open `http://localhost:8000` in your browser.
2. Enter your Gemini API Key directly in the **Gemini API Key** field.
3. Click **Connect** to start chatting with Gemini in real time!

## Project Structure

```
/
├── server.py        # Lightweight static web server (No genai SDK required)
├── requirements.txt # Minimal Python dependency (aiohttp)
└── frontend/
    ├── index.html    # UI with direct API Key input field
    ├── geminilive.js # Vanilla JS WebSocket client
    ├── mediaUtils.js # Real-time audio/video streaming & recording
    ├── tools.js      # Custom tool implementations
    └── script.js     # Main application workflow logic
```

## Comparison

| Feature | `gemini-live-ephemeral-tokens-websocket` | `gemini-live-api-key-websocket-no-genai` |
| :--- | :--- | :--- |
| **Authentication** | Ephemeral Tokens via backend `/api/token` | Direct API Key input in browser UI |
| **Backend Dependency** | `google-genai`, `python-dotenv`, `aiohttp` | `aiohttp` (Zero GenAI SDK dependency) |
| **WebSocket Endpoint** | `BidiGenerateContentConstrained?access_token=...` | `BidiGenerateContent?key=...` |
| **Ideal For** | Production (hides API key on backend) | Local Testing, Demo & Lightweight Prototyping |
