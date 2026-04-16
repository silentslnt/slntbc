import discord
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime
import json
from logger import CloneLogger

class ServerCloner:
    def __init__(self, bot, source_guild: discord.Guild, dest_guild: discord.Guild):
        self.bot = bot
        self.source = source_guild
        self.dest = dest_guild
        self.role_map: Dict[int, discord.Role] = {}
        self.channel_map: Dict[int, discord.abc.GuildChannel] = {}
        self.category_map: Dict[int, discord.CategoryChannel] = {}
        self.emoji_map: Dict[str, discord.Emoji] = {}
        self.logger = CloneLogger(source_guild.name, dest_guild.name)
        
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
            await asyncio.sleep(1)
        
        self.logger.log_complete()
        self.logger.save()
    
    async def delete_all_channels(self):
        """Remove all existing channels in destination"""
        deleted = 0
        for channel in self.dest.channels:
            try:
                await channel.delete()
                deleted += 1
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
                await asyncio.sleep(0.5)
                
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
                await asyncio.sleep(0.5)
                
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
                await asyncio.sleep(0.5)
                
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
                    await asyncio.sleep(0.3)
                    
            except Exception as e:
                self.logger.log_error(f"Permission error on {dest_channel.name}: {e}")
        
        self.logger.log_action(f"Set {perms_set} permission overwrites")
    
    async def clone_emojis(self):
        """Clone all custom emojis (static and animated)"""
        created = 0
        skipped = 0
        
        # Check emoji slots
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
                    # Download emoji image
                    async with session.get(str(emoji.url)) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            
                            # Create emoji in destination
                            new_emoji = await self.dest.create_custom_emoji(
                                name=emoji.name,
                                image=image_bytes,
                                reason=f"Cloned from {self.source.name}"
                            )
                            
                            self.emoji_map[emoji.name] = new_emoji
                            created += 1
                            await asyncio.sleep(0.5)
                            
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
                # Get webhooks from source
                source_webhooks = await source_channel.webhooks()
                
                async with aiohttp.ClientSession() as session:
                    for webhook in source_webhooks:
                        try:
                            # Download avatar if exists
                            avatar_bytes = None
                            if webhook.avatar:
                                async with session.get(str(webhook.avatar.url)) as resp:
                                    if resp.status == 200:
                                        avatar_bytes = await resp.read()
                            
                            # Create webhook in destination
                            await dest_channel.create_webhook(
                                name=webhook.name or "Cloned Webhook",
                                avatar=avatar_bytes,
                                reason=f"Cloned from {self.source.name}"
                            )
                            
                            created += 1
                            await asyncio.sleep(0.5)
                            
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
                await asyncio.sleep(0.5)
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
                await asyncio.sleep(0.5)
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
                
                await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.log_error(f"Failed to create channel from template: {e}")
        
        self.logger.log_complete()