from dataclasses import dataclass, field
import math
import random
from typing import Optional
from pygame import Vector2
from terrain import Boulder, Navigator, free_position, move_and_slide

CHARACTER_RADIUS = 12
MOVE_SPEED = 320.0
ENEMY_RADIUS = 15
BULLET_RADIUS = 3
BULLET_SPEED = 520.0
SHOT_INTERVAL = 0.25
SPAWN_INTERVAL = 0.9
DIFFICULTY_INTERVAL = 15.0
SPEED_GAIN_PER_STEP = 0.12
SPAWN_RATE_GAIN_PER_STEP = 0.25
BASE_ENEMY_SPEEDS = {"red": 150.0, "orange": 165.0, "blue": 105.0}
PREDICTION_SECONDS = 0.65
AGGRESSION_RANGE = 180.0
AGGRESSION_BOOST = 1.18
BLUE_SPAWN_TIME = 30.0
BLUE_RUSH_RANGE = 260.0
BLUE_RUSH_BOOST = 3.0
BLUE_TRIGGER_RADIUS = 55.0
BLUE_EXPLOSION_RADIUS = 90.0
EXPLOSION_DURATION = 0.3
RED_ARMOR_TIME = 180.0
MAX_BOULDERS = 8


@dataclass(eq=False)
class Enemy:
    position: Vector2
    kind: str
    hits: int = 0
    aggressive: bool = False
    rushing: bool = False
    waypoints: list = field(default_factory=list)
    route_timer: float = 0.0
    route_goal: Optional[Vector2] = None

    @property
    def points(self):
        return {"red": 1, "orange": 2, "blue": 3}[self.kind]

    def target(self, player: Vector2, velocity: Vector2, width: int, height: int):
        target = Vector2(player)
        if self.kind == "orange" and not self.aggressive:
            target += velocity * PREDICTION_SECONDS
        target.x = max(CHARACTER_RADIUS, min(width - CHARACTER_RADIUS, target.x))
        target.y = max(CHARACTER_RADIUS, min(height - CHARACTER_RADIUS, target.y))
        return target


@dataclass(eq=False)
class Bullet:
    position: Vector2
    velocity: Vector2


@dataclass
class Explosion:
    position: Vector2
    remaining: float = EXPLOSION_DURATION


def hit_fraction(start: Vector2, end: Vector2, radius: float) -> Optional[float]:
    # First contact along a segment relative to a circle centered at zero.
    offset = start.length_squared() - radius * radius
    if offset <= 0:
        return 0.0
    delta = end - start
    a = delta.length_squared()
    if a == 0:
        return None
    b = 2 * start.dot(delta)
    discriminant = b * b - 4 * a * offset
    if discriminant < 0:
        return None
    fraction = (-b - math.sqrt(discriminant)) / (2 * a)
    return fraction if 0 <= fraction <= 1 else None


