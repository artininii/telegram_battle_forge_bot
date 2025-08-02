import sqlite3
import random
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database initialization
def init_db():
    try:
        conn = sqlite3.connect('battle_forge.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY,
            username TEXT,
            sperms INTEGER DEFAULT 0,
            eggs INTEGER DEFAULT 0,
            water INTEGER DEFAULT 100,
            food INTEGER DEFAULT 100,
            medicine INTEGER DEFAULT 100,
            ore INTEGER DEFAULT 100,
            water_quality TEXT DEFAULT 'medium',
            food_quality TEXT DEFAULT 'medium',
            medicine_quality TEXT DEFAULT 'medium',
            ore_quality TEXT DEFAULT 'medium',
            coins INTEGER DEFAULT 10,
            war_wins INTEGER DEFAULT 0,
            last_resource_collect TEXT,
            last_supplies_collect TEXT,
            last_event TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS citizens (
            citizen_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT,
            role TEXT,
            health INTEGER,
            attack INTEGER,
            defense INTEGER,
            created_at TEXT,
            status TEXT DEFAULT 'active',
            injured_until TEXT,
            FOREIGN KEY (player_id) REFERENCES players (player_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS babies (
            baby_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT,
            created_at TEXT,
            born_at TEXT,
            is_born INTEGER DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players (player_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            item TEXT,
            quantity INTEGER,
            price INTEGER,
            currency TEXT,
            status TEXT DEFAULT 'open',
            FOREIGN KEY (seller_id) REFERENCES players (player_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            name TEXT UNIQUE,
            wins INTEGER DEFAULT 0,
            win_streak INTEGER DEFAULT 0,
            power INTEGER DEFAULT 100,
            FOREIGN KEY (player_id) REFERENCES players (player_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport TEXT,
            team_ids TEXT,  -- JSON list of team IDs
            max_teams INTEGER,
            status TEXT DEFAULT 'open',
            start_time TEXT,
            last_update_message_id INTEGER
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS wagers (
            wager_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            match_id INTEGER,
            team_id INTEGER,
            amount INTEGER,
            FOREIGN KEY (player_id) REFERENCES players (player_id),
            FOREIGN KEY (match_id) REFERENCES matches (match_id),
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )''')
        # Initialize AI teams
        c.execute('SELECT COUNT(*) FROM teams WHERE player_id IS NULL')
        if c.fetchone()[0] == 0:
            ai_teams = [
                "ThunderBolts", "IronVanguards", "BlazeCrusaders", "ShadowSprinters", "StormRiders",
                "CrimsonWolves", "FrostTitans", "NightSpecters", "SolarKnights", "LunarDefenders",
                "SteelPhantoms", "WildStallions", "GoldenHawks", "DarkScorpions", "SilverEagles",
                "EmeraldVipers", "ObsidianBears", "SapphireSharks"
            ]
            for name in ai_teams:
                c.execute('INSERT INTO teams (name, power) VALUES (?, 100)', (name,))
            conn.commit()
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise
    finally:
        conn.close()

# Initialize database
init_db()

# Helper functions
def get_player(conn, player_id):
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM players WHERE player_id = ?', (player_id,))
        return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching player {player_id}: {str(e)}")
        return None

def update_player(conn, player_id, username, sperms, eggs, water, food, medicine, ore, water_quality, food_quality, medicine_quality, ore_quality, coins, war_wins, last_resource_collect, last_supplies_collect, last_event):
    try:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO players (player_id, username, sperms, eggs, water, food, medicine, ore, water_quality, food_quality, medicine_quality, ore_quality, coins, war_wins, last_resource_collect, last_supplies_collect, last_event)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (player_id, username, sperms, eggs, water, food, medicine, ore, water_quality, food_quality, medicine_quality, ore_quality, coins, war_wins, last_resource_collect, last_supplies_collect, last_event))
        conn.commit()
        logger.debug(f"Updated player {player_id}")
    except Exception as e:
        logger.error(f"Error updating player {player_id}: {str(e)}")

def get_babies(conn, player_id):
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM babies WHERE player_id = ?', (player_id,))
        return c.fetchall()
    except Exception as e:
        logger.error(f"Error fetching babies for player {player_id}: {str(e)}")
        return []

def get_citizens(conn, player_id):
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM citizens WHERE player_id = ? AND status != "dead"', (player_id,))
        return c.fetchall()
    except Exception as e:
        logger.error(f"Error fetching citizens for player {player_id}: {str(e)}")
        return []

def create_citizen(conn, player_id, name, role, health, attack, defense, created_at):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO citizens (player_id, name, role, health, attack, defense, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, "active")',
                  (player_id, name, role, health, attack, defense, created_at))
        conn.commit()
        logger.debug(f"Created citizen for player {player_id}")
    except Exception as e:
        logger.error(f"Error creating citizen for player {player_id}: {str(e)}")

def initialize_player_citizens(conn, player_id):
    try:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM citizens WHERE player_id = ?', (player_id,))
        if c.fetchone()[0] == 0:
            for i in range(10000):
                role = random.choice(['worker', 'miner', 'fighter', 'teacher', 'professor', 'healer', 'engineer', 'trader', 'scout', 'workless'])
                health = random.randint(50, 80) + (10 if role == 'healer' else 0)
                attack = random.randint(15, 25) if role == 'fighter' else random.randint(5, 15)
                defense = random.randint(15, 25) if role == 'fighter' else random.randint(5, 15)
                create_citizen(conn, player_id, f"citizen_{i+1}", role, health, attack, defense, datetime.now().isoformat())
            logger.debug(f"Initialized 10,000 citizens for player {player_id}")
    except Exception as e:
        logger.error(f"Error initializing citizens for player {player_id}: {str(e)}")

def create_baby(conn, player_id, name, created_at):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO babies (player_id, name, created_at) VALUES (?, ?, ?)', (player_id, name, created_at))
        conn.commit()
        logger.debug(f"Created baby for player {player_id}")
        return c.lastrowid
    except Exception as e:
        logger.error(f"Error creating baby for player {player_id}: {str(e)}")
        return None

def update_baby(conn, baby_id, is_born, born_at):
    try:
        c = conn.cursor()
        c.execute('UPDATE babies SET is_born = ?, born_at = ? WHERE baby_id = ?', (is_born, born_at, baby_id))
        conn.commit()
        logger.debug(f"Updated baby {baby_id}")
    except Exception as e:
        logger.error(f"Error updating baby {baby_id}: {str(e)}")

def update_citizen(conn, citizen_id, status, injured_until=None):
    try:
        c = conn.cursor()
        if injured_until:
            c.execute('UPDATE citizens SET status = ?, injured_until = ? WHERE citizen_id = ?', (status, injured_until, citizen_id))
        else:
            c.execute('UPDATE citizens SET status = ? WHERE citizen_id = ?', (status, citizen_id))
        conn.commit()
        logger.debug(f"Updated citizen {citizen_id} status to {status}")
    except Exception as e:
        logger.error(f"Error updating citizen {citizen_id}: {str(e)}")

def create_trade(conn, seller_id, item, quantity, price, currency):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO trades (seller_id, item, quantity, price, currency) VALUES (?, ?, ?, ?, ?)',
                  (seller_id, item, quantity, price, currency))
        conn.commit()
        logger.debug(f"Created trade for player {seller_id}")
    except Exception as e:
        logger.error(f"Error creating trade for player {seller_id}: {str(e)}")

def get_open_trades(conn):
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM trades WHERE status = "open"')
        return c.fetchall()
    except Exception as e:
        logger.error(f"Error fetching open trades: {str(e)}")
        return []

def get_team(conn, team_id):
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM teams WHERE team_id = ?', (team_id,))
        return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching team {team_id}: {str(e)}")
        return None

def get_player_team(conn, player_id):
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM teams WHERE player_id = ?', (player_id,))
        return c.fetchone()
    except Exception as e:
        logger.error(f"Error fetching team for player {player_id}: {str(e)}")
        return None

def create_team(conn, player_id, name):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO teams (player_id, name, power) VALUES (?, ?, 100)', (player_id, name))
        conn.commit()
        logger.debug(f"Created team {name} for player {player_id}")
    except Exception as e:
        logger.error(f"Error creating team for player {player_id}: {str(e)}")
        raise

def update_team(conn, team_id, wins, win_streak, power):
    try:
        c = conn.cursor()
        c.execute('UPDATE teams SET wins = ?, win_streak = ?, power = ? WHERE team_id = ?',
                  (wins, win_streak, power, team_id))
        conn.commit()
        logger.debug(f"Updated team {team_id}")
    except Exception as e:
        logger.error(f"Error updating team {team_id}: {str(e)}")

def create_match(conn, sport, creator_team_id, max_teams):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO matches (sport, team_ids, max_teams, status, start_time) VALUES (?, ?, ?, ?, ?)',
                  (sport, json.dumps([creator_team_id]), max_teams, 'open', datetime.now().isoformat()))
        conn.commit()
        match_id = c.lastrowid
        logger.debug(f"Created match {match_id}: {sport} for {max_teams} teams")
        return match_id
    except Exception as e:
        logger.error(f"Error creating match: {str(e)}")
        return None

def update_match(conn, match_id, status, team_ids=None, last_update_message_id=None):
    try:
        c = conn.cursor()
        if team_ids is not None and last_update_message_id is not None:
            c.execute('UPDATE matches SET status = ?, team_ids = ?, last_update_message_id = ? WHERE match_id = ?',
                      (status, json.dumps(team_ids), last_update_message_id, match_id))
        elif team_ids is not None:
            c.execute('UPDATE matches SET status = ?, team_ids = ? WHERE match_id = ?',
                      (status, json.dumps(team_ids), match_id))
        elif last_update_message_id is not None:
            c.execute('UPDATE matches SET status = ?, last_update_message_id = ? WHERE match_id = ?',
                      (status, last_update_message_id, match_id))
        else:
            c.execute('UPDATE matches SET status = ? WHERE match_id = ?', (status, match_id))
        conn.commit()
        logger.debug(f"Updated match {match_id} to status {status}")
    except Exception as e:
        logger.error(f"Error updating match {match_id}: {str(e)}")

def create_wager(conn, player_id, match_id, team_id, amount):
    try:
        c = conn.cursor()
        c.execute('INSERT INTO wagers (player_id, match_id, team_id, amount) VALUES (?, ?, ?, ?)',
                  (player_id, match_id, team_id, amount))
        conn.commit()
        logger.debug(f"Created wager for player {player_id} on match {match_id}")
    except Exception as e:
        logger.error(f"Error creating wager for player {player_id}: {str(e)}")

def get_wagers(conn, match_id):
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM wagers WHERE match_id = ?', (match_id,))
        return c.fetchall()
    except Exception as e:
        logger.error(f"Error fetching wagers for match {match_id}: {str(e)}")
        return []

def can_collect_resources(player):
    if not player or not player[14]:
        return True
    last_collect = datetime.fromisoformat(player[14])
    return datetime.now() >= last_collect + timedelta(hours=24)

def can_collect_supplies(player):
    if not player or not player[15]:
        return True
    last_collect = datetime.fromisoformat(player[15])
    return datetime.now() >= last_collect + timedelta(hours=12)

def can_trigger_event(player):
    if not player or not player[16]:
        return True
    last_event = datetime.fromisoformat(player[16])
    return datetime.now() >= last_event + timedelta(hours=24)

def quality_modifier(quality):
    return {'high': 1.5, 'medium': 1.0, 'low': 0.5}[quality]

def grow_babies(conn, player_id):
    try:
        babies = get_babies(conn, player_id)
        player = get_player(conn, player_id)
        now = datetime.now()
        population = len(babies) + len(get_citizens(conn, player_id))
        overpopulation = population > (player[4] + player[5] + player[6] + player[7]) / 10
        for baby in babies:
            if baby[5] == 1:
                born_at = datetime.fromisoformat(baby[4])
                teachers = sum(1 for c in get_citizens(conn, player_id) if c[3] == 'teacher')
                growth_modifier = max(0.5, 1.0 - teachers * 0.1)
                if now >= born_at + timedelta(hours=24 * growth_modifier):
                    role = random.choice(['worker', 'miner', 'fighter', 'teacher', 'professor', 'healer', 'engineer', 'trader', 'scout', 'workless'])
                    health = random.randint(50, 80) + (10 if role == 'healer' else 0)
                    attack = random.randint(15, 25) if role == 'fighter' else random.randint(5, 15)
                    defense = random.randint(15, 25) if role == 'fighter' else random.randint(5, 15)
                    if role == 'fighter':
                        attack *= quality_modifier(player[11])
                        defense *= quality_modifier(player[11])
                    create_citizen(conn, player_id, baby[2], role, health, attack, defense, now.isoformat())
                    c = conn.cursor()
                    c.execute('DELETE FROM babies WHERE baby_id = ?', (baby[0],))
                    conn.commit()
            elif now >= datetime.fromisoformat(baby[3]) + timedelta(hours=9):
                base_chance = 0.5
                professors = sum(1 for c in get_citizens(conn, player_id) if c[3] == 'professor')
                chance = base_chance + sum(quality_modifier(player[i]) for i in [8, 9, 10, 11]) + professors * 0.1
                if overpopulation:
                    chance *= 0.8
                if player[4] >= 5 and player[5] >= 5 and player[6] >= 5 and player[7] >= 5 and random.random() < chance:
                    update_baby(conn, baby[0], 1, now.isoformat())
                    update_player(conn, player_id, player[1], player[2], player[3], player[4] - 5, player[5] - 5, player[6] - 5, player[7] - 5,
                                 player[8], player[9], player[10], player[11], player[12], player[13], player[14], player[15], player[16])
    except Exception as e:
        logger.error(f"Error in grow_babies for player {player_id}: {str(e)}")

def produce_supplies(conn, player_id):
    try:
        player = get_player(conn, player_id)
        citizens = get_citizens(conn, player_id)
        workers = [c for c in citizens if c[3] == 'worker' and c[8] == 'active']
        miners = [c for c in citizens if c[3] == 'miner' and c[8] == 'active']
        water, food, medicine, ore = 0, 0, 0, 0
        for _ in workers:
            supply_type = random.choice(['water', 'food', 'medicine'])
            amount = int(random.randint(1, 3) * quality_modifier(player[8 if supply_type == 'water' else 9 if supply_type == 'food' else 10]))
            if supply_type == 'water':
                water += amount
            elif supply_type == 'food':
                food += amount
            else:
                medicine += amount
        for _ in miners:
            ore += int(random.randint(1, 3) * quality_modifier(player[11]))
        if water or food or medicine or ore:
            update_player(conn, player_id, player[1], player[2], player[3], player[4] + water, player[5] + food, player[6] + medicine, player[7] + ore,
                         player[8], player[9], player[10], player[11], player[12], player[13], player[14], player[15], player[16])
        return water, food, medicine, ore
    except Exception as e:
        logger.error(f"Error in produce_supplies for player {player_id}: {str(e)}")
        return 0, 0, 0, 0

def random_event(conn, chat_id):
    try:
        c = conn.cursor()
        c.execute('SELECT player_id FROM players')
        players = c.fetchall()
        now = datetime.now()
        event = random.choice(['boom', 'plague'])
        response = f"Random event in group {chat_id}: "
        for player_id in players:
            player = get_player(conn, player_id[0])
            if not can_trigger_event(player):
                continue
            if event == 'boom':
                water = random.randint(10, 20)
                food = random.randint(10, 20)
                medicine = random.randint(10, 20)
                ore = random.randint(10, 20)
                update_player(conn, player_id[0], player[1], player[2], player[3], player[4] + water, player[5] + food, player[6] + medicine, player[7] + ore,
                             player[8], player[9], player[10], player[11], player[12], player[13], player[14], player[15], now.isoformat())
                response += f"Resource boom! @{player[1]} gained {water} water, {food} food, {medicine} medicine, {ore} ore.\n"
            else:
                citizens = get_citizens(conn, player_id[0])
                babies = get_babies(conn, player_id[0])
                affected = random.sample(citizens + babies, k=int(len(citizens + babies) * random.uniform(0.1, 0.3)))
                for unit in affected:
                    if unit in babies:
                        c.execute('DELETE FROM babies WHERE baby_id = ?', (unit[0],))
                    else:
                        update_citizen(conn, unit[0], 'dead')
                conn.commit()
                response += f"Plague! @{player[1]} lost {len(affected)} population.\n"
        logger.debug(f"Random event triggered: {event}")
        return response
    except Exception as e:
        logger.error(f"Error in random_event: {str(e)}")
        return ""

def calculate_currency_value(player, citizens, babies):
    try:
        total_supplies = player[4] + player[5] + player[6] + player[7] * 2
        population = len(babies) + len(citizens)
        return total_supplies / max(population, 1)
    except Exception as e:
        logger.error(f"Error calculating currency value for player {player[1]}: {str(e)}")
        return 1.0

async def simulate_match(update, context, match_id, sport, team_ids):
    try:
        conn = sqlite3.connect('battle_forge.db')
        teams = [get_team(conn, team_id) for team_id in team_ids]
        group_name = update.effective_chat.title or "group"
        chat_id = update.effective_chat.id
        is_racing = sport in ['f1_racing', 'horse_racing']
        timeline = [] if not is_racing else None
        scores = {team[2]: 0 for team in teams}
        sets = {team[2]: 0 for team in teams} if sport == 'volleyball' else None
        hits = {team[2]: 0 for team in teams} if sport == 'boxing' else None
        distances = {team[2]: 0 for team in teams} if is_racing else None
        message = await update.message.reply_text(f"{sport} match started: {', '.join([team[2] for team in teams])}!")
        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)

        if is_racing:
            race_distance = 1000
            update_interval = 5
            intervals = 60 // update_interval
            for i in range(intervals):
                await asyncio.sleep(update_interval)
                for team in teams:
                    advance = random.randint(10, 50) * (1 + (team[5] - 100) / 200)
                    distances[team[2]] += advance
                leaderboard = f"{sport}: " + ", ".join(f"{team}: {distances[team]:.0f}m" for team in distances)
                new_message = await context.bot.send_message(chat_id=chat_id, text=leaderboard)
                if message.message_id:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                message = new_message
                update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
            sorted_teams = sorted(distances.items(), key=lambda x: x[1], reverse=True)
            winner_name = sorted_teams[0][0]
            winner_id = next(team[0] for team in teams if team[2] == winner_name)
        else:
            if sport == 'volleyball':
                set_number = 1
                match_time = 0
                while match_time < 60 and max(sets.values(), default=0) < 3:
                    team1, team2 = random.sample(teams, 2)
                    team1_set_score = 0
                    team2_set_score = 0
                    while match_time < 60 and (team1_set_score < 25 and team2_set_score < 25 or abs(team1_set_score - team2_set_score) < 2):
                        await asyncio.sleep(random.uniform(1, 3))
                        match_time += random.uniform(1, 3)
                        team1_chance = 0.5 + (team1[5] - team2[5]) / 200
                        if random.random() < 0.1:
                            fouling_team = team1 if random.random() < 0.5 else team2
                            other_team = team2 if fouling_team == team1 else team1
                            event_text = f"{sport} set {set_number}: {fouling_team[2]} {team1_set_score} - {other_team[2]} {team2_set_score}, {fouling_team[2]} service fault!"
                            scores[other_team[2]] += 1
                            if other_team == team1:
                                team1_set_score += 1
                            else:
                                team2_set_score += 1
                        else:
                            scoring_team = team1 if random.random() < team1_chance else team2
                            event_text = f"{sport} set {set_number}: {scoring_team[2]} {team1_set_score} - {other_team[2]} {team2_set_score}, {scoring_team[2]} scores on a serve!"
                            scores[scoring_team[2]] += 1
                            if scoring_team == team1:
                                team1_set_score += 1
                            else:
                                team2_set_score += 1
                        timeline.append(event_text)
                        new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                        if message.message_id:
                            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        message = new_message
                        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                    if team1_set_score > team2_set_score:
                        sets[team1[2]] += 1
                    else:
                        sets[team2[2]] += 1
                    set_number += 1
                winner_id = next(team[0] for team in teams if sets[team[2]] >= 3) if max(sets.values(), default=0) >= 3 else None
            elif sport == 'basketball':
                for quarter in range(1, 5):
                    quarter_time = 0
                    while quarter_time < 15:
                        await asyncio.sleep(random.uniform(1, 3))
                        quarter_time += random.uniform(1, 3)
                        team1, team2 = random.sample(teams, 2)
                        team1_chance = 0.5 + (team1[5] - team2[5]) / 200
                        if random.random() < 0.15:
                            fouling_team = team1 if random.random() < 0.5 else team2
                            other_team = team2 if fouling_team == team1 else team1
                            free_throws = random.randint(1, 2)
                            event_text = f"{sport} quarter {quarter} (0:{15-quarter_time:.0f}): {other_team[2]} {scores[other_team[2]]} - {fouling_team[2]} {scores[fouling_team[2]]}, {fouling_team[2]} commits a foul!"
                            timeline.append(event_text)
                            new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                            if message.message_id:
                                await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                            message = new_message
                            update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                            for _ in range(free_throws):
                                if random.random() < 0.7:
                                    scores[other_team[2]] += 1
                                    event_text = f"{sport} quarter {quarter} (0:{15-quarter_time:.0f}): {other_team[2]} {scores[other_team[2]]} - {fouling_team[2]} {scores[fouling_team[2]]}, {other_team[2]} scores a free throw!"
                                    timeline.append(event_text)
                                    new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                                    if message.message_id:
                                        await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                                    message = new_message
                                    update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                        elif random.random() < 0.2:
                            shooting_team = team1 if random.random() < team1_chance else team2
                            other_team = team2 if shooting_team == team1 else team1
                            event_text = f"{sport} quarter {quarter} (0:{15-quarter_time:.0f}): {shooting_team[2]} {scores[shooting_team[2]]} - {other_team[2]} {scores[other_team[2]]}, {shooting_team[2]} airball!"
                            timeline.append(event_text)
                            new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                            if message.message_id:
                                await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                            message = new_message
                            update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                        else:
                            scoring_team = team1 if random.random() < team1_chance else team2
                            other_team = team2 if scoring_team == team1 else team1
                            points = random.choice([2, 3])
                            scores[scoring_team[2]] += points
                            event_text = f"{sport} quarter {quarter} (0:{15-quarter_time:.0f}): {scoring_team[2]} {scores[scoring_team[2]]} - {other_team[2]} {scores[other_team[2]]}, {scoring_team[2]} scores {points} points!"
                            timeline.append(event_text)
                            new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                            if message.message_id:
                                await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                            message = new_message
                            update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                    event_text = f"{sport} quarter {quarter} ends: " + ", ".join(f"{team[2]} {scores[team[2]]}" for team in teams)
                    timeline.append(event_text)
                    new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                    if message.message_id:
                        await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                    message = new_message
                    update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                winner_id = max(scores.items(), key=lambda x: x[1])[1] if len(set(scores.values())) > 1 else None
                winner_id = next(team[0] for team in teams if team[2] == winner_id) if winner_id else None
            elif sport == 'soccer':
                match_time = 0
                while match_time < 60:
                    await asyncio.sleep(random.uniform(1, 3))
                    match_time += random.uniform(1, 3)
                    team1, team2 = random.sample(teams, 2)
                    team1_chance = 0.5 + (team1[5] - team2[5]) / 200
                    if random.random() < 0.1:
                        fouling_team = team1 if random.random() < 0.5 else team2
                        other_team = team2 if fouling_team == team1 else team1
                        event_text = f"{sport} (0:{60-match_time:.0f}): {other_team[2]} {scores[other_team[2]]} - {fouling_team[2]} {scores[fouling_team[2]]}, {fouling_team[2]} commits a foul!"
                        timeline.append(event_text)
                        new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                        if message.message_id:
                            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        message = new_message
                        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                        if random.random() < 0.2:
                            scores[other_team[2]] += 1
                            event_text = f"{sport} (0:{60-match_time:.0f}): {other_team[2]} {scores[other_team[2]]} - {fouling_team[2]} {scores[fouling_team[2]]}, {other_team[2]} scores a penalty goal!"
                            timeline.append(event_text)
                            new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                            if message.message_id:
                                await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                            message = new_message
                            update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                    elif random.random() < 0.2:
                        shooting_team = team1 if random.random() < team1_chance else team2
                        other_team = team2 if shooting_team == team1 else team1
                        event_text = f"{sport} (0:{60-match_time:.0f}): {shooting_team[2]} {scores[shooting_team[2]]} - {other_team[2]} {scores[other_team[2]]}, {shooting_team[2]} shot missed!"
                        timeline.append(event_text)
                        new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                        if message.message_id:
                            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        message = new_message
                        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                    elif random.random() < team1_chance * 0.02:
                        scores[team1[2]] += 1
                        event_text = f"{sport} (0:{60-match_time:.0f}): {team1[2]} {scores[team1[2]]} - {team2[2]} {scores[team2[2]]}, {team1[2]} scores a goal!"
                        timeline.append(event_text)
                        new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                        if message.message_id:
                            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        message = new_message
                        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                    elif random.random() < (1 - team1_chance) * 0.02:
                        scores[team2[2]] += 1
                        event_text = f"{sport} (0:{60-match_time:.0f}): {team1[2]} {scores[team1[2]]} - {team2[2]} {scores[team2[2]]}, {team2[2]} scores a goal!"
                        timeline.append(event_text)
                        new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                        if message.message_id:
                            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        message = new_message
                        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                winner_id = max(scores.items(), key=lambda x: x[1])[1] if len(set(scores.values())) > 1 else None
                winner_id = next(team[0] for team in teams if team[2] == winner_id) if winner_id else None
            elif sport == 'boxing':
                match_time = 0
                while match_time < 60:
                    await asyncio.sleep(random.uniform(1, 3))
                    match_time += random.uniform(1, 3)
                    team1, team2 = random.sample(teams, 2)
                    team1_chance = 0.5 + (team1[5] - team2[5]) / 200
                    if random.random() < 0.1:
                        fouling_team = team1 if random.random() < 0.5 else team2
                        other_team = team2 if fouling_team == team1 else team1
                        scores[other_team[2]] += 1
                        event_text = f"{sport} (0:{60-match_time:.0f}): {other_team[2]} {scores[other_team[2]]} - {fouling_team[2]} {scores[fouling_team[2]]}, {fouling_team[2]} illegal move!"
                        timeline.append(event_text)
                        new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                        if message.message_id:
                            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        message = new_message
                        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                    else:
                        hitting_team = team1 if random.random() < team1_chance else team2
                        other_team = team2 if hitting_team == team1 else team1
                        hits[hitting_team[2]] += random.randint(0, 3)
                        event_text = f"{sport} (0:{60-match_time:.0f}): {hitting_team[2]} {scores[hitting_team[2]]} - {other_team[2]} {scores[other_team[2]]}, {hitting_team[2]} lands a {'jab' if random.random() < 0.5 else 'hook'}!"
                        timeline.append(event_text)
                        new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                        if message.message_id:
                            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                        message = new_message
                        update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                        if hits[hitting_team[2]] >= 3 and random.random() < 0.5:
                            scores[hitting_team[2]] += 10
                            event_text = f"{sport} (0:{60-match_time:.0f}): {hitting_team[2]} {scores[hitting_team[2]]} - {other_team[2]} {scores[other_team[2]]}, {hitting_team[2]} scores a knockout (10 points)!"
                            timeline.append(event_text)
                            new_message = await context.bot.send_message(chat_id=chat_id, text=event_text)
                            if message.message_id:
                                await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                            message = new_message
                            update_match(conn, match_id, 'open', team_ids=team_ids, last_update_message_id=message.message_id)
                            break
                winner_id = max(scores.items(), key=lambda x: x[1])[1] if len(set(scores.values())) > 1 else None
                winner_id = next(team[0] for team in teams if team[2] == winner_id) if winner_id else None

        for team in teams:
            wins = team[3]
            win_streak = team[4]
            power = team[5]
            if team[0] == winner_id:
                wins += 1
                win_streak += 1
                power += 10
            elif winner_id is None:
                win_streak = 0
            else:
                win_streak = 0
            update_team(conn, team[0], wins, win_streak, power)

        for team in teams:
            if team[1]:
                player = get_player(conn, team[1])
                coins_change = 5 if team[0] == winner_id else 1 if winner_id is None else -2
                new_coins = max(player[12] + coins_change, 0)
                update_player(conn, team[1], player[1], player[2], player[3], player[4], player[5], player[6], player[7],
                             player[8], player[9], player[10], player[11], new_coins, player[13], player[14], player[15], player[16])

        wagers = get_wagers(conn, match_id)
        for wager in wagers:
            player = get_player(conn, wager[1])
            if wager[3] == winner_id:
                new_coins = player[12] + wager[4] * 2
                update_player(conn, wager[1], player[1], player[2], player[3], player[4], player[5], player[6], player[7],
                             player[8], player[9], player[10], player[11], new_coins, player[13], player[14], player[15], player[16])
                await context.bot.send_message(chat_id=chat_id, text=f"@{player[1]} won {wager[4]*2} {group_name} coins from wager!")
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"@{player[1]} lost {wager[4]} {group_name} coins from wager.")

        final_text = f"{sport} final result:\n"
        if is_racing:
            sorted_teams = sorted(distances.items(), key=lambda x: x[1], reverse=True)
            for i, (team, distance) in enumerate(sorted_teams, 1):
                final_text += f"{i}st: {team} ({distance:.0f}m)\n"
        else:
            final_text += ", ".join(f"{team[2]}: {scores[team[2]]}" for team in teams) + "\n"
            if sport == 'volleyball':
                final_text += "Sets: " + ", ".join(f"{team[2]} {sets[team[2]]}" for team in teams) + "\n"
            final_text += f"Winner: {next(team[2] for team in teams if team[0] == winner_id) if winner_id else 'tie'}!\n"
            if timeline:
                final_text += "\nMatch timeline:\n" + "\n".join(timeline)
        await context.bot.send_message(chat_id=chat_id, text=final_text)
        update_match(conn, match_id, 'closed')
        conn.close()
    except Exception as e:
        logger.error(f"Error in simulate_match for match {match_id}: {str(e)}")
        await update.message.reply_text("Error during match simulation.")

async def random_match_event(context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect('battle_forge.db')
        c = conn.cursor()
        c.execute('SELECT team_id, name FROM teams')
        teams = c.fetchall()
        if len(teams) < 2:
            conn.close()
            return
        sport = random.choice(['basketball', 'soccer', 'volleyball', 'f1_racing', 'horse_racing', 'boxing'])
        num_teams = random.randint(2, 4) if sport in ['f1_racing', 'horse_racing'] else 2
        selected_teams = random.sample(teams, num_teams)
        team_ids = [team[0] for team in selected_teams]
        match_id = create_match(conn, sport, team_ids[0], num_teams)
        team_ids = team_ids[:1]
        update_match(conn, match_id, 'open', team_ids=team_ids)
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=f"Random {sport} match for {num_teams} teams! {selected_teams[0][1]} has joined. Use /acceptsport {match_id} to join! Use /gamble {match_id} <team_name> <amount> to bet!"
        )
        conn.close()
        await asyncio.sleep(30)
        conn = sqlite3.connect('battle_forge.db')
        c = conn.cursor()
        c.execute('SELECT team_ids FROM matches WHERE match_id = ?', (match_id,))
        team_ids = json.loads(c.fetchone()[0])
        if len(team_ids) < 2:
            await context.bot.send_message(chat_id=context.job.chat_id, text=f"Match {match_id} cancelled: not enough teams joined.")
            update_match(conn, match_id, 'closed')
            conn.close()
            return
        conn.close()
        await simulate_match(context.job.context, context, match_id, sport, team_ids)
    except Exception as e:
        logger.error(f"Error in random_match_event: {str(e)}")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        group_name = update.effective_chat.title or "group"
        player_id = update.effective_user.id
        username = update.effective_user.username or f"user_{player_id}"
        conn = sqlite3.connect('battle_forge.db')
        try:
            player = get_player(conn, player_id)
            if not player:
                initialize_player_citizens(conn, player_id)
                create_team(conn, player_id, f"@{username}_team")
                update_player(conn, player_id, username, 0, 0, 100, 100, 100, 100, 'medium', 'medium', 'medium', 'medium', 10, 0, None, None, None)
            logger.debug(f"Start command by player {player_id} in chat {update.effective_chat.id}")
            await update.message.reply_text(
                f"Welcome to BattleForgeBot in {group_name}! ⚔️\n"
                f"Currency: {group_name} coin\n"
                "Commands:\n"
                "/collectresources - Collect sperms and eggs every 24h\n"
                "/collectsupplies - Collect water, food, medicine, ore every 12h\n"
                "/merge <sperms> <eggs> - Create babies\n"
                "/upgradequality <resource> - Upgrade resource quality\n"
                "/mystats - View resources, population, coins\n"
                "/currencies - View all players' coin values\n"
                "/sellable - View items available for trading\n"
                "/trade <item> <quantity> <price> - Offer a trade\n"
                "/accepttrade <trade_id> - Accept a trade\n"
                "/war <opponent_player_id> <fighter_count> - Start a war\n"
                "/sportevent <sport> <num_teams> - Create a sport match\n"
                "/acceptsport <match_id> - Join a sport match\n"
                "/teamstats - View your team stats\n"
                "/gamble <match_id> <team_name> <amount> - Bet on a match\n"
                "/leaderboard - Top players by coins and wins"
            )
            if update.effective_chat.id not in context.job_queue.get_jobs_by_name(f"random_match_{update.effective_chat.id}"):
                context.job_queue.run_repeating(
                    random_match_event,
                    interval=random.randint(5*3600, 6*3600),
                    first=0,
                    context=update,
                    name=f"random_match_{update.effective_chat.id}",
                    job_kwargs={"chat_id": update.effective_chat.id}
                )
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")
        await update.message.reply_text("An error occurred. Please try again.")

async def collectresources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    username = update.effective_user.username or f"user_{player_id}"
    conn = sqlite3.connect('battle_forge.db')
    try:
        player = get_player(conn, player_id)
        if not can_collect_resources(player):
            logger.debug(f"Player {player_id} tried to collect resources too soon")
            await update.message.reply_text("You've already collected resources in the last 24 hours!")
            return
        sperms_gained = random.randint(100000, 200000)
        eggs_gained = random.randint(50, 150)
        new_sperms = sperms_gained if not player else player[2] + sperms_gained
        new_eggs = eggs_gained if not player else player[3] + eggs_gained
        if not player:
            initialize_player_citizens(conn, player_id)
            create_team(conn, player_id, f"@{username}_team")
            update_player(conn, player_id, username, new_sperms, new_eggs, 100, 100, 100, 100, 'medium', 'medium', 'medium', 'medium', 10, 0, datetime.now().isoformat(), None, None)
        else:
            update_player(conn, player_id, username, new_sperms, new_eggs, player[4], player[5], player[6], player[7], player[8], player[9], player[10], player[11], player[12], player[13], datetime.now().isoformat(), player[15], player[16])
        logger.debug(f"Player {player_id} collected {sperms_gained} sperms, {eggs_gained} eggs")
        await update.message.reply_text(f"You collected {sperms_gained} sperms and {eggs_gained} eggs! Totals: {new_sperms} sperms, {new_eggs} eggs")
    except Exception as e:
        logger.error(f"Error in collectresources for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while collecting resources.")
    finally:
        conn.close()

async def collectsupplies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    username = update.effective_user.username or f"user_{player_id}"
    conn = sqlite3.connect('battle_forge.db')
    try:
        player = get_player(conn, player_id)
        if not can_collect_supplies(player):
            logger.debug(f"Player {player_id} tried to collect supplies too soon")
            await update.message.reply_text("You've already collected supplies in the last 12 hours!")
            return
        water_gained = random.randint(10, 20)
        food_gained = random.randint(10, 20)
        medicine_gained = random.randint(10, 20)
        ore_gained = random.randint(10, 20)
        new_water = water_gained if not player else player[4] + water_gained
        new_food = food_gained if not player else player[5] + food_gained
        new_medicine = medicine_gained if not player else player[6] + medicine_gained
        new_ore = ore_gained if not player else player[7] + ore_gained
        if not player:
            initialize_player_citizens(conn, player_id)
            create_team(conn, player_id, f"@{username}_team")
            update_player(conn, player_id, username, 0, 0, new_water, new_food, new_medicine, new_ore, 'medium', 'medium', 'medium', 'medium', 10, 0, None, datetime.now().isoformat(), None)
        else:
            update_player(conn, player_id, username, player[2], player[3], new_water, new_food, new_medicine, new_ore, player[8], player[9], player[10], player[11], player[12], player[13], player[14], datetime.now().isoformat(), player[16])
        logger.debug(f"Player {player_id} collected {water_gained} water, {food_gained} food, {medicine_gained} medicine, {ore_gained} ore")
        await update.message.reply_text(f"You collected {water_gained} water, {food_gained} food, {medicine_gained} medicine, {ore_gained} ore!")
    except Exception as e:
        logger.error(f"Error in collectsupplies for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while collecting supplies.")
    finally:
        conn.close()

async def merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    username = update.effective_user.username or f"user_{player_id}"
    if len(context.args) != 2:
        logger.debug(f"Player {player_id} used invalid merge syntax")
        await update.message.reply_text("Usage: /merge <sperm_count> <egg_count>")
        return
    try:
        sperm_count, egg_count = map(int, context.args)
        if sperm_count <= 0 or egg_count <= 0:
            await update.message.reply_text("Sperm and egg counts must be positive!")
            return
        conn = sqlite3.connect('battle_forge.db')
        try:
            player = get_player(conn, player_id)
            if not player:
                initialize_player_citizens(conn, player_id)
                create_team(conn, player_id, f"@{username}_team")
                player = get_player(conn, player_id)
            if player[2] < sperm_count or player[3] < egg_count:
                logger.debug(f"Player {player_id} has insufficient sperms or eggs")
                await update.message.reply_text("Not enough sperms or eggs!")
                return
            for i in range(min(sperm_count, egg_count)):
                create_baby(conn, player_id, f"baby_{random.randint(1000, 9999)}", datetime.now().isoformat())
            update_player(conn, player_id, username, player[2] - sperm_count, player[3] - egg_count, player[4], player[5], player[6], player[7],
                         player[8], player[9], player[10], player[11], player[12], player[13], player[14], player[15], player[16])
            logger.debug(f"Player {player_id} merged {min(sperm_count, egg_count)} sperms and eggs")
            await update.message.reply_text(f"Merged {min(sperm_count, egg_count)} sperms and eggs to create babies!")
        finally:
            conn.close()
    except ValueError:
        logger.debug(f"Player {player_id} used invalid numbers for merge")
        await update.message.reply_text("Sperm and egg counts must be numbers!")
    except Exception as e:
        logger.error(f"Error in merge for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while merging.")

async def upgradequality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    if not context.args:
        logger.debug(f"Player {player_id} used invalid upgradequality syntax")
        await update.message.reply_text("Usage: /upgradequality <resource> (water, food, medicine, ore)")
        return
    resource = context.args[0].lower()
    if resource not in ['water', 'food', 'medicine', 'ore']:
        logger.debug(f"Player {player_id} specified invalid resource: {resource}")
        await update.message.reply_text("Invalid resource! Use water, food, medicine, or ore.")
        return
    conn = sqlite3.connect('battle_forge.db')
    try:
        player = get_player(conn, player_id)
        if not player:
            username = update.effective_user.username or f"user_{player_id}"
            initialize_player_citizens(conn, player_id)
            create_team(conn, player_id, f"@{username}_team")
            player = get_player(conn, player_id)
        if player[12] < 10:
            logger.debug(f"Player {player_id} has insufficient coins")
            await update.message.reply_text(f"You need 10 {update.effective_chat.title or 'group'} coins to upgrade!")
            return
        quality_index = {'water': 8, 'food': 9, 'medicine': 10, 'ore': 11}[resource]
        current_quality = player[quality_index]
        if current_quality == 'high':
            logger.debug(f"Player {player_id} tried to upgrade {resource} already at high")
            await update.message.reply_text(f"{resource} quality is already high!")
            return
        new_quality = 'medium' if current_quality == 'low' else 'high'
        new_player_data = list(player)
        new_player_data[quality_index] = new_quality
        new_player_data[12] -= 10
        update_player(conn, player_id, player[1], *new_player_data[2:])
        logger.debug(f"Player {player_id} upgraded {resource} to {new_quality}")
        await update.message.reply_text(f"Upgraded {resource} quality to {new_quality}!")
    except Exception as e:
        logger.error(f"Error in upgradequality for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while upgrading quality.")
    finally:
        conn.close()

async def currencies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    conn = sqlite3.connect('battle_forge.db')
    try:
        c = conn.cursor()
        c.execute('SELECT player_id, username FROM players')
        players = c.fetchall()
        response = f"Currency values in {group_name}:\n"
        for player in players:
            player_data = get_player(conn, player[0])
            citizens = get_citizens(conn, player[0])
            babies = get_babies(conn, player[0])
            currency_value = calculate_currency_value(player_data, citizens, babies)
            response += f"@{player[1]} coin: {currency_value:.2f} {group_name} coins\n"
        logger.debug(f"Player {player_id} viewed currencies")
        await update.message.reply_text(response or "No players have currencies yet!")
    except Exception as e:
        logger.error(f"Error in currencies for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while viewing currencies.")
    finally:
        conn.close()

async def sellable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    conn = sqlite3.connect('battle_forge.db')
    try:
        player = get_player(conn, player_id)
        if not player:
            username = update.effective_user.username or f"user_{player_id}"
            initialize_player_citizens(conn, player_id)
            create_team(conn, player_id, f"@{username}_team")
            player = get_player(conn, player_id)
        citizens = get_citizens(conn, player_id)
        response = "Items you can sell:\n"
        response += f"`sperms`: {player[2]}\n"
        response += f"`eggs`: {player[3]}\n"
        response += f"`water`: {player[4]}\n"
        response += f"`food`: {player[5]}\n"
        response += f"`medicine`: {player[6]}\n"
        response += f"`ore`: {player[7]}\n"
        response += "\nActive citizens:\n"
        active_citizens = [c for c in citizens if c[8] == 'active']
        if active_citizens:
            for citizen in active_citizens:
                response += f"id: citizen_{citizen[0]}, name: {citizen[2]}, role: {citizen[3]}\n"
        else:
            response += "No active citizens available.\n"
        response += f"\nUse /trade <item> <quantity> <price> to sell (e.g., /trade sperms 1000 5)"
        formatted_response = f"```\n{response}\n```"
        logger.debug(f"Player {player_id} viewed sellable items")
        await update.message.reply_text(formatted_response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in sellable for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while viewing sellable items.")
    finally:
        conn.close()

async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    conn = sqlite3.connect('battle_forge.db')
    try:
        player = get_player(conn, player_id)
        if not player:
            username = update.effective_user.username or f"user_{player_id}"
            initialize_player_citizens(conn, player_id)
            create_team(conn, player_id, f"@{username}_team")
            player = get_player(conn, player_id)
        grow_babies(conn, player_id)
        water, food, medicine, ore = produce_supplies(conn, player_id)
        player = get_player(conn, player_id)
        babies = get_babies(conn, player_id)
        citizens = get_citizens(conn, player_id)
        currency_value = calculate_currency_value(player, citizens, babies)
        group_name = update.effective_chat.title or "group"
        response = f"Your stats:\nSperms: {player[2]}\nEggs: {player[3]}\n"
        response += f"Water: {player[4]} ({player[8]})\nFood: {player[5]} ({player[9]})\nMedicine: {player[6]} ({player[10]})\nOre: {player[7]} ({player[11]})\n"
        response += f"{group_name} coins: {player[12]}\nWar wins: {player[13]}\n"
        response += f"@{player[1]} coin value: {currency_value:.2f} {group_name} coins\n"
        response += f"New supplies: +{water} water, +{food} food, +{medicine} medicine, +{ore} ore\n"
        response += "\nBabies:\n" + (f"{len(babies)} pending birth\n" if babies else "No babies\n")
        response += "\nCitizens:\n"
        if not citizens:
            response += "No citizens\n"
        else:
            for citizen in citizens:
                status = f" ({citizen[8]}{', until ' + datetime.fromisoformat(citizen[9]).strftime('%Y-%m-%d %H:%M') if citizen[8] == 'injured' else ''})"
                response += f"id: {citizen[0]}, name: {citizen[2]}, role: {citizen[3]}, health: {citizen[4]}, attack: {citizen[5]}, defense: {citizen[6]}{status}\n"
        logger.debug(f"Player {player_id} viewed stats")
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error in mystats for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while viewing stats.")
    finally:
        conn.close()

async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    if len(context.args) != 3:
        logger.debug(f"Player {player_id} used invalid trade syntax")
        await update.message.reply_text(f"Usage: /trade <item> <quantity> <price> (price in {group_name} coin)")
        return
    item, quantity, price = context.args
    try:
        quantity = int(quantity)
        price = int(price)
        if quantity <= 0 or price <= 0:
            logger.debug(f"Player {player_id} specified invalid quantity or price")
            await update.message.reply_text("Quantity and price must be positive!")
            return
        conn = sqlite3.connect('battle_forge.db')
        try:
            player = get_player(conn, player_id)
            if not player:
                username = update.effective_user.username or f"user_{player_id}"
                initialize_player_citizens(conn, player_id)
                create_team(conn, player_id, f"@{username}_team")
                player = get_player(conn, player_id)
            if item in ['sperms', 'eggs', 'water', 'food', 'medicine', 'ore']:
                index = {'sperms': 2, 'eggs': 3, 'water': 4, 'food': 5, 'medicine': 6, 'ore': 7}[item]
                if player[index] < quantity:
                    logger.debug(f"Player {player_id} has insufficient {item}")
                    await update.message.reply_text(f"Not enough {item}!")
                    return
            elif item.startswith('citizen_'):
                citizen_id = int(item.split('_')[1])
                if not any(c[0] == citizen_id and c[1] == player_id and c[8] == 'active' for c in get_citizens(conn, player_id)):
                    logger.debug(f"Player {player_id} specified invalid or unavailable citizen id: {citizen_id}")
                    await update.message.reply_text("Invalid or unavailable citizen id!")
                    return
            else:
                logger.debug(f"Player {player_id} specified invalid item: {item}")
                await update.message.reply_text("Invalid item! Use sperms, eggs, water, food, medicine, ore, or citizen_<id>")
                return
            traders = sum(1 for c in get_citizens(conn, player_id) if c[3] == 'trader' and c[8] == 'active')
            if random.random() < 0.9 - traders * 0.1:
                create_trade(conn, player_id, item, quantity, price, f"{group_name} coin")
                logger.debug(f"Player {player_id} created trade: {quantity} {item} for {price} {group_name} coin")
                await update.message.reply_text(f"Trade created: {quantity} {item} for {price} {group_name} coin")
            else:
                logger.debug(f"Player {player_id} trade failed due to market fluctuations")
                await update.message.reply_text("Trade failed due to market fluctuations!")
        finally:
            conn.close()
    except ValueError:
        logger.debug(f"Player {player_id} used invalid numbers for trade")
        await update.message.reply_text("Quantity and price must be numbers!")
    except Exception as e:
        logger.error(f"Error in trade for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while creating trade.")

async def accepttrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    conn = sqlite3.connect('battle_forge.db')
    try:
        if not context.args:
            trades = get_open_trades(conn)
            response = "Open trades:\n"
            for trade in trades:
                seller = get_player(conn, trade[1])
                response += f"id: {trade[0]}, seller: @{seller[1]}, item: {trade[2]}, quantity: {trade[3]}, price: {trade[4]} {trade[5]}\n"
            logger.debug(f"Player {player_id} viewed open trades")
            await update.message.reply_text(response or "No open trades!")
            return
        trade_id = int(context.args[0])
        c = conn.cursor()
        c.execute('SELECT * FROM trades WHERE trade_id = ? AND status = "open"', (trade_id,))
        trade = c.fetchone()
        if not trade:
            logger.debug(f"Player {player_id} specified invalid or closed trade id: {trade_id}")
            await update.message.reply_text("Invalid or closed trade id!")
            return
        if trade[5] != f"{group_name} coin":
            logger.debug(f"Player {player_id} attempted to accept trade with invalid currency: {trade[5]}")
            await update.message.reply_text(f"Trade uses invalid currency: {trade[5]}!")
            return
        if trade[1] == player_id:
            logger.debug(f"Player {player_id} tried to accept their own trade")
            await update.message.reply_text("You can't accept your own trade!")
            return
        buyer = get_player(conn, player_id)
        if not buyer:
            username = update.effective_user.username or f"user_{player_id}"
            initialize_player_citizens(conn, player_id)
            create_team(conn, player_id, f"@{username}_team")
            buyer = get_player(conn, player_id)
        if buyer[12] < trade[4]:
            logger.debug(f"Player {player_id} has insufficient coins for trade {trade_id}")
            await update.message.reply_text(f"Not enough {group_name} coins!")
            return
        seller = get_player(conn, trade[1])
        resource_map = {'sperms': 2, 'eggs': 3, 'water': 4, 'food': 5, 'medicine': 6, 'ore': 7}
        if trade[2] in resource_map:
            index = resource_map[trade[2]]
            if seller[index] < trade[3]:
                logger.debug(f"Seller {trade[1]} has insufficient {trade[2]} for trade {trade_id}")
                await update.message.reply_text(f"Seller no longer has enough {trade[2]}!")
                c.execute('UPDATE trades SET status = "closed" WHERE trade_id = ?', (trade_id,))
                conn.commit()
                return
            buyer_data = list(buyer)
            seller_data = list(seller)
            buyer_data[index] += trade[3]
            seller_data[index] -= trade[3]
            buyer_data[12] -= trade[4]
            seller_data[12] += trade[4]
            update_player(conn, buyer[0], buyer[1], *buyer_data[2:])
            update_player(conn, seller[0], seller[1], *seller_data[2:])
        elif trade[2].startswith('citizen_'):
            citizen_id = int(trade[2].split('_')[1])
            citizen = next((c for c in get_citizens(conn, trade[1]) if c[0] == citizen_id and c[8] == 'active'), None)
            if not citizen:
                logger.debug(f"Player {player_id} specified invalid or unavailable citizen id: {citizen_id}")
                await update.message.reply_text("Citizen is no longer available!")
                c.execute('UPDATE trades SET status = "closed" WHERE trade_id = ?', (trade_id,))
                conn.commit()
                return
            c.execute('UPDATE citizens SET player_id = ? WHERE citizen_id = ?', (player_id, citizen_id))
            buyer_data = list(buyer)
            seller_data = list(seller)
            buyer_data[12] -= trade[4]
            seller_data[12] += trade[4]
            update_player(conn, buyer[0], buyer[1], *buyer_data[2:])
            update_player(conn, seller[0], seller[1], *seller_data[2:])
        c.execute('UPDATE trades SET status = "closed" WHERE trade_id = ?', (trade_id,))
        conn.commit()
        logger.debug(f"Player {player_id} accepted trade {trade_id}: {trade[3]} {trade[2]} for {trade[4]} {group_name} coins")
        await update.message.reply_text(f"Trade accepted: {trade[3]} {trade[2]} for {trade[4]} {group_name} coins!")
    except ValueError:
        logger.debug(f"Player {player_id} used invalid trade id")
        await update.message.reply_text("Trade id must be a number!")
    except Exception as e:
        logger.error(f"Error in accepttrade for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while accepting trade.")
    finally:
        conn.close()

async def sportevent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    valid_sports = ['basketball', 'soccer', 'volleyball', 'f1_racing', 'horse_racing', 'boxing']
    if len(context.args) != 2:
        logger.debug(f"Player {player_id} used invalid sportevent syntax")
        await update.message.reply_text(f"Usage: /sportevent <sport> <num_teams> (sports: {', '.join(valid_sports)})")
        return
    sport, num_teams = context.args
    try:
        num_teams = int(num_teams)
        if sport not in valid_sports:
            logger.debug(f"Player {player_id} specified invalid sport: {sport}")
            await update.message.reply_text(f"Invalid sport! Choose from: {', '.join(valid_sports)}")
            return
        if sport in ['f1_racing', 'horse_racing']:
            if not 2 <= num_teams <= 4:
                logger.debug(f"Player {player_id} specified invalid number of teams for {sport}: {num_teams}")
                await update.message.reply_text(f"Racing sports require 2–4 teams, got {num_teams}")
                return
        else:
            if num_teams != 2:
                logger.debug(f"Player {player_id} specified invalid number of teams for {sport}: {num_teams}")
                await update.message.reply_text(f"Non-racing sports require exactly 2 teams, got {num_teams}")
                return
        if num_teams < 2:
            logger.debug(f"Player {player_id} specified invalid number of teams: {num_teams}")
            await update.message.reply_text("Number of teams must be at least 2!")
            return
        conn = sqlite3.connect('battle_forge.db')
        try:
            player = get_player(conn, player_id)
            if not player:
                username = update.effective_user.username or f"user_{player_id}"
                initialize_player_citizens(conn, player_id)
                create_team(conn, player_id, f"@{username}_team")
                player = get_player(conn, player_id)
            team = get_player_team(conn, player_id)
            if not team:
                team_name = f"@{update.effective_user.username or f'user_{player_id}'}_team"
                create_team(conn, player_id, team_name)
                team = get_player_team(conn, player_id)
                if not team:
                    logger.error(f"Failed to create team for player {player_id}")
                    await update.message.reply_text("Failed to create your team!")
                    return
            match_id = create_match(conn, sport, team[0], num_teams)
            if not match_id:
                logger.error(f"Failed to create match for player {player_id}, team {team[0]}")
                await update.message.reply_text("Failed to create sport event!")
                return
            logger.debug(f"Player {player_id} created match {match_id}: {sport} for {num_teams} teams")
            await update.message.reply_text(
                f"{sport} event created for {num_teams} teams! {team[2]} has joined (match id: {match_id}). "
                f"use /acceptsport {match_id} to join! use /gamble {match_id} <team_name> <amount> to bet!"
            )
        except Exception as e:
            logger.error(f"Error in sportevent for player {player_id}: {str(e)}")
            await update.message.reply_text("An error occurred while creating sport event.")
        finally:
            conn.close()
    except ValueError:
        logger.debug(f"Player {player_id} used invalid number of teams")
        await update.message.reply_text("Number of teams must be a number!")
    except Exception as e:
        logger.error(f"Error in sportevent for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while creating sport event.")

async def acceptsport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    if not context.args:
        logger.debug(f"Player {player_id} used invalid acceptsport syntax")
        await update.message.reply_text("Usage: /acceptsport <match_id>")
        return
    try:
        match_id = int(context.args[0])
        conn = sqlite3.connect('battle_forge.db')
        try:
            c = conn.cursor()
            c.execute('SELECT * FROM matches WHERE match_id = ? AND status = "open"', (match_id,))
            match = c.fetchone()
            if not match:
                logger.debug(f"Player {player_id} specified invalid or closed match id: {match_id}")
                await update.message.reply_text("Invalid or closed match id!")
                return
            player = get_player(conn, player_id)
            if not player:
                username = update.effective_user.username or f"user_{player_id}"
                initialize_player_citizens(conn, player_id)
                create_team(conn, player_id, f"@{username}_team")
                player = get_player(conn, player_id)
            team = get_player_team(conn, player_id)
            if not team:
                team_name = f"@{update.effective_user.username or f'user_{player_id}'}_team"
                create_team(conn, player_id, team_name)
                team = get_player_team(conn, player_id)
                if not team:
                    logger.error(f"Failed to create team for player {player_id}")
                    await update.message.reply_text("Failed to create your team!")
                    return
            team_ids = json.loads(match[2])
            if team[0] in team_ids:
                logger.debug(f"Player {player_id} is already in match {match_id}")
                await update.message.reply_text("You have already joined this match!")
                return
            if len(team_ids) >= match[3]:
                logger.debug(f"Match {match_id} is already full")
                await update.message.reply_text("This match is already full!")
                return
            team_ids.append(team[0])
            update_match(conn, match_id, 'open', team_ids=team_ids)
            if len(team_ids) == match[3]:
                logger.debug(f"Match {match_id} is now full, starting in 30 seconds")
                await update.message.reply_text(f"{match[1]} event full! Match starting in 30 seconds...")
                await asyncio.sleep(30)  # 30-second delay before match starts
                await simulate_match(update, context, match_id, match[1], team_ids)
            else:
                logger.debug(f"Player {player_id} joined match {match_id}")
                await update.message.reply_text(
                    f"You joined {match[1]} match! Waiting for {match[3] - len(team_ids)} more teams. "
                    f"use /gamble {match_id} <team_name> <amount> to bet!"
                )
        except Exception as e:
            logger.error(f"Error in acceptsport for player {player_id}: {str(e)}")
            await update.message.reply_text("An error occurred while joining sport event.")
        finally:
            conn.close()
    except ValueError:
        logger.debug(f"Player {player_id} used invalid match id")
        await update.message.reply_text("Match id must be a number!")
    except Exception as e:
        logger.error(f"Error in acceptsport for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while joining sport event.")

async def teamstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    conn = sqlite3.connect('battle_forge.db')
    try:
        player = get_player(conn, player_id)
        if not player:
            username = update.effective_user.username or f"user_{player_id}"
            initialize_player_citizens(conn, player_id)
            create_team(conn, player_id, f"@{username}_team")
            player = get_player(conn, player_id)
        team = get_player_team(conn, player_id)
        if not team:
            team_name = f"@{update.effective_user.username or f'user_{player_id}'}_team"
            create_team(conn, player_id, team_name)
            team = get_player_team(conn, player_id)
        response = f"Team stats for {team[2]}:\n"
        response += f"Wins: {team[3]}\nWin streak: {team[4]}\nPower: {team[5]}\n"
        response += "Supports all sports: basketball, soccer, volleyball, f1_racing, horse_racing, boxing"
        logger.debug(f"Player {player_id} viewed team stats")
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error in teamstats for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while viewing team stats.")
    finally:
        conn.close()

async def gamble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    if len(context.args) != 3:
        logger.debug(f"Player {player_id} used invalid gamble syntax")
        await update.message.reply_text("Usage: /gamble <match_id> <team_name> <amount>")
        return
    try:
        match_id, team_name, amount = context.args
        match_id = int(match_id)
        amount = int(amount)
        if amount <= 0:
            logger.debug(f"Player {player_id} specified invalid bet amount: {amount}")
            await update.message.reply_text("Bet amount must be positive!")
            return
        conn = sqlite3.connect('battle_forge.db')
        try:
            c = conn.cursor()
            c.execute('SELECT * FROM matches WHERE match_id = ? AND status = "open"', (match_id,))
            match = c.fetchone()
            if not match:
                logger.debug(f"Player {player_id} specified invalid or closed match id: {match_id}")
                await update.message.reply_text("Invalid or closed match id!")
                return
            team_ids = json.loads(match[2])
            teams = [get_team(conn, team_id) for team_id in team_ids]
            if not teams or team_name not in [team[2] for team in teams if team]:
                logger.debug(f"Player {player_id} specified invalid team: {team_name}")
                await update.message.reply_text("Invalid team name!")
                return
            team_id = next(team[0] for team in teams if team and team[2] == team_name)
            player = get_player(conn, player_id)
            if not player:
                username = update.effective_user.username or f"user_{player_id}"
                initialize_player_citizens(conn, player_id)
                create_team(conn, player_id, f"@{username}_team")
                player = get_player(conn, player_id)
            if player[12] < amount:
                logger.debug(f"Player {player_id} has insufficient {group_name} coins")
                await update.message.reply_text(f"Not enough {group_name} coins!")
                return
            create_wager(conn, player_id, match_id, team_id, amount)
            update_player(conn, player_id, player[1], player[2], player[3], player[4], player[5], player[6], player[7],
                         player[8], player[9], player[10], player[11], player[12] - amount, player[13], player[14], player[15], player[16])
            logger.debug(f"Player {player_id} placed bet of {amount} on {team_name} for match {match_id}")
            await update.message.reply_text(f"Bet placed: {amount} {group_name} coins on {team_name} for match {match_id}!")
        except Exception as e:
            logger.error(f"Error in gamble for player {player_id}: {str(e)}")
            await update.message.reply_text("An error occurred while placing bet.")
        finally:
            conn.close()
    except ValueError:
        logger.debug(f"Player {player_id} used invalid match id or amount")
        await update.message.reply_text("Match id and amount must be numbers!")
    except Exception as e:
        logger.error(f"Error in gamble for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while placing bet.")

async def war(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    if len(context.args) != 2:
        logger.debug(f"Player {player_id} used invalid war syntax")
        await update.message.reply_text("Usage: /war <opponent_player_id> <fighter_count>")
        return
    try:
        opponent_id, fighter_count = map(int, context.args)
        if fighter_count <= 0:
            logger.debug(f"Player {player_id} specified invalid fighter count: {fighter_count}")
            await update.message.reply_text("Fighter count must be positive!")
            return
        conn = sqlite3.connect('battle_forge.db')
        try:
            player = get_player(conn, player_id)
            opponent = get_player(conn, opponent_id)
            if not player or not opponent:
                logger.debug(f"Player {player_id} or opponent {opponent_id} not found")
                await update.message.reply_text("Player or opponent not found!")
                return
            if player_id == opponent_id:
                logger.debug(f"Player {player_id} tried to war themselves")
                await update.message.reply_text("You can't war yourself!")
                return
            player_fighters = [c for c in get_citizens(conn, player_id) if c[3] == 'fighter' and c[8] == 'active']
            opponent_fighters = [c for c in get_citizens(conn, opponent_id) if c[3] == 'fighter' and c[8] == 'active']
            if len(player_fighters) < fighter_count or len(opponent_fighters) < fighter_count:
                logger.debug(f"Insufficient fighters for war: player {player_id} has {len(player_fighters)}, opponent {opponent_id} has {len(opponent_fighters)}")
                await update.message.reply_text("Not enough fighters available!")
                return
            player_power = sum(f[5] * f[4] / 100 for f in player_fighters[:fighter_count]) * quality_modifier(player[11])
            opponent_power = sum(f[5] * f[4] / 100 for f in opponent_fighters[:fighter_count]) * quality_modifier(opponent[11])
            player_score = random.randint(0, 100) + player_power
            opponent_score = random.randint(0, 100) + opponent_power
            player_affected = random.sample(player_fighters, k=int(fighter_count * random.uniform(0.1, 0.3)))
            opponent_affected = random.sample(opponent_fighters, k=int(fighter_count * random.uniform(0.1, 0.3)))
            for fighter in player_affected:
                if random.random() < 0.5:
                    update_citizen(conn, fighter[0], 'dead')
                else:
                    update_citizen(conn, fighter[0], 'injured', (datetime.now() + timedelta(hours=24)).isoformat())
            for fighter in opponent_affected:
                if random.random() < 0.5:
                    update_citizen(conn, fighter[0], 'dead')
                else:
                    update_citizen(conn, fighter[0], 'injured', (datetime.now() + timedelta(hours=24)).isoformat())
            resources_stolen = {}
            coins_change = 0
            response = f"War result: {group_name}\n@{player[1]} (power: {player_power:.2f}) vs @{opponent[1]} (power: {opponent_power:.2f})\n"
            if player_score > opponent_score:
                coins_change = 5
                update_player(conn, player_id, player[1], player[2], player[3], player[4], player[5], player[6], player[7],
                             player[8], player[9], player[10], player[11], player[12] + 5, player[13] + 1, player[14], player[15], player[16])
                update_player(conn, opponent_id, opponent[1], opponent[2], opponent[3], opponent[4], opponent[5], opponent[6], opponent[7],
                             opponent[8], opponent[9], opponent[10], opponent[11], max(opponent[12] - 5, 0), opponent[13], opponent[14], opponent[15], opponent[16])
                for resource in ['sperms', 'eggs', 'water', 'food', 'medicine', 'ore']:
                    index = {'sperms': 2, 'eggs': 3, 'water': 4, 'food': 5, 'medicine': 6, 'ore': 7}[resource]
                    amount = random.randint(0, int(opponent[index] * 0.1))
                    if amount > 0:
                        resources_stolen[resource] = amount
                        player_data = list(player)
                        opponent_data = list(opponent)
                        player_data[index] += amount
                        opponent_data[index] -= amount
                        update_player(conn, player_id, player[1], *player_data[2:])
                        update_player(conn, opponent_id, opponent[1], *opponent_data[2:])
                response += f"Resources stolen: {', '.join(f'{amount} {res}' for res, amount in resources_stolen.items())}\n" if resources_stolen else ""
            else:
                coins_change = -5
                update_player(conn, player_id, player[1], player[2], player[3], player[4], player[5], player[6], player[7],
                             player[8], player[9], player[10], player[11], max(player[12] - 5, 0), player[13], player[14], player[15], player[16])
                update_player(conn, opponent_id, opponent[1], opponent[2], opponent[3], opponent[4], opponent[5], opponent[6], opponent[7],
                             opponent[8], opponent[9], opponent[10], opponent[11], opponent[12] + 5, opponent[13] + 1, opponent[14], opponent[15], opponent[16])
                for resource in ['sperms', 'eggs', 'water', 'food', 'medicine', 'ore']:
                    index = {'sperms': 2, 'eggs': 3, 'water': 4, 'food': 5, 'medicine': 6, 'ore': 7}[resource]
                    amount = random.randint(0, int(player[index] * 0.1))
                    if amount > 0:
                        resources_stolen[resource] = amount
                        player_data = list(player)
                        opponent_data = list(opponent)
                        player_data[index] -= amount
                        opponent_data[index] += amount
                        update_player(conn, player_id, player[1], *player_data[2:])
                        update_player(conn, opponent_id, opponent[1], *opponent_data[2:])
                response += f"Resources stolen: {', '.join(f'{amount} {res}' for res, amount in resources_stolen.items())}\n" if resources_stolen else ""
            response += f"@{player[1]} {'wins' if player_score > opponent_score else 'loses' if opponent_score > player_score else 'ties'}! "
            response += f"Coins: {coins_change:+d}, losses: {len(player_affected)} population\n"
            response += f"@{opponent[1]} losses: {len(opponent_affected)} population"
            conn.commit()
            logger.debug(f"War executed by player {player_id} against {opponent_id}: {player_score} vs {opponent_score}")
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in war for player {player_id}: {str(e)}")
            await update.message.reply_text("An error occurred during the war.")
        finally:
            conn.close()
    except ValueError:
        logger.debug(f"Player {player_id} used invalid war arguments")
        await update.message.reply_text("Opponent id and fighter count must be numbers!")
    except Exception as e:
        logger.error(f"Error in war for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred during the war.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.effective_user.id
    group_name = update.effective_chat.title or "group"
    conn = sqlite3.connect('battle_forge.db')
    try:
        c = conn.cursor()
        c.execute('SELECT player_id, username, coins, war_wins FROM players ORDER BY coins DESC, war_wins DESC LIMIT 10')
        players = c.fetchall()
        response = f"🏆 Leaderboard for {group_name} 🏆\n\n"
        for i, player in enumerate(players, 1):
            player_data = get_player(conn, player[0])
            citizens = get_citizens(conn, player[0])
            babies = get_babies(conn, player[0])
            currency_value = calculate_currency_value(player_data, citizens, babies)
            response += f"{i}. @{player[1]}\n"
            response += f"   {group_name} coins: {player[2]}\n"
            response += f"   War wins: {player[3]}\n"
            response += f"   @{player[1]} coin value: {currency_value:.2f} {group_name} coins\n\n"
        logger.debug(f"Player {player_id} viewed leaderboard")
        await update.message.reply_text(response or "No players on the leaderboard yet!")
    except Exception as e:
        logger.error(f"Error in leaderboard for player {player_id}: {str(e)}")
        await update.message.reply_text("An error occurred while viewing the leaderboard.")
    finally:
        conn.close()

def main():
    try:
        # Load bot token from environment variable
        token = os.getenv('BOT_TOKEN')
        if not token:
            # Hardcode token for testing (not recommended for production)
            token = '8225820998:AAG7Gz5-6u_DgwlCEOriDPdVpeuC5FmVLfs'  # Replace with your actual token from @BotFather
            logger.warning("Using hardcoded token for testing. Consider using a .env file for security.")
        
        # Initialize the bot
        application = Application.builder().token(token).build()

        # Add command handlers
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('collectresources', collectresources))
        application.add_handler(CommandHandler('collectsupplies', collectsupplies))
        application.add_handler(CommandHandler('merge', merge))
        application.add_handler(CommandHandler('upgradequality', upgradequality))
        application.add_handler(CommandHandler('mystats', mystats))
        application.add_handler(CommandHandler('currencies', currencies))
        application.add_handler(CommandHandler('sellable', sellable))
        application.add_handler(CommandHandler('trade', trade))
        application.add_handler(CommandHandler('accepttrade', accepttrade))
        application.add_handler(CommandHandler('sportevent', sportevent))
        application.add_handler(CommandHandler('acceptsport', acceptsport))
        application.add_handler(CommandHandler('teamstats', teamstats))
        application.add_handler(CommandHandler('gamble', gamble))
        application.add_handler(CommandHandler('war', war))
        application.add_handler(CommandHandler('leaderboard', leaderboard))

        # Start the bot
        logger.info("Starting BattleForgeBot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        print(f"Failed to start bot: {str(e)}")

if __name__ == '__main__':
    main()
