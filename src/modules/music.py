import asyncio
import logging
import os
import subprocess
import typing
from time import time

import discord
import wavelink
from discord import Embed
from discord.ext import commands

import utils.general
import utils.rng

log = logging.getLogger(__name__)

# TODO: add guild independant queues
# TODO: add playlist support


class Music(commands.Cog, name='Music'):
    def __init__(self, bot):
        self.bot = bot
        self.songqueue = PseudoQueue()

        # Start Lavalink
        log.info("Starting Lavalink Server")
        #TODO: (noncritical) dont try to reopen on update
        subprocess.Popen(["java", "-jar", "Lavalink.jar"], cwd="Lavalink")
        # Connect to Lavalink
        bot.loop.create_task(self.connect_nodes())

        log.info(f"Registered Cog: {self.qualified_name}")


    async def connect_nodes(self):
        """Connect to our Lavalink nodes."""
        await self.bot.wait_until_ready()

        log.debug("Attempting to connect to Lavalink Server")
        connection_attempt = 1
        while connection_attempt < 5:
            result = await wavelink.NodePool.create_node(
                bot = self.bot,
                host = "localhost",
                port = 2333,
                password = os.getenv("Lavalink_Password") )

            if result.is_connected():
                break
            log.debug("connection failed. reattempting...")
            await asyncio.sleep(0.5)
            connection_attempt += 1
        else:
            log.error("Failed to connect to Lavalink server")


    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a node has finished connecting."""
        log.info(f'Lavalink Node: <{node.identifier}> is ready!')



    ##### Commands #####
    @commands.command()
    async def play(self, ctx, *, request: typing.Union[wavelink.YouTubeTrack, wavelink.YouTubePlaylist, wavelink.SoundCloudTrack], queuetop=False):
        """Streams from a url (doesn't predownload)"""

        vc: wavelink.Player = ctx.voice_client
        queue: function = self.songqueue.put_top if queuetop else self.songqueue.put

        if isinstance(request, wavelink.YouTubePlaylist):
            for track in request.tracks:
                track.requester = ctx.author 
            queue(request.tracks)

            msg = Embed(
                title = f"Queued playlist",
                description = request.name,
                color = utils.rng.random_color()
            )
            await ctx.send(embed=msg)
        else:
            request.requester = ctx.author
            queue_pos = queue(request)

            if ctx.voice_client.is_playing():
                msg = Embed(
                    title = f"Track queued - Position {queue_pos}",
                    description = request.title,
                    url = request.uri,
                    color = utils.rng.random_color()
                )
                if hasattr(request, "thumbnail"):
                    msg.set_image(url=request.thumbnail)
                await ctx.send(embed=msg)

        # If bot isn't playing, process queue
        if not ctx.voice_client.is_playing():
            while not self.songqueue.empty():
                track = self.songqueue.pop()
                try:
                    await vc.play(track)
                except Exception as e:
                    log.info(f"Encountered error:{e}")
                await self.np(ctx)

                try:
                    while ctx.voice_client.is_playing():
                        await asyncio.sleep(0.1)
                except AttributeError: # voice client annihilation when forcefully disconnected
                    pass


    @commands.command()
    async def playnext(self, ctx, *, request: typing.Union[wavelink.YouTubeTrack, wavelink.YouTubePlaylist, wavelink.SoundCloudTrack]):
        """Adds song to top of play queue"""
        await self.play(ctx, request=request, queuetop=True)


    @commands.command()
    async def np(self, ctx):
        if ctx.voice_client.is_playing():
            track = ctx.voice_client.source

            desc = f"[{track.title}]({track.uri})\n\n"
            if track.requester:
                desc += f"Requested by: {track.requester.mention}"
            if (position := ctx.voice_client.position) == track.duration:
                desc += f"\nLength: {utils.general.sec_to_minsec(int(track.duration))}"
            else:
                desc += f"\n{utils.general.sec_to_minsec(int(position))} / {utils.general.sec_to_minsec(int(track.duration))}"

            msg = Embed(
                title = f"Now Playing",
                description = desc,
                color = utils.rng.random_color()
            )
            if hasattr(track, "thumbnail"):
                msg.set_thumbnail(url=track.thumbnail)

            await ctx.send(embed=msg)
        else:
            await ctx.send("Nothing is playing")


    @commands.command()
    async def queue(self, ctx):
        if sq:= self.songqueue.show():
            tracklist = ""
            for idx,track in enumerate(sq):
                tracklist += f"{idx+1} :  [{track.title}]({track.uri}) - {track.requester.mention}\n"
            msg = Embed(
                title = f"Queued tracks:",
                description = tracklist,
                color = utils.rng.random_color()
            )
        else:
            msg = Embed(
                title = f"Queue is empty",
                color = utils.rng.random_color()
            )
        await ctx.send(embed=msg)


    @commands.command()
    async def skip(self, ctx, num = None):
        if not num:
            await ctx.voice_client.stop()
            await utils.general.send_confirmation(ctx)
        else:
            try:
                self.songqueue.pop(int(num)-1)
                await ctx.voice_client.stop()
                await utils.general.send_confirmation(ctx)
            except:
                await ctx.send("Error: please enter a valid index number")


    @commands.command()
    async def remove(self, ctx, idx):
        try:
            self.songqueue.remove(idx)
            await utils.general.send_confirmation(ctx)
        except (IndexError, TypeError) as e:
            await ctx.send(e)
            await ctx.send("Enter a valid index")


    @commands.command()
    async def clear(self, ctx):
        self.songqueue.clear()
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def seek(self, ctx, time):
        try:
            seconds = utils.general.timestr_to_secs(time)
            seektime = seconds*1000

            if seconds > ctx.voice_client.source.duration:
                raise ValueError

            log.debug(f"seeking to {seconds} seconds")
            await ctx.voice_client.seek(seektime)
            await utils.general.send_confirmation(ctx)
        except:
            await ctx.send("Error: invalid timestamp")


    @commands.command()
    async def restart(self, ctx):
        """seeks to beginning of song"""
        await self.seek(ctx, "0")


    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()
        self.songqueue.clear()
        await utils.general.send_confirmation(ctx)


    @play.before_invoke
    @playnext.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect(cls=wavelink.Player)
            else:
                await ctx.send("You are not connected to a voice channel.")


    
    @play.error
    async def error(self, ctx, exception):
        #if isinstance(exception, youtube_dl.utils.DownloadError) or isinstance(exception, youtube_dl.utils.ExtractorError):
        #    await ctx.send("Error: video unavailable")
        #else:
        await ctx.send(exception)


    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Disconnects bot from voice channel if no users are connected and clears queue if bot is disconnected"""
        if after.channel is None:
            if member == self.bot.user:
                log.debug(f"Was forceflly disconnected from channel {after.channel}")
                self.songqueue.clear()
            elif vc := member.guild.voice_client and not len(vc.channel.members) > 1:
                log.debug(f"All users in channel {vc.channel} have disconnected. Bot will isconnecting.")
                await vc.disconnect()
                self.songqueue.clear()



class PseudoQueue:
    def __init__(self):
        self.list = []

    def pop(self, n=None):
        if n:
            if not n < len(self.list):
                raise IndexError
            element = self.list[n]
            self.list = self.list[n:]
            return element
        else:
            element = self.list[0]
            del self.list[0]
            return element

    def put(self, item) -> int:
        try:
            self.list.extend(item)
        except:
            self.list.append(item)
        return len(self.list)

    def put_top(self, item) -> int:
        try:
            item.extend(self.list)
            self.list = item
        except:
            self.list.insert(0, item)
        return 1

    def clear(self):
        self.list.clear()

    def remove(self, idx):
        del self.list[int(idx)-1]

    def show(self):
        return self.list.copy()

    def empty(self):
        return not self.list
