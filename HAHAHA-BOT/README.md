# HAHAHA BOT

A Discord entertainment bot with 100+ registered prefix commands, games, XP, coins, polls, moderation and owner-only prank-preview controls.

## Setup
1. Use Python 3.10+.
2. Copy .env.example to .env.
3. Set DISCORD_TOKEN to a freshly regenerated Discord bot token.
4. Set OWNER_ID to your Discord numeric user ID.
5. Enable Message Content Intent and Server Members Intent in the Discord Developer Portal.
6. Run pip install -r requirements.txt, then python bot.py.

## Commands
Use !help to list commands. Create polls with !poll Question | Option A | Option B and view real reactions with !pollresult MESSAGE_ID.

Owner-only prank preview: !prankpollpreview MESSAGE_ID OPTION_NUMBER FAKE_VOTES. This is explicitly labelled simulated and does not alter real poll totals. The owner panel is !ownerpanel.

Polls, XP, coins and warnings are in memory and reset when the process restarts. Never commit .env or share your bot token.