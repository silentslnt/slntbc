import discord
from discord.ext import commands
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime
import json
import random
from logger import CloneLogger

async def human_delay(min_seconds=1.5, max_seconds=3.5):
    """Simulate human-like delays to avoid detection"""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))

class ServerCloner:
    def __init__(self, bot, source_guild: discord.Guild, dest_guild: discord.Guild):
        self.bot = bot
        self.source = source_guild
        self.dest = dest_guild
        self.role_map: Dict[int, discord.Role] = {}
        self.channel_map: Dict[int, discord.abc.GuildChannel] = {}
        self.category_map: Dict[int, discord.CategoryChannel] = {}
        self.emoji_map: Dict[str, discord.Emoji] = {}
        self.logger = CloneLogger(source_guild.name if source_guild else "Unknown", dest_guild.name)
        
    @staticmethod
    async def scrape_server_with_token(server_id: int, user_token: str) -> dict:
        """
        Scrape server data using user token (for servers bot isn't in)
        Uses human-like delays to avoid detection
        """
        headers = {
            "Authorization": user_token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        base_url = "https://discord.com/api/v10"
        
        async with aiohttp.ClientSession(headers=headers) as session:
            
            # Get guild data
            await human_delay(0.5, 1.0)
            async with session.get(f"{base_url}/guilds/{server_id}") as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to fetch guild: {resp.status} - {await resp.text()}")
                guild_data = await resp.json()
            
            # Get roles
            await human_delay(1.0, 2.0)
            async with session.get(f"{base_url}/guilds/{server_id}/roles") as resp:
                roles_data = await resp.json() if resp.status == 200 else []
            
            # Get channels
            await human_delay(1.0, 2.0)
            async with session.get(f"{base_url}/guilds/{server_id}/channels") as resp:
                channels_data = await resp.json() if resp.status == 200 else []
            
            # Get emojis
            await human_delay(1.0, 2.0)
            async with session.get(f"{base_url}/guilds/{server_id}/emojis") as resp:
                emojis_data = await resp.json() if resp.status == 200 else []
            
            return {
                'guild': guild_data,
                'roles': roles_data,
                'channels': channels_data,
                'emojis': emojis_data
            }
    
@staticmethod
async def apply_scraped_data(bot, scraped_data, dest_guild, ctx=None, options=None):
    """
    Apply scraped server data to destination guild
    Uses human-like delays for safety
    """
    if options is None:
        options = {
            'delete_channels': True,
            'delete_roles': True,
            'clone_roles': True,
            'clone_channels': True,
            'clone_emojis': True,
            'clone_stickers': True
        }
    
    logger = CloneLogger(scraped_data['guild']['name'], dest_guild.name)
    logger.log_start()
    
    role_map = {}
    category_map = {}
    channel_map = {}
    
    # Delete existing roles
    if options.get('delete_roles'):
        if ctx:
            await ctx.send("⏳ Clearing existing roles...")
        for role in dest_guild.roles:
            if role.name == "@everyone" or role.managed:
                continue
            try:
                await role.delete()
                await human_delay(0.3, 0.8)
            except:
                pass
    
    # Delete existing channels
    if options.get('delete_channels'):
        if ctx:
            await ctx.send("⏳ Clearing existing channels...")
        for channel in dest_guild.channels:
            try:
                await channel.delete()
                await human_delay(0.3, 0.8)
            except:
                pass
    
    # Create roles
    if options.get('clone_roles'):
        if ctx:
            await ctx.send("⏳ Creating roles...")
        
        roles_sorted = sorted(scraped_data['roles'], key=lambda r: r.get('position', 0), reverse=True)
        
        for role_data in roles_sorted:
            if role_data['name'] == "@everyone":
                perms = discord.Permissions(int(role_data['permissions']))
                await dest_guild.default_role.edit(permissions=perms)
                role_map[role_data['id']] = dest_guild.default_role
                continue
            
            if role_data.get('managed'):
                continue
            
            try:
                new_role = await dest_guild.create_role(
                    name=role_data['name'],
                    permissions=discord.Permissions(int(role_data['permissions'])),
                    color=discord.Color(role_data.get('color', 0)),
                    hoist=role_data.get('hoist', False),
                    mentionable=role_data.get('mentionable', False)
                )
                role_map[role_data['id']] = new_role
                await human_delay(1.2, 2.5)
            except Exception as e:
                logger.log_error(f"Failed to create role {role_data['name']}: {e}")
    
    # Create categories and channels
    if options.get('clone_channels'):
        if ctx:
            await ctx.send("⏳ Creating categories...")
        
        categories = [c for c in scraped_data['channels'] if c['type'] == 4]
        categories.sort(key=lambda c: c.get('position', 0))
        
        for cat_data in categories:
            try:
                new_cat = await dest_guild.create_category(
                    name=cat_data['name'],
                    position=cat_data.get('position', 0)
                )
                category_map[cat_data['id']] = new_cat
                channel_map[cat_data['id']] = new_cat
                await human_delay(1.0, 2.0)
            except Exception as e:
                logger.log_error(f"Failed to create category: {e}")
        
        if ctx:
            await ctx.send("⏳ Creating channels...")
        
        channels = [c for c in scraped_data['channels'] if c['type'] != 4]
        channels.sort(key=lambda c: c.get('position', 0))
        
        for chan_data in channels:
            try:
                category = category_map.get(chan_data.get('parent_id'))
                
                # Text channel (type 0)
                if chan_data['type'] == 0:
                    new_chan = await dest_guild.create_text_channel(
                        name=chan_data['name'],
                        topic=chan_data.get('topic'),
                        nsfw=chan_data.get('nsfw', False),
                        slowmode_delay=chan_data.get('rate_limit_per_user', 0),
                        category=category
                    )
                
                # Voice channel (type 2)
                elif chan_data['type'] == 2:
                    new_chan = await dest_guild.create_voice_channel(
                        name=chan_data['name'],
                        bitrate=min(chan_data.get('bitrate', 64000), dest_guild.bitrate_limit),
                        user_limit=chan_data.get('user_limit', 0),
                        category=category
                    )
                
                # Forum channel (type 15)
                elif chan_data['type'] == 15:
                    new_chan = await dest_guild.create_forum_channel(
                        name=chan_data['name'],
                        topic=chan_data.get('topic'),
                        category=category
                    )
                
                # Stage channel (type 13)
                elif chan_data['type'] == 13:
                    new_chan = await dest_guild.create_stage_channel(
                        name=chan_data['name'],
                        category=category
                    )
                
                else:
                    continue
                
                channel_map[chan_data['id']] = new_chan
                
                # Apply permission overwrites
                if 'permission_overwrites' in chan_data and options.get('clone_roles'):
                    for overwrite in chan_data['permission_overwrites']:
                        try:
                            # Role overwrite
                            if overwrite['type'] == 0:
                                target_role = role_map.get(int(overwrite['id']))
                                if target_role:
                                    allow = discord.Permissions(int(overwrite['allow']))
                                    deny = discord.Permissions(int(overwrite['deny']))
                                    await new_chan.set_permissions(
                                        target_role,
                                        overwrite=discord.PermissionOverwrite.from_pair(allow, deny)
                                    )
                                    await human_delay(0.5, 1.0)
                        except Exception as e:
                            logger.log_error(f"Failed to set permissions: {e}")
                
                await human_delay(1.0, 2.5)
                
            except Exception as e:
                logger.log_error(f"Failed to create channel {chan_data.get('name', 'Unknown')}: {e}")
    
    # Clone emojis
    if options.get('clone_emojis'):
        if ctx:
            await ctx.send("⏳ Cloning emojis...")
        
        async with aiohttp.ClientSession() as session:
            for emoji_data in scraped_data.get('emojis', []):
                try:
                    emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_data['id']}.{'gif' if emoji_data.get('animated') else 'png'}"
                    
                    async with session.get(emoji_url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            await dest_guild.create_custom_emoji(
                                name=emoji_data['name'],
                                image=image_bytes
                            )
                            await human_delay(1.5, 3.0)
                except Exception as e:
                    logger.log_error(f"Failed to clone emoji: {e}")
    
    # Clone stickers
    if options.get('clone_stickers') and 'stickers' in scraped_data:
        if ctx:
            await ctx.send("⏳ Cloning stickers...")
        
        async with aiohttp.ClientSession() as session:
            for sticker_data in scraped_data.get('stickers', []):
                try:
                    # Download sticker
                    sticker_url = f"https://media.discordapp.net/stickers/{sticker_data['id']}.png"
                    
                    async with session.get(sticker_url) as resp:
                        if resp.status == 200:
                            sticker_bytes = await resp.read()
                            
                            # Create sticker
                            await dest_guild.create_sticker(
                                name=sticker_data['name'],
                                description=sticker_data.get('description', ''),
                                emoji=sticker_data.get('tags', '😀'),
                                file=discord.File(io.BytesIO(sticker_bytes), filename='sticker.png')
                            )
                            await human_delay(1.5, 3.0)
                except Exception as e:
                    logger.log_error(f"Failed to clone sticker: {e}")
    
    logger.log_complete()
    logger.save()
    
    if ctx:
        await ctx.send("✅ Clone complete!")
    
    # Keep all the old methods for when bot IS in the server
    async def clone_server(self, ctx=None, options: Dict[str, bool] = None):
        """Execute full or partial server clone"""
        
        if options is None:
            options = {
                'roles': True,
                'channels': True,
                'emojis': True,
                'webhooks': True,
                'delete_existing': True
            }
        
        self.logger.log_start()
        
        steps = []
        
        if options.get('delete_existing'):
            steps.extend([
                ("Deleting existing channels", self.delete_all_channels),
                ("Deleting existing roles", self.delete_all_roles),
            ])
        
        if options.get('roles'):
            steps.append(("Cloning roles", self.clone_roles))
        
        if options.get('channels'):
            steps.extend([
                ("Cloning categories", self.clone_categories),
                ("Cloning channels", self.clone_channels),
                ("Setting permissions", self.clone_permissions),
            ])
        
        if options.get('emojis'):
            steps.append(("Cloning emojis", self.clone_emojis))
        
        if options.get('webhooks'):
            steps.append(("Cloning webhooks", self.clone_webhooks))
        
        for step_name, step_func in steps:
            if ctx:
                await ctx.send(f"⏳ {step_name}...")
            self.logger.log_step(step_name)
            await step_func()
            await human_delay(0.8, 1.5)
        
        self.logger.log_complete()
        self.logger.save()
    
    async def delete_all_channels(self):
        """Remove all existing channels in destination"""
        deleted = 0
        for channel in self.dest.channels:
            try:
                await channel.delete()
                deleted += 1
                await human_delay(0.3, 0.7)
            except discord.Forbidden:
                pass
        self.logger.log_action(f"Deleted {deleted} channels")
    
    async def delete_all_roles(self):
        """Remove all roles except @everyone and bot roles"""
        deleted = 0
        for role in self.dest.roles:
            if role.name == "@everyone":
                continue
            if role.managed:
                continue
            try:
                await role.delete()
                deleted += 1
                await human_delay(0.3, 0.7)
            except discord.Forbidden:
                pass
        self.logger.log_action(f"Deleted {deleted} roles")
    
    async def clone_roles(self):
        """Recreate all roles with permissions and hierarchy"""
        roles = sorted(self.source.roles, key=lambda r: r.position, reverse=True)
        created = 0
        
        for role in roles:
            if role.name == "@everyone":
                await self.dest.default_role.edit(permissions=role.permissions)
                self.role_map[role.id] = self.dest.default_role
                continue
            
            if role.managed:
                continue
            
            try:
                new_role = await self.dest.create_role(
                    name=role.name,
                    permissions=role.permissions,
                    color=role.color,
                    hoist=role.hoist,
                    mentionable=role.mentionable
                )
                self.role_map[role.id] = new_role
                created += 1
                await human_delay(0.8, 1.5)
                
            except discord.Forbidden:
                self.logger.log_error(f"Failed to create role: {role.name}")
        
        self.logger.log_action(f"Created {created} roles")
    
    async def clone_categories(self):
        """Recreate all categories with positions"""
        categories = sorted(self.source.categories, key=lambda c: c.position)
        created = 0
        
        for category in categories:
            try:
                new_category = await self.dest.create_category(
                    name=category.name,
                    position=category.position
                )
                self.category_map[category.id] = new_category
                self.channel_map[category.id] = new_category
                created += 1
                await human_delay(0.8, 1.5)
                
            except discord.Forbidden:
                self.logger.log_error(f"Failed to create category: {category.name}")
        
        self.logger.log_action(f"Created {created} categories")
    
    async def clone_channels(self):
        """Recreate all text/voice/forum/stage channels"""
        channels = [c for c in self.source.channels if not isinstance(c, discord.CategoryChannel)]
        channels.sort(key=lambda c: c.position)
        created = 0
        
        for channel in channels:
            try:
                category = None
                if channel.category_id:
                    category = self.category_map.get(channel.category_id)
                
                if isinstance(channel, discord.TextChannel):
                    new_channel = await self.dest.create_text_channel(
                        name=channel.name,
                        topic=channel.topic,
                        position=channel.position,
                        nsfw=channel.nsfw,
                        slowmode_delay=channel.slowmode_delay,
                        category=category
                    )
                    
                elif isinstance(channel, discord.VoiceChannel):
                    new_channel = await self.dest.create_voice_channel(
                        name=channel.name,
                        position=channel.position,
                        bitrate=min(channel.bitrate, self.dest.bitrate_limit),
                        user_limit=channel.user_limit,
                        category=category
                    )
                    
                elif isinstance(channel, discord.ForumChannel):
                    new_channel = await self.dest.create_forum_channel(
                        name=channel.name,
                        topic=channel.topic,
                        position=channel.position,
                        category=category
                    )
                
                elif isinstance(channel, discord.StageChannel):
                    new_channel = await self.dest.create_stage_channel(
                        name=channel.name,
                        position=channel.position,
                        category=category
                    )
                
                else:
                    continue
                
                self.channel_map[channel.id] = new_channel
                created += 1
                await human_delay(0.8, 1.8)
                
            except Exception as e:
                self.logger.log_error(f"Error cloning {channel.name}: {e}")
        
        self.logger.log_action(f"Created {created} channels")
    
    async def clone_permissions(self):
        """Apply permission overwrites to all channels"""
        perms_set = 0
        
        for source_channel_id, dest_channel in self.channel_map.items():
            source_channel = self.source.get_channel(source_channel_id)
            
            if not source_channel:
                continue
            
            try:
                for target in dest_channel.overwrites:
                    await dest_channel.set_permissions(target, overwrite=None)
                
                for target, overwrite in source_channel.overwrites.items():
                    if isinstance(target, discord.Role):
                        new_target = self.role_map.get(target.id)
                        if not new_target:
                            continue
                    else:
                        new_target = self.dest.get_member(target.id)
                        if not new_target:
                            continue
                    
                    await dest_channel.set_permissions(new_target, overwrite=overwrite)
                    perms_set += 1
                    await human_delay(0.4, 0.9)
                    
            except Exception as e:
                self.logger.log_error(f"Permission error on {dest_channel.name}: {e}")
        
        self.logger.log_action(f"Set {perms_set} permission overwrites")
    
    async def clone_emojis(self):
        """Clone all custom emojis (static and animated)"""
        created = 0
        skipped = 0
        
        emoji_limit = self.dest.emoji_limit
        current_emojis = len(self.dest.emojis)
        
        if current_emojis >= emoji_limit:
            self.logger.log_error(f"Emoji limit reached ({emoji_limit})")
            return
        
        async with aiohttp.ClientSession() as session:
            for emoji in self.source.emojis:
                if current_emojis + created >= emoji_limit:
                    skipped = len(self.source.emojis) - created
                    break
                
                try:
                    async with session.get(str(emoji.url)) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            
                            new_emoji = await self.dest.create_custom_emoji(
                                name=emoji.name,
                                image=image_bytes,
                                reason=f"Cloned from {self.source.name}"
                            )
                            
                            self.emoji_map[emoji.name] = new_emoji
                            created += 1
                            await human_delay(1.2, 2.5)
                            
                except discord.Forbidden:
                    self.logger.log_error(f"Missing permissions to create emoji: {emoji.name}")
                    break
                except discord.HTTPException as e:
                    self.logger.log_error(f"Failed to create emoji {emoji.name}: {e}")
        
        self.logger.log_action(f"Created {created} emojis" + (f" ({skipped} skipped - limit reached)" if skipped else ""))
    
    async def clone_webhooks(self):
        """Recreate webhooks in text channels"""
        created = 0
        
        for source_channel_id, dest_channel in self.channel_map.items():
            source_channel = self.source.get_channel(source_channel_id)
            
            if not isinstance(source_channel, discord.TextChannel):
                continue
            if not isinstance(dest_channel, discord.TextChannel):
                continue
            
            try:
                source_webhooks = await source_channel.webhooks()
                
                async with aiohttp.ClientSession() as session:
                    for webhook in source_webhooks:
                        try:
                            avatar_bytes = None
                            if webhook.avatar:
                                async with session.get(str(webhook.avatar.url)) as resp:
                                    if resp.status == 200:
                                        avatar_bytes = await resp.read()
                            
                            await dest_channel.create_webhook(
                                name=webhook.name or "Cloned Webhook",
                                avatar=avatar_bytes,
                                reason=f"Cloned from {self.source.name}"
                            )
                            
                            created += 1
                            await human_delay(1.0, 2.0)
                            
                        except discord.HTTPException as e:
                            self.logger.log_error(f"Failed to create webhook in {dest_channel.name}: {e}")
                            
            except discord.Forbidden:
                continue
        
        self.logger.log_action(f"Created {created} webhooks")
    
    def generate_template(self) -> dict:
        """Generate reusable JSON template of server structure"""
        template = {
            'name': self.source.name,
            'created_at': datetime.utcnow().isoformat(),
            'roles': [],
            'categories': [],
            'channels': [],
            'emojis': []
        }
        
        # Roles
        for role in sorted(self.source.roles, key=lambda r: r.position, reverse=True):
            if role.name == "@everyone" or role.managed:
                continue
            
            template['roles'].append({
                'name': role.name,
                'color': role.color.value,
                'permissions': role.permissions.value,
                'hoist': role.hoist,
                'mentionable': role.mentionable,
                'position': role.position
            })
        
        # Categories
        for cat in sorted(self.source.categories, key=lambda c: c.position):
            template['categories'].append({
                'name': cat.name,
                'position': cat.position,
                'id': cat.id
            })
        
        # Channels
        for channel in sorted(self.source.channels, key=lambda c: c.position):
            if isinstance(channel, discord.CategoryChannel):
                continue
            
            channel_data = {
                'name': channel.name,
                'position': channel.position,
                'category_id': channel.category_id if channel.category else None
            }
            
            if isinstance(channel, discord.TextChannel):
                channel_data.update({
                    'type': 'text',
                    'topic': channel.topic,
                    'nsfw': channel.nsfw,
                    'slowmode': channel.slowmode_delay
                })
            elif isinstance(channel, discord.VoiceChannel):
                channel_data.update({
                    'type': 'voice',
                    'bitrate': channel.bitrate,
                    'user_limit': channel.user_limit
                })
            elif isinstance(channel, discord.ForumChannel):
                channel_data.update({
                    'type': 'forum',
                    'topic': channel.topic
                })
            elif isinstance(channel, discord.StageChannel):
                channel_data.update({
                    'type': 'stage'
                })
            
            template['channels'].append(channel_data)
        
        # Emojis
        for emoji in self.source.emojis:
            template['emojis'].append({
                'name': emoji.name,
                'url': str(emoji.url),
                'animated': emoji.animated
            })
        
        return template
    
    async def apply_template(self, template: dict, ctx=None):
        """Apply saved template to destination server"""
        self.logger.log_start()
        
        # Create roles from template
        if ctx:
            await ctx.send("⏳ Creating roles from template...")
        
        for role_data in template['roles']:
            try:
                await self.dest.create_role(
                    name=role_data['name'],
                    color=discord.Color(role_data['color']),
                    permissions=discord.Permissions(role_data['permissions']),
                    hoist=role_data['hoist'],
                    mentionable=role_data['mentionable']
                )
                await human_delay(0.8, 1.5)
            except Exception as e:
                self.logger.log_error(f"Failed to create role from template: {e}")
        
        # Create categories
        if ctx:
            await ctx.send("⏳ Creating categories from template...")
        
        category_map = {}
        for cat_data in template['categories']:
            try:
                new_cat = await self.dest.create_category(
                    name=cat_data['name'],
                    position=cat_data['position']
                )
                category_map[cat_data['id']] = new_cat
                await human_delay(0.8, 1.5)
            except Exception as e:
                self.logger.log_error(f"Failed to create category from template: {e}")
        
        # Create channels
        if ctx:
            await ctx.send("⏳ Creating channels from template...")
        
        for chan_data in template['channels']:
            try:
                category = category_map.get(chan_data['category_id'])
                
                if chan_data['type'] == 'text':
                    await self.dest.create_text_channel(
                        name=chan_data['name'],
                        topic=chan_data.get('topic'),
                        nsfw=chan_data.get('nsfw', False),
                        slowmode_delay=chan_data.get('slowmode', 0),
                        category=category
                    )
                elif chan_data['type'] == 'voice':
                    await self.dest.create_voice_channel(
                        name=chan_data['name'],
                        bitrate=min(chan_data['bitrate'], self.dest.bitrate_limit),
                        user_limit=chan_data.get('user_limit', 0),
                        category=category
                    )
                elif chan_data['type'] == 'forum':
                    await self.dest.create_forum_channel(
                        name=chan_data['name'],
                        topic=chan_data.get('topic'),
                        category=category
                    )
                elif chan_data['type'] == 'stage':
                    await self.dest.create_stage_channel(
                        name=chan_data['name'],
                        category=category
                    )
                
                await human_delay(0.8, 1.8)
            except Exception as e:
                self.logger.log_error(f"Failed to create channel from template: {e}")
        
        self.logger.log_complete()