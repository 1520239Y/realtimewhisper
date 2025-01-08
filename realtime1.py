import asyncio
import websockets
import pyaudio
import numpy as np
import base64
import json
import wave
import io
import os
import sys
import time
from pynput import keyboard
from go2_tools import tools, tool_dict

shift_pressed = False

# タイミング計測用の辞書
timing_info = {
    "audio_capture_start": None,
    "audio_capture_end": None,
    "commit_time": None,
    "response_created_time": None,
    "response_done_time": None,
    "function_call_start_time": None,
    "function_call_end_time": None,
}

def on_press(key):
    global shift_pressed
    # Shiftが押された瞬間の時刻を記録
    if key == keyboard.Key.shift and not shift_pressed:
        shift_pressed = True
        timing_info["audio_capture_start"] = time.time()
        print("🎙️ Recording...")

def on_release(key):
    global shift_pressed
    # Shiftを離した時刻を記録
    if key == keyboard.Key.shift and shift_pressed:
        shift_pressed = False
        timing_info["audio_capture_end"] = time.time()

listener = keyboard.Listener(on_press=on_press, on_release=on_release)

def tool_handler(tool_name, args=None):
    # ロボットに行動命令を出すなどの処理をここに書く想定
    start = time.time()
    tool_dict[tool_name]()
    end = time.time()
    # ツール実行の終了時刻を記録（犬型ロボットを動かす想定）
    timing_info["function_call_end_time"] = end

    # 各種処理時間をログに出力
    log_timing_info()

def base64_to_pcm16(base64_audio):
    audio_data = base64.b64decode(base64_audio)
    return audio_data

async def send_audio(websocket, stream, CHUNK):
    def read_audio_block():
        try:
            return stream.read(CHUNK, exception_on_overflow=False)
        except Exception as e:
            print(f"[Error] {e}")
            return None

    audio_saved = False

    while True:
        if shift_pressed:
            audio_data = await asyncio.get_event_loop().run_in_executor(None, read_audio_block)
            if audio_data is None:
                continue
            audio_saved = True

            # PCM16データをBase64にエンコード
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            audio_event = {
                "type": "input_audio_buffer.append",
                "audio": base64_audio
            }
            await websocket.send(json.dumps(audio_event))
        else:
            if audio_saved:
                # 音声バッファの送信が完了した時点（Shiftを離した瞬間のあと）
                timing_info["commit_time"] = time.time()
                await websocket.send(json.dumps({"type": "input_audio_buffer.commit"}))
                await websocket.send(json.dumps({"type": "response.create"}))
                audio_saved = False

        await asyncio.sleep(0)

async def receive_audio(websocket, output_stream):
    loop = asyncio.get_event_loop()

    while True:
        response = await websocket.recv()
        response_data = json.loads(response)

        # 関数呼び出し（ロボット行動開始）に関するイベントを検知
        if (
            "type" in response_data and 
            response_data["type"] == "response.function_call_arguments.done"
        ):
            # ロボット行動開始の時刻を記録
            timing_info["function_call_start_time"] = time.time()

            func_name = response_data["name"]
            args = response_data["arguments"]
            call_id = response_data["call_id"]
            tool_handler(func_name)  # ツール（ロボット行動）実行

            # 実行結果を再度サーバーに返す
            func_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": "正常に動作しました。"
                }
            }
            await websocket.send(json.dumps(func_event))
            await websocket.send(json.dumps({"type": "response.create"}))
            print(f"<FunctionCalling> name: {func_name}, args: {args}", end="")

        elif "type" in response_data and response_data["type"] == "response.created":
            # サーバ側の処理（音声→テキスト変換含む）が開始されたとみなし記録
            timing_info["response_created_time"] = time.time()
            print("assistant: ", end="", flush=True)

        elif "type" in response_data and response_data["type"] == "response.audio_transcript.delta":
            # テキストが逐次表示される
            print(response_data["delta"], end="", flush=True)

        elif "type" in response_data and response_data["type"] == "response.done":
            # LLMの応答が完了した時刻を記録
            timing_info["response_done_time"] = time.time()
            print()  # 改行

            # 各種処理時間をログに出力
            log_timing_info()

        elif "type" in response_data and response_data["type"] == "error":
            print(f"error:\n{response_data['error']}")
            sys.exit()

        # サーバーからの音声応答データがある場合、スピーカーへ出力
        if "delta" in response_data:
            if response_data["type"] == "response.audio.delta":
                base64_audio_response = response_data["delta"]
                if base64_audio_response:
                    pcm16_audio = base64_to_pcm16(base64_audio_response)
                    await loop.run_in_executor(None, output_stream.write, pcm16_audio)

