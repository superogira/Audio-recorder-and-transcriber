import pyaudio
import wave
from pydub import AudioSegment, effects
import numpy as np
import os
import time
import threading
import queue
from datetime import datetime
import requests
import json
import random
import msvcrt
import azure.cognitiveservices.speech as speechsdk
from google.cloud import speech
from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator


# สร้าง Event ควบคุมการพิมพ์ amplitude
print_event = threading.Event()
print_event.set()  # เริ่มต้นให้พิมพ์ได้

# === โหลด config จากไฟล์ ===
CONFIG_FILE = "recorder_transcriber-config.json"
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError("ไม่พบ recorder_transcriber-config.json")

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

# === ตั้งค่า AssemblyAI API (ยังไม่รองรับภาษาไทย) ===
ASSEMBLYAI_API_KEY = config.get("assemblyai_api_key", "") # Key สำหรับเรียก API
ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLYAI_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"

# === ตั้งค่า Azure Speech API ===
SPEECH_KEY = config.get("azure_speech_key","") # Key สำหรับเรียก API
SERVICE_REGION = config.get("azure_service_region","") # Location หรือ Region สำหรับเรียก Resource
LANGUAGE = config.get("azure_language","") # ภาษาที่จะถอดเสียง

# === ตั้งค่า Google Cloud API ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.get("google_credentials","") # ตำแหน่งและชื่อไฟล์ Credentials
LANGUAGE_CODE = config.get("google_language_code","") # ภาษาที่จะถอดเสียง

# === ตั้งค่า Speechmatics Speech-to-Text ===
SPEECHMATICS_API_KEY = config.get("speechmatics_api_key", "") # API KEY
SPEECHMATICS_LANGUAGE_CODE = config.get("speechmatics_language", "") # ภาษาที่จะถอดเสียง
SPEECHMATICS_URL = "https://asr.api.speechmatics.com/v2"

# === ตั้งค่า IBM Cloud Speech to Text (ยังไม่รองรับภาษาไทย) ===
IBM_API_KEY = config.get("ibm_api_key", "") # API KEY
IBM_LANGUAGE_CODE = config.get("ibm_language_code", "") # ภาษาที่จะถอดเสียง ยังไม่มีภาษาไทย
IBM_URL = config.get("ibm_url", "")

# ดึงการตั้งค่าจากไฟล์ recorder_config.json
FREQUENCY = config.get("frequency","") # ความถี่วิทยุที่ทำการบันทึกเสียงมา
STATION = config.get("station","") # สถานี หรือ นามเรียกขาน ของผู้บันทึกเสียง
THRESHOLD = config.get("threshold", 500) # ความดังต้องเกินกว่า ถึงจะเริ่มบันทึกเสียง
RECORD_SECONDS = config.get("record_length",60) # ระยะเวลาสูงสุดที่จะบันทึกได้
SILENCE_LIMIT = config.get("silence_limit", 1) # ถ้าเงียบเกินกว่า * วินาที ให้หยุดบันทึกเสียง
MIN_DURATION_SEC = config.get("min_duration_sec", 3) # ถ้าความยาวเสียงน้อยกว่า * วินาที ไม่ต้องบันทึกไฟล์ ไม่ต้องแปลงไฟล์
AUDIO_PRE_PROCESSING = config.get("audio_pre_processing", False) # ปิด-เปิด ระบบประมวผลไฟล์เสียง (Filter, Normalize)
AUDIO_FILTER = config.get("audio_filter", False) # ปิด-เปิด ระบบ Audio Filter
AUDIO_HIGH_PASS_FILTER = config.get("audio_high_pass_filter", 300) # ตั้งค่า Audio High Pass Filter (เสียงความถี่ สูงเกินกว่าเท่าไหร่ ถึงจะผ่านได้)
AUDIO_LOW_PASS_FILTER = config.get("audio_low_pass_filter", 8000) # ตั้งค่า Audio Low Pass Filter (เสียงความถี่ ต่ำกว่าเท่าไหร่ ถึงจะผ่านได้)
AUDIO_NORMALIZE = config.get("audio_normalize", False) # ปิด-เปิดระบบ ปรับระดับความดังของเสียงให้เท่า ๆ กัน
SAVE_FOLDER = config.get("save_folder","audio_files") # โฟลเดอร์สำหรับเก็บไฟล์เสียงที่บันทึก
LOG_FILE = config.get("log_file","system.log") # ชื่อไฟล์สำหรับเก็บ Log
NUM_WORKERS = config.get("num_workers", 2) # จำนวน worker ที่จะประมวลผลพร้อมกันได้ (เช่น 2 หรือ 4)
UPLOAD_ENABLED = config.get("upload", True) # ตั้งค่า เปิด-ปิด การใช้งานระบบอัพโหลดไฟล์ และบันทึกข้อมูล
UPLOAD_URL = config.get("upload_url", "https://e25wop.com/ham_radio_recorder_transcriber/upload.php") # URL ระบบอัพโหลดไฟล์ และบันทึกข้อมูล
ALTERNATE_ENGINES = config.get("alternate_engines", ["azure", "google"]) # ระบบที่จะใช้ใน alternate mode
RANDOM_ENGINES = config.get("random_engines", ["azure", "google"]) # ระบบที่จะใช้ใน random mode
TRANSCRIBE_ENGINE_MODE = config.get("transcribe_engine_mode", "azure") # เลือกระบบที่ต้องการใช้: "assemblyai", "azure", "google", "ibm", "speechmatics", "random, "alternate"

