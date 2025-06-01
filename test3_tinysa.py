# coding: utf-8

import pyaudio
import wave
from pydub import AudioSegment, effects
import numpy as np
import os
import time
import threading
import queue
from datetime import datetime, time as dt_time
import requests
import json
import random
import azure.cognitiveservices.speech as speechsdk
from google.cloud import speech
from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
import subprocess
import serial
import re # สำหรับ parse output

# Imports ใหม่สำหรับ Cross-platform keyboard input
import platform
if platform.system() == "Windows":
    import msvcrt
else: # Linux/macOS
    import sys
    import select
    import tty
    import termios


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
AZURE_TTS_RESPONSES_ENABLED = config.get("azure_tts_responses_enabled", False)
TTS_RESPONSES_CONFIG = config.get("tts_responses", [])

# === ตั้งค่า Google Cloud API ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.get("google_credentials","") # ตำแหน่งและชื่อไฟล์ Credentials
LANGUAGE_CODE = config.get("google_language_code","") # ภาษาที่จะถอดเสียง

# === ตั้งค่า Speechmatics Speech-to-Text ===
SPEECHMATICS_API_KEY = config.get("speechmatics_api_key", "") # API KEY
SPEECHMATICS_LANGUAGE_CODE = config.get("speechmatics_language", "") # ภาษาที่จะถอดเสียง
SPEECHMATICS_OPERATING_POINT = config.get("speechmatics_operating_point", "standard") # Accuracy
SPEECHMATICS_URL = "https://asr.api.speechmatics.com/v2"

# === ตั้งค่า IBM Cloud Speech to Text (ยังไม่รองรับภาษาไทย) ===
IBM_API_KEY = config.get("ibm_api_key", "") # API KEY
IBM_LANGUAGE_CODE = config.get("ibm_language_code", "") # ภาษาที่จะถอดเสียง ยังไม่มีภาษาไทย
IBM_URL = config.get("ibm_url", "")

# --- การตั้งค่า (ควรจะมาจาก config file ของคุณ) ---
TINYSA_ENABLED = config.get("tinysa_enabled", True)
TINYSA_SERIAL_PORT = '/dev/ttyACM0'  # <<<< แก้ไขเป็นพอร์ตที่ถูกต้องของ TinySA บน Pi ของคุณ
TINYSA_BAUDRATE = 115200            # Baudrate ปกติของ TinySA คือ 115200 หรือตรวจสอบจากคู่มือ
TARGET_FREQUENCY_HZ = 145200000    # ความถี่ที่คุณต้องการวัด (Hz)
TINYSA_SWEEP_POINTS = config.get("tinysa_sweep_points", 40) # จำนวนจุดในการ sweep
TINYSA_REPEAT_INTERVAL = config.get("tinysa_repeat_interval", 5) # ms (ตามที่คุณระบุ)
# อาจจะต้องมีตัวแปรเก็บสถานะของ TinySA (paused/resumed)
tinysa_is_paused = True # เริ่มต้นให้ pause ไว้ก่อน
# คุณอาจจะต้องมีค่าอื่นๆ เช่น RBW, Attenuation ที่เหมาะสมกับการวัดของคุณ

# ดึงการตั้งค่าจากไฟล์ recorder_config.json
FREQUENCY = config.get("frequency","") # ความถี่วิทยุที่ทำการบันทึกเสียงมา
STATION = config.get("station","") # สถานี หรือ นามเรียกขาน ของผู้บันทึกเสียง
RECORDING_SCHEDULE_ENABLED = config.get("recording_schedule_enabled", False) # ค่า default คือ False (ไม่ใช้ตารางเวลา)
RECORDING_SCHEDULE = config.get("recording_schedule", []) # ค่า default คือ array ว่าง
THRESHOLD = config.get("threshold", 500) # ความดังต้องเกินกว่า ถึงจะเริ่มบันทึกเสียง
RECORD_SECONDS = config.get("record_length",60) # ระยะเวลาสูงสุดที่จะบันทึกได้
SILENCE_LIMIT = config.get("silence_limit", 1) # ถ้าเงียบเกินกว่า * วินาที ให้หยุดบันทึกเสียง
MIN_DURATION_SEC = config.get("min_duration_sec", 3) # ถ้าความยาวเสียงน้อยกว่า * วินาที ไม่ต้องบันทึกไฟล์ ไม่ต้องแปลงไฟล์
AUDIO_PRE_PROCESSING = config.get("audio_pre_processing", False) # ปิด-เปิด ระบบประมวผลไฟล์เสียง (Filter, Normalize)
AUDIO_FILTER = config.get("audio_filter", False) # ปิด-เปิด ระบบ Audio Filter
AUDIO_HIGH_PASS_FILTER = config.get("audio_high_pass_filter", 300) # ตั้งค่า Audio High Pass Filter (เสียงความถี่ สูงเกินกว่าเท่าไหร่ ถึงจะผ่านได้)
AUDIO_LOW_PASS_FILTER = config.get("audio_low_pass_filter", 8000) # ตั้งค่า Audio Low Pass Filter (เสียงความถี่ ต่ำกว่าเท่าไหร่ ถึงจะผ่านได้)
AUDIO_NORMALIZE = config.get("audio_normalize", False) # ปิด-เปิดระบบ ปรับระดับความดังของเสียงให้เท่า ๆ กัน
MP3_CONVERSION_ENABLED = config.get("mp3_conversion_enabled", True) # ค่า default คือ True (เปิดใช้งาน)
MP3_BITRATE = config.get("mp3_bitrate","24k") # bitrate ที่ใช้สำหรับการแปลงเป็น mp3
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

# ระบบบ Schedule
def is_within_scheduled_time(schedule_list):
    """
    ตรวจสอบว่าเวลาปัจจุบันอยู่ในช่วงเวลาใดๆ ที่กำหนดใน schedule_list หรือไม่
    schedule_list คือ array ของ dictionaries ที่มี "start_time" และ "end_time"
    """
    if not schedule_list: # ถ้าไม่มีตารางเวลาเลย ก็ถือว่าอยู่นอกตาราง
        return False

    now_time = datetime.now().time() # เวลาปัจจุบัน (เฉพาะส่วนเวลา)

    for schedule_item in schedule_list:
        try:
            start_h, start_m = map(int, schedule_item.get("start_time", "00:00").split(':'))
            end_h, end_m = map(int, schedule_item.get("end_time", "23:59").split(':'))

            start_dt_time = dt_time(start_h, start_m)
            end_dt_time = dt_time(end_h, end_m)

            if start_dt_time <= end_dt_time:
                # กรณีที่ช่วงเวลาไม่ข้ามวัน (เช่น 08:00 - 17:00)
                if start_dt_time <= now_time <= end_dt_time:
                    return True
            else: # กรณีที่ช่วงเวลาข้ามวัน (เช่น 22:00 - 02:00)
                if now_time >= start_dt_time or now_time <= end_dt_time:
                    return True
        except ValueError:
            log(f"⚠️ รูปแบบเวลาใน schedule ไม่ถูกต้อง: {schedule_item}")
            continue # ข้ามรายการนี้ไป แล้วตรวจสอบรายการถัดไป
    return False

# ฟังก์ชันสำหรับ non-blocking keyboard input บน Linux/macOS
if platform.system() != "Windows":
    def kbhit_linux():
        """ตรวจสอบว่ามี key ถูกกดหรือไม่บน Linux/macOS"""
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

    def getch_linux():
        """อ่าน key ที่ถูกกดบน Linux/macOS"""
        if not kbhit_linux(): # ควรตรวจสอบ kbhit_linux() ก่อนเรียก getch_linux()
            return None
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