class Arena:
    def __init__(self, width: int, height: int, rng=None, boulders=None):
        self.width, self.height = width, height
        self.rng = rng if rng is not None else random.Random()
        self.position = Vector2(width / 2, height / 2)
        self.velocity = Vector2()
        self.aim_angle = 0.0
        self.health = 15
        self.score = 0
        self.heals = 3
        self.paused = False
        self.enemies = []
        self.bullets = []
        self.explosions = []
        self.shot_timer = 0.0
        self.spawn_timer = 1.0
        self.elapsed = 0.0
        self.boulders = self.generate_boulders() if boulders is None else list(boulders)
        self.navigator = Navigator(self.boulders, ENEMY_RADIUS)

    @property
    def timer_text(self):
        seconds = int(self.elapsed)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    @property
    def difficulty_step(self):
        return int(self.elapsed // DIFFICULTY_INTERVAL)

    @property
    def spawn_interval(self):
        return SPAWN_INTERVAL / (1 + self.difficulty_step * SPAWN_RATE_GAIN_PER_STEP)

    def enemy_speed(self, enemy):
        base = BASE_ENEMY_SPEEDS[enemy.kind]
        speed = base * (1 + self.difficulty_step * SPEED_GAIN_PER_STEP)
        if enemy.kind == "blue" and enemy.rushing:
            return speed * BLUE_RUSH_BOOST
        return speed * AGGRESSION_BOOST if enemy.aggressive else speed

    def explode(self, position, player_position, direct_contact=False):
        """Damage happens once; the remaining explosion lifetime is visual only."""
        self.explosions.append(Explosion(Vector2(position)))
        if direct_contact:
            self.health = max(0, self.health - 2)
        elif position.distance_to(player_position) <= BLUE_EXPLOSION_RADIUS + CHARACTER_RADIUS:
            self.health = max(0, self.health - 1)

    def enemy_health(self, enemy):
        maximum = 2 if enemy.kind == "red" and self.elapsed >= RED_ARMOR_TIME else 1
        return maximum - enemy.hits

    def generate_boulders(self):
        rocks = []
        count = min(MAX_BOULDERS, max(3, self.width * self.height // 150000))
        safe_radius = min(150, min(self.width, self.height) * 0.22)
        for _ in range(300):
            if len(rocks) >= count:
                break
            radius = self.rng.uniform(26, min(58, max(26, min(self.width, self.height) * 0.08)))
            inset = radius + 45
            if self.width <= inset * 2 or self.height <= inset * 2:
                break
            position = Vector2(self.rng.uniform(inset, self.width - inset),
                               self.rng.uniform(inset, self.height - inset))
            if position.distance_to(self.position) < safe_radius + radius:
                continue
            if any(position.distance_to(rock.position) < radius + rock.radius + 65 for rock in rocks):
                continue
            rocks.append(Boulder(position, radius))
        return rocks

    def move_enemy(self, enemy, dt):
        enemy.aggressive = (enemy.kind == "orange"
                            and enemy.position.distance_to(self.position) <= AGGRESSION_RANGE)
        if enemy.kind == "blue" and enemy.position.distance_to(self.position) <= BLUE_RUSH_RANGE:
            enemy.rushing = True
        target = enemy.target(self.position, self.velocity, self.width, self.height)
        target = free_position(target, ENEMY_RADIUS + 2, self.boulders)
        enemy.route_timer -= dt
        if self.navigator.clear(enemy.position, target):
            enemy.waypoints = [target]
        elif (not enemy.waypoints or enemy.route_timer <= 0 or enemy.route_goal is None
              or enemy.route_goal.distance_to(target) > 45):
            enemy.waypoints = self.navigator.route(enemy.position, target)
            enemy.route_goal = Vector2(target)
            enemy.route_timer = 0.4
        budget = self.enemy_speed(enemy) * dt
        while enemy.waypoints and budget > 0:
            delta = enemy.waypoints[0] - enemy.position
            distance = delta.length()
            if distance < 0.1:
                enemy.waypoints.pop(0)
                continue
            step = min(distance, budget)
            enemy.position = move_and_slide(enemy.position, delta / distance * step,
                                            ENEMY_RADIUS, self.boulders)
            budget -= step
            if enemy.position.distance_to(enemy.waypoints[0]) < 0.1:
                enemy.waypoints.pop(0)

    @property
    def game_over(self):
        return self.health <= 0

    def spawn_enemy(self):
        margin = ENEMY_RADIUS + 24
        edge = self.rng.randrange(4)
        if edge < 2:
            position = Vector2(-margin if edge == 0 else self.width + margin,
                               self.rng.uniform(0, self.height))
        else:
            position = Vector2(self.rng.uniform(0, self.width),
                               -margin if edge == 2 else self.height + margin)
        roll = self.rng.random()
        if self.elapsed >= BLUE_SPAWN_TIME:
            kind = "blue" if roll < 0.25 else "orange" if roll < 0.55 else "red"
        else:
            kind = "orange" if roll < 0.35 else "red"
        self.enemies.append(Enemy(position, kind))

    def update(self, dt, move=(0, 0), aim=(0, 0), pause_pressed=False,
               heal_pressed=False, connected=True):
        if self.game_over:
            return
        if pause_pressed:
            self.paused = not self.paused
        if self.paused or not connected:
            return
        previous_spawn_interval = self.spawn_interval
        self.elapsed += dt
        # Keep progress toward the next spawn when a difficulty step speeds it up.
        self.spawn_timer *= self.spawn_interval / previous_spawn_interval
        for explosion in self.explosions:
            explosion.remaining -= dt
        self.explosions = [effect for effect in self.explosions if effect.remaining > 0]
        if heal_pressed and self.heals > 0:
            self.heals -= 1
            self.health += 2

        previous_position = Vector2(self.position)
        self.position = move_and_slide(self.position, Vector2(move) * MOVE_SPEED * dt,
                                       CHARACTER_RADIUS, self.boulders, (self.width, self.height))
        # Actual movement accounts for the player pressing into a map boundary.
        self.velocity = (self.position - previous_position) / dt if dt > 0 else Vector2()
        if Vector2(aim).length_squared() > 0:
            self.aim_angle = math.atan2(aim[1], aim[0])

        self.spawn_timer -= dt
        while self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer += self.spawn_interval

        self.shot_timer -= dt
        while self.shot_timer <= 0:
            direction = Vector2(math.cos(self.aim_angle), math.sin(self.aim_angle))
            self.bullets.append(Bullet(self.position + direction * (CHARACTER_RADIUS + BULLET_RADIUS),
                                       direction * BULLET_SPEED))
            self.shot_timer += SHOT_INTERVAL

        previous_enemies = {}
        for enemy in self.enemies:
            previous_enemies[enemy] = Vector2(enemy.position)
            self.move_enemy(enemy, dt)

        remaining_bullets = []
        for bullet in self.bullets:
            previous = Vector2(bullet.position)
            bullet.position += bullet.velocity * dt
            first_hit, first_fraction = None, float("inf")
            rock_fraction = float("inf")
            for rock in self.boulders:
                fraction = hit_fraction(previous - rock.position, bullet.position - rock.position,
                                        rock.radius + BULLET_RADIUS)
                if fraction is not None:
                    rock_fraction = min(rock_fraction, fraction)
            for enemy in self.enemies:
                fraction = hit_fraction(previous - previous_enemies[enemy],
                                        bullet.position - enemy.position,
                                        BULLET_RADIUS + ENEMY_RADIUS)
                if fraction is not None and fraction < first_fraction:
                    first_hit, first_fraction = enemy, fraction
            if rock_fraction <= first_fraction and rock_fraction != float("inf"):
                continue
            if first_hit is not None:
                first_hit.hits += 1
                if self.enemy_health(first_hit) <= 0:
                    self.enemies.remove(first_hit)
                    self.score += first_hit.points
            elif (-BULLET_RADIUS <= bullet.position.x <= self.width + BULLET_RADIUS
                  and -BULLET_RADIUS <= bullet.position.y <= self.height + BULLET_RADIUS):
                remaining_bullets.append(bullet)
        self.bullets = remaining_bullets

        remaining_enemies = []
        for enemy in self.enemies:
            contact = hit_fraction(previous_enemies[enemy] - previous_position,
                                   enemy.position - self.position,
                                   ENEMY_RADIUS + CHARACTER_RADIUS)
            if enemy.kind == "blue":
                proximity = hit_fraction(previous_enemies[enemy] - previous_position,
                                         enemy.position - self.position, BLUE_TRIGGER_RADIUS)
                # Direct contact wins over the proximity blast, never stacking damage.
                fraction = contact if contact is not None else proximity
                if fraction is not None:
                    blast_position = previous_enemies[enemy].lerp(enemy.position, fraction)
                    player_at_blast = previous_position.lerp(self.position, fraction)
                    self.explode(blast_position, player_at_blast, direct_contact=contact is not None)
                    continue
            if contact is not None:
                # Consume the touching enemy so one contact costs one health.
                self.health = max(0, self.health - 1)
            else:
                remaining_enemies.append(enemy)
        self.enemies = remaining_enemies
