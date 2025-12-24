"""
Zombie Survival Tower Defense (Single-file Pygame)
==================================================
Installation
------------
1) Install Python 3.10+ from https://www.python.org/
2) Install Pygame:
   - Windows/macOS/Linux:  python -m pip install pygame
3) Run the game:
   - python zombie_tower_defense.py

This is a self-contained, asset-free tower defense game with a polished
menu system, multiple tower types, waves, scoring, upgrades, and high
score saving.
"""

import json
import math
import os
import random
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

# ----------------------------
# Config
# ----------------------------
WIDTH, HEIGHT = 1100, 720
FPS = 60
TITLE = "Zombie Survival: Tower Defense"
HIGHSCORE_FILE = "highscore.json"

# Colors
DARK = (20, 22, 28)
DARKER = (14, 16, 20)
WHITE = (235, 235, 235)
SOFT_WHITE = (200, 200, 200)
GREEN = (0, 220, 130)
RED = (230, 70, 70)
BLUE = (80, 160, 255)
YELLOW = (250, 220, 90)
PURPLE = (180, 120, 255)
ORANGE = (255, 140, 60)
TEAL = (80, 220, 220)

# Grid for placement
GRID_SIZE = 50
UI_HEIGHT = 100
PLAY_AREA = pygame.Rect(0, 0, WIDTH, HEIGHT - UI_HEIGHT)

# ----------------------------
# Helpers
# ----------------------------

def clamp(value, low, high):
    return max(low, min(high, value))