# ระบบปรับเปลี่ยนค่า Config ระหว่างทำงาน
def control_thread():
    global FREQUENCY
    global THRESHOLD
    global SILENCE_LIMIT
    global UPLOAD_ENABLED
    global TRANSCRIBE_ENGINE_MODE
    global AUDIO_PRE_PROCESSING
    global MP3_CONVERSION_ENABLED
    """
    รันขนาบข้าง main loop เพื่ออ่านคำสั่งจาก stdin
    - หากผู้ใช้พิมพ์ F จะเข้าโหมดเปลี่ยน FREQUENCY
    - หากผู้ใช้พิมพ์ T จะเข้าโหมดเปลี่ยน THRESHOLD
    - หากผู้ใช้พิมพ์ S จะเข้าโหมดเปลี่ยน SILENCE_LIMIT
    - หากผู้ใช้พิมพ์ U จะสลับโหมดเปิด/ปิด UPLOAD_ENABLED
    - หากผู้ใช้พิมพ์ E จะเข้าโหมดเปลี่ยน TRANSCRIBE_ENGINE_MODE
    - หากผู้ใช้พิมพ์ A จะสลับโหมดเปิด/ปิด AUDIO_PRE_PROCESSING
    - หากผู้ใช้พิมพ์ M จะสลับโหมดเปิด/ปิด MP3 Conversion
    """

    is_windows = platform.system() == "Windows"

    while True:
        key_pressed_detected = False
        char_pressed_value = None

        if is_windows:
            if msvcrt.kbhit():
                key_pressed_detected = True
                # msvcrt.getch() returns bytes, convert to string and uppercase
                try:
                    char_pressed_value = msvcrt.getch().decode('utf-8', errors='ignore').upper()
                except: # Handle potential errors if it's a special key not decodable
                    pass
        else: # Linux/macOS
            if kbhit_linux():
                log("DEBUG: kbhit_linux() is True")  # เพิ่ม log
                key_pressed_detected = True
                # getch_linux() returns string, just uppercase
                char_val = getch_linux()
                log(f"DEBUG: getch_linux() returned: {repr(char_val)}")  # เพิ่ม log ดูค่าที่ได้
                if char_val:
                     char_pressed_value = char_val.upper()

        if key_pressed_detected and char_pressed_value:
            if char_pressed_value  == 'F':
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

            elif char_pressed_value  == 'T':
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
            elif char_pressed_value  == 'S':
                # หยุด Print
                print_event.clear()
                # ขึ้น prompt ให้ผู้ใช้ใส่ SILENCE_LIMIT ใหม่
                old = SILENCE_LIMIT
                new = input(f"\nปัจจุบัน SILENCE_LIMIT ค่าเดิมคือ {old}  กรุณาใส่ค่า SILENCE_LIMIT ใหม่ (เฉพาะตัวเลข): ").strip()
                print_event.set()
                """
                # ตรวจสอบว่าเป็นตัวเลขล้วน
                if new.isdigit():
                    SILENCE_LIMIT = int(new)
                    log(f"🔄 (Config) เปลี่ยน SILENCE_LIMIT จาก '{old}' เป็น '{new}' เรียบร้อย")
                else:
                    log(f"❌ ค่าที่ป้อนไม่ถูกต้อง: `{new}` ไม่ใช่ตัวเลขล้วน")
                """
                try:
                    # พยายามแปลงเป็น float
                    new_float_val = float(new)
                    SILENCE_LIMIT = new_float_val # เก็บเป็น float
                    log(f"🔄 (Config) เปลี่ยน SILENCE_LIMIT จาก '{old}' เป็น '{SILENCE_LIMIT}' เรียบร้อย")
                except ValueError:
                    # หากแปลงเป็น float ไม่สำเร็จ (เช่น ผู้ใช้ใส่ตัวอักษร)
                    log(f"❌ ค่าที่ป้อนไม่ถูกต้อง: `{new}` ไม่ใช่ตัวเลขหรือทศนิยมที่ถูกต้อง")

            elif char_pressed_value  == 'U':
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
            elif char_pressed_value  == 'E':
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
            elif char_pressed_value  == 'A':
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
            elif char_pressed_value == 'M': # สมมติว่าใช้ 'M' สำหรับ MP3 Conversion
                print_event.clear()
                if MP3_CONVERSION_ENABLED:
                    MP3_CONVERSION_ENABLED = False
                else:
                    MP3_CONVERSION_ENABLED = True
                print_event.set()
                log(f"🔄 (Config) การแปลงเป็น MP3 ตอนนี้ {'✅ เปิดใช้งาน' if MP3_CONVERSION_ENABLED else '❌ ปิดใช้งาน'}")

        time.sleep(0.1)
        # อาจขยายกรณีอื่นเช่น 'S' เปลี่ยน STATION ได้ตามต้องการ

