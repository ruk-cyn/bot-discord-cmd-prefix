import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# สร้าง Modal (ฟอร์ม)
class FeedbackModal(Modal):
    def __init__(self):
        super().__init__(title="📋 ฟอร์ม Feedback")

        # สร้าง TextInput 2 ช่อง
        self.name = TextInput(
            label="ชื่อของคุณ",
            placeholder="กรอกชื่อที่นี่",
            required=True,
            max_length=50
        )
        self.add_item(self.name)

        self.feedback = TextInput(
            label="ความคิดเห็น",
            placeholder="กรอกความคิดเห็นของคุณ",
            style=discord.TextStyle.paragraph,  # multi-line
            required=True,
            max_length=500
        )
        self.add_item(self.feedback)

    async def on_submit(self, interaction: discord.Interaction):
        # เมื่อ submit ให้ตอบกลับ
        await interaction.response.send_message(
            f"ขอบคุณ {self.name.value}! เราได้รับ Feedback ของคุณแล้ว:\n{self.feedback.value}",
            ephemeral=True
        )

# คำสั่งส่งปุ่มเปิดฟอร์ม
@bot.command()
async def feedback(ctx):
    button = Button(label="กรอกฟอร์ม Feedback", style=discord.ButtonStyle.primary)

    async def button_callback(interaction):
        await interaction.response.send_modal(FeedbackModal())

    button.callback = button_callback

    view = View()
    view.add_item(button)

    await ctx.send("กดปุ่มด้านล่างเพื่อกรอกฟอร์ม Feedback:", view=view)

bot.run("MTQxNTk0MzI5MzMyMTM1MTE5OA.GYaKf1.a6t5qq5yVykCTVZ87XR5wk5hNxUSn3CGKrVUco")
