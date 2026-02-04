import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import sqlite3
import random
import time
import json
import math
from typing import Optional, List, Dict

# ==============================================================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==============================================================================

TOKEN = "YOUR_TOKEN_HERE"  # ⚠️ REPLACE THIS

# 🎨 Theme Colors
C_GOLD = 0xFFD700
C_RED = 0xDC143C
C_BLUE = 0x1E90FF
C_GREEN = 0x32CD32
C_PURPLE = 0x9400D3
C_DARK = 0x2F3136

# ==============================================================================
# 📜 DATA REPOSITORY (Classes, Skills, Items)
# ==============================================================================

CLASSES = {
    "Kshatriya": {
        "desc": "Warrior. High HP/ATK. Master of weapons.",
        "stats": {"hp": 150, "mp": 30, "atk": 12, "def": 5, "spd": 2},
        "skills": ["Heavy Strike", "Shield Bash", "Rage"]
    },
    "Brahmin": {
        "desc": "Sage. High MP/Magic. Master of Astras.",
        "stats": {"hp": 80, "mp": 100, "atk": 5, "def": 2, "spd": 4},
        "skills": ["Agni Blast", "Vayu Cutter", "Soma Heal"]
    },
    "Vanara": {
        "desc": "Trickster. High Crit/Speed. Master of agility.",
        "stats": {"hp": 100, "mp": 50, "atk": 10, "def": 3, "spd": 8},
        "skills": ["Twin Strike", "Ambush", "Dodge"]
    }
}

SKILLS = {
    # Kshatriya
    "Heavy Strike": {"cost": 10, "type": "dmg", "val": 1.5, "desc": "Deals 150% DMG."},
    "Shield Bash": {"cost": 15, "type": "stun", "val": 0, "desc": "Stuns enemy for 1 turn."},
    "Rage": {"cost": 20, "type": "buff_atk", "val": 2.0, "desc": "Double ATK for next turn."},
    
    # Brahmin
    "Agni Blast": {"cost": 25, "type": "dmg_magic", "val": 2.5, "desc": "Blast of holy fire (250% Magic DMG)."},
    "Vayu Cutter": {"cost": 15, "type": "dmg_magic", "val": 1.2, "desc": "Wind blade. Ignores Defense."},
    "Soma Heal": {"cost": 30, "type": "heal", "val": 50, "desc": "Heals 50% Max HP."},
    
    # Vanara
    "Twin Strike": {"cost": 15, "type": "multi", "val": 2, "desc": "Hit twice (80% DMG each)."},
    "Ambush": {"cost": 20, "type": "crit", "val": 100, "desc": "Next hit is guaranteed Crit."},
    "Dodge": {"cost": 10, "type": "buff_spd", "val": 999, "desc": "Evade next attack."},
}

MOBS = {
    "Varanasi": [
        {"n": "Street Thug", "hp": 50, "atk": 8, "xp": 15, "g": 10},
        {"n": "Rabid Dog", "hp": 40, "atk": 12, "xp": 12, "g": 5},
    ],
    "Dandaka Forest": [
        {"n": "Rakshasa Scout", "hp": 150, "atk": 25, "xp": 50, "g": 30},
        {"n": "Giant Python", "hp": 200, "atk": 20, "xp": 60, "g": 40},
    ],
    "Lanka": [
        {"n": "Asura General", "hp": 500, "atk": 60, "xp": 200, "g": 150},
        {"n": "Dark Sorcerer", "hp": 350, "atk": 80, "xp": 250, "g": 120},
    ]
}

# Renamed from PETS to RELICS for cultural respect
RELICS = {
    "Vajra Pendant": {"stat": "atk", "val": 5, "desc": "+5 ATK (Strength)"},
    "Wind Anklet": {"stat": "spd", "val": 5, "desc": "+5 SPD (Agility)"},
    "Rudraksha Bead": {"stat": "hp", "val": 50, "desc": "+50 HP (Vitality)"}
}

