import unittest
from unittest.mock import patch

from arena import Arena, Enemy, Explosion
from game import GameSession
from pygame import Vector2


class SessionTests(unittest.TestCase):
    def setUp(self):
        factory = patch("game.Arena", side_effect=lambda w, h: Arena(w, h, boulders=[]))
        factory.start()
        self.addCleanup(factory.stop)
        self.session = GameSession(800, 600)

    def test_intro_waits_for_right_button_and_keeps_game_frozen(self):
        arena = self.session.arena
        start = Vector2(arena.position)
        for _ in range(100):
            self.session.update(.05, move=(1, 0), aim=(0, -1), pause_pressed=True)
        self.assertFalse(self.session.started)
        self.assertEqual(arena.position, start)
        self.assertEqual((arena.elapsed, arena.health, arena.heals, arena.paused), (0, 15, 3, False))
        self.assertFalse(arena.enemies)
        self.assertFalse(arena.bullets)

    def test_start_consumes_button_without_healing_and_following_press_heals(self):
        self.session.update(.05, right_pressed=True)
        self.assertTrue(self.session.started)
        self.assertEqual((self.session.arena.health, self.session.arena.heals), (15, 3))
        self.assertEqual(self.session.arena.elapsed, 0)
        self.session.update(.05)
        self.assertGreater(self.session.arena.elapsed, 0)
        self.assertEqual(self.session.arena.heals, 3)
        self.session.update(.05, right_pressed=True)
        self.assertEqual((self.session.arena.health, self.session.arena.heals), (17, 2))

    def test_disconnected_right_press_cannot_start_or_restart(self):
        self.session.update(.05, right_pressed=True, connected=False)
        self.assertFalse(self.session.started)
        self.session.update(.05, right_pressed=True)
        self.session.arena.health = 0
        self.session.update(.05, right_pressed=True, connected=False)
        self.assertTrue(self.session.arena.game_over)

    def test_restart_returns_to_intro_and_needs_another_press_to_start(self):
        self.session.update(.05, right_pressed=True)
        old = self.session.arena
        old.health, old.score, old.heals, old.elapsed = 0, 42, 0, 240
        old.enemies.append(Enemy(Vector2(100, 100), "blue"))
        old.explosions.append(Explosion(Vector2(200, 200)))
        self.session.update(.05, pause_pressed=True)
        self.assertIs(self.session.arena, old)
        self.session.update(.05, right_pressed=True)
        fresh = self.session.arena
        self.assertIsNot(fresh, old)
        self.assertFalse(self.session.started)
        self.assertEqual((fresh.health, fresh.score, fresh.heals, fresh.elapsed), (15, 0, 3, 0))
        self.assertFalse(fresh.enemies)
        self.assertFalse(fresh.explosions)
        self.assertFalse(fresh.paused)
        for _ in range(100):
            self.session.update(.05, move=(1, 0))
        self.assertFalse(self.session.started)
        self.assertEqual(fresh.elapsed, 0)
        self.assertFalse(fresh.bullets)
        self.assertFalse(fresh.enemies)
        self.session.update(.05, right_pressed=True)
        self.assertTrue(self.session.started)
        self.assertIs(self.session.arena, fresh)
        self.assertEqual((fresh.health, fresh.heals, fresh.elapsed), (15, 3, 0))
        self.session.update(.05)
        self.assertGreater(fresh.elapsed, 0)
        self.assertEqual(fresh.heals, 3)


if __name__ == "__main__":
    unittest.main()
