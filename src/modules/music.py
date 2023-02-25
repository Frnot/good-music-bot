import asyncio
import logging
import math
import os
import re
import subprocess

import discord
import wavelink
from discord import Embed
from discord.ext import commands

import utils.general
import utils.rng
from modules.permissions import Permissions

log = logging.getLogger(__name__)

# todo: dont make undo action expire upon new queue action 
# (send each track obj pointer to its respective undo view)


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


    @commands.Cog.listener()
    async def on_wavelink_track_start(self, vc, track):
        await self.np(vc.spawn_ctx)


    @commands.Cog.listener()
    async def on_wavelink_track_end(self, vc, track, reason):
        if not vc.queue.is_empty():
            new_track = vc.queue.pop()
            await vc.play(new_track)
        else:
            vc.spawn_ctx = None
            await vc.stop()


    ##### Commands #####
    @commands.command()
    async def play(self, ctx, *, request, queuetop=False):
        """Streams from a url (doesn't predownload)"""

        vc: Player = ctx.voice_client
        queuetracks: function = vc.queue.put_top if queuetop else vc.queue.put

        if re.match(r'https?://(?:www\.)?.+', request):
            try:
                result = await vc.node.get_playlist(identifier=request, cls=wavelink.YouTubePlaylist)
            except wavelink.LavalinkException:
                result = (await vc.node.get_tracks(query=request, cls=wavelink.YouTubeTrack))[0]
        else:
            result = (await vc.node.get_tracks(query=f"ytsearch:{request}", cls=wavelink.YouTubeTrack))[0]

        if vc.old_undo_view:
            await vc.old_undo_view.expire()
            vc.old_undo_view = None

        if isinstance(result, wavelink.YouTubePlaylist):
            playlist = result
            for track in playlist.tracks:
                track.requester = ctx.author 
            queuetracks(playlist.tracks)

            embed = Embed(
                title = f"Queued playlist",
                description = playlist.name,
                color = utils.rng.random_color()
            )
            view = Undo(undo_func=vc.queue.undo,
                        requester_id=ctx.author.id)
            view.message = await ctx.send(embed=embed, view=view)
            vc.old_undo_view = view

        else:
            track = result
            track.requester = ctx.author
            queue_pos = queuetracks(track)

            if vc.is_playing():
                embed = Embed(
                    title = f"Track queued - Position {queue_pos}",
                    description = track.title,
                    url = track.uri,
                    color = utils.rng.random_color()
                )
                embed.set_thumbnail(url=result.thumbnail)
                view = Undo(undo_func=vc.queue.undo,
                            requester_id=ctx.author.id)
                view.message = await ctx.send(embed=embed, view=view)
                vc.old_undo_view = view

        # If bot isn't playing, process queue
        if not vc.is_playing() and not vc.spawn_ctx:
            vc.spawn_ctx = ctx
            track = vc.queue.pop()
            await vc.play(track)



    @commands.command()
    async def playnext(self, ctx, *, request):
        """Adds song to top of play queue"""
        await self.play(ctx, request=request, queuetop=True)


    @commands.command()
    async def np(self, ctx):
        """Shows info of currently playing track"""

        vc: Player = ctx.voice_client
        if vc.old_np_view:
            await vc.old_np_view.expire()

        if vc.is_playing():
            track = vc.source

            embed = Embed(
                title = f"Now Playing",
                description = f"[{track.title}]({track.uri})\n",
                color = utils.rng.random_color()
            )
            if track.requester:
                embed.add_field(name="Requested by:", value=track.requester.mention, inline=False)
            if vc.position == track.duration:
                position = f"\n{utils.general.sec_to_minsec(0)} / {utils.general.sec_to_minsec(int(track.duration))}"
                time_remaining = track.duration
            else:
                position = f"\n{utils.general.sec_to_minsec(int(vc.position))} / {utils.general.sec_to_minsec(int(track.duration))}"
                time_remaining = track.duration - vc.position
            embed.add_field(name="Position", value=position, inline=False)
            if hasattr(track, "thumbnail"):
                embed.set_thumbnail(url=track.thumbnail)

            view = NowPlaying(ctx=ctx, 
                              restart_func=self.restart, 
                              skip_func=self.skip, 
                              timeout=time_remaining)
            view.message = await ctx.send(embed=embed, view=view)
            vc.old_np_view = view

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
                await ctx.author.voice.channel.connect(cls=Player)
                discord.VoiceChannel.connect
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
    @np.error
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
        if vc := member.guild.voice_client: # Bot is/was connected to vc
            if after.channel is None or after.channel is not vc.channel: # User disconnected or left
                # Bot was forcefully disconnected or Bot is the only user connected to the vc
                if member.id == self.bot.user.id or not (len(vc.channel.members) > 1): 
                    await vc.old_np_view.expire()
                    await vc.disconnect()