# ==============================================================================
# 🗄️ DATABASE
# ==============================================================================

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("agni_v4.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                uid INTEGER PRIMARY KEY,
                name TEXT,
                p_class TEXT DEFAULT 'Kshatriya',
                lvl INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                hp INTEGER DEFAULT 100,
                mp INTEGER DEFAULT 50,
                max_hp INTEGER DEFAULT 100,
                max_mp INTEGER DEFAULT 50,
                stats TEXT DEFAULT '{"atk": 10, "def": 5, "spd": 5}',
                gold INTEGER DEFAULT 100,
                loc TEXT DEFAULT 'Varanasi',
                relic TEXT DEFAULT 'None',
                inventory TEXT DEFAULT '{}'
            )
        """)
        self.conn.commit()

    def get_player(self, uid):
        self.cursor.execute("SELECT * FROM players WHERE uid=?", (uid,))
        row = self.cursor.fetchone()
        if not row: return None
        cols = ["uid", "name", "p_class", "lvl", "xp", "hp", "mp", "max_hp", "max_mp", "stats", "gold", "loc", "relic", "inv"]
        d = dict(zip(cols, row))
        d["stats"] = json.loads(d["stats"])
        d["inv"] = json.loads(d["inv"])
        return d

    def update_player(self, uid, data):
        clauses = []
        vals = []
        for k, v in data.items():
            if k == "uid": continue
            clauses.append(f"{k}=?")
            vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
        vals.append(uid)
        self.cursor.execute(f"UPDATE players SET {', '.join(clauses)} WHERE uid=?", vals)
        self.conn.commit()

    def create_player(self, uid, name, p_class):
        base = CLASSES[p_class]["stats"]
        stats = {"atk": base["atk"], "def": base["def"], "spd": base["spd"]}
        self.cursor.execute("""
            INSERT INTO players (uid, name, p_class, hp, max_hp, mp, max_mp, stats)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name, p_class, base["hp"], base["hp"], base["mp"], base["mp"], json.dumps(stats)))
        self.conn.commit()

db = Database()

# ==============================================================================
# 🛠️ UTILS
# ==============================================================================

def bar(curr, max_val, color="🟩", length=10):
    pct = max(0, min(1, curr / max(1, max_val)))
    filled = int(length * pct)
    return f"{color * filled}{'⬛' * (length - filled)}"

def calc_stats(p):
    s = p['stats'].copy()
    # Add Relic Bonus
    if p['relic'] in RELICS:
        bonus = RELICS[p['relic']]
        if bonus['stat'] in s:
            s[bonus['stat']] += bonus['val']
        elif bonus['stat'] == 'hp':
             # HP handled separately usually, but for max stats:
             pass 
    return s

# ==============================================================================
# ⚔️ TACTICAL COMBAT ENGINE
# ==============================================================================