def load_high_score() -> int:
    if not os.path.exists(HIGHSCORE_FILE):
        return 0
    try:
        with open(HIGHSCORE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return int(data.get("high_score", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def save_high_score(score: int):
    try:
        with open(HIGHSCORE_FILE, "w", encoding="utf-8") as handle:
            json.dump({"high_score": score}, handle)
    except OSError:
        pass


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ----------------------------
# Data definitions
# ----------------------------

@dataclass
class TowerType:
    name: str
    cost: int
    range: int
    fire_rate: float
    damage: int
    color: Tuple[int, int, int]
    bullet_color: Tuple[int, int, int]
    splash_radius: int = 0
    slow: float = 0.0
    slow_duration: float = 0.0


TOWER_TYPES = [
    TowerType("Rifle", 80, 160, 1.5, 15, BLUE, YELLOW),
    TowerType("Sniper", 140, 260, 0.7, 45, PURPLE, WHITE),
    TowerType("Splash", 160, 170, 0.9, 30, ORANGE, YELLOW, splash_radius=60),
    TowerType("Frost", 120, 150, 1.2, 12, TEAL, TEAL, slow=0.45, slow_duration=1.8),
]

ZOMBIE_TYPES = {
    "walker": {"speed": 45, "health": 90, "reward": 8, "color": (90, 200, 120)},
    "runner": {"speed": 80, "health": 65, "reward": 10, "color": (110, 230, 150)},
    "brute": {"speed": 35, "health": 200, "reward": 18, "color": (70, 170, 80)},
    "boss": {"speed": 30, "health": 800, "reward": 80, "color": (150, 240, 150)},
}


# ----------------------------
# Core Entities
# ----------------------------

class Zombie:
    def __init__(self, path: List[Tuple[int, int]], zombie_type: str):
        self.path = path
        self.type = zombie_type
        stats = ZOMBIE_TYPES[zombie_type]
        self.max_health = stats["health"]
        self.health = float(self.max_health)
        self.speed = stats["speed"]
        self.reward = stats["reward"]
        self.color = stats["color"]
        self.radius = 16 if zombie_type != "boss" else 24
        self.path_index = 0
        self.position = pygame.Vector2(self.path[0])
        self.slow_timer = 0.0
        self.slow_factor = 1.0

    def update(self, dt: float) -> bool:
        if self.slow_timer > 0:
            self.slow_timer -= dt
        else:
            self.slow_factor = 1.0
        if self.path_index >= len(self.path) - 1:
            return True
        target = pygame.Vector2(self.path[self.path_index + 1])
        direction = (target - self.position)
        dist = direction.length()
        if dist == 0:
            self.path_index += 1
            return False
        direction = direction.normalize()
        move = self.speed * self.slow_factor * dt
        if move >= dist:
            self.position = target
            self.path_index += 1
        else:
            self.position += direction * move
        return False

    def draw(self, surface: pygame.Surface):
        pygame.draw.circle(surface, DARKER, self.position, self.radius + 3)
        pygame.draw.circle(surface, self.color, self.position, self.radius)
        bar_width = self.radius * 2
        bar_height = 5
        health_ratio = self.health / self.max_health
        bar_x = self.position.x - self.radius
        bar_y = self.position.y - self.radius - 10
        pygame.draw.rect(surface, DARKER, (bar_x, bar_y, bar_width, bar_height))
        pygame.draw.rect(surface, GREEN, (bar_x, bar_y, bar_width * health_ratio, bar_height))


class Projectile:
    def __init__(self, position: pygame.Vector2, target: Zombie, speed: float, damage: int,
                 color: Tuple[int, int, int], splash_radius: int = 0, slow: float = 0.0,
                 slow_duration: float = 0.0):
        self.position = pygame.Vector2(position)
        self.target = target
        self.speed = speed
        self.damage = damage
        self.color = color
        self.splash_radius = splash_radius
        self.slow = slow
        self.slow_duration = slow_duration
        self.alive = True

    def update(self, dt: float):
        if not self.target or self.target.health <= 0:
            self.alive = False
            return
        direction = (self.target.position - self.position)
        dist = direction.length()
        if dist == 0:
            self.alive = False
            return
        direction = direction.normalize()
        move = self.speed * dt
        if move >= dist:
            self.position = pygame.Vector2(self.target.position)
            self.alive = False
        else:
            self.position += direction * move

    def draw(self, surface: pygame.Surface):
        pygame.draw.circle(surface, self.color, self.position, 4)


class Tower:
    def __init__(self, tower_type: TowerType, position: Tuple[int, int]):
        self.tower_type = tower_type
        self.position = pygame.Vector2(position)
        self.cooldown = 0.0
        self.level = 1
        self.pulse = 0.0

    def upgrade_cost(self) -> int:
        return int(self.tower_type.cost * (0.75 + 0.5 * self.level))

    def upgrade(self):
        self.level += 1

    def stats(self):
        dmg = self.tower_type.damage + (self.level - 1) * 6
        rate = self.tower_type.fire_rate + (self.level - 1) * 0.2
        rng = self.tower_type.range + (self.level - 1) * 10
        return dmg, rate, rng

    def update(self, dt: float, zombies: List[Zombie], projectiles: List[Projectile]):
        self.cooldown = max(0.0, self.cooldown - dt)
        self.pulse = (self.pulse + dt) % 1.5
        dmg, rate, rng = self.stats()
        target = None
        best_dist = float("inf")
        for zombie in zombies:
            dist = zombie.position.distance_to(self.position)
            if dist <= rng and dist < best_dist:
                best_dist = dist
                target = zombie
        if target and self.cooldown <= 0:
            self.cooldown = 1.0 / rate
            projectiles.append(
                Projectile(
                    self.position,
                    target,
                    speed=320,
                    damage=dmg,
                    color=self.tower_type.bullet_color,
                    splash_radius=self.tower_type.splash_radius,
                    slow=self.tower_type.slow,
                    slow_duration=self.tower_type.slow_duration,
                )
            )

    def draw(self, surface: pygame.Surface, selected=False):
        size = 26
        rect = pygame.Rect(0, 0, size, size)
        rect.center = self.position
        pygame.draw.rect(surface, DARKER, rect.inflate(6, 6), border_radius=6)
        pygame.draw.rect(surface, self.tower_type.color, rect, border_radius=6)
        if selected:
            pygame.draw.circle(surface, SOFT_WHITE, self.position, self.tower_type.range, 1)


# ----------------------------
# UI helpers
# ----------------------------

class Button:
    def __init__(self, rect: pygame.Rect, text: str, font, bg=BLUE, fg=WHITE):
        self.rect = rect
        self.text = text
        self.font = font
        self.bg = bg
        self.fg = fg
        self.hover = False

    def draw(self, surface):
        color = tuple(min(255, c + 20) for c in self.bg) if self.hover else self.bg
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        label = self.font.render(self.text, True, self.fg)
        label_rect = label.get_rect(center=self.rect.center)
        surface.blit(label, label_rect)

    def update(self, mouse_pos):
        self.hover = self.rect.collidepoint(mouse_pos)

    def clicked(self, mouse_pos, pressed):
        return pressed and self.rect.collidepoint(mouse_pos)


# ----------------------------
# Game class
# ----------------------------

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 20)
        self.big_font = pygame.font.SysFont("arial", 36, bold=True)
        self.tiny_font = pygame.font.SysFont("arial", 16)
        self.running = True

        self.state = "menu"
        self.high_score = load_high_score()
        self.settings = {"difficulty": "Normal"}

        self.reset_game()

    def reset_game(self):
        self.path = [
            (0, 140), (200, 140), (200, 360), (420, 360),
            (420, 180), (700, 180), (700, 500), (980, 500),
            (980, 260), (WIDTH, 260),
        ]
        self.towers: List[Tower] = []
        self.projectiles: List[Projectile] = []
        self.zombies: List[Zombie] = []
        self.selected_tower: Optional[int] = None
        self.coins = 180
        self.lives = 20
        self.score = 0
        self.wave = 0
        self.wave_in_progress = False
        self.spawn_timer = 0.0
        self.spawn_queue: List[Tuple[str, float]] = []
        self.pause = False

    def make_wave(self, wave_number: int) -> List[Tuple[str, float]]:
        queue = []
        base_count = 6 + wave_number * 2
        for _ in range(base_count):
            queue.append(("walker", 0.8))
        if wave_number >= 2:
            for _ in range(2 + wave_number // 2):
                queue.append(("runner", 0.7))
        if wave_number >= 4:
            for _ in range(1 + wave_number // 3):
                queue.append(("brute", 1.4))
        if wave_number % 5 == 0:
            queue.append(("boss", 2.2))
        random.shuffle(queue)
        return queue

    def start_wave(self):
        self.wave += 1
        self.wave_in_progress = True
        self.spawn_queue = self.make_wave(self.wave)
        self.spawn_timer = 1.0

    def handle_projectiles(self, dt: float):
        for projectile in list(self.projectiles):
            projectile.update(dt)
            if not projectile.alive:
                if projectile.target and projectile.target.health > 0:
                    if projectile.splash_radius > 0:
                        for zombie in self.zombies:
                            if zombie.position.distance_to(projectile.position) <= projectile.splash_radius:
                                zombie.health -= projectile.damage
                    else:
                        projectile.target.health -= projectile.damage
                    if projectile.slow > 0 and projectile.target.health > 0:
                        projectile.target.slow_factor = 1 - projectile.slow
                        projectile.target.slow_timer = projectile.slow_duration
                self.projectiles.remove(projectile)

    def remove_dead_zombies(self):
        for zombie in list(self.zombies):
            if zombie.health <= 0:
                self.zombies.remove(zombie)
                self.coins += zombie.reward
                self.score += 20 + self.wave * 5

    def update_game(self, dt: float):
        if self.pause:
            return
        if not self.wave_in_progress and not self.zombies:
            pass
        if self.wave_in_progress:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0 and self.spawn_queue:
                zombie_type, delay = self.spawn_queue.pop()
                self.zombies.append(Zombie(self.path, zombie_type))
                self.spawn_timer = delay
            if not self.spawn_queue and not self.zombies:
                self.wave_in_progress = False
                self.coins += 30 + self.wave * 5

        for zombie in list(self.zombies):
            reached_end = zombie.update(dt)
            if reached_end:
                self.zombies.remove(zombie)
                self.lives -= 1
                if self.lives <= 0:
                    self.state = "gameover"
                    self.high_score = max(self.high_score, self.score)
                    save_high_score(self.high_score)

        self.handle_projectiles(dt)
        self.remove_dead_zombies()

        for tower in self.towers:
            tower.update(dt, self.zombies, self.projectiles)

    # ----------------------------
    # Rendering
    # ----------------------------

    def draw_path(self):
        pygame.draw.lines(self.screen, (60, 80, 60), False, self.path, 40)
        pygame.draw.lines(self.screen, (40, 60, 40), False, self.path, 6)

    def draw_grid(self):
        for x in range(0, WIDTH, GRID_SIZE):
            pygame.draw.line(self.screen, (30, 35, 40), (x, 0), (x, PLAY_AREA.bottom))
        for y in range(0, PLAY_AREA.bottom, GRID_SIZE):
            pygame.draw.line(self.screen, (30, 35, 40), (0, y), (WIDTH, y))

    def draw_ui(self):
        ui_rect = pygame.Rect(0, PLAY_AREA.bottom, WIDTH, UI_HEIGHT)
        pygame.draw.rect(self.screen, DARKER, ui_rect)

        labels = [
            f"Lives: {self.lives}",
            f"Coins: {self.coins}",
            f"Score: {self.score}",
            f"Wave: {self.wave}",
        ]
        for idx, text in enumerate(labels):
            label = self.font.render(text, True, WHITE)
            self.screen.blit(label, (20 + idx * 180, PLAY_AREA.bottom + 10))

        wave_text = "In Progress" if self.wave_in_progress else "Ready"
        status = self.tiny_font.render(f"Wave: {wave_text}", True, SOFT_WHITE)
        self.screen.blit(status, (20, PLAY_AREA.bottom + 40))
<<<<<<< HEAD
        if not self.wave_in_progress:
            prompt = self.tiny_font.render("Press SPACE to start next wave", True, SOFT_WHITE)
            self.screen.blit(prompt, (20, PLAY_AREA.bottom + 60))
=======
>>>>>>> main

        for i, tower_type in enumerate(TOWER_TYPES):
            x = 420 + i * 160
            rect = pygame.Rect(x, PLAY_AREA.bottom + 10, 140, 70)
            pygame.draw.rect(self.screen, tower_type.color, rect, border_radius=8)
            name = self.tiny_font.render(tower_type.name, True, DARKER)
            cost = self.tiny_font.render(f"${tower_type.cost}", True, DARKER)
            self.screen.blit(name, (x + 8, PLAY_AREA.bottom + 14))
            self.screen.blit(cost, (x + 8, PLAY_AREA.bottom + 38))
            if self.coins < tower_type.cost:
<<<<<<< HEAD
                overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                self.screen.blit(overlay, rect.topleft)
=======
                pygame.draw.rect(self.screen, (0, 0, 0, 120), rect)
>>>>>>> main

    def draw_game(self):
        self.screen.fill(DARK)
        self.draw_path()
        self.draw_grid()
        for tower in self.towers:
            selected = self.selected_tower is not None and self.towers[self.selected_tower] == tower
            tower.draw(self.screen, selected)
        for zombie in self.zombies:
            zombie.draw(self.screen)
        for projectile in self.projectiles:
            projectile.draw(self.screen)
<<<<<<< HEAD
        self.draw_placement_preview()
=======
>>>>>>> main
        self.draw_ui()
        if self.pause:
            self.draw_overlay("Paused", "Press P to resume")

<<<<<<< HEAD
    def draw_placement_preview(self):
        if self.selected_tower is None:
            return
        mouse_pos = pygame.mouse.get_pos()
        if mouse_pos[1] > PLAY_AREA.bottom:
            return
        snapped = (
            mouse_pos[0] // GRID_SIZE * GRID_SIZE + GRID_SIZE // 2,
            mouse_pos[1] // GRID_SIZE * GRID_SIZE + GRID_SIZE // 2,
        )
        tower_type = TOWER_TYPES[self.selected_tower]
        can_place = self.can_place(snapped)
        color = tower_type.color if can_place else RED
        preview_rect = pygame.Rect(0, 0, 26, 26)
        preview_rect.center = snapped
        preview = pygame.Surface(preview_rect.size, pygame.SRCALPHA)
        preview.fill((*color, 140))
        self.screen.blit(preview, preview_rect.topleft)
        pygame.draw.circle(self.screen, color, snapped, tower_type.range, 1)

=======
>>>>>>> main
    def draw_overlay(self, title: str, subtitle: str):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        title_label = self.big_font.render(title, True, WHITE)
        subtitle_label = self.font.render(subtitle, True, SOFT_WHITE)
        self.screen.blit(title_label, title_label.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
        self.screen.blit(subtitle_label, subtitle_label.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))

    # ----------------------------
    # Input
    # ----------------------------

    def can_place(self, position: Tuple[int, int]) -> bool:
        rect = pygame.Rect(position[0] - 16, position[1] - 16, 32, 32)
        if not PLAY_AREA.contains(rect):
            return False
        for tower in self.towers:
            if tower.position.distance_to(position) < 36:
                return False
        # Avoid path
        for i in range(len(self.path) - 1):
            a = pygame.Vector2(self.path[i])
            b = pygame.Vector2(self.path[i + 1])
            if self.point_to_segment_distance(position, a, b) < 40:
                return False
        return True

    @staticmethod
    def point_to_segment_distance(point, a, b):
        ap = pygame.Vector2(point) - a
        ab = b - a
        ab_len2 = ab.length_squared()
        if ab_len2 == 0:
            return ap.length()
        t = clamp(ap.dot(ab) / ab_len2, 0, 1)
        closest = a + ab * t
        return pygame.Vector2(point).distance_to(closest)

    def handle_game_click(self, pos: Tuple[int, int]):
        if pos[1] > PLAY_AREA.bottom:
            for i, tower_type in enumerate(TOWER_TYPES):
                rect = pygame.Rect(420 + i * 160, PLAY_AREA.bottom + 10, 140, 70)
                if rect.collidepoint(pos) and self.coins >= tower_type.cost:
                    self.selected_tower = i
            return

        if self.selected_tower is not None:
            snapped = (
                pos[0] // GRID_SIZE * GRID_SIZE + GRID_SIZE // 2,
                pos[1] // GRID_SIZE * GRID_SIZE + GRID_SIZE // 2,
            )
            if self.can_place(snapped):
                tower_type = TOWER_TYPES[self.selected_tower]
<<<<<<< HEAD
                if self.coins >= tower_type.cost:
                    self.towers.append(Tower(tower_type, snapped))
                    self.coins -= tower_type.cost
=======
                self.towers.append(Tower(tower_type, snapped))
                self.coins -= tower_type.cost
>>>>>>> main
            return

        for idx, tower in enumerate(self.towers):
            if tower.position.distance_to(pos) < 20:
                self.selected_tower = idx
                return

    def handle_key(self, event):
        if event.key == pygame.K_ESCAPE:
            self.state = "menu"
        if event.key == pygame.K_p:
            self.pause = not self.pause
        if event.key == pygame.K_SPACE and not self.wave_in_progress:
            self.start_wave()
        if event.key == pygame.K_u and self.selected_tower is not None:
            tower = self.towers[self.selected_tower]
            cost = tower.upgrade_cost()
            if self.coins >= cost:
                self.coins -= cost
                tower.upgrade()

    # ----------------------------
    # Menus
    # ----------------------------

    def run_menu(self):
        start_btn = Button(pygame.Rect(WIDTH // 2 - 120, 260, 240, 50), "Start Game", self.font)
        settings_btn = Button(pygame.Rect(WIDTH // 2 - 120, 320, 240, 50), "Settings", self.font)
        quit_btn = Button(pygame.Rect(WIDTH // 2 - 120, 380, 240, 50), "Quit", self.font, bg=RED)

        while self.state == "menu" and self.running:
            dt = self.clock.tick(FPS) / 1000
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if start_btn.clicked(mouse_pos, True):
                        self.reset_game()
                        self.state = "game"
                    if settings_btn.clicked(mouse_pos, True):
                        self.state = "settings"
                    if quit_btn.clicked(mouse_pos, True):
                        self.running = False

            for button in (start_btn, settings_btn, quit_btn):
                button.update(mouse_pos)

            self.screen.fill(DARK)
            title = self.big_font.render(TITLE, True, WHITE)
            subtitle = self.font.render("Survive the horde. Build smart. Win big.", True, SOFT_WHITE)
            high = self.font.render(f"High Score: {self.high_score}", True, YELLOW)
            self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 180)))
            self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 220)))
            self.screen.blit(high, high.get_rect(center=(WIDTH // 2, 460)))
            for button in (start_btn, settings_btn, quit_btn):
                button.draw(self.screen)

            pygame.display.flip()

    def run_settings(self):
        back_btn = Button(pygame.Rect(WIDTH // 2 - 120, 420, 240, 50), "Back", self.font)
        difficulty_btn = Button(pygame.Rect(WIDTH // 2 - 120, 320, 240, 50),
                                f"Difficulty: {self.settings['difficulty']}", self.font)

        while self.state == "settings" and self.running:
            dt = self.clock.tick(FPS) / 1000
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if back_btn.clicked(mouse_pos, True):
                        self.state = "menu"
                    if difficulty_btn.clicked(mouse_pos, True):
                        self.settings["difficulty"] = "Hard" if self.settings["difficulty"] == "Normal" else "Normal"
                        difficulty_btn.text = f"Difficulty: {self.settings['difficulty']}"

            for button in (back_btn, difficulty_btn):
                button.update(mouse_pos)

            self.screen.fill(DARK)
            title = self.big_font.render("Settings", True, WHITE)
            self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 200)))
            for button in (difficulty_btn, back_btn):
                button.draw(self.screen)
            pygame.display.flip()

    def run_gameover(self):
        retry_btn = Button(pygame.Rect(WIDTH // 2 - 120, 360, 240, 50), "Retry", self.font)
        menu_btn = Button(pygame.Rect(WIDTH // 2 - 120, 420, 240, 50), "Main Menu", self.font)

        while self.state == "gameover" and self.running:
            dt = self.clock.tick(FPS) / 1000
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if retry_btn.clicked(mouse_pos, True):
                        self.reset_game()
                        self.state = "game"
                    if menu_btn.clicked(mouse_pos, True):
                        self.state = "menu"

            for button in (retry_btn, menu_btn):
                button.update(mouse_pos)

            self.screen.fill(DARK)
            title = self.big_font.render("Game Over", True, RED)
            score = self.font.render(f"Score: {self.score}", True, WHITE)
            high = self.font.render(f"High Score: {self.high_score}", True, YELLOW)
            self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 220)))
            self.screen.blit(score, score.get_rect(center=(WIDTH // 2, 270)))
            self.screen.blit(high, high.get_rect(center=(WIDTH // 2, 300)))
            for button in (retry_btn, menu_btn):
                button.draw(self.screen)
            pygame.display.flip()

    # ----------------------------
    # Main loop
    # ----------------------------

    def run(self):
        while self.running:
            if self.state == "menu":
                self.run_menu()
                continue
            if self.state == "settings":
                self.run_settings()
                continue
            if self.state == "gameover":
                self.run_gameover()
                continue

            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_game_click(event.pos)
                if event.type == pygame.KEYDOWN:
                    self.handle_key(event)

            self.update_game(dt)
            self.draw_game()
            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
