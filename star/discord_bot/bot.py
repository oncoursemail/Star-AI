"""Discord slash commands, embeds, contextual voice messages, and voice playback.

No message-content intent, self-bot account, autonomous actions, or background
recording is used. The gateway is strictly opt-in and owner-scoped.
"""
from dataclasses import dataclass, field
import io
import logging
import os

from .audio import MAX_ATTACHMENT_BYTES, ffmpeg_path, post_voice_message, validate_attachment, pcm_to_wav
from .core import AccessPolicy, MAX_AUDIO_TEXT, MAX_EMBED_DESCRIPTION, embed_parts
from .dm_mode import DMSettings, MAX_IMAGE_BYTES, classify_owner_dm, prepare_discord_image
from .service import DiscordService

_LOG = logging.getLogger(__name__)
_GOLD = 0xE4B95B


@dataclass(frozen=True)
class BotConfig:
    token: str
    policy: AccessPolicy
    sync_commands: bool = False
    sync_guild_id: int | None = None
    dm: DMSettings = field(default_factory=DMSettings)

    @classmethod
    def from_env(cls, env=None) -> "BotConfig":
        vars = os.environ if env is None else env
        token = vars.get("STAR_DISCORD_BOT_TOKEN", "").strip()
        if not token or any(char.isspace() for char in token):
            raise ValueError("STAR_DISCORD_BOT_TOKEN must be set outside the repository")
        policy = AccessPolicy.from_env(vars)
        raw = vars.get("STAR_DISCORD_SYNC_GUILD_ID", "").strip()
        sync = vars.get("STAR_DISCORD_SYNC_COMMANDS", "0").strip()
        if sync not in {"", "0", "1"}:
            raise ValueError("STAR_DISCORD_SYNC_COMMANDS must be 0 or 1")
        if raw and (not raw.isdecimal() or int(raw) not in policy.guilds):
            raise ValueError("Command-sync test guild must be in STAR_DISCORD_GUILD_IDS")
        if sync == "1" and not raw:
            raise ValueError("Supply an approved STAR_DISCORD_SYNC_GUILD_ID before syncing commands")
        return cls(token, policy, sync == "1", int(raw) if raw else None,
                   DMSettings.from_env(vars))


