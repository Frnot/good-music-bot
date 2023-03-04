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


#TODO: on loop, update status view's expire
#TODO: expire undo when queued one track and it gets played or removed


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


    ####################
    ##### Commands #####
    ####################


    @commands.command()
    async def play(self, ctx, *, request, queuetop=False):
        """Streams from a url (doesn't predownload)"""
        embed, view = await ctx.voice_client.playadd(ctx, request, ctx.author, queuetop)
        if embed and view:
            view.message = await ctx.send(embed=embed, view=view)


    @commands.command()
    async def playnext(self, ctx, *, request):
        """Adds song to top of play queue"""
        await self.play(ctx, request=request, queuetop=True)


    @commands.command()
    async def remove(self, ctx, idx):
        if await ctx.voice_client.remove(idx):
            await utils.general.send_confirmation(ctx)


    @commands.command()
    async def clear(self, ctx):
        ctx.voice_client.queue.clear()
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def skip(self, ctx, num=None):
        if await ctx.voice_client.skip(num):
            await utils.general.send_confirmation(ctx)


    @commands.command()
    async def seek(self, ctx, time):
        await ctx.voice_client.seek(time)
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def restart(self, ctx):
        await ctx.voice_client.restart()
        await utils.general.send_confirmation(ctx)

    
    @commands.command()
    async def loop(self, ctx):
        if track := await ctx.voice_client.loop():
            embed = Embed(
                title = f"Looping Track",
                description = f"[{track.title}]({track.uri})\n",
                color = utils.rng.random_color()
            )
            embed.add_field(name="Requested by:", value=ctx.author.mention)
            if hasattr(track, "thumbnail"):
                embed.set_thumbnail(url=track.thumbnail)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Disabled loop mode")


    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()
        await utils.general.send_confirmation(ctx)


    @commands.command()
    async def np(self, ctx):
        """Shows info of currently playing track"""
        await ctx.voice_client.status(ctx.channel)


    @commands.command()
    async def queue(self, ctx):
        embed, view = await ctx.voice_client.showqueue(ctx.author)
        if view:
            view.message = await ctx.send(embed=embed, view=view)
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
    @loop.before_invoke
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


    @commands.Cog.listener()
    async def on_wavelink_track_start(self, vc, track):
        if vc.loop_track and track.id == vc.loop_track.id:
            pass
        else:
            await vc.status(vc.spawn_ctx.channel)


    @commands.Cog.listener()
    async def on_wavelink_track_end(self, vc, track, reason):
        # track doesn't have requester attribute, have to use vc.loop_track
        if vc.loop_track and reason == "FINISHED":
            await vc.play(vc.loop_track)
        else:
            if vc.loop_track:
                vc.loop_track = None
            if not vc.queue.is_empty():
                new_track = vc.queue.pop()
                await vc.play(new_track)
            else:
                vc.spawn_ctx = None
                await vc.stop()