last_engine_index = -1

# === ตั้งค่าระบบ ===
CHUNK = 1024
RATE = 16000

os.makedirs(SAVE_FOLDER, exist_ok=True)
audio_queue = queue.Queue()

# ระบบบันทึก Log ลงไฟล์และแสดงผล
def log(msg):
    now = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    if print_event.is_set():
        print(f"{now} {msg}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{now} {msg}\n")

# ระบบปรับเปลี่ยนค่า Config ระหว่างทำงาน
def control_thread():
    global FREQUENCY
    global THRESHOLD
    global SILENCE_LIMIT
    global UPLOAD_ENABLED
    global TRANSCRIBE_ENGINE_MODE
    global AUDIO_PRE_PROCESSING
    """
    รันขนาบข้าง main loop เพื่ออ่านคำสั่งจาก stdin
    - หากผู้ใช้พิมพ์ F จะเข้าโหมดเปลี่ยน FREQUENCY
    - หากผู้ใช้พิมพ์ T จะเข้าโหมดเปลี่ยน THRESHOLD
    - หากผู้ใช้พิมพ์ S จะเข้าโหมดเปลี่ยน SILENCE_LIMIT
    - หากผู้ใช้พิมพ์ U จะสลับโหมดเปิด/ปิด UPLOAD_ENABLED
    - หากผู้ใช้พิมพ์ E จะเข้าโหมดเปลี่ยน TRANSCRIBE_ENGINE_MODE
    - หากผู้ใช้พิมพ์ A จะสลับโหมดเปิด/ปิด AUDIO_PRE_PROCESSING
    """
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getch().upper()
            if key == b'F':
                # หยุด Print
                print_event.clear()
                # ขึ้น prompt ให้ผู้ใช้ใส่ FREQUENCY ใหม่
                old = FREQUENCY
                new = input(f"\nปัจจุบัน FREQUENCY ค่าเดิมคือ {old}  กรุณาใส่ค่า FREQUENCY ใหม่: ").strip()
                # กลับมาอนุญาตให้ Print ได้ต่อ
                print_event.set()
                if new :
                    FREQUENCY = new
                    log(f"🔄 (Config) เปลี่ยน FREQUENCY จาก '{old}' เป็น '{new}' เรียบร้อย")

            elif key == b'T':
                # หยุด Print
                print_event.clear()
                # ขึ้น prompt ให้ผู้ใช้ใส่ THRESHOLD ใหม่
                old = THRESHOLD
                new = input(f"\nปัจจุบัน THRESHOLD ค่าเดิมคือ {old}  กรุณาใส่ค่า THRESHOLD ใหม่ (เฉพาะตัวเลข): ").strip()
                print_event.set()
                # ตรวจสอบว่าเป็นตัวเลขล้วน
                if new.isdigit():
                    THRESHOLD = int(new)
                    log(f"🔄 (Config) เปลี่ยน THRESHOLD จาก '{old}' เป็น '{new}' เรียบร้อย")
                else:
                    print_event.set()
                    log(f"❌ ค่าที่ป้อนไม่ถูกต้อง: `{new}` ไม่ใช่ตัวเลขล้วน")
            elif key == b'S':
                # หยุด Print
                print_event.clear()
                # ขึ้น prompt ให้ผู้ใช้ใส่ SILENCE_LIMIT ใหม่
                old = SILENCE_LIMIT
                new = input(f"\nปัจจุบัน SILENCE_LIMIT ค่าเดิมคือ {old}  กรุณาใส่ค่า SILENCE_LIMIT ใหม่ (เฉพาะตัวเลข): ").strip()
                print_event.set()
                # ตรวจสอบว่าเป็นตัวเลขล้วน
                if new.isdigit():
                    SILENCE_LIMIT = int(new)
                    log(f"🔄 (Config) เปลี่ยน SILENCE_LIMIT จาก '{old}' เป็น '{new}' เรียบร้อย")
                else:
                    log(f"❌ ค่าที่ป้อนไม่ถูกต้อง: `{new}` ไม่ใช่ตัวเลขล้วน")
            elif key == b'U':
                # หยุด Print
                print_event.clear()
                # ขึ้น prompt ให้ผู้ใช้เลือกสถานะการ UPLOAD
                # text = "เปิดใช้งานอยู่" if UPLOAD_ENABLED else "ปิดใช้งานอยู่"
                # new = input(f"\nปัจจุบัน UPLOAD {text}  หากต้องการเปลี่ยน ให้พิมพ์ 0 (ปิด) หรือ 1 (เปิด): ").strip()
                # print_event.set()
                if UPLOAD_ENABLED:
                    UPLOAD_ENABLED = False
                else:
                    UPLOAD_ENABLED = True
                print_event.set()
                log(f"🔄 (Config) ระบบ UPLOAD ตอนนี้ {'✅ เปิด' if UPLOAD_ENABLED else '❌ ปิด'} เรียบร้อย")
                """
                if new in ("0", "1"):
                    UPLOAD_ENABLED = (new == "1")
                    log(f"🔄 (Config) ระบบ UPLOAD ตอนนี้ {'✅ เปิด' if UPLOAD_ENABLED else '❌ ปิด'} เรียบร้อย")
                else:
                    log(f"❌ ค่าที่ป้อนไม่ถูกต้อง: `{new}` โปรดพิมพ์เฉพาะ 0 หรือ 1 เท่านั้น")
                """
            elif key == b'E':
                # หยุด Print
                print_event.clear()
                # ขึ้น prompt ให้ผู้ใช้เลือกโหมดแปลงเสียง
                old = TRANSCRIBE_ENGINE_MODE
                new = input(f"\nปัจจุบันระบบแปลงเสียง {old} ถูกเลือกไว้ กรุณาพิมพ์ระบบใหม่ที่ต้องการกำหนด (assemblyai, azure, google, ibm, speechmatics, random, alternate): ").strip()
                print_event.set()
                if new in ("azure", "google", "ibm", "speechmatics", "random", "alternate"):
                    TRANSCRIBE_ENGINE_MODE = new
                    log(f"🔄 (Config) เปลี่ยน TRANSCRIBE_ENGINE ระบบแปลงเสียงจาก '{old}' เป็น '{new}' เรียบร้อย")
                else:
                    log(f"❌ ค่าที่ป้อนไม่ถูกต้อง: `{new}` โปรดพิมพ์ assemblyai, azure, google, ibm, speechmatics, random หรือ alternate เท่านั้น")
            elif key == b'A':
                # หยุด Print
                print_event.clear()
                # ขึ้น prompt ให้ผู้ใช้เลือกการทำ Audio Pre Process
                # text = "เปิดใช้งานอยู่" if AUDIO_PRE_PROCESSING else "ปิดใช้งานอยู่"
                # new = input(f"\nปัจจุบัน Audio Pre-processing {text}  หากต้องการเปลี่ยน ให้พิมพ์ 0 (ปิด) หรือ 1 (เปิด): ").strip()
                #print_event.set()
                if AUDIO_PRE_PROCESSING:
                    AUDIO_PRE_PROCESSING = False
                else:
                    AUDIO_PRE_PROCESSING = True
                print_event.set()
                log(f"🔄 (Config) ระบบ Audio Pre-processing ตอนนี้ {'✅ เปิด' if AUDIO_PRE_PROCESSING else '❌ ปิด'} เรียบร้อย")
                """
                if new in ("0", "1"):
                    AUDIO_PRE_PROCESSING = (new == "1")
                    log(f"🔄 (Config) ระบบ Audio Pre-processing ตอนนี้ {'✅ เปิด' if AUDIO_PRE_PROCESSING else '❌ ปิด'} เรียบร้อย")
                else:
                    log(f"❌ ค่าที่ป้อนไม่ถูกต้อง: `{new}` โปรดพิมพ์เฉพาะ 0 หรือ 1 เท่านั้น")
                """
        time.sleep(0.1)
        # อาจขยายกรณีอื่นเช่น 'S' เปลี่ยน STATION ได้ตามต้องการ

