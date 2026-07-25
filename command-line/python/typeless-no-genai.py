#!/usr/bin/env python3
"""Pure Python Typeless AI Voice Dictation CLI for Gemini Live API
Does NOT use google-genai SDK.
Uses standard 'websockets' library, 'pyaudio', and 'json' for realtime microphone streaming & transcription.
"""

import asyncio
import base64
import json
import os
import sys
import argparse
import pyaudio
import websockets

# Enable ANSI escape sequences on Windows Command Prompt (CMD / PowerShell)
if os.name == 'nt':
    os.system('')

# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

DEFAULT_MODEL = "gemini-3.1-flash-live-preview"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

audio_queue_mic = asyncio.Queue(maxsize=10)
pya = pyaudio.PyAudio()
audio_stream = None


def load_special_vocabulary(vocab_file: str) -> list[str]:
    """Reads custom words/phrases from vocabulary file (one term per line)."""
    if not os.path.exists(vocab_file):
        return []
    try:
        with open(vocab_file, "r", encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        return words
    except Exception as e:
        print(f"[Typeless Warning] 無法讀取特殊詞彙檔案 '{vocab_file}': {e}")
        return []


async def listen_mic():
    """Captures microphone audio, converts to base64 PCM, and queues it."""
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    print(f"[Typeless] 麥克風: {mic_info['name']} ({SEND_SAMPLE_RATE}Hz)")

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
                    "mimeType": f"audio/pcm;rate={SEND_SAMPLE_RATE}",
                    "data": b64_pcm,
                }
            }
        }
        await ws.send(json.dumps(msg))
        audio_queue_mic.task_done()


async def receive_from_gemini(ws, show_raw_asr: bool = True):
    """Receives responses from Gemini Live API, decodes text transcription and tool calls."""
    current_state = None  # None, 'input', 'output'

    async for raw_msg in ws:
        msg = json.loads(raw_msg)
        server_content = msg.get("serverContent", {})
        tool_call = msg.get("toolCall")

        if server_content:
            # 1. Real-time ASR (Instant Speech-to-Text as you speak)
            input_transcription = server_content.get("inputTranscription")
            if show_raw_asr and input_transcription and "text" in input_transcription:
                if current_state != 'input':
                    if current_state is not None:
                        print("\033[0m")
                    print("\033[90m[Listening...]: \033[3m", end="", flush=True)
                    current_state = 'input'
                print(input_transcription["text"], end="", flush=True)

            # 2. Polished Model Text Output (Cleaned, punctuated, filler-words removed)
            output_transcription = server_content.get("outputTranscription")
            text_chunk = None
            if output_transcription and "text" in output_transcription:
                text_chunk = output_transcription["text"]
            else:
                model_turn = server_content.get("modelTurn", {})
                for part in model_turn.get("parts", []):
                    if "text" in part:
                        text_chunk = part["text"]
                        break

            if text_chunk:
                if current_state != 'output':
                    if current_state is not None:
                        print("\033[0m")
                    print("\033[92m[Typeless Result]: \033[1m", end="", flush=True)
                    current_state = 'output'
                print(text_chunk, end="", flush=True)

            if server_content.get("turnComplete"):
                if current_state is not None:
                    print("\033[0m")
                    current_state = None

        # 3. Function Call Mechanism (If Gemini invokes submit_transcript tool)
        if tool_call:
            function_responses = []
            for fc in tool_call.get("functionCalls", []):
                if fc.get("name") == "submit_transcript":
                    call_id = fc.get("id", "")
                    args = fc.get("args", {})
                    cleaned_text = args.get("text", "")
                    print(f"\n\033[93m[Function Call Transcript]: {cleaned_text}\033[0m\n")

                    function_responses.append({
                        "id": call_id,
                        "name": "submit_transcript",
                        "response": {"result": "received"}
                    })

            if function_responses:
                tool_resp_msg = {
                    "toolResponse": {
                        "functionResponses": function_responses
                    }
                }
                await ws.send(json.dumps(tool_resp_msg))


