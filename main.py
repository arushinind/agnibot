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

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ WARNING: DISCORD_TOKEN not found.")

COLORS = {
    "GOLD": 0xFFD700, "CRIMSON": 0xDC143C, "CYAN": 0x00FFFF, "PURPLE": 0x9400D3,
    "GREEN": 0x32CD32, "SAFFRON": 0xFF9933, "VOID": 0x2C2F33, "CHAKRA": 0xFF1493,
    "PRANA": 0x3498DB, "MYTHIC": 0xFF0055
}

ICONS = {
    "hp": "❤️", "gold": "🪙", "xp": "✨", "karma": "🌟", "vidya": "📜",
    "atk": "⚔️", "def": "🛡️", "mat": "📦", "mount": "🐾"
}

# ==============================================================================
# 📜 GAME DATA
# ==============================================================================

PATHS = {
    "Kshatriya": {"stats": {"atk": 10, "hp": 100, "crit": 0.05}, "ability": "Rage Strike", "icon": "🗡️"},
    "Brahmin":   {"stats": {"atk": 5, "hp": 50, "crit": 0.02},  "ability": "Mantra Blast", "icon": "🔥"},
    "Vanara":    {"stats": {"atk": 8, "hp": 70, "crit": 0.20},  "ability": "Ambush",       "icon": "🐵"}
}

MATERIALS = {
    "Iron Ore":    {"r": "Common", "price": 10},
    "Demon Blood": {"r": "Uncommon", "price": 50},
    "Star Metal":  {"r": "Rare", "price": 200},
    "Soma Drop":   {"r": "Epic", "price": 500},
    "Naga Scale":  {"r": "Rare", "price": 150}
}

RECIPES = {
    "Steel Sword":     {"type": "wep", "atk": 20, "cost": {"Iron Ore": 5}, "desc": "Standard issue blade."},
    "Rakshasa Bow":    {"type": "wep", "atk": 45, "cost": {"Iron Ore": 10, "Demon Blood": 5}, "desc": "Draws blood on impact."},
    "Thunder Scepter": {"type": "wep", "atk": 120, "cost": {"Star Metal": 10, "Soma Drop": 2}, "desc": "Crackles with lightning."},
    "Storm Trident":   {"type": "wep", "atk": 250, "cost": {"Star Metal": 20, "Soma Drop": 10}, "desc": "A legendary three-pronged spear."},
    "Kavacha Armor":   {"type": "arm", "hp": 200, "cost": {"Iron Ore": 20, "Naga Scale": 10}, "desc": "Sun-blessed armor."}
}

# RENAMED to Generic Fantasy Creatures to respect sentiments
VAHANAS = {
    "Gilded Rat":      {"name": "Gilded Rat",      "buff": "+10% Gold",   "stat": "gold_mult", "val": 0.1},
    "Emerald Peacock": {"name": "Emerald Peacock", "buff": "+15% Crit",   "stat": "crit",      "val": 0.15},
    "Ironclad Bull":   {"name": "Ironclad Bull",   "buff": "+200 Max HP", "stat": "hp",        "val": 200},
    "Storm Falcon":    {"name": "Storm Falcon",    "buff": "+20% Dodge",  "stat": "dodge",     "val": 0.2}
}

LOCATIONS = {
    "Varanasi": {"lvl": 1, "mats": ["Iron Ore"]},
    "Dandaka":  {"lvl": 10, "mats": ["Iron Ore", "Demon Blood"]},
    "Lanka":    {"lvl": 40, "mats": ["Demon Blood", "Naga Scale"]},
    "Kailash":  {"lvl": 70, "mats": ["Star Metal", "Soma Drop"]}
}

# ==============================================================================
# 🗄️ DATABASE
# ==============================================================================