# ระบบบันทึกเสียง
def record_until_silent():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    log(f"📡 รอฟังเสียง ({FREQUENCY}) ...")
    frames = []
    recording = False
    silence_chunks = 0 # นับจำนวน chunks ที่เงียบติดต่อกันระหว่างการบันทึก

    if TRANSCRIBE_ENGINE_MODE == "google":
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

        if print_event.is_set():
            print(f"️🎚️ Amplitude ({FREQUENCY}) : {amplitude:.2f}", end='\r')
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

# ระบบ Pre-processing ตัด noise, normalize volume, และ apply high-pass filter
def preprocess_audio(in_path):
    """
    1) โหลดไฟล์
    2) แปลงเป็น mono
    3) ตัดความถี่ต่ำ (<300 Hz) กับสูง (>8000 Hz)
    4) Normalize ระดับเสียง
    //5) (optional) ทำ noise reduction
    6) บันทึกไฟล์ใหม่แล้ว return path
    """
    # 1) โหลด
    sound = AudioSegment.from_file(in_path, format="wav")
    # 2) mono
    sound = sound.set_channels(1)
    # 3) high-pass + low-pass
    if AUDIO_FILTER:
        sound = sound.high_pass_filter(AUDIO_HIGH_PASS_FILTER).low_pass_filter(AUDIO_LOW_PASS_FILTER)
    # 4) normalize
    if AUDIO_NORMALIZE:
        sound = effects.normalize(sound)

    # 6) export
    out_path = in_path.replace(".wav", "_processed.wav")
    sound.export(out_path, format="wav")
    log("🎯 Pre-processing ไฟล์เสียงเรียบร้อย")
    return out_path

