import asyncio
import logging
from queue import Queue

import discord
from discord import Embed
from discord.ext import commands
import youtube_dl

import utils.rng
import utils.general

log = logging.getLogger(__name__)

# TODO: leave chat when everyone leaves
# TODO: embed messages
# TODO: add "now playing"
# TODO:     add current place in track
# TODO: add seekability
# TODO: add guild independant queues
# TODO: add playlist support
# TODO: clear queue when disconnected



class Music(commands.Cog, name='Music'):
    def __init__(self, bot):
        self.bot = bot
        self.songqueue = PseudoQueue()
        log.info(f"Registered Cog: {self.qualified_name}")



    ##### Commands #####
    @commands.command()
    async def play(self, ctx, *, url, queuetop=False):
        """Streams from a url (doesn't predownload)"""

        track = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)

        if queuetop:
            queue_pos = self.songqueue.put_top(track)
        else:
            queue_pos = self.songqueue.put(track)

        if ctx.voice_client.is_playing():
            msg = Embed(
                title = f"Track queued - Position {queue_pos}",
                description = track.title,
                url = track.url,
                color = utils.rng.random_color()
            ).set_image(url=track.thumbnail)
            await ctx.send(embed=msg)

        else:
            while not self.songqueue.empty():
                track = self.songqueue.get()
                ctx.voice_client.play(track, after=lambda e: print(f'Player error: {e}') if e else None)

                msg = Embed(
                    title = "Now playing:",
                    description = track.title,
                    url = track.url,
                    color = utils.rng.random_color()
                ).set_thumbnail(url=track.thumbnail)
                await ctx.send(embed=msg)

                while ctx.voice_client.is_playing():
                    await asyncio.sleep(0.1)


    @commands.command()
    async def playnext(self, ctx, *, url):
        """Adds song to top of play queue"""

        await self.play(ctx, url=url, queuetop=True)

        #TODO accept queuenumber as argument to reorder queue


    @commands.command()
    async def queue(self, ctx):
        if sq:= self.songqueue.show():
            tracklist = ""
            for idx,track in enumerate(sq):
                tracklist += f"{idx+1} :  [{track.title}]({track.url})\n"
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
    async def skip(self, ctx):
        ctx.voice_client.stop()
        await utils.general.send_confirmation(ctx)


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



class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.streamurl = data.get('url')
        self.url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')


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
        return len(self.list)

    def put_top(self, item):
        self.list.insert(0, item)
        return 1

    def show(self):
        return self.list.copy()

    def empty(self):
        return not self.list