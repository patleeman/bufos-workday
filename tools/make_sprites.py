"""Build the Level 1 enemy, boss, NPC, projectile and item sprites.

Outputs (all in assets/sprites/, frames side by side, left to right):
  roomba.png         32x16  2 frames  enemy, angry robot vacuum
  tangled_cable.png  32x16  2 frames  enemy, wriggling cable knot
  printer.png        64x32  2 frames  boss, idle / jammed (weak point)
  paper.png          16x16  1 frame   boss projectile
  tongue.png         48x16  3 frames  Actor layout: down, up, right
  cable_hook.png     48x16  3 frames  Actor layout: down, up, right
  it_guy.png         32x16  2 frames  NPC, sleeping frog with headset
  crt.png            32x16  2 frames  NPC, legacy CRT with a frog face
  chest.png          32x16  2 frames  closed / open
  item_cable.png, item_key.png, item_password.png, item_map.png,
  item_mug.png       16x16  1 frame each
  hud_coffee.png     40x16 per frame, one frame per (max, hp), max 3..5
  Level 2 (Break Room):
  sugar_ant.png      32x16  2 frames  enemy, ant carrying a sugar cube
  tupperware.png     32x16  2 frames  enemy, moldy box with a puffing lid
  espresso.png       96x32  3 frames  boss, idle / brewing / overheated
  coffee_pod.png     16x16  1 frame   boss projectile
  steam.png          32x16  2 frames  boss projectile
  cracked_wall.png   16x16  1 frame   opaque breakable doorway block
  coffee_happy.png   32x16  2 frames  NPC, frog crying into decaf
  receptionist.png   32x16  2 frames  NPC, frog offering a form
  item_badge.png, item_po.png  16x16  1 frame each
  bufo_dash.png      48x16  3 frames  Bufo dash: down, up, right
  Levels 3-6 and the ending: see the SPRITES table at the bottom; frog
  characters share FROG_TOP plus swappable faces and bodies.
  palettes.json      suggested in-game palettes (light, mid, dark)

Preview: previews/sprites-preview.png, every sprite at 8x in its suggested
palette on the basement floor color.

Pixel key:  . transparent   D darkest   M middle   L lightest
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FLOOR = (0x6F, 0x7A, 0x8E)

# GB Studio's fixed sprite shades. The scene's sprite palette recolors them.
GBS = {
    ".": (0x65, 0xFF, 0x00),
    "D": (0x07, 0x18, 0x21),
    "M": (0x86, 0xC0, 0x6C),
    "L": (0xE0, 0xF8, 0xCF),
}

# Suggested in-game sprite palettes: light, mid, dark.
PALETTES = {
    # Silver body, red LED: the LED is the only light-shade pixel group.
    "roomba": ["#ff3b30", "#a9b0bf", "#14161f"],
    # Blue Ethernet cable, white plug heads.
    "tangled_cable": ["#f2f6ff", "#3a7ae0", "#0c1428"],
    # Off-white plastic, grey panels/LCD, near-black outline.
    "printer": ["#f4efe2", "#8f98aa", "#1c1c28"],
    "paper": ["#ffffff", "#9fb4d8", "#18203a"],
    # Pink tongue: mid shade is the tongue, light is the shine.
    "tongue": ["#ffd3e2", "#ee5d8f", "#3e0f22"],
    "hud_coffee": ["#fff4d8", "#9a5424", "#1c0e06"],
    "warning": ["#ff3b30", "#a9b0bf", "#14161f"],
    "cable_hook": ["#f2f6ff", "#3a7ae0", "#0c1428"],
    # Same frog family as Bufo, a little bluer so he reads as a different frog.
    "it_guy": ["#dfe8b8", "#5f9a6a", "#18241c"],
    # Beige case, green phosphor screen.
    "crt": ["#e8dcaa", "#5cb84a", "#1a1e14"],
    # Brown wood, gold bands and lock.
    "chest": ["#ffd447", "#a8643a", "#2a160a"],
    "item_cable": ["#f2f6ff", "#3a7ae0", "#0c1428"],
    "item_key": ["#fff3a6", "#e2b232", "#3a2808"],
    "item_password": ["#fff59a", "#e7b84a", "#3a2c10"],
    "item_map": ["#dceaff", "#4a7ed4", "#102044"],
    "item_mug": ["#ffffff", "#b06a34", "#2a1608"],
    # Level 2: Break Room.
    # Dark red-brown ant, white sugar cube.
    "sugar_ant": ["#fff8ec", "#a8342a", "#2a0a08"],
    # Sickly green mold on pale plastic.
    "tupperware": ["#e4f0b0", "#7fa832", "#1e2a10"],
    # Chrome light shade, red mid shade (accents; whole body when overheated).
    "espresso": ["#e8eef4", "#e03a2a", "#1a1c24"],
    # Gold foil rim, brown capsule.
    "coffee_pod": ["#ffd860", "#8a4a22", "#24120a"],
    "steam": ["#ffffff", "#c4ccd6", "#4a5462"],
    # Warm beige office drywall.
    "cracked_wall": ["#e8dcc0", "#b8a684", "#4a3c2a"],
    # Frog green; light shade is the blue of the tears and the decaf mug.
    "coffee_happy": ["#a8d8ff", "#6b9b4b", "#1c2a1c"],
    "receptionist": ["#e6ecb8", "#6b9b4b", "#1c2a1c"],
    # White badge, coffee-red header.
    "item_badge": ["#ffffff", "#d04a2a", "#20140c"],
    # White paper, red stamp.
    "item_po": ["#ffffff", "#e03030", "#1a1a28"],
    # Bufo's own palette, so the dash matches bufo.png in game.
    "bufo_dash": ["#dfe8a8", "#6b9b4b", "#1c2a1c"],
    # Level 3: Open-Plan Office.
    "quick_sync": ["#eef0e0", "#6b9b4b", "#1c2a1c"],
    "standup_frog": ["#f4f0a0", "#6b9b4b", "#1c2a1c"],
    "email": ["#ffffff", "#9fb4d8", "#18203a"],
    # Storm grey with glowing yellow eyes, lightning and envelopes.
    "reply_storm": ["#f8f0b0", "#5a6078", "#141824"],
    "mini_storm": ["#f8f0b0", "#5a6078", "#141824"],
    "item_headphones": ["#e8ecf4", "#5a6aa8", "#141824"],
    # Level 4: HR. Warm brown dark shade and a cream cardigan.
    "hr_frog": ["#f2dcb0", "#7aa860", "#3a2618"],
    "red_tape": ["#ffd0c0", "#d02828", "#2a0808"],
    "hydra_body": ["#ece0bc", "#a89870", "#2a2418"],
    "binder_head": ["#f4f4f0", "#3a6ad0", "#101830"],
    "policy_doc": ["#ffffff", "#e03030", "#1a1a28"],
    "item_keycard": ["#f0f4ff", "#3a7ae0", "#101828"],
    "item_folder": ["#f0d890", "#5aa040", "#2a2010"],
    "item_stamp": ["#f0d8a0", "#d03030", "#2a1a10"],
    # Level 5: Server Room. Beige case, green screen glow.
    "kevin": ["#e8e0c8", "#50c878", "#142018"],
    "firewall": ["#ffd040", "#d04020", "#2a0a04"],
    "kevin_usb": ["#e8e0c8", "#50c878", "#142018"],
    # Level 6: Executive Floor. Each board member's light shade is their color.
    "yes_man": ["#e0e8c0", "#6b9b4b", "#12161a"],
    "board_cfo": ["#b8f088", "#6b9b4b", "#1a2418"],
    "board_cmo": ["#ff9ad0", "#6b9b4b", "#1c1424"],
    "board_coo": ["#e8f0f8", "#6b9b4b", "#182030"],
    "board_cto": ["#c8e0ff", "#6b9b4b", "#10141c"],
    # Gold tie and glasses.
    "brock_seated": ["#ffd84a", "#6a9a50", "#1c2418"],
    "spreadsheet": ["#ffffff", "#e03030", "#1a2a1a"],
    # Warning yellow, grey tile edge, black void.
    "hole": ["#ffd040", "#5a6070", "#0a0c10"],
    "megaphone_blast": ["#ffffff", "#ff9ad0", "#1c1424"],
    # Ending.
    "staff_frog": ["#eef0e0", "#6b9b4b", "#1c2a1c"],
}

# --------------------------------------------------------------------------
# Roomba: top view, front bumper at the top, one angry red LED eye.
# Frame B rotates the side brush and squints the LED.

ROOMBA_A = """
D..D.DDDDDD.....
.D.DDMMMMMMDD...
..DMMMMMMMMMMD..
.DMDDDDDDDDDDMD.
.DMMDMMMMMMDMMD.
DMMMMDDMMDDMMMMD
DMMMMMDDDDMMMMMD
DMMMMDLLLLDMMMMD
DMMMMDLDDLDMMMMD
DMMMMDLLLLDMMMMD
DMMMMMDDDDMMMMMD
.DMMMMMMMMMMMMD.
.DMMMMDDDDMMMMD.
..DMMMMMMMMMMD..
...DDMMMMMMDD...
.....DDDDDD.....
"""

ROOMBA_B = """
..D..DDDDDD.....
..DDDMMMMMMDD...
DDDMMMMMMMMMMD..
.DMDDDDDDDDDDMD.
.DMMDMMMMMMDMMD.
DMMMMDDMMDDMMMMD
DMMMMMDDDDMMMMMD
DMMMMDDDDDDMMMMD
DMMMMDLLLLDMMMMD
DMMMMDDDDDDMMMMD
DMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMD.
.DMMMMDDDDMMMMD.
..DMMMMMMMMMMD..
...DDMMMMMMDD...
.....DDDDDD.....
"""

# --------------------------------------------------------------------------
# Tangled cable: a ball of cable with two RJ45 plug heads on necks.

CABLE_A = """
DDDDD......DDDDD
DLDLD......DLDLD
DLLLD......DLLLD
DDDDD......DDDDD
.DMD........DMD.
.DMD.DDDDDD.DMD.
.DMDDMMMMMMDDMD.
.DMMDDDDDDDDMMD.
DMDDMMDMMDMMDDMD
DMDMDDMDDMDDMDMD
DMMDMMDDDDMMDMMD
DMDDMDMMMMDMDDMD
.DMMDDDDDDDDMMD.
.DMDMMMMMMMMDMD.
..DDDDMMMMDDDD..
....DDDDDDDD....
"""

CABLE_B = """
..DDDDD..DDDDD..
..DLDLD..DLDLD..
..DLLLD..DLLLD..
..DDDDD..DDDDD..
...DMD....DMD...
...DMDDDDDDMD...
..DDMMMMMMMMDD..
.DMMDDDDDDDDMMD.
DMDDMMDMMDMMDDMD
DMDMDDMDDMDDMDMD
DMMDMMDDDDMMDMMD
DMDDMDMMMMDMDDMD
.DMMDDDDDDDDMMD.
.DMDMMMMMMMMDMD.
..DDDDMMMMDDDD..
....DDDDDDDD....
"""

# --------------------------------------------------------------------------
# Printer boss, 32x32. LCD face is the mid shade with dark features.

PRINTER_IDLE = """
................................
................................
................................
.......DDDDDDDDDDDDDDDDDD.......
.......DLLLLLLLLLLLLLLLLD.......
..DDDDDDLMMMMMMMMMMMMMMLDDDDDD..
.DLLLLLDDDDDDDDDDDDDDDDDDLLLLLD.
.DLLLLLLLLLLLLLLLLLLLLLLLLLLLLD.
.DMMMMMMMMMMMMMMMMMMMMMMMMMMMMD.
.DLLLDDDDDDDDDDDDDDDDDDDDLLLLLD.
.DLLLDMMMMMMMMMMMMMMMMMMDLLLLLD.
.DLLLDMDDMMMMMMMMMMMMDDMDLLLLLD.
.DLLLDMMMDDMMMMMMMMDDMMMDLDDDLD.
.DLLLDMMDDDDMMMMMMDDDDMMDLDLDLD.
.DLLLDMMDDDDMMMMMMDDDDMMDLDDDLD.
.DLLLDMMMMMMMMMMMMMMMMMMDLLLLLD.
.DLLLDMMMMMMDDDDDDMMMMMMDLDDDLD.
.DLLLDMMMMMDMMMMMMDMMMMMDLDLDLD.
.DLLLDMMMMMMMMMMMMMMMMMMDLDDDLD.
.DLLLDDDDDDDDDDDDDDDDDDDDLLLLLD.
.DLLLLLLLLLLLLLLLLLLLLLLLLLLLLD.
.DMMMMMMMMMMMMMMMMMMMMMMMMMMMMD.
.DDDDDDDDDDDDDDDDDDDDDDDDDDDDDD.
.DLLLLLLLLLLLLLLLLLLLLLLLLLLLLD.
.DLLLLLLLLLLDDDDDDDDLLLLLLLLLLD.
.DLLLLLLLLLLDMMMMMMDLLLLLLLLLLD.
.DLLLLLLLLLLLLLLLLLLLLLLLLLLLLD.
.DMMMMMMMMMMMMMMMMMMMMMMMMMMMMD.
.DDDDDDDDDDDDDDDDDDDDDDDDDDDDDD.
..DDDD....................DDDD..
................................
................................
"""

PRINTER_JAM = """
.........DD.DDD.........D..D..D.
........DLLDLLLD.........D.D.D..
.......DLLDLLDLLD.......D.DLD.D.
.......DLDLLLLDLDDDDDD...DLLLD..
.......DLLLDLLLLDLLLLD..DLLLLLD.
..DDDDDDDLLLLDLDLMMMLDDDDDLLLDD.
.DLLLLLDDDDDDDDDDDDDDDDDDLDLDLD.
.DLLLLLLLLLLLLLLLLLLLLLLLLLLLLD.
.DMMMMMMMMMMMMMMMMMMMMMMMMMMMMD.
.DLLLDDDDDDDDDDDDDDDDDDDDLLLLLD.
.DLLLDMMMMMMMMMMMMMMMMMMDLLLLLD.
.DLLLDMMMMMMMMMMMMMMMMMMDLLLLLD.
.DLLLDMMDMMDMMMMMMDMMDMMDLDDDLD.
.DLLLDMMMDDMMMMMMMMDDMMMDLDLDLD.
.DLLLDMMDMMDMMMMMMDMMDMMDLDDDLD.
.DLLLDMMMMMMMMMMMMMMMMMMDLLLLLD.
.DLLLDMMMMDMMDMMDMMDMMMMDLDDDLD.
.DLLLDMMMMMDMMDMMDMMDMMMDLDLDLD.
.DLLLDMMMMMMMMMMMMMMMMMMDLDDDLD.
.DLLLDDDDDDDDDDDDDDDDDDDDLLLLLD.
.DLLLLLLLLLLLLLLLLLLLLLLLLLLLLD.
.DMMMMMMMMMMMMMMMMMMMMMMMMMMMMD.
.DDDDDDDDDDDDDDDDDDDDDDDDDDDDDD.
.DDDDLLDLLDDDDDDDDDDDDDLLDLDDDD.
.DDDLLDLLLLDDDDDDDDDDDLLLLDLDDD.
DDDLDLLLDLLDDDDDDDDDDLDLLLLLLDDD
DLLLLDLLLDLLLLLLLLDDDLLLDLLLLLLD
DLLLLLLLLLLLLDDDDDDDDLLLLLLLLLLD
DLLLLLLLLLLLLDMMMMMMDLLLLLLLLLLD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD
................................
"""

# --------------------------------------------------------------------------
# Paper projectile: a sheet with a folded corner and text lines.

PAPER = """
................
....DDDDDDDD....
....DLLLLLLDD...
....DLMMMMLDLD..
....DLLLLLLDDDD.
....DLMMMMMMMLD.
....DLLLLLLLLLD.
....DLMMMMMMMLD.
....DLLLLLLLLLD.
....DLMMMMMMMLD.
....DLLLLLLLLLD.
....DLMMMMMLLLD.
....DLLLLLLLLLD.
....DDDDDDDDDDD.
................
................
"""

# --------------------------------------------------------------------------
# Tongue: drawn facing down (mouth above the frame). Up and right derive.

TONGUE_DOWN = """
.....DMLMMD.....
.....DMLMMD.....
.....DMLMMD.....
.....DMLMMD.....
.....DMLMMD.....
.....DMLMMD.....
.....DMLMMD.....
.....DMLMMD.....
....DMMLMMMD....
...DMMMMMMMMD...
...DMLLMMMMMD...
...DMLMMMMMMD...
...DMMMMMMMMD...
....DMMMMMMD....
.....DDDDDD.....
................
"""

# Cable hook: RJ45 plug drawn facing down (cable comes from above).

HOOK_DOWN = """
......DMMD......
......DMMD......
......DMMD......
......DMMD......
......DMMD......
.....DDMMDD.....
.....DMMMMD.....
....DMMMMMMD....
...DDDDDDDDDD...
...DLLLLLLLLD...
...DLLDDDDLLD...
...DLLLLLLLLD...
...DLLLLLLLLD...
...DLDLDLDLDD...
...DDDDDDDDDD...
................
"""

# --------------------------------------------------------------------------
# IT guy: Bufo's species, asleep, wearing a headset with a mic boom.

IT_A = """
...DDD....DDD...
..DMMMD.DDMMMD..
..DMMMDDDDMMMD..
.DMMMMMMMMMMMMD.
DDDMMMMMMMMMMDDD
DLDMDDDMMDDDMDLD
DLDMMMMMMMMMMDLD
DDDMMMMDDMMMMDDD
.DDDMMMMMMMMMMD.
.DMDLDDDDDDDDMD.
..DMLLLLLLLLMD..
.DMDLLLLLLLLDMD.
.DMDLLLLLLLLDMD.
..DDMLLLLLLMDD..
..DMMDDDDDDMMD..
..DDD......DDD..
"""

IT_B = """
.............DDD
...DDD....DDD.D.
..DMMMD.DDMMMDDD
..DMMMDDDDMMMD..
.DMMMMMMMMMMMMD.
DDDMMMMMMMMMMDDD
DLDMDDDMMDDDMDLD
DLDMMMMMMMMMMDLD
DDDMMMMDDMMMMDDD
.DDDMMMMMMMMMMD.
.DMDLDDDDDDDDMD.
.DMDLLLLLLLLDMD.
.DMDLLLLLLLLDMD.
..DDMLLLLLLMDD..
..DMMDDDDDDMMD..
..DDD......DDD..
"""

# --------------------------------------------------------------------------
# CRT: beige monitor, chunky back to the right, frog face on the screen.

CRT_A = """
................
DDDDDDDDDDDDD...
DLLLLLLLLLLLDDD.
DLDDDDDDDDDLDLLD
DLDMLLMMLLMDDLLD
DLDMLDMMDLMDDLLD
DLDMMMMMMMMDDLLD
DLDDMMMMMMDDDLLD
DLDMDDDDDDMDDLLD
DLDDDDDDDDDLDLLD
DLLLLLLLDLDLDLD.
DDDDDDDDDDDDDDD.
...DDLLLLDD.....
..DDDDDDDDDD....
................
................
"""

CRT_B = """
................
DDDDDDDDDDDDD...
DLLLLLLLLLLLDDD.
DLDDDDDDDDDLDLLD
DLDMMMMMMMMDDLLD
DLDMDDMMDDMDDLLD
DLDMMMMMMMMDDLLD
DLDDMMMMMMDDDLLD
DLDMDDDDDDMDDLLD
DLDDDDDDDDDLDLLD
DLLLLLLLDLDLDLD.
DDDDDDDDDDDDDDD.
...DDLLLLDD.....
..DDDDDDDDDD....
................
................
"""

# --------------------------------------------------------------------------
# Chest: closed, then open.

CHEST_CLOSED = """
................
................
................
................
...DDDDDDDDDD...
..DMMLMMMMLMMD..
.DMMMLMMMMLMMMD.
.DMMMLMMMMLMMMD.
.DMMMLDDDDLMMMD.
.DDDDDDLLDDDDDD.
.DMMMLDLLDLMMMD.
.DMMMLDDDDLMMMD.
.DMMMLMMMMLMMMD.
.DMMMLMMMMLMMMD.
.DMMMLMMMMLMMMD.
.DDDDDDDDDDDDDD.
"""

CHEST_OPEN = """
....DDDDDDDD....
...DMMLMMLMMD...
..DMMMLMMLMMMD..
.DDDDDDDDDDDDDD.
.DMMMMMMMMMMMMD.
.DDDDDDDDDDDDDD.
.DDDDDDDDDDDDDD.
.DDDLDDDDDDDDDD.
.DDDDDDDDDDLDDD.
.DLLLLLLLLLLLLD.
.DMMMLDLLDLMMMD.
.DMMMLDDDDLMMMD.
.DMMMLMMMMLMMMD.
.DMMMLMMMMLMMMD.
.DMMMLMMMMLMMMD.
.DDDDDDDDDDDDDD.
"""

# --------------------------------------------------------------------------
# Item icons.

ITEM_CABLE = """
................
.....DDDDDD.....
...DDMMMMMMDD...
..DMMDDDDDDMMD..
.DMDDMMMMMMDDMD.
.DMDMDDDDDDMDMD.
DMDMDD....DDMDMD
DMDMD......DMDMD
DMDMD......DMDMD
DMDMDD....DDMDMD
.DMDMDDDDDDMDMD.
.DMDDMMMMMMDDMDD
..DMMDDDDDDMMDLD
...DDMMMMMMDDDLD
.....DDDDDDDLLLD
...........DDDD.
"""

ITEM_KEY = """
................
................
..DDDD..........
.DLLLLD.........
DLMDDMMD........
DLD..DMDDDDDDDD.
DLD..DMLLLLLLLMD
DMMDDMMMMMMMMMMD
.DMMMMDDDDDMDMD.
..DDDD.....DMD..
...........DMD..
............D...
................
................
................
................
"""

ITEM_PASSWORD = """
................
................
.DDDDDDDDDDDDD..
.DLLLLLLLLLLLD..
.DLDDLDLDDDLLD..
.DLLDDLDDLLDLD..
.DLLLLLLLLLLLD..
.DLDLDDLDDDLLD..
.DLLDLLDDLLDLD..
.DLLLLLLLLLLLD..
.DLDDDLDLDDLLD..
.DLLLLLLLLMMMD..
.DLLLLLLLLMLD...
.DLLLLLLLLMD....
.DDDDDDDDDD.....
................
"""

ITEM_MAP = """
................
.....DDDDDD.....
DDDDDDMMMMDDDDDD
DLLLLDMMMMDLLLLD
DLDLLDMMMMDLLLLD
DLLLLDMMMMDLLLLD
DLLDLDMDMMDLLLLD
DLLLLDMMMMDLLLLD
DLLLLDMMDMDLMLMD
DLLLLDMMMMDLLMLD
DLLLLDMMMMDLMLMD
DLLLLDMMMMDLLLLD
DLLLLDMMMMDLLLLD
DDDDDDMMMMDDDDDD
.....DDDDDD.....
................
"""

ITEM_MUG = """
....L....L......
...L....L.......
...L....L.......
....L....L......
.....L....L.....
..DDDDDDDDDD....
.DLMMMMMMMMLD...
.DLDDDDDDDDLDDD.
.DLLLLLLLLLLDLLD
.DLLLLLLLLLLDDLD
.DLLLLLLLLLLD.LD
.DLLLLLLLLLLDDLD
.DMLLLLLLLLLDLD.
.DMMLLLLLLLMDD..
..DDDDDDDDDD....
................
"""


# ==========================================================================
# Level 2: the Break Room.
# ==========================================================================

# Sugar ant: side view facing right, a sugar cube held over its head.

ANT_A = """
.......DDDDDD...
.......DLLLMD...
.......DLLLLD...
.......DLMLLD...
.......DLLLLD...
.......DDDDDD.D.
........D.D..D..
.DDDD...D.DDDD..
DMMMMD.DDDMMMMD.
DMLMMMDMMDMLDMD.
DMMMMMDMMDMLLMMD
DMMMMDDDDDMMMMD.
.DDDD.D.D..DDD..
.....D..D...D...
....D..D.....D..
...DD..DD....DD.
"""

ANT_B = """
.......DDDDDD...
.......DLLLMD...
.......DLLLLD...
.......DLMLLD...
.......DLLLLD...
.......DDDDDD.D.
........D.D..D..
.DDDD...D.DDDD..
DMMMMD.DDDMMMMD.
DMLMMMDMMDMLDMD.
DMMMMMDMMDMLLMMD
DMMMMDDDDDMMMMD.
.DDDD..D.D.DDD..
......D..D.D....
......D...D.D...
.....DD...DD.DD.
"""

# Moldy Tupperware: fuzzy lid that puffs up, two beady eyes in the mold.

TUPPER_A = """
................
................
................
................
....D.D..D.D....
...DMDMDDMDMD...
..DDDDDDDDDDDD..
.DMMMMMMMMMMMMD.
.DDDDDDDDDDDDDD.
..DLLMMLLLLMLD..
..DLMMMLLLMMLD..
..DLLDLLLLDLLD..
..DLLLLMMLLLLD..
..DLMLLLLLLMLD..
..DLLLLLLLLLLD..
...DDDDDDDDDD...
"""

TUPPER_B = """
................
..D.D.D..D.D.D..
.DMDMDMDDMDMDMD.
.DMMMMMMMMMMMMD.
..DDDDDDDDDDDD..
.DMMMMMMMMMMMMD.
.DMMMMMMMMMMMMD.
.DDDDDDDDDDDDDD.
..DMDMMDDMMDMD..
..DLLMMLLLLMLD..
..DLMMMLLLMMLD..
..DLDDLLLLDDLD..
..DLLLLMMLLLLD..
..DLMLLLLLLMLD..
..DLLLLLLLLLLD..
...DDDDDDDDDD...
"""

# Espresso machine boss, 32x32. Chrome is the light shade, red the mid
# shade. Faces are 14x14 pressure-gauge overlays at (9, 3) that poke above
# the machine like a head; "?" keeps the pixel underneath.

ESPRESSO_BODY = """
................................
................................
................................
..........................DDD...
..........................DLD...
..........................DLD...
..DDDDDDDDDDDDDDDDDDDDDDDDDDDD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLMMLLLLLLLLLLLLMMLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DLDLLLLLLLLLLLLLLLLLLLLLLDLD..
..DMMMMMMMMMMMMMMMMMMMMMMMMMMD..
..DDDDDDDDDDDDDDDDDDDDDDDDDDDD..
..DLDDDLLLLDDDDDDDDDDDLLLLDDLD..
DDDDDDDLLLLDDDDDDDDDDDLLLLDDDDDD
DMMMMMDDLLDDDDDDDDDDDDDLLDDMMMMD
DDDLDDDDDDDDDDDDDDDDDDDDDDDDLDDD
..DLDDDDDDDDDDDDDDDDDDDDDDDDLD..
..DLDDDDDDDDDDDDDDDDDDDDDDDDLD..
..DLDDDDDDDDDDDDDDDDDDDDDDDDLD..
..DDDDDDDDDDDDDDDDDDDDDDDDDDDD..
..DLDLDLDLDLDLDLDLDLDLDLDLDLDD..
..DLLLLLLLLLLLLLLLLLLLLLLLLLLD..
..DDDDDDDDDDDDDDDDDDDDDDDDDDDD..
..DDD....................DDD....
................................
"""

FACE_SMUG = """
?????DDDD?????
???DDMMMMDD???
??DMMLLLLMMD??
?DMLLLLLLLLMD?
?DMLLLLLLLLMD?
DMLDDDLLDDDLMD
DMLLDDLLLDDLMD
DMLLLLLLLLLLMD
DMLLLLLLLLDLMD
?DMLDDDDDDLMD?
?DMLLLLLLLLMD?
??DMMLLLLMMD??
???DDMMMMDD???
?????DDDD?????
"""

FACE_INTENSE = """
?????DDDD?????
???DDMMMMDD???
??DMMLLLLMMD??
?DMLLLLLLLLMD?
?DMDLLLLLLDMD?
DMLLDDLLDDLLMD
DMLDDDLLDDDLMD
DMLDDDLLDDDLMD
DMLLLLLLLLLLMD
?DMLDDDDDDLMD?
?DMLDLDLDDLMD?
??DMMLLLLMMD??
???DDMMMMDD???
?????DDDD?????
"""

FACE_DIZZY = """
?????DDDD?????
???DDMMMMDD???
??DMMLLLLMMD??
?DMLLLLLLLLMD?
?DMLLLLLLLLMD?
DMLDDLLLLDDLMD
DMDLDDLLDDLDMD
DMDLLDLLDLLDMD
DMLDDLLLLDDLMD
?DMDLLDDLLDMD?
?DMLDDLLDDLMD?
??DMMLLLLMMD??
???DDMMMMDD???
?????DDDD?????
"""

PUFF = """
??DDDD??
?DLLLLDD
DLLLLLLD
DLLLLLLD
?DDDDDD?
"""

SMALL_PUFF = """
?DDD?
DLLLD
DLLLD
?DDD?
"""

# Overheated: the drip tray drops open on its right hinge and drips.
TRAY_OPEN = """
..DDDDDDDDDDDDDDDDDDDDDDDDDDDD..
...................DDDDDDDDDDD..
..........DDDDDDDDDMDLDLDLDLDD..
..DDDDDDDDDLDLDLDLDLDDDDDDDDDD..
..DLDLDLDLDLDDDDDDDDDD...DDD....
..DDDDDDDDDD........L...........
"""

# Coffee pod: foil rim on top, domed capsule body.

POD = """
................
................
................
..DDDDDDDDDDDD..
..DLLLLLLLLLLD..
..DDDDDDDDDDDD..
...DMMMMMLLMD...
...DMMMMMMLMD...
....DMMMMMLD....
....DMMMMMMD....
.....DMMMMD.....
......DDDD......
................
................
................
................
"""

# Steam puff projectile.

STEAM_A = """
................
................
.....DDD........
...DDLLLD.DDD...
..DLLLLLLDLLLD..
.DLLLLLLLLLLLLD.
.DLLLLLLLLLLLMD.
DLLLLLLLLLLLLMMD
DLLLLLLLLLLLMMMD
DMLLLLLLLLLMMMD.
.DMMLLLMMMMMMD..
..DDMMMDDDMMD...
....DDD...DD....
................
................
................
"""

STEAM_B = """
................
........DDD.....
..DDD..DLLLD....
.DLLLDDLLLLLD...
.DLLLLLLLLLLDDD.
.DLLLLLLLLLLLLLD
DLLLLLLLLLLLLLMD
DLLLLLLLLLLLLMMD
DMLLLLLLLLLLMMMD
.DMLLLLLLLLMMMD.
..DMMMLLLMMMMD..
...DDMMMDDMMD...
.....DDD..DD....
................
................
................
"""

# Cracked drywall chunk that plugs a doorway. Fully opaque.

CRACKED_WALL = """
DDDDDDDDDDDDDDDD
DLLLLLLDLLLLLLMD
DLLLLLLDLLLLLLMD
DLLLLLDLLLLLLLMD
DLLLLLDDLLLMLLMD
DLDDLLLDLLLLLLMD
DLLLDDLDDLLLLLMD
DLLLLLDDLDDLLLMD
DLMLLLLDLLLDDLMD
DLLLLLDLLLLLLDMD
DLLLLLDLLLLLLLMD
DLLLLDLLLLMLLLMD
DLLLDDLLLLLLLLMD
DLLLDLLLMLLLLLMD
DMMMDMMMMMMMMMMD
DDDDDDDDDDDDDDDD
"""

# Coffee-happy frog crying into a decaf mug. Light shade = tears + mug.

SAD_A = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
.DMMMMDDDDMMMMD.
DMMDDDMMMMDDDMMD
DMDMMMDMMDMMMDMD
DMLMMMMMMMMMMLMD
DMLMMMMDDMMMMLMD
DMLMMDDDDDDMMLMD
DMMMDMMMMMMDMMMD
DMMDDDDDDDDDDDMD
DDMDLLLLLLLLDDDD
DMMDLMMLMLLLDLD.
DDMDLMLLMMLLDLD.
.D.DLMMLMLLLDDD.
...DLLLLLLLLD...
...DDDDDDDDDD...
"""

