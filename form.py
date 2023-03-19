import json
import discord
import os
from datetime import datetime
from discord import app_commands
from dotenv import load_dotenv


def get_int_from_env(env_name):
    env_value = os.getenv(env_name)
    if env_value is not None:
        try:
            int_value = int(env_value)
            return int_value
        except ValueError:
            return False
    return False


load_dotenv()
GUILD_ID = get_int_from_env("GUILD_ID")
if not GUILD_ID:
    print("No GUILD_ID set in the .env file, aborting...")
    quit()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Load Configuration
with open("config.json", "r") as f:
    f_data = json.load(f)
# Load Data
if not os.path.isfile("data/fviews.json"):
    views_db = {}
else:
    with open("data/fviews.json", "r") as f:
        views_db = json.load(f)
if not os.path.isfile("data/pviews.json"):
    pviews_db = {}
else:
    with open("data/pviews.json", "r") as f:
        pviews_db = json.load(f)
if not os.path.isfile("data/cache.json"):
    cache = {}
else:
    with open("data/cache.json", "r") as f:
        cache = json.load(f)


def set_cache(key, value):
    cache[key] = value
    with open("data/cache.json", "w") as f:
        json.dump(cache, f)


# ( STR, INT )
def register_fview(row_id, thread_id):
    if row_id not in views_db:
        views_db[row_id] = list()
    if thread_id not in views_db[row_id]:
        views_db[row_id].append(thread_id)
        with open("data/fviews.json", "w") as f:
            json.dump(views_db, f)


def register_pview(ch_id, msg_id, form_ids):
    if ch_id not in pviews_db:
        pviews_db[ch_id] = dict()
        pviews_db[ch_id][msg_id] = list()
    if msg_id not in pviews_db[ch_id]:
        pviews_db[ch_id][msg_id] = form_ids
        with open("data/pviews.json", "w") as f:
            json.dump(pviews_db, f)


# Emoji list: https://gist.github.com/Vexs/629488c4bb4126ad2a9909309ed6bd71
# TODO: try to use dropdowns


class MyClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def setup_hook(self) -> None:
        for c_key in views_db:
            for c_val in views_db[c_key]:
                self.add_view(ButtonsRow(c_key, c_val))
        for ch_id in pviews_db:
            for msg_id in pviews_db[ch_id]:
                # ch_id -> msg_id -> list(form_id)
                self.add_view(FormsView(ch_id, msg_id, pviews_db[ch_id][msg_id]))
        # Sync the application command with Discord.
        guild = discord.utils.get(self.guilds, id=GUILD_ID)
        await self.tree.sync(guild=guild)


def forum_exists(category, thread_name):
    for thread in category.channels:
        if thread.name == thread_name:
            return thread
    return False


async def get_ch_in_cat(guild, channel_id, category_id):
    # Get the channel object from the ID
    channel = guild.get_channel(channel_id)
    # Check if the channel exists and is in the specified category
    if channel and channel.category_id == category_id:
        return channel
    else:
        return False


async def get_category(guild):
    # INIT CATEGORY
    CAT_ID = cache["FORM_CATEGORY"]
    if not CAT_ID:
        log_msg = "Creating Forms Category"
        form_category = await guild.create_category(
            name=f_data["msg"]["category_name"], reason=log_msg
        )
        set_cache("FORM_CATEGORY", form_category.id)
    else:
        form_category = await guild.fetch_channel(CAT_ID)
    return form_category


async def get_forum(guild):
    # INIT FORUM CHANNEL
    CAT_ID = cache["FORM_CATEGORY"]
    FORUM_ID = cache["FORM_FORUM"]
    if not FORUM_ID:
        log_msg = "Creating Forms Forum"
        cat = await get_category(guild)
        forum = await guild.create_forum(
            name=f_data["msg"]["forum_name"],
            reason=log_msg,
            topic=f_data["msg"]["forum_topic"],
            category=cat,
        )
        set_cache("FORM_FORUM", forum.id)
    else:
        forum = await get_ch_in_cat(guild, FORUM_ID, CAT_ID)
    return forum


