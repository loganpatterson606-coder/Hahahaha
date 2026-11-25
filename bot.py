import os, random, asyncio, sqlite3
from datetime import datetime, timezone
from collections import Counter
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
PREFIX = os.getenv("BOT_PREFIX", "!")
if not TOKEN or not OWNER_ID:
    raise RuntimeError("Set DISCORD_TOKEN and OWNER_ID in .env")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
class HahahaBot(commands.Bot):
    async def setup_hook(self):
        # Register slash commands with Discord when the bot starts.
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash commands with Discord.")
        except Exception as exc:
            print(f"Slash-command sync failed: {type(exc).__name__}: {exc}")
            raise

bot = HahahaBot(command_prefix=commands.when_mentioned_or(PREFIX), intents=intents, help_command=None)
started = datetime.now(timezone.utc)
xp, coins, warnings, polls = Counter(), Counter(), Counter(), {}

# Per-server response customisations. SQLite keeps settings across ordinary bot restarts.
DB_PATH = os.getenv("BOT_DATABASE", os.path.join(os.path.dirname(__file__), "bot_data.sqlite3"))
db = sqlite3.connect(DB_PATH)
db.execute("""CREATE TABLE IF NOT EXISTS custom_responses (
    guild_id INTEGER NOT NULL, category TEXT NOT NULL, response TEXT NOT NULL,
    PRIMARY KEY (guild_id, category, response)
)""")
db.commit()

def custom_responses(guild_id, category):
    if not guild_id:
        return []
    rows = db.execute(
        "SELECT response FROM custom_responses WHERE guild_id=? AND category=? ORDER BY rowid",
        (guild_id, category)
    ).fetchall()
    return [row[0] for row in rows]

def response_pool(ctx, category, defaults):
    return list(defaults) + custom_responses(ctx.guild.id if ctx.guild else None, category)

def owner_only():
    return commands.check(lambda ctx: ctx.author.id == OWNER_ID)

async def say(ctx, text):
    await ctx.reply(text, mention_author=False)

@bot.event
async def on_ready():
    print(f"HAHAHA BOT online: {bot.user} ({bot.user.id})")

@bot.event
async def on_message(message):
    if not message.author.bot:
        xp[message.author.id] += random.randint(2, 8)
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    if isinstance(error, commands.CheckFailure): return await say(ctx, "Owner-only command.")
    if isinstance(error, commands.MissingRequiredArgument): return await say(ctx, f"Missing: {error.param.name}")
    await say(ctx, f"Command error: {type(error).__name__}")

@bot.hybrid_command(name="help")
async def help_cmd(ctx):
    names = sorted(c.name for c in bot.commands if not c.hidden)
    await say(ctx, f"HAHAHA BOT — {len(names)} commands\n" + " • ".join(f"{PREFIX}{n}" for n in names[:110]))

@bot.hybrid_command()
async def ping(ctx): await say(ctx, f"Pong! {round(bot.latency*1000)}ms")
@bot.hybrid_command()
async def uptime(ctx): await say(ctx, str(datetime.now(timezone.utc)-started).split(".")[0])
@bot.hybrid_command()
async def serverinfo(ctx): await say(ctx, f"{ctx.guild.name} • {ctx.guild.member_count} members")
@bot.hybrid_command()
async def userinfo(ctx, member:discord.Member=None):
    m=member or ctx.author
    await say(ctx, f"{m} • ID {m.id} • joined {m.joined_at}")
@bot.hybrid_command()
async def avatar(ctx, member:discord.Member=None): await say(ctx, (member or ctx.author).display_avatar.url)
@bot.hybrid_command()
async def saytext(ctx, *, text): await say(ctx, text)
@bot.hybrid_command()
async def choose(ctx, *, choices):
    opts=[x.strip() for x in choices.split("|") if x.strip()]
    await say(ctx, random.choice(opts) if len(opts)>1 else "Use option 1 | option 2.")
@bot.hybrid_command()
async def coinflip(ctx): await say(ctx, random.choice(["Heads","Tails"]))
@bot.hybrid_command()
async def dice(ctx, sides:int=6):
    if not 2<=sides<=1000: return await say(ctx,"Choose 2–1000 sides.")
    await say(ctx, f"🎲 {random.randint(1,sides)}")