SAD_B = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
.DMMMMDDDDMMMMD.
DMMDDDMMMMDDDMMD
DMDMMMDMMDMMMDMD
DMLMMMMMMMMMMLMD
DMMMMMMDDMMMMMMD
DMLMMDDDDDDMMLMD
DMLMDMMMMMMDMLMD
DMMDDDDDDDDDDDMD
DDMDLLLLLLLLDDDD
DMMDLMMLMLLLDLD.
DDMDLMLLMMLLDLD.
.D.DLMMLMLLLDDD.
...DLLLLLLLLD...
...DDDDDDDDDD...
"""

# Receptionist frog behind a desk, holding out a form.

DESK_A = """
................
..DDD...DDD.....
.DMMMD.DMMMD....
.DLLDMDMDLLD....
DMLDLMMMLDLMD...
DMMMMMMMMMMMDDD.
DMMDMMMMMDMMDLLD
DMMMDDDDDMMMDLLD
.DMMMMMMMMMDDLLD
.DMMMMMMMMMMDDDD
.DMMMMMMMMMMMMD.
DDDDDDDDDDDDDDDD
DLLLLLLLLLLLLLLD
DMMMMMMMMMMMMMMD
DLLLLLLLLLLLLLLD
DDDDDDDDDDDDDDDD
"""

DESK_B = """
................
..DDD...DDD.DDD.
.DMMMD.DMMMDLLLD
.DLLDMDMDLLDLLLD
DMLDLMMMLDLMDDDD
DMMMMMMMMMMMDMD.
DMMDMMMMMDMMDMD.
DMMMDDDDDMMMDMD.
.DMMMMMMMMMDMMD.
.DMMMMMMMMMMMMD.
.DMMMMMMMMMMMD..
DDDDDDDDDDDDDDDD
DLLLLLLLLLLLLLLD
DMMMMMMMMMMMMMMD
DLLLLLLLLLLLLLLD
DDDDDDDDDDDDDDDD
"""

# Boss key: "World's Okayest Barista" badge on a clip.

ITEM_BADGE = """
................
......DDDD......
......DLLD......
..DDDDDDDDDDDD..
.DMMMMMMMMMMMMD.
.DMLMLMLLMLMLMD.
.DMMMMMMMMMMMMD.
.DLLLLLLLLLLLLD.
.DLDDDDLLLLLLLD.
.DLDLLDDLDDDLLD.
.DLDLLDDLLLLLLD.
.DLLDDLLLDDDDLD.
.DLLLLLLLLLLLLD.
.DDDDDDDDDDDDDD.
................
................
"""

# Purchase order with a big red stamp.

ITEM_PO = """
................
..DDDDDDDDDD....
..DLLLLLLLLDD...
..DLDDDLLLLDLD..
..DLLLLLLLLDDDD.
..DLDDDDDDDDDLD.
..DLLLLLLLLLLLD.
..DLMMMMMMMMMLD.
..DLMLMLMMLLMLD.
..DLMLMMLMLMMLD.
..DLMMMMMMMMMLD.
..DLLLLLLLLLLLD.
..DLDDDDDLDDDLD.
..DLLLLLLLLLLLD.
..DDDDDDDDDDDDD.
................
"""

# Bufo dash, drawn from assets/sprites/bufo.png frames (down A, up A,
# right A): body crouched forward, legs kicked back, trailing speed lines.

DASH_DOWN = """
.D....D..D....D.
.D....D..D....D.
......D..D......
..DDDD....DDDD..
.DMMMMD..DMMMMD.
.DMMDDDDDDDDMMD.
DDDLLLDMMDLLLDDD
DMLLDDDMMDDDLLMD
DMMLLLMMMMLLLMMD
DMMMMMDMMDMMMMMD
DMMMMMMMMMMMMMMD
DMMDDDDDDDDDDMMD
.DDMLLLLLLLLMDD.
DMDLLLLLLLLLLDMD
.DMMDDDDDDDDDMD.
.DDDD.......DD..
"""

DASH_UP = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
.DMMMMDDDDMMMMD.
DMMMMMMMMMMMMMMD
DMMMLMMMMMMLMMMD
DMMMMMMMMMMMMMMD
DMLMMMMMMMMMLMMD
DMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMD.
.DMMMMMLMMMMMMD.
DMDMMMMMMMMMMDMD
.DMMDDDDDDDDDMD.
.DDDD.......DD..
......D..D......
.D....D..D....D.
.D....D..D....D.
"""

