import logging

import discord
from discord.ext import commands

import utils.general
from utils import db

log = logging.getLogger(__name__)

class Permissions(commands.Cog, name='Permissions'):
    def __init__(self, bot):
        self.bot = bot
        log.info(f"Registered Cog: {self.qualified_name}")


    @commands.command()
    @commands.is_owner()
    async def ban(self, ctx, user: discord.User):
        """Add a user to ban list, removing their ability to use this bot"""

        user_banned = await self.query_banlist(user.id)
        if user_banned:
            await ctx.send("User is already banned")
        else:
            await self.add_to_banlist(user.id)
            await utils.general.send_confirmation(ctx)


    @commands.command()
    @commands.is_owner()
    async def unban(self, ctx, user: discord.User):
        """Remove a user from ban list, returning their ability to use this bot"""

        user_banned = await self.query_banlist(user.id)
        if user_banned:
            await self.remove_from_banlist(user.id)
            await utils.general.send_confirmation(ctx)
        else:
            await ctx.send("User is not banned")


    @ban.error
    @unban.error
    async def error(self, ctx, exception):
        log.debug(exception)
        if isinstance(exception, commands.NotOwner):
            await ctx.send("Fuck you!")
        elif isinstance(exception, commands.MissingRequiredArgument):
            await ctx.send("Error: specify a user")
        else:
            await ctx.send(exception)


    async def has_permission(self, ctx):
        if await ctx.bot.is_owner(ctx.author): # anti-lockout
            return True
        if await self.query_banlist(ctx.author.id):
            raise UserIsBanned(f"{ctx.author.mention} eat shit!")
        else:
            return True


    async def add_to_banlist(self, id):
        await db.insert("banlist", [["user_id", id]])


    async def remove_from_banlist(self, id):
        await db.delete("banlist", ["user_id", id])


    async def query_banlist(self, id):
        try:
            if await db.select("user_id", "banlist", "user_id", id) is not None:
                return True
            else:
                return False
        except Exception as e:
            log.error(f"Error querying banlist database for id {id}")
            return None
        


class UserIsBanned(commands.CheckFailure):
    pass


async def can_interact(view, interaction):
    view.ctx.interaction = interaction
    banned = await view.ctx.bot.get_cog('Permissions').query_banlist(view.ctx.author.id)
    in_channel = view.ctx.author.voice.channel == view.ctx.voice_client.channel
    
    if not banned and in_channel:
        return True
    elif banned:
        await view.ctx.send("Fuck you!", ephemeral=True)
    elif not in_channel:
        await view.ctx.send("You must be in the voice channel to perform that action", ephemeral=True)
    return False
    