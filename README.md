# HAHAHA BOT

A Discord bot with entertainment commands, games, XP/coins, polls, and permission-checked moderation tools.

## Deploy on Render

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