DASH_RIGHT = """
.........DDDD...
........DMMMMD..
DDDD....DDDDDD..
.....DDDDLLLDLD.
DDD.DMMMDLLLDDMD
...DMMMMMDLLLLMD
..DMMMLMMMMMMMMD
..DMMMMMMMMMMMDD
.DMMLMMMMMMMMMMD
DDMMMMMMMMDDDDD.
.DMMMMMMMLLLLLD.
.DMMMMMMDLLLLD..
..DMMMMDMLLLD...
DDDDMMDDMMDDD...
DMMDDD...DMMD...
DDD.......DDDD..
"""


def parse(art, w=16, h=16):
    rows = art.strip("\n").splitlines()
    assert len(rows) == h, (len(rows), art)
    for i, r in enumerate(rows):
        assert len(r) == w, (i, len(r), r)
        assert set(r) <= set(".DML"), (i, r)
    return rows


def vflip(rows):
    return rows[::-1]


def transpose(rows):
    return ["".join(rows[y][x] for y in range(len(rows))) for x in range(len(rows[0]))]


def actor(down):
    """Actor layout from a down-facing frame: down, up, right."""
    d = parse(down)
    return [d, vflip(d), transpose(d)]


def tongue_frames(down):
    """Half-out and fully-out tongue for each direction: down, up, right (x2 each)."""
    full = parse(down)
    half = full[7:] + ["." * 16] * 7
    return [half, full, vflip(half), vflip(full), transpose(half), transpose(full)]