async def get_archive(guild, category_id):
    # INIT ARCHIVE CHANNEL
    LOG_ID = cache["LOG_CHANNEL"]
    if not LOG_ID:  # If channel got deleted or does not exist yet
        log_msg = "Creating Archived Forms Channel"
        cat = await get_category(guild)
        archive = await guild.create_text_channel(
            name=f_data["msg"]["archive_name"],
            category=cat,
            topic=f_data["msg"]["archive_topic"],
            reason=log_msg,
        )
        set_cache("LOG_CHANNEL", archive.id)
    else:
        archive = await get_ch_in_cat(guild, LOG_ID, category_id)
    return archive


async def update_forum_tags(forum):
    # Update tags
    for form_tmpl in f_data["forms"]:
        if form_tmpl["type"] != "modal":  # Only modals for now
            continue
        tag_found = False
        for tag in forum.available_tags:
            if tag.name == form_tmpl["name"]:
                tag_found = True
                break
        if not tag_found:
            emoji = form_tmpl.get("emoji")
            if emoji:
                await forum.create_tag(
                    name=form_tmpl["name"],
                    moderated=True,
                    emoji=discord.PartialEmoji.from_str(emoji),
                )
            else:
                await forum.create_tag(name=form_tmpl["name"], moderated=True)
    return forum.available_tags


class CustomModal(discord.ui.Modal, title="Test"):
    def __init__(self, form_template):
        super().__init__(timeout=60.0)
        self.title = form_template["name"]

        for field in form_template["fields"]:
            text_style = (
                discord.TextStyle.short
                if field["type"] == "text"
                else discord.TextStyle.paragraph
            )
            max_length = 255 if field["type"] == "text" else 1000
            self.add_item(
                discord.ui.TextInput(
                    custom_id=field["id"],
                    label=field["name"],
                    placeholder=field["placeholder"],
                    required=field["required"],
                    style=text_style,
                    max_length=max_length,
                )
            )
            """
            elif field['type'] == 'select':
                select_options = []
                for option in field['options']:
                    select_options.append(discord.SelectOption(label=option))
                self.add_item(discord.ui.Select(custom_id=field['name'], placeholder=field['placeholder'], options=select_options, min_values=field['min_values'], max_values=field['max_values']))
            """

        # Set the form template and response message
        self.form_template = form_template
        self.response_message = form_template["response_message"]

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        embed = discord.Embed(
            title=f":page_facing_up: **{self.form_template['name']}**",
            description=f"**{self.form_template['description']}**",
            color=discord.Colour.purple(),
        )
        for child in self.children:
            embed.add_field(
                name=f"{child.label}",
                value=f"{child.value}",
                inline=True if child.style == discord.TextStyle.short else False,
            )
        current_date = datetime.now().strftime("%Y/%m/%d %H:%M")
        embed.set_footer(
            icon_url=interaction.user.avatar,
            text=f"{interaction.user.name} - {current_date}",
        )

        forum_category = await get_category(interaction.guild)
        forum = await get_forum(interaction.guild)
        available_tags = await update_forum_tags(forum)
        applied_tags = []
        for tag in available_tags:
            if self.form_template["name"] == tag.name:
                applied_tags.append(tag)
                break
        thread, message = await forum.create_thread(
            name=f"{self.form_template['name']} | {interaction.user.name}",
            embed=embed,
            content=f"{interaction.user.mention}",
            applied_tags=applied_tags,
            auto_archive_duration=10080,
        )
        register_fview(self.form_template["id"], thread.id)
        await message.edit(view=ButtonsRow(self.form_template["id"], thread.id))
        await thread.add_user(interaction.user)
        # await message.add_reaction(u"\U00002705")
        # await message.add_reaction(u"\U000026d4")
        await interaction.followup.send(
            content=f"{self.response_message}", ephemeral=True
        )

    async def on_cancel(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            content="Form cancelled.", ephemeral=True
        )


class FormsView(discord.ui.View):
    def __init__(self, ch_id, msg_id, form_ids):
        super().__init__(timeout=None)
        for index, form_id in enumerate(form_ids):
            self.add_item(FormButton(ch_id, index, form_id))


class FormButton(discord.ui.Button):
    def __init__(self, ch_id, index, form_id):
        form_template = None
        for row in f_data["forms"]:
            if row["id"] == form_id:
                form_template = row
                break
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=form_template["name"],
            custom_id=f"formv{ch_id}-{form_id}-{index}",
        )
        self.form_template = form_template

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CustomModal(self.form_template))


