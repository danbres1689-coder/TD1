# Zombie Survival Tower Defense Game
# ==================================
# Installation Instructions:
# 1. Install Python 3.x from https://www.python.org/ if not already installed.
# 2. Install Pygame via pip: Open a terminal/command prompt and run `pip install pygame`.
# 3. Save this script as a .py file (e.g., zombie_tower_defense.py).
# 4. Run the script: `python zombie_tower_defense.py`.
# No external assets needed; everything is generated in-code using simple shapes and colors.
# The game uses mouse for tower placement/upgrades and UI interactions, spacebar to start waves,
# P key to pause, ESC to quit menus or return to main menu.

import pygame
import sys
import random
import math
import os

# Initialize Pygame
pygame.init()
pygame.mixer.init()  # For sound effects

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
TILE_SIZE = 40  # For grid-based placement (optional snap)
MAX_WAVES = 10  # Number of waves to win
START_LIVES = 20
START_COINS = 200
PATH_WIDTH = 40  # Width of the path for collision avoidance

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
DARK_GREEN = (0, 128, 0)
PURPLE = (128, 0, 128)

# Define the path zombies follow (a winding path from left to right)
PATH = [
    (0, 300), (100, 300), (100, 200), (200, 200), (200, 400),
    (300, 400), (300, 100), (400, 100), (400, 500), (500, 500),
    (500, 200), (600, 200), (600, 400), (700, 400), (700, 300),
    (800, 300)
]

# Sound placeholders (simple tones using Pygame mixer)
# Generate simple beep sounds in-memory
def create_beep_sound(frequency, duration):
    sample_rate = pygame.mixer.get_init()[0]
    max_amplitude = 2 ** (abs(pygame.mixer.get_init()[1]) - 1) - 1
    samples = int(sample_rate * duration)
    wave = [int(max_amplitude * math.sin(2 * math.pi * frequency * x / sample_rate)) for x in range(samples)]
    sound = pygame.sndarray.make_sound(pygame.sndarray.array(wave))
    return sound

SHOOT_SOUND = create_beep_sound(440, 0.1)  # A4 note for shooting
HIT_SOUND = create_beep_sound(220, 0.1)    # A3 note for hit
DEATH_SOUND = create_beep_sound(110, 0.2)  # A2 note for death
WAVE_SOUND = create_beep_sound(880, 0.3)   # A5 note for wave start
COIN_SOUND = create_beep_sound(660, 0.1)   # E5 note for coin

# High score file
HIGH_SCORE_FILE = "highscore.txt"

# Load high score
def load_high_score():
    if os.path.exists(HIGH_SCORE_FILE):
        with open(HIGH_SCORE_FILE, "r") as f:
            return int(f.read().strip())
    return 0

# Save high score
def save_high_score(score):
    current_high = load_high_score()
    if score > current_high:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(score))

# Button class for menus
class Button:
    def __init__(self, x, y, width, height, text, color=BLUE, text_color=WHITE):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.font = pygame.font.SysFont(None, 40)

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

# Tower class
class Tower:
    def __init__(self, x, y, tower_type):
        self.pos = (x, y)
        self.type = tower_type
        self.level = 1
        self.cooldown = 0
        self.target = None
        self.range = 150
        self.damage = 10
        self.fire_rate = 60  # Frames between shots
        self.cost = 100
        self.upgrade_cost = 50
        self.color = BLUE
        self.size = 20  # Rectangle half-size

        # Tower types
        if tower_type == "sniper":
            self.range = 300
            self.damage = 50
            self.fire_rate = 120
            self.cost = 200
            self.upgrade_cost = 100
            self.color = PURPLE
        elif tower_type == "aoe":
            self.range = 100
            self.damage = 20
            self.fire_rate = 90
            self.cost = 150
            self.upgrade_cost = 75
            self.color = RED
        elif tower_type == "slow":
            self.range = 120
            self.damage = 5
            self.fire_rate = 30
            self.cost = 120
            self.upgrade_cost = 60
            self.color = GREEN  # Slowing effect

    def upgrade(self):
        self.level += 1
        self.damage += 10
        self.range += 20
        self.fire_rate = max(10, self.fire_rate - 10)
        self.upgrade_cost += 50

    def find_target(self, zombies):
        closest = None
        min_dist = float('inf')
        for zombie in zombies:
            dist = math.hypot(zombie.pos[0] - self.pos[0], zombie.pos[1] - self.pos[1])
            if dist < self.range and dist < min_dist:
                min_dist = dist
                closest = zombie
        self.target = closest

    def shoot(self, bullets):
        if self.target:
            bullet = Bullet(self.pos[0], self.pos[1], self.target, self.damage, self.type)
            bullets.append(bullet)
            SHOOT_SOUND.play()
            self.cooldown = self.fire_rate

    def draw(self, screen):
        # Draw tower as rectangle with level indicator
        pygame.draw.rect(screen, self.color, (self.pos[0] - self.size, self.pos[1] - self.size, self.size*2, self.size*2))
        pygame.draw.circle(screen, YELLOW, self.pos, self.range, 1)  # Range circle (debug, optional)
        font = pygame.font.SysFont(None, 20)
        level_text = font.render(str(self.level), True, WHITE)
        screen.blit(level_text, (self.pos[0] - 5, self.pos[1] - 10))

