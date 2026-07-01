import sqlite3
import json
import os

DB_FILE = "database.sqlite"

def get_db():
    conn = sqlite3.connect(DB_FILE, isolation_level="EXCLUSIVE")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            coins INTEGER NOT NULL DEFAULT 1000,
            is_pro BOOLEAN NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            cosmetics TEXT NOT NULL DEFAULT '["default"]',
            elo INTEGER NOT NULL DEFAULT 1200
        )''')
        conn.commit()

init_db()

def get_user(user_id: str):
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (user_id, coins, is_pro, wins, losses, cosmetics, elo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, 1000, False, 0, 0, '["default"]', 1200)
            )
            conn.commit()
            return {
                "coins": 1000,
                "is_pro": False,
                "wins": 0,
                "losses": 0,
                "cosmetics": ["default"],
                "elo": 1200
            }
        return {
            "coins": row["coins"],
            "is_pro": bool(row["is_pro"]),
            "wins": row["wins"],
            "losses": row["losses"],
            "cosmetics": json.loads(row["cosmetics"]),
            "elo": row["elo"]
        }

def update_user(user_id: str, updates: dict):
    with get_db() as conn:
        # First ensure user exists and lock the row
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            get_user(user_id) # create it
            cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()

        new_coins = row["coins"]
        new_is_pro = bool(row["is_pro"])
        new_wins = row["wins"]
        new_losses = row["losses"]
        new_cosmetics = json.loads(row["cosmetics"])
        new_elo = row["elo"]

        for k, v in updates.items():
            if k == "coins":
                new_coins += v
            elif k == "cosmetics":
                if v not in new_cosmetics:
                    new_cosmetics.append(v)
            elif k == "is_pro":
                new_is_pro = v
            elif k == "wins":
                new_wins = v
            elif k == "losses":
                new_losses = v
            elif k == "elo":
                new_elo = v

        conn.execute(
            "UPDATE users SET coins=?, is_pro=?, wins=?, losses=?, cosmetics=?, elo=? WHERE user_id=?",
            (new_coins, new_is_pro, new_wins, new_losses, json.dumps(new_cosmetics), new_elo, user_id)
        )
        conn.commit()
        
        return {
            "coins": new_coins,
            "is_pro": new_is_pro,
            "wins": new_wins,
            "losses": new_losses,
            "cosmetics": new_cosmetics,
            "elo": new_elo
        }
