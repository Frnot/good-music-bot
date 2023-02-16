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
from utils import db
from modules.admin_commands import AdminCommands
from modules.music import Music
from modules.permissions import Permissions

log = logging.getLogger(__name__)

# gets version from installed package
version = metadata.version('good_music_bot')


def run_bot(bot_token):
    log.info(f"Running version v{version}")

    # Create bot
    global bot
    bot = Bot(command_prefix=dcommands.when_mentioned_or("."), intents=discord.Intents.all(),
              activity=discord.Activity(name=f"v{version}", type=discord.ActivityType.playing))

    # Run bot
    bot.run(bot_token)

    # Cleanup
    db.close()



class Bot(dcommands.Bot):
    async def on_ready(self):
        log.info(f"Logged on as {bot.user}!\nReady.")

    async def setup_hook(self):
        # Load Database
        log.info("Loading database")
        await db.loadasync()

        # Load modules
        await bot.add_cog(AdminCommands(bot))
        await bot.add_cog(Music(bot))
        await bot.add_cog(Permissions(bot))
        # Load permission checker
        bot.add_check(bot.get_cog('Permissions').has_permission)

    def version(self):
        return version