def log_timing_info():
    """
    音声取得からテキスト変換、LLM解析、ロボット行動まで
    それぞれの処理時間を計算して出力する
    """
    print("\n----- 処理時間計測ログ -----")
    # 1. 音声取得時間
    if timing_info["audio_capture_start"] and timing_info["audio_capture_end"]:
        audio_time = timing_info["audio_capture_end"] - timing_info["audio_capture_start"]
        print(f"  - 音声取得時間: {audio_time:.3f} 秒")
    # 2. 音声コミットから response.created まで（目安として音声→テキスト変換＋初期処理）
    if timing_info["commit_time"] and timing_info["response_created_time"]:
        text_conversion_time = timing_info["response_created_time"] - timing_info["commit_time"]
        print(f"  - 音声→テキスト変換＆LLM初期処理時間: {text_conversion_time:.3f} 秒")
    # 3. response.created から response.done まで（LLM解析推論）
    if timing_info["response_created_time"] and timing_info["response_done_time"]:
        llm_analysis_time = timing_info["response_done_time"] - timing_info["response_created_time"]
        print(f"  - LLM解析(推論)時間: {llm_analysis_time:.3f} 秒")
    # 4. ツール(ロボット行動)呼び出しの処理時間
    if timing_info["function_call_start_time"] and timing_info["function_call_end_time"]:
        robot_action_time = timing_info["function_call_end_time"] - timing_info["function_call_start_time"]
        print(f"  - ロボット行動実行時間: {robot_action_time:.3f} 秒")
    print("--------------------------\n")

API_KEY = os.environ.get('OPENAI_API_KEY')

# APIキーの存在チェック
if not API_KEY or API_KEY.strip() == "":
    print("[ERROR] OPENAI_API_KEYが設定されていません。環境変数にAPIキーを設定してください。")
    sys.exit(1)

# WebSocket接続先
WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
HEADERS = {
        "Authorization": "Bearer " + API_KEY,
        "OpenAI-Beta": "realtime=v1"
}

async def stream_audio_and_receive_response():
    async with websockets.connect(WS_URL, additional_headers=HEADERS) as websocket:
        print("[INFO] WebSocket connection established.")

        # リアルタイムセッションの初期設定
        init_request = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "instructions": "ユーザーからの入力に対し適切な動作を選択して呼び出してください。"
                                "例えば、「慰めて」や「なにかして」と言われたら適切な動作を選択して呼び出してください。"
                                "また、大阪弁で軽快に喋ってください。",
                "voice": "alloy",  # "alloy", "echo", "shimmer" など
                "turn_detection": None,
                "tools": tools,
                "tool_choice": "auto"
            }
        }
        await websocket.send(json.dumps(init_request))
        print("[INFO] Initial request sent to the server.\n")

        # PyAudioの設定
        CHUNK = 2048
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 24000

        p = pyaudio.PyAudio()

        # マイクストリームの初期化（input_device_index=None → OSのデフォルトデバイス）
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=None,
            frames_per_buffer=CHUNK
        )

        # 音声出力ストリーム（サーバー応答の読み上げ）
        output_stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=CHUNK
        )

        # 利用可能なオーディオデバイス一覧を表示（デバッグ用）
        print("Available audio devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"Index {i}: {info['name']} (Input Channels: {info['maxInputChannels']})")

        print("\n[INFO] Microphone input activated. Starting audio playback from server...\n")

        try:
            # 音声送信タスクと音声受信タスクを非同期で並行実行
            send_task = asyncio.create_task(send_audio(websocket, stream, CHUNK))
            receive_task = asyncio.create_task(receive_audio(websocket, output_stream))
            await asyncio.gather(send_task, receive_task)
        except KeyboardInterrupt:
            print("[Exit]")
        finally:
            if stream.is_active():
                    stream.stop_stream()
            stream.close()
            output_stream.stop_stream()
            output_stream.close()
            p.terminate()

if __name__ == "__main__":
    listener.start()
    asyncio.get_event_loop().run_until_complete(stream_audio_and_receive_response())
    listener.join()