# ระบบถอดเสียงด้วย AssemblyAI
def transcribe_audio_assemblyai(filepath, duration, engine_used):
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json"
    }
    log(f"🧠 ส่งไฟล์ไป AssemblyAI: {filepath}")

    # 1) อัปโหลดไฟล์ ให้ได้ upload_url
    with open(filepath, "rb") as f:
        upload_resp = requests.post(
            ASSEMBLYAI_UPLOAD_URL,
            headers={"authorization": ASSEMBLYAI_API_KEY},
            data=f
        )
    upload_resp.raise_for_status()
    upload_url = upload_resp.json()["upload_url"]

    # 2) สร้าง transcript job
    json_payload = {
        "audio_url": upload_url,
        # ... ใส่ options เพิ่มเติมตามต้องการ เช่น speaker_labels, punctuate ...
    }
    # เปลี่ยนเป็นเก็บ response ก่อน raise
    transcript_resp = requests.post(
        ASSEMBLYAI_TRANSCRIPT_URL,
        headers=headers,
        json=json_payload
    )
    # พิมพ์สถานะและข้อความกลับมาให้เห็นชัดๆ
    log(f"🔍 AssemblyAI transcript request returned { transcript_resp.status_code }: {transcript_resp.text}")

    # ถ้าไม่สำเร็จ ก็ return
    if transcript_resp.status_code != 200:
        return

    job_resp = requests.post(
        ASSEMBLYAI_TRANSCRIPT_URL,
        headers=headers,
        json=json_payload
    )

    job_resp.raise_for_status()
    job_id = job_resp.json()["id"]
    log(f"🔍 AssemblyAI job created: {job_id}")

    # 3) Polling จนเสร็จ
    status = ""
    while status not in ("completed", "error"):
        time.sleep(5)
        status_resp = requests.get(
            f"{ASSEMBLYAI_TRANSCRIPT_URL}/{job_id}",
            headers=headers
        )
        status_resp.raise_for_status()
        j = status_resp.json()
        status = j["status"]
        log(f"🔄 AssemblyAI job {job_id} status: {status}")

    # 4) อ่านผลลัพธ์
    if status == "completed":
        text = j.get("text", "").strip()
        if text:
            log(f"✅ ถอดข้อความ (AssemblyAI): {text[:50]}…")
        else:
            log("❌ AssemblyAI: ไม่สามารถถอดข้อความจากเสียงได้")
            text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
    else:
        log(f"❌ AssemblyAI job error: {j.get('error', 'unknown')}")
        text = "[ยกเลิกหรือเกิดข้อผิดพลาด]"

    # 5) บันทึกและอัปโหลด
    with open(filepath.replace(".wav", ".txt"), "w", encoding="utf-8") as ftxt:
        ftxt.write(text)
    upload_audio_and_text(filepath, text, duration, engine_used)

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

