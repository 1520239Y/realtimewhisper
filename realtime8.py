import asyncio
import websockets
import pyaudio
import base64
import json
import os
import sys
import time
import audioop  # 無音検出用
from go2_tools_test import tools, tool_dict

# タイミング計測用の辞書
timing_info = {
    "audio_capture_start": None,
    "audio_capture_end": None,
    "commit_time": None,
    "response_created_time": None,
    "response_done_time": None,
    "function_call_start_time": None,
    "function_call_end_time": None,

    # 追加: TTS関係のタイミング
    "tts_generation_start_time": None,
    "tts_generation_end_time": None,
    "tts_playback_start_time": None,
    "tts_playback_end_time": None,
}

def tool_handler(tool_name, args=None):
    """
    ロボット動作を実行する関数。
    ログの表示は行わず、function_callの開始・終了時刻のみ記録する。
    """
    timing_info["function_call_start_time"] = time.time()
    tool_dict[tool_name]()  # ここで実際のツール(ロボット行動等)を実行
    timing_info["function_call_end_time"] = time.time()
    # log_timing_info() は呼ばない

def base64_to_pcm16(base64_audio):
    audio_data = base64.b64decode(base64_audio)
    return audio_data

def log_timing_info():
    print("\n----- 処理時間計測ログ -----")

    # 1. 音声取得時間
    if timing_info["audio_capture_start"] and timing_info["audio_capture_end"]:
        audio_time = timing_info["audio_capture_end"] - timing_info["audio_capture_start"]
        print(f"  - 音声取得時間: {audio_time:.3f} 秒")

    # 2. 音声コミット後～LLM応答開始
    if timing_info["commit_time"] and timing_info["response_created_time"]:
        text_conversion_time = timing_info["response_created_time"] - timing_info["commit_time"]
        print(f"  - 音声→テキスト変換＆LLM初期処理時間: {text_conversion_time:.3f} 秒")

    # 3. 応答生成開始～応答完了 (LLM推論)
    if timing_info["response_created_time"] and timing_info["response_done_time"]:
        llm_analysis_time = timing_info["response_done_time"] - timing_info["response_created_time"]
        print(f"  - LLM解析(推論)時間: {llm_analysis_time:.3f} 秒")

    # 4. ツール(ロボット動作)実行時間
    if timing_info["function_call_start_time"] and timing_info["function_call_end_time"]:
        robot_action_time = timing_info["function_call_end_time"] - timing_info["function_call_start_time"]
        print(f"  - ロボット行動実行時間: {robot_action_time:.3f} 秒")

    # 追加: TTS生成時間
    if timing_info["tts_generation_start_time"] and timing_info["tts_generation_end_time"]:
        tts_gen_time = timing_info["tts_generation_end_time"] - timing_info["tts_generation_start_time"]
        print(f"  - TTS生成時間: {tts_gen_time:.3f} 秒")

    # 追加: TTS再生時間
    if timing_info["tts_playback_start_time"] and timing_info["tts_playback_end_time"]:
        tts_playback_time = timing_info["tts_playback_end_time"] - timing_info["tts_playback_start_time"]
        print(f"  - TTS再生時間: {tts_playback_time:.3f} 秒")

    print("--------------------------\n")

def reset_timing_info():
    """
    次回計測に備えて timing_info をリセットする場合に使用。
    必要なければ呼ばなくても良い。
    """
    global timing_info
    timing_info = {
        "audio_capture_start": None,
        "audio_capture_end": None,
        "commit_time": None,
        "response_created_time": None,
        "response_done_time": None,
        "function_call_start_time": None,
        "function_call_end_time": None,

        # TTS関連もリセット
        "tts_generation_start_time": None,
        "tts_generation_end_time": None,
        "tts_playback_start_time": None,
        "tts_playback_end_time": None,
    }

async def receive_audio(websocket, output_stream):
    loop = asyncio.get_event_loop()
    partial_transcript = ""
    response_in_progress = False

    while True:
        try:
            response = await websocket.recv()
        except websockets.ConnectionClosed:
            print("[WARN] The server closed the connection. Stopping receive loop.")
            break

        response_data = json.loads(response)

        # --- ツール呼び出し ---
        if response_data.get("type") == "response.function_call_arguments.done":
            func_name = response_data["name"]
            args = response_data["arguments"]
            call_id = response_data["call_id"]
            tool_handler(func_name)
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

        # --- 応答開始 ---
        elif response_data.get("type") == "response.created":
            timing_info["response_created_time"] = time.time()

            if not response_in_progress:
                print("assistant: ", end="", flush=True)
                response_in_progress = True

        # --- 応答途中 (テキスト) ---
        elif response_data.get("type") == "response.audio_transcript.delta":
            new_transcript = response_data["delta"]
            if new_transcript.startswith(partial_transcript):
                added_text = new_transcript[len(partial_transcript):]
                print(added_text, end="", flush=True)
            else:
                print(new_transcript, end="", flush=True)
            partial_transcript = new_transcript

        # --- 応答終了 ---
        elif response_data.get("type") == "response.done":
            timing_info["response_done_time"] = time.time()

            # TTS再生が終わったとみなすので、ここで記録
            if timing_info["tts_playback_start_time"] is not None:
                timing_info["tts_playback_end_time"] = time.time()

            print()  # 改行

            partial_transcript = ""
            response_in_progress = False

            # ここでログを表示
            log_timing_info()

        # --- エラー ---
        elif response_data.get("type") == "error":
            print(f"[ERROR from server] {response_data['error']}")

        # --- 音声応答 (TTS) ---
        if response_data.get("type") == "response.audio.delta":
            # TTS生成開始・終了時刻を計測
            if timing_info["tts_generation_start_time"] is None:
                # 最初のチャンクを受け取った瞬間に開始時間を記録
                timing_info["tts_generation_start_time"] = time.time()
                # 再生開始時間も同時に記録
                timing_info["tts_playback_start_time"] = time.time()

            # チャンク毎に終了時刻を更新（最後に受け取ったタイミング）
            timing_info["tts_generation_end_time"] = time.time()

            base64_audio_response = response_data["delta"]
            if base64_audio_response:
                pcm16_audio = base64_to_pcm16(base64_audio_response)
                await loop.run_in_executor(None, output_stream.write, pcm16_audio)

