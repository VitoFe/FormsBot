import os
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
from discord import app_commands
import discord


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
    print("GUILD_ID env variable not set, aborting...", file=sys.stderr)
    try:
        sys.exit(0)
    except SystemExit:
        print("Exiting...")
BOT_TOKEN = os.getenv("BOT_TOKEN")


class Settings:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = self.load_json(config_file)
        self.lang_file = f"lang/{config['lang']}.json"
        self.lang = self.load_json(self.lang_file, default={})
        self.views_file = "data/fviews.json"
        self.views_db = self.load_json(self.views_file, default={})
        self.pviews_file = "data/pviews.json"
        self.pviews_db = self.load_json(self.pviews_file, default={})
        self.cache_file = "data/cache.json"
        self.cache = self.load_json(self.cache_file, default={"FORM_CHANNELS": {}})

    def load_json(self, file_name, default=None):
        if os.path.isfile(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                return json.load(file)
        else:
            return default

    def reload_config(self):
        self.config = self.load_json(self.config_file)
        self.lang = self.load_json(self.lang_file)

    def get_forms(self):
        return self.config['forms']

    def get_role(self, role):
        return self.config['roles'].get(role)

    def set_cache(self, key, value):
        self.cache[key] = value
        with open(self.cache_file, "w", encoding="utf-8") as file:
            json.dump(self.cache, file)

    def register_fview(self, form_id, thread_id, user_id):
        if form_id not in self.get_forms():
            print(f"Invalid form id: {form_id}")
            return
        if form_id not in self.views_db:
            self.views_db[form_id] = {}
        self.views_db[form_id][thread_id] = user_id
        with open(self.views_file, "w", encoding="utf-8") as file:
            json.dump(self.views_db, file)

    def unregister_fview(self, form_id, thread_id):
        if form_id not in self.get_forms():
            print(f"Invalid form id: {form_id}")
            return
        if form_id in self.views_db and thread_id in self.views_db[form_id]:
            del self.views_db[form_id][thread_id]
            with open(self.views_file, "w", encoding="utf-8") as file:
                json.dump(self.views_db, file)

    def register_pview(self, ch_id, msg_id, form_ids):
        print(f"Registering pview for ch_id {ch_id} msg_id {msg_id} form_ids {form_ids}")
        self.pviews_db.setdefault(ch_id, {})
        self.pviews_db[ch_id].setdefault(msg_id, form_ids)
        with open(self.pviews_file, "w", encoding="utf-8") as file:
            json.dump(self.pviews_db, file)


config = Settings("config.json")


def user_has_fview(user_id, form_id):
    if form_id in config.views_db:
        views = config.views_db[form_id]
        for view in views:
            if view[1] == user_id:
                return True
    return False


async def update_nick():
    guild = discord.utils.get(client.guilds, id=GUILD_ID)
    client_member = guild.me
    bot_nickname = config.lang["bot_nickname"]
    if client_member.nick != bot_nickname:
        await client_member.edit(nick=bot_nickname)
        print(f'Updated Nick to {bot_nickname}')


class MyClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        activity = discord.Game(name=config.lang["bot_activity_name"])
        super().__init__(intents=intents, activity=activity)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        os.system("clear")
        print(
            r"""
          ______                       ____        _   
         |  ____|                     |  _ \      | |  
         | |__ ___  _ __ _ __ ___  ___| |_) | ___ | |_ 
         |  __/ _ \| '__| '_ ` _ \/ __|  _ < / _ \| __|
         | | | (_) | |  | | | | | \__ \ |_) | (_) | |_ 
         |_|  \___/|_|  |_| |_| |_|___/____/ \___/ \__|
        """
        )
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def setup_hook(self) -> None:
        # Restore View States
        for c_key in config.views_db:
            for c_val in config.views_db[c_key]:
                self.add_view(ButtonsRow(c_key, c_val[0]))
        for ch_id in config.pviews_db:
            for msg_id in config.pviews_db[ch_id]:
                # ch_id -> msg_id -> list(form_id)
                self.add_view(view=FormsView(ch_id, config.pviews_db[ch_id][msg_id]))
        # Sync commands with Discord
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))


def get_form_data(form_id):
    return config.get_forms().get(form_id)


async def get_ch_in_cat(guild, channel_id, category_id):
    # Get the channel object from the ID
    channel = guild.get_channel(channel_id)
    # Check if the channel exists and is in the specified category
    if channel and channel.category_id == category_id:
        return channel
    return False


async def get_category(guild):
    # INIT CATEGORY
    category_id = config.cache.get("FORM_CATEGORY")
    if not category_id:
        log_msg = "Creating Forms Category"
        form_category = await guild.create_category(
            name=config.lang["category_name"], reason=log_msg
        )
        config.set_cache("FORM_CATEGORY", form_category.id)
    else:
        form_category = await guild.fetch_channel(category_id)
    return form_category


