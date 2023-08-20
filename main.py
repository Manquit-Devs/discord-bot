import os
import wavelink
from src.bot import Bot

from discord.ext import commands


class Music(commands.Cog):
    """Music cog to hold Wavelink related commands and listeners."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.vc = None

        bot.loop.create_task(self.connect_nodes())

        @bot.slash_command(name="pause3", description="Resumir")
        async def pause3(ctx: commands.Context):
            await self.vc.resume()
            await ctx.respond(f"Resumed: `{self.vc.source.title}`"
                              )  # return a message

        @bot.slash_command(name="pause2", description="Pausar")
        async def pause2(ctx: commands.Context):
            await self.vc.pause()
            await ctx.respond(f"Paused: `{self.vc.source.title}`"
                              )  # return a message

        @bot.slash_command(name="play2")
        async def play2(ctx, search: str):
            self.vc: wavelink.Player = ctx.voice_client
            # vc = ctx.voice_client  # define our voice client

            if not self.vc:  # check if the bot is not in a voice channel
                self.vc = await ctx.author.voice.channel.connect(
                    cls=wavelink.Player)  # connect to the voice channel

            if ctx.author.voice.channel.id != self.vc.channel.id:  # check if the bot is not in the voice channel
                return await ctx.respond(
                    "You must be in the same voice channel as the bot."
                )  # return an error message

            song = await wavelink.YouTubeTrack.search(query=search,
                                                      return_first=True
                                                      )  # search for the song

            if not song:  # check if the song is not found
                return await ctx.respond("No song found."
                                         )  # return an error message

            await self.vc.play(song)  # play the song
            await ctx.respond(f"Now playing: `{self.vc.source.title}`"
                              )  # return a message

    async def connect_nodes(self):
        """Connect to our Lavalink nodes."""
        await self.bot.wait_until_ready()

        await wavelink.NodePool.create_node(bot=self.bot,
                                            host='0.0.0.0',
                                            port=2333,
                                            password='youshallnotpass')

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a node has finished connecting."""
        print(f'Node: <{node.identifier}> is ready!')


if __name__ == "__main__":
    music_bot = Bot()
    music_bot.add_cog(Music(music_bot))
    music_bot.run(os.getenv("TOKEN"))
