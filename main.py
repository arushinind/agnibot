import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import sqlite3
import random
import time
import json
import math
import os
from typing import Optional, List, Dict, Any

# ==============================================================================
# ⚙️ CONFIGURATION
# ==============================================================================

# Get Token from Environment Variable for security
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ WARNING: DISCORD_TOKEN not found in environment variables.")

COLORS = {
    "GOLD": 0xFFD700, "CRIMSON": 0xDC143C, "CYAN": 0x00FFFF, "PURPLE": 0x9400D3,
    "GREEN": 0x32CD32, "SAFFRON": 0xFF9933, "VOID": 0x2C2F33, "GATE": 0xFF1493,
    "ENERGY": 0x3498DB, "MYTHIC": 0xFF0055
}

ICONS = {
    "hp": "❤️", "gold": "🪙", "xp": "✨", "rep": "🌟", "mana": "🧿",
    "atk": "⚔️", "def": "🛡️", "mat": "📦", "mount": "🐾", "rebirth": "🌀"
}

# ==============================================================================
# 📜 GAME DATA
# ==============================================================================

PATHS = {
    "Warrior": {"stats": {"atk": 15, "hp": 150, "crit": 0.05}, "ability": "Heavy Smash", "icon": "🗡️"},
    "Mage":    {"stats": {"atk": 8, "hp": 80, "crit": 0.02},  "ability": "Arcane Blast", "icon": "🔥"},
    "Rogue":   {"stats": {"atk": 12, "hp": 100, "crit": 0.25}, "ability": "Sneak Attack", "icon": "🎭"}
}

MATERIALS = {
    "Iron Ore":     {"r": "Common", "price": 10},
    "Dark Essence": {"r": "Uncommon", "price": 50},
    "Star Metal":   {"r": "Rare", "price": 200},
    "Life Essence": {"r": "Epic", "price": 500},
    "Hard Scale":   {"r": "Rare", "price": 150}
}

RECIPES = {
    "Vampire Dagger":  {"type": "wep", "atk": 35, "cost": {"Iron Ore": 10, "Dark Essence": 5}, "desc": "Heals 10% of damage dealt."},
    "Storm Staff":     {"type": "wep", "atk": 150, "cost": {"Star Metal": 10, "Life Essence": 2}, "desc": "Crackles with lightning."},
    "Royal Spear":     {"type": "wep", "atk": 300, "cost": {"Star Metal": 20, "Life Essence": 10}, "desc": "God-killer weapon."},
    "Plate Armor":     {"type": "arm", "hp": 300, "cost": {"Iron Ore": 20, "Hard Scale": 10}, "desc": "Heavy protection."}
}

VAHANAS = {
    "Gilded Rat":      {"name": "Gilded Rat",      "buff": "+20% Gold",   "stat": "gold_mult", "val": 0.2},
    "Emerald Peacock": {"name": "Emerald Peacock", "buff": "+15% Crit",   "stat": "crit",      "val": 0.15},
    "Ironclad Bull":   {"name": "Ironclad Bull",   "buff": "+300 Max HP", "stat": "hp",        "val": 300},
    "Storm Falcon":    {"name": "Storm Falcon",    "buff": "+25% Dodge",  "stat": "dodge",     "val": 0.25}
}

LOCATIONS = {
    "Sun City":    {"lvl": 1, "mats": ["Iron Ore"]},
    "Mist Woods":  {"lvl": 10, "mats": ["Iron Ore", "Dark Essence"]},
    "Gold Fort":   {"lvl": 30, "mats": ["Dark Essence", "Hard Scale"]},
    "Sky Peak":    {"lvl": 60, "mats": ["Star Metal", "Life Essence"]}
}

ITEMS = {
    "Potion":     {"type": "heal", "val": 150, "price": 50, "rep": 0, "desc": "Heals 150 HP"},
    "Elixir":     {"type": "heal", "val": 9999, "price": 500, "rep": 20, "desc": "Full Heal"},
    "Fire Scroll":{"type": "dmg", "val": 800, "price": 1500, "rep": 0, "desc": "800 DMG"},
}