# ระบบบันทึกเสียง
def record_until_silent(pyaudio_instance, tinysa_ser=None):
    global tinysa_is_paused  # เพื่อให้สามารถอ้างอิงและแก้ไขสถานะได้
    stream = None  # <<<< กำหนดค่าเริ่มต้นเป็น None
    frames = []  # <<<< ย้าย frames มาประกาศที่นี่เพื่อให้ finally เห็น
    recording = False
    silence_chunks = 0 # นับจำนวน chunks ที่เงียบติดต่อกันระหว่างการบันทึก

    signal_strengths_db = []  # List สำหรับเก็บค่าความแรงสัญญาณ
    last_tinysa_check_time = 0 # ตั้งเป็น 0 เพื่อให้เช็คครั้งแรกเลยเมื่อเริ่มอัด

    try:
        stream = pyaudio_instance.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        # --- เมื่อเริ่มรอฟังเสียง ให้แน่ใจว่า TinySA pause อยู่ (ถ้าจะควบคุมแบบนี้) ---
        # หรือจะ resume ตอนเริ่มอัดเลยก็ได้
        if TINYSA_ENABLED and tinysa_ser and not tinysa_is_paused:  # ถ้าเปิดใช้งาน TinySA และมันยังไม่ pause
            pause_tinysa(tinysa_ser)

        # log(f"📡 รอฟังเสียง ({FREQUENCY}) ...")
        log(f"📡 รอฟังเสียง ({FREQUENCY}) ... (TinySA Paused: {tinysa_is_paused})")

        if TRANSCRIBE_ENGINE_MODE == "google":
            max_record_sec = 59  # ของ Google Cloud API หากอัดเสียงเกินกว่า 60 วินาที จะไม่สามารถถอดข้อความได้ จึงต้องกำหนดเป็น 59
        else:
            max_record_sec = RECORD_SECONDS

        # คำนวณจำนวน chunks สูงสุดที่อนุญาต
        # การคำนวณนี้ทำให้ max_chunks * (CHUNK / RATE) <= max_record_sec
        max_chunks = int(RATE / CHUNK * max_record_sec)

        last_rtl_sdr_check_time = time.time()

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
                    # --- เมื่อเริ่มอัด ให้ Resume TinySA และวัดค่าครั้งแรก ---
                    if TINYSA_ENABLED and tinysa_ser:
                        resume_tinysa(tinysa_ser)
                        # อาจจะ setup ใหม่ถ้าความถี่เปลี่ยน (ถ้า FREQUENCY เปลี่ยนได้)
                        current_monitoring_freq_hz_for_tinysa = int(
                            float(FREQUENCY) * 1_000_000) if FREQUENCY.upper() != "SCAN" else TARGET_FREQUENCY_HZ

                        # Setup TinySA (จะถูกเรียกถ้าความถี่เปลี่ยน หรือครั้งแรก)
                        # คุณอาจจะต้องมี logic เพิ่มเติมถ้าต้องการ setup ทุกครั้งที่เริ่ม record ใหม่
                        # หรือ setup เฉพาะเมื่อความถี่เปลี่ยนจริงๆ
                        # if getattr(tinysa_ser, 'last_configured_freq_tinysa', None) != current_monitoring_freq_hz_for_tinysa or \
                        #    getattr(tinysa_ser, 'needs_initial_setup', True): # เพิ่ม flag สำหรับ setup ครั้งแรก
                        setup_tinysa_for_measurement(tinysa_ser, current_monitoring_freq_hz_for_tinysa,
                                                     TINYSA_SWEEP_POINTS, TINYSA_REPEAT_INTERVAL)

                        # time.sleep(TINYSA_REPEAT_INTERVAL / 1000 * 2)  # รอ sweep แรก
                        # strength = get_signal_strength_tinysa(tinysa_ser)
                        # if strength is not None:
                        #     signal_strengths_db.append(strength)
                        # last_tinysa_check_time = time.time()
                        last_tinysa_check_time = time.time()  # << รีเซ็ตเวลาเช็ค เพื่อให้รอบถัดไปรอ 1 วินาทีจริงๆ # ไม่มีการอ่านค่า strength ทันทีตรงนี้แล้ว

            else:  # recording is True (กำลังอัดเสียง)
                frames.append(data)  # เพิ่ม chunk ปัจจุบันเข้าไปใน frames

                # --- อ่านค่าความแรงสัญญาณจาก TinySA เป็นระยะ (เมื่อ recording = True) ---
                if TINYSA_ENABLED and tinysa_ser and not tinysa_is_paused and (time.time() - last_tinysa_check_time >= 1.5):  # อ่านทุกๆ 1.5 วินาที (ปรับได้)

                    # ไม่จำเป็นต้อง setup TinySA ซ้ำที่นี่ ยกเว้น FREQUENCY มีการเปลี่ยนแปลงแบบ dynamic
                    # ซึ่ง control_thread ควรจะจัดการเรื่องการ re-setup ถ้า FREQUENCY เปลี่ยน

                    strength = get_signal_strength_tinysa(tinysa_ser)
                    # if strength is not None:
                    #     signal_strengths_db.append(strength)
                    # last_tinysa_check_time = time.time()
                    if strength is not None:
                        if not signal_strengths_db and len(frames) < (
                                RATE / CHUNK * 0.5):  # ตัวอย่าง: ถ้าเป็นค่าแรกๆ และยังอัดไม่ถึง 0.5 วิ อาจจะข้าม
                            log(f"📡 [TinySA] ข้ามการเก็บค่าสัญญาณรอบแรก: {strength:.2f} dBm (เพื่อรอความเสถียร)")
                        else:
                            signal_strengths_db.append(strength)
                            log(f"📡 [TinySA] เก็บค่าสัญญาณ: {strength:.2f} dBm")
                    last_tinysa_check_time = time.time()

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
                    # log(f"🛑 หยุดอัด (...พร้อมข้อมูลสัญญาณถ้ามี...)")
                    # --- เมื่อหยุดอัด ให้ Pause TinySA ---
                    if TINYSA_ENABLED and tinysa_ser:
                        pause_tinysa(tinysa_ser)
                    if stopped_by_length and not stopped_by_silence:
                        log(f"🛑 หยุดอัด (ถึงขีดจำกัดความยาวสูงสุด {max_record_sec:.1f} วินาที)")
                    elif stopped_by_silence and not stopped_by_length:
                        log(f"🛑 หยุดอัด (ตรวจพบความเงียบ {SILENCE_LIMIT} วินาที)")
                    else:  # กรณีหยุดเพราะทั้งสองอย่าง หรืออย่างใดอย่างหนึ่งเกิดขึ้นพร้อมกัน
                        log(f"🛑 หยุดอัด (ถึงขีดจำกัดความยาวสูงสุด หรือ ตรวจพบความเงียบ)")
                    break

    except Exception as e:
        log(f"❌ เกิดข้อผิดพลาดระหว่างการเปิด stream หรือบันทึก: {e}")
        # อาจจะพยายามปิด stream และ p ถ้าเกิด error ที่นี่
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e_close:
                log(f"⚠️ Error ปิด stream หลังเกิด exception: {e_close}")
        return None  # คืนค่า None ถ้าเกิดข้อผิดพลาด
    finally:
        if stream is not None:  # <<<< ตรวจสอบว่า stream ถูกสร้างแล้วหรือยัง
            try:
                if stream.is_active():  # <<<< ตรวจสอบว่า stream active ก่อน stop
                    stream.stop_stream()
                stream.close()
                log("🔇 Stream ปิดเรียบร้อยแล้วใน finally")
            except Exception as e_close:
                log(f"⚠️ Error ปิด stream ใน finally: {e_close}")
        # ไม่ต้อง p.terminate() ที่นี่แล้ว จะไปทำข้างนอกสุด

    if not frames:  # ถ้าไม่มี frames เลย (เช่น เกิด error ก่อนเริ่มอัด)
        log(f"⛔ ไม่มีข้อมูลเสียงที่ถูกบันทึก")
        return None

    duration = len(frames) * CHUNK / RATE
    if duration < MIN_DURATION_SEC:
        log(f"⛔ เสียงสั้นเกินไป ({duration:.2f} วินาที) — ไม่บันทึก")
        return None

    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".wav"
    filepath = os.path.join(SAVE_FOLDER, filename)

    average_signal_db = None
    num_strength_samples = len(signal_strengths_db)  # จำนวนตัวอย่างความแรงสัญญาณที่เก็บได้

    if num_strength_samples > 0:
        log(f"📊 [SignalCalc] จำนวนตัวอย่างความแรงสัญญาณที่เก็บได้: {num_strength_samples}")
        log(f"   [SignalCalc] ค่าทั้งหมด: {['{:.2f}'.format(s) for s in signal_strengths_db]}")

        if num_strength_samples >= 3:
            # ถ้ามีอย่างน้อย 3 ค่า ให้ตัดค่าแรกและค่าสุดท้ายออก
            meaningful_strengths = signal_strengths_db[1:-1] # เอาตั้งแต่ index 1 จนถึงก่อนตัวสุดท้าย
            if meaningful_strengths: # ตรวจสอบอีกครั้งว่าหลังจากตัดแล้วยังมีข้อมูล
                average_signal_db = sum(meaningful_strengths) / len(meaningful_strengths)
                log(f"📊 [SignalCalc] คำนวณค่าเฉลี่ยจาก {len(meaningful_strengths)} ค่า (ตัดหัวท้าย): {average_signal_db:.2f} dBm")
            else: # กรณีที่ num_strength_samples คือ 2 พอดี แล้ว [1:-1] จะได้ list ว่าง
                # ในกรณีนี้ เราอาจจะเลือกใช้ค่าเฉลี่ยของทั้งสองค่าเดิม หรือค่าเดียว
                average_signal_db = sum(signal_strengths_db) / num_strength_samples
                log(f"📊 [SignalCalc] มีตัวอย่างน้อยกว่า 3 (คือ {num_strength_samples} ค่า), คำนวณจากทั้งหมด: {average_signal_db:.2f} dBm")

        elif num_strength_samples > 0: # ถ้ามี 1 หรือ 2 ค่า
            # คำนวณค่าเฉลี่ยจากทั้งหมดที่มี (เพราะตัดหัวท้ายไม่ได้ หรือไม่มีประโยชน์)
            average_signal_db = sum(signal_strengths_db) / num_strength_samples
            log(f"📊 [SignalCalc] มีตัวอย่างน้อยเกินไปที่จะตัดหัวท้าย ({num_strength_samples} ค่า), คำนวณจากทั้งหมด: {average_signal_db:.2f} dBm")
        # else: num_strength_samples คือ 0, average_signal_db จะยังเป็น None

    if average_signal_db is not None:
        log(f"📊 ค่าเฉลี่ยความแรงสัญญาณสุดท้ายที่จะใช้: {average_signal_db:.2f} dBm")
    else:
        log(f"📊 ไม่สามารถคำนวณค่าเฉลี่ยความแรงสัญญาณได้ (ไม่มีตัวอย่าง)")

    # if signal_strengths_db:
    #     average_signal_db = sum(signal_strengths_db) / len(signal_strengths_db)
    #     log(f"📊 ค่าเฉลี่ยความแรงสัญญาณระหว่างบันทึก: {average_signal_db:.2f} dBm")

    try:
        wf = wave.open(filepath, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(pyaudio_instance.get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        log(f"💾 บันทึกไฟล์เสียง ({duration:.2f} วินาที) : {filepath}")

        # --- หลังจบการบันทึกและคำนวณค่าเฉลี่ย ให้แน่ใจว่า TinySA pause อีกครั้ง ---
        if TINYSA_ENABLED and tinysa_ser:
            pause_tinysa(tinysa_ser)

        return filepath, duration, average_signal_db

    except Exception as e_write:
        log(f"❌ เกิดข้อผิดพลาดขณะบันทึกไฟล์ wave: {e_write}")
        return None

def send_tinysa_command(ser, command_str, read_response=False, delay_after_command=0.1):
    """Helper function to send command and optionally read response."""
    if not ser or not ser.is_open:
        log(f"⚠️ [TinySA] Serial port not open for command: {command_str.strip()}")
        return None if read_response else False
    try:
        log(f"➡️ [TinySA] Sending: {command_str.strip()}")
        ser.write(command_str.encode())
        time.sleep(delay_after_command) # ให้เวลากับอุปกรณ์
        if read_response:
            # TinySA มักจะตอบกลับทันที หรือมี prompt (เช่น 'ch> ')
            # การ read_until() อาจจะต้องปรับตาม prompt หรือ terminator ที่ TinySA ใช้
            # ถ้าไม่มี prompt ที่ชัดเจน อาจจะอ่านตามจำนวน bytes ที่คาดหวัง หรือใช้ timeout
            response_lines = []
            # อ่านจนกว่าจะไม่มีข้อมูลใหม่ใน buffer หรือเจอ prompt (ถ้ามี)
            # นี่เป็นวิธีอ่านแบบง่าย อาจจะต้องปรับปรุง
            # while ser.in_waiting > 0:
            #     line = ser.readline().strip().decode('ascii', errors='ignore')
            #     if line:
            #         response_lines.append(line)
            #     else: # อาจจะเจอ empty line ถ้าหมดข้อมูลแล้ว
            #         break
            # response_str = "\n".join(response_lines)

            # วิธีที่อาจจะดีกว่าคือรอ prompt หรือ timeout สั้นๆ
            # TinySA บางรุ่นอาจจะมี prompt เช่น 'ch> ' หรือ '>'
            # ในที่นี้จะลองอ่านแบบรอ timeout เล็กน้อย
            response_bytes = b''
            start_time = time.time()
            while (time.time() - start_time) < 0.5: # รอสูงสุด 0.5 วินาทีสำหรับ response
                if ser.in_waiting > 0:
                    response_bytes += ser.read(ser.in_waiting)
                else:
                    if response_bytes: # ถ้ามีข้อมูลแล้ว และไม่มีอะไรเพิ่ม ก็ break
                        break
                    time.sleep(0.05) # หน่วงเล็กน้อยถ้ายังไม่มีข้อมูล

            response_str = response_bytes.strip().decode('ascii', errors='ignore')
            log(f"⬅️ [TinySA] Received: {response_str if response_str else '<No immediate response>'}")
            return response_str
        return True
    except serial.SerialException as e:
        log(f"❌ [TinySA] Serial error sending command '{command_str.strip()}': {e}")
        return None if read_response else False
    except Exception as e:
        log(f"❌ [TinySA] Error sending command '{command_str.strip()}': {e}")
        return None if read_response else False

def setup_tinysa_for_measurement(ser, center_freq_hz, sweep_points, repeat_interval_ms):
    """ตั้งค่า TinySA สำหรับการวัด ณ ความถี่ที่กำหนด"""
    global tinysa_is_paused
    if not ser or not ser.is_open:
        return False
    try:
        if tinysa_is_paused:  # ถ้า pause อยู่ ให้ resume ก่อนตั้งค่า
            send_tinysa_command(ser, "resume\r\n")
            tinysa_is_paused = False
            log(f"📡 [TinySA] Resumed for setup.")

        # กำหนดช่วงความถี่ (ให้แคบที่สุดรอบ center_freq_hz)
        # sweep freq_mhz_start freq_mhz_end sweep_point
        # TinySA รับความถี่เป็น Hz สำหรับคำสั่ง sweep
        # เราจะตั้ง span เล็กๆ รอบ center frequency
        # ตัวอย่าง span 20kHz (10kHz แต่ละข้าง) ซึ่งเป็น 20000Hz
        # หรือจะใช้ 0 span ถ้า TinySA รองรับการวัดที่จุดเดียวโดยตรง (ต้องดูคู่มือ)
        # สมมติว่าเราต้องการ span แคบๆ พอให้ marker จับได้
        span_hz = 20000  # 20 kHz span (ปรับได้)
        freq_start_hz = center_freq_hz - (span_hz // 2)
        freq_end_hz = center_freq_hz + (span_hz // 2)

        send_tinysa_command(ser, f"sweep {freq_start_hz} {freq_end_hz} {sweep_points}\r\n")

        # กำหนด interval
        send_tinysa_command(ser, f"repeat {repeat_interval_ms}\r\n")

        # กำหนด Marker 1 ไปยังความถี่กลาง
        send_tinysa_command(ser, f"marker 1 {center_freq_hz}\r\n")

        log(f"✅ [TinySA] Setup complete for {center_freq_hz / 1_000_000:.3f} MHz.")
        return True
    except Exception as e:
        log(f"❌ [TinySA] Exception during setup_tinysa: {e}")
        return False


def get_signal_strength_tinysa(ser):
    """อ่านค่าความแรงสัญญาณจาก Marker 1 ของ TinySA"""
    global tinysa_is_paused
    if not ser or not ser.is_open:
        return None
    try:
        if tinysa_is_paused:  # ถ้า pause อยู่ ให้ resume ก่อนอ่านค่า
            send_tinysa_command(ser, b"resume\r\n")
            tinysa_is_paused = False
            log(f"📡 [TinySA] Resumed for reading signal strength.")
            time.sleep(TINYSA_REPEAT_INTERVAL / 1000 * 2)  # รอให้มีการ sweep อย่างน้อยหนึ่งรอบหลังจาก resume

        raw_response = send_tinysa_command(ser, "marker\r\n", read_response=True,
                                           delay_after_command=0.1)

        if raw_response:
            # ตัวอย่าง response: "1 20 145200000 -2.95e+01"
            # หรืออาจจะมีหลายบรรทัด หรือมี prompt "ch> "
            # เราต้องการหาบรรทัดที่ขึ้นต้นด้วย "1 " (Marker 1)
            lines = raw_response.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith("1 "):  # Marker 1 data
                    parts = line.split()  # แยกด้วย space
                    if len(parts) == 4:
                        try:
                            # parts[0] = marker number (1)
                            # parts[1] = sweep point (20)
                            # parts[2] = frequency (145200000)
                            # parts[3] = signal value (-2.95e+01)
                            signal_str = parts[3]
                            dbm_value = float(signal_str)  # ค่าที่ได้คือ -29.5
                            log(f"📡 [TinySA] Marker 1 Raw: '{line}', Parsed dBm: {dbm_value:.2f}")
                            return dbm_value
                        except ValueError:
                            log(f"⚠️ [TinySA] Could not parse signal value from: '{line}'")
                            continue  # ลองบรรทัดถัดไปถ้ามี
                    else:
                        log(f"⚠️ [TinySA] Unexpected marker line format: '{line}'")
            log(f"⚠️ [TinySA] Could not find valid Marker 1 data in response: '{raw_response}'")
        else:
            log("⚠️ [TinySA] No response from 'marker' command.")
        return None
    except Exception as e:
        log(f"❌ [TinySA] Error getting signal strength from TinySA: {e}")
        return None

def pause_tinysa(ser):
    global tinysa_is_paused
    if ser and ser.is_open and not tinysa_is_paused:
        send_tinysa_command(ser, "pause\r\n")
        tinysa_is_paused = True
        log("⏸️ [TinySA] Paused.")

def resume_tinysa(ser):
    global tinysa_is_paused
    if ser and ser.is_open and tinysa_is_paused:
        send_tinysa_command(ser, "resume\r\n")
        tinysa_is_paused = False
        log("▶️ [TinySA] Resumed.")

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
def transcribe_audio_assemblyai_and_get_text(filepath_wav):
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json"
    }
    log(f"🧠 [STT] ส่งเสียงไป AssemblyAI: {filepath_wav}")

    # 1) อัปโหลดไฟล์ ให้ได้ upload_url
    with open(filepath_wav, "rb") as f:
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
    log(f"🔍 [STT] AssemblyAI transcript request returned { transcript_resp.status_code }: {transcript_resp.text}")

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
    log(f"🔍 [STT] AssemblyAI job created: {job_id}")

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
        log(f"🔄 [STT] AssemblyAI job {job_id} status: {status}")

    # 4) อ่านผลลัพธ์
    if status == "completed":
        text = j.get("text", "").strip()
        if text:
            log(f"✅ [STT] ถอดข้อความ (AssemblyAI): {text[:50]}…")
        else:
            log("❌ [STT] AssemblyAI: ไม่สามารถถอดข้อความจากเสียงได้: {filepath_wav}")
            text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
    else:
        log(f"❌ [STT] AssemblyAI job error: {j.get('error', 'unknown')}")
        text = "[ยกเลิกหรือเกิดข้อผิดพลาด]"

    # 5) บันทึกและอัปโหลด
    # with open(filepath_wav.replace(".wav", ".txt"), "w", encoding="utf-8") as ftxt:
    #     ftxt.write(text)
    # upload_audio_and_text(filepath_wav, mp3_filepath, text, duration, engine_used)

    # (ทางเลือก) บันทึก text file ชั่วคราว ถ้าต้องการ debug
    # temp_txt_path = filepath_wav.replace(".wav", "_temp_transcript.txt")
    # with open(temp_txt_path, "w", encoding="utf-8") as f:
    #     f.write(text)

    return text

# ระบบถอดเสียงด้วย Azure
def transcribe_audio_azure_and_get_text(filepath_wav):
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)
    speech_config.speech_recognition_language = LANGUAGE
    audio_config = speechsdk.audio.AudioConfig(filename=filepath_wav)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    log(f"🧠 [STT] ส่งเสียงไป Azure: {filepath_wav}")
    result = recognizer.recognize_once()
    # text = "[Transcription Error]" # Default text

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        text = result.text.strip()
        log(f"✅ [STT] ถอดข้อความ (Azure): {text}")
    elif result.reason == speechsdk.ResultReason.NoMatch:
        text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
        log("❌ [STT] Azure: ไม่สามารถถอดข้อความจากเสียงได้: {filepath_wav}")
    else:
        text = f"[ยกเลิกหรือเกิดข้อผิดพลาดในการถอดความ: {result.reason}]"
        log(f"🚫 [STT] ยกเลิก (Azure): {result.reason} สำหรับ {filepath_wav}")

    # with open(filepath_wav.replace(".wav", ".txt"), "w", encoding="utf-8") as f:
    #     f.write(text)

    # (ทางเลือก) บันทึก text file ชั่วคราว ถ้าต้องการ debug
    # temp_txt_path = filepath_wav.replace(".wav", "_temp_transcript.txt")
    # with open(temp_txt_path, "w", encoding="utf-8") as f:
    #     f.write(text)

    # upload_audio_and_text(filepath_wav, mp3_filepath, text, duration, engine_used)
    return text

# ระบบถอดเสียงด้วย Google Cloud
def transcribe_audio_google_and_get_text(filepath_wav):
    try:  # เพิ่ม try-except ครอบคลุมการทำงานทั้งหมดของฟังก์ชัน
        client = speech.SpeechClient()
        log(f"🧠 [STT] ส่งเสียงไป Google: {filepath_wav}")

        if not os.path.exists(filepath_wav):
            log(f"❌ [STT Google] ไม่พบไฟล์: {filepath_wav}")
            return "[Error: Audio file not found]"

        with open(filepath_wav, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code=LANGUAGE_CODE, # LANGUAGE_CODE จาก global config
            audio_channel_count=1,
            enable_automatic_punctuation=True
        )

        response = client.recognize(config=config, audio=audio)
        # text = "[Transcription Error]"  # Default text

        if not response.results:
            text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
            log("❌ [STT] Google: ไม่สามารถถอดข้อความจากเสียงได้ สำหรับไฟล์: {filepath_wav}")
        else:
            # ตรวจสอบให้แน่ใจว่า alternatives ไม่ได้ว่างเปล่า
            # text = response.results[0].alternatives[0].transcript
            # log(f"✅ [STT] ถอดข้อความ (Google): {text}")
            if response.results[0].alternatives:
                text = response.results[0].alternatives[0].transcript.strip()
                log(f"✅ [STT] ถอดข้อความ (Google): {text}")
            else:
                text = "[Google STT returned no alternatives]"
                log(f"⚠️ [STT] Google: ไม่พบ alternatives ในผลลัพธ์สำหรับไฟล์: {filepath_wav}")

        # with open(filepath_wav.replace(".wav", ".txt"), "w", encoding="utf-8") as f:
        #     f.write(text)
        #
        # upload_audio_and_text(filepath_wav, mp3_filepath, text, duration, engine_used)

        # (ทางเลือก) บันทึก text file ชั่วคราว ถ้าต้องการ debug
        # temp_txt_path = filepath_wav.replace(".wav", "_temp_transcript.txt")
        # with open(temp_txt_path, "w", encoding="utf-8") as f:
        #     f.write(text)
    except Exception as e:
        log(f"❌ [STT Google] เกิด Exception ขณะถอดความไฟล์ {filepath_wav}: {e}")
        text = f"[Google STT Exception: {e}]"
    return text

# ระบบถอดเสียงด้วย IBM Cloud
def transcribe_audio_ibm_and_get_text(filepath_wav):
    log(f"🧠 ส่งเสียงไป IBM Watson: {filepath_wav}")
    authenticator = IAMAuthenticator(IBM_API_KEY)
    speech_to_text = SpeechToTextV1(authenticator=authenticator)
    speech_to_text.set_service_url(IBM_URL)

    with open(filepath_wav, 'rb') as audio_file:
        response = speech_to_text.recognize(
            audio=audio_file,
            content_type='audio/wav',
            model=IBM_LANGUAGE_CODE,
            timestamps=False,
            word_confidence=False
        ).get_result()

    results = response.get("results", [])
    # text = "[Transcription Error]"  # Default text

    if results and "alternatives" in results[0]:
        text = results[0]["alternatives"][0]["transcript"]
        log(f"✅ [STT] ถอดข้อความ (IBM Watson): {text}")
    else:
        text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
        log("❌ [STT] IBM Watson: ไม่สามารถถอดข้อความจากเสียงได้: {filepath_wav}")

    # with open(filepath_wav.replace(".wav", ".txt"), "w", encoding="utf-8") as f:
    #     f.write(text)
    #
    # upload_audio_and_text(filepath_wav, mp3_filepath, text, duration, engine_used)

    # (ทางเลือก) บันทึก text file ชั่วคราว ถ้าต้องการ debug
    # temp_txt_path = filepath_wav.replace(".wav", "_temp_transcript.txt")
    # with open(temp_txt_path, "w", encoding="utf-8") as f:
    #     f.write(text)

    return text

# ระบบถอดเสียงด้วย Speechmatics
def transcribe_audio_speechmatics_and_get_text(filepath_wav):
    log(f"🧠 [STT] ส่งเสียงไป Speechmatics: {filepath_wav}")
    headers = {
        'Authorization': f'Bearer {SPEECHMATICS_API_KEY}',
        'Accept': 'application/json'
    }

    # เตรียม JSON ตามสเปค v2
    config_payload = {
        "type": "transcription",
        "transcription_config": {
            "language": f"{SPEECHMATICS_LANGUAGE_CODE}",
            "operating_point": f"{SPEECHMATICS_OPERATING_POINT}"
            # ถ้าต้องการติวเพิ่ม เช่น operating_point, diarization ฯลฯ ให้ใส่ตรงนี้
        }
    }

    files = {
        'data_file': open(filepath_wav, 'rb')
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
        log(f"❌ [STT] Speechmatics error {resp.status_code}: {err}")
        return

    job = resp.json()
    # log(f"🔍 [STT] Speechmatics response on job creation: {job}")

    # ดึง job ID
    job_id = job.get("id") or job.get("job",{}).get("id")
    if not job_id:
        log("❌ [STT] ไม่พบ job ID ใน response")
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
            log(f"❌ [STT] ไม่พบ status ใน response ของ Speechmatics: {resp_status}")
            break

        # log(f"🔄 Speechmatics job {job_id} status: {status}")
        if status in ('failed', 'expired'):
            log(f"❌ [STT] Speechmatics job {job_id} failed")
            text = "[ไม่สามารถถอดข้อความจากเสียงได้]"
            break
    else:
        # ดาวน์โหลด transcript
        txt_resp = requests.get(f"{SPEECHMATICS_URL}/jobs/{job_id}/transcript?format=txt", headers=headers)
        txt_resp.raise_for_status()
        text = txt_resp.content.decode('utf-8').strip()

        # หลัง decode แล้วได้ตัวแปร text
        if text.strip():
            log(f"✅ [STT] ถอดข้อความ (Speechmatics): {text}")
        else:
            log("❌ [STT] Speechmatics: ไม่สามารถถอดข้อความจากเสียงได้: {filepath_wav}")
            text = "[ไม่สามารถถอดข้อความจากเสียงได้]"

    # บันทึกและอัปโหลด
    # with open(filepath_wav.replace(".wav", ".txt"), "w", encoding="utf-8") as ftxt:
    #     ftxt.write(text)
    # upload_audio_and_text(filepath_wav, mp3_filepath, text, duration, engine_used)

    # (ทางเลือก) บันทึก text file ชั่วคราว ถ้าต้องการ debug
    # temp_txt_path = filepath_wav.replace(".wav", "_temp_transcript.txt")
    # with open(temp_txt_path, "w", encoding="utf-8") as f:
    #     f.write(text)
    return text


def speak_text_azure(text_to_speak, voice_name=None):
    """
    ใช้ Azure TTS เพื่อแปลงข้อความเป็นเสียงและเล่นออกทางลำโพง
    """
    if not SPEECH_KEY or not SERVICE_REGION:
        log("⚠️ ไม่ได้ตั้งค่า Azure Speech Key หรือ Region สำหรับ TTS")
        return

    try:
        speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)

        # ตั้งค่าภาษาสำหรับเสียงพูด (อาจจะแตกต่างจากภาษา STT ได้ แต่ควรเป็นภาษาเดียวกับ response_text)
        speech_config.speech_synthesis_language = "th-TH"  # หรือดึงจาก config ถ้าต้องการความยืดหยุ่น

        if voice_name:
            speech_config.speech_synthesis_voice_name = voice_name
        else:
            # ถ้าไม่ได้ระบุ voice_name สามารถตั้งค่า default voice ที่นี่ได้
            speech_config.speech_synthesis_voice_name = "th-TH-PremwadeeNeural"  # ตัวอย่างเสียงผู้หญิง
            # speech_config.speech_synthesis_voice_name = "th-TH-NiwatNeural" # ตัวอย่างเสียงผู้ชาย

        # เล่นเสียงออกทาง default speaker
        # หากต้องการบันทึกเป็นไฟล์ ให้ใช้ speechsdk.AudioConfig(filename="path/to/output.wav")
        # แล้วใช้ speech_synthesizer.speak_text_async(text_to_speak).get()
        # ในที่นี้เราจะเล่นโดยตรง
        audio_config_playback = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config,
                                                         audio_config=audio_config_playback)

        log(f"📢 [TTS Azure] กำลังพูด: '{text_to_speak}' (Voice: {speech_config.speech_synthesis_voice_name})")
        result = speech_synthesizer.speak_text_async(text_to_speak).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            log(f"✅ [TTS Azure] พูดข้อความสำเร็จ")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            log(f"❌ [TTS Azure] การสังเคราะห์เสียงถูกยกเลิก: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                log(f"   รายละเอียดข้อผิดพลาด: {cancellation_details.error_details}")
    except Exception as e:
        log(f"❌ [TTS Azure] เกิดข้อผิดพลาดระหว่างการสังเคราะห์เสียง: {e}")


# (ทางเลือก) ฟังก์ชันสำหรับบันทึก TTS เป็นไฟล์ .wav
def synthesize_text_to_wav_azure(text_to_speak, output_filename, voice_name=None):
    if not SPEECH_KEY or not SERVICE_REGION:
        log("⚠️ ไม่ได้ตั้งค่า Azure Speech Key หรือ Region สำหรับ TTS (to file)")
        return False
    try:
        speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)
        speech_config.speech_synthesis_language = "th-TH"
        if voice_name:
            speech_config.speech_synthesis_voice_name = voice_name
        else:
            speech_config.speech_synthesis_voice_name = "th-TH-PremwadeeNeural"

        audio_config_file = speechsdk.audio.AudioOutputConfig(filename=output_filename)
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config_file)

        log(f"💾 [TTS Azure] กำลังสังเคราะห์เสียง '{text_to_speak}' เป็นไฟล์: {output_filename}")
        result = speech_synthesizer.speak_text_async(text_to_speak).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            log(f"✅ [TTS Azure] สังเคราะห์เสียงเป็นไฟล์ {output_filename} สำเร็จ")
            return True
        # ... (จัดการ Canceled/Error เหมือนเดิม) ...
    except Exception as e:
        log(f"❌ [TTS Azure] เกิดข้อผิดพลาดระหว่างการสังเคราะห์เสียงเป็นไฟล์: {e}")
    return False