WARNING = """
.....LLLLLL.....
...LLDDDDDDLL...
..LDD......DDL..
.LD....LL....DL.
.LD...LLLL...DL.
LD....LLLL....DL
LD....LLLL....DL
LD.....LL.....DL
LD.....LL.....DL
LD............DL
LD.....LL.....DL
.LD...LLLL...DL.
.LD....LL....DL.
..LDD......DDL..
...LLDDDDDDLL...
.....LLLLLL.....
"""

CUP_FULL = [
    "..L.L...",
    "DDDDDD..",
    "DMMMMDD.",
    "DMLMMD.D",
    "DMLMMD.D",
    "DMMMMDD.",
    ".DMMD...",
    "..DD....",
]
CUP_EMPTY = [
    "........",
    "DDDDDD..",
    "D....DD.",
    "D....D.D",
    "D....D.D",
    "D....DD.",
    ".D..D...",
    "..DD....",
]
HUD_STATES = [(mx, hp) for mx in (3, 4, 5) for hp in range(mx + 1)]


def hud_frames():
    """Coffee-cup health bar: one 40x16 frame per (max cups, full cups).

    Frame order: for max in (3, 4, 5): for hp in 0..max.
    """
    frames = []
    for mx, hp in HUD_STATES:
        rows = ["." * 40 for _ in range(16)]
        for i in range(mx):
            cup = CUP_FULL if i < hp else CUP_EMPTY
            for y in range(8):
                rows[y + 4] = rows[y + 4][: i * 8] + cup[y] + rows[y + 4][i * 8 + 8 :]
        frames.append(rows)
    return frames