BITS = {
"fact":["Octopuses have three hearts.","Bananas are berries; strawberries aren't.","A day on Venus is longer than its year."],
"roast":["Your Wi-Fi has more connection than your jokes.","You're proof autocorrect can't fix everything.","You bring joy… especially when you leave."],
"riddle":["What has keys but no locks? A piano.","What gets wetter as it dries? A towel."],
"meme":["Me opening the fridge for the ninth time: new update?","When the teacher says pair up and you become a group of one."],
"truth":["What's a tiny thing that improves your day?","What's your most irrational fear?"],
"dare":["Send a message using only emojis.","Talk like a pirate for three messages."],
"vibe":["chaotic good ✨","sleepy legend 😴","main character energy 🎬"],
"mood":["unreasonably silly","focused and thriving","one inconvenience from logging off"],
"emoji":["😂","💀","🗿","🔥","😭","🤡","👑"],
"animal":["red panda 🐼","capybara 🦫","axolotl 🦎","penguin 🐧"],
"color":["purple","electric blue","sunset orange","mint green"],
"snack":["crisps","cookies","nachos","fruit"],
"movie":["a chaotic heist comedy","a space adventure","a mystery with 17 plot twists"],
"song":["a dramatic movie soundtrack","an upbeat pop anthem","lo-fi beats"],
"challenge":["No saying lol for ten minutes.","Describe your day as a movie title."],
"brainrot":["Certified yap session.","The vibes are NOT passing the vibe check."],
"npc":["Greetings, traveller. The quest marker is behind you.","I used to be an adventurer like you…"],
"clapback":["That take needs a software update.","Bold words from someone with autocorrect on."],
"excuse":["My goldfish scheduled a meeting.","The Wi-Fi and I are going through something."],
"fakeerror":["ERROR 418: I'm a teapot.","404: Motivation not found."],
"typing":["*is typing…*","typing faster than the speed of light"],
"dramatic":["THIS IS THE MOST IMPORTANT MOMENT IN SERVER HISTORY.","Cue dramatic music 🎻"],
"wouldyourather":["Fight one horse-sized duck or 100 duck-sized horses?","Unlimited pizza or unlimited tacos?"],
"neverhaveiever":["Never have I ever waved back at someone who wasn't waving.","Never forgotten why I entered a room."],
"rate":["10/10 iconic","7/10 mildly suspicious","100/10 certified legend"],
"insult":["That was certainly a decision.","Please update your argument and try again."],
"ship":["You two have 99% meme compatibility 💞"],
}
def make_generated_command(lines):
    async def generated(ctx):
        category = generated.__name__
        await say(ctx, random.choice(response_pool(ctx, category, lines)))
    return generated

for name, lines in BITS.items():
    callback = make_generated_command(lines)
    callback.__name__ = name
    bot.hybrid_command(name=name)(callback)

@bot.hybrid_command(name="addresponse", description="Add a custom response to any fun command")
@commands.has_permissions(manage_guild=True)
async def addresponse(ctx, category: str, *, response: str):
    category = category.lower().strip()
    if not ctx.guild:
        return await say(ctx, "Use this command inside a server.")
    if category not in BITS:
        return await say(ctx, "Unknown category. Use /settings to see every customisable category.")
    response = response.strip()
    if not response or len(response) > 1800:
        return await say(ctx, "Response must be between 1 and 1800 characters.")
    db.execute(
        "INSERT OR IGNORE INTO custom_responses (guild_id, category, response) VALUES (?, ?, ?)",
        (ctx.guild.id, category, response)
    )
    db.commit()
    await say(ctx, f"Added a custom {category} response for this server.")

@bot.hybrid_command(name="setresponse", description="Replace custom responses for a fun command")
@commands.has_permissions(manage_guild=True)
async def setresponse(ctx, category: str, *, response: str):
    category = category.lower().strip()
    if not ctx.guild:
        return await say(ctx, "Use this command inside a server.")
    if category not in BITS:
        return await say(ctx, "Unknown category. Use /settings to see every customisable category.")
    response = response.strip()
    if not response or len(response) > 1800:
        return await say(ctx, "Response must be between 1 and 1800 characters.")
    db.execute("DELETE FROM custom_responses WHERE guild_id=? AND category=?", (ctx.guild.id, category))
    db.execute(
        "INSERT INTO custom_responses (guild_id, category, response) VALUES (?, ?, ?)",
        (ctx.guild.id, category, response)
    )
    db.commit()
    await say(ctx, f"Replaced this server's custom {category} responses.")

