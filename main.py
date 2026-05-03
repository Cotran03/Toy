# Imports
import discord
from discord.ext import commands
import os

# Import Config
from config import TOKEN, GUILD_ID, ADMIN_COMMAND_CHANNEL

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
    if ctx.channel.id != ADMIN_COMMAND_CHANNEL:
        await ctx.message.delete()
        return

    if not ctx.author.guild_permissions.administrator:
        await ctx.message.delete()
        return

    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)

    await ctx.message.delete()
    await ctx.send(f"슬래시 커맨드 {len(synced)}개 동기화 완료", delete_after=5)


# Run the bot
bot.run(TOKEN)