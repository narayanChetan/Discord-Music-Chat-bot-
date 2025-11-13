import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
import os
import aiohttp
import asyncio

# LOAD ENVIRONMENT 
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

FFMPEG_PATH = "ffmpeg"  # or r"C:\path\to\ffmpeg.exe" on Windows
queues = {}

# INTENTS 
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# MUSIC SYSTEM
async def play_next(ctx):
    guild_id = ctx.guild.id
    if queues.get(guild_id) and len(queues[guild_id]) > 0:
        search = queues[guild_id].pop(0)

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'noplaylist': True,
            'default_search': 'ytsearch',
            'quiet': True,
            'extract_flat': False,
            'geo_bypass': True,
            'nocheckcertificate': True
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search, download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    info = info['entries'][0]

                audio_url = info['url']
                title = info['title']

            voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
            voice_client.play(
                FFmpegPCMAudio(audio_url, executable=FFMPEG_PATH, options='-vn'),
                after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
            )
            await ctx.send(f"▶ Now playing: **{title}**")

        except Exception as e:
            await ctx.send(f"⚠️ Error playing track: `{search}`\n```{e}```")
            print("Error:", e)


@bot.command(name="play", help="Play song by name or URL in VC.")
async def play(ctx, *, search: str):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ You must be in a voice channel first!")
        return

    vc_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client:
        voice_client = await vc_channel.connect()

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    queues[guild_id].append(search)
    await ctx.send(f"✅ Added to queue: `{search}`")

    # If nothing is playing, start playing
    if not voice_client.is_playing():
        await play_next(ctx)


@bot.command(name="stop", help="Stop current song but remain in VC.")
async def stop(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏹️ Stopped playback.")
    else:
        await ctx.send("❌ No audio is playing right now.")


@bot.command(name="skip", help="Skip current song and play next in queue.")
async def skip(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Skipped current song.")
    else:
        await ctx.send("❌ No song is playing to skip.")


@bot.command(name="queue", help="Show current music queue.")
async def show_queue(ctx):
    guild_id = ctx.guild.id
    if queues.get(guild_id) and len(queues[guild_id]) > 0:
        queue_list = "\n".join(f"{i+1}. {item}" for i, item in enumerate(queues[guild_id]))
        await ctx.send(f"📜 Current queue:\n{queue_list}")
    else:
        await ctx.send("✅ The queue is currently empty.")


@bot.command(name="leave", help="Disconnect bot from VC.")
async def leave(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("👋 Disconnected from voice channel.")
        queues.pop(ctx.guild.id, None)
    else:
        await ctx.send("❌ I'm not in a voice channel.")


# CHATBOT (DeepSeek via OpenRouter)
@bot.command()
async def chat(ctx, *, prompt: str):
    await ctx.send("🤖 Thinking...")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-github-name/discord-bot",
        "X-Title": "Discord Bot"
    }

    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a friendly Discord assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                print("Chat API result:", result)
                reply = result["choices"][0]["message"]["content"]
                await ctx.send(f"🤖 **ChatBot:** {reply}")

    except Exception as e:
        await ctx.send("⚠️ API error. Try again later.")
        print("Chatbot error:", e)


# CALL MEMBER (DM INVITE) 
@bot.command()
async def call(ctx, member: discord.Member):
    if not ctx.author.voice:
        return await ctx.send("❌ Join a voice channel first!")

    vc = ctx.author.voice.channel
    embed = discord.Embed(
        title="📞 Meeting Invite!",
        description=f"**{ctx.author.name}** is calling you to join VC:\n👉 **{vc.name}**",
        color=0x00FF00
    )

    try:
        await member.send(embed=embed)
        await ctx.send(f"✅ Meeting request sent to {member.mention}!")
    except discord.Forbidden:
        await ctx.send("⚠️ Unable to DM this user. They might have DMs disabled.")


@bot.event
async def on_ready():
    print(f"✅ Bot is live as {bot.user}")


bot.run(TOKEN)