GAME_TIPS = [
    "Tip: You heal 40% HP when using 'Rest' in battle.",
    "Tip: Golden Enemies drop 10x Gold and XP.",
    "Tip: Reincarnating at Level 50 boosts ALL stats permanently by 20%.",
    "Tip: Different regions drop different crafting materials.",
    "Tip: The Vampire Dagger heals you on every hit."
]

# ==============================================================================
# 🗄️ DATABASE
# ==============================================================================

class Database:
    def __init__(self, db_name="agni_v14.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                path TEXT DEFAULT 'None',
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                gold INTEGER DEFAULT 0,
                rebirths INTEGER DEFAULT 0,
                location TEXT DEFAULT 'Sun City',
                inventory TEXT DEFAULT '{}',
                materials TEXT DEFAULT '{}',
                equipment TEXT DEFAULT '{"wep": "None", "arm": "None", "mount": "None"}'
            )
        """)
        # Migration: Add rebirths if missing for old DBs
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN rebirths INTEGER DEFAULT 0")
        except:
            pass
        self.conn.commit()

    def get_user(self, uid):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        res = self.cursor.fetchone()
        if res:
            cols = ["user_id", "path", "level", "xp", "hp", "max_hp", "gold", "rebirths", "location", "inventory", "materials", "equipment"]
            d = dict(zip(cols, res))
            for k in ["inventory", "materials", "equipment"]:
                d[k] = json.loads(d[k])
            return d
        return None

    def create_user(self, uid, path="Warrior"):
        if not self.get_user(uid):
            p_stats = PATHS[path]["stats"]
            hp = 100 + p_stats["hp"]
            inv = json.dumps({"Potion": 5}) # Start with 5 potions
            self.cursor.execute("INSERT INTO users (user_id, path, hp, max_hp, inventory) VALUES (?, ?, ?, ?, ?)", (uid, path, hp, hp, inv))
            self.conn.commit()
            return True
        return False

    def update_user(self, uid, data):
        clauses, vals = [], []
        for k, v in data.items():
            if k == "user_id": continue
            clauses.append(f"{k}=?")
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
        vals.append(uid)
        self.cursor.execute(f"UPDATE users SET {', '.join(clauses)} WHERE user_id=?", vals)
        self.conn.commit()

db = Database()

# ==============================================================================
# 🎨 UI HELPERS
# ==============================================================================

class DharmaEmbed(discord.Embed):
    def __init__(self, title, description=None, color=COLORS["SAFFRON"], user=None):
        super().__init__(title=f"⚔️ {title}", description=description, color=color)
        if user:
            u = db.get_user(user.id)
            if u:
                path = u.get('path', 'Unknown')
                lvl = u.get('level', 1)
                rebirth = f"🌀 {u['rebirths']} " if u['rebirths'] > 0 else ""
                self.set_footer(text=f"{path} • {rebirth}Lvl {lvl} • {ICONS['gold']} {u['gold']}")
        else:
            self.set_footer(text=f"💡 {random.choice(GAME_TIPS)}")

def render_hp(curr, max_val, length=10):
    pct = max(0, min(1, curr / max(1, max_val)))
    filled = int(length * pct)
    c = "🟩" if pct > 0.5 else "🟥"
    return f"{c*filled}{'⬛'*(length-filled)} `{curr}/{max_val}`"

def calculate_stats(u):
    # Base Stats
    path_stats = PATHS.get(u['path'], PATHS['Warrior'])['stats']
    
    # REBIRTH MULTIPLIER (The Addiction Hook)
    # Each rebirth adds +20% to ALL stats. Infinite scaling.
    mult = 1.0 + (u['rebirths'] * 0.20)
    
    atk = int(((u['level'] * 4) + path_stats['atk']) * mult)
    max_hp = int((100 + path_stats['hp'] + (u['level'] * 10)) * mult)
    crit = path_stats['crit']
    
    # Gear Stats
    eq = u['equipment']
    if eq['wep'] in RECIPES: atk += int(RECIPES[eq['wep']]['atk'] * mult)
    if eq['arm'] in RECIPES: max_hp += int(RECIPES[eq['arm']]['hp'] * mult)
    
    # Mount Stats
    if eq['mount'] in VAHANAS:
        v = VAHANAS[eq['mount']]
        if v['stat'] == 'hp': max_hp += int(v['val'] * mult)
        if v['stat'] == 'crit': crit += v['val']
        
    return {"atk": atk, "max_hp": max_hp, "crit": crit}

# ==============================================================================
# ⚔️ COMBAT SYSTEM (WAVE + GOLDEN ENEMIES)
# ==============================================================================

class CombatView(ui.View):
    def __init__(self, user, location):
        super().__init__(timeout=300)
        self.user = user
        self.u = db.get_user(user.id)
        self.stats = calculate_stats(self.u)
        self.loc = location
        
        # Sync HP cap
        if self.u['hp'] > self.stats['max_hp']: self.u['hp'] = self.stats['max_hp']
        
        self.wave = 1
        self.max_waves = 3
        self.logs = ["⚔️ **Encounter Started!**"]
        self.spawn_enemy()
        self.update_buttons()

    def update_buttons(self):
        inv = self.u['inventory']
        # Find heal button dynamically
        heal_btn = None
        for child in self.children:
            if getattr(child, "custom_id", "") == "heal_btn":
                heal_btn = child
                break
        
        if heal_btn:
            if inv.get("Potion", 0) > 0:
                heal_btn.label = f"Potion ({inv['Potion']})"
                heal_btn.style = discord.ButtonStyle.success
                heal_btn.emoji = "🧪"
            else:
                heal_btn.label = "Rest (40%)"
                heal_btn.style = discord.ButtonStyle.secondary
                heal_btn.emoji = "💤"

    def spawn_enemy(self):
        # GOLDEN ENEMY CHECK (Dopamine Spike)
        is_golden = random.random() < 0.05 # 5% Chance
        
        lvl = self.u['level'] + (self.wave - 1) * 2
        names = ["Dark Knight", "Feral Ogre", "Night Ghoul", "Venom Serpent"]
        mats = LOCATIONS.get(self.loc, LOCATIONS["Sun City"])["mats"]
        
        if is_golden:
            self.enemy = {
                "name": f"✨ GOLDEN {random.choice(names)} ✨",
                "lvl": lvl,
                "hp": 30, # Weak HP, easy kill
                "max_hp": 30,
                "atk": 5,
                "drop_mat": "Life Essence", # Rare drop guaranteed
                "is_golden": True
            }
            self.logs.append(f"⚠️ **A GOLDEN ENEMY APPEARED!** (Huge Loot!)")
        else:
            self.enemy = {
                "name": f"{random.choice(names)}",
                "lvl": lvl,
                "hp": 50 + (lvl * 15),
                "max_hp": 50 + (lvl * 15),
                "atk": 10 + (lvl * 3),
                "drop_mat": random.choice(mats),
                "is_golden": False
            }
            self.logs.append(f"Wave {self.wave}: {self.enemy['name']} appeared!")

    def get_embed(self, status="FIGHT"):
        c = COLORS["GOLD"] if self.enemy.get('is_golden') else (COLORS["CRIMSON"] if status=="FIGHT" else COLORS["GREEN"])
        e = discord.Embed(title=f"⚔️ {self.loc} (Wave {self.wave})", color=c)
        e.add_field(name="🛡️ You", value=render_hp(self.u['hp'], self.stats['max_hp']), inline=True)
        e.add_field(name=f"👹 {self.enemy['name']}", value=render_hp(self.enemy['hp'], self.enemy['max_hp']), inline=True)
        
        log_txt = "\n".join(self.logs[-5:])
        e.add_field(name="📜 Log", value=f"```diff\n{log_txt}\n```", inline=False)
        return e

    async def end_turn(self, interaction):
        if self.enemy['hp'] <= 0:
            # Rewards
            gold_mult = 10 if self.enemy.get('is_golden') else 1
            if self.u['equipment']['mount'] == "Gilded Rat": gold_mult += 0.2
            
            # Drop
            mat = self.enemy['drop_mat']
            self.u['materials'][mat] = self.u['materials'].get(mat, 0) + 1
            self.logs.append(f"📦 Dropped: {mat}")

            if self.wave < self.max_waves:
                # Wave Regen (Buffed to 30%)
                regen = int(self.stats['max_hp'] * 0.3)
                self.u['hp'] = min(self.stats['max_hp'], self.u['hp'] + regen)
                self.logs.append(f"💚 Restored {regen} HP between waves.")
                
                self.wave += 1
                self.spawn_enemy()
                self.update_buttons()
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
            else:
                # Clear Dungeon
                gold = int(50 * self.u['level'] * gold_mult)
                xp = int(100 * self.u['level'] * gold_mult)
                self.u['gold'] += gold
                self.u['xp'] += xp
                
                # Level Up (Full Heal)
                if self.u['xp'] >= self.u['level'] * 150:
                    self.u['level'] += 1
                    self.u['xp'] = 0
                    self.u['hp'] = self.stats['max_hp'] # Full Heal on Level Up
                    self.logs.append("✨ **LEVEL UP!** Fully Healed.")
                
                db.update_user(self.user.id, self.u)
                
                embed = self.get_embed("WIN")
                embed.add_field(name="Victory!", value=f"🪙 +{gold} Gold\n✨ +{xp} XP\n📦 {mat}")
                await interaction.response.edit_message(embed=embed, view=None)
            return

        # Enemy Turn
        dmg = random.randint(int(self.enemy['atk']*0.8), int(self.enemy['atk']*1.2))
        
        # Dodge Check
        dodge_chance = 0.25 if self.u['equipment']['mount'] == "Storm Falcon" else 0.05
        if random.random() < dodge_chance:
            self.logs.append("💨 DODGED the attack!")
        else:
            self.u['hp'] -= dmg
            self.logs.append(f"- Enemy hit for {dmg}!")

        if self.u['hp'] <= 0:
            self.u['hp'] = 10
            db.update_user(self.user.id, self.u)
            embed = self.get_embed("LOSE")
            embed.description = "You fell... but your legacy remains."
            await interaction.response.edit_message(embed=embed, view=None)
            return

        db.update_user(self.user.id, self.u)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Strike", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def attack(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id: return
        
        dmg = int(self.stats['atk'] * random.uniform(0.9, 1.1))
        if random.random() < self.stats['crit']:
            dmg *= 2
            self.logs.append(f"💥 **CRIT!** {dmg} DMG!")
        else:
            self.logs.append(f"+ Hit for {dmg}.")
            
        # LIFESTEAL MECHANIC
        if self.u['equipment']['wep'] == "Vampire Dagger":
            heal = int(dmg * 0.1)
            self.u['hp'] = min(self.stats['max_hp'], self.u['hp'] + heal)
            
        self.enemy['hp'] -= dmg
        await self.end_turn(interaction)

    @ui.button(label="Heal", style=discord.ButtonStyle.success, emoji="🧪", custom_id="heal_btn")
    async def heal(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id: return
        inv = self.u['inventory']
        
        if inv.get("Potion", 0) > 0:
            inv["Potion"] -= 1
            heal = 150 # Buffed Potion
            self.u['hp'] = min(self.stats['max_hp'], self.u['hp'] + heal)
            self.logs.append("+ Potion (+150 HP)")
            await self.end_turn(interaction)
        else:
            # BUFFED REST: 40% Heal
            heal = int(self.stats['max_hp'] * 0.40)
            self.u['hp'] = min(self.stats['max_hp'], self.u['hp'] + heal)
            self.logs.append(f"💤 Deep Rest (+{heal} HP).")
            await self.end_turn(interaction)

# ==============================================================================
# ⚒️ CRAFTING VIEW
# ==============================================================================

class CraftingView(ui.View):
    def __init__(self, uid):
        super().__init__()
        self.uid = uid
        self.add_item(CraftSelect(uid))

class CraftSelect(ui.Select):
    def __init__(self, uid):
        self.uid = uid
        opts = []
        for k, v in RECIPES.items():
            reqs = ", ".join([f"{n}x{q}" for n,q in v['cost'].items()])
            opts.append(discord.SelectOption(
                label=k, 
                description=f"{v['type'].upper()} | Req: {reqs}", 
                value=k, emoji="⚒️"
            ))
        super().__init__(placeholder="Select Item to Forge...", options=opts)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid: return
        item_name = self.values[0]
        recipe = RECIPES[item_name]
        u = db.get_user(self.uid)
        
        # Check Mats
        for mat, qty in recipe['cost'].items():
            if u['materials'].get(mat, 0) < qty:
                return await interaction.response.send_message(f"❌ Missing Material: Need {qty}x {mat}", ephemeral=True)
        
        # Deduct Mats
        for mat, qty in recipe['cost'].items():
            u['materials'][mat] -= qty
            
        # Add Item
        if recipe['type'] == 'wep': u['equipment']['wep'] = item_name
        elif recipe['type'] == 'arm': u['equipment']['arm'] = item_name
        
        db.update_user(self.uid, u)
        await interaction.response.send_message(f"🔥 **FUSION SUCCESSFUL!** You forged **{item_name}**!", ephemeral=True)

# ==============================================================================
# 🐣 MOUNT VIEW
# ==============================================================================

class MountView(ui.View):
    def __init__(self, uid):
        super().__init__()
        self.uid = uid
        self.u = db.get_user(uid)
        
        select = ui.Select(placeholder="Bond with a Spirit Beast...")
        for k, v in VAHANAS.items():
            select.add_option(label=v['name'], description=v['buff'], value=k, emoji="🐾")
        
        async def cb(interaction):
            if interaction.user.id != self.uid: return
            val = select.values[0]
            # Cost check
            if self.u['gold'] < 500:
                return await interaction.response.send_message("❌ Need 500 Gold to bond.", ephemeral=True)
            
            self.u['gold'] -= 500
            self.u['equipment']['mount'] = val
            db.update_user(self.uid, self.u)
            await interaction.response.send_message(f"🐾 You are now riding the **{VAHANAS[val]['name']}**!", ephemeral=True)
            
        select.callback = cb
        self.add_item(select)

# ==============================================================================
# 🚀 MAIN COMMANDS
# ==============================================================================

class AgniBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        await self.tree.sync()
        print("🔥 Agni 14.0 (Eternal Cycle) is Online.")

bot = AgniBot()

@bot.tree.command(name="start", description="Begin your saga")
async def start(interaction: discord.Interaction):
    if db.create_user(interaction.user.id):
        await interaction.response.send_message("⚔️ **Legend Begun.** Use `/battle` to fight.", ephemeral=True)
    else:
        await interaction.response.send_message("You are already playing.", ephemeral=True)

@bot.tree.command(name="battle", description="Fight (5% chance for GOLDEN enemies)")
async def battle(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if not u: return await interaction.response.send_message("Use `/start` first.")
    if u['hp'] < 10: return await interaction.response.send_message("🩸 Too weak! Heal first.", ephemeral=True)
    await interaction.response.send_message(view=CombatView(interaction.user, u['location']))

@bot.tree.command(name="spin", description="Gamble Gold (High Risk, High Reward)")
async def spin(interaction: discord.Interaction, amount: int):
    u = db.get_user(interaction.user.id)
    if not u: return
    if u['gold'] < amount: return await interaction.response.send_message("Not enough Gold.", ephemeral=True)
    if amount < 100: return await interaction.response.send_message("Minimum bet 100.", ephemeral=True)
    
    u['gold'] -= amount
    roll = random.randint(1, 100)
    
    embed = DharmaEmbed("Divine Wheel", color=COLORS["GOLD"])
    if roll >= 90: # 10% Jackpot
        win = amount * 3
        u['gold'] += win
        embed.description = f"🎰 **JACKPOT!** Rolled {roll}.\nWon **{win} Gold!**"
    elif roll >= 50: # Win
        win = int(amount * 1.5)
        u['gold'] += win
        embed.description = f"✅ **WIN!** Rolled {roll}.\nWon **{win} Gold!**"
    else:
        embed.description = f"❌ **LOSS.** Rolled {roll}.\nLost {amount} Gold."
        embed.color = COLORS["VOID"]
        
    db.update_user(interaction.user.id, u)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reincarnate", description="Reset Level for Permanent Power (Lvl 50+)")
async def reincarnate(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if not u: return
    if u['level'] < 50: return await interaction.response.send_message("🔒 Must be Level 50 to Reincarnate.", ephemeral=True)
    
    # Confirmation View
    view = ui.View()
    btn = ui.Button(label="ASCEND", style=discord.ButtonStyle.danger, emoji="🌀")
    
    async def confirm(inter):
        if inter.user.id != interaction.user.id: return
        u['level'] = 1
        u['xp'] = 0
        u['rebirths'] += 1
        # Keep gold, inventory, gear
        db.update_user(inter.user.id, u)
        
        embed = DharmaEmbed("Ascension", f"🌀 **REBIRTH #{u['rebirths']} COMPLETE!**\n\nAll stats increased by **20%** permanently.\nLevel reset to 1.", COLORS["MYTHIC"])
        await inter.response.edit_message(embed=embed, view=None)
        
    btn.callback = confirm
    view.add_item(btn)
    await interaction.response.send_message("⚠️ **Are you sure?**\nLevel will reset to 1. Stats will increase PERMANENTLY.", view=view, ephemeral=True)

@bot.tree.command(name="forge", description="Craft Powerful Weapons")
async def forge(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if not u: return await interaction.response.send_message("Use `/start` first.")
    
    mat_str = ", ".join([f"{k}: {v}" for k,v in u['materials'].items()]) or "None"
    embed = DharmaEmbed("Cosmic Forge", f"**Materials:** {mat_str}\n\nSelect a recipe to Forge.")
    await interaction.response.send_message(embed=embed, view=CraftingView(interaction.user.id))

@bot.tree.command(name="shop", description="Buy Potions and Scrolls")
async def shop(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    view = ui.View()
    select = ui.Select(placeholder="Buy Items...")
    for k, v in ITEMS.items():
        select.add_option(label=f"{k} ({v['price']} G)", description=v['desc'], value=k)
    
    async def cb(inter):
        val = select.values[0]
        cost = ITEMS[val]['price']
        usr = db.get_user(inter.user.id)
        if usr['gold'] < cost: return await inter.response.send_message("Too poor.", ephemeral=True)
        usr['gold'] -= cost
        usr['inventory'][val] = usr['inventory'].get(val, 0) + 1
        db.update_user(inter.user.id, usr)
        await inter.response.send_message(f"Bought {val}.")
        
    select.callback = cb
    view.add_item(select)
    await interaction.response.send_message(view=view)

@bot.tree.command(name="stables", description="Equip Spirit Mounts")
async def stables(interaction: discord.Interaction):
    await interaction.response.send_message("🐾 **Divine Stables**\nBond with a creature for 500 Gold.", view=MountView(interaction.user.id))

@bot.tree.command(name="profile", description="View Stats & Rebirths")
async def profile(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if not u: return await interaction.response.send_message("Use `/start` first.")
    
    stats = calculate_stats(u)
    eq = u['equipment']
    
    embed = DharmaEmbed("Hero Profile", user=interaction.user)
    embed.add_field(name="Stats (Buffed)", value=f"❤️ HP: {u['hp']}/{stats['max_hp']}\n⚔️ ATK: {stats['atk']}\n🎯 Crit: {int(stats['crit']*100)}%", inline=True)
    embed.add_field(name="Equipment", value=f"🗡️ Wep: {eq['wep']}\n🛡️ Arm: {eq['arm']}\n🐾 Mount: {eq['mount']}", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="travel", description="Move to new regions")
async def travel(interaction: discord.Interaction):
    view = ui.View()
    select = ui.Select(placeholder="Travel to...")
    for k, v in LOCATIONS.items():
        select.add_option(label=k, description=f"Lvl {v['lvl']}+ | Mats: {', '.join(v['mats'])}", value=k)
    
    async def cb(inter):
        if inter.user.id != interaction.user.id: return
        loc = select.values[0]
        u = db.get_user(inter.user.id)
        if u['level'] < LOCATIONS[loc]['lvl']: return await inter.response.send_message("🔒 Level too low.", ephemeral=True)
        u['location'] = loc
        db.update_user(inter.user.id, u)
        await inter.response.send_message(f"🌏 Arrived at **{loc}**.")
    
    select.callback = cb
    view.add_item(select)
    await interaction.response.send_message(view=view)

bot.run(TOKEN)
