import math
import unittest
from unittest.mock import patch

from controller import ControllerState, SerialController, joystick_vector, parse_packet


class InputTests(unittest.TestCase):
    def test_packet_and_button_values(self):
        self.assertEqual(
            parse_packet("LeftXY: 0, 4950    RightXY: 1790, 2000    Buttons: 1, 0\r\n"),
            ControllerState(0, 4950, 1790, 2000, True, False),
        )

    def test_boot_noise_and_partial_packets_are_ignored(self):
        for line in ("ESP-ROM: booting", "LeftXY: 1790, 1790", "LeftXY: 1, 2 RightXY: 3, 4 Buttons: 2, 0"):
            self.assertIsNone(parse_packet(line))

    def test_deadzone_and_asymmetric_endpoints(self):
        self.assertEqual(joystick_vector(1790, 1790), (0, 0))
        self.assertEqual(joystick_vector(1850, 1730), (0, 0))
        self.assertEqual(joystick_vector(0, 1790), (-1, 0))
        self.assertEqual(joystick_vector(4950, 1790), (1, 0))
        self.assertEqual(joystick_vector(1790, 4950, invert_y=True), (0, -1))

    def test_diagonal_speed_is_capped_and_partial_deflection_is_proportional(self):
        self.assertAlmostEqual(math.hypot(*joystick_vector(4950, 4950)), 1)
        self.assertAlmostEqual(joystick_vector(3370, 1790)[0], (0.5 - 0.12) / 0.88)

    def test_fragmented_packets_button_edges_and_stale_input(self):
        class FakeSerial:
            pending = b"LeftXY: 4950, 1790    RightXY: 1790, "

            @property
            def in_waiting(self):
                return len(self.pending)

            def read(self, size):
                result, self.pending = self.pending[:size], self.pending[size:]
                return result

            def close(self):
                pass

        device = FakeSerial()
        with patch("controller.serial.Serial", return_value=device), patch("controller.time.monotonic") as clock:
            clock.return_value = 10.0
            controller = SerialController()
            controller.poll()
            self.assertFalse(controller.connected)
            device.pending = (
                b"1790    Buttons: 1, 0\r\n"
                b"LeftXY: 4950, 1790    RightXY: 1790, 1790    Buttons: 0, 1\n"
            )
            state = controller.poll()
            self.assertTrue(controller.connected)
            self.assertEqual(state.left_x, 4950)
            self.assertFalse(state.button1)
            self.assertTrue(state.button2)
            self.assertTrue(controller.button1_pressed)
            self.assertTrue(controller.button2_pressed)
            controller.poll()
            self.assertFalse(controller.button1_pressed)
            self.assertFalse(controller.button2_pressed)
            # A bouncing release/press must not toggle pause or spend another heal.
            clock.return_value = 10.05
            device.pending = b"LeftXY: 4950, 1790    RightXY: 1790, 1790    Buttons: 1, 0\n"
            controller.poll()
            self.assertFalse(controller.button1_pressed)
            clock.return_value = 10.3
            device.pending = (
                b"LeftXY: 4950, 1790    RightXY: 1790, 1790    Buttons: 0, 0\n"
                b"LeftXY: 4950, 1790    RightXY: 1790, 1790    Buttons: 1, 0\n"
            )
            controller.poll()
            self.assertTrue(controller.button1_pressed)
            clock.return_value = 10.9
            self.assertEqual(controller.poll(), ControllerState())
            self.assertFalse(controller.connected)
            device.pending = b"LeftXY: 0, 1790    RightXY: 1790, 1790    Buttons: 0, 0\n"
            self.assertEqual(controller.poll().left_x, 0)
            self.assertTrue(controller.connected)
            controller.close()


if __name__ == "__main__":
    unittest.main()