# Bullet class
class Bullet:
    def __init__(self, x, y, target, damage, tower_type):
        self.pos = [x, y]
        self.target = target
        self.damage = damage
        self.speed = 10
        self.color = YELLOW
        self.type = tower_type
        self.radius = 5

    def update(self, zombies):
        if not self.target.alive:
            return True  # Remove if target dead
        dx = self.target.pos[0] - self.pos[0]
        dy = self.target.pos[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist < self.speed:
            self.hit(self.target, zombies)
            return True
        dx /= dist
        dy /= dist
        self.pos[0] += dx * self.speed
        self.pos[1] += dy * self.speed
        return False

    def hit(self, zombie, zombies):
        zombie.health -= self.damage
        HIT_SOUND.play()
        if zombie.health <= 0:
            zombie.alive = False
            DEATH_SOUND.play()
        if self.type == "aoe":
            # Area damage
            for other in zombies:
                if other != zombie and math.hypot(other.pos[0] - zombie.pos[0], other.pos[1] - zombie.pos[1]) < 50:
                    other.health -= self.damage // 2
                    if other.health <= 0:
                        other.alive = False
        elif self.type == "slow":
            zombie.speed *= 0.5  # Slow effect

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)

# Zombie class
class Zombie:
    def __init__(self, zombie_type="normal"):
        self.pos = list(PATH[0])  # Start at beginning of path
        self.path_index = 1
        self.health = 50
        self.max_health = 50
        self.speed = 1.0
        self.color = DARK_GREEN
        self.radius = 15
        self.alive = True
        self.type = zombie_type

        # Zombie variations
        if zombie_type == "fast":
            self.health = 30
            self.speed = 2.0
            self.color = GREEN
            self.radius = 10
        elif zombie_type == "tanky":
            self.health = 100
            self.speed = 0.5
            self.color = RED
            self.radius = 20
        elif zombie_type == "boss":
            self.health = 500
            self.speed = 0.8
            self.color = PURPLE
            self.radius = 30

        self.max_health = self.health

    def update(self):
        if self.path_index < len(PATH):
            target = PATH[self.path_index]
            dx = target[0] - self.pos[0]
            dy = target[1] - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist < self.speed:
                self.pos = list(target)
                self.path_index += 1
            else:
                dx /= dist
                dy /= dist
                self.pos[0] += dx * self.speed
                self.pos[1] += dy * self.speed
        else:
            return True  # Reached end
        return False

    def draw(self, screen):
        # Draw zombie as circle with health bar
        pygame.draw.circle(screen, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)
        health_width = (self.health / self.max_health) * self.radius * 2
        pygame.draw.rect(screen, RED, (self.pos[0] - self.radius, self.pos[1] - self.radius - 5, self.radius * 2, 5))
        pygame.draw.rect(screen, GREEN, (self.pos[0] - self.radius, self.pos[1] - self.radius - 5, health_width, 5))

# Power-up class (rare drop)
class PowerUp:
    def __init__(self, x, y, pu_type="coin"):
        self.pos = (x, y)
        self.type = pu_type
        self.color = YELLOW if pu_type == "coin" else BLUE
        self.radius = 10
        self.active = True

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, self.pos, self.radius)