# ระบบถอดเสียงด้วย IBM Cloud
def transcribe_audio_ibm(filepath, duration, engine_used):
    log(f"🧠 ส่งเสียงไป IBM Watson: {filepath}")
    authenticator = IAMAuthenticator(IBM_API_KEY)
    speech_to_text = SpeechToTextV1(authenticator=authenticator)
    speech_to_text.set_service_url(IBM_URL)

    with open(filepath, 'rb') as audio_file:
        response = speech_to_text.recognize(
            audio=audio_file,
            content_type='audio/wav',
            model=IBM_LANGUAGE_CODE,
            timestamps=False,
            word_confidence=False
        ).get_result()

    results = response.get("results", [])
    if results and "alternatives" in results[0]:
        text = results[0]["alternatives"][0]["transcript"]
        log(f"✅ ถอดข้อความ (IBM Watson): {text}")
    else:
        text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
        log("❌ IBM Watson: ไม่สามารถถอดข้อความจากเสียงได้")

    with open(filepath.replace(".wav", ".txt"), "w", encoding="utf-8") as f:
        f.write(text)

    upload_audio_and_text(filepath, text, duration, engine_used)

# ระบบถอดเสียงด้วย Speechmatics
def transcribe_audio_speechmatics(filepath, duration, engine_used):
    log(f"🧠 ส่งเสียงไป Speechmatics: {filepath}")
    headers = {
        'Authorization': f'Bearer {SPEECHMATICS_API_KEY}',
        'Accept': 'application/json'
    }

    # เตรียม JSON ตามสเปค v2
    config_payload = {
        "type": "transcription",
        "transcription_config": {
            "language": f"{SPEECHMATICS_LANGUAGE_CODE}"
            # ถ้าต้องการติวเพิ่ม เช่น operating_point, diarization ฯลฯ ให้ใส่ตรงนี้
        }
    }

    files = {
        'data_file': open(filepath, 'rb')
    }
    data = {
        'config': json.dumps(config_payload)
    }

    # เรียก POST jobs
    resp = requests.post(
        f"{SPEECHMATICS_URL}/jobs/",
        headers=headers,
        files=files,
        data=data
    )

    # 2xx หมดคือ success
    if not (200 <= resp.status_code < 300):
        err = resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else resp.text
        log(f"❌ Speechmatics error {resp.status_code}: {err}")
        return

    job = resp.json()
    # log(f"🔍 Speechmatics response on job creation: {job}")

    # ดึง job ID
    job_id = job.get("id") or job.get("job",{}).get("id")
    if not job_id:
        log("❌ ไม่พบ job ID ใน response")
        return

    # Poll status จนเสร็จ
    status = None
    while status != 'done':
        time.sleep(5)
        st = requests.get(f"{SPEECHMATICS_URL}/jobs/{job_id}", headers=headers)
        st.raise_for_status()
        resp_status = st.json()
        if 'status' in resp_status:
            status = resp_status['status']
        else:
            # ถ้า status อยู่ภายใน key 'job'
            status = resp_status.get('job', {}).get('status')

        if status is None:
            log(f"❌ ไม่พบ status ใน response ของ Speechmatics: {resp_status}")
            break

        # log(f"🔄 Speechmatics job {job_id} status: {status}")
        if status in ('failed', 'expired'):
            log(f"❌ Speechmatics job {job_id} failed.")
            text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
            break
    else:
        # ดาวน์โหลด transcript
        txt_resp = requests.get(f"{SPEECHMATICS_URL}/jobs/{job_id}/transcript?format=txt", headers=headers)
        txt_resp.raise_for_status()
        text = txt_resp.content.decode('utf-8').strip()

        # หลัง decode แล้วได้ตัวแปร text
        if text.strip():
            log(f"✅ ถอดข้อความ (Speechmatics): {text}")
        else:
            log("❌ Speechmatics: ไม่สามารถถอดข้อความจากเสียงได้")
            text = "[ไม่สามารถถอดข้อความจากเสียงได้]"

    # บันทึกและอัปโหลด
    with open(filepath.replace(".wav", ".txt"), "w", encoding="utf-8") as ftxt:
        ftxt.write(text)
    upload_audio_and_text(filepath, text, duration, engine_used)

