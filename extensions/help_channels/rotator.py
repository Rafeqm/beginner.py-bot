from discord import Message, RawReactionActionEvent, TextChannel
from extensions.help_channels.channel_manager import ChannelManager
import dippy.labels


class HelpRotatorExtension(dippy.Extension):
    client: dippy.client.Client
    log: dippy.logging.Logging
    labels: dippy.labels.storage.StorageInterface
    manager: ChannelManager

    @dippy.Extension.listener("message")
    async def on_message(self, message: Message):
        category = message.channel.category
        if not category or not category.guild:
            return

        if message.author.bot:
            return

        if message.content.startswith("!"):
            return

        categories = await self.manager.get_categories(category.guild)
        if not categories:
            return

        actions = {
            "help-archive": self.manager.update_archived_channel,
            "getting-help": self.manager.update_help_channel,
        }
        for help_type, category_id in categories.items():
            if category.id == category_id and help_type in actions:
                await actions[help_type](message.channel, message.author)
                break

    @dippy.Extension.listener("raw_reaction_add")
    async def on_reaction_add(self, reaction: RawReactionActionEvent):
        emoji = reaction.emoji.name
        if emoji not in self.manager.reaction_topics and emoji != "🙋":
            return

        channel: TextChannel = self.client.get_channel(reaction.channel_id)
        categories = await self.manager.get_categories(channel.guild)

        if channel.category.id != categories["get-help"] or "hidden" in channel.name:
            return

        member = await channel.guild.fetch_member(reaction.user_id)
        if member.bot:
            return

        await self.manager.update_get_help_channel(
            channel, member, self.manager.reaction_topics[emoji]
        )
