import asyncio
import logging
from queue import Queue

import discord
from discord.ext import commands
import youtube_dl

import utils.rng
import utils.general

log = logging.getLogger(__name__)



class Music(commands.Cog, name='Music'):
    def __init__(self, bot):
        self.bot = bot
        self.songqueue = PseudoQueue()
        log.info(f"Registered Cog: {self.qualified_name}")



    ##### Commands #####
    @commands.command()
    async def play(self, ctx, *, url):
        """Streams from a url (doesn't predownload)"""

        track = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
        self.songqueue.put(track)
        if not ctx.voice_client.is_playing():
            while not self.songqueue.empty():
                track = self.songqueue.get()
                await ctx.send(f'Now playing: {track.title}')
                ctx.voice_client.play(track, after=lambda e: print(f'Player error: {e}') if e else None)

                while ctx.voice_client.is_playing():
                    await asyncio.sleep(0.1)
            await ctx.send("Queue is empty")
        else:
            await ctx.send(f'Queued track: {track.title}')
        

    @commands.command()
    async def queue(self, ctx):
        if sq:= self.songqueue.show():
            msg = ""
            for idx,element in enumerate(sq):
                msg += f"{idx}: {element.title}\n"
        else:
            msg = "Queue is empty"
        await ctx.send(msg)


    @commands.command()
    async def skip(self, ctx):
        """stop"""

        ctx.voice_client.stop()
        await utils.general.send_confirmation(ctx)
        # TODO: make operate on queue


    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")


    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()


    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        #elif ctx.voice_client.is_playing():
        #    ctx.voice_client.stop()



    ##### Model #####
    async def stream_track(self, ctx):
        while not self.songqueue.empty():
            track = self.songqueue.get()
            await ctx.send(f'Now playing: {track.title}')
            ctx.voice_client.play(track, after=lambda e: print(f'Player error: {e}') if e else None)

            while ctx.voice_client.is_playing():
                await asyncio.sleep(0.1)
        await ctx.send("Queue is empty")



class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


ytdl = youtube_dl.YoutubeDL({
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
})


ffmpeg_options = {
    'options': '-vn',
}


class PseudoQueue:
    def __init__(self):
        self.list = []

    def get(self):
        element = self.list[0]
        del self.list[0]
        return element

    def put(self, item):
        self.list.append(item)

    def show(self):
        return self.list.copy()

    def empty(self):
        return not self.list