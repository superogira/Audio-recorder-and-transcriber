# Audio-recorder-and-transcriber
source code ทำงานกับ Python 3.11.9 ถ้าเวอร์ชั่นสูงกว่านี้อาจจะไม่ทำงาน


## ไปทดลองเล่นได้ที่
[E25WOP.com](https://e25wop.com/ham_radio_recorder_transcriber/)
![Alt text](Audio-recorder-and-transcriber-web?raw=true)

## การถอดข้อความจากเสียง ปัจจุบันทำไว้รองรับ 2 ระบบ คือ
1. Microsoft Azure AI Speech to Text
2. Google Cloud Speech-to-Text

เพราะฉนั้นก่อนการใช้งานควรไปสร้าง API ก่อน (วิธีการสมัคร , การสร้าง สามารถสอบถามจาก ChatGPT ได้เลย)


## การตั้งค่าการทำงานของระบบ ให้ตั้งค่าที่ไฟล์ recorder_transcriber-config.json
![Alt text](recorder_transcriber-config.json.png?raw=true)


## ถ้าจะ Host ระบบเว็บด้วยตัวเอง อย่าลืมไป...
- กำหนด username ใน secure_config.php
- ทำ echo password_hash แล้วเอาค่าที่ hash แล้วไปกำหนดให้ $hashed_password
- สร้างฐานข้อมูลจากไฟล์ 1.database.sql
- ตั้งค่า ฐานข้อมูลใน db_config.php
- ตั้งค่าว่าจะเก็บไฟล์ขนาดรวมกันได้เท่าไหร่  ($maxSize) ก่อนจะลบไฟล์เก่าสุดออก ใน upload.php (ค่าพื้นฐาน คือ 5GB)


# ปัญหาที่ทราบอยู่แล้ว
- ถ้าใช้ Remote Desktop Connection ของ Windows เพื่อ Remote เข้าไป run ระบบ
ตอนตัดการเชื่อมต่อ Remote จะเกิด error แนวทางแก้ไขเบื้องต้นคือ ให้ใช้โปรแกรม Remote ตัวอื่น เช่น Anydesk


### มีปัญหาข้อสอบถามติดต่อได้ที่ Facebook
[FACEBOOK](https://www.facebook.com/superogira)