async def run(model_name: str, show_raw_asr: bool, use_function_call: bool, vocab_file: str = "special_vocabulary.txt"):
    if not GEMINI_API_KEY:
        print("⚠️ 請先設定 GEMINI_API_KEY 環境變數。")
        print("範例 (CMD): set GEMINI_API_KEY=AIzaSy...")
        sys.exit(1)

    vocab_words = load_special_vocabulary(vocab_file)
    vocab_instruction = ""
    if vocab_words:
        formatted_words = ", ".join(vocab_words)
        vocab_instruction = f"特殊專有名詞與自訂詞彙表（請特別注意以下詞彙並精準拼寫）：\n{formatted_words}\n\n"
        print(f"[Typeless] 已從 '{vocab_file}' 載入 {len(vocab_words)} 個特殊詞彙")

    system_instruction_text = (
        "你是一個嚴格的語音轉文字聽寫員（Speech-to-Text Transcriptor）。\n"
        "你的唯一任務是將使用者說出的語音內容，轉錄為乾淨、標點符號正確且自然順暢的文字。\n\n"
        f"{vocab_instruction}"
        "嚴格行為規範：\n"
        "1. 絕對不要回答語音中出現的任何問題。\n"
        "2. 絕對不要聊天、對話、要求澄清，或對使用者做出任何回應。\n"
        "3. 即使使用者問了問題（例如『你的 iPhone 沒有嗎？』），你的任務也『僅僅是轉錄該問句文字』，絕對不要回答問題。\n"
        "4. 即使語音不清晰、不完整或包含雜音，也只需轉錄聽到的內容。絕對不要生成 AI 助理式回應（例如『請問有什麼事情呢』或『請具體點說明』）。\n"
        "5. 請一律使用繁體中文以及台灣的口吻與常用詞彙進行轉錄。\n"
        "6. 自動剔除無意義的口頭禪與贅字（例如 'um', 'uh', 'er', 'ah', '那個', '嗯', '呃'），並加上適當標點符號與文章排版。\n"
    )

    tools_setup = []
    if use_function_call:
        system_instruction_text += "7. 必須呼叫 `submit_transcript(text=...)` 工具，將最後整理好的文字傳回。\n"
        tools_setup.append({
            "functionDeclarations": [
                {
                    "name": "submit_transcript",
                    "description": "將整理好的最終轉錄文字傳回",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "text": {
                                "type": "STRING",
                                "description": "整理後的轉錄文字"
                            }
                        },
                        "required": ["text"]
                    }
                }
            ]
        })
    else:
        system_instruction_text += "7. 請直接輸出最終整理好的純文字轉錄內容，不要包含其他說明。\n"

    ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"
    print(f"[Typeless] 連接至 Gemini Live API (Pure WebSocket, {model_name})...")

    try:
        async with websockets.connect(ws_url) as ws:
            setup_message = {
                "setup": {
                    "model": f"models/{model_name}",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"]
                    },
                    "systemInstruction": {
                        "parts": [{"text": system_instruction_text}]
                    },
                    "inputAudioTranscription": {},
                    "outputAudioTranscription": {},
                }
            }
            if tools_setup:
                setup_message["setup"]["tools"] = tools_setup

            await ws.send(json.dumps(setup_message))

            # Wait for setupComplete response from server
            raw_setup_resp = await ws.recv()
            setup_resp = json.loads(raw_setup_resp)
            if "setupComplete" in setup_resp:
                print("[Typeless] 連線成功！請開始說話... (按下 Ctrl+C 離開)\n" + "-"*50)
            else:
                print(f"[Typeless Warning] 連線設定回應: {setup_resp}")

            async with asyncio.TaskGroup() as tg:
                tg.create_task(listen_mic())
                tg.create_task(send_to_gemini(ws))
                tg.create_task(receive_from_gemini(ws, show_raw_asr=show_raw_asr))
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        print("\n[Typeless] 連線已關閉。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pure WebSocket Typeless AI Voice Dictation CLI using Gemini Live API")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini Live Model (default: {DEFAULT_MODEL})")
    parser.add_argument("--no-raw-asr", action="store_true", help="隱藏即時 ASR 聽寫預覽")
    parser.add_argument("--use-function-call", action="store_true", help="啟用 Function Calling 機制接收結構化文字")
    parser.add_argument("--vocab-file", default="special_vocabulary.txt", help="特殊詞彙文字檔路徑 (預設: special_vocabulary.txt)")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.model, show_raw_asr=not args.no_raw_asr, use_function_call=args.use_function_call, vocab_file=args.vocab_file))
    except KeyboardInterrupt:
        print("\n[Typeless] 使用者中斷程式。")