# Main menu
def main_menu(screen, clock, high_score):
    buttons = [
        Button(300, 200, 200, 50, "Start Game"),
        Button(300, 300, 200, 50, "Settings"),
        Button(300, 400, 200, 50, "Quit")
    ]
    font = pygame.font.SysFont(None, 50)
    title_text = font.render("Zombie Tower Defense", True, WHITE)
    hs_text = font.render(f"High Score: {high_score}", True, YELLOW)

    running = True
    while running:
        screen.fill(BLACK)
        screen.blit(title_text, (200, 100))
        screen.blit(hs_text, (250, 150))
        for button in buttons:
            button.draw(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if buttons[0].is_clicked(pos):
                    return "start"
                elif buttons[1].is_clicked(pos):
                    return "settings"
                elif buttons[2].is_clicked(pos):
                    sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    sys.exit()

        pygame.display.flip()
        clock.tick(FPS)

# Settings menu (placeholder, e.g., sound toggle)
def settings_menu(screen, clock):
    buttons = [
        Button(300, 200, 200, 50, "Sound: ON"),  # Toggle placeholder
        Button(300, 300, 200, 50, "Back")
    ]
    running = True
    while running:
        screen.fill(BLACK)
        for button in buttons:
            button.draw(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if buttons[1].is_clicked(pos):
                    return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return

        pygame.display.flip()
        clock.tick(FPS)

# Pause menu
def pause_menu(screen, clock):
    buttons = [
        Button(300, 200, 200, 50, "Resume"),
        Button(300, 300, 200, 50, "Quit to Menu")
    ]
    font = pygame.font.SysFont(None, 50)
    pause_text = font.render("Paused", True, WHITE)

    running = True
    while running:
        screen.fill(BLACK)
        screen.blit(pause_text, (350, 100))
        for button in buttons:
            button.draw(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if buttons[0].is_clicked(pos):
                    return "resume"
                elif buttons[1].is_clicked(pos):
                    return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                    return "resume"

        pygame.display.flip()
        clock.tick(FPS)

# Game over screen
def game_over(screen, clock, won, score):
    font = pygame.font.SysFont(None, 50)
    result_text = font.render("You Win!" if won else "Game Over", True, GREEN if won else RED)
    score_text = font.render(f"Score: {score}", True, WHITE)
    button = Button(300, 300, 200, 50, "Back to Menu")

    running = True
    while running:
        screen.fill(BLACK)
        screen.blit(result_text, (300, 100))
        screen.blit(score_text, (350, 200))
        button.draw(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if button.is_clicked(pygame.mouse.get_pos()):
                    return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return

        pygame.display.flip()
        clock.tick(FPS)

# Main game loop
def game_loop(screen, clock):
    lives = START_LIVES
    coins = START_COINS
    score = 0
    wave = 1
    zombies = []
    bullets = []
    towers = []
    power_ups = []
    spawning = False
    zombies_to_spawn = 0
    spawn_timer = 0
    spawn_interval = 60  # Frames between spawns
    between_waves = True
    selected_tower_type = None
    tower_buttons = {
        "basic": Button(10, SCREEN_HEIGHT - 50, 100, 40, "Basic (100)"),
        "sniper": Button(120, SCREEN_HEIGHT - 50, 100, 40, "Sniper (200)"),
        "aoe": Button(230, SCREEN_HEIGHT - 50, 100, 40, "AoE (150)"),
        "slow": Button(340, SCREEN_HEIGHT - 50, 100, 40, "Slow (120)"),
    }
    font = pygame.font.SysFont(None, 30)
    upgrade_button = Button(0, 0, 100, 40, "Upgrade (50)", color=GRAY)  # Dynamic position

    running = True
    while running:
        screen.fill(BLACK)

        # Draw path
        pygame.draw.lines(screen, GRAY, False, PATH, PATH_WIDTH)

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "quit"
                if event.key == pygame.K_p:
                    result = pause_menu(screen, clock)
                    if result == "quit":
                        return "quit"
                if event.key == pygame.K_SPACE and between_waves:
                    between_waves = False
                    spawning = True
                    zombies_to_spawn = wave * 5 + 5  # Increase with wave
                    spawn_interval = max(30, 60 - wave * 2)
                    WAVE_SOUND.play()
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                # Check tower buttons
                for t_type, button in tower_buttons.items():
                    if button.is_clicked(pos):
                        selected_tower_type = t_type
                        break
                # Place tower if selected
                if selected_tower_type and pos[1] < SCREEN_HEIGHT - 60:
                    cost = Tower(0, 0, selected_tower_type).cost
                    if coins >= cost:
                        # Check not on path
                        on_path = False
                        for i in range(len(PATH) - 1):
                            p1, p2 = PATH[i], PATH[i+1]
                            if math.hypot(pos[0] - p1[0], pos[1] - p1[1]) < PATH_WIDTH / 2 or math.hypot(pos[0] - p2[0], pos[1] - p2[1]) < PATH_WIDTH / 2:
                                on_path = True
                                break
                        if not on_path:
                            towers.append(Tower(pos[0], pos[1], selected_tower_type))
                            coins -= cost
                            selected_tower_type = None
                # Upgrade tower
                selected_tower = None
                for tower in towers:
                    if math.hypot(pos[0] - tower.pos[0], pos[1] - tower.pos[1]) < tower.size:
                        selected_tower = tower
                        upgrade_button.rect.topleft = (pos[0], pos[1] + 30)
                        upgrade_button.text = f"Upgrade ({tower.upgrade_cost})"
                        upgrade_button.color = BLUE if coins >= tower.upgrade_cost else GRAY
                        break
                if selected_tower and upgrade_button.is_clicked(pos) and coins >= selected_tower.upgrade_cost:
                    coins -= selected_tower.upgrade_cost
                    selected_tower.upgrade()

        # Update game
        if spawning:
            spawn_timer += 1
            if spawn_timer >= spawn_interval and zombies_to_spawn > 0:
                zombie_type = random.choice(["normal", "fast", "tanky"])
                if wave % 5 == 0 and zombies_to_spawn == 1:  # Boss on every 5th wave
                    zombie_type = "boss"
                zombies.append(Zombie(zombie_type))
                zombies_to_spawn -= 1
                spawn_timer = 0
            if zombies_to_spawn <= 0 and not zombies:
                spawning = False
                between_waves = True
                wave += 1
                score += 100 * (wave - 1)  # Bonus for wave survived
                if wave > MAX_WAVES:
                    save_high_score(score)
                    game_over(screen, clock, True, score)
                    return "menu"

        # Update zombies
        to_remove = []
        for zombie in zombies:
            if not zombie.alive:
                to_remove.append(zombie)
                coins += 20  # Earn coins
                score += 10
                COIN_SOUND.play()
                # Rare power-up drop
                if random.random() < 0.1:
                    pu_type = random.choice(["coin", "health"])
                    power_ups.append(PowerUp(zombie.pos[0], zombie.pos[1], pu_type))
            elif zombie.update():
                to_remove.append(zombie)
                lives -= 1 if zombie.type != "boss" else 5
                if lives <= 0:
                    save_high_score(score)
                    game_over(screen, clock, False, score)
                    return "menu"
        for z in to_remove:
            zombies.remove(z)

        # Update towers
        for tower in towers:
            tower.find_target(zombies)
            if tower.cooldown > 0:
                tower.cooldown -= 1
            else:
                tower.shoot(bullets)

        # Update bullets
        to_remove = []
        for bullet in bullets:
            if bullet.update(zombies):
                to_remove.append(bullet)
        for b in to_remove:
            bullets.remove(b)

        # Update power-ups (collect if near base or something, simple: auto-collect for now)
        to_remove = []
        for pu in power_ups:
            # Simple: disappear after time, but add effect
            if random.random() < 0.01:  # Slow disappear
                if pu.type == "coin":
                    coins += 50
                elif pu.type == "health":
                    lives = min(START_LIVES, lives + 5)
                to_remove.append(pu)
        for p in to_remove:
            power_ups.remove(p)

        # Draw everything
        for zombie in zombies:
            zombie.draw(screen)
        for bullet in bullets:
            bullet.draw(screen)
        for tower in towers:
            tower.draw(screen)
        for pu in power_ups:
            pu.draw(screen)

        # Draw UI
        ui_text = font.render(f"Lives: {lives}  Coins: {coins}  Score: {score}  Wave: {wave}/{MAX_WAVES}", True, WHITE)
        screen.blit(ui_text, (10, 10))
        for button in tower_buttons.values():
            button.draw(screen)
        if between_waves:
            wave_text = font.render("Press SPACE to start next wave", True, YELLOW)
            screen.blit(wave_text, (250, SCREEN_HEIGHT - 80))
        if selected_tower:
            upgrade_button.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

# Main program
def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Zombie Tower Defense")
    clock = pygame.time.Clock()
    high_score = load_high_score()

    while True:
        menu_choice = main_menu(screen, clock, high_score)
        if menu_choice == "start":
            result = game_loop(screen, clock)
            if result == "quit":
                continue
        elif menu_choice == "settings":
            settings_menu(screen, clock)
        high_score = load_high_score()  # Reload after game

if __name__ == "__main__":
    main()