# --- ฟังก์ชันสำหรับแปลง MP3 (อาจจะแยกออกมาเพื่อให้เรียกใน thread) ---
def convert_to_mp3_task(wav_path_to_convert, original_wav_basename_for_mp3_name):
    mp3_filepath_local = None
    try:
        if os.path.exists(wav_path_to_convert):
            sound = AudioSegment.from_wav(wav_path_to_convert)
            mp3_filename_local = os.path.splitext(original_wav_basename_for_mp3_name)[0] + ".mp3"
            mp3_filepath_temp_local = os.path.join(SAVE_FOLDER, mp3_filename_local)

            log(f"🔄 [MP3 Conv] กำลังแปลงไฟล์ {wav_path_to_convert} เป็น MP3: {mp3_filepath_temp_local}")
            sound.export(mp3_filepath_temp_local, format="mp3", bitrate=MP3_BITRATE)  # ใช้ MP3_BITRATE จาก config
            log(f"✅ [MP3 Conv] แปลงเป็น MP3 สำเร็จ (Bitrate: {MP3_BITRATE}): {mp3_filepath_temp_local}")
            mp3_filepath_local = mp3_filepath_temp_local
        else:
            log(f"⚠️ [MP3 Conv] ไม่พบไฟล์ {wav_path_to_convert} สำหรับการแปลงเป็น MP3")
    except Exception as e_mp3:
        log(f"❌ [MP3 Conv] เกิดข้อผิดพลาดระหว่างการแปลงเป็น MP3 สำหรับ {wav_path_to_convert}: {e_mp3}")
    return mp3_filepath_local