class Database:
    def __init__(self, db_name="agni_v12.db"):
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
                vidya INTEGER DEFAULT 0,
                karma INTEGER DEFAULT 0,
                location TEXT DEFAULT 'Varanasi',
                meditate_start TEXT DEFAULT '0',
                chakras TEXT DEFAULT '[]',
                inventory TEXT DEFAULT '{}',
                materials TEXT DEFAULT '{}',
                equipment TEXT DEFAULT '{"wep": "None", "arm": "None", "mount": "None"}'
            )
        """)
        self.conn.commit()

    def get_user(self, uid):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        res = self.cursor.fetchone()
        if res:
            cols = ["user_id", "path", "level", "xp", "hp", "max_hp", "gold", "vidya", "karma", "location", "meditate_start", "chakras", "inventory", "materials", "equipment"]
            d = dict(zip(cols, res))
            for k in ["chakras", "inventory", "materials", "equipment"]:
                d[k] = json.loads(d[k])
            return d
        return None

    def create_user(self, uid, path="Kshatriya"):
        if not self.get_user(uid):
            p_stats = PATHS[path]["stats"]
            hp = 100 + p_stats["hp"]
            self.cursor.execute("INSERT INTO users (user_id, path, hp, max_hp) VALUES (?, ?, ?, ?)", (uid, path, hp, hp))
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
        super().__init__(title=f"🕉️ {title}", description=description, color=color)
        if user:
            u = db.get_user(user.id)
            if u:
                path = u.get('path', 'Unknown')
                lvl = u.get('level', 1)
                self.set_footer(text=f"{path} • Lvl {lvl} • {ICONS['gold']} {u['gold']}")

def render_hp(curr, max_val, length=10):
    pct = max(0, min(1, curr / max(1, max_val)))
    filled = int(length * pct)
    c = "🟩" if pct > 0.5 else "🟥"
    return f"{c*filled}{'⬛'*(length-filled)} `{curr}/{max_val}`"

def calculate_stats(u):
    # Base Stats
    path_stats = PATHS.get(u['path'], PATHS['Kshatriya'])['stats']
    atk = (u['level'] * 3) + path_stats['atk']
    max_hp = u['max_hp']
    crit = path_stats['crit']
    
    # Gear Stats
    eq = u['equipment']
    if eq['wep'] in RECIPES: atk += RECIPES[eq['wep']]['atk']
    if eq['arm'] in RECIPES: max_hp += RECIPES[eq['arm']]['hp']
    
    # Mount Stats
    if eq['mount'] in VAHANAS:
        v = VAHANAS[eq['mount']]
        if v['stat'] == 'hp': max_hp += v['val']
        if v['stat'] == 'crit': crit += v['val']
        
    return {"atk": atk, "max_hp": max_hp, "crit": crit}

# ==============================================================================
# ⚒️ CRAFTING SYSTEM (FUSION)
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
# ⚔️ COMBAT SYSTEM (WAVE BASED)
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
        
        # Wave Logic
        self.wave = 1
        self.max_waves = 3
        self.logs = ["⚔️ **Encounter Started!**"]
        self.spawn_enemy()

    def spawn_enemy(self):
        lvl = self.u['level'] + (self.wave - 1) * 2
        names = ["Asura", "Rakshasa", "Pishacha", "Naga Warrior"]
        mats = LOCATIONS.get(self.loc, LOCATIONS["Varanasi"])["mats"]
        
        self.enemy = {
            "name": f"{random.choice(names)}",
            "lvl": lvl,
            "hp": 50 + (lvl * 15),
            "max_hp": 50 + (lvl * 15),
            "atk": 10 + (lvl * 2),
            "drop_mat": random.choice(mats)
        }
        self.logs.append(f"⚠️ **Wave {self.wave}/{self.max_waves}:** {self.enemy['name']} appeared!")

    def get_embed(self, status="FIGHT"):
        c = COLORS["CRIMSON"] if status=="FIGHT" else (COLORS["GREEN"] if status=="WIN" else COLORS["VOID"])
        e = discord.Embed(title=f"⚔️ {self.loc} (Wave {self.wave})", color=c)
        
        e.add_field(name="🛡️ You", value=render_hp(self.u['hp'], self.stats['max_hp']), inline=True)
        e.add_field(name=f"👹 {self.enemy['name']}", value=render_hp(self.enemy['hp'], self.enemy['max_hp']), inline=True)
        
        log_txt = "\n".join(self.logs[-5:])
        e.add_field(name="📜 Log", value=f"```diff\n{log_txt}\n```", inline=False)
        return e

    async def end_turn(self, interaction):
        if self.enemy['hp'] <= 0:
            # Wave Clear
            mat = self.enemy['drop_mat']
            self.u['materials'][mat] = self.u['materials'].get(mat, 0) + 1
            self.logs.append(f"📦 Dropped: {mat}")
            
            if self.wave < self.max_waves:
                self.wave += 1
                self.spawn_enemy()
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
            else:
                # Dungeon Clear
                gold = 50 * self.u['level']
                xp = 100 * self.u['level']
                self.u['gold'] += gold
                self.u['xp'] += xp
                
                # Check Level Up
                if self.u['xp'] >= self.u['level'] * 150:
                    self.u['level'] += 1
                    self.u['xp'] = 0
                    self.logs.append("✨ **LEVEL UP!**")
                
                db.update_user(self.user.id, self.u)
                
                embed = self.get_embed("WIN")
                embed.add_field(name="Rewards", value=f"🪙 {gold} Gold\n✨ {xp} XP\n📦 Gathered Materials")
                await interaction.response.edit_message(embed=embed, view=None)
            return

        # Enemy Turn
        dmg = random.randint(int(self.enemy['atk']*0.8), int(self.enemy['atk']*1.2))
        
        # Mount Dodge
        if self.u['equipment']['mount'] == "Storm Falcon" and random.random() < 0.2:
            self.logs.append("💨 Storm Falcon dodged the attack!")
        else:
            self.u['hp'] -= dmg
            self.logs.append(f"- Enemy hit for {dmg}!")

        if self.u['hp'] <= 0:
            self.u['hp'] = 10
            db.update_user(self.user.id, self.u)
            embed = self.get_embed("LOSE")
            embed.description = "You fell in the dungeon..."
            await interaction.response.edit_message(embed=embed, view=None)
            return

        db.update_user(self.user.id, self.u)
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
            
        self.enemy['hp'] -= dmg
        await self.end_turn(interaction)

    @ui.button(label="Heal", style=discord.ButtonStyle.success, emoji="🧪")
    async def heal(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id: return
        inv = self.u['inventory']
        if inv.get("Soma", 0) > 0:
            inv["Soma"] -= 1
            heal = 100
            self.u['hp'] = min(self.stats['max_hp'], self.u['hp'] + heal)
            self.logs.append("+ Used Soma (+100 HP)")
            await self.end_turn(interaction)
        else:
            await interaction.response.send_message("No Soma!", ephemeral=True)

# ==============================================================================
# 🐣 MOUNT SYSTEM (STABLES)
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
        print("🔥 Agni 12.0 (Respect) is Online.")

bot = AgniBot()

@bot.tree.command(name="start", description="Begin your saga")
async def start(interaction: discord.Interaction):
    if db.create_user(interaction.user.id):
        await interaction.response.send_message("🕉️ **Soul Awakened.** Use `/battle` to gather materials.")
    else:
        await interaction.response.send_message("You are already on the path.", ephemeral=True)

@bot.tree.command(name="battle", description="Enter the Dungeon (3 Waves)")
async def battle(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if not u: return await interaction.response.send_message("Use `/start` first.")
    if u['hp'] < 20: return await interaction.response.send_message("🩸 Too weak! Heal first.", ephemeral=True)
    
    await interaction.response.send_message(view=CombatView(interaction.user, u['location']))

@bot.tree.command(name="forge", description="Craft Powerful Weapons")
async def forge(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if not u: return await interaction.response.send_message("Use `/start` first.")
    
    mat_str = ", ".join([f"{k}: {v}" for k,v in u['materials'].items()]) or "None"
    embed = DharmaEmbed("Cosmic Forge", f"**Your Materials:**\n{mat_str}\n\nSelect a recipe below to perform Fusion.")
    await interaction.response.send_message(embed=embed, view=CraftingView(interaction.user.id))

@bot.tree.command(name="stables", description="Equip Spirit Mounts")
async def stables(interaction: discord.Interaction):
    await interaction.response.send_message("🐾 **Divine Stables**\nBond with a creature for 500 Gold.", view=MountView(interaction.user.id))

@bot.tree.command(name="profile", description="View Gear and Stats")
async def profile(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if not u: return await interaction.response.send_message("Use `/start` first.")
    
    stats = calculate_stats(u)
    eq = u['equipment']
    
    embed = DharmaEmbed("Hero Profile", user=interaction.user)
    embed.add_field(name="Stats", value=f"❤️ HP: {u['hp']}/{stats['max_hp']}\n⚔️ ATK: {stats['atk']}\n🎯 Crit: {int(stats['crit']*100)}%", inline=True)
    embed.add_field(name="Equipment", value=f"🗡️ Wep: {eq['wep']}\n🛡️ Arm: {eq['arm']}\n🐾 Mount: {eq['mount']}", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="travel", description="Move to new regions (Better Mats)")
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

@bot.tree.command(name="heal", description="Full Heal (Costs 100g)")
async def heal(interaction: discord.Interaction):
    u = db.get_user(interaction.user.id)
    if u['gold'] < 100: return await interaction.response.send_message("Need 100 Gold.", ephemeral=True)
    
    stats = calculate_stats(u)
    u['gold'] -= 100
    u['hp'] = stats['max_hp']
    db.update_user(interaction.user.id, u)
    await interaction.response.send_message("💚 Fully Healed.")

bot.run(TOKEN)