def overlay(base, patch, x0, y0):
    """Paste an ASCII patch onto a frame; "?" in the patch keeps the base."""
    rows = [list(r) for r in base]
    for dy, line in enumerate(patch.strip("\n").splitlines()):
        for dx, ch in enumerate(line):
            if ch != "?":
                rows[y0 + dy][x0 + dx] = ch
    return ["".join(r) for r in rows]


def espresso_frames():
    """Idle (smug), brewing (steam, intense), overheated (red, dizzy, tray open)."""
    body = parse(ESPRESSO_BODY, 32, 32)
    idle = overlay(body, FACE_SMUG, 9, 3)

    brew = overlay(body, FACE_INTENSE, 9, 3)
    brew = overlay(brew, PUFF, 24, 0)
    brew = overlay(brew, SMALL_PUFF, 19, 0)

    # Red-hot: chrome (light) becomes the mid shade, except the gauge face.
    hot = [r.replace("L", "M") for r in body]
    hot = overlay(hot, FACE_DIZZY, 9, 3)
    hot = overlay(hot, TRAY_OPEN, 0, 26)
    hot = overlay(hot, PUFF, 24, 0)
    hot = overlay(hot, SMALL_PUFF, 19, 0)
    hot = overlay(hot, PUFF, 1, 1)
    hot = overlay(hot, SMALL_PUFF, 0, 9)
    hot = overlay(hot, SMALL_PUFF, 27, 11)
    for r in (idle, brew, hot):
        assert len(r) == 32 and all(len(x) == 32 for x in r)
    return [idle, brew, hot]

# ==========================================================================
# Levels 3-6 and the ending.
# ==========================================================================


def rows_of(art):
    return art.strip("\n").splitlines()


def frame(*parts, w=16, h=16):
    """Stack ASCII blocks into one frame and check its size."""
    rows = [r for p in parts for r in rows_of(p)]
    assert len(rows) == h and all(len(r) == w for r in rows), rows
    assert all(set(r) <= set(".DML") for r in rows), rows
    return rows


def shift(rows, dx=0, dy=0):
    """Move a frame by whole pixels; uncovered pixels become transparent."""
    h, w = len(rows), len(rows[0])
    out = []
    for y in range(h):
        sy = y - dy
        line = ""
        for x in range(w):
            sx = x - dx
            line += rows[sy][sx] if 0 <= sy < h and 0 <= sx < w else "."
        out.append(line)
    return out


def outlined(rows):
    """Give every visible pixel a dark 1px outline (4-neighbour)."""
    h, w = len(rows), len(rows[0])
    out = [list(r) for r in rows]
    for y in range(h):
        for x in range(w):
            if rows[y][x] != ".":
                continue
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and rows[ny][nx] not in ".D":
                    out[y][x] = "D"
    return ["".join(r) for r in out]


def brickify(rows, top=7):
    """Fill mid-shade pixels below `top` with a staggered brick pattern."""
    out = [list(r) for r in rows]
    for y in range(top, len(rows)):
        for x, ch in enumerate(rows[y]):
            if ch != "M":
                continue
            course = (y - top) // 3
            if (y - top) % 3 == 0 or (x + (2 if course % 2 else 0)) % 5 == 0:
                out[y][x] = "D"
    return ["".join(r) for r in out]


# --- Shared frog parts (Bufo's species: wide head, two eye bumps) ---------

