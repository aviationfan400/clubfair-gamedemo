# ESP32 joystick survival game

A fullscreen black Pygame window with a small white character and an aim arrow.
The left joystick moves the character; the right joystick points the arrow.
Release the right stick to keep the last aim direction. Press **Esc** to quit.
The character stays inside the window. Both sticks' Y axes are inverted by default
to match your controller: rolling up moves or aims up.

## Gameplay

- The window opens on a controls screen. Press the **right button** to begin;
  the timer, enemies, and shooting stay frozen until then.
- Start with **15 health**, **0 score**, and **3 heals**.
- **Red enemies** chase your current position at a base **150 pixels/second**
  (previously 110). Destroy one for **1 point**.
- **Orange enemies** chase a position **0.65 seconds ahead** of your actual
  movement. Destroy one for **2 points**. When stationary, they target your position.
  Within **180 pixels**, they switch to chasing you directly and gain **18% speed**.
  A gold outline marks this aggressive state; it ends when you move out of range.
  Their base speed is **165 pixels/second** (previously 125).
- From **00:30**, **blue enemies** join the spawn pool. They approach at a base
  **105 pixels/second**. Within **260 pixels**, they start flashing and rush at
  **3 times their current base speed**, continuing the rush until destroyed.
  At **55 pixels** from the player they explode with a **90-pixel blast radius**.
  A blast deals **1 damage**; direct contact deals **2 damage total**, with no
  additional blast damage. The blue enemy disappears and the blast briefly fades.
  Shooting one takes one bullet, prevents its explosion, and awards **3 points**.
- Enemies spawn fully outside a random screen edge, initially every **0.9 seconds**.
  After 00:30, spawn chances are **45% red, 30% orange, and 25% blue**.
- The **MM:SS timer** counts active gameplay and freezes on pause, disconnect,
  or game over. Every **15 seconds** adds **12% of the original base speed** to
  every enemy type, including enemies already on the map, and adds **25% of the
  original spawn rate**. Spawn interval is `0.9 / (1 + 0.25 * difficulty_steps)`.
- From **03:00**, all red enemies require **two bullet hits** to kill. A small
  pale ring marks red enemies that still have both hits remaining. Orange enemies
  still take one hit, and score is awarded only on the killing shot.
- You automatically fire tiny white bullets along the arrow **4 times per second**,
  at **520 pixels per second**. Each bullet deals one hit and is consumed.
- Each new game generates up to **8 gray boulders**, with random positions and
  radii (roughly **26–58 pixels**, adjusted for small windows). The center stays
  clear and boulders are spaced apart to leave passages. Players slide along
  boulders; enemies follow paths around them. Boulders also stop bullets.
- A red or orange enemy touching you costs **1 health**, then that enemy disappears
  without awarding points. Blue enemies use their explosion damage instead.
- **Left button / Button 1 / GPIO 25:** pause or resume. Movement, aiming, enemies,
  bullets, spawn/shoot timers, and heals all freeze while paused.
- **Right button / Button 2 / GPIO 26:** consume one heal to add **2 health**.
  Health can exceed the initial 15. At zero heals the button does nothing.
- Health, score, remaining heals, and elapsed time appear at the top of the screen.
- At zero health the game ends. Press the **right button** to return to the intro,
  then press it again to begin a new run, or press **Esc** to exit. Starting or
  returning to the intro does not consume a heal. A new run resets the
  timer, difficulty, health, score, and heals, and generates new terrain.
- The simulation also freezes while the controller is disconnected or input is stale.

Speeds and timing are defined at the top of `arena.py`. Existing Arduino firmware
using the documented packet format still works; these gameplay changes are in Python.

## Setup and run

### Arduino IDE setup (first time)

1. In Arduino IDE, open **File > Preferences** and add this URL to
   **Additional Boards Manager URLs**:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
