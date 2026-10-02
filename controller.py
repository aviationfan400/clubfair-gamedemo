"""ESP32 packet parsing, joystick calibration, and nonblocking serial input."""

from dataclasses import dataclass
import math
import re
import time
from typing import Optional, Tuple

import serial


PACKET = re.compile(
    r"LeftXY:\s*(\d+)\s*,\s*(\d+)\s+"
    r"RightXY:\s*(\d+)\s*,\s*(\d+)\s+"
    r"Buttons:\s*([01])\s*,\s*([01])"
)


@dataclass(frozen=True)
class ControllerState:
    left_x: int = 1790
    left_y: int = 1790
    right_x: int = 1790
    right_y: int = 1790
    button1: bool = False
    button2: bool = False


def parse_packet(line: str) -> Optional[ControllerState]:
    """Ignore boot messages and incomplete/malformed packets."""
    match = PACKET.fullmatch(line.strip())
    if match is None:
        return None
    lx, ly, rx, ry, b1, b2 = map(int, match.groups())
    return ControllerState(lx, ly, rx, ry, bool(b1), bool(b2))


def joystick_vector(
    x: int,
    y: int,
    center: float = 1790,
    maximum: float = 4950,
    deadzone: float = 0.12,
    invert_y: bool = False,
) -> Tuple[float, float]:
    # Normalize each side of the off-center range, then apply a radial dead zone.
    def axis(raw: int) -> float:
        span = center if raw < center else maximum - center
        return max(-1.0, min(1.0, (raw - center) / span))

    dx, dy = axis(x), axis(y)
    if invert_y:
        dy = -dy
    length = math.hypot(dx, dy)
    if length <= deadzone:
        return 0.0, 0.0
    strength = (min(length, 1.0) - deadzone) / (1.0 - deadzone)
    return dx / length * strength, dy / length * strength


class SerialController:
    # Read without blocking rendering; reconnect and stop motion on stale data.

    def __init__(self, port: str = "COM3", baud: int = 115200):
        self.port = port
        self.baud = baud
        self.state = ControllerState()
        self.button1_pressed = False
        self.button2_pressed = False
        self.connected = False
        self._serial = None
        self._buffer = bytearray()
        self._last_packet = None
        self._retry_at = 0.0
        self._status = ""
        self._last_button1_press = float("-inf")
        self._last_button2_press = float("-inf")

    def _report(self, message: str) -> None:
        if message != self._status:
            print(message, flush=True)
            self._status = message

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except (serial.SerialException, OSError):
                pass
        self._serial = None
        self.connected = False

    def poll(self) -> ControllerState:
        # Pressed flags indicate rising edges collected since the previous poll.
        self.button1_pressed = False
        self.button2_pressed = False
        now = time.monotonic()
        if self._serial is None and now >= self._retry_at:
            self._retry_at = now + 2.0
            try:
                self._serial = serial.Serial(self.port, self.baud, timeout=0)
                self._buffer.clear()
                self._last_packet = None
                self._report(f"Opened {self.port} at {self.baud} baud; waiting for ESP32 data.")
            except (serial.SerialException, OSError) as error:
                self._report(f"Waiting for {self.port}: {error}")

        if self._serial is not None:
            try:
                self._buffer.extend(self._serial.read(min(self._serial.in_waiting, 8192)))
                while b"\n" in self._buffer:
                    line, _, remaining = self._buffer.partition(b"\n")
                    self._buffer = bytearray(remaining)
                    packet = parse_packet(line.decode("ascii", errors="replace"))
                    if packet is None:
                        continue
                    # Suppress switch bounce while retaining momentary press packets.
                    if packet.button1 and not self.state.button1 and now - self._last_button1_press >= 0.2:
                        self.button1_pressed = True
                        self._last_button1_press = now
                    if packet.button2 and not self.state.button2 and now - self._last_button2_press >= 0.2:
                        self.button2_pressed = True
                        self._last_button2_press = now
                    self.state = packet
                    self._last_packet = now
                    self.connected = True
                    self._report(f"Receiving controller input on {self.port}.")
                if len(self._buffer) > 16384:
                    self._buffer.clear()
            except (serial.SerialException, OSError) as error:
                self._report(f"Controller disconnected: {error}")
                self.close()
                self._retry_at = now + 2.0

        if self._serial is None or self._last_packet is None or now - self._last_packet > 0.5:
            if self.connected:
                self._report("Controller data is stale; movement paused until input resumes.")
            self.connected = False
            self.state = ControllerState()
            self.button1_pressed = False
            self.button2_pressed = False
        return self.state
