import sys
import logging
import discord
from discord.ext import commands as dcommands
from dotenv import load_dotenv
if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata

# Import modules
from modules import admin_commands, music


log = logging.getLogger(__name__)

version = metadata.version('good_music_bot')




def run_bot(bot_token):
    log.info(f"Running version v{version}")

    # Create bot
    global bot
    bot = Bot(command_prefix=guild_prefix, intents=discord.Intents.all(),
              activity=discord.Activity(name=f"v{version}", type=discord.ActivityType.playing))

    # Load modules
    bot.add_cog(modules.admin_commands.Cog(bot))
    bot.add_cog(commands.general.Cog(bot))

    bot.add_cog(music.Cog(bot))

    # Run bot
    bot.run(bot_token)

    # Cleanup
    db.close()



async def guild_prefix(bot, message):
    bot
    prefix_return = await bot.get_cog('Prefix').get(message.guild.id)
    return dcommands.when_mentioned_or(prefix_return)(bot, message)


class Bot(dcommands.Bot):
    async def on_ready(self):
        log.info(f"Logged on as {bot.user}!\nReady.")