@bot.hybrid_command(name="resetresponse", description="Remove custom responses for a fun command")
@commands.has_permissions(manage_guild=True)
async def resetresponse(ctx, category: str):
    category = category.lower().strip()
    if not ctx.guild:
        return await say(ctx, "Use this command inside a server.")
    if category not in BITS:
        return await say(ctx, "Unknown category. Use /settings to see every customisable category.")
    db.execute("DELETE FROM custom_responses WHERE guild_id=? AND category=?", (ctx.guild.id, category))
    db.commit()
    await say(ctx, f"Reset {category} to the built-in responses.")

@bot.hybrid_command(name="settings", description="Show this server's fun-command customisations")
async def settings(ctx):
    if not ctx.guild:
        return await say(ctx, "Use this command inside a server.")
    rows = db.execute(
        "SELECT category, COUNT(*) FROM custom_responses WHERE guild_id=? GROUP BY category ORDER BY category",
        (ctx.guild.id,)
    ).fetchall()
    lines = [f"{category}: {count} custom response(s)" for category, count in rows]
    categories = ", ".join(sorted(BITS))
    await say(ctx, "**HAHAHA BOT customisation**\n"
                   + ("\n".join(lines) if lines else "No custom responses yet.")
                   + f"\n\n**Available categories:** {categories}"
                   + "\nUse /customizer to open the interactive customisation menu. Requires Manage Server.")