2. Open **Boards Manager**, search for **esp32**, and install **esp32 by Espressif Systems**.
3. Select your actual board under **Tools > Board > esp32**. For a generic classic
   ESP32 development board, this is commonly **ESP32 Dev Module**; use the entry
   matching your board. The pin assignments here assume a classic ESP32 with
   GPIO 25, 26, and 32–35 available.
4. Select **Tools > Port > COM3**.

`Serial`, `pinMode`, and `analogRead` come from the Arduino core supplied by the
board package. Compile/upload the `.ino` in Arduino IDE. A generic C++ editor
can flag these names as undefined when it does not know the Arduino core's
headers and board configuration. The sketch explicitly includes `Arduino.h`;
Arduino IDE also adds this include automatically when preprocessing `.ino` files.
If Arduino IDE's **Verify** succeeds, editor squiggles elsewhere do not indicate
a sketch compilation failure. If Verify fails, check the board package and
selected board, then inspect the first compiler error.

Official setup: [Espressif Arduino installation guide](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html).

### Upload and start the game

1. Open `arduino/esp32_controller/esp32_controller.ino` in Arduino IDE.
2. Select your ESP32 board and **COM3**, then upload the sketch.
3. Close Arduino IDE's **Serial Monitor and Serial Plotter** so Python can open COM3.
4. In a terminal in this folder, run:

   ```powershell
   python -m pip install -r requirements.txt
   python game.py
   ```

The ESP32 communicates directly with Python over USB serial at **115200 baud**.
Arduino IDE is used to upload the sketch; it does not need to stay open.
Your original sketch and its 100 ms updates also work. The included sketch uses
10 ms updates for smoother aiming. Buttons connect their input pin to GND when
pressed; `INPUT_PULLUP` maps released to false and pressed to true in the packet.

| Input | ESP32 pin |
| --- | --- |
| Left X | 33 |
| Left Y | 32 |
| Right X | 35 |
| Right Y | 34 |
| Button 1 | 25 |
| Button 2 | 26 |

Each serial line has this format:

```text
LeftXY: 1790, 1790    RightXY: 1790, 1790    Buttons: 0, 0
```

## Calibration and options

Defaults use your reported center **1790** and range **0–4950** for both sticks.
Each side of the center is scaled separately, with a 12% radial dead zone to
prevent drift. Movement speed increases with stick deflection, with diagonal
speed capped at the same maximum as horizontal and vertical movement.

By default increasing X moves/aims right and increasing Y moves/aims up.
To disable Y inversion for a different controller, use the corresponding
`--no-invert-left-y` or `--no-invert-right-y` flag:

```powershell
python game.py --no-invert-left-y --no-invert-right-y
python game.py --windowed
python game.py --port COM3 --center 1790 --maximum 4950 --deadzone 0.12
```

Use the actual readings from your board if calibration differs. The game
ignores boot messages and malformed packets, retries an unavailable port every
two seconds, and freezes gameplay if no valid packet arrives for half a second.
Connection information appears in the terminal and a waiting message appears in the game.
Opening a serial connection may restart the ESP32; input resumes after it boots.

## Button input

Inside the game loop, `inputs.button1` and `inputs.button2` hold the latest
button state. `controller.button1_pressed` and `controller.button2_pressed`
are true for a frame when a released-to-pressed transition is received, including
when a press and release arrive together between frames. These are raw input
events with a 200 ms interval between accepted presses of the same button to
suppress switch bounce. Holding a button does not repeat its action. Presses
received while paused are consumed; heals are not queued for resume.

## Checks

Run the game from the project root, which contains `game.py`, `controller.py`,
and `requirements.txt`. The `tests` folder only contains automated checks.
If your terminal is currently in `clubfair-gamedemo/tests`, run:

```powershell
cd ..
python game.py
```

Alternatively, `python ../game.py` starts the game directly from the `tests` folder.
To run the automated checks from the project root:

```powershell
python -m unittest discover -s tests -v
```