# ระบบอัพโหลดไฟล์และข้อมูลเข้าไปเก็บที่เว็บและฐานข้อมูล
def upload_audio_and_text(original_wav_path, mp3_filepath, transcript, duration, engine_used, worker_id_for_log=None):
    log_prefix = f"[Worker {worker_id_for_log}] " if worker_id_for_log is not None else ""

    if not UPLOAD_ENABLED:
        log(f"{log_prefix}❌☁️ ข้ามกระบวนการ Upload เนื่องด้วยการ Upload ถูกตั้งค่าปิดการใช้งาน")
        return

    source_name = get_source_name(engine_used)

    file_to_upload_path = None
    filename_for_db = None

    if mp3_filepath and os.path.exists(mp3_filepath):
        file_to_upload_path = mp3_filepath
        filename_for_db = os.path.basename(mp3_filepath) # ใช้ชื่อไฟล์ .mp3 สำหรับ DB
        log(f"{log_prefix}📤 อัปโหลดไฟล์ MP3: {file_to_upload_path}")
    elif original_wav_path and os.path.exists(original_wav_path): # ถ้าไม่มี mp3 หรือแปลงไม่สำเร็จ ก็ใช้ wav เดิม
        file_to_upload_path = original_wav_path
        filename_for_db = os.path.basename(original_wav_path) # ใช้ชื่อไฟล์ .wav สำหรับ DB
        log(f"{log_prefix}📤 อัปโหลดไฟล์ WAV (เนื่องจากไม่มี MP3): {file_to_upload_path}")
    else:
        log(f"{log_prefix}⚠️ ไม่พบไฟล์เสียง (ทั้ง WAV และ MP3) สำหรับอัปโหลด")
        # อาจจะยังต้องการอัปโหลดเฉพาะ transcript ถ้ามี
        # filename_for_db = f"NO_AUDIO_FILE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt" # ชื่อสมมติ
        # return # หรือจะให้อัปโหลด text อย่างเดียวก็ได้

    # files = {'audio': open(audio_path, 'rb')}
    data = {
        'transcript': transcript,
        'filename': filename_for_db,
        'source': source_name,
        'frequency': FREQUENCY,
        'station': STATION,
        'duration': str(round(duration, 2))
    }

    files_payload = None
    if file_to_upload_path:
        try:
            files_payload = {'audio': (os.path.basename(file_to_upload_path), open(file_to_upload_path, 'rb'))}
        except IOError as e:
            log(f"{log_prefix}❌ ไม่สามารถเปิดไฟล์ {file_to_upload_path} สำหรับอัปโหลด: {e}")
            # อาจจะยังส่งข้อมูล text ไป
            file_to_upload_path = None # ไม่ต้องพยายามอัปโหลดไฟล์

    try:
        log(f"{log_prefix}📤 กำลังส่งข้อมูลไปเว็บ: filename DB={data['filename']}, transcript={transcript[:30]}...")
        if files_payload:
            res = requests.post(UPLOAD_URL, files=files_payload, data=data, timeout=60) # เพิ่ม timeout
        else: # อัปโหลดเฉพาะ data (ถ้าไม่มีไฟล์เสียง)
             res = requests.post(UPLOAD_URL, data=data, timeout=30)

        if res.status_code == 200:
            log(f"{log_prefix}☁️ อัปโหลดข้อมูลเรียบร้อย")
        else:
            log(f"{log_prefix}❌ Upload error: {res.status_code} - {res.text}")
    except requests.exceptions.RequestException as e:
        log(f"{log_prefix}❌ Upload exception (requests): {e}")
    except Exception as e:
        log(f"{log_prefix}❌ Upload exception (general): {e}")
    finally:
        # ปิดไฟล์ถ้ามีการเปิดไว้ใน files_payload
        if files_payload and 'audio' in files_payload and hasattr(files_payload['audio'][1], 'close'):
            files_payload['audio'][1].close()


