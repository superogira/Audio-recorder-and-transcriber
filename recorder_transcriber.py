import pyaudio
import wave
import numpy as np
import os
import time
import threading
import queue
from datetime import datetime
import requests
import json
import random
import azure.cognitiveservices.speech as speechsdk
from google.cloud import speech

last_engine = None  # สำหรับ mode 'alternate'

# === โหลด config จากไฟล์ ===
CONFIG_FILE = "recorder_transcriber-config.json"
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError("ไม่พบ recorder_transcriber-config.json")

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

# === ตั้งค่า Azure Speech API===
SPEECH_KEY = config.get("azure_speech_key","") # Key สำหรับเรียก API
SERVICE_REGION = config.get("azure_service_region","") # Location หรือ Region สำหรับเรียก Resource
LANGUAGE = config.get("azure_language","") # ภาษาที่จะถอดเสียง

# === ตั้งค่า Google Cloud API ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.get("google_credentials","") # ตำแหน่งและชื่อไฟล์ Credentials
LANGUAGE_CODE = config.get("google_language_code","") # ภาษาที่จะถอดเสียง

# ดึงการตั้งค่าจากไฟล์ recorder_config.json
FREQUENCY = config.get("frequency","") # ความถี่วิทยุที่ทำการบันทึกเสียงมา
STATION = config.get("station","") # สถานี หรือ นามเรียกขาน ของผู้บันทึกเสียง
THRESHOLD = config.get("threshold", 500) # ความดังต้องเกินกว่า ถึงจะเริ่มบันทึกเสียง
RECORD_SECONDS = config.get("record_length",60) # ระยะเวลาสูงสุดที่จะบันทึกได้
SILENCE_LIMIT = config.get("silence_limit", 1) # ถ้าเงียบเกินกว่า * วินาที ให้หยุดบันทึกเสียง
MIN_DURATION_SEC = config.get("min_duration_sec", 3) # ถ้าความยาวเสียงน้อยกว่า * วินาที ไม่ต้องบันทึกไฟล์ ไม่ต้องแปลงไฟล์
SAVE_FOLDER = config.get("save_folder","audio_files") # โฟลเดอร์สำหรับเก็บไฟล์เสียงที่บันทึก
LOG_FILE = config.get("log_file","system.log") # ชื่อไฟล์สำหรับเก็บ Log
NUM_WORKERS = config.get("num_workers", 2) # จำนวน worker ที่จะประมวลผลพร้อมกัน (เช่น 2 หรือ 4)
UPLOAD_URL = config.get("upload_url", "https://catgg.net/ham_radio_recorder_transcriber/upload.php") # URL ระบบอัพโหลดไฟล์ และบันทึกข้อมูล
TRANSCRIBE_ENGINE = config.get("transcribe_engine", "azure") # เลือกระบบที่ต้องการใช้: "azure", "google", "random, "alternate"

# === ตั้งค่าระบบ ===
CHUNK = 1024
RATE = 16000

os.makedirs(SAVE_FOLDER, exist_ok=True)
audio_queue = queue.Queue()

# ระบบบันทึก Log ลงไฟล์และแสดงผล
def log(msg):
    now = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{now} {msg}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{now} {msg}\n")