async def get_channel(guild, form_id):
    # INIT FORM CHANNEL
    category_id = config.cache.get("FORM_CATEGORY")
    forum_ch_id = config.cache["FORM_CHANNELS"].get(form_id)
    if not forum_ch_id:
        log_msg = "Creating Form Channel"
        cat = await get_category(guild)
        channel = await guild.create_text_channel(
            name=get_form_data(form_id)["name"].replace(" ", "-").lower(),
            reason=log_msg,
            topic=config.lang["forum_topic"],
            category=cat,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=True, send_messages=False
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                ),
            },
        )
        config.cache["FORM_CHANNELS"][form_id] = channel.id
        config.set_cache("FORM_CHANNELS", config.cache["FORM_CHANNELS"])
    else:
        channel = await get_ch_in_cat(guild, forum_ch_id, category_id)
    return channel


async def get_archive(guild, category_id):
    # INIT ARCHIVE CHANNEL
    log_ch_id = config.cache.get("LOG_CHANNEL")
    if not log_ch_id:  # If channel got deleted or does not exist yet
        log_msg = "Creating Archived Forms Channel"
        cat = await get_category(guild)
        role = guild.get_role(config.get_role("archive_channel"))
        archive = await guild.create_text_channel(
            name=config.lang["archive_name"],
            category=cat,
            topic=config.lang["archive_topic"],
            reason=log_msg,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False, send_messages=False
                ),
                role: discord.PermissionOverwrite(
                    read_messages=True, send_messages=False
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                ),
            },
        )
        config.set_cache("LOG_CHANNEL", archive.id)
    else:
        archive = await get_ch_in_cat(guild, log_ch_id, category_id)
    return archive


class FormModal(discord.ui.Modal, title="Test"):
    def __init__(self, form_id):
        super().__init__(timeout=60.0)
        form_template = get_form_data(form_id)
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
        # Set the form template and response message
        self.form_id = form_id
        self.response_message = form_template["response_message"]

    async def on_submit(self, interaction: discord.Interaction):
        form_template = get_form_data(self.form_id)
        await interaction.response.defer(thinking=True, ephemeral=True)
        embed = discord.Embed(
            title=f":page_facing_up: **{form_template['name']}**",
            description=f"**{form_template['description']}**",
            color=discord.Colour.purple(),
        )
        for child in self.children:
            embed.add_field(
                name=f"{child.label}",
                value=f"{child.value}",
                inline=child.style == discord.TextStyle.short,
            )
        current_date = datetime.now().strftime("%Y/%m/%d %H:%M")
        embed.set_footer(
            icon_url=interaction.user.avatar,
            text=f"{interaction.user.name} - {current_date}",
        )
        guild = interaction.guild
        role = guild.get_role(config.get_role("read_forms"))
        channel = await get_channel(guild, self.form_id)
        thread = await channel.create_thread(
            name=f"{form_template['name']} | {interaction.user.name}",
            message=None,
            type=None,
            invitable=False,
            auto_archive_duration=10080,
        )
        await thread.send(
            content=f"{role.mention} {interaction.user.mention}",
            embed=embed,
            view=ButtonsRow(self.form_id, thread.id),
            silent=True,
            allowed_mentions=discord.AllowedMentions.all(),
        )
        # Users are added by mentions
        await thread.add_user(interaction.user)
        # for member in role.members:
        #    await thread.add_user(member)
        # await message.add_reaction(u"\U00002705")
        # await message.add_reaction(u"\U000026d4")
        config.register_fview(self.form_id, thread.id, interaction.user.id)
        await interaction.followup.send(
            content=f"{self.response_message}", ephemeral=True
        )

    async def on_cancel(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            content=config.lang["cancel_message"], ephemeral=True
        )


# Permanent buttons to submit forms
class FormsView(discord.ui.View):
    def __init__(self, ch_id, form_ids):
        super().__init__(timeout=None)
        for index, form_id in enumerate(form_ids):
            self.add_item(FormButton(ch_id, index, form_id))


class FormButton(discord.ui.Button):
    def __init__(self, ch_id, index, form_id):
        form_template = get_form_data(form_id)
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=form_template["name"],
            custom_id=f"formv{ch_id}-{form_id}-{index}",
        )
        self.form_id = form_id
        self.form_template = form_template

    async def callback(self, interaction: discord.Interaction):
        if self.form_template["unique"] and user_has_fview(
                interaction.user.id, self.form_id
        ):
            await interaction.response.send_message(
                content=config.lang["error_unique"], ephemeral=True
            )
        else:
            await interaction.response.send_modal(FormModal(self.form_id))


