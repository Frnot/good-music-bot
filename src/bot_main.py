import logging
import sys

import discord
from discord.ext import commands as dcommands
from dotenv import load_dotenv

if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata

# Import modules
from modules.admin_commands import AdminCommands, has_permission
from modules.music import Music

log = logging.getLogger(__name__)

# gets version from installed package
version = metadata.version('good_music_bot')


def run_bot(bot_token):
    log.info(f"Running version v{version}")

    #intents = discord.Intents.default()
    #intents.message_content = True

    # Create bot
    global bot
    bot = Bot(command_prefix=dcommands.when_mentioned_or("."), intents=discord.Intents.all(),
              activity=discord.Activity(name=f"v{version}", type=discord.ActivityType.playing))

    # Run bot
    bot.run(bot_token)



class Bot(dcommands.Bot):
    async def on_ready(self):
        log.info(f"Logged on as {bot.user}!\nReady.")

    async def setup_hook(self):
        # Load modules
        await bot.add_cog(AdminCommands(bot))
        await bot.add_cog(Music(bot))
        # Load permission checker
        bot.add_check(has_permission)

    def version(self):
        return version


