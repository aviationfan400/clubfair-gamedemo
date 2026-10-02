import argparse
import math
import pygame
from controller import SerialController, joystick_vector
from arena import (Arena, BULLET_RADIUS, CHARACTER_RADIUS, ENEMY_RADIUS,
                   BLUE_EXPLOSION_RADIUS, EXPLOSION_DURATION)

class GameSession:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.arena = Arena(width, height)
        self.started = False

    def update(self, dt, move=(0, 0), aim=(0, 0), pause_pressed=False,
               right_pressed=False, connected=True):
        if not self.started or self.arena.game_over:
            if connected and right_pressed:
                if self.arena.game_over:
                    self.arena = Arena(self.width, self.height)
                    self.started = False
                else:
                    self.started = True
            # Starting/restarting consumes this press; it must not spend a heal.
            return
        self.arena.update(dt, move, aim, pause_pressed, right_pressed, connected)


def read_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--center", type=float, default=1790)
    parser.add_argument("--maximum", type=float, default=4950)
    parser.add_argument("--deadzone", type=float, default=0.12)
    parser.add_argument("--invert-left-y", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--invert-right-y", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--windowed", action="store_true", help="Use a 1280 x 720 window")


def draw_character(screen: pygame.Surface, position: pygame.Vector2, angle: float) -> None:
    white = (255, 255, 255)
    direction = pygame.Vector2(math.cos(angle), math.sin(angle))
    perpendicular = pygame.Vector2(-direction.y, direction.x)
    start = position + direction * (CHARACTER_RADIUS + 7)
    tip = position + direction * (CHARACTER_RADIUS + 39)
    base = tip - direction * 12
    pygame.draw.circle(screen, white, (round(position.x), round(position.y)), CHARACTER_RADIUS)
    pygame.draw.line(screen, white, start, base, 3)
    pygame.draw.polygon(screen, white, [tip, base + perpendicular * 7, base - perpendicular * 7])


def draw_intro(screen, font, title_font, connected):
    screen.fill((0, 0, 0))
    card = pygame.Surface((760, 500))
    card.fill((0, 0, 0))

    def centered(text, selected_font, y, color=(255, 255, 255)):
        label = selected_font.render(text, True, color)
        card.blit(label, label.get_rect(center=(380, y)))

    centered("CODING CLUB DEMO GAME", title_font, 55)
    centered("CONTROLS", font, 106, (170, 170, 180))
    pygame.draw.line(card, (65, 65, 75), (60, 130), (700, 130))
    rows = [
        ("Left joystick", "Move"),
        ("Right joystick", "Aim"),
        ("Left button", "Pause / resume"),
        ("Right button", "Heal +2 health (3 uses)"),
        ("Esc key", "Quit"),
    ]
    for i, (control, action) in enumerate(rows):
        y = 153 + i * 36
        card.blit(font.render(control, True, (170, 170, 180)), (85, y))
        card.blit(font.render(action, True, (255, 255, 255)), (335, y))
    centered("Press the RIGHT button to begin", font, 407, (110, 205, 255))
    status = "Controller connected" if True else "Waiting for connection"
    centered(status, font, 450, (170, 170, 180))
    scale = min(1.0, (screen.get_width() - 24) / 760, (screen.get_height() - 24) / 500)
    if scale < 1:
        card = pygame.transform.smoothscale(card, (max(1, int(760 * scale)), max(1, int(500 * scale))))
    screen.blit(card, card.get_rect(center=screen.get_rect().center))


