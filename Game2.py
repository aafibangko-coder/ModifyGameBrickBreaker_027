import pygame
import random
import sqlite3
import sys
import math

# ============================================================
# BLOCK BREAKER ULTIMATE
# Controls:
#   LEFT/RIGHT or A/D : Move paddle
#   SPACE             : Launch ball / Resume
#   X                 : Fire laser (requires laser ammo)
#   P                 : Pause
#   ESC               : Back to menu / Exit
# ============================================================

pygame.init()

WIDTH, HEIGHT = 800, 600
FPS = 60
DB_NAME = "block_breaker.db"

# Colors
BLACK = (13, 16, 30)
WHITE = (240, 244, 255)
GRAY = (130, 140, 160)
BLUE = (70, 155, 255)
CYAN = (60, 225, 235)
GREEN = (65, 205, 125)
RED = (245, 80, 90)
YELLOW = (255, 220, 80)
ORANGE = (255, 155, 65)
PURPLE = (180, 105, 245)
PINK = (255, 105, 190)
GOLD = (255, 190, 45)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Block Breaker Ultimate")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("arial", 20)
SMALL = pygame.font.SysFont("arial", 15)
BIG = pygame.font.SysFont("arial", 46, bold=True)
MID = pygame.font.SysFont("arial", 28, bold=True)

POWER_DURATION = 8000
PLAY_TOP = 55
PLAY_BOTTOM = HEIGHT - 45

# ------------------------- DATABASE -------------------------

def db_connect():
    return sqlite3.connect(DB_NAME)


def init_database():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player TEXT NOT NULL,
                score INTEGER NOT NULL,
                level INTEGER NOT NULL,
                coins INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_data (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_coins INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT OR IGNORE INTO player_data (id, total_coins) VALUES (1, 0)"
        )


def get_total_coins():
    with db_connect() as conn:
        row = conn.execute(
            "SELECT total_coins FROM player_data WHERE id = 1"
        ).fetchone()
        return row[0] if row else 0


def add_total_coins(amount):
    if amount <= 0:
        return
    with db_connect() as conn:
        conn.execute(
            "UPDATE player_data SET total_coins = total_coins + ? WHERE id = 1",
            (amount,)
        )


def save_result(player, score, level, coins):
    player = (player.strip() or "Player")[:20]
    with db_connect() as conn:
        conn.execute(
            "INSERT INTO leaderboard (player, score, level, coins) VALUES (?, ?, ?, ?)",
            (player, score, level, coins)
        )


def get_leaderboard():
    with db_connect() as conn:
        return conn.execute("""
            SELECT player, score, level, coins, created_at
            FROM leaderboard
            ORDER BY score DESC, level DESC
            LIMIT 10
        """).fetchall()

