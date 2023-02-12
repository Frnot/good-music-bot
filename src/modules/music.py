import asyncio
import logging
import os
import subprocess
from time import time

import discord
from discord import Embed
from discord.ext import commands
import wavelink

import utils.rng
import utils.general

log = logging.getLogger(__name__)

# TODO: add seekability
# TODO: add guild independant queues
# TODO: add playlist support
# TODO: add remove command to clear certain elements from queue


class Music(commands.Cog, name='Music'):
    def __init__(self, bot):
        self.bot = bot
        self.songqueue = PseudoQueue()

        # Start Lavalink
        subprocess.Popen(["java", "-jar", "Lavalink.jar"], cwd="Lavalink")
        # Connect to Lavalink
        bot.loop.create_task(self.connect_nodes())

        log.info(f"Registered Cog: {self.qualified_name}")


    async def connect_nodes(self):
        """Connect to our Lavalink nodes."""
        await self.bot.wait_until_ready()
        # TODO add loop to retry here
        await asyncio.sleep(3)
        await wavelink.NodePool.create_node(
            bot = self.bot,
            host = "localhost",
            port = 2333,
            password = os.getenv("Lavalink_Password") )


    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a node has finished connecting."""
        log.info(f'Lavalink Node: <{node.identifier}> is ready!')



    ##### Commands #####
    @commands.command()
    async def play(self, ctx, *, query, queuetop=False):
        """Streams from a url (doesn't predownload)"""

        vc: wavelink.Player = ctx.voice_client

        # TODO: better regex for url matching
        if "http" in query:
            track = (await vc.node.get_tracks(query=query, cls=wavelink.Track))[0]
        else:
            track = await wavelink.YouTubeTrack.search(query=query, return_first=True)

        track.requester = ctx.author


        if queuetop:
            queue_pos = self.songqueue.put_top(track)
        else:
            queue_pos = self.songqueue.put(track)

        if ctx.voice_client.is_playing():
            msg = Embed(
                title = f"Track queued - Position {queue_pos}",
                description = track.title,
                url = track.uri,
                color = utils.rng.random_color()
            ).set_image(url=track.thumbnail)
            await ctx.send(embed=msg)

        else:
            while not self.songqueue.empty():
                track = self.songqueue.get()
                try:
                    await vc.play(track)
                except Exception as e:
                    log.info(f"Encountered error:{e}")
                await self.np(ctx)

                while ctx.voice_client.is_playing():
                    await asyncio.sleep(0.1)


    @commands.command()
    async def playnext(self, ctx, *, url):
        """Adds song to top of play queue"""
        await self.play(ctx, url=url, queuetop=True)

        #TODO accept queuenumber as argument to reorder queue


    @commands.command()
    async def np(self, ctx):
        if ctx.voice_client.is_playing():
            track = ctx.voice_client.source

            desc = f"[{track.title}]({track.uri})\n\n"
            if track.requester:
                desc += f"Requested by: {track.requester.mention}"
            if (position := ctx.voice_client.position) != track.duration:
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
    async def clear(self, ctx):
        self.songqueue.clear()
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()
        self.songqueue.clear()
        await utils.general.send_confirmation(ctx)


    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect(cls=wavelink.Player)
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")


    
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
            if vc := member.guild.voice_client:
                if not vc.is_connected():
                    self.songqueue.clear()
                elif not len(vc.channel.members) > 1:
                    await vc.disconnect()
                    self.songqueue.clear()



class PseudoQueue:
    def __init__(self):
        self.list = []
        self.inflight = None

    def get(self):
        self.inflight = self.list[0]
        del self.list[0]
        return self.inflight

    def pop(self, n):
        if not n < len(self.list):
            raise IndexError
        self.list = self.list[n:]
            

    def put(self, item):
        self.list.append(item)
        return len(self.list)

    def put_top(self, item):
        self.list.insert(0, item)
        return 1

    def clear(self):
        self.list.clear()
        self.inflight = None

    def show(self):
        return self.list.copy()

    def empty(self):
        return not self.list
