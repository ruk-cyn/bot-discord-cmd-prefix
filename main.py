import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View 
import aiohttp
import json
from datetime import datetime
import asyncio
from aiohttp import web, ClientSession
from dotenv import load_dotenv

# -----------------------------
# โหลด environment variables
# -----------------------------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ORDER_CHANNEL_ID = int(os.getenv("ORDER_CHANNEL_ID", "0"))
EVENT_CHANNEL_ID = int(os.getenv("EVENT_CHANNEL_ID", "0"))

if not DISCORD_TOKEN or not WEBHOOK_URL:
    raise ValueError("โปรดตั้งค่า environment variables ให้ครบ")

# -----------------------------
# Discord bot setup
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------
# Globals for Training
# -----------------------------
progress_message = None
is_running = False
last_update_time = None
TIMEOUT_SECONDS = 900  # 15 นาที

# -----------------------------
# ฟังก์ชัน Utility
# -----------------------------
def make_bar(p, total=20):
    filled = int((p / 100) * total)
    return "▓" * filled + "░" * (total - filled)

# -----------------------------
# 1️⃣ Calendar Embed
# -----------------------------
def create_event_embed(events):
    embed = discord.Embed(title="📅 ตารางกิจกรรมจาก Google Calendar", color=discord.Color.purple())
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

        start_dt = datetime.fromisoformat(start).strftime("%Y-%m-%d %H:%M") if start else "ไม่ระบุ"
        end_dt = datetime.fromisoformat(end).strftime("%Y-%m-%d %H:%M") if end else "ไม่ระบุ"

        table_text = (
            f"**เวลา:** {start_dt} - {end_dt}\n"
            f"**สถานที่:** {location}\n"
            f"**Event Link:** [คลิกเพื่อดู]({html_link})\n"
        )
        if meet_link:
            table_text += f"**Google Meet:** [เข้าร่วม]({meet_link})\n"
        table_text += f"{separator}"
        embed.add_field(name=summary, value=table_text, inline=False)

    return embed

async def fetch_calendar_events():
    async with aiohttp.ClientSession() as session:
        payload = {"source": "calendar"}
        async with session.post(WEBHOOK_URL, json=payload) as resp:
            if resp.status != 200:
                print(f"❌ ดึงข้อมูล Calendar ไม่สำเร็จ: {resp.status}")
                return []
            try:
                data = await resp.json()
                return data if isinstance(data, list) else []
            except:
                print("❌ ข้อมูล Calendar จาก Webhook ไม่ใช่ JSON")
                return []

@bot.command()
async def events(ctx):
    events_data = await fetch_calendar_events()
    if not events_data:
        await ctx.send("❌ ไม่มีข้อมูล Calendar")
        return
    embed = create_event_embed(events_data)
    await ctx.send(embed=embed)

# -----------------------------
# 2️⃣ Orders + Print Button
# -----------------------------
async def fetch_orders(channel, author_name="ระบบอัตโนมัติ", source="manual"):
    async with aiohttp.ClientSession() as session:
        payload = {"source": source}
        async with session.post(WEBHOOK_URL, json=payload) as resp:
            if resp.status != 200:
                await channel.send(f"❌ ดึงข้อมูลไม่สำเร็จ: {resp.status}")
                return
            try:
                data = await resp.json()
            except:
                await channel.send("❌ ข้อมูลจาก Webhook ไม่ใช่ JSON")
                return

            for order_item in data:
                picking_id = order_item.get("picking_id", "ไม่ระบุ")
                names = order_item.get("names", [])
                link = order_item.get("link")
                state = order_item.get("state", "ไม่ระบุ")
                state_display = {"confirmed": "รอ", "waiting": "รอ", "assigned": "พร้อม"}.get(state, "ไม่ระบุ")
                names_list = "\n".join([f"- {name}" for name in names]) if names else "ไม่มีสินค้า"

                embed = discord.Embed(
                    title=f"📦 คำสั่งซื้อ {picking_id}",
                    description=f"**สินค้า:**\n{names_list}\n\n**สถานะ:** `{state_display}`",
                    color=discord.Color.green() if state == "assigned" else discord.Color.blue()
                )
                embed.set_footer(text=f"เรียกโดย: {author_name}")

                view = None
                if state == "assigned" and link:
                    view = View()
                    view.add_item(Button(label="🖨️ Print", style=discord.ButtonStyle.link, url=link))
                await channel.send(embed=embed, view=view)

@bot.command()
async def order(ctx):
    await fetch_orders(ctx.channel, ctx.author.display_name, source="order")

# -----------------------------
# 3️⃣ Attach File (Google Drive)
# -----------------------------
class DriveButton(View):
    def __init__(self, url: str):
        super().__init__()
        self.add_item(Button(label="📎 กดที่นี่เพื่อแนบไฟล์", url=url))