# --- ปรับปรุง schedule_task ---
def schedule_task(fp_wav, dur, avg_signal_db):
    processed_filepath_for_transcription = fp_wav
    original_wav_to_delete_later = fp_wav
    processed_wav_to_delete_later = None

    if AUDIO_PRE_PROCESSING:
        log(f"⚙️ [PreProc] เริ่ม Pre-processing ไฟล์: {fp_wav}")
        processed_filepath_for_transcription = preprocess_audio(fp_wav)  # นี่คือ _processed.wav หรือ wav เดิม
        if processed_filepath_for_transcription != fp_wav:  # ถ้ามีการสร้างไฟล์ _processed จริงๆ
            processed_wav_to_delete_later = processed_filepath_for_transcription
        log(f"👍 [PreProc] Pre-processing เสร็จสิ้น: {processed_filepath_for_transcription}")

    # --- เริ่มงานถอดความและแปลง MP3 ขนานกัน ---
    transcript_result = None
    mp3_result_path = None
    engine_actually_used_in_stt = None

    # สร้าง thread สำหรับแต่ละงาน
    stt_thread = None
    mp3_thread = None

    # ฟังก์ชันเป้าหมายสำหรับ thread ถอดความ
    def stt_target():
        nonlocal transcript_result, engine_actually_used_in_stt  # เพื่อให้สามารถ assign ค่ากลับมาได้ , อ้างอิงตัวแปรจาก scope ของ schedule_task
        try:
            current_mode = TRANSCRIBE_ENGINE_MODE  # อ่านค่า global
            engine_to_run = current_mode

            if current_mode == "random":
                if RANDOM_ENGINES:
                    engine_to_run = random.choice(RANDOM_ENGINES)
                else:
                    log("⚠️ [STT Target] ไม่มีระบบใน random_engines, ใช้ Azure เป็น fallback")
                    engine_to_run = "azure"
            elif current_mode == "alternate":
                global last_engine_index
                if ALTERNATE_ENGINES:
                    last_engine_index = (last_engine_index + 1) % len(ALTERNATE_ENGINES)
                    engine_to_run = ALTERNATE_ENGINES[last_engine_index]
                else:
                    log("⚠️ [STT Target] ไม่มีระบบใน alternate_engines, ใช้ Azure เป็น fallback")
                    engine_to_run = "azure"

            engine_actually_used_in_stt = engine_to_run  # <--- เก็บ engine ที่ใช้จริง
            log(f"🚦 [TaskMgr] เริ่ม Thread ถอดความ ({engine_actually_used_in_stt}) สำหรับ: {processed_filepath_for_transcription}")

            if engine_actually_used_in_stt == "azure":
                transcript_result = transcribe_audio_azure_and_get_text(processed_filepath_for_transcription)
            elif engine_actually_used_in_stt == "google":
                transcript_result = transcribe_audio_google_and_get_text(processed_filepath_for_transcription)
            # ... (เพิ่ม elif สำหรับ STT engines อื่นๆ) ...
            elif engine_actually_used_in_stt == "speechmatics":
                transcript_result = transcribe_audio_speechmatics_and_get_text(processed_filepath_for_transcription)
            elif engine_actually_used_in_stt == "ibm":
                transcript_result = transcribe_audio_ibm_and_get_text(processed_filepath_for_transcription)
            elif engine_actually_used_in_stt == "assemblyai":
                transcript_result = transcribe_audio_assemblyai_and_get_text(processed_filepath_for_transcription)
            else:
                log(f"⚠️ [TaskMgr] ไม่รู้จัก STT engine: {engine_actually_used_in_stt}")
                transcript_result = f"[Unknown STT Engine: {engine_actually_used_in_stt}]"
        except Exception as e_stt_thread:
            log(f"❌ [TaskMgr] Exception ใน STT Thread: {e_stt_thread}")
            transcript_result = f"[Exception during STT: {e_stt_thread}]"
            if engine_actually_used_in_stt is None:  # ถ้า error ก่อนจะกำหนด engine ที่ใช้จริง
                engine_actually_used_in_stt = "error_engine_selection"

    # ฟังก์ชันเป้าหมายสำหรับ thread แปลง MP3
    def mp3_target():
        nonlocal mp3_result_path
        if MP3_CONVERSION_ENABLED:
            try:
                log(f"🚦 [TaskMgr] เริ่ม Thread แปลง MP3 สำหรับ: {processed_filepath_for_transcription}")
                # ส่งชื่อไฟล์ .wav ดั้งเดิม (fp_wav) ไปเพื่อใช้เป็น base name ของไฟล์ mp3
                mp3_result_path = convert_to_mp3_task(processed_filepath_for_transcription, os.path.basename(fp_wav))
            except Exception as e_mp3_thread:
                log(f"❌ [TaskMgr] Exception ใน MP3 Thread: {e_mp3_thread}")
        else:
            log(f"ℹ️ [TaskMgr] การแปลงเป็น MP3 ถูกปิดใช้งาน")
            mp3_result_path = None # ไม่มีการแปลง

    stt_thread = threading.Thread(target=stt_target)
    if MP3_CONVERSION_ENABLED:  # สร้างและเริ่ม MP3 thread ต่อเมื่อเปิดใช้งาน
        mp3_thread = threading.Thread(target=mp3_target)

    stt_thread.start()
    if mp3_thread:
        mp3_thread.start()

    log(f"⏳ [TaskMgr] รอ Thread ถอดความ{ ' และแปลง MP3' if MP3_CONVERSION_ENABLED else ''} ให้เสร็จสิ้นสำหรับ {os.path.basename(fp_wav)}...")
    stt_thread.join()  # รอ STT thread จบ
    if mp3_thread:
        mp3_thread.join()  # รอ MP3 thread จบ
    log(f"🏁 [TaskMgr] Thread ทั้งสองทำงานเสร็จสิ้นสำหรับ {os.path.basename(fp_wav)}. Engine ที่ใช้: {engine_actually_used_in_stt}")

    # --- เมื่อทั้งสองงานเสร็จสิ้น ---
    # (transcript_result จะมีค่า text หรือ error message)
    # (mp3_result_path จะมี path ของ mp3 หรือ None)

    # ส่งข้อมูลทั้งหมดไปให้ worker (หรือจะเรียก upload_audio_and_text โดยตรงจากที่นี่ก็ได้)
    # เราต้องส่ง "engine_used" ไปด้วย แต่ตอนนี้ engine ถูกเลือกภายใน stt_target
    # อาจจะต้องปรับให้ stt_target คืนค่า (transcript, engine_actually_used)

    # เพื่อความง่ายในตัวอย่างนี้ จะสมมติว่าเรารู้ engine ที่ใช้ (TRANSCRIBE_ENGINE_MODE ถ้าไม่ random/alternate)
    # หรือเราสามารถดึง engine ที่ใช้จริงจาก stt_target ได้ถ้าปรับแก้
    # final_engine_used_for_upload = engine_used_in_stt  # หรือ engine ที่ใช้จริงถ้ามีการ random/alternate
    # (จำเป็นต้องมี logic ที่ซับซ้อนกว่านี้ในการส่ง engine ที่ใช้จริง ถ้ามีการ random/alternate)

    # เตรียมข้อมูลสำหรับ audio_queue หรือ upload_audio_and_text
    # processed_filepath_for_transcription คือไฟล์ .wav หรือ _processed.wav ที่ใช้ถอดความ
    # mp3_result_path คือไฟล์ .mp3 (ถ้ามี)
    # dur คือ duration
    # transcript_result คือข้อความที่ถอดได้
    # original_wav_to_delete_later, processed_wav_to_delete_later คือไฟล์ที่จะลบ

    audio_queue.put((
        processed_filepath_for_transcription,
        mp3_result_path,
        dur,
        # transcript_result if transcript_result is not None else "[Transcription not available]",  # ให้มีค่าเสมอ
        # transcript_result if transcript_result is not None else "[No transcript]",
        transcript_result if transcript_result is not None else "[No transcript available]",
        # engine_used_in_stt if engine_used_in_stt is not None else TRANSCRIBE_ENGINE_MODE,  # <--- ส่ง engine ที่ใช้จริง
        engine_actually_used_in_stt if engine_actually_used_in_stt is not None else "unknown_error_engine",  # <--- ส่ง engine ที่ใช้จริง
        # final_engine_used_for_upload,
        original_wav_to_delete_later,
        processed_wav_to_delete_later,
        avg_signal_db
    ))

