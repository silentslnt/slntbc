import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from cloner import ServerCloner
from template_manager import TemplateManager
import asyncio

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
template_mgr = TemplateManager()

@bot.event
async def on_ready():
    print(f'🤖 Logged in as {bot.user}')
    print(f'📊 Servers: {len(bot.guilds)}')
    print('✅ Ready to clone')

# === FULL CLONE COMMANDS ===

@bot.command()
@commands.has_permissions(administrator=True)
async def clone(ctx, source_server_id: int):
    """
    Full clone to current server
    Usage: !clone 123456789012345678
    """
    source_guild = bot.get_guild(source_server_id)
    
    if not source_guild:
        await ctx.send("❌ Bot is not in that server or invalid ID")
        return
    
    if not source_guild.me.guild_permissions.administrator:
        await ctx.send("❌ Bot needs Administrator in source server")
        return
    
    dest_guild = ctx.guild
    await ctx.send(f"🔄 Starting full clone of **{source_guild.name}**...")
    
    cloner = ServerCloner(bot, source_guild, dest_guild)
    
    try:
        await cloner.clone_server(ctx)
        await ctx.send(f"✅ Clone complete! Check logs for details.")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command()
@commands.has_permissions(administrator=True)
async def newclone(ctx, source_server_id: int, *, new_server_name: str):
    """
    Create new server and clone
    Usage: !newclone 123456789012345678 My New Server
    """
    source_guild = bot.get_guild(source_server_id)
    
    if not source_guild:
        await ctx.send("❌ Bot is not in that server or invalid ID")
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
        await ctx.send("❌ Invalid server ID")
        return
    
    await ctx.send("🔄 Cloning roles only...")
    
    cloner = ServerCloner(bot, source_guild, ctx.guild)
    await cloner.clone_server(ctx, options={
        'roles': True,
        'channels': False,
        'emojis': False,
        'webhooks': False,
        'delete_existing': False
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
        'webhooks': False,
        'delete_existing': True
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
    embed.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await ctx.send(embed=embed)

@bot.command()
async def help_clone(ctx):
    """Show all cloner commands"""
    embed = discord.Embed(
        title="🔧 Server Cloner - All Commands",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="**Full Cloning**",
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
        name="Requirements",
        value="• Administrator permission required\n• Bot needs Admin in source server\n• Bot must be member of source server",
        inline=False
    )
    
    await ctx.send(embed=embed)

bot.run(os.getenv('DISCORD_TOKEN'))