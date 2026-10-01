import random
import sys
import unittest
from unittest.mock import patch

from pygame import Vector2

from arena import (Arena, Bullet, Enemy, ENEMY_RADIUS, PREDICTION_SECONDS,
                   SHOT_INTERVAL, AGGRESSION_BOOST, MAX_BOULDERS,
                   BASE_ENEMY_SPEEDS, BLUE_RUSH_BOOST, BLUE_EXPLOSION_RADIUS)
from terrain import Boulder
from controller import joystick_vector
from game import read_arguments


class ArenaTests(unittest.TestCase):
    def arena(self):
        arena = Arena(800, 600, random.Random(10), boulders=[])
        arena.shot_timer = 100
        arena.spawn_timer = 100
        return arena

    def test_both_sticks_invert_y_by_default(self):
        with patch.object(sys, "argv", ["game.py"]):
            args = read_arguments()
        for inverted in (args.invert_left_y, args.invert_right_y):
            self.assertLess(joystick_vector(1790, 4950, invert_y=inverted)[1], 0)
        with patch.object(sys, "argv", ["game.py", "--no-invert-left-y"]):
            self.assertFalse(read_arguments().invert_left_y)

    def test_starting_values_and_heals_are_limited(self):
        arena = self.arena()
        self.assertEqual((arena.health, arena.score, arena.heals), (15, 0, 3))
        for _ in range(4):
            arena.update(0.01, heal_pressed=True)
        self.assertEqual((arena.health, arena.heals), (21, 0))

    def test_pause_freezes_everything_until_pressed_again(self):
        arena = self.arena()
        arena.enemies.append(Enemy(Vector2(50, 50), "orange"))
        arena.bullets.append(Bullet(Vector2(100, 100), Vector2(500, 0)))
        before = (Vector2(arena.position), Vector2(arena.enemies[0].position),
                  Vector2(arena.bullets[0].position), arena.shot_timer, arena.spawn_timer)
        for pause in (True, False, False):
            arena.update(0.05, (1, 0), (0, -1), pause_pressed=pause, heal_pressed=True)
        self.assertTrue(arena.paused)
        self.assertEqual(before, (arena.position, arena.enemies[0].position,
                                 arena.bullets[0].position, arena.shot_timer, arena.spawn_timer))
        self.assertEqual((arena.health, arena.heals, arena.score, arena.aim_angle), (15, 3, 0, 0))
        arena.update(0.05, (1, 0), pause_pressed=True)
        self.assertFalse(arena.paused)
        self.assertGreater(arena.position.x, before[0].x)

    def test_disconnect_and_game_over_freeze_simulation(self):
        arena = self.arena()
        start = Vector2(arena.position)
        arena.update(0.1, (1, 0), heal_pressed=True, connected=False)
        self.assertEqual(arena.position, start)
        self.assertEqual((arena.health, arena.heals, arena.spawn_timer), (15, 3, 100))
        arena.health = 0
        arena.update(0.1, (1, 0), heal_pressed=True)
        self.assertTrue(arena.game_over)
        self.assertEqual(arena.position, start)
        self.assertEqual((arena.health, arena.heals), (0, 3))

    def test_red_chases_and_orange_predicts(self):
        arena = self.arena()
        red = Enemy(Vector2(100, 100), "red")
        orange = Enemy(Vector2(100, 100), "orange")
        velocity = Vector2(100, 0)
        self.assertEqual(red.target(arena.position, velocity, 800, 600), arena.position)
        self.assertEqual(orange.target(arena.position, velocity, 800, 600),
                         arena.position + velocity * PREDICTION_SECONDS)
        self.assertEqual(orange.target(arena.position, Vector2(), 800, 600), arena.position)
        arena.enemies = [red, orange]
        arena.update(0.05, move=(1, 0))
        red_heading = red.position - Vector2(100, 100)
        orange_heading = orange.position - Vector2(100, 100)
        self.assertLess(orange_heading.y / orange_heading.x, red_heading.y / red_heading.x)

    def test_prediction_uses_actual_velocity_at_wall(self):
        arena = self.arena()
        arena.position.x = 788
        arena.update(0.05, (1, 0))
        self.assertEqual(arena.velocity, Vector2())

    def test_enemies_spawn_fully_outside_each_edge(self):
        arena = self.arena()
        edges = set()
        for _ in range(100):
            arena.spawn_enemy()
            p = arena.enemies[-1].position
            outside = (p.x + ENEMY_RADIUS < 0, p.x - ENEMY_RADIUS > 800,
                       p.y + ENEMY_RADIUS < 0, p.y - ENEMY_RADIUS > 600)
            self.assertTrue(any(outside))
            edges.update(i for i, value in enumerate(outside) if value)
        self.assertEqual(edges, {0, 1, 2, 3})

    def test_bullets_hit_once_and_award_correct_points(self):
        for kind, score in (("red", 1), ("orange", 2)):
            arena = self.arena()
            arena.enemies = [Enemy(Vector2(200, 100), kind)]
            arena.bullets = [Bullet(Vector2(100, 100), Vector2(4000, 0))]
            arena.update(0.05)
            self.assertEqual(arena.score, score)
            self.assertFalse(arena.enemies)
            self.assertFalse(arena.bullets)

    def test_bullet_hits_nearest_enemy_even_if_list_is_reversed(self):
        arena = self.arena()
        near = Enemy(Vector2(170, 100), "red")
        far = Enemy(Vector2(250, 100), "orange")
        arena.enemies = [far, near]
        arena.bullets = [Bullet(Vector2(100, 100), Vector2(4000, 0))]
        arena.update(0.05)
        self.assertEqual(arena.enemies, [far])
        self.assertEqual(arena.score, 1)

    def test_each_contact_costs_one_health_without_score(self):
        arena = self.arena()
        arena.enemies = [Enemy(Vector2(arena.position), kind) for kind in ("red", "orange")]
        arena.update(0.01)
        self.assertEqual((arena.health, arena.score), (13, 0))
        self.assertFalse(arena.enemies)
        arena.update(0.01)
        self.assertEqual(arena.health, 13)

    def test_automatic_shots_keep_original_direction(self):
        arena = self.arena()
        arena.shot_timer = 0
        arena.update(0.01, aim=(0, -1))
        self.assertEqual(len(arena.bullets), 1)
        first = arena.bullets[0]
        self.assertAlmostEqual(first.velocity.x, 0)
        self.assertLess(first.velocity.y, 0)
        arena.update(SHOT_INTERVAL, aim=(1, 0))
        self.assertEqual(len(arena.bullets), 2)
        self.assertLess(first.velocity.y, 0)
        self.assertGreater(arena.bullets[1].velocity.x, 0)
        arena.update(0.01)
        self.assertEqual(arena.aim_angle, 0)

    def test_offscreen_bullets_are_removed(self):
        arena = self.arena()
        arena.bullets = [Bullet(Vector2(800, 200), Vector2(520, 0))]
        arena.update(0.05)
        self.assertFalse(arena.bullets)

    def test_orange_aggression_switches_target_and_speed_only_when_near(self):
        arena = self.arena()
        enemy = Enemy(Vector2(300, 300), "orange")
        arena.velocity = Vector2(0, 100)
        arena.move_enemy(enemy, 0)
        self.assertTrue(enemy.aggressive)
        self.assertEqual(enemy.target(arena.position, arena.velocity, 800, 600), arena.position)
        self.assertAlmostEqual(arena.enemy_speed(enemy), 165 * AGGRESSION_BOOST)
        enemy.position.x = 100
        arena.move_enemy(enemy, 0)
        self.assertFalse(enemy.aggressive)
        self.assertGreater(enemy.target(arena.position, arena.velocity, 800, 600).y, arena.position.y)
        self.assertEqual(arena.enemy_speed(enemy), 165)

    def test_clock_and_fifteen_second_difficulty_pause_disconnect_and_restart(self):
        arena = self.arena()
        red = Enemy(Vector2(), "red")
        arena.elapsed = 14.9
        self.assertEqual(arena.timer_text, "00:14")
        self.assertEqual(arena.enemy_speed(red), 150)
        arena.update(0.2)
        self.assertEqual(arena.timer_text, "00:15")
        self.assertAlmostEqual(arena.enemy_speed(red), 150 * 1.12)
        elapsed = arena.elapsed
        arena.update(0.1, pause_pressed=True)
        arena.update(1)
        self.assertEqual(arena.elapsed, elapsed)
        arena.update(1, pause_pressed=True, connected=False)
        self.assertEqual(arena.elapsed, elapsed)
        arena.health = 0
        arena.update(1)
        self.assertEqual(arena.elapsed, elapsed)
        self.assertEqual(self.arena().timer_text, "00:00")

    def test_existing_and_new_red_enemies_need_two_hits_at_three_minutes(self):
        arena = self.arena()
        existing = Enemy(Vector2(200, 100), "red")
        arena.enemies = [existing]
        arena.elapsed = 179.99
        self.assertEqual(arena.enemy_health(existing), 1)
        arena.update(0.02)
        self.assertEqual(arena.timer_text, "03:00")
        self.assertEqual(arena.enemy_health(existing), 2)
        self.assertEqual(arena.enemy_health(Enemy(Vector2(), "red")), 2)
        self.assertEqual(arena.enemy_health(Enemy(Vector2(), "orange")), 1)
        for hit in range(2):
            arena.bullets = [Bullet(Vector2(existing.position), Vector2())]
            arena.update(0.001)
            self.assertEqual(arena.score, hit)
            self.assertEqual(len(arena.enemies), 1 - hit)
            self.assertFalse(arena.bullets)

    def test_terrain_generation_caps_count_and_leaves_center_and_corridors_clear(self):
        for width, height in ((800, 600), (1280, 720), (1920, 1080)):
            arena = Arena(width, height, random.Random(10))
            self.assertGreater(len(arena.boulders), 0)
            self.assertLessEqual(len(arena.boulders), MAX_BOULDERS)
            safe_radius = min(150, min(width, height) * 0.22)
            for i, rock in enumerate(arena.boulders):
                self.assertGreaterEqual(rock.position.distance_to(arena.position) - rock.radius, safe_radius)
                self.assertGreater(rock.position.x - rock.radius, 0)
                self.assertLess(rock.position.x + rock.radius, width)
                self.assertGreater(rock.position.y - rock.radius, 0)
                self.assertLess(rock.position.y + rock.radius, height)
                for other in arena.boulders[:i]:
                    self.assertGreaterEqual(rock.position.distance_to(other.position),
                                            rock.radius + other.radius + 65)

    def test_boulders_block_bullets_before_enemies(self):
        rock = Boulder(Vector2(200, 100), 30)
        arena = Arena(800, 600, boulders=[rock])
        arena.shot_timer = arena.spawn_timer = 100
        arena.enemies = [Enemy(Vector2(280, 100), "red")]
        arena.bullets = [Bullet(Vector2(100, 100), Vector2(4000, 0))]
        arena.update(0.05)
        self.assertEqual(arena.score, 0)
        self.assertEqual(len(arena.enemies), 1)
        self.assertFalse(arena.bullets)

    def test_speed_and_spawn_rate_increase_at_each_fifteen_second_boundary(self):
        arena = self.arena()
        for elapsed, steps in ((14.99, 0), (15, 1), (29.99, 1), (30, 2), (45, 3), (60, 4)):
            arena.elapsed = elapsed
            self.assertEqual(arena.difficulty_step, steps)
            for kind, base in BASE_ENEMY_SPEEDS.items():
                self.assertAlmostEqual(arena.enemy_speed(Enemy(Vector2(), kind)), base * (1 + steps * .12))
            self.assertAlmostEqual(arena.spawn_interval, .9 / (1 + steps * .25))

    def test_spawn_count_increases_with_difficulty_and_countdown_scales(self):
        counts = []
        for elapsed in (0, 90):
            arena = self.arena()
            arena.elapsed = elapsed
            arena.spawn_timer = arena.spawn_interval
            with patch.object(arena, "spawn_enemy") as spawn:
                for _ in range(200):
                    arena.update(.05)
                counts.append(spawn.call_count)
        self.assertGreater(counts[1], counts[0])
        arena = self.arena()
        arena.elapsed = 14.99
        arena.spawn_timer = .45
        arena.update(.02)
        self.assertAlmostEqual(arena.spawn_timer, .45 / 1.25 - .02)

    def test_blue_enemies_only_spawn_from_thirty_seconds(self):
        arena = self.arena()
        arena.elapsed = 29.99
        for _ in range(200):
            arena.spawn_enemy()
        self.assertNotIn("blue", {enemy.kind for enemy in arena.enemies})
        arena.enemies.clear()
        arena.elapsed = 30
        for _ in range(200):
            arena.spawn_enemy()
        self.assertEqual({enemy.kind for enemy in arena.enemies}, {"red", "orange", "blue"})

    def test_blue_rush_starts_at_medium_range_and_stays_active(self):
        arena = self.arena()
        enemy = Enemy(Vector2(100, 300), "blue")
        arena.move_enemy(enemy, 0)
        self.assertFalse(enemy.rushing)
        self.assertEqual(arena.enemy_speed(enemy), 105)
        enemy.position.x = 200
        arena.move_enemy(enemy, 0)
        self.assertTrue(enemy.rushing)
        self.assertEqual(arena.enemy_speed(enemy), 105 * BLUE_RUSH_BOOST)
        enemy.position.x = 100
        arena.move_enemy(enemy, 0)
        self.assertTrue(enemy.rushing)
        self.assertEqual(enemy.target(arena.position, Vector2(100, 100), 800, 600), arena.position)

    def test_blue_proximity_blast_damages_once_and_awards_no_score(self):
        arena = self.arena()
        arena.enemies = [Enemy(arena.position + Vector2(50, 0), "blue")]
        arena.update(.01)
        self.assertEqual((arena.health, arena.score), (14, 0))
        self.assertFalse(arena.enemies)
        self.assertEqual(len(arena.explosions), 1)
        arena.update(.1)
        self.assertEqual(arena.health, 14)
        arena.update(.21)
        self.assertFalse(arena.explosions)

    def test_blue_direct_contact_deals_two_damage_without_stacking(self):
        for offset, move in ((20, (0, 0)), (40, (1, 0))):
            arena = self.arena()
            arena.enemies = [Enemy(arena.position + Vector2(offset, 0), "blue")]
            arena.update(.05, move)
            self.assertEqual((arena.health, arena.score), (13, 0))
            self.assertEqual(len(arena.explosions), 1)
            self.assertFalse(arena.enemies)

    def test_blast_only_hurts_players_in_radius(self):
        arena = self.arena()
        arena.explode(arena.position + Vector2(BLUE_EXPLOSION_RADIUS + 30, 0), arena.position)
        self.assertEqual(arena.health, 15)
        arena.explode(arena.position + Vector2(BLUE_EXPLOSION_RADIUS - 1, 0), arena.position)
        self.assertEqual(arena.health, 14)

    def test_bullet_can_destroy_blue_before_it_explodes(self):
        arena = self.arena()
        enemy = Enemy(arena.position + Vector2(50, 0), "blue")
        arena.enemies = [enemy]
        arena.bullets = [Bullet(Vector2(enemy.position), Vector2())]
        arena.update(.001)
        self.assertEqual((arena.health, arena.score), (15, 3))
        self.assertFalse(arena.enemies)
        self.assertFalse(arena.explosions)

    def test_pause_freezes_blue_rush_and_explosion_effects(self):
        arena = self.arena()
        enemy = Enemy(arena.position + Vector2(120, 0), "blue", rushing=True)
        arena.enemies = [enemy]
        arena.explode(Vector2(0, 0), arena.position)
        previous_position = Vector2(enemy.position)
        previous_lifetime = arena.explosions[0].remaining
        arena.update(.1, pause_pressed=True)
        arena.update(.5)
        self.assertEqual(enemy.position, previous_position)
        self.assertEqual(arena.explosions[0].remaining, previous_lifetime)
        self.assertEqual(arena.elapsed, 0)


if __name__ == "__main__":
    unittest.main()
