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


# ------------------------- DRAW HELPERS -------------------------

def draw_text(text, x, y, color=WHITE, font=FONT, center=False):
    image = font.render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(image, rect)


def draw_background():
    screen.fill(BLACK)
    # Subtle stars
    for i in range(45):
        x = (i * 97 + 31) % WIDTH
        y = (i * 53 + 17) % HEIGHT
        pygame.draw.circle(screen, (35, 43, 67), (x, y), 1)


def draw_button(text, rect, mouse_pos, color=BLUE):
    hovered = rect.collidepoint(mouse_pos)
    fill = tuple(min(255, c + 35) for c in color) if hovered else color
    pygame.draw.rect(screen, fill, rect, border_radius=9)
    pygame.draw.rect(screen, WHITE, rect, 2, border_radius=9)
    draw_text(text, rect.centerx, rect.centery, WHITE, MID, center=True)


# ------------------------- GAME OBJECTS -------------------------

class Paddle:
    def __init__(self):
        self.base_width = 110
        self.width = self.base_width
        self.rect = pygame.Rect(WIDTH // 2 - self.width // 2, HEIGHT - 38,
                                self.width, 14)
        self.speed = 8
        self.long_until = 0
        self.magnet_until = 0
        self.shield_until = 0

    def update(self, keys):
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.rect.x += self.speed
        self.rect.left = max(0, self.rect.left)
        self.rect.right = min(WIDTH, self.rect.right)

        now = pygame.time.get_ticks()
        if self.long_until and now >= self.long_until:
            center = self.rect.centerx
            self.width = self.base_width
            self.rect.width = self.width
            self.rect.centerx = center
            self.rect.clamp_ip(screen.get_rect())
            self.long_until = 0

    def activate_long(self):
        center = self.rect.centerx
        self.width = 165
        self.rect.width = self.width
        self.rect.centerx = center
        self.rect.clamp_ip(screen.get_rect())
        self.long_until = pygame.time.get_ticks() + POWER_DURATION

    def draw(self):
        color = CYAN if self.long_until > pygame.time.get_ticks() else BLUE
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, WHITE, self.rect, 2, border_radius=8)


class Ball:
    def __init__(self, x=None, y=None, vx=None, vy=None):
        self.radius = 8
        self.x = WIDTH / 2 if x is None else float(x)
        self.y = HEIGHT - 55 if y is None else float(y)
        self.vx = random.choice([-4.2, 4.2]) if vx is None else float(vx)
        self.vy = -4.8 if vy is None else float(vy)
        self.stuck = True
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.update_rect()
        self.last_fire_hit = 0

    def update_rect(self):
        self.rect.center = (round(self.x), round(self.y))

    def launch(self):
        if self.stuck:
            self.stuck = False

    def clone(self, angle_sign):
        clone = Ball(self.x, self.y, self.vx * angle_sign, self.vy)
        clone.stuck = False
        return clone

    def update(self, slow_active, paddle):
        if self.stuck:
            self.x = paddle.rect.centerx
            self.y = paddle.rect.top - self.radius - 1
            self.update_rect()
            return False

        factor = 0.72 if slow_active else 1.0
        self.x += self.vx * factor
        self.y += self.vy * factor

        if self.x - self.radius <= 0:
            self.x = self.radius
            self.vx = abs(self.vx)
        elif self.x + self.radius >= WIDTH:
            self.x = WIDTH - self.radius
            self.vx = -abs(self.vx)

        if self.y - self.radius <= PLAY_TOP:
            self.y = PLAY_TOP + self.radius
            self.vy = abs(self.vy)

        self.update_rect()
        return self.y - self.radius > HEIGHT

    def bounce_paddle(self, paddle):
        if not self.stuck and self.vy > 0 and self.rect.colliderect(paddle.rect):
            self.y = paddle.rect.top - self.radius - 1
            offset = (self.x - paddle.rect.centerx) / max(1, paddle.rect.width / 2)
            self.vx = max(-6.0, min(6.0, offset * 6.0))
            if abs(self.vx) < 1.2:
                self.vx = 1.2 if self.vx >= 0 else -1.2
            self.vy = -max(4.0, math.sqrt(max(1, 46 - self.vx * self.vx)))
            self.update_rect()

    def draw(self, fire_active):
        color = ORANGE if fire_active else YELLOW
        pygame.draw.circle(screen, color, (round(self.x), round(self.y)), self.radius)
        pygame.draw.circle(screen, WHITE, (round(self.x - 2), round(self.y - 2)), 2)
