import discord
from discord.ext import commands
from discord import ui
import asyncio
import os
from dotenv import load_dotenv
import io

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Intents (채팅을 읽어야 하므로 필수!)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # ⭐ 중요: 이게 켜져 있어야 !setup을 읽음

# !로 시작하는 명령어로 변경
bot = commands.Bot(command_prefix="!", intents=intents)

# === Views (버튼들) ===
class VerifyView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label="Verify & Enter", style=discord.ButtonStyle.success, emoji="✅", custom_id="v_enter")
    async def verify(self, interaction: discord.Interaction, button: ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Member")
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("Welcome! Access Granted.", ephemeral=True)
        else:
            await interaction.response.send_message("Creating role...", ephemeral=True)

class TicketLaunchView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label="Open Private Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="t_open")
    async def open(self, interaction: discord.Interaction, button: ui.Button):
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        member_role = discord.utils.get(interaction.guild.roles, name="Member")
        if member_role:
             overwrites[member_role] = discord.PermissionOverwrite(read_messages=False) # 멤버들도 못 봄

        cat = discord.utils.get(interaction.guild.categories, name="🔒 SUPPORT TICKETS")
        if not cat: cat = await interaction.guild.create_category("🔒 SUPPORT TICKETS") # 없으면 만듦

        ch = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name}", category=cat, overwrites=overwrites)

        embed = discord.Embed(
            title="🎫 Private Support",
            description=f"Hello {interaction.user.mention}! Staff will be here soon.",
            color=discord.Color.gold()
        )
        await ch.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"Ticket created: {ch.mention}", ephemeral=True)

class TicketControlView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label="Close & Log", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="t_close")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Closing...", ephemeral=True)

        # LOGGING
        messages = [msg async for msg in interaction.channel.history(limit=500, oldest_first=True)]
        log_text = f"Transcrip for {interaction.channel.name}\n\n"
        for m in messages:
            log_text += f"[{m.created_at}] {m.author.name}: {m.content}\n"

        log_ch = discord.utils.get(interaction.guild.channels, name="admin-logs")
        if log_ch:
            file = discord.File(io.StringIO(log_text), filename=f"{interaction.channel.name}.txt")
            await log_ch.send(f"📕 Ticket Closed", file=file)

        await asyncio.sleep(1)
        await interaction.channel.delete()

# === COMMANDS (채팅 명령어 버전) ===
@bot.command()
async def clear(ctx):
    """ !clear : 모든 채널 삭제 """
    await ctx.send("💥 Clearing all channels...")
    for ch in ctx.guild.channels:
        try: await ch.delete()
        except: pass
    await ctx.guild.create_text_channel("setup-zone")

@bot.command()
async def setup(ctx):
    """ !setup : 서버 구축 (V3) """
    await ctx.send("🚧 Building V3 Server...")
    guild = ctx.guild

    # 1. Roles
    if not discord.utils.get(guild.roles, name="Member"):
        await guild.create_role(name="Member", color=discord.Color.blue(), hoist=True)
    member_role = discord.utils.get(guild.roles, name="Member")
    everyone = guild.default_role

    # 2. ENTRANCE
    cat1 = await guild.create_category("🚪 ENTRANCE")
    c1 = await guild.create_text_channel("verify-here", category=cat1)
    await c1.set_permissions(everyone, read_messages=True)
    await c1.set_permissions(member_role, read_messages=False)
    await c1.send("Click to Verified:", view=VerifyView())

    # 3. PLAZA
    cat2 = await guild.create_category("📢 PLAZA")
    await cat2.set_permissions(everyone, read_messages=False)
    await cat2.set_permissions(member_role, read_messages=True)

    await guild.create_text_channel("announcements", category=cat2)
    await guild.create_text_channel("general-chat", category=cat2)
    try: await guild.create_forum_channel("feature-requests", category=cat2)
    except: await guild.create_text_channel("feature-requests-txt", category=cat2)

    # 4. SUPPORT
    cat3 = await guild.create_category("🆘 SUPPORT")
    await cat3.set_permissions(everyone, read_messages=False)
    await cat3.set_permissions(member_role, read_messages=True)
    c_help = await guild.create_text_channel("get-help", category=cat3)
    await c_help.set_permissions(member_role, send_messages=False) # 채팅 금지
    await c_help.send("Need Support?", view=TicketLaunchView())

    # 5. ADMIN
    cat_admin = await guild.create_category("🔒 ADMIN ONLY")
    await cat_admin.set_permissions(everyone, read_messages=False)
    await guild.create_text_channel("admin-logs", category=cat_admin)

    # 6. VOICE
    cat_voice = await guild.create_category("🔊 VOICE")
    await cat_voice.set_permissions(everyone, read_messages=False)
    await cat_voice.set_permissions(member_role, read_messages=True)
    await guild.create_voice_channel("Community Voice", category=cat_voice)

    # 7. Ticket Category
    await guild.create_category("🔒 SUPPORT TICKETS")

    await ctx.send("✅ Setup Complete!")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Ready! Type '!setup' in chat.")
    bot.add_view(VerifyView())
    bot.add_view(TicketLaunchView())
    bot.add_view(TicketControlView())

if __name__ == "__main__":
    bot.run(TOKEN)
