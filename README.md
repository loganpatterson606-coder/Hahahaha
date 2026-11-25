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

## Per-server customisation

Server members with **Manage Server** can customise every built-in fun-response category (including `brainrot`, `fakeerror`, jokes, roasts, memes, NPC lines, and more):

- `/addresponse category response` — add another possible response.
- `/setresponse category response` — replace that category's custom responses with one response.
- `/resetresponse category` — remove custom responses and return to the defaults.
- `/settings` — list categories and show which ones have custom responses.

Category names are shown by `/settings`. Custom responses are stored in a local SQLite database. On Render, attach a persistent disk and set `BOT_DATABASE` to a path on that disk if you want settings to survive redeploys; otherwise the platform may discard the database during a new deploy.

## Polls, giveaways, and Spotify

- `/pollbuilder` opens a form for a poll question, options, duration, and outcome mode. Normal polls count button votes. The selected-member mode is explicitly labelled as an admin-selected outcome in the public post.
- `/giveaway` opens a form for the prize, duration, and winner mode. Random mode selects from members who entered. Selected mode publicly labels the chosen member as admin-selected, not a random winner.
- `/song` opens Spotify search and returns track links. Add `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` to Render environment variables from a Spotify Developer application.
- Spotify's Web API does not provide audio streams for a Discord bot to relay in voice chat. This implementation searches Spotify and links to tracks; it does not play audio in a Discord voice channel.
- `/customizer` includes the response editor, poll builder, giveaway builder, and Spotify search.

Admin-selected poll and giveaway outcomes are deliberately disclosed in the posted message; they are not presented as genuine random or vote-counted results.
