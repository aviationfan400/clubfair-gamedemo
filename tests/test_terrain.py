import unittest

from pygame import Vector2

from arena import Arena, Enemy, ENEMY_RADIUS
from terrain import Boulder, Navigator, move_and_slide, segment_clear


class TerrainTests(unittest.TestCase):
    def test_player_cannot_cross_boulder_even_with_large_movement(self):
        rock = Boulder(Vector2(300, 300), 50)
        result = move_and_slide(Vector2(100, 300), Vector2(500, 0), 12, [rock])
        self.assertLess(result.x, 239)
        self.assertGreaterEqual(result.distance_to(rock.position), 62)

    def test_diagonal_movement_slides_around_rock(self):
        rock = Boulder(Vector2(300, 300), 50)
        start = Vector2(238, 300)
        result = move_and_slide(start, Vector2(20, 20), 12, [rock])
        self.assertGreater(result.y, start.y)
        self.assertGreaterEqual(result.distance_to(rock.position), 62)

    def test_route_segments_clear_multiple_boulders(self):
        rocks = [Boulder(Vector2(300, 260), 65), Boulder(Vector2(475, 340), 70)]
        navigator = Navigator(rocks, ENEMY_RADIUS)
        start, goal = Vector2(100, 300), Vector2(700, 300)
        self.assertFalse(navigator.clear(start, goal))
        path = navigator.route(start, goal)
        self.assertGreater(len(path), 1)
        for point in path:
            self.assertTrue(navigator.clear(start, point))
            start = point
        self.assertEqual(path[-1], goal)

    def test_enemy_detours_and_reaches_player_without_entering_rocks(self):
        for kind in ("red", "orange", "blue"):
            rocks = [Boulder(Vector2(300, 260), 65), Boulder(Vector2(475, 340), 70)]
            arena = Arena(800, 600, boulders=rocks)
            arena.position = Vector2(700, 300)
            arena.shot_timer = arena.spawn_timer = 100
            enemy = Enemy(Vector2(100, 300), kind)
            arena.enemies = [enemy]
            for _ in range(600):
                arena.update(1 / 60)
                for rock in rocks:
                    self.assertGreaterEqual(enemy.position.distance_to(rock.position),
                                            rock.radius + ENEMY_RADIUS - 0.001)
                if not arena.enemies:
                    break
            self.assertFalse(arena.enemies, f"{kind} got stuck on terrain")
            self.assertEqual(arena.health, 14)

    def test_predictive_target_inside_rock_is_projected_to_reachable_ground(self):
        rock = Boulder(Vector2(500, 300), 50)
        navigator = Navigator([rock], ENEMY_RADIUS)
        start = Vector2(200, 300)
        path = navigator.route(start, rock.position)
        self.assertTrue(path)
        for point in path:
            self.assertTrue(segment_clear(start, point, [rock], ENEMY_RADIUS))
            start = point


if __name__ == "__main__":
    unittest.main()
