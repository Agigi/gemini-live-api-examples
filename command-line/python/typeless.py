import os
import sys
import asyncio
import argparse
import pyaudio
from google import genai
from google.genai import types

# Enable ANSI escape sequences on Windows Command Prompt (CMD / PowerShell)
if os.name == 'nt':
    os.system('')

# PyAudio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

# Live API configuration
DEFAULT_MODEL = "gemini-3.1-flash-live-preview"

audio_queue_mic = asyncio.Queue(maxsize=10)
pya = pyaudio.PyAudio()
audio_stream = None

# Custom tool definition for Function Calling (optional extra mechanism)
def submit_transcript(text: str) -> dict:
    """Submit the cleaned, formatted transcript of what the user spoke."""
    return {"status": "success", "received_length": len(text)}

async def listen_audio():
    """Listens for audio from microphone and puts raw PCM bytes into queue."""
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    print(f"[Typeless] Microphone: {mic_info['name']} ({SEND_SAMPLE_RATE}Hz)")
    
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
        await audio_queue_mic.put(data)

async def send_realtime(session):
    """Sends audio from microphone queue to Gemini Live API."""
    while True:
        chunk = await audio_queue_mic.get()
        await session.send_realtime_input(
            audio=types.Blob(
                data=chunk,
                mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}"
            )
        )
        audio_queue_mic.task_done()

async def receive_responses(session, show_raw_asr: bool = True):
    """Receives responses from Gemini Live API and prints transcription to command line."""
    current_state = None  # None, 'input', 'output'
    
    while True:
        async for response in session.receive():
            server_content = response.server_content
            tool_call = response.tool_call

            if server_content:
                # 1. Real-time ASR (Instant Speech-to-Text as you speak)
                if show_raw_asr and server_content.input_transcription and server_content.input_transcription.text:
                    if current_state != 'input':
                        if current_state is not None:
                            print("\033[0m")
                        print("\033[90m[Listening...]: \033[3m", end="", flush=True)
                        current_state = 'input'
                    t = server_content.input_transcription.text
                    print(t, end="", flush=True)

                # 2. Polished Model Text Output (Cleaned, punctuated, filler-words removed)
                text_chunk = None
                if server_content.output_transcription and server_content.output_transcription.text:
                    text_chunk = server_content.output_transcription.text
                elif server_content.model_turn:
                    for part in server_content.model_turn.parts:
                        if part.text:
                            text_chunk = part.text
                            break

                if text_chunk:
                    if current_state != 'output':
                        if current_state is not None:
                            print("\033[0m")
                        print("\033[92m[Typeless Result]: \033[1m", end="", flush=True)
                        current_state = 'output'
                    print(text_chunk, end="", flush=True)

                if server_content.turn_complete:
                    if current_state is not None:
                        print("\033[0m")
                        current_state = None

            # 3. Function Call Mechanism (If Gemini invokes submit_transcript tool)
            if tool_call:
                function_responses = []
                for fc in tool_call.function_calls:
                    if fc.name == "submit_transcript":
                        cleaned_text = fc.args.get("text", "")
                        print(f"\n\033[93m[Function Call Transcript]: {cleaned_text}\033[0m\n")
                        
                        function_responses.append(
                            types.FunctionResponse(
                                name=fc.name,
                                id=fc.id,
                                response={"result": "received"}
                            )
                        )
                if function_responses:
                    await session.send_tool_response(function_responses=function_responses)

def load_special_vocabulary(vocab_file: str) -> list[str]:
    """Reads custom words/phrases from vocabulary file (one term per line)."""
    if not os.path.exists(vocab_file):
        return []
    try:
        with open(vocab_file, "r", encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        return words
    except Exception as e:
        print(f"[Typeless Warning] Failed to read vocabulary file '{vocab_file}': {e}")
        return []

async def run(model_name: str, show_raw_asr: bool, use_function_call: bool, vocab_file: str = "special_vocabulary.txt"):
    client = genai.Client()

    vocab_words = load_special_vocabulary(vocab_file)
    vocab_instruction = ""
    if vocab_words:
        formatted_words = ", ".join(vocab_words)
        vocab_instruction = f"特殊專有名詞與自訂詞彙表（請特別注意以下詞彙並精準拼寫）：\n{formatted_words}\n\n"
        print(f"[Typeless] 已從 '{vocab_file}' 載入 {len(vocab_words)} 個特殊詞彙")

    system_instruction = (
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

    tools = []
    if use_function_call:
        system_instruction += "7. 必須呼叫 `submit_transcript(text=...)` 工具，將最後整理好的文字傳回。\n"
        tools.append(submit_transcript)
    else:
        system_instruction += "7. 請直接輸出最終整理好的純文字轉錄內容，不要包含其他說明。\n"

    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],  # Gemini Live API requires AUDIO modality connection
        system_instruction=types.Content(parts=[types.Part(text=system_instruction)]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        tools=tools if tools else None,
    )

    print(f"[Typeless] Connecting to Gemini Live API ({model_name})...")
    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            print("[Typeless] Connected! Start speaking now... (Press Ctrl+C to exit)\n" + "-"*50)
            async with asyncio.TaskGroup() as tg:
                tg.create_task(listen_audio())
                tg.create_task(send_realtime(session))
                tg.create_task(receive_responses(session, show_raw_asr=show_raw_asr))
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        print("\n[Typeless] Connection closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Typeless-style AI Voice Dictation CLI using Gemini Live API")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini Live Model (default: {DEFAULT_MODEL})")
    parser.add_argument("--no-raw-asr", action="store_true", help="Hide raw real-time speech recognition preview")
    parser.add_argument("--use-function-call", action="store_true", help="Enable Function Calling mechanism to receive structured text")
    parser.add_argument("--vocab-file", default="special_vocabulary.txt", help="Path to custom vocabulary text file (default: special_vocabulary.txt)")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.model, show_raw_asr=not args.no_raw_asr, use_function_call=args.use_function_call, vocab_file=args.vocab_file))
    except KeyboardInterrupt:
        print("\n[Typeless] Interrupted by user.")