# ระบบอัพโหลดไฟล์และข้อมูลเข้าไปเก็บที่เว็บและฐานข้อมูล
def upload_audio_and_text(audio_path, transcript, duration, engine_used):
    if not UPLOAD_ENABLED:
        log("❌☁️ ข้ามกระบวนการ Upload เนื่องด้วยการ Upload ถูกตั้งค่าปิดการใช้งาน")
        return

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
                engine = TRANSCRIBE_ENGINE_MODE

                if engine == "random":
                    engine = random.choice(RANDOM_ENGINES)
                elif engine == "alternate":
                    global last_engine_index
                    if not ALTERNATE_ENGINES:
                        log("⚠️ ไม่มีระบบใน alternate_engines ให้เลือกใช้งาน")
                        engine = "azure"  # fallback
                    else:
                        last_engine_index = (last_engine_index + 1) % len(ALTERNATE_ENGINES)
                        engine = ALTERNATE_ENGINES[last_engine_index]


                if engine == "assemblyai":
                    log(f"[Worker {worker_id}] 🎯 ใช้ระบบ AssemblyAI สำหรับการแปลงเสียง")
                    transcribe_audio_assemblyai(filepath, duration, engine)
                elif engine == "azure":
                    log(f"[Worker {worker_id}] 🎯 ใช้ระบบ Azure สำหรับการแปลงเสียง")
                    transcribe_audio_azure(filepath, duration, engine)
                elif engine == "google":
                    log(f"[Worker {worker_id}] 🎯 ใช้ระบบ Google Cloud สำหรับการแปลงเสียง")
                    transcribe_audio_google(filepath, duration, engine)
                elif engine == "ibm":
                    log(f"[Worker {worker_id}] 🎯 ใช้ระบบ IBM Cloud สำหรับการแปลงเสียง")
                    transcribe_audio_ibm(filepath, duration, engine)
                elif engine == "speechmatics":
                    log(f"[Worker {worker_id}] 🎯 ใช้ระบบ Speechmatics สำหรับการแปลงเสียง")
                    transcribe_audio_speechmatics(filepath, duration, engine)
                else:
                    log(f"[Worker {worker_id}] ⚠️ ไม่มีระบบแปลงเสียงที่เลือก '{engine}'")
            except Exception as e:
                log(f"[Worker {worker_id}]❌ ERROR: {e}")
        audio_queue.task_done()

