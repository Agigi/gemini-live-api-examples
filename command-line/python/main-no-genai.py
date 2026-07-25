#!/usr/bin/env python3
"""Pure Python Real-Time Voice Chat Client for Gemini Live API
Does NOT use google-genai SDK.
Uses standard 'websockets' library, 'pyaudio', and 'json' for realtime microphone streaming & speaker playback.
"""

import asyncio
import base64
import json
import os
import sys
import pyaudio
import websockets

# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-3.1-flash-live-preview"

# WebSocket endpoint using standard API Key
WS_URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"

pya = pyaudio.PyAudio()
audio_queue_output = asyncio.Queue()
audio_queue_mic = asyncio.Queue(maxsize=5)
audio_stream = None


async def listen_mic():
    """Captures microphone audio, converts to base64 PCM, and queues it."""
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )
    kwargs = {"exception_on_overflow": False} if __debug__ else {}
    while True:
        data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, **kwargs)
        base64_pcm = base64.b64encode(data).decode("utf-8")
        await audio_queue_mic.put(base64_pcm)


async def send_to_gemini(ws):
    """Sends microphone audio chunks from queue to Gemini Live API WebSocket."""
    while True:
        b64_pcm = await audio_queue_mic.get()
        msg = {
            "realtimeInput": {
                "audio": {
                    "mimeType": "audio/pcm",
                    "data": b64_pcm,
                }
            }
        }
        await ws.send(json.dumps(msg))


async def receive_from_gemini(ws):
    """Receives responses from Gemini Live API, decodes audio bytes and text transcription."""
    last_was_input = False
    async for raw_msg in ws:
        msg = json.loads(raw_msg)
        server_content = msg.get("serverContent", {})

        # 1. Parse audio output parts
        model_turn = server_content.get("modelTurn", {})
        for part in model_turn.get("parts", []):
            inline_data = part.get("inlineData", {})
            if inline_data and "data" in inline_data:
                pcm_bytes = base64.b64decode(inline_data["data"])
                audio_queue_output.put_nowait(pcm_bytes)

        # 2. Print output transcription (Gemini speaking)
        output_transcription = server_content.get("outputTranscription")
        if output_transcription and "text" in output_transcription:
            if last_was_input:
                print()
                last_was_input = False
            t = output_transcription.get("text", "")
            print(t, end="", flush=True)
            if t.rstrip()[-1:] in ".!?":
                print()

        # 3. Print input transcription (User speaking)
        input_transcription = server_content.get("inputTranscription")
        if input_transcription and "text" in input_transcription:
            if not last_was_input:
                print()
                last_was_input = True
            t = input_transcription.get("text", "")
            print(f"\033[3m{t}\033[0m", end="", flush=True)
            if t.rstrip()[-1:] in ".!?":
                print()

        # 4. Handle interruption
        if server_content.get("interrupted"):
            while not audio_queue_output.empty():
                audio_queue_output.get_nowait()


async def play_audio():
    """Plays received PCM audio data from queue to speaker."""
    stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE,
        output=True,
    )
    while True:
        pcm_bytes = await audio_queue_output.get()
        await asyncio.to_thread(stream.write, pcm_bytes)


async def main():
    if not GEMINI_API_KEY:
        print("⚠️ Please set GEMINI_API_KEY environment variable.")
        print("Example (CMD): set GEMINI_API_KEY=AIzaSy...")
        sys.exit(1)

    print("🔌 Connecting to Gemini Live API via pure WebSocket...")

    try:
        async with websockets.connect(WS_URL) as ws:
            # Send initial setup message
            setup_message = {
                "setup": {
                    "model": f"models/{MODEL}",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {
                                    "voiceName": "Puck"
                                }
                            }
                        },
                    },
                    "systemInstruction": {
                        "parts": [{"text": "You are a helpful and friendly AI assistant."}]
                    },
                    "outputAudioTranscription": {},
                    "inputAudioTranscription": {},
                }
            }
            await ws.send(json.dumps(setup_message))

            # Wait for setupComplete response
            setup_resp = await ws.recv()
            print("✅ Connected to Gemini Live API!")
            print("🎙️ Start speaking into your microphone... (Press Ctrl+C to quit)\n")

            async with asyncio.TaskGroup() as tg:
                tg.create_task(listen_mic())
                tg.create_task(send_to_gemini(ws))
                tg.create_task(receive_from_gemini(ws))
                tg.create_task(play_audio())
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        print("\n👋 Disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user.")
