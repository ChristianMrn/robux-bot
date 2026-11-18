import discord
from discord.ext import commands
import os
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from http.server import ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is online!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting web server on 0.0.0.0:{port} ...", flush=True)
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        print(f"Web server listening on port {port}", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"Web server failed: {e}", flush=True)

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
BANNER_FILE = "banner.json"
pending_orders = {}

def load_stock():
    try:
        with open(STOCK_FILE, "r") as f:
            return json.load(f)
    except:
        return {"robux": 0}

def save_stock(stock):
    with open(STOCK_FILE, "w") as f:
        json.dump(stock, f, indent=4)

def load_banner():
    try:
        with open(BANNER_FILE, "r") as f:
            data = json.load(f)
            return data.get("url", None)
    except:
        return None

def save_banner(url):
    with open(BANNER_FILE, "w") as f:
        json.dump({"url": url}, f, indent=4)

def robux_for_pesos(pesos):
    return int(pesos / PRICE_PER_ROBUX)

def pricelist_text():
    amounts = [50, 100, 150, 200, 300, 500, 1000]
    return "\n".join([f"₱{p} = {robux_for_pesos(p)} Robux" for p in amounts])

def make_catalogue_embed(stock):
    embed = discord.Embed(title="🛒 ROBUX PRICE CATALOGUE", description="PH's Discounted Robux Store\nLive prices, synced with our ordering system.", color=0xA855F7)
    banner = load_banner()
    if banner:
        embed.set_image(url=banner)
    embed.add_field(name="💜 Robux Transfer:", value="🟢 Available", inline=False)
    embed.add_field(name="📦 Stock:", value=f"**{stock['robux']} Robux available**", inline=False)
    embed.add_field(name="💡 How to buy:", value="Press a button below. Pindot ka lang!", inline=False)
    embed.add_field(name="Payment:", value="GCash", inline=False)
    embed.set_footer(text="Robux Shop • ₱0.70 per Robux • Fast & Legit")
    return embed

async def create_pending_ticket(guild, user, pesos, need):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    channel = await guild.create_text_channel(f"ticket-{user.name}-{pesos}", overwrites=overwrites)
    pending_orders[channel.id] = {"buyer_id": user.id, "buyer_name": str(user), "pesos": pesos, "need": need}
    return channel

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="✅ Confirm - Paid na", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Seller/admin lang pwede mag-confirm.", ephemeral=True)
            return
        order = pending_orders.get(interaction.channel.id)
        if not order:
            await interaction.response.send_message("❌ Wala nang pending order dito.", ephemeral=True)
            return
        stock = load_stock()
        if stock["robux"] < order["need"]:
            await interaction.response.send_message(f"❌ Kulang stock! Need {order['need']} pero {stock['robux']} lang.", ephemeral=True)
            return
        stock["robux"] -= order["need"]
        save_stock(stock)
        del pending_orders[interaction.channel.id]
        embed = discord.Embed(title="✅ TRANSACTION CONFIRMED", color=0x22C55E)
        embed.add_field(name="Buyer", value=f"<@{order['buyer_id']}>", inline=False)
        embed.add_field(name="Amount", value=f"₱{order['pesos']}", inline=True)
        embed.add_field(name="Robux Sent", value=f"{order['need']} Robux", inline=True)
        embed.add_field(name="Remaining Stock", value=f"{stock['robux']} Robux", inline=False)
        await interaction.response.send_message(embed=embed)
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Seller/admin lang pwede mag-cancel.", ephemeral=True)
            return
        order = pending_orders.pop(interaction.channel.id, None)
        if not order:
            await interaction.response.send_message("Wala nang pending order.", ephemeral=True)
            return
        await interaction.response.send_message(f"❌ Order cancelled. Hindi nabawasan stock. Stock pa rin: {load_stock()['robux']} Robux.")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

class AdminSettingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.button(label="➕ Add Stock", style=discord.ButtonStyle.success)
    async def add_stock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin lang pwede.", ephemeral=True)
            return
        await interaction.response.send_message("Type mo: `!addstock <amount>`\nExample: `!addstock 1000`", ephemeral=True)
    @discord.ui.button(label="➖ Remove Stock", style=discord.ButtonStyle.danger)
    async def remove_stock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin lang pwede.", ephemeral=True)
            return
        await interaction.response.send_message("Type mo: `!removestock <amount>`\nExample: `!removestock 500`", ephemeral=True)
    @discord.ui.button(label="✏️ Set Stock", style=discord.ButtonStyle.primary)
    async def set_stock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin lang pwede.", ephemeral=True)
            return
        await interaction.response.send_message("Type mo: `!setstock <amount>`\nExample: `!setstock 2000`", ephemeral=True)
    @discord.ui.button(label="🖼️ Set Banner", style=discord.ButtonStyle.secondary)
    async def set_banner_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin lang pwede.", ephemeral=True)
            return
        await interaction.response.send_message("Para magpalit ng banner:\n1. Mag-attach ka ng pic\n2. Type mo `!setbanner` sabay nung pic\nPara alisin: `!removebanner`", ephemeral=True)
    @discord.ui.button(label="🗑️ Reset Stock", style=discord.ButtonStyle.secondary)
    async def reset_stock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin lang pwede.", ephemeral=True)
            return
        stock = load_stock()
        stock["robux"] = 0
        save_stock(stock)
        await interaction.response.send_message("🗑️ Stock reset to 0.", ephemeral=True)

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
            try:
                channel = await create_pending_ticket(interaction.guild, interaction.user, pesos, need)
                embed = discord.Embed(title="🧾 PENDING ORDER - Waiting for Payment", description="Hindi pa nabawasan stock. Magbabawas lang pag ni-confirm ni seller.", color=0xF59E0B)
                embed.add_field(name="Buyer", value=interaction.user.mention, inline=False)
                embed.add_field(name="Amount to Pay", value=f"₱{pesos}", inline=True)
                embed.add_field(name="You Will Get", value=f"{need} Robux", inline=True)
                embed.add_field(name="Current Stock (hindi pa bawas)", value=f"{stock['robux']} Robux", inline=False)
                embed.add_field(name="Next Step", value="1. Pay via GCash\n2. Send screenshot + IGN HERE\n3. Antayin si seller mag-Confirm", inline=False)
                await channel.send(f"{interaction.user.mention} Ticket mo auto-created!", embed=embed, view=ConfirmView())
                await interaction.response.send_message(f"✅ Pending order! Ticket mo: {channel.mention}\n₱{pesos} = {need} Robux\nHindi pa nabawasan stock.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)
        return callback

class CatalogueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="💰 View Robux Prices", style=discord.ButtonStyle.primary)
    async def view_prices(self, interaction: discord.Interaction, button: discord.ui.Button):
        stock = load_stock()
        embed = discord.Embed(title="💜 ROBUX PRICELIST 💜", description="₱0.70 per Robux", color=0xA855F7)
        banner = load_banner()
        if banner:
            embed.set_image(url=banner)
        embed.add_field(name="Price List", value=pricelist_text(), inline=False)
        embed.add_field(name="📦 Stock", value=f"{stock['robux']} Robux", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    @discord.ui.button(label="🛒 Buy Now", style=discord.ButtonStyle.success)
    async def buy_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Choose Amount", description="Pindutin mo kung magkano bibilhin mo:\nStock HINDI pa mababawas hanggat hindi nag-confirm si seller.", color=0x22C55E)
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

@bot.command()
async def shop(ctx):
    stock = load_stock()
    await ctx.send(embed=make_catalogue_embed(stock), view=CatalogueView())

@bot.command()
async def pricelist(ctx):
    stock = load_stock()
    embed = discord.Embed(title="💜 ROBUX PRICELIST 💜", description="₱0.70 per Robux", color=0xA855F7)
    banner = load_banner()
    if banner:
        embed.set_image(url=banner)
    embed.add_field(name="Price List", value=pricelist_text(), inline=False)
    embed.add_field(name="📦 Stock", value=f"{stock['robux']} Robux", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def stock(ctx):
    stock = load_stock()
    await ctx.send(f"📦 **Current Stock:** {stock['robux']} Robux")

@bot.command()
@commands.has_permissions(administrator=True)
async def setbanner(ctx):
    if not ctx.message.attachments:
        await ctx.send("❌ Walang pic! Ganito:\n1. Mag-attach ka ng pic\n2. Type mo `!setbanner` sa same message")
        return
    url = ctx.message.attachments[0].url
    save_banner(url)
    embed = discord.Embed(title="🖼️ Banner Updated!", description="Na-palitan na yung banner!", color=0xA855F7)
    embed.set_image(url=url)
    await ctx.send(embed=embed)
    await ctx.send("Test mo: `!shop` - dapat may pic na sa taas!")

@bot.command()
@commands.has_permissions(administrator=True)
async def removebanner(ctx):
    with open(BANNER_FILE, "w") as f:
        json.dump({"url": None}, f)
    await ctx.send("🗑️ Banner removed.")

@bot.command()
@commands.has_permissions(administrator=True)
async def admin(ctx):
    stock = load_stock()
    banner = load_banner()
    embed = discord.Embed(title="⚙️ ADMIN SETTINGS", description="Ikaw lang makakakita nito. Admin only.", color=0xFF6B00)
    embed.add_field(name="📦 Current Stock", value=f"{stock['robux']} Robux", inline=False)
    embed.add_field(name="🖼️ Banner", value="May banner na ✅" if banner else "Walang banner - type `!setbanner` + attach pic", inline=False)
    embed.add_field(name="Commands", value="`!addstock` - Dagdag\n`!removestock` - Bawas\n`!setstock` - Palitan exact\n`!setbanner` + attach pic - Palit banner\n`!removebanner` - Alisin banner\n`!confirm` - Confirm order", inline=False)
    await ctx.send(embed=embed, view=AdminSettingsView())

@bot.command()
@commands.has_permissions(administrator=True)
async def addstock(ctx, amount: int):
    stock = load_stock()
    stock["robux"] += amount
    save_stock(stock)
    await ctx.send(f"✅ Added {amount} Robux. New stock: {stock['robux']} Robux")

@bot.command()
@commands.has_permissions(administrator=True)
async def removestock(ctx, amount: int):
    stock = load_stock()
    if amount > stock["robux"]:
        await ctx.send(f"❌ Hindi pwede. Stock mo lang ay {stock['robux']} Robux.")
        return
    stock["robux"] -= amount
    save_stock(stock)
    await ctx.send(f"➖ Removed {amount} Robux. New stock: {stock['robux']} Robux")

@bot.command()
@commands.has_permissions(administrator=True)
async def setstock(ctx, amount: int):
    stock = load_stock()
    old = stock["robux"]
    stock["robux"] = amount
    save_stock(stock)
    await ctx.send(f"✏️ Stock changed: {old} -> {amount} Robux")

@bot.command()
@commands.has_permissions(administrator=True)
async def confirm(ctx):
    order = pending_orders.get(ctx.channel.id)
    if not order:
        await ctx.send("❌ Walang pending order dito.")
        return
    stock = load_stock()
    if stock["robux"] < order["need"]:
        await ctx.send(f"❌ Kulang stock!")
        return
    stock["robux"] -= order["need"]
    save_stock(stock)
    del pending_orders[ctx.channel.id]
    await ctx.send(f"✅ Confirmed! ₱{order['pesos']} = {order['need']} Robux. Remaining: {stock['robux']} Robux")

@bot.command()
async def buy(ctx, pesos: int = None):
    if pesos is None:
        await ctx.send("Usage: `!buy <pesos>` or use `!shop`")
        return
    if pesos < 50:
        await ctx.send("❌ Minimum order is ₱50")
        return
    need = robux_for_pesos(pesos)
    stock = load_stock()
    if stock["robux"] < need:
        await ctx.send(f"❌ Out of stock! Only {stock['robux']} Robux left.")
        return
    channel = await create_pending_ticket(ctx.guild, ctx.author, pesos, need)
    embed = discord.Embed(title="🧾 PENDING ORDER", description="Hindi pa nabawasan stock.", color=0xF59E0B)
    embed.add_field(name="Amount", value=f"₱{pesos}", inline=True)
    embed.add_field(name="You Get", value=f"{need} Robux", inline=True)
    await channel.send(embed=embed, view=ConfirmView())
    await ctx.send(f"✅ Pending order: {channel.mention}. Hindi pa nabawasan stock.")

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
        pending_orders.pop(ctx.channel.id, None)
        await ctx.send("Closing ticket in 3 seconds...")
        import asyncio
        await asyncio.sleep(3)
        await ctx.channel.delete()
    else:
        await ctx.send("This is not a ticket channel.")

bot.run(TOKEN)
