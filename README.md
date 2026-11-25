# HAHAHA BOT

A Discord bot with entertainment commands, games, XP/coins, polls, and permission-checked moderation tools.

## Website

A responsive static website and command directory is included in [website/](website/index.html). It uses the supplied dark dashboard visual style and is independent of the bot process.

To publish it with GitHub Pages:
1. Open the repository **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch `main` and folder `/website`, then save.
4. GitHub Pages will show the published website URL in the Pages settings.

The site is a project/command showcase. It does not expose the bot token or claim a live connection to Discord.

## Deploy the Discord bot on Render

This repository includes `render.yaml` configured as a **Background Worker**. A Discord bot needs a persistent outbound gateway connection; it is not a normal web service.

1. In Render, choose **New + → Blueprint** and connect this repository.
2. Render reads `render.yaml` and creates the worker.
3. In the worker's **Environment** settings, add:
   - `DISCORD_TOKEN`: your newly regenerated Discord bot token
   - `OWNER_ID`: your numeric Discord user ID
   - `BOT_PREFIX`: optional; defaults to `!`
4. Deploy. Check the Render logs for `HAHAHA BOT online`.

In the Discord Developer Portal, enable **Message Content Intent** and **Server Members Intent** for the bot. Invite it with only the permissions it needs.

## Local run

Use Python 3.10+, install with `pip install -r requirements.txt`, set the environment variables from `.env.example`, then run `python bot.py`.

## Notes

- Never put your real bot token in GitHub. If it was ever pasted or committed, regenerate it in the Discord Developer Portal.
- Owner-only controls are permission checked and hidden from the normal `!help` list.
- `!prankpollpreview` creates a clearly labelled simulation only; it does not change real poll totals.
- XP, coins, warnings, and poll lookup data are in memory and reset when the worker restarts.
- Use `!help` in Discord to see the available commands.
