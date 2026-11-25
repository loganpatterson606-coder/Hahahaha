import os, random, asyncio
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
"joke":["Why did the scarecrow win? Outstanding in his field.","I told my PC a joke. It crashed laughing.","Parallel lines have so much in common."],
"fact":["Octopuses have three hearts.","Bananas are berries; strawberries aren't.","A day on Venus is longer than its year."],
"quote":["Stay curious. Stay chaotic.","Be yourself; everyone else is taken."],
"roast":["Your Wi-Fi has more connection than your jokes.","You're proof autocorrect can't fix everything.","You bring joy… especially when you leave."],
"compliment":["Your vibe is immaculate.","You make the group chat better.","Your brain has premium DLC."],
"pickup":["Are you Wi-Fi? I feel a connection.","Are you a keyboard? You're just my type."],
"motivate":["One step at a time. You've got this.","Progress beats perfection."],
"fortune":["A surprise W is approaching.","Avoid arguing with a toaster today."],
"riddle":["What has keys but no locks? A piano.","What gets wetter as it dries? A towel."],
"meme":["Me opening the fridge for the ninth time: new update?","When the teacher says pair up and you become a group of one."],
"dadjoke":["I'm reading a book about anti-gravity. Impossible to put down.","I only know 25 letters. I don't know y."],
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
"sleep":["Go hydrate and get some rest 😴","Your pillow misses you."],
"coffee":["☕ One cup of motivation.","Espresso yourself."],
"mathjoke":["Why was 6 afraid of 7? Because 7 8 9."],
"wouldyourather":["Fight one horse-sized duck or 100 duck-sized horses?","Unlimited pizza or unlimited tacos?"],
"neverhaveiever":["Never have I ever waved back at someone who wasn't waving.","Never forgotten why I entered a room."],
"rate":["10/10 iconic","7/10 mildly suspicious","100/10 certified legend"],
"insult":["You absolute soggy biscuit.","You malfunctioning toaster."],
"ship":["You two have 99% meme compatibility 💞"],
}
for name, lines in BITS.items():
    async def generated(ctx, _lines=lines):
        await say(ctx, random.choice(_lines))
    bot.hybrid_command(name=name)(generated)

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
@bot.hybrid_command(hidden=True)
@owner_only()
async def prankpollpreview(ctx, message_id:int, option_number:int, fake_votes:int=100):
    p=polls.get(message_id)
    if not p or not 1<=option_number<=len(p["options"]) or not 1<=fake_votes<=10000:
        return await say(ctx,"Invalid poll, option, or preview count.")
    await say(ctx,f"SIMULATED PRANK PREVIEW — NOT REAL VOTES\n{p['options'][option_number-1]}: {fake_votes} imaginary votes. Actual totals unchanged.")
@bot.hybrid_command(hidden=True)
@owner_only()
async def ownerpanel(ctx): await say(ctx,f"Owner panel for {OWNER_ID}: prankpollpreview, shutdown")
@bot.hybrid_command(hidden=True)
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