class ButtonsRow(discord.ui.View):
    def __init__(self, row_id, thread_id):
        super().__init__(timeout=None)
        row_template = None
        for row in f_data["forms"]:
            if row["id"] == row_id:
                row_template = row
                break
        for index, btn in enumerate(row_template["buttons"]):
            if btn["type"] == "url":
                self.add_item(
                    discord.ui.Button(
                        style=discord.ButtonStyle[btn["style"]],
                        label=btn["label"],
                        url=btn["url"],
                    )
                )
            elif btn["type"] == "accept" or btn["type"] == "deny":
                self.add_item(CloseButton(row_template["id"], index, thread_id))


class CloseButton(discord.ui.Button):
    def __init__(self, row_id, index, cid):
        row_template = None
        for row in f_data["forms"]:
            if row["id"] == row_id:
                row_template = row
                break
        btn = row_template["buttons"][index]
        super().__init__(
            style=discord.ButtonStyle[btn["style"]],
            label=btn["label"],
            custom_id=f"formb{btn['type']}-{cid}",
        )
        self.cid = cid
        self.btn_type = btn["type"]

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        if self.btn_type == "deny":
            await interaction.response.send_modal(CloseReason(self.cid, self.btn_type))
        elif self.btn_type == "accept":
            await close_thread(interaction, self.cid, self.btn_type, None)


async def close_thread(interaction, cid, btn_type, reason):
    await interaction.response.defer(ephemeral=True, thinking=True)
    DISCORD_GUILD = discord.utils.get(client.guilds, id=interaction.guild_id)
    channel = await DISCORD_GUILD.fetch_channel(cid)
    CAT_ID = cache["FORM_CATEGORY"]
    archive = await get_archive(DISCORD_GUILD, CAT_ID)
    embed = interaction.message.embeds[0]
    status_emoji = "\U00002705" if btn_type == "accept" else "\U000026d4"
    status = "Approved" if btn_type == "accept" else "Denied"
    embed.add_field(
        name=f"{status_emoji} Status",
        value=f"Approved by {interaction.user.name}",
        inline=False,
    )
    if reason:
        embed.add_field(name=f"\U00002753 Reason", value=f"{reason}", inline=False)
    await archive.send(embed=embed)
    await interaction.followup.send(content=f"{status_emoji} {status}", ephemeral=True)
    await channel.delete()


class CloseReason(discord.ui.Modal, title="Reason"):
    def __init__(self, cid, btn_type):
        super().__init__(custom_id=f"formbr{btn_type}-{cid}")
        self.cid = cid
        self.btn_type = btn_type

    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Write a valid reason here...",
        max_length=300,
        style=discord.TextStyle.long,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await close_thread(interaction, self.cid, self.btn_type, self.reason.value)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            "Oops! Something went wrong.", ephemeral=True
        )


client = MyClient()
DISCORD_GUILD = discord.utils.get(client.guilds, id=GUILD_ID)


@client.tree.command(guild=DISCORD_GUILD, description=f_data["msg"]["cmd_desc"])
async def form(interaction: discord.Interaction, form_id: str):
    form_template = None
    for f in f_data["forms"]:
        if f["id"] == form_id:
            form_template = f
            break
    if not form_template:
        await interaction.response.send_message(
            f"{f_data['msg']['invalid_fid']}", ephemeral=True
        )
    elif f["type"] == "modal":
        await interaction.response.send_modal(CustomModal(form_template))


@client.tree.command(guild=DISCORD_GUILD, description=f_data["msg"]["cmd_desc"])
@app_commands.default_permissions(manage_messages=True)
async def formpost(interaction: discord.Interaction, persist: bool, form_ids: str):
    is_invalid = False
    valid_fids = list()
    form_ids = form_ids.split()
    for f in f_data["forms"]:
        valid_fids.append(f["id"])
    for f in form_ids:
        if f not in valid_fids:
            is_invalid = True
            break
    if is_invalid:
        await interaction.response.send_message(
            f"{f_data['msg']['invalid_fid']}", ephemeral=True
        )
    else:
        await interaction.response.defer(ephemeral=True, thinking=True)
        last_msg = await interaction.channel.fetch_message(
            interaction.channel.last_message_id
        )
        ch_id = interaction.channel_id
        await interaction.channel.send(
            content=last_msg.content, view=FormsView(ch_id, last_msg.id, form_ids)
        )
        if persist:
            register_pview(ch_id, last_msg.id, form_ids)
        await interaction.followup.send(content="\U00002705", ephemeral=True)


client.run(BOT_TOKEN)
