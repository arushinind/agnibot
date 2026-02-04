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
# ⚙️ CONFIGURATION & ASSETS
# ==============================================================================

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ WARNING: DISCORD_TOKEN not found.")

COLORS = {
    "GOLD": 0xFFD700, "CRIMSON": 0xDC143C, "CYAN": 0x00FFFF, "PURPLE": 0x9400D3,
    "GREEN": 0x32CD32, "ORANGE": 0xFF8C00, "SAFFRON": 0xFF9933, "VOID": 0x2C2F33,
    "CHAKRA": 0xFF1493, "DANGER": 0xFF0000
}

ICONS = {
    "hp": "❤️", "gold": "🪙", "xp": "✨", "karma": "🌟", "vidya": "📜",
    "atk": "⚔️", "def": "🛡️", "meditate": "🧘", "travel": "🌏",
    "shop": "🏪", "profile": "👤", "battle": "👹", "menu": "🏠"
}

# ==============================================================================
# 📜 GAME DATA
# ==============================================================================

HINDU_FACTS = [
    "The Rigveda (c. 1500 BCE) mentions the 'Sapta Sindhu' (Seven Rivers) of Punjab.",
    "Sushruta described rhinoplasty (plastic surgery) in 600 BCE.",
    "Kanada (c. 600 BCE) proposed the atomic theory (Vaisheshika) centuries before Dalton.",
    "The concept of 'Maya' (Illusion) is central to Advaita Vedanta philosophy.",
    "The number system we use today (1-9 and 0) originated in India."
]

CHAKRAS = {
    "Muladhara":   {"name": "Root", "cost": 500, "vidya": 2, "effect": "+50 Max HP", "stat": "hp", "val": 50, "color": "🔴"},
    "Swadhisthana":{"name": "Sacral", "cost": 1000, "vidya": 5, "effect": "+10% Gold", "stat": "gold_mult", "val": 0.1, "color": "🟠"},
    "Manipura":    {"name": "Solar", "cost": 2500, "vidya": 10, "effect": "+20 Atk", "stat": "atk", "val": 20, "color": "🟡"},
    "Anahata":     {"name": "Heart", "cost": 5000, "vidya": 20, "effect": "HP Regen", "stat": "regen", "val": 10, "color": "🟢"},
    "Vishuddha":   {"name": "Throat", "cost": 10000, "vidya": 35, "effect": "+20% XP", "stat": "xp_mult", "val": 0.2, "color": "🔵"},
    "Ajna":        {"name": "3rd Eye", "cost": 25000, "vidya": 50, "effect": "+15% Crit", "stat": "crit", "val": 0.15, "color": "🟣"},
    "Sahasrara":   {"name": "Crown", "cost": 50000, "vidya": 100, "effect": "Moksha Boost", "stat": "moksha", "val": 1, "color": "⚪"}
}

LOCATIONS = {
    "Varanasi": {"level": 1, "desc": "City of Lights", "img": "https://i.imgur.com/8Q5Q5Q5.png"}, # Placeholder logic
    "Dandaka Forest": {"level": 10, "desc": "Exile Grounds"},
    "Kishkindha": {"level": 25, "desc": "Vanara Kingdom"},
    "Lanka": {"level": 50, "desc": "Golden Fortress"},
    "Kailash": {"level": 80, "desc": "Holy Peak"}
}

ITEMS = {
    "Soma": {"type": "heal", "val": 100, "price": 100, "karma": 0, "desc": "Heals 100 HP"},
    "Amrit": {"type": "heal", "val": 9999, "price": 1000, "karma": 20, "desc": "Full Heal"},
    "Agneyastra": {"type": "dmg", "val": 500, "price": 3000, "karma": 0, "desc": "500 DMG"},
    "Brahmastra": {"type": "dmg", "val": 2000, "price": 10000, "karma": 50, "desc": "2000 DMG"},
}

# ==============================================================================
# 🗄️ DATABASE SYSTEM
# ==============================================================================

