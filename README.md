# Discord Forms Bot :robot:

Discord Forms Bot is a discord.py bot that allows you to create and manage forms on Discord. You can use this bot to collect feedback, surveys, applications, or any other data from your Discord members. :speech_balloon:

## Features :sparkles:

- Create custom forms with multiple questions and different types of inputs using a user-friendly `config.json` :pencil:
- Forms are created in a specific category and each form has a dedicated Thread channel :mailbox:
- Archive channel for logging :page_facing_up:
- Permissions to read and moderate forms are tied to specific configurable Roles :busts_in_silhouette:

## Installation :computer:

To run this bot, you need to have Python 3.8 or higher and the following dependencies installed:
- [discord.py (2.2.2+)](https://pypi.org/project/discord.py/)
- [python-dotenv (1.0.0+)](https://pypi.org/project/python-dotenv/)

#### You can install them using pip: `pip install -r requirements.txt`

You also need to create a bot account on Discord and invite it to your server. For more information, [see this guide](https://discordpy.readthedocs.io/en/stable/discord.html).

## Configuration :gear:

Before running the bot, you need to setup some environment variables:
- `BOT_TOKEN`: The token of your Bot application, from [Discord Developer Portal](https://discord.com/developers/applications)
- `GUILD_ID`: The ID of your Discord Server. To get your Discord server ID, you need to turn on the developer mode in your Discord app settings. This will let you copy the ID of any server, user, channel, or message by right-clicking on it and choosing Copy ID from the context menu.
Required permissions integer: 157236587600

## License :page_with_curl:

This project is licensed under the MIT License - see the LICENSE file included in this project for details.

## Disclaimer :warning:

This project is not endorsed or affiliated with discord.py. Discord.py is licensed under the MIT License and its source code can be found at https://github.com/Rapptz/discord.py. The author of discord.py (Rapptz) is not liable for any damages or issues arising from the use of discord.py in this project. This project respects the terms and conditions of the MIT License and acknowledges the authorship and contribution of discord.py. 