class Player(wavelink.Player):
    def __init__(self, client, channel):
        super().__init__(client, channel)

        self.queue = PseudoQueue()
        self.spawn_ctx = None
        self.old_np_view = None
        self.old_undo_view = None



class ExpiringView(discord.ui.View):
    """Expiring views will disable all childen upon calling expire()"""
    def __init__(self, track_list, *, timeout = 30):
        super().__init__(timeout=timeout)

    async def on_timeout(self):
        await self.expire()

    async def expire(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)
        self.stop()



class GatedView(ExpiringView):
    """Gated views check for user permission before allowing interactions"""
    async def interaction_check(self, interaction: discord.Interaction):
        banned = await Permissions.query_banlist(interaction.user.id)
        in_channel = interaction.user.voice.channel == interaction.guild.voice_client.channel if interaction.user.voice else False

        if not banned and in_channel:
            return True
        elif banned:
            await interaction.response.send_message("Fuck you!", ephemeral=True, delete_after=10)
        elif not in_channel:
            await interaction.response.send_message("You must be in the voice channel to perform that action", ephemeral=True, delete_after=10)
        return False



class TrackList(GatedView):
    """discord.py view for tracklist queue"""
    def __init__(self, track_list, *, timeout = 30):
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


    def generate_embed(self, page):
        start_idx = page*self.pagesize
        tracks = self.tracklist[start_idx:start_idx+self.pagesize]
        
        index, title, requester = "", "", ""
        for i,track in enumerate(tracks, start=1):
            index += f"{start_idx+i}\n"
            title += f"[{track.title[:42]}]({track.uri})\n"
            requester += f"{track.requester.mention}\n"

        embed = Embed(title = f"Queued tracks: {page+1} / {self.pagecount}",color = utils.rng.random_color())
        embed.add_field(name="#", value = index)
        embed.add_field(name="Track", value = title)
        embed.add_field(name="Requested by", value = requester)

        return embed



class NowPlaying(GatedView):
    """discord.py view to display durrently playing track"""
    def __init__(self, ctx, restart_func, skip_func, *, timeout = 10):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.restart_func = restart_func
        self.skip_func = skip_func


    @discord.ui.button(label='Restart', custom_id="restart", style=discord.ButtonStyle.grey)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.restart_func(self.ctx, confirm=False)

        track = interaction.guild.voice_client.source
        self.timeout = track.duration

        position = f"\n{utils.general.sec_to_minsec(0)} / {utils.general.sec_to_minsec(int(track.duration))} (restarted)"
        field_idx = next(i for i,x in enumerate(interaction.message.embeds[0].fields) if x.name == "Position")
        embed = interaction.message.embeds[0].set_field_at(field_idx, name="Position", value=position)
        
        await interaction.response.edit_message(embed=embed)


    @discord.ui.button(label='Skip', custom_id="skip", style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.skip_func(self.ctx, confirm=False)
        button.style = discord.ButtonStyle.red
        await interaction.response.edit_message(view=self)
        await self.expire()



class Undo(ExpiringView):
    """discord.py view for undo button"""
    def __init__(self, *, undo_func, requester_id, timeout = 30):
        super().__init__(timeout=timeout)
        self.undo_func = undo_func
        self.requester_id = requester_id

    
    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("You did not queue this item.", ephemeral=True, delete_after=10)
            return False
        else:
            return True


    @discord.ui.button(label='Undo', style=discord.ButtonStyle.grey)
    async def undo(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.style = discord.ButtonStyle.red
        await interaction.response.edit_message(view=self)
        self.undo_func()



class PseudoQueue:
    __slots__ = ("list","mru")

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
        self.mru = (0, len(self.list))
        try: # item is iterable
            self.list.extend(item)
        except:
            self.list.append(item)
        return len(self.list)


    def put_top(self, item) -> int:
        try: # item is iterable
            self.mru = (len(item), None)
            item.extend(self.list)
            self.list = item
        except:
            self.mru = (1, None)
            self.list.insert(0, item)
        return 1

    def clear(self):
        self.list.clear()

    def remove(self, idx):
        del self.list[int(idx)-1]

    def undo(self):
        self.list = self.list[self.mru[0]:self.mru[1]]
        self.mru = None

    def show(self):
        return self.list.copy()

    def is_empty(self):
        return not self.list
