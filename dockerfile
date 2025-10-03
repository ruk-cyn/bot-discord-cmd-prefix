FROM python:3.11-slim

WORKDIR /app

# ติดตั้ง dependencies ทั้งหมด รวม dotenv
RUN pip install --no-cache-dir discord.py==2.4.0 requests python-dotenv

COPY . .

CMD ["python", "main.py"]