def worker(worker_id):
    while True:
        task = audio_queue.get()
        if task is None: # วิธีการบอกให้ worker หยุด (ถ้าต้องการ)
            break

        # ขยาย tuple ให้รับค่าใหม่
        file_for_transcription_wav, mp3_path, duration, transcript_text, engine_actually_used, \
        original_wav_to_delete, processed_wav_to_delete, avg_signal_db_from_queue = task

        # log(f"[Worker {worker_id}]  : {os.path.basename(file_for_transcription_wav if file_for_transcription_wav else 'NoWAV')}, MP3: {os.path.basename(mp3_path if mp3_path else 'NoMP3')}, Engine: {engine_actually_used}")
        # log(f"[Worker {worker_id}] ... Signal: {avg_signal_db_from_queue:.2f} dB" if avg_signal_db_from_queue is not None else f"[Worker {worker_id}] ... Signal: N/A")
        log_prefix = f"[Worker {worker_id}]"
        log(f"{log_prefix} Processing: {os.path.basename(file_for_transcription_wav if file_for_transcription_wav else 'NoWAV')}, MP3: {os.path.basename(mp3_path if mp3_path else 'NoMP3')}, Engine: {engine_actually_used}, Signal: {avg_signal_db_from_queue:.2f} dB" if avg_signal_db_from_queue is not None else f"[Worker {worker_id}] Processing: {os.path.basename(file_for_transcription_wav if file_for_transcription_wav else 'NoWAV')}, MP3: {os.path.basename(mp3_path if mp3_path else 'NoMP3')}, Engine: {engine_actually_used}, Signal: N/A")
        log(f"{log_prefix} 📝 ข้อความที่ถอดได้: {transcript_text}")  # แสดงข้อความที่ถอดได้

        try:
            # --- ส่วนตรวจสอบ Keyword และเรียก TTS ---
            if AZURE_TTS_RESPONSES_ENABLED and transcript_text and not transcript_text.startswith("["):  # ตรวจสอบว่าไม่ใช่ error message
                for tts_config_item in TTS_RESPONSES_CONFIG:
                    trigger_keywords = tts_config_item.get("trigger_keywords", [])
                    except_keywords_list = tts_config_item.get("except_keywords", [])  # ดึงคำที่ยกเว้น

                    # --- กำหนด Keyword เฉพาะสำหรับการรายงานระดับสัญญาณ ---
                    signal_report_keywords = ["ทดสอบระดับสัญญา", "ทดสอบสัญญา"]
                    # --- สิ้นสุดการกำหนด Keyword เฉพาะ ---

                    found_trigger = False
                    is_signal_report_trigger = False # Flag ว่า trigger นี้เป็น trigger สำหรับรายงานสัญญาณหรือไม่

                    for keyword in trigger_keywords:
                        if keyword.lower() in transcript_text.lower():
                            found_trigger = True
                            # ตรวจสอบว่าเป็น keyword ที่ต้องการให้รายงานระดับสัญญาณหรือไม่
                            for sr_keyword in signal_report_keywords:
                                if sr_keyword.lower() == keyword.lower():
                                    is_signal_report_trigger = True
                                    break
                            break # เมื่อเจอ trigger keyword แรก ก็ออกจาก loop trigger_keywords ของ rule นี้

                    if found_trigger:
                        # ถ้าเจอ Keyword หลักแล้ว ให้ตรวจสอบคำที่ยกเว้น
                        found_exception = False
                        if except_keywords_list:  # ตรวจสอบว่ามีรายการคำยกเว้นหรือไม่
                            for except_word in except_keywords_list:
                                if except_word.lower() in transcript_text.lower():
                                    found_exception = True
                                    log(f"{log_prefix} ℹ️ พบ Keyword '{keyword}' แต่ก็พบคำยกเว้น '{except_word}' ด้วย จึงไม่ทำการตอบกลับ TTS")
                                    break  # ออกจาก loop ของ except_keywords

                        if not found_exception:  # ถ้าไม่พบคำที่ยกเว้นใดๆ จึงค่อยพิจารณาสร้างข้อความตอบกลับ
                            response_to_speak_base = tts_config_item.get("response_text")
                            response_voice = tts_config_item.get("response_voice")

                            final_response_to_speak = response_to_speak_base

                            # เพิ่มข้อมูลระดับสัญญาณก็ต่อเมื่อ is_signal_report_trigger เป็น True เท่านั้น
                            if is_signal_report_trigger and avg_signal_db_from_queue is not None:
                                if "{signal_db}" in final_response_to_speak:
                                    final_response_to_speak = final_response_to_speak.replace("{signal_db}",
                                                                                              f"{avg_signal_db_from_queue:.1f}")
                                else: # ถ้าไม่มี placeholder ก็ต่อท้าย (สำหรับกรณี "ทดสอบระดับสัญญาณ" เท่านั้น)
                                    final_response_to_speak += f" ระดับสัญญาณเฉลี่ย {avg_signal_db_from_queue:.1f} ดีบีเอ็ม"
                            # --- สิ้นสุดการตรวจสอบ ---

                            if final_response_to_speak:
                                log(f"{log_prefix} 🗣️ พบ Keyword, กำลังเตรียมพูด: '{final_response_to_speak}'")
                                tts_thread = threading.Thread(target=speak_text_azure,
                                                              args=(final_response_to_speak, response_voice),
                                                              daemon=True)
                                tts_thread.start()
                            break  # ออกจาก loop ของ tts_config_item (เมื่อเจอ rule แรกที่ match และไม่ติด exception และได้ดำเนินการแล้ว)
        # --- สิ้นสุดส่วน TTS ---

            # เรียก upload_audio_and_text โดยตรง เพราะการถอดความทำไปแล้ว
            upload_audio_and_text(
                file_for_transcription_wav,  # path ของ wav ที่ใช้ถอดความ (อาจเป็น _processed.wav)
                mp3_path,  # path ของ mp3 (ถ้ามี)
                transcript_text,
                duration,
                engine_actually_used,  # engine ที่ใช้จริง
                worker_id
                # avg_signal_db_from_queue   # <--- ส่งค่าความแรงสัญญาณ
            )

            # === การลบไฟล์ WAV ===
            # จะลบไฟล์ WAV ก็ต่อเมื่อ
            # 1. เปิดใช้งานการแปลง MP3 และการแปลงนั้นสำเร็จ (mp3_path มีค่า)
            should_delete_wavs = MP3_CONVERSION_ENABLED and mp3_path and os.path.exists(mp3_path)

            if should_delete_wavs:
                log(f"{log_prefix} เงื่อนไขการลบ WAVs เป็นจริง (MP3 Enabled: {MP3_CONVERSION_ENABLED}, MP3 Path: {mp3_path})")
                # === ลบไฟล์ WAV ที่ไม่ต้องการแล้ว (หลังจาก upload เสร็จ) ===
                if processed_wav_to_delete and os.path.exists(processed_wav_to_delete):
                    # ลบ _processed.wav ถ้ามันถูกสร้างและไม่ใช่ไฟล์เดียวกับ original_wav_to_delete
                    if processed_wav_to_delete != original_wav_to_delete:
                        try:
                            os.remove(processed_wav_to_delete)
                            log(f"{log_prefix} 🗑️ ลบไฟล์ _processed.wav: {processed_wav_to_delete}")
                        except OSError as e:
                            log(f"{log_prefix} ⚠️ ไม่สามารถลบไฟล์ {processed_wav_to_delete}: {e}")

                if original_wav_to_delete and os.path.exists(original_wav_to_delete):
                    try:
                        os.remove(original_wav_to_delete)
                        log(f"{log_prefix} 🗑️ ลบไฟล์ .wav ต้นฉบับ: {original_wav_to_delete}")
                    except OSError as e:
                        log(f"{log_prefix} ⚠️ ไม่สามารถลบไฟล์ {original_wav_to_delete}: {e}")

            else:
                log_reason = ""
                if not MP3_CONVERSION_ENABLED:
                    log_reason = "การแปลง MP3 ถูกปิดใช้งาน"
                elif not (mp3_path and os.path.exists(mp3_path)):
                    log_reason = "การแปลง MP3 ล้มเหลว หรือไม่พบไฟล์ MP3"
                else:
                    log_reason = "เงื่อนไขอื่น (โปรดตรวจสอบ)"
                log(f"{log_prefix} ℹ️ ข้ามการลบไฟล์ WAVs. เนื่องจาก: {log_reason}")
                # log(f"[Worker {worker_id}] ℹ️ ข้ามการลบไฟล์ WAVs (MP3 Enabled: {MP3_CONVERSION_ENABLED}, MP3 Path: {mp3_path})")

        except Exception as e:
            log(f"{log_prefix} ❌ ERROR ใน worker ขณะจัดการ task สำหรับ {os.path.basename(file_for_transcription_wav if file_for_transcription_wav else 'N/A')}: {e}")
            # อาจจะยังต้องการพยายามลบไฟล์ถ้าเกิด exception หลัง upload
        finally:
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

    log_waiting_message = True # ตัวแปรสำหรับควบคุมการ log ข้อความ "รอช่วงเวลาบันทึก..."

    p_instance = pyaudio.PyAudio() # สร้าง instance ของ PyAudio ครั้งเดียว
    tinysa_serial_connection = None  # ประกาศตัวแปรสำหรับเก็บ connection ของ TinySA

    if TINYSA_ENABLED: # เปลี่ยนเป็นเงื่อนไขนี้ (หรือสร้าง config key ใหม่ เช่น TINYSA_ENABLED)
        try:
            tinysa_serial_connection = serial.Serial(TINYSA_SERIAL_PORT, TINYSA_BAUDRATE, timeout=0.5) # ตั้ง timeout
            log(f"✅ [TinySA] Connected to TinySA on {TINYSA_SERIAL_PORT}")
            # ทำการ setup TinySA ครั้งแรก
            # ไม่ต้อง setup ที่นี่แล้ว จะไป setup ตอนเริ่ม record_until_silent
            # แต่สั่ง pause ไว้ก่อนเลย
            pause_tinysa(tinysa_serial_connection)
        except serial.SerialException as e:
            log(f"❌ [TinySA] Could not open serial port {TINYSA_SERIAL_PORT}: {e}")
            log("ℹ️ [TinySA] Signal strength measurement will be disabled.")
            TINYSA_ENABLED = False # ปิดการใช้งานถ้าต่อไม่ได้
        except Exception as e_init:
            log(f"❌ [TinySA] Unexpected error during TinySA initialization: {e_init}")
            log("ℹ️ [TinySA] Signal strength measurement will be disabled.")
            TINYSA_ENABLED = False

    try:
        while True:

            if RECORDING_SCHEDULE_ENABLED: # ถ้าเปิดใช้งานตารางเวลา
                if is_within_scheduled_time(RECORDING_SCHEDULE):
                    if not log_waiting_message: # ถ้าก่อนหน้านี้อยู่นอกเวลา แล้วเพิ่งเข้าเวลา
                        log("🟢 เข้าสู่ช่วงเวลาที่กำหนด เริ่มการบันทึก...")
                        log_waiting_message = True # รีเซ็ตเพื่อให้ log "รอ..." ได้อีกครั้งเมื่อออกนอกเวลา

                    result = record_until_silent(p_instance, tinysa_serial_connection)
                    if result:
                        fp_wav, dur, avg_signal_db = result
                        # เรียก thread ใหม่ให้ทันที ไม่ต้องรอ
                        threading.Thread(
                            target=schedule_task,
                            args=(fp_wav, dur, avg_signal_db),
                            daemon=True
                        ).start()
                    # เลือกจะใส่ sleep น้อยๆ เพื่อไม่ให้ loop เต็มเร็วเกินไป
                    time.sleep(0.1)
                else:
                    if log_waiting_message: # Log ข้อความนี้แค่ครั้งเดียวเมื่ออยู่นอกเวลา
                        current_time_str = datetime.now().strftime("%H:%M:%S")
                        log(f"⏳ เวลาปัจจุบัน {current_time_str} อยู่นอกช่วงเวลาที่กำหนดไว้ในตาราง ({len(RECORDING_SCHEDULE)} ช่วง) กำลังรอ...")
                        log_waiting_message = False
                    time.sleep(30) # หน่วงเวลานานขึ้นเมื่ออยู่นอกตาราง (เช่น 30 วินาที) เพื่อลดการใช้ CPU
            else: # ถ้าไม่ได้เปิดใช้งานตารางเวลา ก็ทำงานตามปกติ
                if not log_waiting_message: # ถ้าก่อนหน้านี้อยู่นอกเวลา (กรณีปิด schedule ขณะรอ)
                    log("🟢 การทำงานตามตารางเวลาถูกปิด เริ่มการบันทึกตามปกติ...")
                    log_waiting_message = True

                result = record_until_silent(p_instance, tinysa_serial_connection)
                if result:
                    fp, dur, average_signal_strength_for_task = result
                    # เรียก thread ใหม่ให้ทันที ไม่ต้องรอ
                    threading.Thread(
                        target=schedule_task,
                        args=(fp, dur, average_signal_strength_for_task),
                        daemon=True
                    ).start()
                # เลือกจะใส่ sleep น้อยๆ เพื่อไม่ให้ loop เต็มเร็วเกินไป
                time.sleep(0.1)
    except KeyboardInterrupt:
        log("🛑 ผู้ใช้สั่งหยุดโปรแกรม (Ctrl+C)")
    except Exception as e_main:
        log(f"❌ เกิดข้อผิดพลาดร้ายแรงใน loop หลัก: {e_main}")
    finally:
        log("🔌 กำลังปิดระบบ PyAudio...")
        if p_instance: # ตรวจสอบว่า ถูกสร้างแล้ว
            p_instance.terminate() # <--- ปิด PyAudio object ครั้งเดียวเมื่อจบโปรแกรม
        if tinysa_serial_connection and tinysa_serial_connection.is_open:
            # send_tinysa_command(tinysa_serial_connection, "resume\r\n")  # Resume ก่อนปิด port เพื่อไม่ให้ค้าง
            # ไม่จำเป็นต้อง resume ก่อน close โดยทั่วไป, แต่ถ้ามีปัญหากับอุปกรณ์บางรุ่นอาจจะลองได้
            # send_tinysa_command(tinysa_serial_connection, "resume\r\n", expect_prompt=False) # ไม่ต้องคาดหวัง prompt ตอนจะปิดแล้ว
            send_tinysa_command(tinysa_serial_connection, "pause\r\n")
            tinysa_serial_connection.close()
            log("✅ [TinySA] Disconnected from TinySA.")
        log("✅ ระบบปิดเรียบร้อย")
