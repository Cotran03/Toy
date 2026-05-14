# Imports
import discord
from discord.ext import commands
import os

from utils.send_log import send_log

# Import Config
from config import TOKEN, GUILD_ID

# Import DB
from db.database import init_db


# Intents
intents = discord.Intents.all()


# Import Cogs
async def load_extensions(bot):
    for filename in os.listdir('cogs'):
        if filename.endswith('.py'):
            extension = 'cogs.' + filename[:-3]
            print(f"{extension} 모듈을 불러왔습니다.")
            await bot.load_extension(extension)


# Bot
class MyBot(commands.Bot):
    async def setup_hook(self):
        init_db()
        await load_extensions(self)
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

bot = MyBot(command_prefix='&', intents=intents, help_command=None)


# Events
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


# Admin Command: &sync
@bot.command(name="sync")
async def sync(ctx: commands.Context):

    if not ctx.author.guild_permissions.administrator:
        await ctx.message.delete()
        await send_log(bot, ctx.author, "&sync", "권한 없는 사용자가 명령어 사용 시도")
        return

    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)

    await ctx.message.delete()
    await ctx.send(f"슬래시 커맨드 {len(synced)}개 동기화 완료", delete_after=5)

# Admin Command: &reload
@bot.command(name="reload")
async def reload(ctx: commands.Context):
    if not ctx.author.guild_permissions.administrator:
        await ctx.message.delete()
        await send_log(bot, ctx.author, "&reload", "권한 없는 사용자가 명령어 사용 시도")
        return

    results = []
    for filename in os.listdir('cogs'):
        if filename.endswith('.py'):
            ext = f"cogs.{filename[:-3]}"
            try:
                await bot.reload_extension(ext)
                results.append(f"✅ {ext}")
            except Exception as e:
                results.append(f"❌ {ext} — {e}")

    await ctx.message.delete()
    await ctx.send("\n".join(results), delete_after=5)


# Run the bot
bot.run(TOKEN)