class CombatView(ui.View):
    def __init__(self, p, mob):
        super().__init__(timeout=300)
        self.p = p
        self.mob = mob
        self.logs = []
        self.turn = 1
        
        # Init Combat Stats
        self.p_stats = calc_stats(p)
        self.m_hp = mob['hp']
        self.m_max = mob['hp']
        
        # Dynamic State
        self.buffs = {} # "atk_up": 2
        self.stunned = False
        self.next_enemy_move = "Attack"
        
        self.add_log(f"⚔️ **ENCOUNTER!** {mob['n']} blocks your path!")
        self.telegraph_enemy()

    def add_log(self, text):
        self.logs.append(text)
        if len(self.logs) > 6: self.logs.pop(0)

    def telegraph_enemy(self):
        # Enemy "AI" - decides move for NEXT turn
        moves = ["Attack", "Charge", "Block"]
        self.next_enemy_move = random.choice(moves)
        if self.next_enemy_move == "Charge":
            self.add_log(f"⚠️ **{self.mob['n']}** is gathering energy! (Danger)")
        elif self.next_enemy_move == "Block":
            self.add_log(f"🛡️ **{self.mob['n']}** raises a guard.")

    def get_embed(self, status="FIGHT"):
        c = C_RED if status == "FIGHT" else (C_GREEN if status == "WIN" else C_DARK)
        desc = f"**Turn {self.turn}** | {self.p['loc']}\n\n"
        
        # Player
        desc += f"**🛡️ {self.p['name']}** ({self.p['p_class']})\n"
        desc += f"HP: {bar(self.p['hp'], self.p['max_hp'])} {self.p['hp']}\n"
        desc += f"MP: {bar(self.p['mp'], self.p['max_mp'], '🟦')} {self.p['mp']}\n\n"
        
        # Enemy
        desc += f"**👹 {self.mob['n']}**\n"
        desc += f"HP: {bar(self.m_hp, self.m_max, '🟥')} {self.m_hp}\n"
        desc += f"Next Move: **{self.next_enemy_move}**\n\n"
        
        desc += "```diff\n" + "\n".join(self.logs) + "\n```"
        return discord.Embed(title=f"⚔️ BATTLE: {self.mob['n']}", description=desc, color=c)

    async def end_turn(self, interaction):
        if self.m_hp <= 0:
            # Win
            gold = self.mob['g']
            xp = self.mob['xp']
            self.p['gold'] += gold
            self.p['xp'] += xp
            
            # Level Up Check
            if self.p['xp'] >= self.p['lvl'] * 100:
                self.p['lvl'] += 1
                self.p['xp'] = 0
                self.p['max_hp'] += 20
                self.p['hp'] = self.p['max_hp']
                self.p['stats']['atk'] += 2
                self.add_log(f"✨ **LEVEL UP!** You are now Lvl {self.p['lvl']}!")

            db.update_player(self.p['uid'], self.p)
            embed = self.get_embed("WIN")
            embed.add_field(name="VICTORY", value=f"💰 +{gold} Gold\n✨ +{xp} XP")
            await interaction.response.edit_message(embed=embed, view=None)
            return

        # Enemy Action Execution
        if not self.stunned:
            dmg = 0
            msg = ""
            
            if self.next_enemy_move == "Attack":
                dmg = max(1, self.mob['atk'] - self.p_stats['def'])
                msg = f"attacks for {dmg} DMG!"
            elif self.next_enemy_move == "Charge":
                dmg = max(1, (self.mob['atk'] * 2.5) - self.p_stats['def'])
                msg = f"unleashes a DEVASTATING hit for {dmg} DMG!"
            elif self.next_enemy_move == "Block":
                msg = "held their guard."
            
            if dmg > 0:
                # Dodge check
                if random.randint(1, 100) < (self.p_stats['spd'] * 2):
                    self.add_log(f"💨 You DODGED the attack!")
                else:
                    self.p['hp'] -= int(dmg)
                    self.add_log(f"- {self.mob['n']} {msg}")
        else:
            self.add_log(f"💫 {self.mob['n']} is stunned and cannot move!")
            self.stunned = False # Reset stun

        if self.p['hp'] <= 0:
            self.p['hp'] = 10
            db.update_player(self.p['uid'], self.p)
            embed = self.get_embed("LOSE")
            embed.title = "💀 DEFEATED"
            await interaction.response.edit_message(embed=embed, view=None)
            return

        # Prep next turn
        self.turn += 1
        self.p['mp'] = min(self.p['max_mp'], self.p['mp'] + 5) # MP Regen
        self.telegraph_enemy()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Attack", style=discord.ButtonStyle.secondary, emoji="🗡️")
    async def atk_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.p['uid']: return
        dmg = max(1, self.p_stats['atk'])
        if self.next_enemy_move == "Block": dmg = int(dmg * 0.5)
        
        self.m_hp -= dmg
        self.add_log(f"+ You hit for {dmg} DMG.")
        await self.end_turn(interaction)

    @ui.button(label="Skills", style=discord.ButtonStyle.primary, emoji="✨")
    async def skill_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.p['uid']: return
        # Create a dropdown for skills dynamically
        view = SkillSelectView(self, CLASSES[self.p['p_class']]['skills'])
        await interaction.response.send_message("Choose a Mantra:", view=view, ephemeral=True)

    @ui.button(label="Defend", style=discord.ButtonStyle.success, emoji="🛡️")
    async def def_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.p['uid']: return
        self.p_stats['def'] += 10 # Temp boost
        self.add_log("🛡️ You assume a defensive stance.")
        self.p['mp'] += 10 # Defending restores MP
        await self.end_turn(interaction)
        self.p_stats['def'] -= 10 # Revert

