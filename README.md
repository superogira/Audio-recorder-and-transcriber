# Audio-recorder-and-transcriber
ไปทดลองเล่นได้ที่ >>> [E25WOP.com](https://e25wop.com/ham_radio_recorder_transcriber/)


## การถอดข้อความจากเสียง ปัจจุบันทำไว้รองรับ 2 ระบบ คือ
1. Microsoft Azure AI Speech to Text
2. Google Cloud Speech-to-Text
เพราะฉนั้นก่อนการใช้งานควรไปสมัครสร้าง API ก่อน


## การตั้งค่าการทำงานของระบบ ให้ตั้งค่าที่ไฟล์ recorder_transcriber-config.json
![Alt text](recorder_transcriber-config.json.png?raw=true)


## ถ้าจะ Host ระบบเว็บด้วยตัวเอง อย่าลืมไป...
- กำหนด username ใน secure_config.php
- ทำ echo password_hash แล้วเอาค่าที่ hash แล้วไปกำหนดให้ $hashed_password
- สร้างฐานข้อมูลจากไฟล์ 1.database.sql
- ตั้งค่า ฐานข้อมูลใน db_config.php
- ตั้งค่าว่าจะเก็บไฟล์ขนาดรวมกันได้เท่าไหร่  ($maxSize) ก่อนจะลบไฟล์เก่าสุดออก ใน upload.php (ค่าพื้นฐาน คือ 5GB)


### มีปัญหาข้อสอบถามติดต่อได้ที่ Facebook
[FACEBOOK](https://www.facebook.com/superogira)