class Database:
    def __init__(self, db_name="dharma_v7.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                hp INTEGER DEFAULT 100,
                max_hp INTEGER DEFAULT 100,
                gold INTEGER DEFAULT 0,
                vidya INTEGER DEFAULT 0,
                karma INTEGER DEFAULT 0,
                location TEXT DEFAULT 'Varanasi',
                meditate_start TEXT DEFAULT '0',
                chakras_unlocked TEXT DEFAULT '[]',
                inventory TEXT DEFAULT '{}',
                ashram TEXT DEFAULT 'None'
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ashrams (
                name TEXT PRIMARY KEY,
                leader_id INTEGER,
                members TEXT
            )
        """)
        self.conn.commit()

    def get_user(self, uid):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        res = self.cursor.fetchone()
        if res:
            cols = ["user_id", "level", "xp", "hp", "max_hp", "gold", "vidya", "karma", "location", "meditate_start", "chakras", "inventory", "ashram"]
            d = dict(zip(cols, res))
            d["chakras"] = json.loads(d["chakras"])
            d["inventory"] = json.loads(d["inventory"])
            return d
        return None

    def create_user(self, uid):
        if not self.get_user(uid):
            self.cursor.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
            self.conn.commit()
            return True
        return False

    def update_user(self, uid, data):
        clauses = []
        vals = []
        for k, v in data.items():
            if k == "user_id": continue
            clauses.append(f"{k}=?")
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
        vals.append(uid)
        self.cursor.execute(f"UPDATE users SET {', '.join(clauses)} WHERE user_id=?", vals)
        self.conn.commit()

db = Database()

# ==============================================================================
# 🎨 UI COMPONENTS (The "1000x Better" Part)
# ==============================================================================

class DharmaEmbed(discord.Embed):
    def __init__(self, title, description=None, color=COLORS["SAFFRON"], user_data=None, user_obj=None):
        super().__init__(title=f"🕉️ {title}", description=description, color=color)
        if user_data and user_obj:
            txt = f"Lvl {user_data['level']} • {ICONS['gold']} {user_data['gold']} • {ICONS['karma']} {user_data['karma']}"
            self.set_author(name=user_obj.display_name, icon_url=user_obj.display_avatar.url)
            self.set_footer(text=txt)
        else:
            self.set_footer(text=f"📜 {random.choice(HINDU_FACTS)}")

def render_health_bar(current, max_val, length=10):
    pct = max(0, min(1, current / max(1, max_val)))
    filled = int(length * pct)
    
    # Dynamic Color Logic
    if pct > 0.6: char = "🟩"
    elif pct > 0.3: char = "🟨"
    else: char = "🟥"
    
    bar = char * filled + "⬛" * (length - filled)
    return f"{bar} `{current}/{max_val}`"

def render_chakra_tree(unlocked_list):
    # Creates a visual tree: 🔴─🟠─🟡...
    tree = []
    for key, data in CHAKRAS.items():
        if key in unlocked_list:
            tree.append(data['color'])
        else:
            tree.append("🔒")
    return "─".join(tree)

# ==============================================================================
# 🏠 DASHBOARD (MAIN MENU)
# ==============================================================================

class DashboardView(ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    async def refresh_embed(self, interaction):
        u = db.get_user(self.user.id)
        embed = DharmaEmbed("Sanctum Dashboard", "Navigate your spiritual journey.", user_data=u, user_obj=self.user)
        
        # Stats Grid
        embed.add_field(name="Vitality", value=f"{ICONS['hp']} {u['hp']}/{u['max_hp']}\n{ICONS['xp']} {u['xp']}", inline=True)
        embed.add_field(name="Wealth", value=f"{ICONS['gold']} {u['gold']}\n{ICONS['vidya']} {u['vidya']}", inline=True)
        embed.add_field(name="Location", value=f"{ICONS['travel']} **{u['location']}**", inline=True)
        
        # Chakra Visual
        tree = render_chakra_tree(u['chakras'])
        embed.add_field(name="Chakras", value=f"{tree}", inline=False)
        
        # Quick Inventory
        inv_preview = ", ".join([f"{k} x{v}" for k,v in u['inventory'].items()]) or "Empty"
        embed.add_field(name="Satchel", value=inv_preview, inline=False)
        
        return embed

    @ui.button(label="Battle", style=discord.ButtonStyle.danger, emoji=ICONS["battle"], row=0)
    async def battle(self, interaction: discord.Interaction, button: ui.Button):
        u = db.get_user(self.user.id)
        if u['hp'] < 10: return await interaction.response.send_message("🩸 Too weak! Meditate or Heal.", ephemeral=True)
        
        lvl = u['level']
        enemy = {"name": f"Asura Lvl {lvl}", "hp": 50+(lvl*15), "max_hp": 50+(lvl*15), "atk": 10+lvl, "xp": 20+(lvl*5), "gold": 15+lvl}
        await interaction.response.send_message(view=CombatView(self.user, enemy), ephemeral=True)

    @ui.button(label="Meditate", style=discord.ButtonStyle.success, emoji=ICONS["meditate"], row=0)
    async def meditate(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(view=MeditateView(), ephemeral=True)

    @ui.button(label="Shop", style=discord.ButtonStyle.primary, emoji=ICONS["shop"], row=0)
    async def shop(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(view=ShopView(self.user.id), ephemeral=True)

    @ui.button(label="Chakras", style=discord.ButtonStyle.secondary, emoji="🕉️", row=1)
    async def chakras(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(view=ChakraView(self.user), ephemeral=True)

    @ui.button(label="Travel", style=discord.ButtonStyle.secondary, emoji=ICONS["travel"], row=1)
    async def travel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(view=TravelView(self.user.id), ephemeral=True)
    
    @ui.button(label="Refresh", style=discord.ButtonStyle.gray, emoji="🔄", row=1)
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id: return
        embed = await self.refresh_embed(interaction)
        await interaction.message.edit(embed=embed)
        await interaction.response.defer()

# ==============================================================================
# ⚔️ COMBAT SYSTEM (Enhanced UI)
# ==============================================================================

class CombatView(ui.View):
    def __init__(self, user, enemy):
        super().__init__(timeout=180)
        self.user = user
        self.u = db.get_user(user.id)
        self.enemy = enemy
        
        # Apply Passives
        self.atk_mult = 1.0 + (0.2 if "Manipura" in self.u['chakras'] else 0)
        self.crit_chance = 0.05 + (0.15 if "Ajna" in self.u['chakras'] else 0)
        self.regen = 10 if "Anahata" in self.u['chakras'] else 0
        
        self.logs = ["⚔️ **Encounter started!**"]
        self.turn = 1

    def get_embed(self, status="FIGHT"):
        c = COLORS["DANGER"] if status == "FIGHT" else (COLORS["GREEN"] if status == "WIN" else COLORS["VOID"])
        e = discord.Embed(title=f"⚔️ Battle vs {self.enemy['name']}", color=c)
        
        # Layout: Side by Side Fields
        e.add_field(name=f"🛡️ {self.user.display_name}", value=render_health_bar(self.u['hp'], self.u['max_hp']), inline=True)
        e.add_field(name=f"👹 {self.enemy['name']}", value=render_health_bar(self.enemy['hp'], self.enemy['max_hp']), inline=True)
        
        # Battle Log Area
        last_log = self.logs[-1]
        history = "\n".join(self.logs[-4:-1]) # Previous 3 logs
        
        e.add_field(name="⚡ Latest Action", value=f"> {last_log}", inline=False)
        if history:
            e.add_field(name="📜 History", value=f"```diff\n{history}\n```", inline=False)
            
        return e

    async def end_turn(self, interaction):
        # Regen
        if self.regen > 0 and self.u['hp'] < self.u['max_hp']:
            self.u['hp'] = min(self.u['max_hp'], self.u['hp'] + self.regen)

        if self.enemy['hp'] <= 0:
            xp = self.enemy['xp'] * (1.2 if "Vishuddha" in self.u['chakras'] else 1.0)
            gold = self.enemy['gold']
            
            self.u['xp'] += int(xp)
            self.u['gold'] += gold
            self.u['karma'] += 1
            
            # Level Up Check
            lvl_msg = ""
            if self.u['xp'] >= self.u['level'] * 100:
                self.u['level'] += 1
                self.u['xp'] = 0
                self.u['max_hp'] += 10
                self.u['hp'] = self.u['max_hp']
                lvl_msg = "\n✨ **LEVEL UP!**"

            db.update_user(self.user.id, self.u)
            
            embed = self.get_embed("WIN")
            embed.add_field(name="🏆 VICTORY", value=f"Gained: **{int(xp)} XP** | **{gold} Gold**{lvl_msg}", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            return

        # Enemy Turn
        dmg = random.randint(int(self.enemy['atk']*0.8), int(self.enemy['atk']*1.2))
        self.u['hp'] -= dmg
        self.logs.append(f"🩸 Enemy hit you for **{dmg}** damage!")
        
        if self.u['hp'] <= 0:
            self.u['hp'] = 10
            db.update_user(self.user.id, self.u)
            embed = self.get_embed("LOSE")
            embed.add_field(name="💀 DEFEAT", value="You retreated to heal.", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            return

        db.update_user(self.user.id, self.u)
        self.turn += 1
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Strike", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def attack(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id: return
        
        dmg = int(((self.u['level'] * 2) + 10) * self.atk_mult)
        if random.random() < self.crit_chance:
            dmg *= 2
            self.logs.append(f"💥 **CRITICAL HIT!** You dealt **{dmg}**!")
        else:
            self.logs.append(f"🗡️ You hit for **{dmg}**.")
            
        self.enemy['hp'] -= dmg
        await self.end_turn(interaction)

    @ui.button(label="Mantra", style=discord.ButtonStyle.primary, emoji="🕉️")
    async def mantra(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id: return
        dmg = int(self.u['vidya'] * 5) + 40
        self.enemy['hp'] -= dmg
        self.logs.append(f"✨ **Mantra Blast!** You dealt **{dmg}** magic dmg.")
        await self.end_turn(interaction)

# ==============================================================================
# 🛒 SHOP & TRAVEL & CHAKRAS
# ==============================================================================

class ShopView(ui.View):
    def __init__(self, uid):
        super().__init__()
        self.uid = uid
        self.add_item(ShopSelect(uid))

class ShopSelect(ui.Select):
    def __init__(self, uid):
        self.uid = uid
        opts = []
        for k,v in ITEMS.items():
            opts.append(discord.SelectOption(
                label=f"{k} ({v['price']} G)", 
                description=f"Karma: {v['karma']} | {v['desc']}", 
                value=k,
                emoji="💊" if v['type'] == 'heal' else "🔥"
            ))
        super().__init__(placeholder="Select an item...", options=opts)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid: return
        item = ITEMS[self.values[0]]
        u = db.get_user(self.uid)
        
        if u['gold'] < item['price']:
            return await interaction.response.send_message("❌ **Insufficient Funds.**", ephemeral=True)
        if u['karma'] < item['karma']:
            return await interaction.response.send_message(f"❌ **Karma too low.** Need {item['karma']}.", ephemeral=True)
            
        u['gold'] -= item['price']
        u['inventory'][self.values[0]] = u['inventory'].get(self.values[0], 0) + 1
        db.update_user(self.uid, u)
        
        await interaction.response.send_message(f"✅ Purchased **{self.values[0]}**!", ephemeral=True)

class TravelView(ui.View):
    def __init__(self, uid):
        super().__init__()
        self.uid = uid
        opts = []
        for k, v in LOCATIONS.items():
            opts.append(discord.SelectOption(label=k, description=f"Lvl {v['level']}+", value=k, emoji="📍"))
        self.add_item(TravelSelect(uid, opts))

class TravelSelect(ui.Select):
    def __init__(self, uid, opts):
        self.uid = uid
        super().__init__(placeholder="Journey to...", options=opts)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid: return
        dest = self.values[0]
        u = db.get_user(self.uid)
        
        if u['level'] < LOCATIONS[dest]['level']:
            return await interaction.response.send_message("🔒 **Level too low.**", ephemeral=True)
        
        u['location'] = dest
        db.update_user(self.uid, u)
        await interaction.response.send_message(f"🌏 You have arrived at **{dest}**.", ephemeral=True)

class ChakraView(ui.View):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.u = db.get_user(user.id)
        
        for k, v in CHAKRAS.items():
            unlocked = k in self.u['chakras']
            btn = ui.Button(
                label=f"{v['name']}", 
                style=discord.ButtonStyle.success if unlocked else discord.ButtonStyle.secondary,
                emoji=v['color'],
                disabled=unlocked
            )
            btn.callback = self.create_cb(k, v)
            self.add_item(btn)

    def create_cb(self, key, data):
        async def cb(interaction):
            if interaction.user.id != self.user.id: return
            if self.u['gold'] < data['cost'] or self.u['vidya'] < data['vidya']:
                return await interaction.response.send_message(f"❌ Need {data['cost']} Gold & {data['vidya']} Vidya.", ephemeral=True)
            
            self.u['gold'] -= data['cost']
            self.u['chakras'].append(key)
            
            # Apply passive
            if data['stat'] == 'hp':
                self.u['max_hp'] += data['val']
                self.u['hp'] += data['val']
                
            db.update_user(self.user.id, self.u)
            await interaction.response.send_message(f"✨ **{data['name']} Chakra Awakened!**", ephemeral=True)
            # Refresh View
            await interaction.message.edit(view=ChakraView(self.user))
        return cb

# ==============================================================================
# 🧘 ANIMATED MEDITATION
# ==============================================================================

class MeditateView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Focus", style=discord.ButtonStyle.success, emoji="🧘")
    async def focus(self, interaction: discord.Interaction, button: ui.Button):
        db.update_user(interaction.user.id, {"meditate_start": str(time.time())})
        await interaction.response.send_message("🧘 **You enter a deep trance...**\n*Click 'Awaken' when ready to return.*", ephemeral=True)

    @ui.button(label="Awaken", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def awaken(self, interaction: discord.Interaction, button: ui.Button):
        u = db.get_user(interaction.user.id)
        start = float(u['meditate_start'])
        if start == 0: return await interaction.response.send_message("You are not meditating.", ephemeral=True)
        
        mins = int((time.time() - start) / 60)
        if mins < 1: return await interaction.response.send_message("Too soon. Clear your mind.", ephemeral=True)
        
        xp, hp = mins * 10, mins * 5
        u['meditate_start'] = "0"
        u['xp'] += xp
        u['hp'] = min(u['max_hp'], u['hp'] + hp)
        u['vidya'] += int(mins / 5)
        
        db.update_user(interaction.user.id, u)
        await interaction.response.send_message(embed=DharmaEmbed("Awakening", f"Time: {mins}m\n+{xp} XP | +{hp} HP | +{int(mins/5)} Vidya", COLORS["CYAN"]))

# ==============================================================================
# 🚀 MAIN BOT
# ==============================================================================

class AgniBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        await self.tree.sync()
        print("🔥 Agni 7.0 (Nirvana) is Online.")

bot = AgniBot()

@bot.tree.command(name="menu", description="Open the Game Dashboard")
async def menu(interaction: discord.Interaction):
    if db.create_user(interaction.user.id):
        await interaction.response.send_message("Welcome, Seeker.", ephemeral=True)
    
    view = DashboardView(interaction.user)
    embed = await view.refresh_embed(interaction)
    await interaction.response.send_message(embed=embed, view=view)

bot.run(TOKEN)
