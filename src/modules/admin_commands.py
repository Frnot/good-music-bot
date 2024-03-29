import logging
import os
import sys

import discord
import discord.utils
from discord import Embed
from discord.ext import commands

import bot_main
import utils.general

log = logging.getLogger(__name__)

restart = False

class AdminCommands(commands.Cog, name='Admin Commands'):
    def __init__(self, bot):
        self.bot: bot_main.Bot = bot
        log.info(f"Registered Cog: {self.qualified_name}")


    @commands.command()
    @commands.is_owner()
    async def invite(self, ctx):
        """Generate invite link for bot"""
        permissions = discord.Permissions(1099243192305)
        invite_link = discord.utils.oauth_url(self.bot.user.id, permissions=permissions)
        log.info(f"Recieved invite command in guild {ctx.guild.name}")
        await ctx.send(invite_link)


    # Leave server
    @commands.command()
    @commands.is_owner()
    async def leave(self, ctx, guildid=None):
        """Leave server"""
        if not guildid:
            log.info(f"Recieved leave command in guild {ctx.guild.name}")
            await utils.general.send_confirmation(ctx)
            await ctx.guild.leave()
        else:
            if guild := await self.bot.fetch_guild(guildid):
                await utils.general.send_confirmation(ctx)
                await guild.leave()
            else:
                await ctx.send(f"Cannot find guild '{guildid}'")


    @commands.command()
    @commands.is_owner()
    async def servers(self, ctx):
        """Prints all guilds bot is a member of"""
        msg = ""
        for guild in self.bot.guilds:
            msg += f"{guild.name} - {guild.id} - owner: {guild.owner.mention}\n"
        embed = Embed(
            title = f"Guild membership:",
            description = msg
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def perms(self, ctx):
        await ctx.send(ctx.bot_permissions.value)

    # Shutdown
    @commands.command()
    @commands.is_owner()
    async def die(self, ctx):
        """Shutdown"""
        log.info("Received shutdown command")
        await utils.general.send_confirmation(ctx)
        await ctx.bot.close()


    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx):
        """Restart the bot without updating"""
        global restart
        restart = True
        log.info("Restarting")
        await utils.general.send_confirmation(ctx)
        await ctx.bot.close()
    

    @commands.command()
    @commands.is_owner()
    async def update(self, ctx):
        """Install updates from git"""
        global restart
        restart = True

        async with ctx.channel.typing():
            await ctx.send("Updating...")
            await self.status(ctx, "streaming", "update")
            log.info("Running Updates")

            log.debug("executing command: git stash")
            os.system("git stash")

            log.debug("executing command: git pull")
            os.system("git pull")

            if sys.platform.startswith('linux'):
                log.debug(f"executing command: chmod +x -R scripts")
                os.system("chmod +x -R scripts")

            log.debug(f"executing command: \"{sys.executable}\" -m pip install .")
            os.system(f"\"{sys.executable}\" -m pip install .")

            log.info("Updates done. Restarting main process")

        await ctx.bot.close()


    @commands.command()
    @commands.is_owner()
    async def status(self, ctx, action: utils.general.to_lower, status = None):
        """Set Status"""
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
        else:
            actiontype = discord.ActivityType.playing

        await self.bot.change_presence(activity=discord.Activity(name=status, type=actiontype))

        log.info(f"setting status to {actiontype.name} `{status}`")
        await utils.general.send_confirmation(ctx)


    @invite.error
    @leave.error
    @servers.error
    @die.error
    @reload.error
    @update.error
    @status.error
    async def error(self, ctx, exception):
        log.debug(exception)
        if isinstance(exception, commands.NotOwner):
            await ctx.send("Fuck you!")
        elif isinstance(exception, commands.MissingRequiredArgument):
            await ctx.send("Error: command missing required argument")
        else:
            await ctx.send(exception)
