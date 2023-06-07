import logging

import discord
from discord.ext import commands
from sqlalchemy.orm import mapped_column
from sqlalchemy import Integer

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
        """Remove a user form whitelist, removing their ability to use this bot"""

        user_access = await self.query_whitelist(user.id)
        if not user_access:
            await ctx.send("User is already banned")
        else:
            await self.remove_from_whitelist(user.id)
            await utils.general.send_confirmation(ctx)


    @commands.command()
    @commands.is_owner()
    async def unban(self, ctx, user: discord.User):
        """Whitelist a user, giving them ability to use this bot"""

        user_access = await self.query_whitelist(user.id)
        if not user_access:
            await self.add_to_whitelist(user.id)
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
        if not await self.query_whitelist(ctx.author.id):
            raise UserIsBanned(f"{ctx.author.mention} eat shit!")
        else:
            return True


    async def add_to_whitelist(self, id):
        user = Whitelist(user_id=id)
        await db.insert_row(user)


    async def remove_from_whitelist(self, id):
        await db.delete_row(Whitelist, id)


    @classmethod
    async def query_whitelist(cls, id):            
        result = await db.query(Whitelist, id)
        return bool(result)



class Whitelist(db.Base):
    __tablename__ = "user_whitelist"

    user_id = mapped_column(Integer, primary_key=True)



class UserIsBanned(commands.CheckFailure):
    """Custom command exception"""
    pass