# ระบบบันทึกเสียง
def record_until_silent():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    log("📡 รอฟังเสียง...")
    frames = []
    recording = False
    silence_chunks = 0 # นับจำนวน chunks ที่เงียบติดต่อกันระหว่างการบันทึก

    if TRANSCRIBE_ENGINE == "google":
        max_record_sec = 59  # ของ Google Cloud API หากอัดเสียงเกินกว่า 60 วินาที จะไม่สามารถถอดข้อความได้ จึงต้องกำหนดเป็น 59
    else:
        max_record_sec = RECORD_SECONDS

    # คำนวณจำนวน chunks สูงสุดที่อนุญาต
    # การคำนวณนี้ทำให้ max_chunks * (CHUNK / RATE) <= max_record_sec
    max_chunks = int(RATE / CHUNK * max_record_sec)

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_data = np.frombuffer(data, dtype=np.int16)
        amplitude = np.abs(audio_data).mean()

        print(f"🎚️ Amplitude: {amplitude:.2f}", end='\r')

        if not recording:
            if amplitude > THRESHOLD:
                log("🎙️ เริ่มอัด...")
                recording = True
                frames.append(data)  # เพิ่ม chunk แรกที่ทำให้เริ่มอัดเสียง
                silence_chunks = 0  # รีเซ็ตเมื่อเริ่มอัดและมีเสียง
            # ถ้ายังไม่ได้อัดและเสียงเบา ก็วนรอต่อไป
        else:  # recording is True (กำลังอัดเสียง)
            frames.append(data)  # เพิ่ม chunk ปัจจุบันเข้าไปใน frames

            if amplitude <= THRESHOLD:  # ถ้า chunk ปัจจุบันเสียงเบา
                silence_chunks += 1
            else:  # ถ้า chunk ปัจจุบันมีเสียงดัง
                silence_chunks = 0  # รีเซ็ตจำนวน chunks ที่เงียบ

            # ตรวจสอบเงื่อนไขการหยุดอัดเสียงหลังเพิ่มทุก chunk
            # 1. หยุดเพราะเงียบเป็นเวลานานพอ
            stopped_by_silence = silence_chunks > int(RATE / CHUNK * SILENCE_LIMIT)

            # 2. หยุดเพราะความยาวถึงขีดจำกัดสูงสุด
            # ใช้ >= max_chunks เพื่อให้แน่ใจว่าจำนวน frames ไม่เกิน max_chunks
            # ความยาวที่ได้จะเป็น max_chunks * (CHUNK / RATE) ซึ่งจะ <= max_record_sec
            stopped_by_length = len(frames) >= max_chunks

            if stopped_by_silence or stopped_by_length:
                if stopped_by_length and not stopped_by_silence:
                    log(f"🛑 หยุดอัด (ถึงขีดจำกัดความยาวสูงสุด {max_record_sec:.1f} วินาที)")
                elif stopped_by_silence and not stopped_by_length:
                    log(f"🛑 หยุดอัด (ตรวจพบความเงียบ {SILENCE_LIMIT} วินาที)")
                else:  # กรณีหยุดเพราะทั้งสองอย่าง หรืออย่างใดอย่างหนึ่งเกิดขึ้นพร้อมกัน
                    log(f"🛑 หยุดอัด (ถึงขีดจำกัดความยาวสูงสุด หรือ ตรวจพบความเงียบ)")
                break

    stream.stop_stream()
    stream.close()
    p.terminate()

    duration = len(frames) * CHUNK / RATE
    if duration < MIN_DURATION_SEC:
        log(f"⛔ เสียงสั้นเกินไป ({duration:.2f} วินาที) — ไม่บันทึก")
        return None

    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".wav"
    filepath = os.path.join(SAVE_FOLDER, filename)
    wf = wave.open(filepath, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    log(f"💾 บันทึกไฟล์เสียง ({duration:.2f} วินาที) : {filepath}")
    return filepath, duration

# ระบบถอดเสียงด้วย Azure
def transcribe_audio_azure(filepath, duration, engine_used):
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)
    speech_config.speech_recognition_language = LANGUAGE
    audio_config = speechsdk.audio.AudioConfig(filename=filepath)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    log(f"🧠 ส่งเสียงไป Azure: {filepath}")
    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        text = result.text.strip()
        log(f"✅ ถอดข้อความ (Azure): {text}")
    elif result.reason == speechsdk.ResultReason.NoMatch:
        text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
        log("❌ Azure: ไม่สามารถถอดข้อความจากเสียงได้")
    else:
        text = "[ยกเลิกหรือเกิดข้อผิดพลาด]"
        log(f"🚫 ยกเลิก: {result.reason}")

    with open(filepath.replace(".wav", ".txt"), "w", encoding="utf-8") as f:
        f.write(text)

    upload_audio_and_text(filepath, text, duration, engine_used)

