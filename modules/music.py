import discord
from discord.ext import commands
import asyncio
import math
import utils.admin
import utils.rng
import utils.general
import logging
log = logging.getLogger(__name__)


class Cog(commands.Cog, name='Prefix'):
    def __init__(self, bot):
        log.info(f"Registered Cog: {self.qualified_name}")




    ##### Commands #####

    @commands.command()
    @commands.check(utils.admin.is_server_owner)
    async def prefix(self, ctx, new_prefix=None):
        if new_prefix is None:
            current_prefix = await self.get(ctx.guild.id)
            await ctx.send(f"Command prefix: `{current_prefix}`")
            return
        elif new_prefix == "reset":
            log.info(f"Removing custom command prefix for guild '{ctx.guild.name}'")
            await self.remove(ctx.guild.id)
        else:
            log.info(f"Changing custom command prefix for guild '{ctx.guild.name}'")
            await self.add_or_update(ctx.guild.id, new_prefix)
        
        new_prefix = await self.get(ctx.guild.id)
        await ctx.send(f"Command prefix for {ctx.guild.name} is now `{new_prefix}`")

    @prefix.error
    async def prefix_error(self, ctx, exception):
        await ctx.send(f"error: {exception}")




    ##### Model #####

    async def get(self, guild_id):
        prefix = await self.prefixes.get(guild_id)
        if prefix is None:
            await self.add_or_update(guild_id, self.default_prefix)
            prefix = await self.prefixes.get(guild_id)
        return prefix


    async def add_or_update(self, guild_id, new_prefix):
        await self.prefixes.add_or_update(guild_id, new_prefix)


    async def remove(self, guild_id):
        prefix = await self.prefixes.get(guild_id)
        if prefix is not None:
            await self.prefixes.remove(guild_id)