class Player(wavelink.Player):
    """Each server will get its own unique Player object, 
    spawned on bot joining voice channel 
    and destroyed on bot leaving voice channel"""

    #TODO: keep track of all status views while track is playing,
        # when track ends, check if switching to new track. if so, expire all old status views
    #TODO: store currently playing track in status views, send it to restart() func

    __slots__ = ("test",) #TODO: populate

    def __init__(self, client, channel):
        super().__init__(client, channel)

        self.queue = PseudoQueue()

        #TODO: can None items just be defined in slots?
        self.statusview = None

        self.loop_track = None
        self.spawn_ctx = None
        self.old_np_view = None
        self.pagesize = 10


    ### Model ###

    async def playadd(self, ctx, request, author, queuetop):
        queuetracks: function = self.queue.put_top if queuetop else self.queue.put
        embed = view = None

        if re.match(r'https?://(?:www\.)?.+', request):
            try:
                result = await self.node.get_playlist(identifier=request, cls=wavelink.YouTubePlaylist)
            except wavelink.LavalinkException:
                result = (await self.node.get_tracks(query=request, cls=wavelink.YouTubeTrack))[0]
        else:
            result = (await self.node.get_tracks(query=f"ytsearch:{request}", cls=wavelink.YouTubeTrack))[0]

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
            view = Undo(undo_op=(self.queue.unqueue, playlist.tracks), requester_id=author.id)

        else:
            track = result
            track.requester = author
            queue_pos = queuetracks(track)

            if self.is_playing():
                embed = Embed(
                    title = f"Track queued - Position {queue_pos}",
                    description = track.title,
                    url = track.uri,
                    color = utils.rng.random_color()
                )
                embed.set_thumbnail(url=result.thumbnail)
                view = Undo(undo_op=(self.queue.unqueue,[track]),requester_id=author.id)
                

        # If bot isn't playing, process queue
        if not self.is_playing() and not self.spawn_ctx:
            self.spawn_ctx = ctx
            track = self.queue.pop()
            await self.play(track)

        return (embed, view)


    async def remove(self, idx):
        try:
            self.queue.remove(idx)
            return True
        except (IndexError, TypeError) as e:
            raise("Error: please enter a valid index number")


    async def skip(self, num=None):
        if not num:
            await self.stop()
            return True
        else:
            try:
                self.queue.pop(int(num)-1)
                await self.stop()
                return True
            except IndexError:
                raise("Error: please enter a valid index number")
                

    async def seek(self, time):
        try:
            if time == 0:
                seektime = 0
            else:
                seconds = utils.general.timestr_to_secs(time)
                seektime = seconds*1000

                if seconds > self.source.duration:
                    raise ValueError

            await super().seek(seektime)
        except ValueError:
            raise("Error: invalid timestamp")


    async def restart(self):
        await self.seek(0)


    async def loop(self):
        if self.loop_track:
            self.loop_track = None
        else:
            self.loop_track = track = self.source
        return self.loop_track


    async def status(self, response_channel=None):
        if self.is_playing():
            embed = await self.generate_status()
            time_remaining = self.source.duration - self.position
            view = MusicControls(self, timeout=time_remaining)
            view.message = await response_channel.send(embed=embed, view=view)
            self.statusview = view
        else:
            await response_channel.send("Nothing is playing")


    async def showqueue(self, requester):
        if track_list := self.queue.show():
            embeds = await self.generate_tracklists(track_list)
            view = TrackList(embeds, author_id=requester.id) if len(embeds) > 1 else None
            return(embeds[0], view)
        else:
            embed = Embed(
                title = f"Queue is empty",
                color = utils.rng.random_color()
            )
            return(embed, None)



    ### View ###

    async def generate_status(self) -> discord.Embed:
        track = self.source
        embed = Embed(
            title = f"Now Playing",
            description = f"[{track.title}]({track.uri})\n",
            color = utils.rng.random_color()
        )
        if track.requester:
            embed.add_field(name="Requested by:", value=track.requester.mention, inline=False)
        if self.position == track.duration:
            position = f"\n{utils.general.sec_to_minsec(0)} / {utils.general.sec_to_minsec(int(track.duration))}"
        else:
            position = f"\n{utils.general.sec_to_minsec(int(self.position))} / {utils.general.sec_to_minsec(int(track.duration))}"
        embed.add_field(name="Position", value=position, inline=False)
        if hasattr(track, "thumbnail"):
            embed.set_thumbnail(url=track.thumbnail)
        return embed



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
    __slots__ = ("message",)
    def __init__(self, *, timeout=30):
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
    __slots__ = ("author_id",)
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
    """Creates a discord.py view that adds a skip and restart button.

    Attributes
    -----------
    restart: :class:`list`  ex: [function_name, arg1, arg2, ...]
        A list containing the function (and arguments) to be called when the restart button is pressed
    skip: :class:`list`  ex: [function_name, arg1, arg2, ...]
        A list containing the function (and arguments) to be called when the skip button is pressed
    """

    __slots__ = ("vc",)

    def __init__(self, vc, *, timeout = 10):
        super().__init__(timeout=timeout)
        self.vc : Player = vc
        self.children[2].style = discord.ButtonStyle.green if vc.loop_track else discord.ButtonStyle.grey


    @discord.ui.button(label='Restart', custom_id="restart", style=discord.ButtonStyle.grey)
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.vc.restart()
        # Update view timeout
        self.timeout = self.vc.source.duration
        embed = await self.vc.generate_status()
        await interaction.response.edit_message(embed=embed)


    @discord.ui.button(label='Skip', custom_id="skip", style=discord.ButtonStyle.grey)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.vc.skip()
        button.style = discord.ButtonStyle.red
        await interaction.response.edit_message(view=self)
        await self.expire()


    @discord.ui.button(label='Loop', custom_id="loop")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.vc.loop():
            button.style = discord.ButtonStyle.green
        else:
            button.style = discord.ButtonStyle.grey
        await interaction.response.edit_message(view=self)




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

    __slots__ = ("undo_op", "requester_id")

    def __init__(self, *, undo_op: list, requester_id, timeout = 30):
        super().__init__(timeout=timeout)
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
        try: # item is iterable
            self.list.extend(item)
        except:
            self.list.append(item)
        return len(self.list)


    def put_top(self, item) -> int:
        try: # item is iterable
            item.extend(self.list)
            self.list = item
        except:
            self.list.insert(0, item)
        return 1

    def clear(self):
        self.list.clear()

    def remove(self, idx):
        del self.list[int(idx)-1]

    def unqueue(self, tracks):
        for track in tracks:
            try:
                self.list.remove(track)
            except ValueError:
                pass

    def show(self):
        return self.list.copy()

    def is_empty(self):
        return not self.list
