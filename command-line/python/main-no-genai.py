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
MODEL = "gemini-3.8-live"

# WebSocket endpoint using standard API Key
WS_URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"

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

        # 4. Handle tool calls (dual-path: top-level toolCall or modelTurn.parts)
        incoming_calls = []
        raw_tool_call = (
            msg.get("toolCall")
            or msg.get("tool_call")
            or server_content.get("toolCall")
            or server_content.get("tool_call")
        )
        if raw_tool_call:
            calls = raw_tool_call.get("functionCalls") or raw_tool_call.get("function_calls") or []
            incoming_calls.extend(calls)

        model_turn = server_content.get("modelTurn", {})
        parts = model_turn.get("parts", [])
        for part in parts:
            fc = part.get("functionCall") or part.get("function_call")
            if fc:
                if not any(c.get("id") == fc.get("id") for c in incoming_calls if c.get("id")):
                    incoming_calls.append(fc)

        if incoming_calls:
            asyncio.create_task(handle_tool_calls(ws, incoming_calls))

        # 5. Handle interaction status (Background reasoning tracking)
        interaction_status = (
            server_content.get("interactionStatus")
            or server_content.get("interaction_status")
            or msg.get("interactionStatus")
            or msg.get("interaction_status")
        )
        if interaction_status:
            if interaction_status == "IN_PROGRESS":
                print("\n\033[93m⚡ [Model Reasoning: IN_PROGRESS]\033[0m", flush=True)
            elif interaction_status == "REQUIRES_ACTION":
                print("\n\033[92m✅ [Model Status: REQUIRES_ACTION (Ready)]\033[0m", flush=True)

        # 6. Handle interruption
        if server_content.get("interrupted"):
            while not audio_queue_output.empty():
                audio_queue_output.get_nowait()


async def handle_tool_calls(ws, function_calls):
    """Executes tool calls concurrently and sends toolResponse back to Gemini."""
    async def execute_call(fc):
        call_id = fc.get("id", "")
        name = fc.get("name", "")
        args = fc.get("args", {})
        print(f"\n\033[93m🛠️ [Tool Call]: {name}({json.dumps(args, ensure_ascii=False)})\033[0m")
        # Default non-blocking tool execution
        response_payload = {
            "result": "ok",
            "scheduling": "INTERRUPT"
        }
        return {"id": call_id, "name": name, "response": response_payload}

    responses = await asyncio.gather(*(execute_call(fc) for fc in function_calls))
    tool_resp_msg = {
        "toolResponse": {
            "functionResponses": responses
        }
    }
    await ws.send(json.dumps(tool_resp_msg))
    print("\033[92m🛠️ [Tool Response Sent]\033[0m")


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
