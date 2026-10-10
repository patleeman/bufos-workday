# Bufo's Workday

A Zelda-style Game Boy Color RPG about a concerned frog, built with GB Studio 4.
Design doc: BB page "Bufo's Workday: game design doc".

Playable so far:
- The opening: Bufo's cubicle, the CEO's office, the title card.
- Level 1, the IT Basement: 9 rooms, roombas, tangled cables, the Ethernet Cable,
  and The Printer boss.
- The Lobby hub and its elevator.
- Level 2, the Break Room floor: 8 rooms, sugar ants, moldy Tupperware, the
  Coffee Mug dash, cracked walls, and The Sentient Espresso Machine boss.
- About 100 things to look at (A) and lick (B), and 6 original songs.

## Play it

- **In GB Studio:** open `gbstudio/project.gbsproj` and press Play.
- **As a ROM:** `build/bufos_workday.gb` runs in any Game Boy Color emulator
  (SameBoy, Emulicious), or on the Chromatic from a flash cart.
- **Shortcut ROMs:** `bufos_workday_boss.gb` (the Printer), `bufos_workday_level2.gb`
  (Floor 2 elevator) and `bufos_workday_boss2.gb` (the Espresso Machine).

Controls: D-pad to walk, A to talk, look at things and open chests, B to lick,
Select to dash (once Bufo has the Coffee Mug).
The coffee cups in the top-left corner are Bufo's health. The water cooler in the
Help Desk and the leaky pipe by the boss door refill them.

## Folders

- `assets/sprites/`: Bufo, enemies, the Printer, NPCs, chest, projectiles, item icons.
  `palettes.json` holds the suggested in-game colors.
- `assets/backgrounds/basement_<room>.png`: one 160x144 image per room.
- `gbstudio/`: the generated GB Studio project.
- `previews/`: scaled-up previews of the art and the room collision guide.
- `tools/`: the scripts below.

## Scripts

| Script | What it does |
|---|---|
| `make_bufo_sprite.py` | Draws Bufo. |
| `make_sprites.py` | Draws every other sprite. |
| `make_it_basement.py` | Draws the 9 rooms and checks GB Studio's limits, doors and routes. |
| `make_story_scenes.py` | Draws the cubicle, the CEO's office, the title card and Brock. |
| `make_break_room.py` | Draws the 8 Break Room rooms and the Lobby, and checks doors and routes. |
| `make_music.py` | Writes the 4 songs as hUGETracker files (`--previews` renders WAVs to `previews/music/`). |
| `make_gbstudio_project.py` | Builds `gbstudio/` from the art, layouts, dialogue and game logic. |
| `build.sh` | Runs the generator, then compiles `build/bufos_workday.gb`. |
| `setup_cli.sh` | Builds GB Studio's command-line compiler (needed once for `build.sh`). |
| `playtest.py` | Plays the ROM in PyBoy from a script of button presses and saves screenshots. |
| `test_playthrough.sh` | Plays Level 1 from the phone call and Level 2 from the elevator, and fails if any key step breaks. |

`make_gbstudio_project.py` rebuilds `gbstudio/` from scratch. Once you start
editing the project inside GB Studio, stop running it (and `build.sh`), or it
will overwrite your changes. Export the ROM from GB Studio instead.

### Playtesting a single room

`build.sh` reads optional variables for quick tests. `BUFO_PROJECT_DIR` builds into
another folder, which is handy while GB Studio has `gbstudio/` open.

```sh
BUFO_START=printer_room,9,14 BUFO_ITEMS=has_cable,has_password BUFO_HP=20 tools/build.sh
BUFO_START_HP=9 tools/build.sh   # normal start, but Bufo begins with 9 coffee
```

### Setup for the command-line tools

```sh
brew install --cask gb-studio
tools/setup_cli.sh                      # builds the compiler into /tmp/gbs-src
python3 -m venv /tmp/pyboy-venv && /tmp/pyboy-venv/bin/pip install pyboy pillow numpy
tools/test_playthrough.sh
```