async def send_audio(websocket, stream, CHUNK):
    """
    ユーザの音声を常時取得し、無音判定で区切ってサーバに送る
    """
    timing_info["audio_capture_start"] = time.time()

    SILENCE_THRESHOLD = 1200
    MIN_SILENCE_CHUNKS = 20

    in_session = False
    silence_count = 0

    while True:
        try:
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: stream.read(CHUNK, exception_on_overflow=False)
            )
        except Exception as e:
            print(f"[Error reading audio] {e}")
            audio_data = None

        if not audio_data:
            await asyncio.sleep(0.01)
            continue

        volume = audioop.rms(audio_data, 2)
        is_silent = (volume < SILENCE_THRESHOLD)

        if in_session:
            # 発話中に無音が続けば終了
            if is_silent:
                silence_count += 1
            else:
                silence_count = 0

            if silence_count >= MIN_SILENCE_CHUNKS:
                timing_info["commit_time"] = time.time()
                try:
                    await websocket.send(json.dumps({"type": "input_audio_buffer.commit"}))
                    await websocket.send(json.dumps({"type": "response.create"}))
                except websockets.ConnectionClosed:
                    print("[WARN] The server closed the connection before commit.")
                    break
                in_session = False
                silence_count = 0
        else:
            # 発話開始
            if not is_silent:
                in_session = True
                silence_count = 0

        base64_audio = base64.b64encode(audio_data).decode("utf-8")
        audio_event = {
            "type": "input_audio_buffer.append",
            "audio": base64_audio
        }
        try:
            await websocket.send(json.dumps(audio_event))
        except websockets.ConnectionClosed:
            print("[WARN] The server closed the connection. Stopping send loop.")
            break

        await asyncio.sleep(0)

async def stream_audio_and_receive_response():
    API_KEY = os.environ.get('OPENAI_API_KEY')
    if not API_KEY or API_KEY.strip() == "":
        print("[ERROR] OPENAI_API_KEY が設定されていません。")
        return

    WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    HEADERS = {
        "Authorization": "Bearer " + API_KEY,
        "OpenAI-Beta": "realtime=v1"
    }

    async with websockets.connect(WS_URL, additional_headers=HEADERS) as websocket:
        print("[INFO] WebSocket connection established.")

        init_request = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "instructions": (
                    "ユーザーからの入力に対し適切な動作を選択して呼び出してください。"
                    "例えば、「慰めて」や「なにかして」と言われたら"
                    "適切な動作を選択して呼び出してください。"
                    "また、大阪弁で軽快に喋ってください。"
                ),
                "voice": "alloy",
                "turn_detection": None,
                "tools": tools,
                "tool_choice": "auto"
            }
        }
        await websocket.send(json.dumps(init_request))
        print("[INFO] Initial request sent.\n")

        CHUNK = 2048
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 24000

        p = pyaudio.PyAudio()

        # マイク用ストリーム
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=None,
            frames_per_buffer=CHUNK
        )

        # 応答音声再生用ストリーム
        output_stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=CHUNK
        )

        print("Available audio devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"Index {i}: {info['name']} (Input Channels: {info['maxInputChannels']})")

        print("\n[INFO] Microphone input activated. Starting audio playback from server...\n")
        print("[NOTE] ハウリング防止のため、ヘッドホン推奨 or マイクとスピーカーを離すなど調整してください。\n")

        send_task = asyncio.create_task(send_audio(websocket, stream, CHUNK))
        receive_task = asyncio.create_task(receive_audio(websocket, output_stream))

        try:
            await asyncio.gather(send_task, receive_task)
        except KeyboardInterrupt:
            print("[INFO] KeyboardInterrupt caught. Exiting now...")
        finally:
            timing_info["audio_capture_end"] = time.time()

            if stream.is_active():
                stream.stop_stream()
            stream.close()
            output_stream.stop_stream()
            output_stream.close()
            p.terminate()

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(stream_audio_and_receive_response())

if __name__ == "__main__":
    main()