FROG_TOP = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
.DMMMMDDDDMMMMD.
"""

# Faces cover rows 3-9.
FACE_SMILE = """
DMLLLMMMMMMLLLMD
DMLLDMMMMMMDLLMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMDMMMMMMMMDMMD
DMMMDDDDDDDDMMMD
.DDMMMMMMMMMMDD.
"""

FACE_TALK = """
DMLLLMMMMMMLLLMD
DMLLDMMMMMMDLLMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMMDDDDDDDDMMMD
DMMMMDDDDDDMMMMD
.DDMMMMMMMMMMDD.
"""

FACE_EAGER = """
DMLLLMMMMMMLLLMD
DMLDLMMMMMMLDLMD
DMLLLMMMMMMLLLMD
DMMMMMDMMDMMMMMD
DMMDDDDDDDDDDMMD
DMMMDLLLLLLDMMMD
.DDMMDDDDDDMMDD.
"""

FACE_KIND = """
DMMDDMMMMMMDDMMD
DMDMMDMMMMDMMDMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMDMMMMMMMMDMMD
DMMMDDDDDDDDMMMD
.DDMMMMMMMMMMDD.
"""

FACE_GLANCE = """
DMLLLMMMMMMLLLMD
DMLLDMMMMMMLLDMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMMMMMMMMMMMMMD
DMMMMDMDDMDMMMMD
.DDMMMMMMMMMMDD.
"""

FACE_SHOUT = """
DMLDDMMMMMMDDLMD
DMLDLMMMMMMLDLMD
DMMMMMDMMDMMMMMD
DMMDDDDDDDDDDMMD
DMMDLDDDDDDLDMMD
DMMMDDDDDDDDMMMD
.DDMMMMMMMMMMDD.
"""

FACE_FLUSTER = """
DMLLLMMMMMMLLLMD
DMLDLMMMMMMLDLMD
DMLLLMMMMMMLLLMD
DMMMMMDMMDMMMMMD
DMMMMMMMMMMMMMMD
DMMDMDMDMDMDMMMD
.DDMMMMMMMMMMDD.
"""

FACE_CLOSED = """
DMMMMMMMMMMMMMMD
DMDDDMMMMMMDDDMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMDMMMMMMMMDMMD
DMMMDDDDDDDDMMMD
.DDMMMMMMMMMMDD.
"""

# Standing bodies cover rows 10-15.
BODY_SHIRT = """
DMDLLLDLLDLLLDMD
DMDLLLLDDLLLLDMD
.DDLLLLLLLLLLDD.
.DMMDDDDDDDDMMD.
.DMMD......DMMD.
.DDDD......DDDD.
"""

BODY_SUIT = """
DMDDDDLMMLDDDDMD
DMDDDDDMMDDDDDMD
.DDDDDDMMDDDDDD.
.DMMDDDDDDDDMMD.
.DMMD......DMMD.
.DDDD......DDDD.
"""

BODY_CARDIGAN = """
DMDLLLLDDLLLLDMD
DMDLLLDMMDLLLDMD
.DDLDLDMMDLDLDD.
.DMMDDDDDDDDMMD.
.DMMD......DMMD.
.DDDD......DDDD.
"""

# Seated executives: head, shoulders (rows 10-12), table (rows 13-15).
TABLE = """
DDDDDDDDDDDDDDDD
LLLLLLLLLLLLLLLL
DDDDDDDDDDDDDDDD
"""

SHOULDERS_SUIT = """
DDDDDLLMMLLDDDDD
DDDDDDLMMLDDDDDD
DDDDDDDMMDDDDDDD
"""

SHOULDERS_HOODIE = """
DDDLLLLLLLLLLDDD
DDDDLLDLLDLLDDDD
DDDDDLDLLDLDDDDD
"""

SWEAT = """
?D?
DLD
DLD
?D?
"""

# --- Level 3: Open-Plan Office --------------------------------------------

COFFEE_CUP = """
?L?L
DDDD
DLLD
DLLD
?DD?
"""

LAPTOP_SLAB = """
DDD
DLD
DLD
DLD
DLD
DDD
"""

STICKY = """
DDDDD
DLLLD
DDLDD
DLLLD
DDDDD
"""

EMAIL = """
................
................
................
....DDDDDDDDDDD.
.DD.DDLLLLLLLDD.
....DLDLLLLLDLD.
DDD.DLLDLLLDLLD.
....DLLLDLDLLLD.
.DD.DLLLLDLLLLD.
....DLLLLLLLLLD.
....DDDDDDDDDDD.
................
................
................
................
................
"""

STORM_CLOUD = """
................................
................................
..........DDDDD.................
.....DDDDDMMMMMDD....DDDDD......
....DMMMMMMMMMMMMDDDDMMMMMD.....
...DMMMMMMMMMMMMMMMMMMMMMMMDD...
..DMMMMMMMMMMMMMMMMMMMMMMMMMMD..
.DMMMMMMMMMMMMMMMMMMMMMMMMMMMMD.
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMMMMMMMMMMMMMMMMMD.
..DDMMMMMDDMMMMMMMMDDMMMMMMMDD..
....DDDDD..DDDDDDDD..DDDDDDD....
................................
................................
................................
................................
................................
................................
................................
................................
................................
................................
................................
"""

ENVELOPE = """
DDDDDDDD
DDLLLLDD
DLDLLDLD
DLLDDLLD
DDDDDDDD
"""

STORM_EYES = """
DDD??????????DDD
DLLDD??????DDLLD
DLLLLD????DLLLLD
?DLLLD????DLLLD?
??DDD??????DDD??
"""

STORM_FROWN = """
??DDDDDD??
?D??????D?
"""

STORM_ROAR = """
?DDDDDDDD?
DLDLDLDLDD
DDDDDDDDDD
?DDDDDDDD?
"""

STORM_SPIRAL = """
?DD?????????DD?
DLDD???????DDLD
DLLD???????DLLD
?DD?????????DD?
"""

STORM_WAVY = """
D?D?D?D?D
?D?D?D?D?
"""

BOLT = """
??DDDD
?DLLD?
?DLD??
DLLDDD
DLLLLD
DDDLD?
??DLD?
?DLD??
?DD???
"""

DROP = """
?D?
DLD
?D?
"""

MINI_STORM_A = """
................
................
......DDDD......
...DDDMMMMDDD...
..DMMMMMMMMMMMD.
.DMMMMMMMMMMMMMD
DMMDDMMMMMMDDMMD
DMMMLDMMMMDLMMMD
DMMMLLDMMDLLMMMD
DMMMMMMMMMMMMMMD
DMMMMMDDDDMMMMMD
.DMMMDMMMMDMMMD.
..DDDDDDDDDDDD..
................
................
................
"""

MINI_STORM_B = """
................
......DDDD......
...DDDMMMMDDD...
..DMMMMMMMMMMMD.
.DMMMMMMMMMMMMMD
DMMDDMMMMMMDDMMD
DMMMLDMMMMDLMMMD
DMMMLLDMMDLLMMMD
DMMMMMMMMMMMMMMD
DMMMMDDDDDDMMMMD
.DMMMDLDLDLDMMD.
..DDDDDDLDDDDD..
.......DLD......
......DLD.......
......DLLD......
.......DD.......
"""

ITEM_HEADPHONES = """
................
.....DDDDDD.....
...DDMMMMMMDD...
..DMMDDDDDDMMD..
.DMDD......DDMD.
.DMD........DMD.
.DMD........DMD.
DDDDD......DDDDD
DMMLD......DLMMD
DMMLD......DLMMD
DMMLD......DLMMD
DMMLD......DLMMD
DMMLD......DLMMD
.DDDD......DDDD.
................
................
"""

# --- Level 4: HR ------------------------------------------------------------

TEACUP = """
DDDDDD?
DLLLLDD
DLLLLDD
?DDDD??
DDDDDDD
"""

TAPE_A = """
................
................
................
...DDDDD........
.DDMMMMMDD......
.DMLLMMMMMD.....
DMLMMDDDMMMD....
DMLMDLLLDMMDDDD.
DMMMDLDLDMMMMMMD
DMMMDLLLDMMDDDMD
DMMMMDDDMMMD.DMD
.DMMMMMMMMD..DMD
.DDMMMMMDD..DMD.
...DDDDD...DLLD.
...........DDD..
................
"""

TAPE_B = """
................
............DDD.
...........DLLD.
...DDDDD...DMD..
.DDMMMMMDD.DMD..
.DMLLMMMMMDDMD..
DMLMMDDDMMMMMD..
DMLMDLLLDMMDD...
DMMMDLDLDMMD....
DMMMDLLLDMMD....
DMMMMDDDMMMD....
.DMMMMMMMMD.....
.DDMMMMMDD......
...DDDDD........
................
................
"""

NECK = """
?DDDD?
DMMMMD
DDDDDD
DMMMMD
DDDDDD
DMMMMD
"""

CABINET_TOP = """
...DDDDDDDDDDDDDDDDDDDDDDDDDD...
...DLLLLLLLLLLLLLLLLLLLLLLLLD...
...DMMMMMMMMMMMMMMMMMMMMMMMMD...
"""

DRAWER = """
...DLDDDDDDDDDDDDDDDDDDDDDDLD...
...DLDLLLLLLDDDDDDDDLLLLLLDLD...
...DLDLLLLLLDLLLLLLDLLLLLLDLD...
...DLDLLLLLLDDDDDDDDLLLLLLDLD...
...DLDLLLLLLLDMMMMDLLLLLLLDLD...
...DLDMMMMMMMMMMMMMMMMMMMMDLD...
"""

CABINET_FOOT = """
...DDDDDDDDDDDDDDDDDDDDDDDDDD...
...DDD..................DDD.....
"""

SHAKE = """
D
?
D
D
?
D
"""

FLYING_PAGES = """
??DDDD???????
?DLLLLD??DDD?
?DLDDLD?DLLLD
??DLLLD?DLDLD
???DDD???DDD?
"""

BINDER_A = """
................
..DDDDDDDDDDDD..
.DDMMMMMMMMMMMD.
DLDMMMMMMMMMMMD.
.DDMLLLLLLLLMMD.
DLDMLDDDDDDLMMD.
.DDMLLLLLLLLMMD.
DLDMMMMMMMMMMMD.
.DDMDDMMMMDDMMD.
DLDMMLDMMDLMMMD.
.DDMMDDMMDDMMMD.
DLDMMMMMMMMMMMD.
.DDMMMDDDDMMMMD.
..DDDDDDDDDDDDD.
................
................
"""

BINDER_B = """
................
..DDDDDDDDDDDD..
LDDMMMMMMMMMMMD.
DLDMMMMMMMMMMMD.
LDDMLLLLLLLLMMD.
DLDMLDDDDDDLMMD.
LDDMLLLLLLLLMMD.
DLDMDDMMMMDDMMD.
LDDMMLDMMDLMMMD.
DLDMMDDMMDDMMMD.
LDDMDDDDDDDDMMD.
DLDMDLDLDLDDMMD.
LDDMDDDDDDDDMMD.
..DDDDDDDDDDDDD.
................
................
"""

BINDER_C = """
................
....DD....DD....
...DLLD..DLLD...
...DLLLDDLLLD...
..DLLLLDDLLLLD..
..DLDDLDDLDDLD..
.DLLLLLDDLLLLLD.
.DLDDDLDDLDDDLD.
DLLLLLLDDLLLLLLD
DDDDDDDDDDDDDDDD
DMMMMMMDDMMMMMMD
DMDDDMMDDMMDDDMD
DMDLDMMDDMMDLDMD
DMDDDMMDDMMDDDMD
DMMMMMMDDMMMMMMD
DDDDDDDDDDDDDDDD
"""

POLICY_DOC = """
................
....DDDDDDDDD...
.DD.DLLLLLLLDD..
....DLDDDDDLDLD.
DDD.DLLLLLLLDDDD
....DLDDDDDDDLLD
.DD.DLLLLLLLLLLD
....DLDDDDDDLLLD
....DLLLLLLLLLLD
....DLLLLMMMMLLD
....DLLLMMLLMMLD
....DLLLMLMMLMLD
....DLLLMMLLMMLD
....DLLLLMMMMLLD
....DDDDDDDDDDDD
................
"""

ITEM_KEYCARD = """
................
................
..DDDDDDDDDDDD..
.DMMMMMDDMMMMMD.
.DMMMMMMMMMMMMD.
.DLLLLLLLLLLLLD.
.DLDDDDLLLLLLLD.
.DLDMMDLDDDDLLD.
.DLDMMDLLLLLLLD.
.DLDDDDLDDDLLLD.
.DLLLLLLLLLLLLD.
..DDDDDDDDDDDD..
................
................
................
................
"""

ITEM_FOLDER = """
................
.DDDDDD.........
.DLLLLLDDDDDDDD.
.DLLLLLLLLLLLLD.
.DLDDDDDDDDDDLD.
.DLDLDDLDLDDLLD.
.DLDDDDDDDDDDLD.
.DLLLLLLLLLLLLD.
.DLLLLDDDDLLLLD.
.DLLLDMMMDDLLLD.
.DLLDMMMMLDDLLD.
.DLLDMMMMMMDLLD.
.DLLLDMMMMDLLLD.
.DLLLLDDDDLLLLD.
.DDDDDDDDDDDDDD.
................
"""

ITEM_STAMP = """
................
......DDDD......
.....DLLLLD.....
.....DLLLLD.....
......DDDD......
......DLLD......
....DDDDDDDD....
...DLLLLLLLLD...
...DDDDDDDDDD...
..DMMMMMMMMMMD..
..DDDDDDDDDDDD..
................
.DDDDDDDDDDDDDD.
.DLMLMMLMLMMLLD.
.DDDDDDDDDDDDDD.
................
"""

# --- Level 5: Server Room ----------------------------------------------------

KEVIN_FACE_SMILE = """
MMMMMMMMMMMMMMMMMMMM
MMMMMDDMMMMMMDDMMMMM
MMMDDMMMMMMMMMMDDMMM
MMMMMMMMMMMMMMMMMMMM
MMMMLDDMMMMMMLDDMMMM
MMMMDDDMMMMMMDDDMMMM
MMMMDDDMMMMMMDDDMMMM
MMMMMMMMMMMMMMMMMMMM
MMMMMMMDMMMMDMMMMMMM
MMMMMMMMDDDDMMMMMMMM
MMMMMMMMMMMMMMMMMMMM
MMMMMMMMMMMMMMMMMMMM
"""

KEVIN_FACE_TALK = """
MMMMMMMMMMMMMMMMMMMM
MMMMMDDMMMMMMDDMMMMM
MMMDDMMMMMMMMMMDDMMM
MMMMMMMMMMMMMMMMMMMM
MMMMLDDMMMMMMLDDMMMM
MMMMDDDMMMMMMDDDMMMM
MMMMDDDMMMMMMDDDMMMM
MMMMMMMMMMMMMMMMMMMM
MMMMMMMMDDDDMMMMMMMM
MMMMMMMDDLLDDMMMMMMM
MMMMMMMMDDDDMMMMMMMM
MMMMMMMMMMMMMMMMMMMM
"""

KEVIN_FACE_HAPPY = """
MMMMMMMMMMMMMMMMMMMM
MMMMMMMMMMMMMMMMMMMM
MMMMMMMMMMMMMMMMMMMM
MMMMMDMMMMMMMMDMMMMM
MMMMDMDMMMMMMDMDMMMM
MMMDMMMDMMMMDMMMDMMM
MMMMMMMMMMMMMMMMMMMM
MMMMMMMMMMMMMMMMMMMM
MMMMMDMMMMMMMMDMMMMM
MMMMMMDDDDDDDDMMMMMM
MMMMMMMDLLLLDMMMMMMM
MMMMMMMMDDDDMMMMMMMM
"""

SPARKLE = """
??D??
?DLD?
DLLLD
?DLD?
??D??
"""

FLAME_A = """
......D.........
.....DLD........
.....DLD....D...
....DMLMD..DLD..
....DMMMD..DLD..
.D..DMMMMDDMMD..
DLD.DMMMMMMMMD..
DMMDMMMMMMMMMMD.
DMMMMMMMMMMMMMD.
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMD.
.DMMMMMMMMMMMMD.
..DDDDDDDDDDDD..
"""

FLAME_B = """
............D...
...D.......DLD..
..DLD......DLD..
..DLD..D...DMD..
..DMMDDLD.DMMD..
..DMMMDMD.DMMD..
.DMMMMMMMDMMMD..
.DMMMMMMMMMMMMD.
DMMMMMMMMMMMMMD.
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMD.
.DMMMMMMMMMMMMD.
..DDDDDDDDDDDD..
"""

USB = """
................
......DDDD......
.....DLLLLD.....
.....DLDDLD.....
.....DLLLLD.....
...DDDDDDDDDD...
...DMMMMMMMMD...
...DMDDMMDDMD...
...DMDDMMDDMD...
...DMMMMMMMMD...
...DMMDMMDMMD...
...DMMMDDMMMD...
...DMMMMMMMMD...
...DDDDDDDDDD...
................
................
"""

# --- Level 6: Executive Floor ------------------------------------------------

VISOR = """
DDDDDDDDDDDDDDDD
DLLLLLLLLLLLLLLD
"""

CALCULATOR = """
DDDDD
DLLLD
DLDLD
DLDLD
DDDDD
"""

SHADES = """
DDDDDDDDDDDDDDDD
DMDDLDDMMDDLDDMD
DMMDDDMMMMDDDMMD
"""

MEGAPHONE = """
????DDD
DDDDLLD
DLLLLLD
DDDDLLD
????DDD
"""

HEADSET = """
..DDDDDDDDDDDD..
"""

HEADSET_MIC = """
DD????????????DD
DLD??????????DLD
DD????????????DD
?D??????????????
??DDL???????????
"""

CLIPBOARD = """
??DD??
DDDDDD
DLLLLD
DLDDLD
DLLLLD
DLDDLD
"""

LAPTOP_BACK = """
DDDDDDDD
DLLLLLLD
DLLMMLLD
DLLMMLLD
DLLLLLLD
"""

SPREADSHEET = """
................
.DDDDDDDDDDDDDD.
.DLLLDLLLDLLLLD.
.DMMLDLLLDLLLLD.
.DLLMMLLLDLLLLD.
.DDDDMMDDDDDDDD.
.DLLLDMMLDLLLLD.
.DLLLDLMMDLLLLD.
.DLLLDLLMMLLLLD.
.DDDDDDDDMMDDDD.
.DLLLDLLLDMMLLD.
.DLLLDLLLDLMMMD.
.DLLLDLLLDLMMMD.
.DLLLDLLLDMMMMD.
.DDDDDDDDDDDDDD.
................
"""

HOLE_OPEN = """
................
..DDDD..DDDDD...
.DMMMMDDMMMMMD..
DMMMMMMMMMMMMMD.
DMMLMMMMMLMMMMMD
DMMMMMMMMMMMMMMD
DDMMMMMMMMMMMMDD
DDDDMMMDDMMMDDDD
DDDDDDDDDDDDDDDD
DDDDDDDDDDDDDDDD
DDDDDDDDDDDDDDDD
DDDDDDDDDDDDDDDD
.DDDDDDDDDDDDDD.
.DDDDDDDDDDDDDD.
..DDDD.DDD.DDD..
................
"""

BLAST = """
................
................
..........L.....
.....L.....L....
......L.....L...
..L....L....L...
...L...L.....L..
...L....L....L..
...L....L....L..
...L...L.....L..
..L....L....L...
......L.....L...
.....L.....L....
..........L.....
................
................
"""

STAFF_A = """
................
................
................
....DDD..DDD....
...DMMMDDMMMD...
..DMLLMMMMLLMD..
..DMLDMMMMDLMD..
..DMMMDMMDMMMD..
..DMDMMMMMMDMD..
..DMMDDDDDDMMD..
...DDMMMMMMDD...
.DMDLLLMMLLLDMD.
.DMDLLLMMLLLDMD.
.DDDDDDDDDDDDDD.
..DMD......DMD..
..DDD......DDD..
"""

STAFF_B = """
DDD..........DDD
DMD..........DMD
DMD..........DMD
DMD.DDD..DDD.DMD
DMDDMMMDDMMMDDMD
DMDMLLMMMMLLMDMD
DMDMLDMMMMDLMDMD
DMDMMMDMMDMMMDMD
DMDMDDDDDDDDMDMD
DMDMMDLLLLDMMDMD
DMDDDMMMMMMDDDMD
.DDDLLLMMLLLDDD.
..DDLLLMMLLLDD..
..DMDDDDDDDDMD..
..DMD......DMD..
..DDD......DDD..
"""


def quick_sync_frames():
    a = frame(FROG_TOP, FACE_SMILE, BODY_SHIRT)
    a = overlay(a, COFFEE_CUP, 0, 10)
    a = overlay(a, LAPTOP_SLAB, 13, 9)
    b = frame(FROG_TOP, FACE_EAGER, BODY_SHIRT)
    b = overlay(b, COFFEE_CUP, 0, 8)
    b = overlay(b, LAPTOP_SLAB, 13, 9)
    return [a, shift(b, dy=1)]


def standup_frames():
    a = overlay(frame(FROG_TOP, FACE_SMILE, BODY_SHIRT), STICKY, 11, 10)
    b = overlay(frame(FROG_TOP, FACE_TALK, BODY_SHIRT), STICKY, 11, 9)
    return [a, b]


def reply_storm_frames():
    cloud = parse(STORM_CLOUD, 32, 32)
    for x, y in ((4, 2), (19, 2), (0, 11), (24, 9), (3, 18), (21, 18)):
        cloud = overlay(cloud, ENVELOPE, x, y)
    idle = overlay(cloud, STORM_EYES, 8, 8)
    idle = overlay(idle, STORM_FROWN, 11, 15)
    send = overlay(cloud, STORM_EYES, 8, 7)
    send = overlay(send, STORM_ROAR, 11, 14)
    send = overlay(send, BOLT, 6, 21)
    send = overlay(send, BOLT, 21, 21)
    send = overlay(send, BOLT, 13, 22)
    low = shift(cloud, dy=4)
    low = overlay(low, STORM_SPIRAL, 9, 13)
    low = overlay(low, STORM_WAVY, 12, 19)
    for x, y in ((6, 27), (15, 29), (24, 27)):
        low = overlay(low, DROP, x, y)
    return [idle, send, low]


def hr_frames():
    a = overlay(frame(FROG_TOP, FACE_KIND, BODY_CARDIGAN), TEACUP, 5, 10)
    b = overlay(frame(FROG_TOP, FACE_GLANCE, BODY_CARDIGAN), TEACUP, 5, 10)
    b = overlay(b, SWEAT, 13, 1)
    return [a, b]


def hydra_frames():
    rows = ["." * 32] * 3
    top = ["." * 32 for _ in range(6)]
    for x in (5, 13, 21):
        top = overlay(top, NECK, x, 0)
    rows += top
    rows += rows_of(CABINET_TOP) + rows_of(DRAWER) * 3 + rows_of(CABINET_FOOT)
    body = frame("\n".join(rows), w=32, h=32)
    hurt = shift(body, dx=1)
    # Jolted sideways, papers fly out of the top, shake marks at the sides.
    hurt = overlay(hurt, FLYING_PAGES, 9, 0)
    for x, y in ((0, 12), (31, 12), (0, 22), (31, 22)):
        hurt = overlay(hurt, SHAKE, x, y)
    return [body, hurt]


def kevin_frames():
    case = ["." * 32] * 3
    case.append("..DDDDDDDDDDDDDDDDDDDDDDDDDDDD..")
    case.append("..DLLLLLLLLLLLLLLLLLLLLLLLLLLD..")
    case.append("..DLL" + "D" * 22 + "LLD..")
    case += ["..DLLD" + "M" * 20 + "DLLD.."] * 14
    case.append("..DLL" + "D" * 22 + "LLD..")
    case.append("..DLLLLLLLLLLLLLLLLLLLLLLLLLLD..")
    case.append("..D" + "L" * 18 + "DMDLDMDLD..")
    case.append("..DDDDDDDDDDDDDDDDDDDDDDDDDDDD..")
    case.append("............DLLLLLLD............")
    case.append("............DLLLLLLD...DDD......")
    case.append("........DDDDDDDDDDDDDDDDLD......")
    case.append(".......DLLLLLLLLLLLLLLLLDMD.....")
    case.append(".......DDDDDDDDDDDDDDDDDDMD.....")
    case.append("......................DMMD......")
    case.append("......................DMD.......")
    case.append("................................")
    body = frame("\n".join(case), w=32, h=32)
    idle = overlay(body, KEVIN_FACE_SMILE, 6, 7)
    talk = overlay(body, KEVIN_FACE_TALK, 6, 7)
    happy = overlay(body, KEVIN_FACE_HAPPY, 6, 7)
    for x, y in ((0, 0), (27, 0), (0, 22), (27, 24)):
        happy = overlay(happy, SPARKLE, x, y)
    return [idle, talk, happy]


def exec_frames(props):
    """Three seated frames: idle, attacking, flustered. `props` adds the
    character's silhouette pieces per frame as (patch, x, y) lists."""
    faces = (FACE_SMILE, FACE_SHOUT, FACE_FLUSTER)
    shoulders = props.get("shoulders", SHOULDERS_SUIT)
    out = []
    for face, extra in zip(faces, props["frames"]):
        f = frame(FROG_TOP, face, shoulders, TABLE)
        for patch, x, y in extra:
            f = overlay(f, patch, x, y)
        out.append(f)
    return out