class SkillSelectView(ui.View):
    def __init__(self, parent_view, skills):
        super().__init__()
        self.parent = parent_view
        self.add_item(SkillSelect(skills))

class SkillSelect(ui.Select):
    def __init__(self, skills):
        options = []
        for s in skills:
            data = SKILLS[s]
            options.append(discord.SelectOption(
                label=f"{s} ({data['cost']} MP)", 
                description=data['desc'], 
                value=s
            ))
        super().__init__(placeholder="Cast a Skill...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        skill_name = self.values[0]
        data = SKILLS[skill_name]
        
        if self.parent.p['mp'] < data['cost']:
            return await interaction.response.send_message("❌ Not enough MP!", ephemeral=True)
            
        self.parent.p['mp'] -= data['cost']
        
        # Execute Skill
        if data['type'] == 'dmg':
            dmg = int(self.parent.p_stats['atk'] * data['val'])
            self.parent.m_hp -= dmg
            self.parent.add_log(f"💥 {skill_name} deals {dmg} DMG!")
            
        elif data['type'] == 'heal':
            heal = int(self.parent.p['max_hp'] * (data['val']/100))
            self.parent.p['hp'] = min(self.parent.p['max_hp'], self.parent.p['hp'] + heal)
            self.parent.add_log(f"💚 {skill_name} heals {heal} HP!")
            
        elif data['type'] == 'stun':
            dmg = int(self.parent.p_stats['atk'] * 0.5)
            self.parent.m_hp -= dmg
            self.parent.stunned = True
            self.parent.add_log(f"💫 {skill_name} Stuns opponent! ({dmg} DMG)")
            
        elif data['type'] == 'multi':
            dmg = int(self.parent.p_stats['atk'] * 0.8)
            hits = data['val']
            total = dmg * hits
            self.parent.m_hp -= total
            self.parent.add_log(f"⚔️ {skill_name} hits {hits} times for {total} DMG!")

        await self.parent.end_turn(interaction)

# ==============================================================================
# 🎲 CHAUPAR (GAMBLING)
# ==============================================================================

class ChauparView(ui.View):
    def __init__(self, p, bet):
        super().__init__()
        self.p = p
        self.bet = bet
        
    @ui.button(label="Roll the Dice 🎲", style=discord.ButtonStyle.blurple)
    async def roll(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.p['uid']: return
        
        # Rigged? No. Random.
        player_roll = random.randint(2, 12)
        shakuni_roll = random.randint(2, 12)
        
        embed = discord.Embed(title="🎲 Chaupar Game", color=C_GOLD)
        embed.add_field(name="Your Roll", value=f"**{player_roll}**")
        embed.add_field(name="Shakuni's Roll", value=f"**{shakuni_roll}**")
        
        if player_roll > shakuni_roll:
            win = self.bet * 2
            self.p['gold'] += self.bet # (Original bet + win amount logic corrected: simply add bet amount to balance to simulate 2x return on investment)
            # Actually, standard logic: remove bet first, add 2x on win. 
            # We removed bet before calling view? No. Let's do it now.
            # Simplified:
            db.update_player(self.p['uid'], {"gold": self.p['gold'] + self.bet})
            embed.description = f"🎉 **YOU WON!** You gained {self.bet} Gold!"
            embed.color = C_GREEN
        elif player_roll < shakuni_roll:
            db.update_player(self.p['uid'], {"gold": self.p['gold'] - self.bet})
            embed.description = f"💀 **SHAKUNI WINS.** You lost {self.bet} Gold."
            embed.color = C_RED
        else:
            embed.description = "🤝 **DRAW.** No gold exchanged."
            
        await interaction.response.edit_message(embed=embed, view=None)

# ==============================================================================
# 🚀 MAIN COMMANDS
# ==============================================================================

class AgniBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        await self.tree.sync()
        print("🔥 Agni 4.0 (Mahabharata) is Ready.")

bot = AgniBot()

class ClassSelect(ui.Select):
    def __init__(self):
        opts = []
        for k, v in CLASSES.items():
            opts.append(discord.SelectOption(label=k, description=v['desc'], value=k))
        super().__init__(placeholder="Choose your Varna (Class)...", options=opts)
    
    async def callback(self, interaction: discord.Interaction):
        c = self.values[0]
        db.create_player(interaction.user.id, interaction.user.display_name, c)
        await interaction.response.send_message(f"🕉️ **Destiny Chosen.** You are now a **{c}**.")

class CreateView(ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(ClassSelect())

@bot.tree.command(name="start", description="Begin your epic saga")
async def start(interaction: discord.Interaction):
    if db.get_player(interaction.user.id):
        return await interaction.response.send_message("You are already on the path.", ephemeral=True)
    embed = discord.Embed(title="🕉️ Choose Your Path", description="The cycle of Samsara begins.", color=C_GOLD)
    await interaction.response.send_message(embed=embed, view=CreateView())

@bot.tree.command(name="battle", description="Tactical Combat")
async def battle(interaction: discord.Interaction):
    p = db.get_player(interaction.user.id)
    if not p: return await interaction.response.send_message("Use `/start` first.")
    
    if p['hp'] <= 0:
         return await interaction.response.send_message("💀 You are incapacitated. Use `/heal`.", ephemeral=True)

    loc = p['loc']
    mobs = MOBS.get(loc, MOBS["Varanasi"])
    mob = random.choice(mobs).copy()
    
    await interaction.response.send_message(view=CombatView(p, mob))

@bot.tree.command(name="profile", description="Check Stats & Skills")
async def profile(interaction: discord.Interaction):
    p = db.get_player(interaction.user.id)
    if not p: return await interaction.response.send_message("Use `/start` first.")
    
    s = p['stats']
    c_data = CLASSES[p['p_class']]
    
    embed = discord.Embed(title=f"📜 {p['name']} the {p['p_class']}", color=C_BLUE)
    embed.add_field(name="Vitals", value=f"❤️ HP: {p['hp']}/{p['max_hp']}\n🟦 MP: {p['mp']}/{p['max_mp']}", inline=True)
    embed.add_field(name="Attributes", value=f"⚔️ ATK: {s['atk']}\n🛡️ DEF: {s['def']}\n👟 SPD: {s['spd']}", inline=True)
    embed.add_field(name="Progression", value=f"✨ Lvl: {p['lvl']}\n💰 Gold: {p['gold']}\n📿 Relic: {p['relic']}", inline=True)
    embed.add_field(name="Skills", value=", ".join(c_data['skills']), inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="heal", description="Meditate to restore HP/MP")
async def heal(interaction: discord.Interaction):
    p = db.get_player(interaction.user.id)
    p['hp'] = p['max_hp']
    p['mp'] = p['max_mp']
    db.update_player(p['uid'], p)
    await interaction.response.send_message("🧘 **Om Namah Shivaya.** You are fully restored.")

@bot.tree.command(name="gamble", description="Play Chaupar against Shakuni")
async def gamble(interaction: discord.Interaction, amount: int):
    p = db.get_player(interaction.user.id)
    if p['gold'] < amount:
        return await interaction.response.send_message("🚫 You cannot afford this bet.", ephemeral=True)
    if amount < 10:
        return await interaction.response.send_message("🚫 Minimum bet is 10 Gold.", ephemeral=True)
        
    await interaction.response.send_message(f"🎲 Bet placed: **{amount} Gold**. Rolling...", view=ChauparView(p, amount))

@bot.tree.command(name="travel", description="Move to a new region")
async def travel(interaction: discord.Interaction):
    view = ui.View()
    select = ui.Select(placeholder="Select Region...")
    for loc in MOBS.keys():
        select.add_option(label=loc, value=loc)
        
    async def cb(inter):
        if inter.user.id != interaction.user.id: return
        p = db.get_player(inter.user.id)
        p['loc'] = select.values[0]
        db.update_player(p['uid'], p)
        await inter.response.send_message(f"🌏 Arrived in **{p['loc']}**.")
        
    select.callback = cb
    view.add_item(select)
    await interaction.response.send_message("Where will you go?", view=view)

bot.run(TOKEN)
