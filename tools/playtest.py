"""Drive the ROM in PyBoy and save screenshots. Usage:

    python tools/playtest.py ROM OUT_DIR "script"

The script is a space-separated list of steps:
    wait:N        run N frames
    A / B / up / down / left / right / start   tap a button
    hold:BUTTON:N hold a button for N frames
    shot:NAME     save a screenshot as OUT_DIR/NAME.png
    vars          print the game's named variables (reads the build's .noi symbol file)
    until:VAR:N:MAX  run frames until variable VAR equals N (gives up after MAX frames)
    pos           print the player's position
    clear         press A until no text box is on screen
    expect:VAR:N  fail unless variable VAR equals N
    mash:N        tap A N times (skip dialogue)
"""

import glob
import json
import os
import sys
import tempfile
from pathlib import Path

from pyboy import PyBoy

BUTTONS = {"A": "a", "B": "b", "up": "up", "down": "down", "left": "left", "right": "right",
           "start": "start", "select": "select"}


def variable_reader(pb):
    """Map variable names to their 16-bit slots in GB Studio's script memory.

    GB Studio drops unused variables when it compiles, so read the real slot
    numbers from the build's globals.i instead of trusting the project's IDs.
    """
    rom_dir = os.path.join(tempfile.gettempdir(), "_gbsbuild/build/rom")
    base = None
    for line in open(glob.glob(os.path.join(rom_dir, "*.noi"))[0]):
        if line.startswith("DEF _script_memory "):
            base = int(line.split()[2], 16)
    names = {}
    for line in open(os.path.join(rom_dir, "globals.i")):
        if line.startswith("VAR_") and "=" in line:
            name, slot = line.split("=")
            if not name.strip().startswith("VAR_TEMP"):
                names[name.strip()[4:].lower()] = int(slot)

    def read():
        out = {}
        for name, i in names.items():
            lo, hi = pb.memory[base + i * 2], pb.memory[base + i * 2 + 1]
            val = lo | (hi << 8)
            out[name] = val - 65536 if val > 32767 else val
        return out
    return read


def main():
    rom, out, script = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    out.mkdir(parents=True, exist_ok=True)
    pb = PyBoy(rom, window="null", cgb=True, sound_emulated=False)
    pb.set_emulation_speed(0)

    read_vars = variable_reader(pb)

    def run(n):
        for _ in range(n):
            pb.tick()

    for step in script.split():
        parts = step.split(":")
        if parts[0] == "wait":
            run(int(parts[1]))
        elif parts[0] == "until":
            name, want, limit = parts[1], int(parts[2]), int(parts[3])
            for _ in range(limit):
                if read_vars()[name] == want:
                    break
                run(1)
            else:
                print(f"until:{name}={want} timed out")
        elif parts[0] == "expect":
            got = read_vars()[parts[1]]
            if got != int(parts[2]):
                pb.stop(save=False)
                raise SystemExit(f"FAIL: expected {parts[1]}={parts[2]}, got {got}")
            print(f"ok: {parts[1]}={got}")
        elif parts[0] == "clear":
            # Press A until the text box (the window layer) stays closed for 40 frames,
            # so back-to-back dialogue boxes all get dismissed.
            run(30)
            closed_for = 0
            for _ in range(400):
                if pb.memory[0xFF4A] >= 144:
                    closed_for += 1
                    if closed_for >= 40:
                        break
                    run(1)
                else:
                    closed_for = 0
                    pb.button("a")
                    run(30)
        elif parts[0] == "pos":
            m = pb.memory
            x = m[0xD146] | (m[0xD147] << 8)
            y = m[0xD148] | (m[0xD149] << 8)
            print(f"player px=({x / 16:.2f},{y / 16:.2f}) tile=({x / 128:.2f},{y / 128:.2f}) last_trigger={m[0xD929]}")
        elif parts[0] == "vars":
            print({k: v for k, v in read_vars().items() if v})
        elif parts[0] == "shot":
            pb.screen.image.save(out / f"{parts[1]}.png")
        elif parts[0] == "hold":
            pb.button_press(BUTTONS[parts[1]])
            run(int(parts[2]))
            pb.button_release(BUTTONS[parts[1]])
            run(2)
        elif parts[0] == "mash":
            for _ in range(int(parts[1])):
                pb.button("a")
                run(24)
        elif parts[0] in BUTTONS:
            pb.button(BUTTONS[parts[0]])
            run(3)
        else:
            raise SystemExit(f"unknown step {step}")
    pb.stop(save=False)


if __name__ == "__main__":
    main()
