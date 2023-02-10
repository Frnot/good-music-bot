import os
import sys
import discord
from discord.ext import commands
import logging

import utils.general

log = logging.getLogger(__name__)

restart = False

class AdminCommands(commands.Cog, name='Admin Commands'):
    def __init__(self, bot):
        self.bot = bot
        log.info(f"Registered Cog: {self.qualified_name}")


    @commands.command()
    @commands.is_owner()
    async def invite(self, ctx):
        """Generate invite link for bot"""
        permission = 1071631556417
        invite_link = f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&scope=bot&permissions={permission}"
        log.info(f"Recieved invite command in guild {ctx.guild.name}")
        await ctx.send(invite_link)


    # Leave server
    @commands.command()
    @commands.is_owner()
    async def leave(self, ctx):
        log.info(f"Recieved leave command in guild {ctx.guild.name}")
        await utils.general.send_confirmation(ctx)
        await ctx.guild.leave()


    # Shutdown
    @commands.command()
    @commands.is_owner()
    async def die(self, ctx):
        log.info("Received shutdown command")
        await utils.general.send_confirmation(ctx)
        await ctx.bot.close()


    # Install Updates
    @commands.command()
    @commands.is_owner()
    async def update(self, ctx):
        global restart
        restart = True

        async with ctx.channel.typing():
            await ctx.send("Updating...")
            self.status(ctx, "streaming", "update")
            log.info("Running Updates")

            log.debug("executing command: git stash")
            os.system("git stash")

            log.debug("executing command: git pull")
            os.system("git pull")

            if sys.platform.startswith('linux'):
                log.debug(f"executing command: chmod +x -R ../scripts")
                os.system("chmod +x -R ../scripts")

            log.debug(f"executing command: \"{sys.executable}\" -m pip install ..")
            os.system(f"\"{sys.executable}\" -m pip install ..")

            log.info("Updates done. Restarting main process")

        await ctx.bot.close()


    # Set status
    @commands.command()
    @commands.is_owner()
    async def status(self, ctx, action: utils.general.to_lower, status = None):
        if action == "clear":
            actiontype = discord.ActivityType.playing
            status = f"v{self.bot.version()}"
        elif action == "playing":
            actiontype = discord.ActivityType.playing
        elif action == "streaming":
            actiontype = discord.ActivityType.streaming
        elif action in ("listening", "listening to"):
            actiontype = discord.ActivityType.listening
        elif action == "watching":
            actiontype = discord.ActivityType.watching
        elif action in ("competing", "competing in"):
            actiontype = discord.ActivityType.competing

        await self.bot.change_presence(activity=discord.Activity(name=status, type=actiontype))

        log.info(f"setting status to {actiontype.name} `{status}`")
        await utils.general.send_confirmation(ctx)


    @leave.error
    @die.error
    @update.error
    @status.error
    async def error(self, ctx, exception):
        log.debug(exception)
        if isinstance(exception, commands.NotOwner):
            await ctx.send("Fuck you!")
        elif isinstance(exception, commands.MissingRequiredArgument):
            await ctx.send("Error: command missing required argument")
        else:
            await ctx.send(f"Error: {exception}")
