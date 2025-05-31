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
    stream = None  # <<<< กำหนดค่าเริ่มต้นเป็น None
    frames = []  # <<<< ย้าย frames มาประกาศที่นี่เพื่อให้ finally เห็น
    recording = False
    silence_chunks = 0 # นับจำนวน chunks ที่เงียบติดต่อกันระหว่างการบันทึก

    signal_strengths_db = []  # List สำหรับเก็บค่าความแรงสัญญาณ
    last_tinysa_check_time = time.time()

    try:
        stream = pyaudio_instance.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        log(f"📡 รอฟังเสียง ({FREQUENCY}) ...")

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

            # --- อ่านค่าความแรงสัญญาณจาก TinySA เป็นระยะ ---
            if tinysa_ser and recording and (time.time() - last_tinysa_check_time >= 1.0): # อ่านทุกๆ 1 วินาที (ปรับได้)
                # แปลง FREQUENCY (ถ้าเป็น SCAN หรือ string อื่นๆ) เป็น Hz ก่อน
                current_monitoring_freq_hz_for_tinysa = None
                try:
                    # สมมติว่า FREQUENCY ถ้าไม่ใช่ SCAN จะเป็นตัวเลข MHz
                    if FREQUENCY.upper() != "SCAN":
                        current_monitoring_freq_hz_for_tinysa = int(float(FREQUENCY) * 1_000_000)
                        # อาจจะต้อง setup TinySA ใหม่ถ้าความถี่เปลี่ยน
                        # setup_tinysa_for_measurement(tinysa_ser, current_monitoring_freq_hz_for_tinysa)
                    else:  # ถ้าเป็น SCAN ก็ใช้ค่า default จาก config
                        current_monitoring_freq_hz_for_tinysa = TARGET_FREQUENCY_HZ
                        # ไม่ต้อง setup ซ้ำถ้าความถี่ไม่เปลี่ยน
                except ValueError:
                    current_monitoring_freq_hz_for_tinysa = TARGET_FREQUENCY_HZ

                # ถ้าความถี่ที่ใช้ setup TinySA ครั้งล่าสุดไม่ตรงกับความถี่ปัจจุบัน ให้ setup ใหม่
                # (ส่วนนี้อาจจะต้องมีตัวแปร global หรือ attribute ของ class เก็บความถี่ที่ setup TinySA ล่าสุด)
                # if tinysa_ser.last_configured_freq != current_monitoring_freq_hz_for_tinysa:
                #    setup_tinysa_for_measurement(tinysa_ser, current_monitoring_freq_hz_for_tinysa)
                #    tinysa_ser.last_configured_freq = current_monitoring_freq_hz_for_tinysa

                strength = get_signal_strength_tinysa(tinysa_ser)
                if strength is not None:
                    signal_strengths_db.append(strength)
                last_tinysa_check_time = time.time()
            # --- สิ้นสุดการอ่านค่าความแรงสัญญาณ ---

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
    if signal_strengths_db:
        average_signal_db = sum(signal_strengths_db) / len(signal_strengths_db)
        log(f"📊 ค่าเฉลี่ยความแรงสัญญาณระหว่างบันทึก: {average_signal_db:.2f} dB")

    try:
        wf = wave.open(filepath, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(pyaudio_instance.get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        log(f"💾 บันทึกไฟล์เสียง ({duration:.2f} วินาที) : {filepath}")
        return filepath, duration, average_signal_db
    except Exception as e_write:
        log(f"❌ เกิดข้อผิดพลาดขณะบันทึกไฟล์ wave: {e_write}")
        return None

def setup_tinysa_for_measurement(ser, freq_hz):
    """ส่งคำสั่งเบื้องต้นเพื่อตั้งค่า TinySA สำหรับการวัด"""
    try:
        # ตัวอย่างคำสั่ง (อาจจะต้องปรับตามคู่มือ TinySA Ultra จริงๆ)
        # คำสั่งเหล่านี้เป็นเพียงการคาดเดา ต้องอ้างอิงจากเอกสารของ TinySA

        # เข้าสู่โหมด Spectrum Analyzer (ถ้าจำเป็น)
        # ser.write(b"MODE SA\r\n") # หรือคำสั่งที่คล้ายกัน
        # time.sleep(0.1)

        # ตั้งค่าความถี่กลาง
        ser.write(f"FREQ:CENT {freq_hz}HZ\r\n".encode())
        log(f"📡 [TinySA] Set Center Freq: {freq_hz} Hz")
        time.sleep(0.1) # หน่วงเวลาให้ TinySA ประมวลผลคำสั่ง

        # ตั้งค่า Span ให้แคบที่สุด (เช่น 0 Hz หรือค่าต่ำสุดที่ทำได้) เพื่อวัดที่จุดเดียว
        ser.write(b"FREQ:SPAN 0HZ\r\n") # หรือค่าที่น้อยมากๆ
        log(f"📡 [TinySA] Set Span: 0 Hz")
        time.sleep(0.1)

        # (ทางเลือก) ตั้งค่า RBW, Attenuation, Reference Level ถ้าจำเป็น
        # ser.write(b"BAND:RES 10KHZ\r\n") # ตัวอย่าง RBW
        # time.sleep(0.1)
        # ser.write(b"INP:ATT 0DB\r\n") # ตัวอย่าง Attenuation
        # time.sleep(0.1)

        # เปิด Marker 1 (ถ้าจะใช้ Marker อ่านค่า)
        # ser.write(b"CALC:MARK1 ON\r\n")
        # time.sleep(0.1)
        # ser.write(f"CALC:MARK1:X {freq_hz}HZ\r\n") # ให้ Marker 1 อยู่ที่ความถี่ที่เราต้องการ
        # time.sleep(0.1)

        # อาจจะมีคำสั่งอื่นๆ เช่น รอให้ sweep เสร็จ หรือ query error
        # ser.write(b"*OPC?\r\n") # รอ operation complete
        # ser.read_until().strip().decode() # อ่าน response

        # ser.write(b"SYST:ERR?\r\n") # ตรวจสอบ error
        # error_check = ser.read_until().strip().decode()
        # if not error_check.startswith("0,"):
        #     log(f"⚠️ [TinySA] Setup error: {error_check}")
        #     return False
        return True
    except Exception as e:
        log(f"❌ [TinySA] Exception during setup: {e}")
        return False

def get_signal_strength_tinysa(ser):
    """อ่านค่าความแรงสัญญาณจาก TinySA (ต้องปรับคำสั่งให้ตรงกับ TinySA Ultra)"""
    if not ser or not ser.is_open:
        log("⚠️ [TinySA] Serial port not open.")
        return None
    try:
        # คำสั่งที่ใช้ในการ Query ค่าพลังงาน/Marker อาจจะเป็น
        # 'CALC:MARK1:Y?' (อ่านค่า Y ของ Marker 1)
        # 'TRACE:DATA? TRACE1' แล้ว parse เพื่อหาค่าที่ความถี่กลาง
        # หรือคำสั่งเฉพาะอื่นๆ ของ TinySA Ultra

        # === ตัวอย่าง: สมมติว่ามีคำสั่งอ่านค่า Peak ของ Marker 1 ===
        # ser.reset_input_buffer() # เคลียร์ buffer ก่อนส่งคำสั่ง
        # ser.write(b"CALC:MARK1:MAX\r\n") # ย้าย marker ไปที่ peak (ถ้าต้องการ)
        # time.sleep(0.2) # รอให้ marker ย้าย
        ser.write(b"CALC:MARK1:Y?\r\n") # ส่งคำสั่ง Query ค่า Y ของ Marker 1
        response_bytes = ser.read_until(b'\r\n') # อ่านจนเจอ newline (หรือตาม terminator ของ TinySA)
        response_str = response_bytes.strip().decode('ascii', errors='ignore')
        log(f"📡 [TinySA] Raw Y response: '{response_str}'")

        # Parse ค่า dBm จาก response (รูปแบบอาจจะต้องปรับ)
        # TinySA มักจะตอบกลับเป็นตัวเลข เช่น "-50.75"
        match = re.search(r"([-+]?\d+\.\d+)", response_str) # มองหาตัวเลขทศนิยม
        if match:
            dbm_value = float(match.group(1))
            log(f"📡 [TinySA] Signal strength: {dbm_value:.2f} dBm")
            return dbm_value
        else:
            log(f"⚠️ [TinySA] Could not parse dBm value from response: '{response_str}'")
            return None
    except serial.SerialException as e:
        log(f"❌ [TinySA] Serial communication error: {e}")
        return None
    except Exception as e:
        log(f"❌ [TinySA] Error getting signal strength from TinySA: {e}")
        return None

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
        log(f"[Worker {worker_id}] Processing: {os.path.basename(file_for_transcription_wav if file_for_transcription_wav else 'NoWAV')}, MP3: {os.path.basename(mp3_path if mp3_path else 'NoMP3')}, Engine: {engine_actually_used}, Signal: {avg_signal_db_from_queue:.2f} dB" if avg_signal_db_from_queue is not None else f"[Worker {worker_id}] Processing: {os.path.basename(file_for_transcription_wav if file_for_transcription_wav else 'NoWAV')}, MP3: {os.path.basename(mp3_path if mp3_path else 'NoMP3')}, Engine: {engine_actually_used}, Signal: N/A")
        log(f"[Worker {worker_id}] 📝 ข้อความที่ถอดได้: {transcript_text}")  # แสดงข้อความที่ถอดได้

        try:
            # --- ส่วนตรวจสอบ Keyword และเรียก TTS ---
            if AZURE_TTS_RESPONSES_ENABLED and transcript_text and not transcript_text.startswith("["):  # ตรวจสอบว่าไม่ใช่ error message
                for tts_config_item in TTS_RESPONSES_CONFIG:
                    trigger_keywords = tts_config_item.get("trigger_keywords", [])
                    except_keywords_list = tts_config_item.get("except_keywords", [])  # ดึงคำที่ยกเว้น

                    found_trigger = False
                    for keyword in trigger_keywords:
                        if keyword.lower() in transcript_text.lower():  # เปรียบเทียบแบบ case-insensitive
                            found_trigger = True
                            break

                    if found_trigger:
                        # ถ้าเจอ Keyword หลักแล้ว ให้ตรวจสอบคำที่ยกเว้น
                        found_exception = False
                        if except_keywords_list:  # ตรวจสอบว่ามีรายการคำยกเว้นหรือไม่
                            for except_word in except_keywords_list:
                                if except_word.lower() in transcript_text.lower():
                                    found_exception = True
                                    log(f"[Worker {worker_id}] ℹ️ พบ Keyword '{keyword}' แต่ก็พบคำยกเว้น '{except_word}' ด้วย จึงไม่ทำการตอบกลับ TTS")
                                    break  # ออกจาก loop ของ except_keywords

                        if not found_exception:  # ถ้าไม่พบคำที่ยกเว้นใดๆ
                            response_to_speak_base = tts_config_item.get("response_text")
                            response_voice = tts_config_item.get("response_voice")

                            # --- เพิ่มค่าความแรงสัญญาณเข้าไปในข้อความตอบกลับ ---
                            final_response_to_speak = response_to_speak_base
                            if avg_signal_db_from_queue is not None and "{signal_db}" in final_response_to_speak:
                                final_response_to_speak = final_response_to_speak.replace("{signal_db}",
                                                                                          f"{avg_signal_db_from_queue:.1f}")
                            elif avg_signal_db_from_queue is not None:  # ถ้าไม่มี placeholder ก็ต่อท้าย (หรือปรับ logic ตามต้องการ)
                                final_response_to_speak += f" ระดับสัญญาณเฉลี่ย {avg_signal_db_from_queue:.1f} ดีบี"
                            # --- สิ้นสุดการเพิ่มค่าความแรงสัญญาณ ---

                        if final_response_to_speak:
                            log(f"[Worker {worker_id}] 🗣️ พบ Keyword, กำลังเตรียมพูด: '{final_response_to_speak}'")
                            # สร้าง thread ใหม่สำหรับ speak_text_azure เพื่อไม่ให้ block worker
                            tts_thread = threading.Thread(target=speak_text_azure,
                                                          args=(final_response_to_speak, response_voice), daemon=True)
                            tts_thread.start()
                            # ไม่ต้อง join tts_thread ที่นี่ เพื่อให้ worker ทำงานต่อไปได้
                        break  # ออกจาก loop ของ tts_config_item (เมื่อเจอ rule แรกที่ match และไม่ติด exception)
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
                log(f"[Worker {worker_id}] เงื่อนไขการลบ WAVs เป็นจริง (MP3 Enabled: {MP3_CONVERSION_ENABLED}, MP3 Path: {mp3_path})")
                # === ลบไฟล์ WAV ที่ไม่ต้องการแล้ว (หลังจาก upload เสร็จ) ===
                if processed_wav_to_delete and os.path.exists(processed_wav_to_delete):
                    # ลบ _processed.wav ถ้ามันถูกสร้างและไม่ใช่ไฟล์เดียวกับ original_wav_to_delete
                    if processed_wav_to_delete != original_wav_to_delete:
                        try:
                            os.remove(processed_wav_to_delete)
                            log(f"[Worker {worker_id}] 🗑️ ลบไฟล์ _processed.wav: {processed_wav_to_delete}")
                        except OSError as e:
                            log(f"[Worker {worker_id}] ⚠️ ไม่สามารถลบไฟล์ {processed_wav_to_delete}: {e}")

                if original_wav_to_delete and os.path.exists(original_wav_to_delete):
                    try:
                        os.remove(original_wav_to_delete)
                        log(f"[Worker {worker_id}] 🗑️ ลบไฟล์ .wav ต้นฉบับ: {original_wav_to_delete}")
                    except OSError as e:
                        log(f"[Worker {worker_id}] ⚠️ ไม่สามารถลบไฟล์ {original_wav_to_delete}: {e}")

            else:
                log_reason = ""
                if not MP3_CONVERSION_ENABLED:
                    log_reason = "การแปลง MP3 ถูกปิดใช้งาน"
                elif not (mp3_path and os.path.exists(mp3_path)):
                    log_reason = "การแปลง MP3 ล้มเหลว หรือไม่พบไฟล์ MP3"
                else:
                    log_reason = "เงื่อนไขอื่น (โปรดตรวจสอบ)"
                log(f"[Worker {worker_id}] ℹ️ ข้ามการลบไฟล์ WAVs. เนื่องจาก: {log_reason}")
                # log(f"[Worker {worker_id}] ℹ️ ข้ามการลบไฟล์ WAVs (MP3 Enabled: {MP3_CONVERSION_ENABLED}, MP3 Path: {mp3_path})")

        except Exception as e:
            log(f"[Worker {worker_id}]❌ ERROR ใน worker ขณะจัดการ task สำหรับ {os.path.basename(file_for_transcription_wav if file_for_transcription_wav else 'N/A')}: {e}")
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
            tinysa_serial_connection = serial.Serial(TINYSA_SERIAL_PORT, TINYSA_BAUDRATE, timeout=1) # ตั้ง timeout
            log(f"✅ [TinySA] Connected to TinySA on {TINYSA_SERIAL_PORT}")
            # ทำการ setup TinySA ครั้งแรก
            if not setup_tinysa_for_measurement(tinysa_serial_connection, TARGET_FREQUENCY_HZ): # Setup ด้วยความถี่เริ่มต้น
                 log(f"⚠️ [TinySA] Initial setup failed. Signal strength reading might be inaccurate.")
                 # อาจจะปิดการใช้งาน tinysa_serial_connection ถ้า setup ล้มเหลว
                 # tinysa_serial_connection.close()
                 # tinysa_serial_connection = None
            # else:
            #    tinysa_serial_connection.last_configured_freq = TARGET_FREQUENCY_HZ # เก็บความถี่ที่ setup ล่าสุด
        except serial.SerialException as e:
            log(f"❌ [TinySA] Could not open serial port {TINYSA_SERIAL_PORT}: {e}")
            log("ℹ️ [TinySA] Signal strength measurement will be disabled.")
            RTL_SDR_ENABLED = False # ปิดการใช้งานถ้าต่อไม่ได้
        except Exception as e_init:
            log(f"❌ [TinySA] Unexpected error during TinySA initialization: {e_init}")
            RTL_SDR_ENABLED = False
            
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

                result = record_until_silent(p_instance)
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
            tinysa_serial_connection.close()
            log("✅ [TinySA] Disconnected from TinySA.")
        log("✅ ระบบปิดเรียบร้อย")