CFO = {
    "frames": [
        [(VISOR, 0, 1), (CALCULATOR, 11, 9)],
        [(VISOR, 0, 1), (CALCULATOR, 11, 4)],
        [(VISOR, 0, 2), (CALCULATOR, 11, 10), (SWEAT, 0, 4)],
    ]
}
CMO = {
    "frames": [
        [(SHADES, 0, 3), (MEGAPHONE, 0, 9)],
        [(SHADES, 0, 3), (MEGAPHONE, 9, 6)],
        [(SHADES, 0, 6), (MEGAPHONE, 0, 10), (SWEAT, 13, 0)],
    ]
}
COO = {
    "frames": [
        [(HEADSET, 0, 0), (HEADSET_MIC, 0, 4), (CLIPBOARD, 10, 8)],
        [(HEADSET, 0, 0), (HEADSET_MIC, 0, 4), (CLIPBOARD, 10, 3)],
        [(HEADSET, 0, 0), (HEADSET_MIC, 0, 4), (FLYING_PAGES, 3, 9), (SWEAT, 13, 0)],
    ]
}
CTO = {
    "shoulders": SHOULDERS_HOODIE,
    "frames": [
        [(LAPTOP_BACK, 8, 9)],
        [(LAPTOP_BACK, 8, 8)],
        [(LAPTOP_BACK, 8, 10), (SWEAT, 0, 3)],
    ],
}