class ResponseConfigModal(discord.ui.Modal):
    def __init__(self, category: str):
        super().__init__(title=f"Customize: {category}"[:45], timeout=300)
        self.category = category
        self.response = discord.ui.TextInput(
            label="Custom response",
            placeholder="Enter the text the bot should use...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.response)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            return await interaction.response.send_message("Use this inside a server.", ephemeral=True)
        value = str(self.response.value).strip()
        db.execute(
            "INSERT OR IGNORE INTO custom_responses (guild_id, category, response) VALUES (?, ?, ?)",
            (interaction.guild_id, self.category, value)
        )
        db.commit()
        await interaction.response.send_message(
            f"Saved a custom {self.category} response for this server.",
            ephemeral=True
        )


class FakeProfileModal(discord.ui.Modal, title="Build a simulated member card"):
    display_name = discord.ui.TextInput(label="Display name", placeholder="e.g. ghost.exe", max_length=32)
    status = discord.ui.TextInput(label="Status", placeholder="online / idle / dnd / offline", max_length=20)
    activity = discord.ui.TextInput(label="Activity", placeholder="e.g. Playing ranked", max_length=80, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        allowed = {"online": "🟢 Online", "idle": "🌙 Idle", "dnd": "⛔ Do Not Disturb", "offline": "⚫ Offline"}
        state = str(self.status.value).strip().lower()
        if state not in allowed:
            return await interaction.response.send_message("Status must be online, idle, dnd, or offline.", ephemeral=True)
        embed = discord.Embed(title="SIMULATED MEMBER PREVIEW", color=discord.Color.dark_grey())
        embed.add_field(name="Display name", value=str(self.display_name.value), inline=True)
        embed.add_field(name="Status (fictional)", value=allowed[state], inline=True)
        embed.add_field(name="Activity (fictional)", value=str(self.activity.value).strip() or "None", inline=False)
        embed.set_footer(text="Preview only — does not create an account or change real member presence.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.hybrid_command(name="customize", description="Open a pop-up form to customise a bot response")
@commands.has_permissions(manage_guild=True)
async def customize(ctx, category: str):
    category = category.strip().lower()
    if not ctx.guild:
        return await say(ctx, "Use this inside a server.")
    if category not in BITS:
        return await say(ctx, "Unknown category. Run /settings to see available categories.")
    if ctx.interaction is None:
        return await say(ctx, "Use the slash command /customize to open the pop-up form.")
    await ctx.interaction.response.send_modal(ResponseConfigModal(category))


@bot.hybrid_command(name="fakeprofile", description="Create a clearly labelled simulated member/status preview")
async def fakeprofile(ctx):
    if ctx.interaction is None:
        return await say(ctx, "Use /fakeprofile to open the pop-up form.")
    await ctx.interaction.response.send_modal(FakeProfileModal())


class CustomCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=name, description=f"Edit {name} output")
            for name in sorted(BITS)[:22]
        ] + [
            discord.SelectOption(label="Poll builder", value="__poll__", description="Configure a poll"),
            discord.SelectOption(label="Giveaway builder", value="__giveaway__", description="Configure a giveaway"),
            discord.SelectOption(label="Spotify search", value="__song__", description="Search Spotify")
        ]
        super().__init__(placeholder="Choose what you want to customise", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("Manage Server permission required.", ephemeral=True)
        selected = self.values[0]
        if selected == "__poll__":
            return await interaction.response.send_modal(PollBuilderModal())
        if selected == "__giveaway__":
            return await interaction.response.send_modal(GiveawayModal())
        if selected == "__song__":
            return await interaction.response.send_modal(SpotifyModal())
        await interaction.response.send_modal(ResponseConfigModal(selected))


class CustomizerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(CustomCategorySelect())


class RiggedPollModal(discord.ui.Modal, title="Create a rigged poll preview"):
    question = discord.ui.TextInput(label="Poll question", max_length=180)
    options = discord.ui.TextInput(label="Options (separate with |)", placeholder="Option A | Option B | Option C", max_length=400)
    winner = discord.ui.TextInput(label="Preselected winner", max_length=80)
    vote_count = discord.ui.TextInput(label="Fake vote count", placeholder="e.g. 250", max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        choices = [item.strip() for item in str(self.options.value).split("|") if item.strip()]
        chosen = str(self.winner.value).strip()
        try:
            count = int(str(self.vote_count.value))
        except ValueError:
            return await interaction.response.send_message("Vote count must be a number.", ephemeral=True)
        if len(choices) < 2 or len(choices) > 8 or chosen not in choices or not 1 <= count <= 100000:
            return await interaction.response.send_message(
                "Use 2–8 options, choose a winner exactly as written, and enter 1–100000 simulated votes.",
                ephemeral=True
            )
        embed = discord.Embed(title="RIGGED POLL — SIMULATION", description=str(self.question.value), color=discord.Color.dark_grey())
        for option in choices:
            value = f"{count:,} simulated votes" if option == chosen else "0 simulated votes"
            embed.add_field(name=option, value=value, inline=False)
        embed.set_footer(text="Fictional preview only. No real votes, reactions, or poll results were changed.")
        await interaction.response.send_message(embed=embed)


@bot.hybrid_command(name="customizer", description="Open the interactive customisation menu")
@commands.has_permissions(manage_guild=True)
async def customizer(ctx):
    if not ctx.guild:
        return await say(ctx, "Use this inside a server.")
    await ctx.send("**HAHAHA BOT CUSTOMIZER**\nSelect a command category below to open its edit form.", view=CustomizerView())


@bot.hybrid_command(name="riggedpoll", description="Create a clearly labelled rigged poll simulation")
async def riggedpoll(ctx):
    if ctx.interaction is None:
        return await say(ctx, "Use /riggedpoll to open the poll builder.")
    await ctx.interaction.response.send_modal(RiggedPollModal())


@bot.hybrid_command(name="faker", description="Open a fake member/status profile builder")
async def faker(ctx):
    if ctx.interaction is None:
        return await say(ctx, "Use /faker to open the profile builder.")
    await ctx.interaction.response.send_modal(FakeProfileModal())


class PollBuilderModal(discord.ui.Modal, title="Create a poll"):
    question = discord.ui.TextInput(label="Question", max_length=180)
    options = discord.ui.TextInput(label="Options separated by |", max_length=400)
    duration = discord.ui.TextInput(label="Duration in minutes", max_length=5)
    mode = discord.ui.TextInput(label="Mode: random or selected", max_length=10)
    member_id = discord.ui.TextInput(label="Selected member ID", required=False, max_length=25)

    async def on_submit(self, interaction):
        choices = [v.strip() for v in str(self.options.value).split("|") if v.strip()]
        try:
            minutes = int(str(self.duration.value))
        except ValueError:
            return await interaction.response.send_message("Duration must be a number.", ephemeral=True)
        mode = str(self.mode.value).strip().lower()
        if not 2 <= len(choices) <= 5 or not 1 <= minutes <= 10080 or mode not in ("random", "selected"):
            return await interaction.response.send_message("Invalid options, duration, or mode.", ephemeral=True)
        target = None
        if mode == "selected":
            try:
                target = interaction.guild.get_member(int(str(self.member_id.value)))
            except (ValueError, TypeError):
                target = None
            if target is None:
                return await interaction.response.send_message("Enter a valid member ID.", ephemeral=True)
        view = PollVoteView(choices, minutes * 60, target, interaction.channel)
        embed = discord.Embed(title="POLL: " + str(self.question.value), description="\n".join(choices))
        embed.add_field(name="Outcome", value="Vote-counted" if target is None else "ADMIN-SELECTED: " + target.mention)
        embed.set_footer(text="Admin-selected outcome is disclosed; this is not a democratic result." if target else "One vote per member.")
        await interaction.response.send_message("Poll posted.", ephemeral=True)
        view.message = await interaction.channel.send(embed=embed, view=view)


class PollVoteView(discord.ui.View):
    def __init__(self, choices, duration, target, channel):
        super().__init__(timeout=duration)
        self.choices, self.target, self.channel, self.votes = choices, target, channel, {}
        self.message = None
        for i, choice in enumerate(choices):
            button = discord.ui.Button(label=choice[:80], style=discord.ButtonStyle.primary)
            button.callback = self.callback_for(i)
            self.add_item(button)

    def callback_for(self, index):
        async def vote(interaction):
            self.votes[interaction.user.id] = index
            await interaction.response.send_message("Vote saved.", ephemeral=True)
        return vote

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.target:
            result = "ADMIN-SELECTED OUTCOME: " + self.target.mention + " (not vote-counted)."
        else:
            counts = [list(self.votes.values()).count(i) for i in range(len(self.choices))]
            high = max(counts) if counts else 0
            winners = [self.choices[i] for i, count in enumerate(counts) if count == high]
            result = "Vote result: " + ", ".join(winners) + " (" + str(high) + " votes)."
        if self.message:
            await self.message.edit(view=self)
            await self.message.reply("Poll closed. " + result)


class GiveawayModal(discord.ui.Modal, title="Create a giveaway"):
    prize = discord.ui.TextInput(label="Prize", max_length=100)
    duration = discord.ui.TextInput(label="Duration in minutes", max_length=5)
    mode = discord.ui.TextInput(label="Mode: random or selected", max_length=10)
    member_id = discord.ui.TextInput(label="Selected winner ID", required=False, max_length=25)

    async def on_submit(self, interaction):
        try:
            minutes = int(str(self.duration.value))
        except ValueError:
            return await interaction.response.send_message("Duration must be a number.", ephemeral=True)
        mode = str(self.mode.value).strip().lower()
        if not 1 <= minutes <= 10080 or mode not in ("random", "selected"):
            return await interaction.response.send_message("Invalid duration or mode.", ephemeral=True)
        target = None
        if mode == "selected":
            try:
                target = interaction.guild.get_member(int(str(self.member_id.value)))
            except (ValueError, TypeError):
                target = None
            if target is None:
                return await interaction.response.send_message("Enter a valid member ID.", ephemeral=True)
        view = GiveawayView(minutes * 60, target)
        embed = discord.Embed(title="GIVEAWAY: " + str(self.prize.value), description="Press Enter to join.")
        embed.add_field(name="Winner selection", value="Random entrant" if target is None else "ADMIN-SELECTED: " + target.mention)
        embed.set_footer(text="Admin-selected winner is disclosed; this is not a random draw." if target else "Winner selected randomly from entrants.")
        await interaction.response.send_message("Giveaway posted.", ephemeral=True)
        view.message = await interaction.channel.send(embed=embed, view=view)
        asyncio.create_task(view.finish())


class GiveawayView(discord.ui.View):
    def __init__(self, duration, target):
        super().__init__(timeout=None)
        self.duration, self.target, self.entries, self.message = duration, target, set(), None
        button = discord.ui.Button(label="Enter giveaway", style=discord.ButtonStyle.success, custom_id="giveaway_join_" + str(random.randint(1, 99999999)))
        button.callback = self.enter
        self.add_item(button)

    async def enter(self, interaction):
        self.entries.add(interaction.user.id)
        await interaction.response.send_message("Entry saved.", ephemeral=True)

    async def finish(self):
        await asyncio.sleep(self.duration)
        for child in self.children:
            child.disabled = True
        if self.target:
            result = "ADMIN-SELECTED WINNER: " + self.target.mention + " (not a random draw)."
        elif self.entries:
            result = "Random winner: <@" + str(random.choice(list(self.entries))) + ">"
        else:
            result = "No entries."
        if self.message:
            await self.message.edit(view=self)
            await self.message.reply("Giveaway closed. " + result)


class SpotifyModal(discord.ui.Modal, title="Search Spotify"):
    query = discord.ui.TextInput(label="Song or artist", max_length=100)

    async def on_submit(self, interaction):
        client_id, secret = os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not secret:
            return await interaction.response.send_message("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in Render.", ephemeral=True)
        try:
            import aiohttp
            async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(client_id, secret)) as session:
                async with session.post("https://accounts.spotify.com/api/token", data={"grant_type": "client_credentials"}) as response:
                    if response.status != 200:
                        return await interaction.response.send_message("Spotify authentication failed.", ephemeral=True)
                    token = (await response.json())["access_token"]
                async with session.get("https://api.spotify.com/v1/search", headers={"Authorization": "Bearer " + token}, params={"q": str(self.query.value), "type": "track", "limit": 5}) as response:
                    if response.status != 200:
                        return await interaction.response.send_message("Spotify search failed.", ephemeral=True)
                    data = await response.json()
            tracks = data.get("tracks", {}).get("items", [])
            if not tracks:
                return await interaction.response.send_message("No tracks found.", ephemeral=True)
            embed = discord.Embed(title="Spotify search results")
            for track in tracks:
                artists = ", ".join(a["name"] for a in track.get("artists", []))
                url = track.get("external_urls", {}).get("spotify", "")
                embed.add_field(name=(track["name"] + " — " + artists)[:256], value="[Open in Spotify](" + url + ")", inline=False)
            embed.set_footer(text="Spotify search/link only; the Web API does not stream audio to Discord.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as exc:
            print("Spotify error:", type(exc).__name__, str(exc))
            await interaction.response.send_message("Spotify search unavailable.", ephemeral=True)


@bot.hybrid_command(name="pollbuilder")
@commands.has_permissions(manage_guild=True)
async def pollbuilder(ctx):
    if ctx.interaction is None:
        return await say(ctx, "Use slash command /pollbuilder.")
    await ctx.interaction.response.send_modal(PollBuilderModal())


@bot.hybrid_command(name="giveaway")
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx):
    if ctx.interaction is None:
        return await say(ctx, "Use slash command /giveaway.")
    await ctx.interaction.response.send_modal(GiveawayModal())


@bot.hybrid_command(name="song")
async def song(ctx):
    if ctx.interaction is None:
        return await say(ctx, "Use slash command /song.")
    await ctx.interaction.response.send_modal(SpotifyModal())


@bot.hybrid_command()
async def guess(ctx, number:int):
    if not 1<=number<=10: return await say(ctx,"Pick 1–10.")
    n=random.randint(1,10); await say(ctx,"Correct!" if n==number else f"Nope — it was {n}.")
@bot.hybrid_command()
async def rps(ctx, choice:str):
    opts=["rock","paper","scissors"]; choice=choice.lower()
    if choice not in opts: return await say(ctx,"Use rock, paper, or scissors.")
    cpu=random.choice(opts)
    win=(choice,cpu) in [("rock","scissors"),("paper","rock"),("scissors","paper")]
    await say(ctx,f"You: {choice} • Me: {cpu} — {'Draw!' if choice==cpu else 'You win!' if win else 'I win!'}")
@bot.hybrid_command()
async def slots(ctx):
    row=[random.choice(["🍒","🍋","💎","7️⃣","🍀"]) for _ in range(3)]
    coins[ctx.author.id]+=10 if len(set(row))==1 else 1
    await say(ctx," | ".join(row)+(" JACKPOT +10!" if len(set(row))==1 else " +1 coin"))
@bot.hybrid_command()
async def balance(ctx): await say(ctx,f"{coins[ctx.author.id]} coins")
@bot.hybrid_command()
async def daily(ctx):
    coins[ctx.author.id]+=25; await say(ctx,"Daily reward: +25 coins.")
@bot.hybrid_command()
async def leaderboard(ctx):
    rows=coins.most_common(10)
    await say(ctx,"Coin leaderboard\n"+("\n".join(f"{i+1}. <@{u}> — {v}" for i,(u,v) in enumerate(rows)) or "No coins yet."))
@bot.hybrid_command()
async def level(ctx): await say(ctx,f"XP {xp[ctx.author.id]} • Level {xp[ctx.author.id]//100}")
@bot.hybrid_command()
async def roll(ctx, maximum:int=100):
    if not 1<=maximum<=1000000: return await say(ctx,"Maximum: 1–1,000,000.")
    await say(ctx,str(random.randint(1,maximum)))
@bot.hybrid_command()
async def trivia(ctx):
    q,a=random.choice([("Red Planet?","Mars"),("Hexagon sides?","6"),("Largest ocean?","Pacific")])
    await say(ctx,f"{q} ||{a}||")

@bot.hybrid_command()
async def poll(ctx, *, prompt):
    parts=[p.strip() for p in prompt.split("|") if p.strip()]
    if not 3<=len(parts)<=11: return await say(ctx,f"Use {PREFIX}poll Question | Option A | Option B.")
    q,opts=parts[0],parts[1:]
    msg=await ctx.send("📊 "+q+"\n"+"\n".join(f"{i+1}. {o}" for i,o in enumerate(opts))+"\nReact to vote. Results count real reactions.")
    emojis=["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for e in emojis[:len(opts)]: await msg.add_reaction(e)
    polls[msg.id]={"options":opts,"channel":ctx.channel.id}
@bot.hybrid_command()
async def pollresult(ctx, message_id:int):
    p=polls.get(message_id)
    if not p: return await say(ctx,"Poll not found (poll data lasts until restart).")
    msg=await ctx.channel.fetch_message(message_id); es=["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    result=[]
    for i,o in enumerate(p["options"]):
        r=discord.utils.get(msg.reactions,emoji=es[i]); result.append(f"{o}: {max(0,r.count-1) if r else 0}")
    await say(ctx,"Actual votes\n"+"\n".join(result))
@bot.hybrid_command(hidden=True, with_app_command=False)
@owner_only()
async def prankpollpreview(ctx, message_id:int, option_number:int, fake_votes:int=100):
    p=polls.get(message_id)
    if not p or not 1<=option_number<=len(p["options"]) or not 1<=fake_votes<=10000:
        return await say(ctx,"Invalid poll, option, or preview count.")
    await say(ctx,f"SIMULATED PRANK PREVIEW — NOT REAL VOTES\n{p['options'][option_number-1]}: {fake_votes} imaginary votes. Actual totals unchanged.")
@bot.hybrid_command(hidden=True, with_app_command=False)
@owner_only()
async def ownerpanel(ctx): await say(ctx,f"Owner panel for {OWNER_ID}: prankpollpreview, shutdown")
@bot.hybrid_command(hidden=True, with_app_command=False)
@owner_only()
async def shutdown(ctx):
    await say(ctx,"Bot shutting down."); await bot.close()

@bot.hybrid_command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member:discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason); await say(ctx,f"Kicked {member}.")
@bot.hybrid_command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member:discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason); await say(ctx,f"Banned {member}.")
@bot.hybrid_command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount:int=5):
    if not 1<=amount<=100: return await say(ctx,"Choose 1–100.")
    deleted=await ctx.channel.purge(limit=amount+1); await ctx.send(f"Deleted {len(deleted)-1}.",delete_after=5)
@bot.hybrid_command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds:int):
    if not 0<=seconds<=21600: return await say(ctx,"Choose 0–21600 seconds.")
    await ctx.channel.edit(slowmode_delay=seconds); await say(ctx,f"Slowmode: {seconds}s.")
