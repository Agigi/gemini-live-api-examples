# Gemini Live API – Command Line (Python)

Minimal command-line applications that stream microphone audio to the Gemini Live API and play back responses in real time using Python.

> **Note:** Use headphones. These scripts use system default audio input and output, which often won't include echo cancellation. To prevent the model from interrupting itself, use headphones.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Gemini API key ([get one here](https://aistudio.google.com/apikey))
- PortAudio (`brew install portaudio` on macOS)

## Setup

```bash
# Create a virtual environment and activate it
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install google-genai pyaudio websockets
```

## Running the Examples

Set your Gemini API Key first:

```bash
export GEMINI_API_KEY="your-api-key"
```

### 1. Official GenAI SDK Version (`main.py`)

Uses the official `google-genai` SDK to handle connection and live session management:

```bash
python main.py
```

### 2. Pure WebSocket Version without GenAI SDK (`main-no-genai.py`)

Communicates directly with the Gemini Live API over WebSocket using standard `websockets` + `json` + `base64` without requiring the `google-genai` SDK:

```bash
python main-no-genai.py
```

You should see **"Connected to Gemini Live API!"** — speak into your microphone and Gemini will respond with audio in real time. Press `Ctrl+C` to quit.

## Real-time Audio Stream Translation (`translate.py`)

A CLI script to translate any remote audio stream URL in real-time using the SDK.

### Run Translation Script

```bash
python translate.py --target es
```

- `--url`: The audio stream URL you want to translate (defaults to a sample WAV audio file: `https://storage.googleapis.com/generativeai-downloads/gemini-cookbook/audio/gemini-live-translate-sample.wav`).
- `--target`: The target translation language code (e.g., `es` for Spanish, `fr` for French, `pl` for Polish). Defaults to `es`.
- `--original-volume`: Volume level for playing the original speaker's audio in the background (float from `0.0` to `1.0`, defaults to `0.08` or 8% volume). Set to `0.0` to disable background playback.

The script will stream the audio, play the original speaker softly in the background, print both the source and translated transcripts with their language codes (e.g., `[Source (en)]` / `[Translation (es)]`), and play the translated audio stream in real-time.