# Buttons under the newly created thread
class ButtonsRow(discord.ui.View):
    def __init__(self, form_id, thread_id):
        super().__init__(timeout=None)
        row_template = get_form_data(form_id)
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
                self.add_item(CloseButton(form_id, index, thread_id))


class CloseButton(discord.ui.Button):
    def __init__(self, form_id, index, cid):
        row_template = get_form_data(form_id)
        btn = row_template["buttons"][index]
        super().__init__(
            style=discord.ButtonStyle[btn["style"]],
            label=btn["label"],
            custom_id=f"formb{btn['type']}-{cid}",
        )
        self.form_id = form_id
        self.cid = cid
        self.btn_type = btn["type"]

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        guild = discord.utils.get(client.guilds, id=interaction.guild_id)
        if guild.get_role(config.get_role("read_forms")) not in interaction.user.roles:
            await interaction.user.send(content=config.lang["error_perms"])
        else:
            if self.btn_type == "deny":
                await interaction.response.send_modal(
                    CloseReason(self.form_id, self.cid, self.btn_type)
                )
            elif self.btn_type == "accept":
                await close_thread(
                    interaction, self.form_id, self.cid, self.btn_type, None
                )


async def close_thread(interaction, form_id, cid, btn_type, reason):
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = discord.utils.get(client.guilds, id=interaction.guild_id)
    channel = await guild.fetch_channel(cid)
    archive = await get_archive(guild, config.cache.get("FORM_CATEGORY"))
    embed = interaction.message.embeds[0]
    status_emoji = "\U00002705" if btn_type == "accept" else "\U000026d4"
    status = (
        config.lang["approved"] if btn_type == "accept" else config.lang["denied"]
    )
    embed.add_field(
        name=f"\n{status_emoji} {status}",
        value=f"{config.lang['reviewed_by']} {interaction.user.name}",
        inline=False,
    )
    if reason:
        embed.add_field(
            name=f"\U00002753 {config.lang['reason']}",
            value=f"{reason}",
            inline=False,
        )
    await archive.send(embed=embed)
    for user in interaction.message.mentions:
        await user.send(content=config.lang["closed_message"], embed=embed)
    await interaction.followup.send(content=f"{status_emoji} {status}", ephemeral=True)
    await channel.delete()
    config.unregister_fview(form_id, cid)


class CloseReason(discord.ui.Modal, title=config.lang["reason"]):
    def __init__(self, form_id, cid, btn_type):
        super().__init__(custom_id=f"formbr{btn_type}-{cid}")
        self.cid = cid
        self.btn_type = btn_type
        self.form_id = form_id

    reason = discord.ui.TextInput(
        label=config.lang["reason"],
        placeholder=config.lang["reason_desc"],
        max_length=300,
        style=discord.TextStyle.long,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await close_thread(
            interaction, self.form_id, self.cid, self.btn_type, self.reason.value
        )

    async def on_error(
            self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            config.lang["error_message"], ephemeral=True
        )
        print(error)


client = MyClient()


@client.tree.command(
    guild=discord.Object(id=GUILD_ID), description=config.lang["cmd_desc"]
)
async def form(interaction: discord.Interaction, form_id: str):
    form_template = get_form_data(form_id)
    if not form_template:
        await interaction.response.send_message(
            f"{config.lang['invalid_fid']}", ephemeral=True
        )
    else:
        if form_template["unique"] and user_has_fview(interaction.user.id, form_id):
            await interaction.response.send_message(
                content=config.lang["error_unique"], ephemeral=True
            )
        else:
            await interaction.response.send_modal(FormModal(form_id))


@client.tree.command(
    guild=discord.Object(id=GUILD_ID), description=config.lang["cmd_desc"]
)
@app_commands.default_permissions(manage_messages=True)
async def formpost(interaction: discord.Interaction, persist: bool, form_ids: str):
    valid_fids = config.get_forms().keys()
    form_ids = form_ids.split()
    is_invalid = any(form_t not in valid_fids for form_t in form_ids)
    if is_invalid:
        await interaction.response.send_message(
            f"{config.lang['invalid_fid']}", ephemeral=True
        )
    else:
        await interaction.response.defer(ephemeral=True, thinking=True)
        ch_id = interaction.channel_id
        msg = await interaction.channel.send(view=FormsView(ch_id, form_ids))
        if persist:
            config.register_pview(ch_id, msg.id, form_ids)
        await interaction.followup.send(content="\U00002705", ephemeral=True)


@client.tree.command(
    guild=discord.Object(id=GUILD_ID), description=config.lang["cmd_desc"]
)
@app_commands.default_permissions(manage_messages=True)
async def formreload(interaction: discord.Interaction):
    config.reload_config()
    await update_nick()
    await interaction.followup.send(content="\U00002705", ephemeral=True)


client.run(BOT_TOKEN)
