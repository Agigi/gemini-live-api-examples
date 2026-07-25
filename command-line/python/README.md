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

### 1. Voice Chat Assistant (GenAI SDK) (`main.py`)

Uses the official `google-genai` SDK to handle connection and live session management:

```bash
python main.py
```

### 2. Pure WebSocket Voice Chat Assistant (`main-no-genai.py`)

Communicates directly with the Gemini Live API over WebSocket using standard `websockets` + `json` + `base64` without requiring the `google-genai` SDK:

```bash
python main-no-genai.py
```

You should see **"Connected to Gemini Live API!"** — speak into your microphone and Gemini will respond with audio in real time. Press `Ctrl+C` to quit.

## Typeless AI Voice Dictation (`typeless.py` & `typeless-no-genai.py`)

AI-powered voice dictation and text polishing tools inspired by Typeless. Unlike general AI assistants, these scripts do not engage in conversation or answer questions—they strictly transcribe spoken speech into clean, formatted, and punctuated Traditional Chinese text with filler words removed.

### 1. GenAI SDK Version (`typeless.py`)

```bash
python typeless.py
```

### 2. Pure WebSocket Version (`typeless-no-genai.py`)

```bash
python typeless-no-genai.py
```

### Command Line Flags & Options

Both `typeless.py` and `typeless-no-genai.py` support the following options:

- `--model`: Specify the Gemini Live model (default: `gemini-3.1-flash-live-preview`).
- `--no-raw-asr`: Hide the real-time gray ASR preview (`[Listening...]`) and only show the final polished transcription result (`[Typeless Result]`).
- `--use-function-call`: Enable Function Calling mechanism, forcing Gemini to return the structured transcript via a `submit_transcript(text=...)` function call.
- `--vocab-file`: Path to custom vocabulary text file (default: `special_vocabulary.txt`). Terms listed in this file (one per line) will be injected into the prompt to ensure accurate spelling of specialized terms and proper nouns.

### Example Usage Commands

```bash
# Default mode (shows real-time ASR preview and loads special_vocabulary.txt)
python typeless-no-genai.py

# Hide raw real-time ASR preview and only output final polished text
python typeless-no-genai.py --no-raw-asr

# Enable Function Calling structured transcript output
python typeless-no-genai.py --use-function-call

# Use a custom vocabulary file
python typeless-no-genai.py --vocab-file my_custom_terms.txt
```

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
