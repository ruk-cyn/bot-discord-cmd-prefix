# ----------------------------
# ขั้นตอนที่ 1: ใช้ Python image
# ----------------------------
FROM python:3.11-slim

# ตั้งค่า working directory
WORKDIR /app

# คัดลอกไฟล์ requirements.txt เข้า container
COPY requirements.txt .

# ติดตั้ง dependencies
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอก source code ทั้งหมดเข้า container
COPY . .

# ตั้งค่า Timezone เป็น Asia/Bangkok (ถ้าต้องการให้เวลาตรงกับไทย)
RUN apt-get update && apt-get install -y tzdata && \
    ln -fs /usr/share/zoneinfo/Asia/Bangkok /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean

# กำหนด environment ว่าเป็น production
ENV PYTHONUNBUFFERED=1

# คำสั่งรันบอท
CMD ["python", "main.py"]