# ระบบถอดเสียงด้วย Google Cloud
def transcribe_audio_google(filepath, duration, engine_used):
    client = speech.SpeechClient()
    log(f"🧠 ส่งเสียงไป Google: {filepath}")

    with open(filepath, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=LANGUAGE_CODE,
        audio_channel_count=1,
        enable_automatic_punctuation=True
    )

    response = client.recognize(config=config, audio=audio)

    if not response.results:
        log("❌ Google: ไม่สามารถถอดข้อความจากเสียงได้")
        text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
    else:
        text = response.results[0].alternatives[0].transcript
        log(f"✅ ถอดข้อความ (Google): {text}")

    with open(filepath.replace(".wav", ".txt"), "w", encoding="utf-8") as f:
        f.write(text)

    upload_audio_and_text(filepath, text, duration, engine_used)

# ระบบอัพโหลดไฟล์และข้อมูลเข้าไปเก็บที่เว็บและฐานข้อมูล
def upload_audio_and_text(audio_path, transcript, duration, engine_used):
    source_name = get_source_name(engine_used)

    files = {'audio': open(audio_path, 'rb')}
    data = {
        'transcript': transcript,
        'filename': os.path.basename(audio_path),
        'source': source_name,
        'frequency': FREQUENCY,
        'station': STATION,
        'duration': str(round(duration, 2))
    }
    try:
        res = requests.post(UPLOAD_URL, files=files, data=data)
        if res.status_code == 200:
            log(f"📤 ส่งข้อมูลไป: filename={data['filename']}, transcript={transcript[:30]}...")
            log("☁️ อัปโหลดเรียบร้อย")
        else:
            log(f"❌ Upload error: {res.status_code}")
    except Exception as e:
        log(f"❌ Upload exception: {e}")

def worker(worker_id):
    while True:
        task = audio_queue.get()
        if task:
            filepath, duration = task
            try:
                global last_engine

                engine = TRANSCRIBE_ENGINE

                if TRANSCRIBE_ENGINE == "random":
                    engine = random.choice(["azure", "google"])
                elif TRANSCRIBE_ENGINE == "alternate":
                    if last_engine == "azure":
                        engine = "google"
                    else:
                        engine = "azure"
                    last_engine = engine

                if engine == "azure":
                    log(f"[Worker {worker_id}] 🎯 ใช้ระบบ Azure สำหรับการแปลงเสียง")
                    transcribe_audio_azure(filepath, duration, engine)
                elif engine == "google":
                    log(f"[Worker {worker_id}]  ใช้ระบบ Google สำหรับการแปลงเสียง")
                    transcribe_audio_google(filepath, duration, engine)
                else:
                    log("⚠️ ยังไม่มีระบบแปลงเสียงที่เลือก")
            except Exception as e:
                log(f"[Worker {worker_id}]❌ ERROR: {e}")
        audio_queue.task_done()

def get_source_name(engine_key):
    return {
        "azure": "Azure AI Speech to Text",
        "google": "Google Cloud Speech-to-Text"
    }.get(engine_key, "ไม่ทราบระบบแปลงเสียง")

# Loop ระบบหลัก
if __name__ == "__main__":
    log(f"🚀 เริ่มระบบ {get_source_name(TRANSCRIBE_ENGINE)} แบบ real-time (โหมด: {TRANSCRIBE_ENGINE})")

    for i in range(NUM_WORKERS):
        threading.Thread(target=worker, args=(i+1,), daemon=True).start()

    while True:
        result = record_until_silent()
        if result:
            filepath, duration = result
            audio_queue.put((filepath, duration))
        time.sleep(0.5)
