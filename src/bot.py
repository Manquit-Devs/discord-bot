import traceback
import os

from discord import Activity, ActivityType, Embed, Option, Bot, Member, Intents, Guild, Message, VoiceState
from discord.ext import commands
from dotenv import load_dotenv

from src.logger import Logger
from src.lyrics.lyrics import Lyrics
from src.player.player import Player
from src.db.sqlite import Database
from src.db.bot_sql import EVENT_TYPES

class Bot(Bot):

    def __init__(self):
        super().__init__(intents=Intents.all())
        load_dotenv()
        self.logger = Logger().get_logger()
        self.logger.info("Iniciando Bot.")
        self.token = os.getenv("TOKEN")
        self.delete_time = 30
        self.player = Player(bot=self)
        self.lyrics = Lyrics(bot=self)
        self.db = Database(self.logger)
        self.__version__ = "0.6.0"

        @self.event
        async def on_ready():
            self.logger.info("Bot conectado com o Discord.")
            self.db.check_guilds_and_users(self.guilds)
            self.loop.create_task(
                self.change_presence(activity=Activity(
                    type=ActivityType.listening, name="no /play, tchama ♫")))

        @self.event
        async def on_presence_update(before: Member, after: Member):
            if not after.bot:
                event = None
                desc = None
                if before.status != after.status:
                    desc = before.status.value
                    if after.status.value == 'online':
                        event = EVENT_TYPES.ONLINE
                    elif after.status.value == 'idle':
                        event = EVENT_TYPES.IDLE
                    elif after.status.value == 'offline':
                        event = EVENT_TYPES.OFFLINE
                    elif after.status.value == 'dnd':
                        event = EVENT_TYPES.DND
                    else:
                        self.logger.error(f'Encontrado status nao previsto: {after.status.value}')
                if before.activity != after.activity:
                    if not before.activity and after.activity.type.name == "playing":
                        event = EVENT_TYPES.PLAYING_START
                        desc = after.activity.name
                    elif before.activity and after.activity and after.activity.type.name == "playing":
                        event = EVENT_TYPES.PLAYING_CHANGE
                        desc = after.activity.name
                    elif before.activity and (not after.activity or after.activity.type.name != "playing"):
                        event = EVENT_TYPES.PLAYING_STOP
                    
                self.db.insert_event(after.id, event.value, after.guild.id, desc)

        @self.event
        async def on_member_join(member: Member):
            if not member.bot:
                self.db.insert_event(member.id, EVENT_TYPES.JOIN.value, member.guild.id)

        @self.event
        async def on_member_remove(member: Member):
            if not member.bot:
                self.db.insert_event(member.id, EVENT_TYPES.LEAVE.value, member.guild.id)

        @self.event
        async def on_member_ban(guild: Guild, member: Member):
            if not member.bot:
                self.db.insert_event(member.id, EVENT_TYPES.BAN.value, guild.id)

        @self.event
        async def on_member_unban(guild: Guild, member: Member):
            if not member.bot:
                self.db.insert_event(member.id, EVENT_TYPES.UNBAN.value, guild.id)

        @self.event
        async def on_message(msg: Message):
            if not msg.author.bot:
                self.db.insert_event(msg.author.id, EVENT_TYPES.MESSAGE_SEND.value, msg.guild.id, msg.channel.name)

        @self.event
        async def on_message_edit(before: Message, after: Message):
            if not after.author.bot:
                self.db.insert_event(after.author.id, EVENT_TYPES.MESSAGE_EDIT.value, after.guild.id)

        @self.event
        async def on_message_delete(msg: Message):
            if not msg.author.bot:
                self.db.insert_event(msg.author.id, EVENT_TYPES.MESSAGE_DELETE.value, msg.guild.id)

        @self.event
        async def on_member_update(before: Member, after: Member):
            if not after.bot and before.nick != after.nick:
                self.db.insert_event(after.id, EVENT_TYPES.NICK_CHANGE.value, after.guild.id, before.nick)

        @self.event
        async def on_voice_state_update(member: Member, before: VoiceState, after: VoiceState):
            if not member.bot:
                event = None
                if before.afk != after.afk:
                    if after.afk:
                        event = EVENT_TYPES.VOICE_AFK_START
                    else:
                        event = EVENT_TYPES.VOICE_AFK_STOP
                elif before.channel != after.channel:
                    if not before.channel or before.channel.type == "private":
                        event = EVENT_TYPES.VOICE_CONNECT
                    elif not after.channel:
                        event = EVENT_TYPES.VOICE_DISCONNECT
                    else:
                        event = EVENT_TYPES.VOICE_MOVE
                elif before.self_mute != after.self_mute:
                    if after.self_mute:
                        event = EVENT_TYPES.VOICE_MUTE_START
                    else:
                        event = EVENT_TYPES.VOICE_MUTE_STOP
                elif before.self_deaf != after.self_deaf:
                    if after.self_deaf:
                        event = EVENT_TYPES.VOICE_DEAF_START
                    else:
                        event = EVENT_TYPES.VOICE_DEAF_STOP
                elif before.self_stream != after.self_stream:
                    if after.self_stream:
                        event = EVENT_TYPES.STREAM_START
                    else:
                        event = EVENT_TYPES.STREAM_STOP
                elif before.mute != after.mute:
                    if after.mute:
                        event = EVENT_TYPES.VOICE_GUILD_MUTE_START
                    else:
                        event = EVENT_TYPES.VOICE_GUILD_MUTE_STOP
                elif before.deaf != after.deaf:
                    if after.deaf:
                        event = EVENT_TYPES.VOICE_GUILD_DEAF_START
                    else:
                        event = EVENT_TYPES.VOICE_GUILD_DEAF_STOP
                    
                if after:
                    self.db.insert_event(member.id, event.value, member.guild.id, after.channel.name)
                else:
                    self.db.insert_event(member.id, event.value, member.guild.id)

        @self.command(
            description="Reproduzir música.",
            options=[
                Option(
                    str,
                    name="musica",
                    description="Nome ou link do youtube.",
                    required=True,
                )
            ],
        )
        async def play(ctx: commands.Context, play_text: str):
            self.logger.info("O bot recebeu uma solicitação de play.")
            try:
                await self.player.play(ctx, play_text)
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="play")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg,
                                  delete_after=self.delete_time)

        @self.command(description="Pausar reprodutor.")
        async def pause(ctx: commands.Context):
            try:
                await self.player.pause(ctx)
                await ctx.respond("A música foi pausada.",
                                  delete_after=self.delete_time)
                self.logger.info("O bot pausou a música.")
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="pause")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(description="Pula para a próxima música.")
        async def next(ctx: commands.Context):
            try:
                await self.player.next(ctx)
                await ctx.respond("A música foi pulada.",
                                  delete_after=self.delete_time)
                self.logger.info("O bot pulou a música.")
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="next")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(description="Continuar reprodutor.")
        async def resume(ctx: commands.Context):
            try:
                await self.player.resume(ctx)
                await ctx.respond("A música foi resumida.",
                                  delete_after=self.delete_time)
                self.logger.info("O bot voltou a reproduzir a música.")
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="resume")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(description="Força a saída do bot do canal onde está.")
        async def leave(ctx: commands.Context):
            try:
                await self.player.leave(ctx)
                await ctx.respond("Faleu valou!",
                                  delete_after=self.delete_time)
                self.logger.info("O bot saiu do canal de voz.")
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="leave")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(description="Mostra a fila de reprodução.")
        async def list(ctx: commands.Context):
            try:
                await self.player.list(ctx)
                self.logger.info("O bot listou a fila de reprodução.")
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="list")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(
            description="Remover música da fila.",
            options=[
                Option(
                    int,
                    name="posicao",
                    description="Posição da música na fila.",
                    required=True,
                )
            ],
        )
        async def remove(ctx: commands.Context, *, idx: int):
            try:
                await self.player.remove(ctx, idx)
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="remove")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(description="Limpa a fila de reprodução.")
        async def clear(ctx: commands.Context):
            try:
                rs = await self.player.clear(ctx)
                if rs:
                    await ctx.respond("Fila esvaziada!",
                                      delete_after=self.delete_time)
                else:
                    embed_msg = Embed(
                        title="Fila vazia",
                        description="Adicione músicas :)",
                        color=0xEB2828,
                    )
                    await ctx.respond(embed=embed_msg,
                                      delete_after=self.delete_time)
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="clear")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(description="Embaralha a fila de reprodução.")
        async def shuffle(ctx: commands.Context):
            try:
                await self.player.shuffle(ctx)
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="shuffle")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(
            description=
            "Busca a letra da música. Como padrão utiliza a música que está sendo reproduzida caso haja.",
            options=[
                Option(
                    str,
                    name="musica",
                    description="Informar nome da música manualmente.",
                    required=False,
                )
            ],
        )
        async def lyrics(ctx: commands.Context, search_text: str = None):
            try:
                await self.lyrics.search_and_send(ctx, search_text)
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="lyrics")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

        @self.command(description="Latência do bot.")
        async def ping(ctx: commands.Context):
            try:
                lat = int(self.latency * 1000)
                self.logger.info(f"Latencia: {lat}ms")
                await ctx.respond(f"Pong! ({lat}ms)",
                                  delete_after=self.delete_time)
            except Exception as err:
                error = str(traceback.format_exc())
                self.logger.error(error)
                await self.send_exception(error, command="ping")
                embed_msg = Embed(
                    title="ERRO",
                    description="Desculpe,\nTive um erro interno.",
                    color=0xFF0000,
                )
                await ctx.respond(embed=embed_msg, delete_after=5)

    async def send_commands_list(self, ctx: commands.Context):
        command_list_msg_title = "🎶 **Lista de comandos**"
        commands_list_msg_description = "**/play** <nome da música> - Coloca uma música solicitada na fila\n\
                **/pause** -  Pausa a música atual\n\
                **/resume** - Voltar a tocar a música pausada\n\
                **/next** - Pula para a proxima música na fila\n\
                **/list** - Exibi a fila de músicas a serem tocadas\n\
                **/shuffle** - Embaralha a fila de músicas a serem tocadas\n\
                **/clear** - Limpa a fila de músicas\n\
                **/remove** <posição da música na fila>  - Remove uma música da fila\n\
                **/lyrics** - Exibi a letra da música que está reproduzindo\n\
                **/lyrics** <nome da música> - Exibi a letra da música solicitada\n\
                **/leave** - Me manda embora 😔\n\
                \n"

        commands_list_embed_msg = Embed(
            title=command_list_msg_title,
            description=commands_list_msg_description,
            color=0x550A8A,
        )
        commands_list_embed_msg.set_footer(text=f"Versão {self.__version__}")
        await ctx.send(embed=commands_list_embed_msg)

    async def send_exception(self,
                             exception: str,
                             command: str = None) -> None:
        debug_guild = int(os.getenv("DEBUG_GUILD"))
        debug_channel = int(os.getenv("DEBUG_CHANNEL"))
        if not (debug_guild and debug_channel):
            self.logger.error("Falha nos parametros de debug")
            return
        out = self.get_guild(debug_guild).get_channel(debug_channel)
        if command:
            emb_title = f"Exception on: {command}"
        else:
            emb_title = f"Exception"
        exeption_embed_msg = Embed(
            title=emb_title,
            description=exception,
            color=0xFF0000,
        )
        await out.send(embed=exeption_embed_msg)
