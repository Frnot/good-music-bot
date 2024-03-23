import logging

import discord
import wavelink
from discord import Embed
from discord.ext import commands
from sqlalchemy.orm import mapped_column
from sqlalchemy import Integer, String

from utils import db
import utils.general
from modules.music import Player

log = logging.getLogger(__name__)


class Favorite_Song(commands.Cog, name='Favorite Song'):
    def __init__(self, bot):
        self.bot = bot
        log.info(f"Registered Cog: {self.qualified_name}")


    #@commands.is_owner()
    @commands.group(pass_context=True, invoke_without_command=True)
    async def favorite(self, ctx):
        usage = """```
favorite add <@User> [song url]
favorite remove <@User>
favorite list```"""
        await ctx.send(usage)


    #@commands.is_owner()
    @favorite.group(pass_context=True)
    async def add(self, ctx, user: discord.User, url):
        track = (await wavelink.Playable.search(url))[0]
        favorite = FavoriteSong(id=user.id, song=track.uri)
        prev_favorite = await db.query(FavoriteSong, user.id)
        if prev_favorite:
            await db.delete_row(FavoriteSong, user.id)
            await db.insert_row(favorite)
            await ctx.send(f"Updated {user.name}'s favorite song from <{prev_favorite.song}> to <{track.uri}>")
        else:
            await db.insert_row(favorite)
            await ctx.send(f"Added <{track.uri}> as {user.name}'s favorite song")


    #@commands.is_owner()
    @favorite.group(pass_context=True)
    async def remove(self, ctx, user: discord.User):
        prev_favorite = await db.query(FavoriteSong, user.id)
        if prev_favorite:
            await db.delete_row(FavoriteSong, user.id)
            await utils.general.send_confirmation(ctx)
        else:
            await ctx.send(f"User did not have a favorite song")


    #@commands.is_owner()
    @favorite.group(pass_context=True, aliases=["list"])
    async def show(self, ctx):
        """Show all users favorites saved in DB"""
        all_favorites = await db.query_all(FavoriteSong)
        if all_favorites:
            favorite = [f"<@{e.id}> : <{e.song}>" for e in all_favorites]
            await ctx.send("\n".join(favorite))
        else:
            await ctx.send("Nobody has a favorite song")



    @favorite.error
    @add.error
    @remove.error
    @show.error
    async def error(self, ctx, exception):
        log.debug(exception)
        if isinstance(exception, commands.NotOwner):
            await ctx.send("Fuck you!")
        elif isinstance(exception, commands.MissingRequiredArgument):
            await ctx.send("Error: missing a required argument")
        else:
            await ctx.send(exception)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Automatically play someone's favorite song when they join the call"""
        if not after.channel or member.id == self.bot.user.id: # if user disconnected or we joined
            return
        if before.channel == after.channel: # state update
            return
        if player := member.guild.voice_client: 
            if after.channel != player.channel: # if bot is in a channel but the user joined a different one
                return
        else:
            player = await after.channel.connect(cls=Player)

        favorite = await db.query(FavoriteSong, member.id)
        if favorite:
            if player.playing:
                if player.current.uri == favorite.song:
                    return
                await player.playnow(favorite.song, self.bot.user, save_current=True)
            else:
                track = (await wavelink.Playable.search(favorite.song))[0]
                track.requester = self.bot.user
                await player.play(track)


class FavoriteSong(db.Base):
    __tablename__ = "users_favorite_songs"

    id   = mapped_column(Integer, primary_key=True)
    song = mapped_column(String)