from datetime import datetime, timedelta
from discord import Member, Message, utils
from extensions.help_channels.channel_manager import ChannelManager
import dippy.labels
import dippy.logging
import re
import time


class HelpRotatorCommandsExtension(dippy.Extension):
    client: dippy.client.Client
    log: dippy.logging.Logging
    labels: dippy.labels.storage.StorageInterface
    manager: ChannelManager

    def __init__(self, *args):
        super().__init__(*args)
        self._topic_limit = 0

    @dippy.Extension.command("!done")
    async def done(self, message: Message):
        category = message.channel.category
        if not category or not category.guild:
            return

        if message.author.bot:
            return

        categories = await self.manager.get_categories(category.guild)
        if not categories:
            return

        if category.id != categories["getting-help"]:
            return

        lock = (
            message.author.guild_permissions.kick_members
            and "lock" in message.content.casefold()
        )

        helper = utils.get(message.guild.roles, name="helpers")
        owner = await self.labels.get("text_channel", message.channel.id, "owner")
        if helper not in message.author.roles and message.author.id != owner:
            return

        await self.manager.archive_channel(message.channel, remove_owner=lock)

    @dippy.Extension.listener("message")
    async def on_message(self, message: Message):
        if "!free" in message.content:
            categories = await self.manager.get_categories(message.guild)
            category = message.guild.get_channel(categories["get-help"])
            channel = category.channels[-1]
            await message.channel.send(
                f"You can claim {channel.mention} to ask your question."
            )

    @dippy.Extension.command("!claim")
    async def claim(self, message: Message):
        member: Member = message.author
        helpers = utils.get(message.guild.roles, name="helpers")
        is_a_helper = helpers in message.author.roles
        if message.mentions and is_a_helper:
            member = message.mentions[0]

        last_claimed, channel_id = await self.labels.get(
            "user", member.id, "last-claimed-channel", (None, None)
        )
        if last_claimed and datetime.utcnow() - datetime.fromisoformat(
            last_claimed
        ) < timedelta(minutes=15):
            channel = self.client.get_channel(channel_id)
            action_message = (
                f"{member.mention} you've already claimed {channel.mention}. If you need to change the topic use the "
                f"topic command when in the channel.\n```\n!topic [topic]\n```"
            )
        else:
            topic, *_ = re.match(
                r"!claim (\w.*?\S)?\s*(?:<|$)", message.content
            ).groups()
            if topic:
                topic = self.manager.sluggify(topic)

            if topic and not is_a_helper and not self.manager.allowed_topic(topic):
                await message.channel.send(
                    "That is not an allowed topic.\nAllowed Topics:\n"
                    + (", ".join(self.manager.allowed_topics())),
                    delete_after=60,
                )
                return

            channel = (await self.manager.get_archive_channels(message.guild))[0]
            await self.manager.update_get_help_channel(channel, member, topic)
            action_message = f"{member.mention} {channel.mention} has been claimed for you to ask and discuss your question in."
        await message.channel.send(action_message, delete_after=60)

    @dippy.Extension.command("!topic")
    async def topic(self, message: Message):
        await message.delete()

        rate_limit = 60
        if time.time() - self._topic_limit < rate_limit:
            await message.channel.send(
                f"Please wait {rate_limit - int(time.time() - self._topic_limit)} seconds to set the topic.",
                delete_after=10,
            )
            return

        categories = await self.manager.get_categories(message.guild)
        if message.channel.category.id not in categories.values():
            return

        owner_id = await self.manager.get_owner(message.channel, just_id=True)

        helpers = utils.get(message.guild.roles, name="helpers")
        is_a_helper = helpers in message.author.roles
        if not is_a_helper and owner_id != message.author.id:
            return

        *_, topic = message.content.partition(" ")
        topic = self.manager.sluggify(topic)

        if not topic:
            await message.channel.send("You must provide a topic", delete_after=10)
            return

        if not is_a_helper and not self.manager.allowed_topic(topic):
            await message.channel.send(
                "That is not an allowed topic.\nAllowed Topics:\n"
                + (", ".join(self.manager.allowed_topics())),
                delete_after=60,
            )
            return

        self._topic_limit = time.time()
        await self.manager.set_channel_topic(message.channel, topic)