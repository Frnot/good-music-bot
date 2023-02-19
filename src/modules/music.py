import asyncio
import logging
import math
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


class Music(commands.Cog, name='Music'):
    def __init__(self, bot):
        self.bot = bot

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
        queuetrack: function = vc.queue.put_top if queuetop else vc.queue.put

        if isinstance(request, wavelink.YouTubePlaylist):
            for track in request.tracks:
                track.requester = ctx.author 
            queuetrack(request.tracks)

            msg = Embed(
                title = f"Queued playlist",
                description = request.name,
                color = utils.rng.random_color()
            )
            await ctx.send(embed=msg)
        else:
            request.requester = ctx.author
            queue_pos = queuetrack(request)

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
            try:
                while not vc.queue.empty():
                    track = vc.queue.pop()
                    try:
                        await vc.play(track)
                    except Exception as e:
                        log.info(f"Encountered error:{e}")
                        continue
                    await self.np(ctx)

                    while ctx.voice_client.is_playing():
                        await asyncio.sleep(0.1)
            except AttributeError: # voice_client annihilation when disconnected
                pass
                    


    @commands.command()
    async def playnext(self, ctx, *, request: typing.Union[wavelink.YouTubeTrack, wavelink.YouTubePlaylist, wavelink.SoundCloudTrack]):
        """Adds song to top of play queue"""
        await self.play(ctx, request=request, queuetop=True)


    @commands.command()
    async def np(self, ctx):
        if hasattr(ctx.voice_client, "old_np_view"):
            await ctx.voice_client.old_np_view.expire()

        if ctx.voice_client.is_playing():
            track = ctx.voice_client.source

            embed = Embed(
                title = f"Now Playing",
                description = f"[{track.title}]({track.uri})\n",
                color = utils.rng.random_color()
            )
            if track.requester:
                embed.add_field(name="Requested by:", value=track.requester.mention, inline=False)
            if ctx.voice_client.position == track.duration:
                position = f"\n{utils.general.sec_to_minsec(0)} / {utils.general.sec_to_minsec(int(track.duration))}"
                time_remaining = track.duration
            else:
                position = f"\n{utils.general.sec_to_minsec(int(ctx.voice_client.position))} / {utils.general.sec_to_minsec(int(track.duration))}"
                time_remaining = track.duration - ctx.voice_client.position
            embed.add_field(name="Position", value=position, inline=False)
            if hasattr(track, "thumbnail"):
                embed.set_thumbnail(url=track.thumbnail)

            view = NowPlaying(ctx=ctx, 
                              restart_func=self.restart, 
                              skip_func=self.skip, 
                              timeout=time_remaining)
            view.message = await ctx.send(embed=embed, view=view)
            ctx.voice_client.old_np_view = view

        else:
            await ctx.send("Nothing is playing")


    @commands.command()
    async def queue(self, ctx):
        track_list = ctx.voice_client.queue.show()
        if not track_list:
            msg = Embed(
                title = f"Queue is empty",
                color = utils.rng.random_color()
            )
            await ctx.send(embed=msg)
        else:
            await TrackList(track_list).send(ctx)


    @commands.command()
    async def skip(self, ctx, num=None, confirm=True):
        if not num:
            await ctx.voice_client.stop()
            if confirm:
                await utils.general.send_confirmation(ctx)
        else:
            try:
                ctx.voice_client.queue.pop(int(num)-1)
                await ctx.voice_client.stop()
                if confirm:
                    await utils.general.send_confirmation(ctx)
            except:
                await ctx.send("Error: please enter a valid index number")


    @commands.command()
    async def remove(self, ctx, idx, confirm=True):
        try:
            ctx.voice_client.queue.remove(idx)
            if confirm:
                await utils.general.send_confirmation(ctx)
        except (IndexError, TypeError) as e:
            await ctx.send(e)
            await ctx.send("Enter a valid index")


    @commands.command()
    async def clear(self, ctx):
        ctx.voice_client.queue.clear()
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def seek(self, ctx, time, confirm=True):
        try:
            seconds = utils.general.timestr_to_secs(time)
            seektime = seconds*1000

            if seconds > ctx.voice_client.source.duration:
                raise ValueError

            log.debug(f"seeking to {seconds} seconds")
            await ctx.voice_client.seek(seektime)
            if confirm:
                await utils.general.send_confirmation(ctx)
        except ValueError:
            await ctx.send("Error: invalid timestamp")


    @commands.command()
    async def restart(self, ctx, confirm=True):
        """seeks to beginning of song"""
        await self.seek(ctx, "0", confirm=confirm)


    @commands.command()
    async def stop(self, ctx, confirm=True):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()
        if confirm:
            await utils.general.send_confirmation(ctx)


    @play.before_invoke
    @playnext.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect(cls=wavelink.Player)
                ctx.voice_client.queue = PseudoQueue() # override default queue instance variable
            else:
                raise commands.CommandError("You are not connected to a voice channel.")


    @np.before_invoke
    @queue.before_invoke
    @skip.before_invoke
    @remove.before_invoke
    @clear.before_invoke
    @seek.before_invoke
    @restart.before_invoke
    @stop.before_invoke
    async def check_voice(self, ctx):
        if ctx.voice_client is None:
            raise commands.CommandError("Bot is not connected to a voice channel.")


    
    @play.error
    @playnext.error
    @queue.error
    @skip.error
    @seek.error
    @remove.error
    @clear.error
    async def error(self, ctx, exception):
        #if isinstance(exception, youtube_dl.utils.DownloadError) or isinstance(exception, youtube_dl.utils.ExtractorError):
        #    await ctx.send("Error: video unavailable")
        #else:
        await ctx.send(exception)


    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Disconnects bot from voice channel if no users are connected and clears queue if bot is disconnected"""
        # TODO check for correct channel
        if vc := member.guild.voice_client: # Bot is connected to vc
            if after.channel is None or after.channel is not vc.channel: # User disconnected or left
                if not (len(vc.channel.members) > 1): # Bot is the only user connected to the vc
                    await vc.disconnect()
                    


class TrackList(discord.ui.View):
    """discord.py view for tracklist queue"""
    def __init__(self, track_list, *, timeout = 5):
        super().__init__(timeout=timeout)
        self.index = 0
        self.tracklist = track_list
        self.pagesize = 10
        self.pagecount = math.ceil(len(track_list) / self.pagesize)

        if len(track_list) <= self.pagesize:
            self.clear_items()


    @discord.ui.button(label='Previous', style=discord.ButtonStyle.grey, disabled=True)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self.children[1].disabled = False
        if self.index == 0:
            button.disabled = True
        await interaction.response.edit_message(view=self, embed=self.generate_embed(self.index))


    @discord.ui.button(label='Next', style=discord.ButtonStyle.grey)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self.children[0].disabled = False
        if self.index == self.pagecount - 1:
            button.disabled = True
        await interaction.response.edit_message(view=self, embed=self.generate_embed(self.index))

    
    async def send(self, ctx):
        embed = self.generate_embed(0)
        self.message = await ctx.send(embed=embed, view=self)


    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    
    def generate_embed(self, page):
        start_idx = page*self.pagesize
        tracks = self.tracklist[start_idx:start_idx+self.pagesize]
        
        index, title, requester = "", "", ""
        for i,track in enumerate(tracks):
            index += f"{start_idx+i+1}\n"
            title += f"[{track.title[:42]}]({track.uri})\n"
            requester += f"{track.requester.mention}\n"

        embed = Embed(title = f"Queued tracks: {page+1} / {self.pagecount}",color = utils.rng.random_color())
        embed.add_field(name="#", value = index)
        embed.add_field(name="track", value = title)
        embed.add_field(name="requested by", value = requester)

        return embed



class NowPlaying(discord.ui.View):
    """discord.py view to display durrently playing track"""
    def __init__(self, ctx, restart_func, skip_func, *, timeout = 10):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.restart = restart_func
        self.skip = skip_func


    @discord.ui.button(label='Restart', custom_id="restart", style=discord.ButtonStyle.grey)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.restart(self.ctx, confirm=False)

        track = interaction.guild.voice_client.source
        self.timeout = track.duration

        position = f"\n{utils.general.sec_to_minsec(0)} / {utils.general.sec_to_minsec(int(track.duration))}"
        field_idx = next(i for i,x in enumerate(interaction.message.embeds[0].fields) if x.name == "Position")
        embed = interaction.message.embeds[0].set_field_at(field_idx, name="Position", value=position)
        
        await interaction.response.edit_message(embed=embed)


    @discord.ui.button(label='Skip', custom_id="skip", style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.skip(self.ctx, confirm=False)
        button.style = discord.ButtonStyle.red
        await interaction.response.edit_message(view=self)
        await self.expire()


    async def on_timeout(self):
        await self.expire()


    async def expire(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)
        self.stop()



class PseudoQueue:
    __slots__ = ("list",)

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
