import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View 
import aiohttp
import json
from datetime import datetime


# โหลดไฟล์ .env
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("โปรดตั้งค่า environment variable DISCORD_TOKEN")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("โปรดตั้งค่า environment variable WEBHOOK_URL")

ORDER_CHANNEL_ID = int(os.getenv("ORDER_CHANNEL_ID", "0"))  # สำหรับ Auto order
EVENT_CHANNEL_ID = int(os.getenv("EVENT_CHANNEL_ID", "0"))  # สำหรับ Auto events

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------
# ฟังก์ชันสร้าง embed table จาก Calendar
# -----------------------------
def create_event_embed(events):
    embed = discord.Embed(
        title="📅 ตารางกิจกรรมจาก Google Calendar",
        color=discord.Color.purple()
    )

    separator = "-------------------------------------"

    for event in events:
        summary = event.get("summary", "ไม่ระบุ")
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        location = event.get("location", "ไม่ระบุ")
        html_link = event.get("htmlLink", "")
        meet_link = ""
        entry_points = event.get("conferenceData", {}).get("entryPoints", [])
        if entry_points:
            meet_link = entry_points[0].get("uri", "")

        # แปลงเวลาให้อ่านง่าย
        start_dt = datetime.fromisoformat(start).strftime("%Y-%m-%d %H:%M") if start else "ไม่ระบุ"
        end_dt = datetime.fromisoformat(end).strftime("%Y-%m-%d %H:%M") if end else "ไม่ระบุ"

        # สร้าง table-like string
        table_text = (
            f"**เวลา:** {start_dt} - {end_dt}\n"
            f"**สถานที่:** {location}\n"
            f"**Event Link:** [คลิกเพื่อดู]({html_link})\n"
        )
        if meet_link:
            table_text += f"**Google Meet:** [เข้าร่วม]({meet_link})\n"

        table_text += f"{separator}"  # เพิ่มเส้นกั้น

        embed.add_field(name=summary, value=table_text, inline=False)

    return embed

# -----------------------------
# ฟังก์ชันดึงข้อมูล Calendar จาก Webhook
# -----------------------------
async def fetch_calendar_events():
    async with aiohttp.ClientSession() as session:
        payload = {"source": "calendar"}  # ✅ ส่งบอกว่าเอาข้อมูล calendar
        async with session.post(WEBHOOK_URL, json=payload) as resp:
            if resp.status != 200:
                print(f"❌ ดึงข้อมูล Calendar ไม่สำเร็จ: {resp.status}")
                return []

            text = await resp.text()
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    return data
                else:
                    print("⚠️ ข้อมูล Calendar ไม่ใช่ list")
                    return []
            except json.JSONDecodeError:
                print("❌ ข้อมูล Calendar จาก Webhook ไม่ใช่ JSON")
                return []

# -----------------------------
# คำสั่ง !events
# -----------------------------
@bot.command()
async def events(ctx):
    events_data = await fetch_calendar_events()
    if not events_data:
        await ctx.send("❌ ไม่มีข้อมูล Calendar")
        return

    embed = create_event_embed(events_data)
    await ctx.send(embed=embed)

# -----------------------------
# ฟังก์ชันสำหรับดึงข้อมูล order + ปุ่ม Print
# -----------------------------
async def fetch_orders(channel, author_name="ระบบอัตโนมัติ", source="manual"):
    async with aiohttp.ClientSession() as session:
        payload = {"source": source}
        async with session.post(WEBHOOK_URL, json=payload) as resp:
            if resp.status != 200:
                await channel.send(f"❌ ดึงข้อมูลไม่สำเร็จ: {resp.status}")
                return

            text = await resp.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                await channel.send("❌ ข้อมูลจาก Webhook ไม่ใช่ JSON")
                return

            for order_item in data:
                picking_id = order_item.get("picking_id", "ไม่ระบุ")
                names = order_item.get("names", [])
                link = order_item.get("link")
                state = order_item.get("state", "ไม่ระบุ")

                # แปลง state เป็นข้อความสำหรับแสดง
                if state in ["confirmed", "waiting"]:
                    state_display = "รอ"
                elif state == "assigned":
                    state_display = "พร้อม"
                else:
                    state_display = "ไม่ระบุ"

                # รายการสินค้า
                names_list = "\n".join([f"- {name}" for name in names]) if names else "ไม่มีสินค้า"

                # Embed
                embed = discord.Embed(
                    title=f"📦 คำสั่งซื้อ {picking_id}",
                    description=f"**สินค้า:**\n{names_list}\n\n**สถานะ:** `{state_display}`",
                    color=discord.Color.green() if state == "assigned" else discord.Color.blue()
                )
                embed.set_footer(text=f"เรียกโดย: {author_name}")

                # ปุ่ม Print เฉพาะเมื่อ state == assigned และมีลิงก์
                view = None
                if state == "assigned" and link:
                    view = View()
                    print_button = Button(
                        label="🖨️ Print",
                        style=discord.ButtonStyle.link,
                        url=link
                    )
                    view.add_item(print_button)

                await channel.send(embed=embed, view=view)
                
# -----------------------------
# คำสั่ง !order
# -----------------------------
@bot.command()
async def order(ctx):
    await fetch_orders(ctx.channel, ctx.author.display_name, source="order")

# -----------------------------
# Task: รันอัตโนมัติทุก 1 ชั่วโมง
# -----------------------------
@tasks.loop(seconds=3600)
async def auto_order():
    if ORDER_CHANNEL_ID:
        channel = bot.get_channel(ORDER_CHANNEL_ID)
        if channel:
            await fetch_orders(channel, "ระบบอัตโนมัติ", source="order")

# -----------------------------
# Task: เด้ง !events ทุก 1 วัน
# -----------------------------
@tasks.loop(seconds=86400)
async def auto_events():
    if EVENT_CHANNEL_ID:
        channel = bot.get_channel(EVENT_CHANNEL_ID)
        if channel:
            events_data = await fetch_calendar_events()
            if events_data:
                embed = create_event_embed(events_data)
                await channel.send(embed=embed)

# -----------------------------
# Event on_ready
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if ORDER_CHANNEL_ID:
        auto_order.start()
    if EVENT_CHANNEL_ID:
        auto_events.start()

# -----------------------------
# รันบอท
# -----------------------------
bot.run(DISCORD_TOKEN)
