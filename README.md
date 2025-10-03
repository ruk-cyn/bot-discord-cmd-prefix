# 1. หยุดและลบ container เก่า
docker-compose down

# 2. สร้าง image ใหม่ (เพื่อติดตั้ง requirements ล่าสุด)
docker-compose build --no-cache

# 3. รัน container ใหม่
docker-compose up -d
