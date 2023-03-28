import asyncio
import logging
import math
import os
import re
import subprocess
from collections import deque

import discord
import wavelink
from discord import Embed
from discord.ext import commands

import utils.general
import utils.rng
from modules.permissions import Permissions

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
        """Connect to the Lavalink nodes."""
        await self.bot.wait_until_ready()

        log.debug("Attempting to connect to Lavalink Server")
        node: wavelink.Node = wavelink.Node(uri='http://localhost:2333', password=os.getenv("Lavalink_Password"))
        await wavelink.NodePool.connect(client=self.bot, nodes=[node])


    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a node has finished connecting."""
        log.info(f'Lavalink Node: <{node.id}> is ready!')


    ####################
    ##### Commands #####
    ####################


    @commands.command()
    async def play(self, ctx, *, request, queuetop=False):
        """Streams from a url (doesn't predownload)"""
        embed, view = await ctx.voice_client.playadd(ctx, request, ctx.author, queuetop)
        if embed and view:
            view.messages.append(await ctx.send(embed=embed, view=view))


    @commands.command()
    async def playnext(self, ctx, *, request):
        """Adds song to top of play queue"""
        await self.play(ctx, request=request, queuetop=True)


    @commands.command()
    async def remove(self, ctx, idx):
        """Removes a song from queue based on index (1-based)"""
        if await ctx.voice_client.remove(idx):
            await utils.general.send_confirmation(ctx)


    @commands.command()
    async def clear(self, ctx):
        """Clears all tracks from queue"""
        ctx.voice_client.dequeue.clear()
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def skip(self, ctx, num=None):
        """Skip [num] tracks in queue.
        Will only skip current playing track by default"""
        if await ctx.voice_client.skip(num):
            await utils.general.send_confirmation(ctx)


    @commands.command()
    async def deskip(self, ctx):
        """Undoes the last skip operation"""
        if await ctx.voice_client.deskip():
            await utils.general.send_confirmation(ctx)


    @commands.command()
    async def seek(self, ctx, time):
        """Seeks to time in current track. mm:ss format"""
        await ctx.voice_client.seek(time)
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def restart(self, ctx):
        """Restarts the current track"""
        await ctx.voice_client.restart()
        await utils.general.send_confirmation(ctx)

    
    @commands.command()
    async def replay(self, ctx):
        """Replays the song that just played"""
        await ctx.voice_client.replay(ctx)
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice channel"""
        await ctx.voice_client.disconnect()
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def np(self, ctx):
        """Shows info of currently playing track"""
        await ctx.voice_client.status(ctx.channel)


    @commands.command()
    async def queue(self, ctx):
        """Shows all tracks that have been queued"""
        embed, view = await ctx.voice_client.showqueue(ctx.author)
        if view:
            view.messages.append(await ctx.send(embed=embed, view=view))
        else:
            await ctx.send(embed=embed)


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
    @deskip.before_invoke
    @remove.before_invoke
    @clear.before_invoke
    @seek.before_invoke
    @restart.before_invoke
    @replay.before_invoke
    @stop.before_invoke
    async def check_voice(self, ctx):
        if ctx.voice_client is None:
            raise commands.CommandError("Bot is not connected to a voice channel.")


    @play.error
    @playnext.error
    @np.error
    @queue.error
    @skip.error
    @deskip.error
    @seek.error
    @remove.error
    @restart.before_invoke
    @replay.before_invoke
    @clear.error
    async def error(self, ctx, exception):
        await ctx.send(exception)

    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Disconnects bot from voice channel if no users are connected and clears queue if bot is disconnected"""
        if vc := member.guild.voice_client: # Bot is/was connected to vc
            if after.channel is None or after.channel is not vc.channel: # User disconnected or left
                # Bot was forcefully disconnected or Bot is the only user connected to the vc
                if member.id == self.bot.user.id or not (len(vc.channel.members) > 1): 
                    await vc.disconnect()
                    await vc.expire_all_views()


    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        vc: Player = payload.player
        if vc.loop_track and payload.track.identifier == vc.loop_track.identifier:
            pass
        else:
            await vc.status(vc.spawn_ctx.channel)


    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        vc = payload.player
        # track doesn't have requester attribute, have to use vc.loop_track
        if vc.loop_track and payload.reason == "FINISHED":
            await vc.play(vc.loop_track)
            vc.last_track = new_track
        else:
            await vc.expire_stale_views() #TODO: put this after new track is started (for ratelimit)
                                            # have to keep track of status views so we dont expire new track view
            if vc.loop_track:
                vc.loop_track = None
            if vc.dequeue: # is not empty
                new_track = vc.dequeue.popleft()
                await vc.play(new_track)
                vc.last_track = new_track
            else:
                vc.spawn_ctx = None
                await vc.stop()
                await vc.expire_all_views()



class Player(wavelink.Player):
    """Each server will get its own unique Player object, 
    spawned on bot joining voice channel 
    and destroyed on bot leaving voice channel"""

    def __init__(self, client, channel):
        super().__init__(client, channel)

        self.dequeue = deque()
        self.status_view = None
        self.misc_views = []
        self.skipped_tracks = None
        self.loop_track = None
        self.last_track = None
        self.spawn_ctx = None
        self.pagesize = 10


    async def disconnect(self):
        await super().disconnect()
        await self.expire_all_views()


    ### Model ###

    async def playadd(self, ctx, request, author, queuetop):
        if queuetop:
            queuetracks: function = lambda tracks : self.dequeue.extendleft(reversed(tracks))
        else:
            queuetracks: function = self.dequeue.extend

        embed = view = None

        if re.match(r'https?://(?:www\.)?.+', request):
            try:
                result = await self.current_node.get_playlist(query=request, cls=wavelink.YouTubePlaylist)
            except wavelink.WavelinkException:
                result = (await self.current_node.get_tracks(query=request, cls=wavelink.YouTubeTrack))[0]
        else:
            result = (await self.current_node.get_tracks(query=f"ytsearch:{request}", cls=wavelink.YouTubeTrack))[0]

        if isinstance(result, wavelink.YouTubePlaylist):
            playlist = result
            for track in playlist.tracks:
                track.requester = author 
            queuetracks(playlist.tracks)

            embed = Embed(
                title = f"Queued playlist",
                description = playlist.name,
                color = utils.rng.random_color()
            )
            view = Undo(container=self.misc_views,
                        undo_op=(lambda tracks : [self.dequeue.remove(track) for track in tracks], playlist.tracks),
                        requester_id=author.id)

        else:
            track = result
            track.requester = author
            queue_pos = queuetracks([track])

            if self.is_playing():
                embed = Embed(
                    title = f"Track queued - Position {queue_pos}",
                    description = track.title,
                    url = track.uri,
                    color = utils.rng.random_color()
                )
                embed.set_thumbnail(url=result.thumbnail)
                view = Undo(container=self.misc_views,
                            undo_op=(lambda track : self.dequeue.remove(track), track),
                            requester_id=author.id)
                

        # If bot isn't playing, process queue
        if not self.is_playing() and not self.spawn_ctx:
            self.spawn_ctx = ctx
            track = self.dequeue.popleft()
            await self.play(track)
            self.last_track = track

        return (embed, view)


    async def remove(self, idx):
        try:
            del self.dequeue[int(idx)-1]
            return True
        except IndexError as e:
            raise commands.CommandError("Error: please enter a valid index number")


    async def skip(self, num=None):
        if not num:
            self.skipped_tracks = [self.current]
            await self.stop()
            return True
        else:
            try:
                self.skipped_tracks = [self.current]
                for _ in range(int(num)-1):
                    self.skipped_tracks.append(self.dequeue.popleft())
                await self.stop()
                return True
            except IndexError:
                raise commands.CommandError("Error: please enter a valid index number")


    async def deskip(self):
        if self.skipped_tracks:
            self.dequeue.appendleft(self.current)
            self.dequeue.extendleft(reversed(self.skipped_tracks))
            self.skipped_tracks = None
            await self.stop()
            return True
        else:
            return False


    async def seek(self, time):
        try:
            if time == 0:
                seektime = 0
            else:
                seconds = utils.general.timestr_to_secs(time)
                seektime = seconds*1000
                if seconds > self.current.duration:
                    raise ValueError
            await super().seek(seektime)
        except ValueError:
            raise commands.CommandError("Error: invalid timestamp")


    async def restart(self):
        await self.seek(0)

    
    async def replay(self, ctx):
        if not self.is_playing() and self.last_track:
            await self.play(self.last_track)
        else:
            await ctx.send("nah i dont really feel like it")


    async def loop(self):
        if self.loop_track:
            self.loop_track = None
        else:
            self.loop_track = track = self.current
        return self.loop_track


    async def status(self, response_channel=None):
        if self.is_playing():
            embed, time_remaining = await self.generate_status()
            if not self.status_view:
                self.status_view = MusicControls(self, timeout=time_remaining)
            self.status_view.messages.append(await response_channel.send(embed=embed, view=self.status_view))
        else:
            await response_channel.send("Nothing is playing")


    async def showqueue(self, requester):
        if track_list := list(self.dequeue):
            embeds = await self.generate_tracklists(track_list)
            view = TrackList(embeds, author_id=requester.id) if len(embeds) > 1 else None
            return(embeds[0], view)
        else:
            embed = Embed(
                title = f"Queue is empty",
                color = utils.rng.random_color()
            )
            return(embed, None)


    async def expire_stale_views(self):
        if self.status_view:
            await self.status_view.expire()
            self.status_view = None


    async def expire_all_views(self):
        if self.status_view:
            await self.status_view.expire()
            self.status_view = None

        for view in self.misc_views:
            await view.expire()
        self.misc_views.clear()


    ### View ###

    async def generate_status(self) -> discord.Embed:
        track = self.current
        embed = Embed(
            title = f"Now Playing",
            description = f"[{track.title}]({track.uri})\n",
            color = utils.rng.random_color()
        )
        if track.requester:
            embed.add_field(name="Requested by:", value=track.requester.mention, inline=False)
        if (player_position := self.position/1000) == (track_duration := track.duration/1000):
            position = f"\n0:00 / {utils.general.sec_to_minsec(int(track_duration))}"
            time_remaining = track_duration # track position is initialzied to duration?
        else:
            position = f"\n{utils.general.sec_to_minsec(int(player_position))} / {utils.general.sec_to_minsec(int(track_duration))}"
            time_remaining = track_duration - player_position
        embed.add_field(name="Position", value=position, inline=False)
        if hasattr(track, "thumbnail"):
            embed.set_thumbnail(url=track.thumbnail)
        return embed, time_remaining



    async def generate_tracklists(self, track_list) -> list[discord.Embed]:
        embeds = []
        pagecount = math.ceil(len(track_list) / self.pagesize)
        for idx in range(pagecount):
            start_idx = idx*self.pagesize
            tracks = track_list[start_idx:start_idx+self.pagesize]
            
            index, title, requester = "", "", ""
            for i,track in enumerate(tracks, start=1):
                index += f"{start_idx+i}\n"
                title += f"[{track.title[:42]}]({track.uri})\n"
                requester += f"{track.requester.mention}\n"

            embed = Embed(title = f"Queued tracks: {idx+1} / {pagecount}",color = utils.rng.random_color())
            embed.add_field(name="#", value = index)
            embed.add_field(name="Track", value = title)
            embed.add_field(name="Requested by", value = requester)

            embeds.append(embed)
        return embeds



class ExpiringView(discord.ui.View):
    """Expiring views will disable all childen upon calling expire()"""
    def __init__(self, container=None, *, timeout=30):
        super().__init__(timeout=timeout)
        self.messages = []
        self.container = container
        if self.container is not None:
            self.container.append(self)

    async def on_timeout(self):
        await self.expire()

    async def expire(self):
        for item in self.children:
            item.disabled = True
        for msg in reversed(self.messages):
            await msg.edit(view=self)
        #self.messages.clear()
        self.stop()
        if self.container:
            self.container.remove(self)



class GatedView(ExpiringView):
    """Gated views check for user permission before allowing interactions"""
    def __init__(self, *, author_id=None, timeout=30):
        super().__init__(timeout=timeout)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction):
        banned = await Permissions.query_banlist(interaction.user.id)
        is_author = interaction.user.id == self.author_id
        in_channel = interaction.user.voice.channel == interaction.guild.voice_client.channel if interaction.user.voice else False

        if banned:
            await interaction.response.send_message("Fuck you!", ephemeral=True, delete_after=10)
            return False
        elif not in_channel and not is_author:
            await interaction.response.send_message("You must be in the voice channel to perform that action", ephemeral=True, delete_after=10)
            return False
        else:
            return True



