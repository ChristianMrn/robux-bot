import discord
from discord.ext import commands
import os
import json

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
PREFIX = "!"
PRICE_PER_ROBUX = 0.70  # 0.70 pesos per Robux
OWNER_ID = 0  # Palitan mo ng Discord User ID mo kung gusto mo ikaw lang maka-addstock

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- STOCK FILE ---
STOCK_FILE = "stock.json"

def load_stock():
    try:
        with open(STOCK_FILE, "r") as f:
            return json.load(f)
    except:
        return {"robux": 0}

def save_stock(stock):
    with open(STOCK_FILE, "w") as f:
        json.dump(stock, f, indent=4)

def robux_for_pesos(pesos):
    return int(pesos / PRICE_PER_ROBUX)

def pricelist_text():
    amounts = [50, 100, 150, 200, 300, 500, 1000]
    lines = []
    for p in amounts:
        lines.append(f"₱{p} = {robux_for_pesos(p)} Robux")
    return "\n".join(lines)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot is online!")

# --- PRICELIST ---
@bot.command()
async def pricelist(ctx):
    stock = load_stock()
    embed = discord.Embed(title="💜 ROBUX PRICELIST 💜", description="₱0.70 per Robux\nFast & Legit!", color=0xA855F7)
    embed.add_field(name="Price List", value=pricelist_text(), inline=False)
    embed.add_field(name="📦 Stock", value=f"{stock['robux']} Robux available", inline=False)
    embed.add_field(name="How to Buy", value="Type `!buy <pesos>` ex: `!buy 100`\nThen open a ticket with `!ticket`", inline=False)
    embed.set_footer(text="Payment: GCash | DM for orders")
    await ctx.send(embed=embed)

@bot.command(aliases=["prices", "price", "menu"])
async def prices_cmd(ctx):
    await pricelist(ctx)

# --- STOCK ---
@bot.command()
async def stock(ctx):
    stock = load_stock()
    await ctx.send(f"📦 **Current Stock:** {stock['robux']} Robux")

@bot.command()
@commands.has_permissions(administrator=True)
async def addstock(ctx, amount: int):
    stock = load_stock()
    stock["robux"] += amount
    save_stock(stock)
    await ctx.send(f"✅ Added {amount} Robux. New stock: {stock['robux']} Robux")

@addstock.error
async def addstock_error(ctx, error):
    await ctx.send("❌ You need Administrator to use this. Usage: `!addstock 1000`")

# --- BUY / ORDER - AUTO DEDUCT ---
@bot.command()
async def buy(ctx, pesos: int = None):
    if pesos is None:
        await ctx.send("Usage: `!buy <pesos>` ex: `!buy 100`")
        return
    if pesos < 50:
        await ctx.send("❌ Minimum order is ₱50")
        return

    need = robux_for_pesos(pesos)
    stock = load_stock()

    if stock["robux"] < need:
        await ctx.send(f"❌ Out of stock! Only {stock['robux']} Robux left. Try smaller amount or contact seller.")
        return

    # Auto-deduct
    stock["robux"] -= need
    save_stock(stock)

    embed = discord.Embed(title="🧾 ORDER CREATED", color=0x22C55E)
    embed.add_field(name="Buyer", value=ctx.author.mention, inline=False)
    embed.add_field(name="Amount Paid", value=f"₱{pesos}", inline=True)
    embed.add_field(name="You Get", value=f"{need} Robux", inline=True)
    embed.add_field(name="Remaining Stock", value=f"{stock['robux']} Robux", inline=False)
    embed.add_field(name="Next Step", value="1. Pay via GCash\n2. Send screenshot in ticket\n3. Type `!ticket` to open ticket", inline=False)
    await ctx.send(embed=embed)

@buy.error
async def buy_error(ctx, error):
    await ctx.send("Usage: `!buy <pesos>` ex: `!buy 100`")

# --- TICKET SYSTEM ---
@bot.command()
async def ticket(ctx):
    guild = ctx.guild
    if guild is None:
        await ctx.send("Use this in a server, not DM.")
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }

    # Add admin role if exists
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await guild.create_text_channel(f"ticket-{ctx.author.name}", overwrites=overwrites)
    await channel.send(f"🎫 Hello {ctx.author.mention}!\nPlease send your order here.\nFormat:\n**IGN:**\n**Amount:** ₱\n**GCash Screenshot:**\n\nSeller will assist you soon. Type `!close` to close ticket.")
    await ctx.send(f"✅ Ticket created: {channel.mention}")

@bot.command()
async def close(ctx):
    if ctx.channel.name.startswith("ticket-"):
        await ctx.send("Closing ticket in 3 seconds...")
        import asyncio
        await asyncio.sleep(3)
        await ctx.channel.delete()
    else:
        await ctx.send("This is not a ticket channel.")

@bot.command()
async def helpme(ctx):
    await ctx.send("**Commands:**\n`!pricelist` - Show prices\n`!stock` - Check stock\n`!buy <pesos>` - Buy Robux\n`!ticket` - Open ticket\n`!close` - Close ticket\n`!addstock <amount>` - Admin only")

bot.run(TOKEN)
