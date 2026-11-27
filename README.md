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

## Per-command customisation

Each built-in fun-response command has its own **Customize this command** button attached to its response. Run a command such as `/roast`, `/joke`, or `/meme`, then press that command's button to open its response editor. There is no central customizer or generic settings command. Customisation requires **Manage Server**.

Custom responses are stored per server in SQLite. On Render, attach a persistent disk and set `BOT_DATABASE` to a path on that disk if you want settings to survive redeploys; otherwise the database may be lost when the service is replaced.

## Polls, giveaways, and Spotify

- `/poll` opens its own form when used without a prompt. The form configures the question, options, duration, and outcome mode. Normal polls count button votes. The selected-member mode is explicitly labelled as an admin-selected outcome in the public post.
- `/giveaway` opens a form for the prize, duration, and winner mode. Random mode selects from members who entered. Selected mode publicly labels the chosen member as admin-selected, not a random winner.
- `/song` opens Spotify search and returns track links. Add `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` to Render environment variables from a Spotify Developer application.
- Spotify's Web API does not provide audio streams for a Discord bot to relay in voice chat. This implementation searches Spotify and links to tracks; it does not play audio in a Discord voice channel.

Admin-selected poll and giveaway outcomes are deliberately disclosed in the posted message; they are not presented as genuine random or vote-counted results.