def get_source_name(engine_key):
    return {
        "assemblyai": "AssemblyAI",
        "azure": "Azure AI Speech to Text",
        "google": "Google Cloud Speech-to-Text",
        "ibm": "IBM Cloud Watson Speech to Text",
        "speechmatics": "Speechmatics Speech-to-Text",
        "alternate": "แปลงเสียงเรียงตามกัน",
        "random": "สุ่มระบบแปลงเสียง"
    }.get(engine_key, "ไม่ทราบระบบแปลงเสียง")

# Loop ระบบหลัก
if __name__ == "__main__":
    # เริ่ม Control Thread ก่อนเลย
    threading.Thread(target=control_thread, daemon=True).start()

    log(f"🚀 เริ่มระบบ {get_source_name(TRANSCRIBE_ENGINE_MODE)} แบบ real-time (โหมด: {TRANSCRIBE_ENGINE_MODE})")

    if TRANSCRIBE_ENGINE_MODE == "alternate":
        log(f"🔁 ลำดับการวนใน alternate mode: {', '.join(ALTERNATE_ENGINES)}")

    if TRANSCRIBE_ENGINE_MODE == "random":
        log(f"🔁 รายการระบบที่นำมาใช้ใน random mode: {', '.join(RANDOM_ENGINES)}")

    print(
        " - กดปุ่ม F เพื่อเปลี่ยนข้อมูลความถี่ที่บันทึก\n"
        " - กดปุ่ม T เพื่อเปลี่ยนค่าการตรวจจับระดับเสียง\n"
        " - กดปุ่ม S เพื่อเปลี่ยนค่าระยะเวลาความเงียบของเสียง\n"
        " - กดปุ่ม U เพื่อ เปิด/ปิด ระบบ Upload\n"
        " - กดปุ่ม E เพื่อเปลี่ยนระบบ Transcribe\n"
        " - กดปุ่ม A เพื่อ เปิด/ปิด ระบบ Audio Pre-processing"
    )

    for i in range(NUM_WORKERS):
        threading.Thread(target=worker, args=(i+1,), daemon=True).start()

    # while True:
        # result = record_until_silent()
        # if result:
            # filepath, duration = result
            # if AUDIO_PRE_PROCESSING:
                # filepath = preprocess_audio(filepath)
            # else:
                # filepath, duration = result
            # audio_queue.put((filepath, duration))
        # time.sleep(0.5)

    def schedule_task(fp, dur):
        # ทำงานหนักฝั่งนี้ (เขียนไฟล์ preprocess แล้ว enqueue)
        if AUDIO_PRE_PROCESSING:
            fp2 = preprocess_audio(fp)
        else:
            fp2 = fp
        audio_queue.put((fp2, dur))

    while True:
        result = record_until_silent()
        if result:
            fp, dur = result
            # เรียก thread ใหม่ให้ทันที ไม่ต้องรอ
            threading.Thread(
                target=schedule_task,
                args=(fp, dur),
                daemon=True
            ).start()
        # เลือกจะใส่ sleep น้อยๆ เพื่อไม่ให้ loop เต็มเร็วเกินไป
        time.sleep(0.1)