@bot.hybrid_command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    ow=ctx.channel.overwrites_for(ctx.guild.default_role); ow.send_messages=False
    await ctx.channel.set_permissions(ctx.guild.default_role,overwrite=ow); await say(ctx,"Channel locked.")
@bot.hybrid_command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    ow=ctx.channel.overwrites_for(ctx.guild.default_role); ow.send_messages=None
    await ctx.channel.set_permissions(ctx.guild.default_role,overwrite=ow); await say(ctx,"Channel unlocked.")
@bot.hybrid_command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member:discord.Member, *, reason="No reason provided"):
    warnings[(ctx.guild.id,member.id)]+=1; await say(ctx,f"{member.mention} warned. Total: {warnings[(ctx.guild.id,member.id)]}. {reason}")
@bot.hybrid_command()
async def hug(ctx, member:discord.Member): await say(ctx,f"{ctx.author.mention} hugs {member.mention}!")
@bot.hybrid_command()
async def slap(ctx, member:discord.Member): await say(ctx,f"Cartoon bonk for {member.mention}!")
@bot.hybrid_command()
async def highfive(ctx, member:discord.Member): await say(ctx,f"{ctx.author.mention} high-fives {member.mention}!")
@bot.hybrid_command()
async def bonk(ctx, member:discord.Member): await say(ctx,f"BONK! {member.mention}, meme jail.")
@bot.hybrid_command()
async def reverse(ctx, *, text): await say(ctx,text[::-1][:1900])
@bot.hybrid_command()
async def claptext(ctx, *, text): await say(ctx," 👏 ".join(text.split())[:1900])
@bot.hybrid_command()
async def mocktext(ctx, *, text): await say(ctx,"".join(c.upper() if i%2 else c.lower() for i,c in enumerate(text))[:1900])
@bot.hybrid_command()
async def spoilertext(ctx, *, text): await say(ctx,f"||{text}||")
@bot.hybrid_command()
async def membercount(ctx): await say(ctx,f"{ctx.guild.member_count}")
@bot.hybrid_command()
async def userid(ctx, member:discord.Member=None): await say(ctx,f"{(member or ctx.author).id}")
@bot.hybrid_command()
async def serverid(ctx): await say(ctx,f"{ctx.guild.id}")
@bot.hybrid_command()
async def timestamp(ctx): await say(ctx,f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>")
@bot.hybrid_command()
async def countdown(ctx, seconds:int):
    if not 1<=seconds<=10: return await say(ctx,"Choose 1–10.")
    m=await ctx.send(str(seconds))
    for n in range(seconds-1,0,-1):
        await asyncio.sleep(1); await m.edit(content=str(n))
    await asyncio.sleep(1); await m.edit(content="GO!")

ALIASES={"haha":"joke","lol":"joke","lmao":"joke","roastme":"roast","hype":"compliment","magic8":"fortune","vibecheck":"vibe","randomemoji":"emoji","randomcolor":"color","randomsnack":"snack","randomanimal":"animal","randommovie":"movie","randomsong":"song","dailychallenge":"challenge","yeet":"dramatic","bruh":"brainrot","skillissue":"roast","wholesome":"compliment","dad_joke":"dadjoke","fakecrash":"fakeerror","error":"fakeerror","coin":"coinflip","flip":"coinflip","8ball":"fortune","jokeplease":"joke","factplease":"fact","quoteplease":"quote","moodcheck":"mood","sleepy":"sleep","coffeeplease":"coffee","clap":"clapback","randomnumber":"roll","riddleme":"riddle","server":"serverinfo","whois":"userinfo","pfp":"avatar","commands":"help","roastbattle":"roast","goodvibes":"compliment","badvibes":"insult","fortune_cookie":"fortune","randomfact":"fact","randomquote":"quote","randomriddle":"riddle","randomjoke":"joke","randomrate":"rate","shipname":"ship","memeplease":"meme","npcmode":"npc","truthplease":"truth","dareplease":"dare","randomchallenge":"challenge"}
for alias,target in ALIASES.items():
    if bot.get_command(target) is None:
        continue
    async def alias_cmd(ctx, _target=target):
        await bot.get_command(_target).callback(ctx)
    bot.command(name=alias)(alias_cmd)

async def handle_http(reader, writer):
    """Serve the root website and a lightweight Render health endpoint."""
    try:
        request = await asyncio.wait_for(reader.readline(), timeout=5)
        if not request:
            return
        parts = request.decode("latin-1").strip().split()
        method, path = (parts[0], parts[1]) if len(parts) >= 2 else ("", "/")
        while True:
            header = await asyncio.wait_for(reader.readline(), timeout=5)
            if header in (b"\r\n", b"\n", b""):
                break

        if method not in ("GET", "HEAD"):
            status, body, content_type = "405 Method Not Allowed", b"Method Not Allowed", "text/plain; charset=utf-8"
        elif path.split("?", 1)[0] in ("/", "/index.html"):
            with open(os.path.join(os.path.dirname(__file__), "index.html"), "rb") as page:
                body = page.read()
            status, content_type = "200 OK", "text/html; charset=utf-8"
        elif path.split("?", 1)[0] == "/health":
            body = b"HAHAHA BOT is running"
            status, content_type = "200 OK", "text/plain; charset=utf-8"
        else:
            body = b"Not Found"
            status, content_type = "404 Not Found", "text/plain; charset=utf-8"

        headers = (
            f"HTTP/1.1 {status}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "Cache-Control: no-store\r\n\r\n"
        ).encode("ascii")
        writer.write(headers)
        if method != "HEAD":
            writer.write(body)
        await writer.drain()
    except (asyncio.TimeoutError, ConnectionError, BrokenPipeError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionError:
            pass


async def main():
    port = int(os.getenv("PORT", "10000"))
    server = await asyncio.start_server(handle_http, "0.0.0.0", port)
    print(f"HAHAHA BOT website listening on port {port}")
    try:
        async with server:
            await bot.start(TOKEN)
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