class TrackList(GatedView):
    """discord.py view for tracklist queue"""
    def __init__(self, pages, *, author_id=None, timeout=30):
        super().__init__(author_id=author_id, timeout=timeout)
        self.pages = pages
        self.index = 0
        self.pagecount = len(pages)


    @discord.ui.button(label='Previous', style=discord.ButtonStyle.grey, disabled=True)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self.children[1].disabled = False
        if self.index == 0:
            button.disabled = True
        await interaction.response.edit_message(view=self, embed=self.pages[self.index])


    @discord.ui.button(label='Next', style=discord.ButtonStyle.grey)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self.children[0].disabled = False
        if self.index == self.pagecount - 1:
            button.disabled = True
        await interaction.response.edit_message(view=self, embed=self.pages[self.index])



class MusicControls(GatedView):
    """Creates a discord.py view that adds a skip and restart button."""

    def __init__(self, vc, *, timeout = 10):
        super().__init__(timeout=timeout)
        self.vc : Player = vc
        self.children[1].disabled = not self.vc.skipped_tracks
        self.children[3].style = discord.ButtonStyle.green if vc.loop_track else discord.ButtonStyle.grey


    @discord.ui.button(label='Restart', custom_id="restart", style=discord.ButtonStyle.grey)
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.vc.restart()
        self.timeout = self.vc.current.duration
        embed, time_remaining = await self.vc.generate_status()
        await interaction.response.edit_message(embed=embed)


    @discord.ui.button(label='Deskip', custom_id="deskip", style=discord.ButtonStyle.grey)
    async def deskip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.vc.deskip()
        button.style = discord.ButtonStyle.blurple
        await interaction.response.edit_message(view=self)
        await self.expire()


    @discord.ui.button(label='Skip', custom_id="skip", style=discord.ButtonStyle.grey)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.vc.skip()
        button.style = discord.ButtonStyle.red
        await interaction.response.edit_message(view=self)
        await self.expire()


    @discord.ui.button(label='Loop', custom_id="loop")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, timeout = await self.vc.generate_status()
        if await self.vc.loop():
            button.style = discord.ButtonStyle.green
            self.timeout = None
        else:
            button.style = discord.ButtonStyle.grey
            self.timeout = timeout
        await interaction.response.defer()
        for msg in reversed(self.messages):
            await msg.edit(embed=embed, view=self)




class Undo(ExpiringView):
    """Creates a discord.py view that adds an undo button.

    The undo function will be called when the undo button is pressed.

    Attributes
    -----------
    undo_func: :class:`list`  ex: [function_name, arg1, arg2, ...]
        A list containing the undo function followed by any arguments
    requester_id: :class:`int`
        The id of the user who is allowed to interact with the view
    """

    def __init__(self, *, container=None, undo_op: list, requester_id, timeout = 30):
        super().__init__(container=container, timeout=timeout)
        self.undo_op = undo_op
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
        self.undo_op[0](self.undo_op[1])