def ceo_head():
    """Brock's head and suit from assets/sprites/ceo.png (frame 0, rows 0-12)."""
    img = Image.open(ROOT / "assets/sprites/ceo.png").convert("RGB")
    key = {v: k for k, v in GBS.items()}
    return ["".join(key[img.getpixel((x, y))] for x in range(16)) for y in range(13)]


BROCK_SHOUT = """
DMDDDDMMMMDDDDMD
DDLLDLDMMDLLDLDD
DMDDDDMMMMDDDDMD
DMMMMMMMMMMMMMMD
DMMMDDDDDDDDMMMD
DMMMDLDDDDLDMMMD
DMMMDDDDDDDDMMMD
.DDMMMMMMMMMMDD.
"""

BROCK_SWEAT = """
DMMDDDDMMMMDDDMD
DMDDLLDMMDDLLDDD
DMMDDDDMMMMDDDMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMMMMMMMMMMMMMD
DMMDMDMDMDMDMMMD
.DDMMMMMMMMMMDD.
"""


def brock_frames():
    head = ceo_head()
    idle = frame("\n".join(head), TABLE)
    shout = overlay(idle, BROCK_SHOUT, 0, 3)
    sweat = overlay(idle, BROCK_SWEAT, 0, 3)
    sweat = overlay(sweat, SWEAT, 0, 0)
    sweat = overlay(sweat, SWEAT, 13, 1)
    return [idle, shout, sweat]


def hole_frames():
    warn = []
    for y in range(16):
        line = ""
        for x in range(16):
            edge = x < 2 or x > 13 or y < 2 or y > 13
            line += ("D" if ((x + y) // 2) % 2 else "L") if edge else "."
        warn.append(line)
    return [warn, parse(HOLE_OPEN)]


def yes_man_frames():
    a = frame(FROG_TOP, FACE_SMILE, BODY_SUIT)
    head = frame(FROG_TOP, FACE_CLOSED, BODY_SUIT)[:10]
    b = ["." * 16] + head + rows_of(BODY_SUIT)[1:]
    return [a, frame("\n".join(b))]


SPRITES = {
    "roomba": [parse(ROOMBA_A), parse(ROOMBA_B)],
    "tangled_cable": [parse(CABLE_A), parse(CABLE_B)],
    "printer": [parse(PRINTER_IDLE, 32, 32), parse(PRINTER_JAM, 32, 32)],
    "paper": [parse(PAPER)],
    "tongue": tongue_frames(TONGUE_DOWN),
    "hud_coffee": hud_frames(),
    "warning": [parse(WARNING), [r.replace("L", "M") for r in parse(WARNING)]],
    "cable_hook": actor(HOOK_DOWN),
    "it_guy": [parse(IT_A), parse(IT_B)],
    "crt": [parse(CRT_A), parse(CRT_B)],
    "chest": [parse(CHEST_CLOSED), parse(CHEST_OPEN)],
    "item_cable": [parse(ITEM_CABLE)],
    "item_key": [parse(ITEM_KEY)],
    "item_password": [parse(ITEM_PASSWORD)],
    "item_map": [parse(ITEM_MAP)],
    "item_mug": [parse(ITEM_MUG)],
    # Level 2: Break Room.
    "sugar_ant": [parse(ANT_A), parse(ANT_B)],
    "tupperware": [parse(TUPPER_A), parse(TUPPER_B)],
    "espresso": espresso_frames(),
    "coffee_pod": [parse(POD)],
    "steam": [parse(STEAM_A), parse(STEAM_B)],
    "cracked_wall": [parse(CRACKED_WALL)],
    "coffee_happy": [parse(SAD_A), parse(SAD_B)],
    "receptionist": [parse(DESK_A), parse(DESK_B)],
    "item_badge": [parse(ITEM_BADGE)],
    "item_po": [parse(ITEM_PO)],
    "bufo_dash": [parse(DASH_DOWN), parse(DASH_UP), parse(DASH_RIGHT)],
    # Level 3: Open-Plan Office.
    "quick_sync": quick_sync_frames(),
    "standup_frog": standup_frames(),
    "email": [parse(EMAIL)],
    "reply_storm": reply_storm_frames(),
    "mini_storm": [parse(MINI_STORM_A), parse(MINI_STORM_B)],
    "item_headphones": [parse(ITEM_HEADPHONES)],
    # Level 4: HR.
    "hr_frog": hr_frames(),
    "red_tape": [parse(TAPE_A), parse(TAPE_B)],
    "hydra_body": hydra_frames(),
    "binder_head": [parse(BINDER_A), parse(BINDER_B), parse(BINDER_C)],
    "policy_doc": [parse(POLICY_DOC)],
    "item_keycard": [parse(ITEM_KEYCARD)],
    "item_folder": [parse(ITEM_FOLDER)],
    "item_stamp": [parse(ITEM_STAMP)],
    # Level 5: Server Room.
    "kevin": kevin_frames(),
    "firewall": [brickify(parse(FLAME_A)), brickify(parse(FLAME_B))],
    "kevin_usb": [parse(USB), shift(parse(USB), dy=-1)],
    # Level 6: Executive Floor.
    "yes_man": yes_man_frames(),
    "board_cfo": exec_frames(CFO),
    "board_cmo": exec_frames(CMO),
    "board_coo": exec_frames(COO),
    "board_cto": exec_frames(CTO),
    "brock_seated": brock_frames(),
    "spreadsheet": [parse(SPREADSHEET)],
    "hole": hole_frames(),
    "megaphone_blast": [outlined(parse(BLAST))],
    # Ending.
    "staff_frog": [parse(STAFF_A), parse(STAFF_B)],
}

# Sprites that must have no transparent pixels.
OPAQUE = {"cracked_wall"}


def hexrgb(h):
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


def palette_colors(name):
    light, mid, dark = (hexrgb(c) for c in PALETTES[name])
    return {".": None, "D": dark, "M": mid, "L": light}


def render(frames, colors, scale=1, bg=None):
    fh = len(frames[0])
    fw = len(frames[0][0])
    img = Image.new("RGBA", (fw * len(frames) * scale, fh * scale), bg or (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for f, rows in enumerate(frames):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                c = colors[ch]
                if c is None:
                    continue
                x0 = (f * fw + x) * scale
                y0 = y * scale
                draw.rectangle([x0, y0, x0 + scale - 1, y0 + scale - 1], fill=(*c, 255))
    return img


def main():
    out = ROOT / "assets/sprites"
    out.mkdir(parents=True, exist_ok=True)
    allowed = set(GBS.values())
    for name, frames in SPRITES.items():
        sheet = render(frames, GBS).convert("RGB")
        sheet.save(out / f"{name}.png")
        used = {sheet.getpixel((x, y)) for x in range(sheet.width) for y in range(sheet.height)}
        assert used <= allowed, (name, used)
        if name in OPAQUE:
            assert GBS["."] not in used, f"{name} must be fully opaque"
        print(f"{name}.png OK: {sheet.size} frames: {len(frames)} colors: {len(used)}")

    (out / "palettes.json").write_text(json.dumps(PALETTES, indent=2) + "\n")

    # Preview: one row per sprite, 8x scale, suggested palette, floor color.
    scale, pad, label_h = 8, 8, 14
    gap = 4 * scale // 8
    blocks = []
    for name, frames in SPRITES.items():
        frames_img = [render([f], palette_colors(name), scale) for f in frames]
        blocks.append((f"{name}  ({len(frames)} frame{'s' if len(frames) > 1 else ''})", frames_img))
    # Wrap long strips (the HUD) so no row is wider than the widest sprite.
    max_row = 64 * scale * 2 + gap * 2
    wrapped = []
    for label, imgs in blocks:
        lines, line, w = [], [], 0
        for im in imgs:
            if line and w + im.width > max_row:
                lines.append(line)
                line, w = [], 0
            line.append(im)
            w += im.width + gap
        lines.append(line)
        wrapped.append((label, lines))
    col_w = max_row + 2 * pad
    heights = [
        label_h + sum(ln[0].height + gap for ln in lines) + pad for _, lines in wrapped
    ]
    blocks = wrapped
    half = (len(blocks) + 1) // 2
    col_h = max(sum(heights[:half]), sum(heights[half:])) + pad
    preview = Image.new("RGB", (col_w * 2, col_h), FLOOR)
    draw = ImageDraw.Draw(preview)
    for i, (label, lines) in enumerate(blocks):
        col = 0 if i < half else 1
        y = pad + sum(heights[(0 if col == 0 else half) : i])
        draw.text((col * col_w + pad, y), label, fill=(255, 255, 255))
        y += label_h
        for line in lines:
            x = col * col_w + pad
            for im in line:
                preview.paste(im, (x, y), im)
                x += im.width + gap
            y += line[0].height + gap
    preview.save(ROOT / "previews/sprites-preview.png")
    print("preview:", preview.size)


if __name__ == "__main__":
    main()
