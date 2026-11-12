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


class Block:
    def __init__(self, x, y, health=1, kind="normal"):
        self.rect = pygame.Rect(x, y, 52, 21)
        self.health = health
        self.kind = kind
        self.max_health = health

    def hit(self):
        self.health -= 1

    def draw(self):
        if self.kind == "bomb":
            color = ORANGE
        elif self.max_health >= 3:
            color = PURPLE
        elif self.max_health == 2:
            color = BLUE
        else:
            color = GREEN
        pygame.draw.rect(screen, color, self.rect, border_radius=4)
        pygame.draw.rect(screen, WHITE, self.rect, 1, border_radius=4)
        if self.kind == "bomb":
            draw_text("B", self.rect.centerx, self.rect.centery, WHITE, SMALL, True)
        elif self.max_health > 1:
            draw_text(str(max(0, self.health)), self.rect.centerx,
                      self.rect.centery, WHITE, SMALL, True)


class Boss:
    def __init__(self, level):
        self.width = 190
        self.height = 34
        self.rect = pygame.Rect(WIDTH // 2 - self.width // 2, 78,
                                self.width, self.height)
        self.max_hp = 18 + level * 4
        self.hp = self.max_hp
        self.speed = 2.2 + level * 0.12
        self.direction = 1
        self.last_hit = 0

    def update(self):
        self.rect.x += int(self.speed * self.direction)
        if self.rect.left <= 15:
            self.rect.left = 15
            self.direction = 1
        elif self.rect.right >= WIDTH - 15:
            self.rect.right = WIDTH - 15
            self.direction = -1

    def hit(self):
        now = pygame.time.get_ticks()
        if now - self.last_hit > 180:
            self.hp -= 1
            self.last_hit = now
            return True
        return False

    def draw(self):
        pygame.draw.rect(screen, (145, 45, 75), self.rect, border_radius=8)
        pygame.draw.rect(screen, PINK, self.rect, 3, border_radius=8)
        bar = pygame.Rect(170, 42, 460, 9)
        pygame.draw.rect(screen, (65, 35, 50), bar, border_radius=4)
        fill = bar.copy()
        fill.width = int(bar.width * max(0, self.hp) / self.max_hp)
        pygame.draw.rect(screen, PINK, fill, border_radius=4)
        draw_text(f"BOSS HP: {max(0, self.hp)}/{self.max_hp}",
                  WIDTH // 2, 27, WHITE, SMALL, True)


class FallingItem:
    COLORS = {
        "LONG": CYAN, "MULTI": PURPLE, "SLOW": GREEN,
        "LIFE": RED, "FIRE": ORANGE, "LASER": YELLOW,
        "MAGNET": PINK, "SHIELD": BLUE
    }
    LABELS = {
        "LONG": "L", "MULTI": "M", "SLOW": "S", "LIFE": "+",
        "FIRE": "F", "LASER": "X", "MAGNET": "G", "SHIELD": "D"
    }

    def __init__(self, x, y, item_type):
        self.x = float(x)
        self.y = float(y)
        self.item_type = item_type
        self.rect = pygame.Rect(int(x - 12), int(y - 12), 24, 24)

    def update(self):
        self.y += 2.7
        self.rect.center = (int(self.x), int(self.y))

    def draw(self):
        color = self.COLORS[self.item_type]
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), 12)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), 12, 1)
        draw_text(self.LABELS[self.item_type], self.x, self.y,
                  BLACK, SMALL, True)


class Coin:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.rect = pygame.Rect(int(x - 8), int(y - 8), 16, 16)

    def update(self):
        self.y += 3.2
        self.rect.center = (int(self.x), int(self.y))

    def draw(self):
        pygame.draw.circle(screen, GOLD, (int(self.x), int(self.y)), 8)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), 8, 1)
        draw_text("$", self.x, self.y, BLACK, SMALL, True)


class Laser:
    def __init__(self, x, y):
        self.rect = pygame.Rect(int(x - 3), int(y - 15), 6, 18)

    def update(self):
        self.rect.y -= 9

    def draw(self):
        pygame.draw.rect(screen, CYAN, self.rect, border_radius=3)
        pygame.draw.rect(screen, WHITE, self.rect, 1, border_radius=3)


# ------------------------- LEVEL GENERATION -------------------------

def create_level(level):
    blocks = []
    cols = 11
    block_w, block_h = 52, 21
    gap_x, gap_y = 9, 9
    total = cols * block_w + (cols - 1) * gap_x
    start_x = (WIDTH - total) // 2
    rows = min(4 + (level - 1) // 2, 7)

    for row in range(rows):
        for col in range(cols):
            # A few gaps make later levels less repetitive.
            if level >= 4 and (row + col + level) % 13 == 0:
                continue
            x = start_x + col * (block_w + gap_x)
            y = 105 + row * (block_h + gap_y)
            health = 1 + min(2, (level - 1) // 3)
            kind = "bomb" if random.random() < 0.10 else "normal"
            blocks.append(Block(x, y, health, kind))

    boss = Boss(level) if level % 3 == 0 else None
    return blocks, boss


# ------------------------- GAME STATE -------------------------

def new_game():
    level = 1
    blocks, boss = create_level(level)
    return {
        "level": level,
        "score": 0,
        "coins": 0,
        "lives": 3,
        "paddle": Paddle(),
        "balls": [Ball()],
        "blocks": blocks,
        "boss": boss,
        "items": [],
        "coins_falling": [],
        "lasers": [],
        "laser_ammo": 0,
        "slow_until": 0,
        "fire_until": 0,
        "magnet_until": 0,
        "shield_until": 0,
        "shield_used": False,
        "level_banner_until": pygame.time.get_ticks() + 1800,
        "saved": False,
        "player": "Player"
    }


def activate_item(item_type, game):
    now = pygame.time.get_ticks()
    paddle = game["paddle"]
    balls = game["balls"]

    if item_type == "LONG":
        paddle.activate_long()
    elif item_type == "MULTI":
        active = [b for b in balls if not b.stuck]
        if active:
            source = active[0]
            balls.append(source.clone(-1))
            balls.append(source.clone(1))
        else:
            balls.append(Ball())
    elif item_type == "SLOW":
        game["slow_until"] = now + POWER_DURATION
    elif item_type == "LIFE":
        game["lives"] = min(5, game["lives"] + 1)
    elif item_type == "FIRE":
        game["fire_until"] = now + POWER_DURATION
    elif item_type == "LASER":
        game["laser_ammo"] = min(30, game["laser_ammo"] + 12)
    elif item_type == "MAGNET":
        game["magnet_until"] = now + POWER_DURATION
    elif item_type == "SHIELD":
        game["shield_until"] = now + POWER_DURATION
        game["shield_used"] = False