def create_bot(config: BotConfig, *, service: DiscordService | None = None):
    """Create a Gateway-connected bot; importing this module remains dependency-light."""
    import discord
    from discord import app_commands
    from discord.ext import commands

    service = service or DiscordService(config.policy)
    intents = discord.Intents.default()
    intents.message_content = False
    intents.members = False
    intents.presences = False
    # DMs addressed directly to this bot do not require privileged MESSAGE_CONTENT.
    # Guild message text and attachments remain inaccessible.
    intents.dm_messages = config.dm.enabled

    class StarBot(commands.Bot):
        async def setup_hook(self):
            # Never repeatedly bulk-overwrite a server's commands unless the
            # owner explicitly requests a sync for an initial install/update.
            if config.sync_commands:
                guild = discord.Object(id=config.sync_guild_id) if config.sync_guild_id else None
                if guild:
                    self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)

    bot = StarBot(command_prefix=commands.when_mentioned, help_command=None,
                  intents=intents, allowed_mentions=discord.AllowedMentions.none())

    def embed(title: str, description: str, *, footer: str = "STAR Intelligence · Discord"):
        result = discord.Embed(title=title[:250], description=description[:MAX_EMBED_DESCRIPTION], color=_GOLD)
        result.set_footer(text=footer)
        return result

    async def problem(interaction, message: str):
        note = embed("STAR · Notice", message[:1200])
        if interaction.response.is_done():
            await interaction.followup.send(embed=note, ephemeral=True,
                                            allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message(embed=note, ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())

    async def permit(interaction):
        try:
            return service.authorized(interaction.user.id, interaction.guild_id, interaction.channel_id)
        except PermissionError as exc:
            await problem(interaction, str(exc))
            return None

    def require_voice_message_permissions(interaction):
        permissions = interaction.app_permissions
        if not (permissions.send_messages and permissions.attach_files and permissions.send_voice_messages):
            raise ValueError("Give STAR Send Messages, Attach Files and Send Voice Messages permissions in this channel")

    async def handle_failure(interaction, exc: Exception):
        if isinstance(exc, (ValueError, FileNotFoundError)):
            await problem(interaction, str(exc))
        else:
            _LOG.exception("STAR Discord operation failed")
            await problem(interaction, "STAR could not complete this request. Check the local bot logs and model/voice setup.")

    async def publish_answer(interaction, answer: str, *, ephemeral: bool, key: tuple,
                             sources: tuple[dict, ...] = ()):
        chunks = embed_parts(answer)
        # Long AI answers are delivered as a real file, not silently truncated.
        attach = None
        if len(chunks) > 1:
            attach = discord.File(io.BytesIO(answer.encode("utf-8")), filename="star-answer.txt")
        response = embed("✦ STAR · Research" if sources else "✦ STAR · Answer",
                         chunks[0] + ("\n\n*Full reply attached.*" if attach else ""))
        if sources:
            # Source URLs come directly from STAR's constrained search adapter,
            # not fabricated by the model or allowed to become executable tools.
            links = []
            for index, source in enumerate(sources[:5], 1):
                url = str(source.get("url", ""))
                if url.startswith("https://") and not any(c in url for c in "\n\r<>` )"):
                    links.append(f"[{index}]({url})")
            if links:
                response.add_field(name="Sources (search excerpts, not full pages)",
                                   value=" · ".join(links)[:1024], inline=False)
        # discord.py treats file=None as a file and fails, so the file is passed only when there is one.
        extra = {"file": attach} if attach is not None else {}
        await interaction.followup.send(
            embed=response,
            view=AnswerActions(key, answer, allow_public_voice=not ephemeral), ephemeral=ephemeral,
            allowed_mentions=discord.AllowedMentions.none(), **extra,
        )

    class AnswerActions(discord.ui.View):
        def __init__(self, key: tuple, answer: str, *, allow_public_voice: bool):
            super().__init__(timeout=600)
            self.key = key
            self.answer = answer
            # Private responses NEVER get a one-click route into a public voice message.
            if not allow_public_voice:
                self.remove_item(self.speak_button)

        @discord.ui.button(label="Voice message (public)", emoji="🔊", style=discord.ButtonStyle.secondary)
        async def speak_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if await permit(interaction) != self.key:
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                require_voice_message_permissions(interaction)
                line = self.answer[:MAX_AUDIO_TEXT]
                msg = await service.voice_message(line)
                await post_voice_message(config.token, interaction.channel_id, msg)
                await interaction.followup.send("STAR sent a voice message in this channel (first 500 characters).",
                                                ephemeral=True)
            except Exception as exc:
                await handle_failure(interaction, exc)

        @discord.ui.button(label="Clear context", emoji="🧹", style=discord.ButtonStyle.secondary)
        async def forget_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if await permit(interaction) != self.key:
                return
            service.forget(self.key)
            await interaction.response.send_message(embed=embed("✦ STAR · Context cleared",
                        "This channel's temporary conversation context is cleared. No desktop memory was changed."),
                        ephemeral=True)

    star = app_commands.Group(name="star", description="STAR Intelligence AI and speech tools")

    @star.command(name="ask", description="Ask STAR's configured local or hosted brain")
    @app_commands.describe(prompt="Question or Roblox development request", private="Only show your answer to you")
    async def ask(interaction: discord.Interaction, prompt: str, private: bool = True):
        key = await permit(interaction)
        if key is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=private)
        try:
            answer = await service.ask(key, prompt)
            await publish_answer(interaction, answer, ephemeral=private, key=key)
        except Exception as exc:
            await handle_failure(interaction, exc)

    @star.command(name="research", description="Research with STAR's configured web search provider")
    @app_commands.describe(question="Question to research with cited sources", private="Keep the result private")
    async def research(interaction: discord.Interaction, question: str, private: bool = True):
        key = await permit(interaction)
        if key is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=private)
        try:
            result = await service.research(key, question)
            await publish_answer(interaction, result.text, ephemeral=private, key=key, sources=result.sources)
        except Exception as exc:
            await handle_failure(interaction, exc)

    @star.command(name="help", description="Show the STAR command guide")
    async def help_command(interaction: discord.Interaction):
        if await permit(interaction) is None:
            return
        result = embed("✦ STAR · Command Center",
            "**Thinking**\n`/star ask` — ask Star (private by default)\n"
            "`/star research` — web-supported answer with actual search sources\n"
            "`/star reset` — forget this channel's temporary context\n"
            "**Speech**\n`/star speak` — post an actual Discord voice message\n"
            "`/star hear` — privately transcribe and answer an audio file\n"
            "`/star converse` — recorded question → PUBLIC voice reply\n"
            "**Voice channel**\n`/star join` — join your voice channel\n"
            "`/star say` — synthesize speech in that channel\n`/star stop` — stop speaking\n"
            "`/star leave` — disconnect\n"
            "**Operations**\n`/star status` — model configuration and permission status\n"
            "`/star doctor` — private setup diagnostics\n"
            "Right-click a text or voice message → **Apps → Ask STAR about this**.\n\n"
            "*Discord mode is chat-only: Roblox Studio, filesystem, GitHub and MCP edits are unavailable.*")
        await interaction.response.send_message(embed=result, ephemeral=True)

    @star.command(name="status", description="Check STAR's Discord configuration")
    async def status(interaction: discord.Interaction):
        if await permit(interaction) is None:
            return
        try:
            from ..desktop_core import Settings, app_data
            settings = Settings.load(app_data() / "settings.json")
            from ..server_roles import quick_model
            model = quick_model(settings) or "Not selected"
            provider = settings.provider
        except (OSError, ValueError):
            model, provider = "Not configured", "Not configured"
        detail = (f"**Provider:** `{provider[:60]}`\n**Model:** `{model[:120]}`\n"
                  "**Access:** configured Discord owner only\n**Intents:** non-privileged\n"
                  "**Tools:** disabled in Discord\n**Context:** temporary, in RAM\n"
                  "**Voice:** Kokoro + FFmpeg (optional)\n**Listening:** audio attachments by explicit request only\n"
                  "*Model availability and audio output have not been tested by this status command.*")
        await interaction.response.send_message(embed=embed("✦ STAR · Status", detail), ephemeral=True)

    @star.command(name="doctor", description="Check STAR Discord installation and voice dependencies")
    async def doctor(interaction: discord.Interaction):
        if await permit(interaction) is None:
            return
        from .health import doctor_snapshot, format_checks
        await interaction.response.defer(thinking=True, ephemeral=True)
        report = await __import__("asyncio").to_thread(doctor_snapshot)
        await interaction.followup.send(embed=embed("✦ STAR · Diagnostics", format_checks(report)),
                                        ephemeral=True)

    @star.command(name="reset", description="Clear the current channel's private conversation memory")
    async def reset(interaction: discord.Interaction):
        key = await permit(interaction)
        if key is None:
            return
        service.forget(key)
        await interaction.response.send_message(embed=embed("✦ STAR · Context cleared",
                 "Temporary Discord context cleared; desktop memory was not modified."), ephemeral=True)

    @star.command(name="speak", description="Send a real Discord voice message with STAR's voice")
    @app_commands.describe(text="Speech to post in the current text channel (public, max 500 characters)")
    async def speak(interaction: discord.Interaction, text: str):
        if await permit(interaction) is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            require_voice_message_permissions(interaction)
            message = await service.voice_message(text)
            await post_voice_message(config.token, interaction.channel_id, message)
            await interaction.followup.send(embed=embed("✦ STAR · Spoken",
                                    "Posted a native Discord voice message in this channel."), ephemeral=True)
        except Exception as exc:
            await handle_failure(interaction, exc)

    async def answer_audio(interaction, attachment, key):
        validate_attachment(attachment.filename, attachment.content_type, attachment.size)
        blob = await attachment.read()
        if len(blob) > MAX_ATTACHMENT_BYTES:
            raise ValueError("Audio attachment was too large")
        transcript = await service.transcribe(filename=attachment.filename,
                            content_type=attachment.content_type, data=blob)
        response = await service.ask(key, transcript)
        await interaction.followup.send(embed=embed("✦ STAR · Heard", f"**Transcript:** {transcript[:1400]}"),
                                        ephemeral=True)
        await publish_answer(interaction, response, ephemeral=True, key=key)

    @star.command(name="hear", description="Transcribe an audio upload and answer the spoken request")
    @app_commands.describe(audio="Audio attachment; an explicit one-off transcription (not channel recording)")
    async def hear(interaction: discord.Interaction, audio: discord.Attachment):
        key = await permit(interaction)
        if key is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            await answer_audio(interaction, audio, key)
        except Exception as exc:
            await handle_failure(interaction, exc)

    @star.command(name="converse", description="Reply aloud to one recorded question (PUBLIC voice message)")
    @app_commands.describe(audio="Audio upload; STAR posts its spoken answer PUBLICLY in this channel")
    async def converse(interaction: discord.Interaction, audio: discord.Attachment):
        key = await permit(interaction)
        if key is None:
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            require_voice_message_permissions(interaction)
            validate_attachment(audio.filename, audio.content_type, audio.size)
            blob = await audio.read()
            result = await service.converse(key, filename=audio.filename,
                                             content_type=audio.content_type, data=blob)
            await post_voice_message(config.token, interaction.channel_id, result.audio)
            await interaction.followup.send(embed=embed("✦ STAR · Voice reply posted",
                f"**You said:** {result.transcript[:1300]}\n\n"
                "**Response:** A native, public voice message was posted. "
                "Use `/star hear` for a private text-only response."), ephemeral=True)
        except Exception as exc:
            await handle_failure(interaction, exc)

    @star.command(name="join", description="Join your current voice channel (speaker only)")
    async def join(interaction: discord.Interaction):
        if await permit(interaction) is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            if interaction.guild is None or not getattr(interaction.user, "voice", None):
                raise ValueError("Join a server voice channel first")
            channel = interaction.user.voice.channel
            if not isinstance(channel, discord.VoiceChannel):
                raise ValueError("Join a regular server voice channel first")
            voice = interaction.guild.voice_client
            if voice and voice.is_connected():
                if voice.channel.id != channel.id:
                    await voice.move_to(channel)
            else:
                await channel.connect(timeout=20, reconnect=True)
            await interaction.followup.send(embed=embed("✦ STAR · Connected",
              "Joined your channel. Use `/star say` to speak. Voice-channel listening is not enabled."), ephemeral=True)
        except Exception as exc:
            await handle_failure(interaction, exc)

    @star.command(name="say", description="Speak text aloud in the voice channel STAR joined")
    async def say(interaction: discord.Interaction, text: str):
        if await permit(interaction) is None:
            return
        voice = interaction.guild.voice_client if interaction.guild else None
        user_voice = getattr(interaction.user, "voice", None)
        if not voice or not voice.is_connected() or not user_voice or user_voice.channel != voice.channel:
            await problem(interaction, "Join STAR's active voice channel and run `/star join` first")
            return
        if voice.is_playing():
            await problem(interaction, "STAR is still speaking; try again when playback finishes")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            pcm, rate = await service.speak_pcm(text)
            wave_bytes = pcm_to_wav(pcm, rate)
            # discord.py's FFmpeg player reads from a BytesIO pipe; never access the user's filesystem.
            source = discord.FFmpegPCMAudio(io.BytesIO(wave_bytes), pipe=True,
                                          executable=ffmpeg_path(service.ffmpeg_dir), options="-vn")
            voice.play(source)
            await interaction.followup.send(embed=embed("✦ STAR · Speaking",
                                        "Playing STAR's synthesized voice in the channel."), ephemeral=True)
        except Exception as exc:
            await handle_failure(interaction, exc)

    @star.command(name="stop", description="Immediately stop STAR's outgoing voice playback")
    async def stop(interaction: discord.Interaction):
        if await permit(interaction) is None:
            return
        voice = interaction.guild.voice_client if interaction.guild else None
        user_voice = getattr(interaction.user, "voice", None)
        if not voice or not voice.is_connected() or not user_voice or user_voice.channel != voice.channel:
            await problem(interaction, "Join STAR's active voice channel to stop playback")
            return
        voice.stop()
        await interaction.response.send_message(embed=embed("✦ STAR · Stopped",
                                                   "Stopped outgoing speech. No audio is recorded."), ephemeral=True)

    @star.command(name="leave", description="Disconnect STAR from its voice channel")
    async def leave(interaction: discord.Interaction):
        if await permit(interaction) is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            voice = interaction.guild.voice_client if interaction.guild else None
            if voice:
                await voice.disconnect(force=True)
            await interaction.followup.send(embed=embed("✦ STAR · Disconnected",
                                                       "STAR has left the voice channel."), ephemeral=True)
        except Exception as exc:
            await handle_failure(interaction, exc)

    bot.tree.add_command(star)

    @app_commands.context_menu(name="Ask STAR about this")
    async def ask_about_message(interaction: discord.Interaction, message: discord.Message):
        key = await permit(interaction)
        if key is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            if message.attachments and message.attachments[0].is_voice_message():
                await answer_audio(interaction, message.attachments[0], key)
            elif message.content:
                response = await service.ask(key, "Explain or help with the following Discord message:\n" +
                                             message.content[:1300])
                await publish_answer(interaction, response, ephemeral=True, key=key)
            else:
                raise ValueError("Choose a message containing text or a Discord voice message")
        except Exception as exc:
            await handle_failure(interaction, exc)

    # Context menus are root application commands, not nested /star subcommands.
    bot.tree.add_command(ask_about_message)

    @bot.event
    async def on_message(message: discord.Message):
        """Private owner DM conversation; never capture arbitrary guild traffic.

        Text is ephemeral, image bytes are inspected only for this request, and
        an explicit remember command proposes (never approves) a lesson.
        """
        if not config.dm.enabled or message.guild is not None or message.author.bot:
            return
        try:
            key = service.authorized(message.author.id, None, message.channel.id)
        except PermissionError:
            return  # No response or information to unapproved users.
        action = classify_owner_dm(
            message.content or "", attachments=len(message.attachments), options=config.dm)
        if action.error:
            await message.channel.send(action.error, allowed_mentions=discord.AllowedMentions.none())
            return
        if action.kind == "ignored":
            return
        try:
            async with message.channel.typing():
                if action.kind == "text":
                    reply_text = await service.ask(key, action.prompt)
                elif action.kind == "image":
                    attachment = message.attachments[0]
                    if attachment.size > MAX_IMAGE_BYTES:
                        raise ValueError("Image exceeds the 6 MiB limit")
                    payload = await attachment.read()
                    photo = prepare_discord_image(
                        attachment.filename, attachment.content_type, attachment.size, payload)
                    reply_text = await service.inspect_image(key, action.prompt, photo)
                elif action.kind == "remember":
                    receipt = await service.propose_dm_lesson(
                        key, message_id=message.id, text=action.prompt,
                        kind=action.lesson_kind, project=config.dm.project)
                    if receipt.status == "candidate":
                        reply_text = (
                            f"Learning candidate #{receipt.lesson_id} saved for the "
                            "STAR desktop review panel. It is not trusted or applied "
                            "until you approve it there."
                        )
                    elif receipt.status == "duplicate":
                        reply_text = "This learning statement is already in STAR's review records."
                    else:
                        reply_text = (
                            "STAR did not save this statement as a lesson. "
                            "Check for sensitive data or a permission request."
                        )
                else:
                    return
        except (ValueError, PermissionError) as exc:
            reply_text = str(exc)[:400]
        except Exception as exc:
            # Never write prompts, screenshots, credentials, or model outputs to logs.
            _LOG.warning("STAR owner DM failed: %s", type(exc).__name__)
            reply_text = "STAR could not process this DM. Check its configured model and image settings."
        options = {"allowed_mentions": discord.AllowedMentions.none()}
        if len(reply_text) > 1900:
            options["file"] = discord.File(
                io.BytesIO(reply_text.encode("utf-8")), filename="star-dm-answer.txt")
            reply_text = reply_text[:1700] + "\n\nFull answer attached."
        await message.channel.send(content=reply_text, **options)

    @bot.event
    async def on_ready():
        _LOG.info("STAR Discord bot connected (guild count: %s)", len(bot.guilds))

    return bot