def draw_game(screen, arena, font, title_font, connected):
    screen.fill((0, 0, 0))
    for rock in arena.boulders:
        center = (round(rock.position.x), round(rock.position.y))
        pygame.draw.circle(screen, (85, 85, 90), center, round(rock.radius))
        pygame.draw.circle(screen, (120, 120, 125), center, round(rock.radius), 2)
    for enemy in arena.enemies:
        color = {"red": (240, 55, 55), "orange": (255, 155, 35), "blue": (45, 135, 255)}[enemy.kind]
        if enemy.rushing and int(arena.elapsed / 0.12) % 2:
            color = (185, 225, 255)
        pygame.draw.circle(screen, color, (round(enemy.position.x), round(enemy.position.y)), ENEMY_RADIUS)
        if enemy.aggressive:
            pygame.draw.circle(screen, (255, 215, 100),
                               (round(enemy.position.x), round(enemy.position.y)), ENEMY_RADIUS + 3, 2)
        if enemy.rushing:
            pygame.draw.circle(screen, (110, 190, 255),
                               (round(enemy.position.x), round(enemy.position.y)), ENEMY_RADIUS + 3, 2)
        if enemy.kind == "red" and arena.enemy_health(enemy) == 2:
            pygame.draw.circle(screen, (255, 170, 170),
                               (round(enemy.position.x), round(enemy.position.y)), 5, 2)
    for bullet in arena.bullets:
        pygame.draw.circle(screen, (255, 255, 255),
                           (round(bullet.position.x), round(bullet.position.y)), BULLET_RADIUS)
    for explosion in arena.explosions:
        strength = max(0, explosion.remaining / EXPLOSION_DURATION)
        radius = round(BLUE_EXPLOSION_RADIUS)
        effect = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        center = (radius + 2, radius + 2)
        pygame.draw.circle(effect, (55, 150, 255, round(70 * strength)), center, radius)
        pygame.draw.circle(effect, (160, 220, 255, round(255 * strength)), center, radius, 3)
        screen.blit(effect, (round(explosion.position.x) - radius - 2,
                             round(explosion.position.y) - radius - 2))
    draw_character(screen, arena.position, arena.aim_angle)

    hud = font.render(f"Health: {arena.health}     Score: {arena.score}     Heals: {arena.heals}     Time: {arena.timer_text}",
                      True, (255, 255, 255))
    pygame.draw.rect(screen, (0, 0, 0), (12, 12, hud.get_width() + 16, hud.get_height() + 16))
    screen.blit(hud, (20, 20))
    message, hint = "", ""
    if arena.game_over:
        message, hint = "GAME OVER", f"Score: {arena.score}   |   Right button: restart   |   Esc: quit"
    elif arena.paused:
        message, hint = "PAUSED", "Press the left button to resume"
    elif not connected:
        message, hint = "WAITING FOR CONTROLLER", "Check USB and close Arduino Serial Monitor"
    if message:
        title = title_font.render(message, True, (255, 255, 255))
        subtitle = font.render(hint, True, (190, 190, 190))
        panel = pygame.Rect(0, 0, max(title.get_width(), subtitle.get_width()) + 48, 120)
        panel.center = screen.get_rect().center
        pygame.draw.rect(screen, (15, 15, 15), panel)
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.centery - 20)))
        screen.blit(subtitle, subtitle.get_rect(center=(panel.centerx, panel.centery + 26)))


def main() -> None:
    args = read_arguments()
    pygame.display.init()
    pygame.font.init()
    controller = SerialController(args.port, args.baud)
    try:
        flags = 0 if args.windowed else pygame.FULLSCREEN
        size = (1280, 720) if args.windowed else (0, 0)
        screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("ESP32 Survival — Esc to exit")
        pygame.mouse.set_visible(False)
        width, height = screen.get_size()
        session = GameSession(width, height)
        font = pygame.font.Font(None, 30)
        title_font = pygame.font.Font(None, 48)
        clock = pygame.time.Clock()
        running = True
        print("Left stick: move. Right stick: aim. Button 1: pause. Button 2: start/heal/return to intro. Esc: exit.", flush=True)

        while running:
            dt = min(clock.tick(60) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    running = False

            inputs = controller.poll()
            move, aim = (0.0, 0.0), (0.0, 0.0)
            if controller.connected:
                move = joystick_vector(
                    inputs.left_x, inputs.left_y, args.center, args.maximum,
                    args.deadzone, args.invert_left_y,
                )
                aim = joystick_vector(
                    inputs.right_x, inputs.right_y, args.center, args.maximum,
                    args.deadzone, args.invert_right_y,
                )
            session.update(dt, move, aim, controller.button1_pressed,
                           controller.button2_pressed, controller.connected)
            if session.started:
                draw_game(screen, session.arena, font, title_font, controller.connected)
            else:
                draw_intro(screen, font, title_font, controller.connected)
            pygame.display.flip()
    finally:
        controller.close()
        pygame.quit()


if __name__ == "__main__":
    main()