@bot.command()
async def attach_file(ctx):
    drive_url = "https://drive.google.com/drive/u/0/folders/1Whual8ZwoS-DbdzJ03PWYwC1lgJFZytj"
    info_text = (
        "คุณสามารถแนบไฟล์ที่ต้องการใช้งานสำหรับ AI Agent ของเราได้ที่ปุ่มด้านล่าง\n\n"
        "**ก่อนแนบไฟล์ โปรดตรวจสอบดังนี้:**\n"
        "- หากยังไม่มีสิทธิ์เข้าถึงไฟล์ กรุณาขอสิทธิ์ด้วยอีเมลบริษัท\n"
        "- หลีกเลี่ยงการแนบไฟล์ที่มีข้อมูลซ้ำกันเยอะเกินไป\n"
        "- ขณะนี้สามารถใช้ **ไฟล์ Excel** ได้ตามปกติ"
    )
    await ctx.reply(info_text, view=DriveButton(drive_url), mention_author=False)

# -----------------------------
# 4️⃣ Training + Webhook Progress
# -----------------------------
@bot.command()
async def training(ctx):
    global progress_message, is_running, last_update_time
    allowed_channel_id = 1425405957609095230
    if ctx.channel.id != allowed_channel_id:
        await ctx.reply(
            f"⚠️ คำสั่งนี้สามารถใช้ได้เฉพาะช่องนี้เท่านั้น "
            f"[กดที่นี่](https://discord.com/channels/{ctx.guild.id}/{allowed_channel_id})",
            mention_author=False
        )
        return
    if is_running:
        await ctx.reply("⚠️ มีการทำงานอยู่แล้ว กรุณารอให้เสร็จสิ้นก่อนเริ่มใหม่", mention_author=False)
        return

    is_running = True
    progress_message = await ctx.reply(f"เริ่มต้นกระบวนการ... [{make_bar(0)}] 0%", mention_author=False)
    last_update_time = asyncio.get_event_loop().time()

    async with ClientSession() as session:
        await session.post(
            "https://n8n.cynlive.com/webhook-test/9e0e7c3e-9f2c-4c94-892f-b91997be92a4",
            json={"discord_user": str(ctx.author.id)}
        )
    check_webhook_timeout.start()

@tasks.loop(seconds=10)
async def check_webhook_timeout():
    global progress_message, is_running, last_update_time
    if is_running and last_update_time:
        now = asyncio.get_event_loop().time()
        if now - last_update_time > TIMEOUT_SECONDS:
            if progress_message:
                await progress_message.edit(content="❌ Process timeout! ไม่มีการอัปเดตจาก webhook")
                progress_message = None
            is_running = False
            check_webhook_timeout.stop()

async def webhook_handler(request):
    global progress_message, is_running, last_update_time
    data = await request.json()
    percent = data.get("progress", 0)
    message = data.get("message", "")
    if progress_message:
        await progress_message.edit(content=f"{message} [{make_bar(percent)}] {percent}%")
        last_update_time = asyncio.get_event_loop().time()
        if percent >= 100:
            await progress_message.edit(content=f"✅ เสร็จสมบูรณ์ [{make_bar(100)}] 100%")
            progress_message = None
            is_running = False
            check_webhook_timeout.stop()
    return web.Response(text="ok")

# -----------------------------
# 5️⃣ Auto Tasks
# -----------------------------
@tasks.loop(seconds=3600)
async def auto_order():
    if ORDER_CHANNEL_ID:
        channel = bot.get_channel(ORDER_CHANNEL_ID)
        if channel:
            await fetch_orders(channel, "ระบบอัตโนมัติ", source="order")

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
# 6️⃣ Webserver for Training webhook
# -----------------------------
app = web.Application()
app.router.add_post("/callback", webhook_handler)

async def start_webserver():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

# -----------------------------
# 7️⃣ Help Command
# -----------------------------
@bot.command()
async def help(ctx):
    """แสดงรายการคำสั่งทั้งหมด"""
    embed = discord.Embed(title="🤖 คำสั่งของบอท", color=discord.Color.gold())
    
    embed.add_field(name="!events", value="📅 ดึงตารางกิจกรรมจาก Google Calendar และแสดงใน embed", inline=False)
    embed.add_field(name="!order", value="📦 ดึงคำสั่งซื้อล่าสุด พร้อมปุ่ม Print สำหรับ order ที่พร้อมจัดส่ง", inline=False)
    embed.add_field(name="!attach_file", value="📎 ส่งปุ่ม Google Drive ให้ผู้ใช้แนบไฟล์ Excel สำหรับ AI Agent", inline=False)
    embed.add_field(name="!training", value="⚙️ เริ่ม process การ training ของ AI Agent และแสดง progress bar\n🔒 ใช้ได้เฉพาะช่องที่กำหนด", inline=False)
    embed.add_field(name="Auto Tasks", value="🕒 ระบบจะดึงคำสั่งซื้อทุก 1 ชั่วโมง และดึงตารางกิจกรรมทุก 1 วันโดยอัตโนมัติ", inline=False)
    embed.set_footer(text="ใช้คำสั่ง !help เพื่อดูรายการคำสั่งทั้งหมด")
    
    await ctx.send(embed=embed)

# -----------------------------
# on_ready
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if ORDER_CHANNEL_ID:
        auto_order.start()
    if EVENT_CHANNEL_ID:
        auto_events.start()
    bot.loop.create_task(start_webserver())

# -----------------------------
# Run bot
# -----------------------------
bot.run(DISCORD_TOKEN)
