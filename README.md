# Audio-recorder-and-transcriber

การถอดข้อความจากเสียง ปัจจุบันทำไว้รองรับ 2 ระบบ คือ
1. Microsoft Azure AI Speech to Text
2. Google Cloud Speech-to-Text
เพราะฉนั้นก่อนการใช้งานควรไปสมัครสร้าง API ก่อน



การตั้งค่าการทำงานของระบบ ให้ตั้งค่าที่ไฟล์ recorder_transcriber-config.json
{
  "azure_speech_key": "xxxxx",					< Key จาก Azure
  "azure_service_region": "southeastasia",		< ภูมิภาคที่จะเรียกใช้ทรัพยากรของ Azure
  "azure_language": "th-TH",					< ภาษาที่จะให้ Auzure ถอดข้อความ
  "google_credentials": "xxx-xxxx-xxxxx.json",	< ชื่อไฟล์ api credential ที่ได้จาก Google Cloud (วางไว้ที่เดียวกัน หรือกำหนดตำแหน่งให้ถูก)
  "google_language_code": "th-TH",				< ภาษาที่จะให้ Google Cloud ถอดข้อความ
  "frequency": "",								< ความถี่ที่บันทึกเสียง หรือถ้าฟังหลายความถี่จะปล่อยว่างไม่ต้องกำหนด หรือใส่เป็นข้อความอื่น ๆ ก็ได้ เช่น scan เป็นต้น 
  "station": "E25WOP",							< ชื่อสถานี หรือ Callsign หรือ ชื่ออื่น ๆ ใด ๆ ของผู้บันทึกเสียง
  "threshold": 400,								< ความดังของเสียงต้องเกินกว่าค่านี้ ถึงจะเริ่มบันทึกเสียง (โปรดตรวจสอบค่าของเสียงในการใช้งานครั้งแรก ว่าอยุ่ประมาณไหน แล้วค่อยมาตั้งให้เหมาะสม)
  "record_length": 60,							< ระยะเวลา * วินาทีสูงสุด ที่จะบันทึกได้  (หากเป็นการส่งไฟล์เสียงไปให้ Google Cloud ถอดข้อความ จะได้ไม่เกิน 60 วินาที)
  "silence_limit": 0.7,							< ถ้าเงียบเกินกว่า * วินาที ให้หยุดบันทึกเสียง หรือก็คือ ถ้าค่าต่ำกว่า threshold เป็นเวลาที่กำหนด ก็จะหยุดบันทึก
  "min_duration_sec": 2.5,						< ถ้าความยาวเสียงน้อยกว่า * วินาที ไม่ต้องบันทึกไฟล์ ไม่ต้องแปลงไฟล์
  "save_folder": "audio_files",					< ชื่อโฟลเดอร์สำหรับเก็บไฟล์เสียงที่บันทึก
  "log_file": "system.log",						< ชื่อไฟล์สำหรับเก็บ Log
  "num_workers": 5,								< จำนวน worker ที่จะประมวลผลพร้อมกันได้ เพื่อที่จะได้อัดเสียงและประมวลผลได้ต่อเนื่อง
  "upload": false,								< เปิด-ปิด ระบบอัพโหลดไฟล์ (true คือ เปิดการใช้งาน , false คือ ปิดการใช้งาน)
  "upload_url": "https://e25wop.com/ham_radio_recorder_transcriber/upload.php",			< URL เว็บไซท์ของระบบบันทึกข้อมูลและอัพโหลดไฟล์ไปเก็บ หรือใช้ของ e25wop ไปเลยก็ได้ (แต่ต้องกำหนด upload เป็น true ด้วย)
  "transcribe_engine": "azure"															< ระบบที่เลือกใช้มาถอดเสียงจากข้อความ สามารถกำหนดได้เป็น  azure, google, random และ alternate
}



***ถ้าจะ Host ระบบเว็บด้วยตัวเอง อย่าลืมไป...
- กำหนด username ใน secure_config.php
- ทำ echo password_hash แล้วเอาค่าที่ hash แล้วไปกำหนดให้ $hashed_password
- สร้างฐานข้อมูลจากไฟล์ 1.database.sql
- ตั้งค่า ฐานข้อมูลใน db_config.php
- ตั้งค่าว่าจะเก็บไฟล์ขนาดรวมกันได้เท่าไหร่  ($maxSize) ก่อนจะลบไฟล์เก่าสุดออก ใน upload.php (ค่าพื้นฐาน คือ 5GB)
