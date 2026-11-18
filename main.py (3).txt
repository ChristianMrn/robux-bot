import discord
from discord.ext import commands
import os
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- KEEP ALIVE FOR RENDER ---
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online!")
    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

TOKEN = os.getenv("TOKEN")
PREFIX = "!"
PRICE_PER_ROBUX = 0.70

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
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
    return "\n".join([f"₱{p} = {robux_for_pesos(p)} Robux" for p in amounts])

def make_catalogue_embed(stock):
    embed = discord.Embed(title="🛒 ROBUX PRICE CATALOGUE", description="PH's Discounted Robux Store\nLive prices, synced with our ordering system.", color=0xA855F7)
    embed.add_field(name="💜 Robux Transfer:", value="🟢 Available", inline=False)
    embed.add_field(name="📦 Stock:", value=f"**{stock['robux']} Robux available**", inline=False)
    embed.add_field(name="💡 How to buy:", value="Press a button below. Pindot ka lang!", inline=False)
    embed.add_field(name="Payment:", value="GCash", inline=False)
    embed.set_footer(text="Robux Shop • ₱0.70 per Robux • Fast & Legit")
    return embed

async def create_auto_ticket(guild, user, pesos, need, stock):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    channel = await guild.create_text_channel(f"ticket-{user.name}-{pesos}", overwrites=overwrites)
    embed = discord.Embed(title="🧾 ORDER CREATED - AUTO TICKET", color=0x22C55E)
    embed.add_field(name="Buyer", value=user.mention, inline=False)
    embed.add_field(name="Amount", value=f"₱{pesos}", inline=True)
    embed.add_field(name="You Get", value=f"{need} Robux", inline=True)
    embed.add_field(name="Remaining Stock", value=f"{stock['robux']} Robux", inline=False)
    embed.add_field(name="Next Step", value="1. Pay via GCash\n2. Send GCash screenshot HERE\n3. Send your Roblox Username / IGN", inline=False)
    await channel.send(f"{user.mention} Ticket mo auto-created na!", embed=embed)
    return channel

class BuyAmountView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        for amt in [50, 100, 150, 200, 300, 500, 1000]:
            btn = discord.ui.Button(label=f"₱{amt} = {robux_for_pesos(amt)} Robux", style=discord.ButtonStyle.primary, custom_id=f"buy_{amt}")
            btn.callback = self.make_buy_callback(amt)
            self.add_item(btn)

    def make_buy_callback(self, pesos):
        async def callback(interaction: discord.Interaction):
            need = robux_for_pesos(pesos)
            stock = load_stock()
            if stock["robux"] < need:
                await interaction.response.send_message(f"❌ Out of stock! Only {stock['robux']} Robux left.", ephemeral=True)
                return
            stock["robux"] -= need
            save_stock(stock)
            try:
                channel = await create_auto_ticket(interaction.guild, interaction.user, pesos, need, stock)
                await interaction.response.send_message(f"✅ Order Created! Auto ticket mo: {channel.mention}\n₱{pesos} = {need} Robux\nPunta ka dun at send mo GCash screenshot + IGN.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"✅ Order Created: ₱{pesos} = {need} Robux. Pero hindi ako makagawa ng ticket. Error: {e}", ephemeral=True)
        return callback

class CatalogueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 View Robux Prices", style=discord.ButtonStyle.primary)
    async def view_prices(self, interaction: discord.Interaction, button: discord.ui.Button):
        stock = load_stock()
        embed = discord.Embed(title="💜 ROBUX PRICELIST 💜", description="₱0.70 per Robux", color=0xA855F7)
        embed.add_field(name="Price List", value=pricelist_text(), inline=False)
        embed.add_field(name="📦 Stock", value=f"{stock['robux']} Robux", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🛒 Buy Now", style=discord.ButtonStyle.success)
    async def buy_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Choose Amount", description="Pindutin mo kung magkano bibilhin mo:", color=0x22C55E)
        await interaction.response.send_message(embed=embed, view=BuyAmountView(), ephemeral=True)

    @discord.ui.button(label="🎫 Open Ticket", style=discord.ButtonStyle.secondary)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        channel = await guild.create_text_channel(f"ticket-{user.name}", overwrites=overwrites)
        await channel.send(f"🎫 Hello {user.mention}!\nSend your order here.\n**IGN:**\n**Amount:** ₱\n**GCash Screenshot:**")
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="📦 Check Stock", style=discord.ButtonStyle.secondary)
    async def check_stock(self, interaction: discord.Interaction, button: discord.ui.Button):
        stock = load_stock()
        await interaction.response.send_message(f"📦 **Current Stock:** {stock['robux']} Robux", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Bot is online!")
    bot.add_view(CatalogueView())

@bot.command()
async def shop(ctx):
    stock = load_stock()
    await ctx.send(embed=make_catalogue_embed(stock), view=CatalogueView())

@bot.command()
async def pricelist(ctx):
    stock = load_stock()
    embed = discord.Embed(title="💜 ROBUX PRICELIST 💜", description="₱0.70 per Robux", color=0xA855F7)
    embed.add_field(name="Price List", value=pricelist_text(), inline=False)
    embed.add_field(name="📦 Stock", value=f"{stock['robux']} Robux", inline=False)
    await ctx.send(embed=embed)

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

@bot.command()
async def buy(ctx, pesos: int = None):
    if pesos is None:
        await ctx.send("Usage: `!buy <pesos>` ex: `!buy 100` or use `!shop`")
        return
    if pesos < 50:
        await ctx.send("❌ Minimum order is ₱50")
        return
    need = robux_for_pesos(pesos)
    stock = load_stock()
    if stock["robux"] < need:
        await ctx.send(f"❌ Out of stock! Only {stock['robux']} Robux left.")
        return
    stock["robux"] -= need
    save_stock(stock)
    channel = await create_auto_ticket(ctx.guild, ctx.author, pesos, need, stock)
    await ctx.send(f"✅ Order Created: ₱{pesos} = {need} Robux. Auto ticket: {channel.mention}")

@bot.command()
async def ticket(ctx):
    guild = ctx.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    channel = await guild.create_text_channel(f"ticket-{ctx.author.name}", overwrites=overwrites)
    await channel.send(f"🎫 Hello {ctx.author.mention}! Send your order here.")
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

bot.run(TOKEN)
