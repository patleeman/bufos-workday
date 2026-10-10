"""Build Level 2, the Break Room floor, plus the Pondcorp Lobby hub, for GB
Studio (Color Only, automatic palettes).

Same shape as make_it_basement.py: ROOMS = {name: (gx, gy, title, layout)}
with 10x9 metatile layouts (16x16 px each, 160x144 per room), and
TILES = {char: (builder, solid)}. Builders take (x, y) in metatiles; the
room being drawn (its rows and floor type) is held in CTX while rendering.

Doors work like the basement: north/south doors at columns 4-5 of the top or
bottom row, east/west doors at row 4, column 0 or 9.
  d  door (walkable)
  B  boss door (top row, columns 4-5)
  w  cracked wall door: drawn as cracked plaster, walkable (a breakable actor
     sits on it)
  E  elevator doors (walkable trigger)
  S  stairs down to the basement (lobby only, walkable)
  C  chest spot (drawn as floor)

validate() checks GB Studio's rules per image: at most 4 colors per 8x8 tile,
every tile inside one of the named 4-color palettes in PAL, at most 8 of those
palettes per image, at most 384 unique tiles.

Outputs:
  assets/backgrounds/break_<room>.png   one per room in ROOMS
  assets/backgrounds/lobby.png          the standalone lobby
  previews/break-room-preview.png       2x floor overview with Bufo
  previews/break-room-collision.txt     which tiles are solid
"""

import math
import random
from collections import deque
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent


def hexc(h):
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


COL = {
    "K": "#0f131a",  # ink
    "W": "#f8f4e8",  # warm white
    "w": "#e4cf9c",  # beige wall
    "v": "#a88a58",  # wall top, plaster shadow
    "l": "#d4dcb4",  # sage linoleum
    "m": "#a8b48c",  # linoleum grout
    "C": "#b8704a",  # terracotta carpet
    "c": "#8e5038",  # carpet weave
    "t": "#a06a3c",  # wood
    "n": "#5a3420",  # dark wood, coffee
    "o": "#c89a5c",  # cardboard, burlap
    "S": "#7c8494",  # steel
    "L": "#c8ccd0",  # light steel
    "R": "#c83838",  # red
    "Y": "#f0c030",  # yellow, gold
    "B": "#58a8e0",  # blue, water, screens
    "G": "#78b848",  # green
    "g": "#2e6a30",  # dark green
    "M": "#e0dcd8",  # marble
    "V": "#a8a0a8",  # marble vein
}
RGB = {k: hexc(v) for k, v in COL.items()}

# Named 4-color palettes. Each room may use at most 8 of them.
PAL = {
    # structure
    "wall": "KvwW",
    "wall_red": "KwWR",
    "wall_blue": "KwWB",
    "wall_yellow": "KwWY",
    "wall_green": "KwWG",
    "chalk": "KtwW",
    # floors
    "lino": "Kmln",
    "carpet": "KcCY",
    "wood": "Kntv",
    "marble": "KVMW",
    # props over plain floor
    "steel_lino": "KSLl",
    "wood_lino": "Ktnl",
    "paper_lino": "KWLl",
    "couch": "KgGC",
    "pingpong": "KGWC",
    "cooler": "KBWC",
    "trash_carpet": "KSLC",
    "boxes": "KonC",
    "bench": "KtnC",
    "sack": "Kont",
    "cups": "KWLt",
    "plant_marble": "KgGM",
    "desk_marble": "KtnM",
    # full-cover props (no floor showing)
    "shelf": "KnYR",
    "label": "KnRW",
    "counter": "KLtn",
    "sink": "KLSB",
    "boss_door": "KntY",
    "fridge": "KWLS",
    "steel_gold": "KSLY",
    "vend": "KRYL",
    "drinks": "KBWL",
    "claw": "KYBW",
    "noodles": "KWRn",
}
PAL_RGB = {k: frozenset(RGB[c] for c in v) for k, v in PAL.items()}

FLOORS = {
    "lino": ("l", "m"),
    "carpet": ("C", "c"),
    "wood": ("t", "n"),
    "marble": ("M", "V"),
}

# The room being drawn: its rows and floor type. Set by render_room().
CTX = {"rows": None, "floor": "carpet"}


# --- grid helpers -----------------------------------------------------------


def blank(c, w=16, h=16):
    return [[c] * w for _ in range(h)]


def paint(g, art, top=0, left=0):
    """Paint letter art over a char grid. '.' is transparent."""
    for y, row in enumerate(art.strip("\n").splitlines()):
        for x, ch in enumerate(row):
            if ch != "." and 0 <= top + y < len(g) and 0 <= left + x < len(g[0]):
                g[top + y][left + x] = ch
    return g


def flip(g):
    return [row[::-1] for row in g]


FONT = {
    "A": [".K.", "K.K", "KKK", "K.K", "K.K"],
    "B": ["KK.", "K.K", "KK.", "K.K", "KK."],
    "C": [".KK", "K..", "K..", "K..", ".KK"],
    "D": ["KK.", "K.K", "K.K", "K.K", "KK."],
    "E": ["KKK", "K..", "KK.", "K..", "KKK"],
    "F": ["KKK", "K..", "KK.", "K..", "K.."],
    "G": [".KK", "K..", "K.K", "K.K", ".KK"],
    "H": ["K.K", "K.K", "KKK", "K.K", "K.K"],
    "I": ["KKK", ".K.", ".K.", ".K.", "KKK"],
    "K": ["K.K", "K.K", "KK.", "K.K", "K.K"],
    "L": ["K..", "K..", "K..", "K..", "KKK"],
    "M": ["K...K", "KK.KK", "K.K.K", "K...K", "K...K"],
    "N": ["K..K", "KK.K", "K.KK", "K..K", "K..K"],
    "O": [".K.", "K.K", "K.K", "K.K", ".K."],
    "P": ["KK.", "K.K", "KK.", "K..", "K.."],
    "R": ["KK.", "K.K", "KK.", "K.K", "K.K"],
    "S": [".KK", "K..", ".K.", "..K", "KK."],
    "T": ["KKK", ".K.", ".K.", ".K.", ".K."],
    "U": ["K.K", "K.K", "K.K", "K.K", "KKK"],
    "V": ["K.K", "K.K", "K.K", "K.K", ".K."],
    "W": ["K...K", "K...K", "K.K.K", "KK.KK", "K...K"],
    "X": ["K.K", "K.K", ".K.", "K.K", "K.K"],
    "Y": ["K.K", "K.K", ".K.", ".K.", ".K."],
    "0": ["KKK", "K.K", "K.K", "K.K", "KKK"],
    "1": [".K.", "KK.", ".K.", ".K.", "KKK"],
    "2": ["KK.", "..K", ".K.", "K..", "KKK"],
    "3": ["KK.", "..K", ".K.", "..K", "KK."],
    "4": ["K.K", "K.K", "KKK", "..K", "..K"],
    "9": ["KKK", "K.K", "KKK", "..K", "KKK"],
    "$": [".K.", "KKK", "KK.", ".KK", "KKK"],
    "!": ["K", "K", "K", ".", "K"],
    "-": ["...", "...", "KKK", "...", "..."],
    " ": ["..", "..", "..", "..", ".."],
}


def text_width(text):
    return sum(len(FONT[ch][0]) + 1 for ch in text) - 1


def stamp(g, x, y, text, c):
    for ch in text:
        glyph = FONT[ch]
        for gy, row in enumerate(glyph):
            for gx, px in enumerate(row):
                if px == "K" and 0 <= y + gy < len(g) and 0 <= x + gx < len(g[0]):
                    g[y + gy][x + gx] = c
        x += len(glyph[0]) + 1
    return g


def stamp_center(g, y, text, c, x0=0, x1=None):
    x1 = len(g[0]) if x1 is None else x1
    return stamp(g, x0 + (x1 - x0 - text_width(text)) // 2, y, text, c)


def run_index(x, y, chars):
    """Position of (x, y) inside a horizontal run of the given chars."""
    row = CTX["rows"][y]
    i = 0
    while x - i - 1 >= 0 and row[x - i - 1] in chars:
        i += 1
    return i


def slice16(big, i):
    return [row[i * 16 : i * 16 + 16] for row in big]


def wide(art_fn, chars):
    """Builder for a multi-metatile decoration drawn as one wide grid."""

    def build(x, y):
        return slice16(art_fn(), run_index(x, y, chars))

    return build


# --- floors -----------------------------------------------------------------


def floor_base():
    return FLOORS[CTX["floor"]][0]


def plain(x=0, y=0):
    """Floor with no pattern: the base under props, so they only add K plus
    two colors of their own."""
    return blank(floor_base())


def floor(x, y):
    kind = CTX["floor"]
    base, pat = FLOORS[kind]
    g = blank(base)
    if kind == "lino":
        # 8 px kitchen tiles with grout lines
        for i in range(16):
            g[7][i] = g[15][i] = pat
            g[i][7] = g[i][15] = pat
        rnd = random.Random(x * 13 + y * 7)
        if rnd.random() < 0.3:
            g[3][3] = g[11][11] = pat
    elif kind == "carpet":
        horiz = (x + y) % 2 == 0
        for yy in range(16):
            for xx in range(16):
                a, b = (xx, yy) if horiz else (yy, xx)
                if b % 4 == 1 and a % 4 != 3:
                    g[yy][xx] = pat
    elif kind == "wood":
        # planks 4 px tall with staggered joints
        for yy in range(16):
            plank = yy // 4
            for xx in range(16):
                if yy % 4 == 3:
                    g[yy][xx] = pat
                elif xx == (plank * 7 + (x * 5 + y * 3) % 4 * 4 + 2) % 16:
                    g[yy][xx] = pat
    elif kind == "marble":
        v = (x * 3 + y * 5) % 4
        if v in (0, 2):
            off = 3 if v == 0 else 9
            for py in range(16):
                px = (py // 2 + off) % 15
                g[py][px] = pat
        elif v == 1:
            for py in range(4, 12):
                g[py][(20 - py) % 15] = pat
        for i in range(16):
            g[15][i] = pat
            g[i][15] = pat
        g[3][4] = g[4][5] = "W"
    return g


# --- walls ------------------------------------------------------------------


def wall(x=0, y=0):
    """Wall face: ink edge, white crown, beige plaster, white rail, baseboard."""
    g = blank("w")
    g[0] = ["K"] * 16
    g[1] = ["W"] * 16
    g[13] = ["W"] * 16
    g[14] = ["K"] * 16
    g[15] = ["K"] * 16
    return g


def wall_top(x, y):
    """Wall seen from above (side and bottom walls)."""
    g = blank("K")
    for i in range(16):
        g[3][i] = g[11][i] = "v"
    for i in range(4, 11):
        g[i][4] = "v"
    for i in list(range(0, 3)) + list(range(12, 16)):
        g[i][12] = "v"
    for i in range(16):
        if x == 0:
            g[i][15], g[i][14] = "w", "K"
        if x == 9:
            g[i][0], g[i][1] = "w", "K"
        if y == 8:
            g[0][i], g[1][i] = "w", "K"
    return g


def door(x, y):
    """Open doorway: the floor runs through between ink jambs."""
    g = floor(x, y)
    if y in (0, 8):
        left = x == 4
        for yy in range(16):
            for xx in ((0, 1, 2) if left else (13, 14, 15)):
                g[yy][xx] = "K"
    else:
        for xx in range(16):
            for yy in (0, 1, 2, 13, 14, 15):
                g[yy][xx] = "K"
    return g


def cracked_wall(x, y):
    """A doorway bricked up with cheap plaster, badly cracked. Walkable: a
    breakable actor sits on it."""
    g = wall()
    if y == 8:
        g = blank("w")
        g[0] = ["K"] * 16
        g[15] = ["K"] * 16
    left = x == 4
    for yy in range(16):
        g[yy][0 if left else 15] = "K"
        g[yy][1 if left else 14] = "v"
    crack = """
................
.......K........
.......K........
......KK........
......K.KK......
.....KK...K.....
....KvK....KK...
...KK.vK.....KK.
...K...K.......K
..KK...KK.......
..K.....K.......
.KK......KK.....
.K.........K....
................
"""
    art = paint(blank("."), crack, top=1)
    if not left:
        art = flip(art)
    for yy in range(16):
        for xx in range(16):
            if art[yy][xx] != ".":
                g[yy][xx] = art[yy][xx]
    # crumbs of plaster on the floor line
    g[12][4 if left else 11] = "v"
    g[12][9 if left else 6] = "v"
    return g


def boss_door(x, y):
    """Heavy wood double door to the Espresso Bar, a gold coffee bean on it."""
    left = x == 4
    art = """
KKKKKKKKKKKKKKKK
KnnnnnnnnnnnnnnK
KntttttttttttnnK
KntKKKKKKKKKtnnK
KntKttttttttKtnK
KntKtttKKKKttKtK
KntKttKYYYYKtKtK
KntKtKYYKYYYKKtK
KntKtKYYYKYYKKtK
KntKtKYYYKYYKKtK
KntKttKYYYKKtKtK
KntKtttKKKKttKtK
KntKttttttttKYYK
KntKKKKKKKKKKYYK
KnttttttttttttnK
KKKKKKKKKKKKKKKK
"""
    g = paint(blank("K"), art)
    return g if left else flip(g)


def elevator(x, y):
    """Brushed steel doors with a gold call light."""
    left = x == 4
    art = """
KKKKKKKKKKKKKKKK
KYYYKKKKKKKKKKKK
KYKYKSSSSSSSSSSK
KKKKKSLLLLLLLLSK
KSSSSSLSSSSSSLSK
KSLLLSLSLLLLSLSK
KSLSSSLSLSSLSLSK
KSLSSSLSLSSLSLSK
KSLSSSLSLSSLSLSK
KSLSSSLSLSSLSLSK
KSLSSSLSLSSLSLSK
KSLSSSLSLLLLSLSK
KSLSSSLSSSSSSLSK
KSLSSSLLLLLLLLSK
KSSSSSSSSSSSSSSK
KKKKKKKKKKKKKKKK
"""
    g = paint(blank("K"), art)
    # the two doors meet in the middle of the pair
    for yy in range(2, 15):
        g[yy][15] = "K"
    return g if left else flip(g)


def stairs(x, y):
    """Marble stairs down to the basement."""
    g = blank("M")
    for step in range(4):
        yy = step * 4
        for xx in range(16):
            g[yy][xx] = "K"
            g[yy + 1][xx] = "W"
            g[yy + 2][xx] = "M"
            g[yy + 3][xx] = "V" if step >= 2 else "M"
    left = x == 4
    for yy in range(16):
        g[yy][0 if left else 15] = "K"
        g[yy][1 if left else 14] = "V"
    return g


# --- wall decorations (row 0) -------------------------------------------------


def on_wall(art, top=2, left=0):
    return paint(wall(), art, top=top, left=left)


def big_wall(w_tiles):
    g = blank("w", 16 * w_tiles, 16)
    g[0] = ["K"] * len(g[0])
    g[1] = ["W"] * len(g[0])
    g[13] = ["W"] * len(g[0])
    g[14] = ["K"] * len(g[0])
    g[15] = ["K"] * len(g[0])
    return g


def framed_sign(w_tiles, fill="W", border="K", inset=2, top=2, bottom=12):
    g = big_wall(w_tiles)
    x0, x1 = inset, 16 * w_tiles - 1 - inset
    for yy in range(top, bottom + 1):
        for xx in range(x0, x1 + 1):
            edge = yy in (top, bottom) or xx in (x0, x1)
            g[yy][xx] = border if edge else fill
    return g, x0, x1


def art_menu():
    """Espresso Bar menu: absurd prices in chalk."""
    g, x0, x1 = framed_sign(3, fill="K", border="t", inset=1, top=2, bottom=13)
    for xx in range(x0, x1 + 1):
        g[1][xx] = "W"
    stamp(g, x0 + 3, 3, "LATTE", "W")
    stamp(g, x1 - 15, 3, "$400", "W")
    stamp(g, x0 + 3, 9 - 1, "WATER", "W")
    stamp(g, x1 - 15, 9 - 1, "$120", "W")
    for xx in range(x0 + 1, x1):
        g[13][xx] = "t"
    return g


def art_open_sign():
    """Red neon HOT sign on a black backing."""
    g = wall()
    paint(g, """
.KKKKKKKKKKKKKK.
.KKKKKKKKKKKKKK.
.KKKKKKKKKKKKKK.
.KKKKKKKKKKKKKK.
.KKKKKKKKKKKKKK.
.KKKKKKKKKKKKKK.
.KKKKKKKKKKKKKK.
.KKKKKKKKKKKKKK.
.....K....K.....
""", top=3)
    stamp(g, 3, 4, "HOT", "R")
    g[5][13] = "W"
    return g


def art_label_sign():
    """Pantry: LABEL YOUR FOOD."""
    g, x0, x1 = framed_sign(2, inset=2, top=2, bottom=12)
    stamp_center(g, 3, "LABEL", "K", x0, x1 + 1)
    stamp_center(g, 7 + 0, "FOOD!", "R" if False else "K", x0, x1 + 1)
    return g


def art_expired():
    """Fridge Room poster: a giant EXPIRED stamp."""
    g, x0, x1 = framed_sign(2, inset=2, top=2, bottom=12)
    for xx in range(x0 + 2, x1 - 1):
        g[4][xx] = g[10][xx] = "R"
    for yy in range(4, 11):
        g[yy][x0 + 2] = g[yy][x1 - 2] = "R"
    stamp_center(g, 5, "EXPIRED", "R", x0, x1 + 1)
    return g


def art_privilege():
    """Lounge: COFFEE IS A PRIVILEGE."""
    g, x0, x1 = framed_sign(3, inset=2, top=2, bottom=13)
    for xx in range(x0 + 1, x1):
        g[3][xx] = "R"
    stamp_center(g, 5, "COFFEE IS A", "K", x0, x1 + 1)
    stamp_center(g, 11 - 0, "PRIVILEGE", "R", x0, x1 + 1)
    return g


def art_tv():
    """Wall TV running a bouncing-logo screensaver (it never hits the corner)."""
    g = wall()
    paint(g, """
KKKKKKKKKKKKKKKK
KBBBBBBBBBBBBBBK
KBBBBBBBBBBBBBBK
KBBBBBWWWWBBBBBK
KBBBBBWKKWBBBBBK
KBBBBBWWWWBBBBBK
KBBBBBBBBBBBBBBK
KBBBBBBBBBBBBBBK
KKKKKKKKKKKKKKKK
......KKKK......
""", top=2)
    return g


def art_staff_only():
    g, x0, x1 = framed_sign(2, inset=3, top=2, bottom=12)
    stamp_center(g, 4, "STAFF", "K", x0, x1 + 1)
    for xx in range(x0 + 3, x1 - 2):
        g[10][xx] = "K"
    return g


def art_directory():
    """Floor directory, two tiles wide."""
    g, x0, x1 = framed_sign(2, fill="W", border="K", inset=1, top=1, bottom=14)
    for xx in range(x0 + 1, x1):
        g[2][xx] = "Y"
    stamp(g, x0 + 2, 3, "3 CEO", "K")
    stamp(g, x0 + 2, 9, "2 BREAK", "K")
    for xx in range(x0 + 1, x1):
        g[15][xx] = "K"
    return g


def art_pondcorp():
    """Pondcorp logo: a green lily pad and the name."""
    g, x0, x1 = framed_sign(3, fill="W", border="K", inset=1, top=2, bottom=13)
    pad = """
..KKKK..
.KGGGGK.
KGGGKGGK
KGGKGGGK
KGGGGGGK
.KGGGGK.
..KKKK..
"""
    paint(g, pad, top=4, left=x0 + 3)
    stamp(g, x0 + 13, 6, "PONDCORP", "K")
    for xx in range(x0 + 13, x1 - 2):
        g[12][xx] = "G"
    return g


def art_family():
    """Gold plaque: WE ARE A FAMILY."""
    g, x0, x1 = framed_sign(3, fill="Y", border="K", inset=3, top=2, bottom=13)
    stamp_center(g, 3, "WE ARE A", "K", x0, x1 + 1)
    stamp_center(g, 8, "FAMILY", "K", x0, x1 + 1)
    return g


# --- props --------------------------------------------------------------------


def on_floor(art, top=0, left=0):
    return paint(plain(), art, top=top, left=left)


def p_bean_sack(x, y):
    art = """
................
.....K....K.....
....KoK..KoK....
....KooKKooK....
...KoooooooK....
..KoonooonooK...
..KonoooooonK...
.KoooooooooooK..
.KooonoooooooK..
.KoooooKKooooK..
.KoooooKKKoonK..
.KooooooooooK.n.
..KKKKKKKKKK.n.n
..............n.
"""
    g = on_floor(art, top=1)
    return flip(g) if x % 2 else g


def p_cup_tower(x, y):
    return on_floor("""
......KKKK......
......KWWK......
......KLLK......
....KKKKKKKK....
....KWWKKWWK....
....KLLKKLLK....
..KKKKKKKKKKKK..
..KWWKKWWKKWWK..
..KLLKKLLKKLLK..
KKKKKKKKKKKKKKKK
KWWKKWWKKWWKKWWK
KLLKKLLKKLLKKLLK
KKKKKKKKKKKKKKKK
""", top=2)


def p_grinder(x, y):
    """Bean grinder on the floor: hopper of beans over a wooden base."""
    return on_floor("""
................
....KKKKKKKK....
....KttttttK....
....KtnnnntK....
....KttttttK....
.....KttttK.....
....KKKKKKKK....
....KnnnnnnK....
....KnKKKKnK....
....KnnnnnnK....
...KKKKKKKKKK...
...KttttttttK...
...KKKKKKKKKK...
""", top=1)


def p_shelf(x, y, brenda=False):
    """Pantry shelving full of snacks (full tile, no floor showing)."""
    g = blank("n")
    for xx in range(16):
        g[0][xx] = "K"
        g[15][xx] = "K"
        for yy in (5, 6, 11, 12):
            g[yy][xx] = "K"
    for yy in range(16):
        g[yy][0] = g[yy][15] = "K"
    rnd = random.Random(x * 7 + y * 3 + (99 if brenda else 0))
    for top in (1, 7):
        xx = 2
        while xx < 13:
            wdt = rnd.choice([2, 3, 3])
            hgt = rnd.choice([3, 4, 4])
            col = "R" if brenda else rnd.choice("YRYR")
            for yy in range(top + 4 - hgt, top + 4):
                for i in range(wdt):
                    if xx + i < 14:
                        g[yy][xx + i] = col
            if hgt > 2:
                g[top + 4 - hgt][xx] = "K" if col == "R" else g[top + 4 - hgt][xx]
            xx += wdt + 1
    if brenda:
        # big DO NOT EAT label taped across the shelf
        paint(g, """
KKKKKKKKKKKKKKKK
KWWWWWWWWWWWWWWK
KWWWWWWWWWWWWWWK
KWWWWWWWWWWWWWWK
KWWWWWWWWWWWWWWK
KWWWWWWWWWWWWWWK
KWWWWWWWWWWWWWWK
KWWWWWWWWWWWWWWK
KKKKKKKKKKKKKKKK
""", top=4)
        stamp(g, 3, 6, "NO!", "R")
    return g


def p_sugar(x, y):
    """Sugar sacks, slumped."""
    return on_floor("""
................
....KK....KK....
...KWWK..KWWK...
...KWLWKKWLWK...
..KWWWWWWWWWWK..
.KWWWWWWWWWWWWK.
.KWWKKKWWWWWWWK.
.KWKWWWWKWWWWLK.
.KWWKKWWKWWWWLK.
.KWWWWKWKWWWLLK.
.KWKKKWWWWWWLLK.
.KWWWWWWWWWLLLK.
..KKKKKKKKKKKK..
""", top=2)


def counter_base():
    """Counter against the wall: laminate top, wood cabinet doors below."""
    g = blank("L")
    for xx in range(16):
        g[7][xx] = "K"
        g[15][xx] = "K"
        for yy in range(8, 15):
            g[yy][xx] = "t"
    for yy in range(8, 15):
        g[yy][7] = g[yy][8] = "n"
        g[yy][0] = g[yy][15] = "K"
    g[11][5] = g[11][10] = "K"
    for xx in range(16):
        g[0][xx] = "K"
    return g


def p_counter(x, y):
    g = counter_base()
    rnd = random.Random(x + y * 5)
    if rnd.random() < 0.5:  # crumbs
        g[3][4] = g[4][9] = "n"
    return g


def p_sink(x, y):
    """Sink: steel basin with a little water. Refills health."""
    g = blank("L")
    paint(g, """
KKKKKKKKKKKKKKKK
LLLLLLLKKLLLLLLL
LLLLLLKLLKLLLLLL
LKKKKKKKKKKKKKKL
LKSSSSSSSSSSSSKL
LKSBBBBBBBBBBSKL
LKSBBBBBLBBBBSKL
KKKKKKKKKKKKKKKK
KSSSSSSSSSSSSSSK
KSLLLLLSSLLLLLSK
KSLSSSLSSLSSSLSK
KSLSSKLSSLKSSLSK
KSLSSSLSSLSSSLSK
KSLLLLLSSLLLLLSK
KSSSSSSSSSSSSSSK
KKKKKKKKKKKKKKKK
""")
    return g


def p_microwave(x, y):
    g = counter_base()
    paint(g, """
KKKKKKKKKKKKKKKK
KSSSSSSSSSSSSSSK
KSKKKKKKKKKSLLSK
KSKBBBBBBBKSLBSK
KSKBBBBBBBKSLLSK
KSKKKKKKKKKSLSSK
KSSSSSSSSSSSSSSK
KKKKKKKKKKKKKKKK
""")
    return g


def p_coffee_maker(x, y):
    """The dead coffee maker: unplugged, a dried ring in the pot."""
    g = counter_base()
    paint(g, """
KKKKKKKKKKKKKKKK
L..KKKKKKKK.....
L..KnnnnnnK...K.
L..KnKKKKnK..K..
L..KnKLLKnK.K...
L..KnKnnKnK.K...
L..KnnnnnnK..KK.
KKKKKKKKKKKKKKKK
""".replace(".", "L"))
    return g


def p_table(x, y):
    """Small kitchen table (two tiles wide)."""
    left = run_index(x, y, "a") == 0
    art = """
................
................
.KKKKKKKKKKKKKKK
KttttttttttttttK
KtnnnnnnnnnnnntK
KtnttttttttttntK
KtnttttttttttntK
KtnnnnnnnnnnnntK
KttttttttttttttK
KKKKKKKKKKKKKKKK
.KnK.........KnK
.KnK.........KnK
.KKK.........KKK
"""
    big = blank(".", 32, 16)
    rows = art.strip("\n").splitlines()
    for yy, row in enumerate(rows):
        for xx, ch in enumerate(row):
            if ch != ".":
                big[yy][xx] = ch
                big[yy][31 - xx] = ch
    g = plain()
    part = slice16(big, 0 if left else 1)
    for yy in range(16):
        for xx in range(16):
            if part[yy][xx] != ".":
                g[yy][xx] = part[yy][xx]
    return g


def p_trash(x, y):
    """Steel bin, overflowing with cups."""
    return on_floor("""
.....LL.LLL.....
....LKLLLLKL....
...LLLLLLLLLL...
..KKKKKKKKKKKK..
..KSSSSSSSSSSK..
...KSLSSSLSSK...
...KSLSSSLSSK...
...KSLSSSLSSK...
...KSLSSSLSSK...
....KSLSSLSK....
....KKKKKKKK....
""", top=2)


def fridge(x, y, lower):
    g = blank("W")
    for i in range(16):
        g[i][0] = g[i][15] = "K"
    if not lower:
        g[0] = ["K"] * 16
        for xx in range(16):
            g[10][xx] = "K"
        for yy in range(3, 9):
            g[yy][12] = "S"
        g[2][3] = g[2][4] = "L"
        rnd = random.Random(x * 3)
        if rnd.random() < 0.6:  # a note under a magnet
            paint(g, """
KKKK
KLLK
KLLK
KKKK
""", top=4, left=3 + rnd.randrange(4))
    else:
        for yy in range(1, 10):
            g[yy][12] = "S"
        g[15] = ["K"] * 16
        g[14] = ["S"] * 16
        g[14][0] = g[14][15] = "K"
    for yy in range(16):
        g[yy][14] = "L" if g[yy][14] == "W" else g[yy][14]
    return g


def p_lunch_table(x, y):
    """The sad lunch shelf: one paper bag with a name on it, and crumbs."""
    return on_floor("""
................
.........KKKK...
........KWWWWK..
....KK..KWKKWK..
...KWLK.KWWWWK..
...KLLK.KWLLWK..
KKKKKKKKKKKKKKKK
KSSSSSSSSSSSSSSK
KLLLLLLLLLLLLLLK
KKKKKKKKKKKKKKKK
.KLK........KLK.
.KLK........KLK.
.KKK........KKK.
""", top=1)


def vending(x, y, lower, kind):
    """Snack machine (red) or drinks machine (blue), two tiles tall."""
    body, accent, light = ("R", "Y", "L") if kind == "snack" else ("B", "W", "L")
    g = blank(body)
    for i in range(16):
        g[i][0] = g[i][15] = "K"
    if not lower:
        g[0] = ["K"] * 16
        g[1] = ["K"] + [light] * 14 + ["K"]
        for yy in range(3, 16):
            for xx in range(2, 11):
                g[yy][xx] = "K"
        for row in (4, 8, 12):
            for xx in range(3, 10, 2):
                g[row][xx] = accent
                g[row + 1][xx] = accent
            for xx in range(3, 10):
                g[row + 2][xx] = light
        for yy in range(4, 10, 2):
            g[yy][12] = g[yy][13] = "K"
        g[11][12] = g[11][13] = light
    else:
        for yy in range(0, 6):
            for xx in range(2, 11):
                g[yy][xx] = "K"
        for xx in range(2, 11):
            for yy in (8, 9, 10, 11):
                g[yy][xx] = "K"
        for xx in range(3, 10):
            g[9][xx] = light
        g[15] = ["K"] * 16
        g[14] = ["K"] + [light] * 14 + ["K"]
        g[2][12] = g[3][12] = "K"
        if kind == "snack" and x == CTX.get("dollar_x"):
            # half a dollar bill, being slowly eaten
            paint(g, """
.......KKKKKKKK.
.......KLLLLLLK.
.......KLKKLLLK.
.......KLLLLLLK.
.......KKKKKKKK.
""", top=1, left=3)
    return g


def claw(x, y, lower):
    """Broken claw machine: the claw is stuck, the plush toys are faceless."""
    g = blank("Y")
    for i in range(16):
        g[i][0] = g[i][15] = "K"
    if not lower:
        g[0] = ["K"] * 16
        for yy in range(2, 16):
            for xx in range(2, 14):
                g[yy][xx] = "B"
        for xx in range(2, 14):
            g[2][xx] = "K"
        for yy in range(3, 7):
            g[yy][7] = "K"
        paint(g, """
.KKK.
K...K
K...K
""", top=7, left=5)
        paint(g, """
.WW..WWW.WW.
WWWWWWWWWWWW
""", top=14, left=2)
        g[4][4] = g[5][3] = "W"
    else:
        for yy in range(0, 4):
            for xx in range(2, 14):
                g[yy][xx] = "W" if yy < 2 else "B"
        for xx in range(2, 14):
            g[4][xx] = "K"
        paint(g, """
KKKKK
KBBBK
KKKKK
""", top=7, left=9)
        # OUT OF ORDER tape cross
        paint(g, """
W...W
.W.W.
..W..
.W.W.
W...W
""", top=6, left=3)
        g[15] = ["K"] * 16
    return g


def p_couch(x, y):
    """Green couch, two tiles wide."""
    left = run_index(x, y, "o") == 0
    art = """
................
..KKKKKKKKKKKKKK
.KGGGGGGGGGGGGGG
KgKGGGGGGGGGGGGG
KgKGGGGGGGGGGGGG
KgKKKKKKKKKKKKKK
KgKGGGGGGGGGGGGG
KgKGGGGGGGGGGGGg
KgKGGGGGGGGGGGGg
KgKgggggggggggg.
KKKKKKKKKKKKKKKK
.KK..........KKK
"""
    g = on_floor(art, top=1)
    # middle seam of the cushions
    for yy in range(7, 11):
        g[yy][15] = "g"
    g[2 + 1][15] = "G"
    return g if left else flip(g)


def p_pingpong(x, y):
    """Ping-pong table, two tiles wide. Nobody uses it."""
    left = run_index(x, y, "P") == 0
    art = """
................
KKKKKKKKKKKKKKKK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KWWWWWWWWWWWWWWW
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KKKKKKKKKKKKKKKK
.KK..........KK.
"""
    g = on_floor(art, top=2)
    if not left:
        g = flip(g)
        for yy in range(2, 12):
            g[yy][0] = "W" if 3 <= yy <= 10 else "K"
    else:
        for yy in range(3, 11):
            g[yy][15] = "W" if yy != 7 else "W"
        g[5][4] = "W"
    return g


def p_cooler(x, y):
    return on_floor("""
.....KKKKKK.....
....KBBBBWBK....
...KBBBBBBWBK...
...KBBBBBBWBK...
...KBBBBBBBBK...
....KBBBBBBK....
.....KKKKKK.....
...KKKKKKKKKK...
...KWWWWWWWWK...
...KWBKWWKBWK...
...KWWWWWWWWK...
...KWWWWWWWWK...
...KWWWWWWWWK...
...KKKKKKKKKK...
""", top=1)


def p_plant(x, y):
    """Fake office plant (the pot shares the leaves' palette)."""
    return on_floor("""
.....KK.KK......
...KKGGKGGKK....
..KGGgGGGgGGK...
.KGgGKGGGKGgGK..
.KGGGGgGgGGGGK..
..KGgGGGGGgGK...
.KGGGKGgGKGGGK..
..KKGGGgGGGKK...
....KKKKKKK.....
....KgggggK.....
.....KgKgK......
.....KgggK......
......KKK.......
""", top=2)


def p_box(x, y):
    """Cardboard box with a taped seam."""
    rnd = random.Random(x * 5 + y * 11)
    art = """
................
.KKKKKKKKKKKKKK.
.KooooooKooooooK
.KooooooKooooooK
.KKKKKKKKKKKKKKK
.KooooooKooooooK
.KoonnooKooooooK
.KooooooKooooooK
.KooooooKoooonoK
.KooooooooooooOK
.KooooooooooooOK
.KKKKKKKKKKKKKKK
................
""".replace("O", "n")
    g = on_floor(art, top=2 if rnd.random() < 0.5 else 1)
    return flip(g) if rnd.random() < 0.5 else g


def p_noodles(x, y):
    """A pallet of instant noodle cups, stacked to the brim (two tiles wide)."""
    g = blank("n")
    for yy in range(0, 13, 4):
        for xx in range(16):
            g[yy][xx] = "K"
        for xx in range(0, 16, 4):
            off = 2 if (yy // 4) % 2 else 0
            cx = (xx + off) % 16
            g[yy + 1][cx] = "R"
            g[yy + 1][(cx + 1) % 16] = "R"
            g[yy + 1][(cx + 2) % 16] = "R"
            g[yy + 2][cx] = "W"
            g[yy + 2][(cx + 1) % 16] = "W"
            g[yy + 2][(cx + 2) % 16] = "W"
            g[yy + 3][cx] = "W"
            g[yy + 3][(cx + 1) % 16] = "W"
            g[yy + 3][(cx + 2) % 16] = "W"
    g[15] = ["K"] * 16
    g[14] = ["n"] * 16
    for xx in range(0, 16, 5):
        g[14][xx] = "K"
    left = run_index(x, y, "N") == 0
    for yy in range(16):
        g[yy][0 if left else 15] = "K"
    return g


def p_rack(x, y):
    """Steel shelving rack with yellow bulk boxes."""
    g = blank("S")
    for i in range(16):
        g[i][0] = g[i][15] = "K"
        g[0][i] = g[15][i] = "K"
        g[5][i] = g[10][i] = "K"
        g[6][i] = g[11][i] = "L"
    rnd = random.Random(x * 3 + y)
    for top in (1, 7, 12):
        xx = 2
        while xx < 13:
            wdt = rnd.choice([3, 4])
            for yy in range(top, top + (4 if top != 12 else 3) - (1 if top == 7 else 0)):
                for i in range(wdt):
                    if xx + i < 14 and yy < 15:
                        g[yy][xx + i] = "Y"
            g[top][xx] = "K" if top != 12 else g[top][xx]
            xx += wdt + 1
    return g


def p_bench(x, y):
    return on_floor("""
................
................
.KKKKKKKKKKKKKK.
KttttttttttttttK
KnnnnnnnnnnnnnnK
KttttttttttttttK
KKKKKKKKKKKKKKKK
.KnK........KnK.
.KnK........KnK.
.KKK........KKK.
""", top=3)


def p_reception(x, y):
    """Reception desk, three tiles wide, marble-top wood."""
    i = run_index(x, y, "k")
    big = blank("M", 48, 16)
    for yy in range(16):
        for xx in range(48):
            big[yy][xx] = "M"
    paint(big, """
.KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK.
KMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMK
KMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KttttttttttttttttttttttttttttttttttttttttttttttK
KtnnnnnnnnnnnntttttttttttttttttttnnnnnnnnnnnntK
KtnttttttttttnttttnnnnnnnnnnnttttntttttttttttntK
KtnttttttttttntttntttttttttttnttntttttttttttntK.
KtnttttttttttnttttnnnnnnnnnnnttttntttttttttttntK
KtnnnnnnnnnnnntttttttttttttttttttnnnnnnnnnnnntK.
KttttttttttttttttttttttttttttttttttttttttttttttK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
""", top=2)
    # a little brass bell on the counter
    paint(big, """
.KK.
KMMK
""", top=0, left=30)
    big[0][31] = "K"
    return slice16(big, i)


def logo_inlay(x, y):
    """Pondcorp lily pad inlaid in the marble, 2x2 metatiles (walkable)."""
    rows = CTX["rows"]
    ox = 16 if x > 0 and rows[y][x - 1] == "@" else 0
    oy = 16 if y > 0 and rows[y - 1][x] == "@" else 0
    big = blank("M", 32, 32)
    cx, cy, r = 15.5, 15.5, 13
    for yy in range(32):
        for xx in range(32):
            d = math.hypot(xx - cx, yy - cy)
            ang = math.degrees(math.atan2(xx - cx, -(yy - cy)))
            notch = 150 <= ang <= 180 or -180 <= ang <= -168
            if d <= r and not (notch and d > 2):
                big[yy][xx] = "G"
                if d > r - 1.2 or (notch and d > 2):
                    big[yy][xx] = "K"
            elif d <= r + 2 and not notch:
                big[yy][xx] = "g"
    for yy in range(32):
        for xx in range(32):
            if big[yy][xx] == "G":
                if any(not (0 <= xx + dx < 32 and 0 <= yy + dy < 32) or big[yy + dy][xx + dx] in "Mg"
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    big[yy][xx] = "K"
    for a in (-120, -60, 0, 60, 120):
        for rr in range(3, 11):
            xx = round(cx + math.sin(math.radians(a)) * rr)
            yy = round(cy - math.cos(math.radians(a)) * rr)
            if big[yy][xx] == "G":
                big[yy][xx] = "g"
    return [row[ox : ox + 16] for row in big[oy : oy + 16]]


# char -> (metatile builder(x, y) -> 16x16 char grid, solid?)
TILES = {
    # structure
    ".": (floor, False),
    "C": (floor, False),  # chest actor stands here
    "=": (wall, True),
    "#": (wall_top, True),
    "d": (door, False),
    "w": (cracked_wall, False),  # breakable wall actor sits here
    "B": (boss_door, False),
    "E": (elevator, False),
    "S": (stairs, False),
    "@": (logo_inlay, False),
    # wall decorations (row 0)
    "{": (wide(art_menu, "{^}"), True),
    "^": (wide(art_menu, "{^}"), True),
    "}": (wide(art_menu, "{^}"), True),
    "O": (lambda x, y: art_open_sign(), True),
    "l": (wide(art_label_sign, "l"), True),
    "X": (wide(art_expired, "X"), True),
    "<": (wide(art_privilege, "<~>"), True),
    "~": (wide(art_privilege, "<~>"), True),
    ">": (wide(art_privilege, "<~>"), True),
    "Y": (lambda x, y: art_tv(), True),
    "!": (wide(art_staff_only, "!"), True),
    "i": (wide(art_directory, "i"), True),
    "(": (wide(art_pondcorp, "(*)"), True),
    "*": (wide(art_pondcorp, "(*)"), True),
    ")": (wide(art_pondcorp, "(*)"), True),
    "[": (wide(art_family, "[_]"), True),
    "_": (wide(art_family, "[_]"), True),
    "]": (wide(art_family, "[_]"), True),
    # props (solid)
    "b": (p_bean_sack, True),
    "u": (p_cup_tower, True),
    "g": (p_grinder, True),
    "h": (lambda x, y: p_shelf(x, y), True),
    "H": (lambda x, y: p_shelf(x, y, brenda=True), True),
    "s": (p_sugar, True),
    "c": (p_counter, True),
    "k": (p_reception, True),
    "I": (p_sink, True),
    "m": (p_microwave, True),
    "f": (p_coffee_maker, True),
    "a": (p_table, True),
    "T": (p_trash, True),
    "F": (lambda x, y: fridge(x, y, False), True),
    "L": (lambda x, y: fridge(x, y, True), True),
    "z": (p_lunch_table, True),
    "V": (lambda x, y: vending(x, y, False, "snack"), True),
    "v": (lambda x, y: vending(x, y, True, "snack"), True),
    "D": (lambda x, y: vending(x, y, False, "drinks"), True),
    "r": (lambda x, y: vending(x, y, True, "drinks"), True),
    "Q": (lambda x, y: claw(x, y, False), True),
    "q": (lambda x, y: claw(x, y, True), True),
    "o": (p_couch, True),
    "P": (p_pingpong, True),
    "j": (p_cooler, True),
    "G": (p_plant, True),
    "x": (p_box, True),
    "N": (p_noodles, True),
    "R": (p_rack, True),
    "e": (p_bench, True),
}

# Each room is one Game Boy screen: 10 x 9 metatiles = 160 x 144 px.
# (grid x, grid y, title, layout)
ROOMS = {
    "espresso_room": (1, 0, "Espresso Bar", """
={^}===O==
#b.cccc.u#
#b......u#
#g.......#
#........#
#........#
#b......u#
#bb....uu#
####dd####
"""),
    "pantry": (0, 1, "Pantry", """
====ll====
#hhH.hhhh#
#........#
#.hh..hh.#
#........#
#.hh..hh.#
#s......C#
#ss....ss#
####ww####
"""),
    "kitchenette": (1, 1, "Kitchenette", """
====BB====
#cIf..mcc#
#........#
#..aa....#
#........d
#........#
#........#
#T......T#
####dd####
"""),
    "fridge_room": (2, 1, "Fridge Room", """
===XX=====
#FFF.FFFF#
#LLL.LLLL#
#........#
d........#
#..z.....#
#......C.#
#T.......#
##########
"""),
    "vending_alley": (0, 2, "Vending Alley", """
====ww====
#VDQ..VD.#
#vrq..vr.#
#........#
#........d
#........#
#........#
#T......T#
##########
"""),
    "lounge": (1, 2, "Break Room", """
=<~>dd=Y==
#........#
#oo....j.#
#........#
d..PP....d
#........#
#oo....G.#
#........#
####dd####
"""),
    "snack_storage": (2, 2, "Snack Storage", """
===!!=====
#RRR.CRRR#
#x.......#
#........#
d........#
#........#
#........#
#NNxx.NNx#
##########
"""),
    "elevator_landing": (1, 3, "Floor 2 Landing", """
=ii=dd====
#G......G#
#........#
#e......e#
#........#
#........#
#G......G#
#........#
####EE####
"""),
}

ROOM_FLOOR = {
    "espresso_room": "wood",
    "pantry": "lino",
    "kitchenette": "lino",
    "fridge_room": "lino",
    "vending_alley": "carpet",
    "lounge": "carpet",
    "snack_storage": "carpet",
    "elevator_landing": "carpet",
    "lobby": "marble",
}

# The vending machine that is eating a dollar (column in vending_alley).
DOLLAR_X = 1

# Standalone hub scene, not on the grid: {name: (title, layout)}
STANDALONE = {
    "lobby": ("Pondcorp Lobby", """
=(*)EE[_]=
#G......G#
#........#
#.....,..#
#kkk.@@..#
#....@@..#
#G......G#
#........#
####SS####
""".replace(",", ".")),
}

LOBBY_MARKERS = {"receptionist": [2, 3], "elevator": [4, 0], "stairs": [4, 8]}

PROPS_HINT = {
    "espresso_room": [
        {"name": "menu_board", "pos": [2, 0]},
        {"name": "hot_neon_sign", "pos": [7, 0]},
        {"name": "espresso_bar_counter", "pos": [4, 1]},
        {"name": "bean_sacks", "pos": [1, 2]},
        {"name": "cup_tower", "pos": [8, 2]},
        {"name": "grinder", "pos": [1, 3]},
    ],
    "pantry": [
        {"name": "do_not_eat_brenda_shelf", "pos": [3, 1]},
        {"name": "snack_shelf", "pos": [2, 3]},
        {"name": "sugar_sacks", "pos": [1, 6]},
        {"name": "label_your_food_sign", "pos": [4, 0]},
    ],
    "kitchenette": [
        {"name": "sink", "pos": [2, 1]},
        {"name": "dead_coffee_maker", "pos": [3, 1]},
        {"name": "microwave", "pos": [6, 1]},
        {"name": "kitchen_table", "pos": [3, 3]},
        {"name": "trash_can", "pos": [1, 7]},
    ],
    "fridge_room": [
        {"name": "fridge_wall", "pos": [5, 2]},
        {"name": "sad_lunch_shelf", "pos": [3, 5]},
        {"name": "expired_poster", "pos": [4, 0]},
        {"name": "trash_can", "pos": [1, 7]},
    ],
    "vending_alley": [
        {"name": "dollar_eating_vending_machine", "pos": [1, 2]},
        {"name": "drinks_machine", "pos": [2, 2]},
        {"name": "broken_claw_machine", "pos": [3, 2]},
        {"name": "trash_can", "pos": [8, 7]},
    ],
    "lounge": [
        {"name": "coffee_is_a_privilege_poster", "pos": [2, 0]},
        {"name": "tv_screensaver", "pos": [7, 0]},
        {"name": "ping_pong_table", "pos": [3, 4]},
        {"name": "couch", "pos": [1, 2]},
        {"name": "water_cooler", "pos": [7, 2]},
        {"name": "fake_plant", "pos": [7, 6]},
    ],
    "snack_storage": [
        {"name": "instant_noodle_pallet", "pos": [1, 7]},
        {"name": "bulk_snack_rack", "pos": [2, 1]},
        {"name": "staff_only_sign", "pos": [4, 0]},
        {"name": "cardboard_box", "pos": [1, 2]},
    ],
    "elevator_landing": [
        {"name": "floor_directory", "pos": [2, 0]},
        {"name": "fake_plant", "pos": [1, 1]},
        {"name": "bench", "pos": [1, 3]},
    ],
    "lobby": [
        {"name": "reception_desk", "pos": [2, 4]},
        {"name": "pondcorp_logo_sign", "pos": [2, 0]},
        {"name": "we_are_a_family_plaque", "pos": [7, 0]},
        {"name": "lobby_plant", "pos": [1, 1]},
    ],
}

DOORS = set("dBw")


# --- rendering and checks -----------------------------------------------------


def room_rows(layout):
    rows = layout.strip().splitlines()
    assert len(rows) == 9 and all(len(r) == 10 for r in rows), [len(r) for r in rows]
    return rows


def render_room(layout, floor_kind="carpet", name=None):
    rows = room_rows(layout)
    CTX["rows"] = rows
    CTX["floor"] = floor_kind
    CTX["dollar_x"] = DOLLAR_X if name == "vending_alley" else None
    canvas = blank("K", 160, 144)
    for my, row in enumerate(rows):
        for mx, ch in enumerate(row):
            g = TILES[ch][0](mx, my)
            assert len(g) == 16 and all(len(r) == 16 for r in g), ch
            for y in range(16):
                for x in range(16):
                    canvas[my * 16 + y][mx * 16 + x] = g[y][x]
    img = Image.new("RGB", (160, 144))
    img.putdata([RGB[c] for row in canvas for c in row])
    return rows, img


def validate(name, img):
    """GB Studio rules per image: <=4 colors per 8x8 tile, each tile inside one
    of the palettes, <=8 palettes per image, <=384 unique tiles."""
    tiles, colorsets = set(), set()
    w, h = img.size
    assert (w, h) == (160, 144), name
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            px = tuple(img.getpixel((tx + x, ty + y)) for y in range(8) for x in range(8))
            cs = frozenset(px)
            assert len(cs) <= 4, (name, "too many colors", tx, ty, sorted(k for k, v in RGB.items() if v in cs))
            tiles.add(px)
            colorsets.add(cs)
    assert len(tiles) <= 384, name
    sets = [cs for cs in colorsets if not any(cs < o for o in colorsets)]
    for cs in sets:
        assert any(cs <= p for p in PAL_RGB.values()), (name, "no palette fits", tx, ty, sorted(k for k, v in RGB.items() if v in cs))
    cands = [k for k, p in PAL_RGB.items() if any(cs <= p for cs in sets)]
    for n in range(1, 9):
        for combo in combinations(cands, n):
            if all(any(cs <= PAL_RGB[k] for k in combo) for cs in sets):
                return len(tiles), combo
    raise AssertionError(f"{name} needs more than 8 palettes")


def door_sides(rows):
    return {
        (0, -1): rows[0][4] in DOORS,
        (0, 1): rows[8][4] in DOORS,
        (-1, 0): rows[4][0] in DOORS,
        (1, 0): rows[4][9] in DOORS,
    }


def check_doors():
    """Every door must line up with a door of the same kind... or at least a
    door, in the neighbouring room; N/S doors fill both columns 4-5."""
    grid_ = {(gx, gy): room_rows(layout) for gx, gy, _, layout in ROOMS.values()}
    for (gx, gy), rows in grid_.items():
        for r in (0, 8):
            if rows[r][4] in DOORS or rows[r][5] in DOORS:
                assert rows[r][4] == rows[r][5], ((gx, gy), "N/S doors need columns 4-5")
        for x in range(10):
            for y in range(9):
                ch = rows[y][x]
                if ch in DOORS:
                    ok = (y in (0, 8) and x in (4, 5)) or (y == 4 and x in (0, 9))
                    assert ok, ((gx, gy), "door in the wrong place", x, y)
        assert "B" not in rows[8] and all(ch != "B" for r in rows[1:] for ch in r), ((gx, gy), "B only on the top row")
        for (dx, dy), has_door in door_sides(rows).items():
            if not has_door:
                continue
            other = grid_.get((gx + dx, gy + dy))
            assert other, f"door at {(gx, gy)} leads nowhere"
            back = {(0, -1): other[8][4], (0, 1): other[0][4], (-1, 0): other[4][9], (1, 0): other[4][0]}
            assert back[(dx, dy)] in DOORS, f"door at {(gx, gy)} has no matching door"
            mine = {(0, -1): rows[0][4], (0, 1): rows[8][4], (-1, 0): rows[4][0], (1, 0): rows[4][9]}[(dx, dy)]
            if "w" in (mine, back[(dx, dy)]):
                assert mine == back[(dx, dy)] == "w", f"cracked wall at {(gx, gy)} must meet a cracked wall"


def walkable(rows, x, y):
    return 0 <= x < 10 and 0 <= y < 9 and not TILES[rows[y][x]][-1]


def reach(rows, start):
    seen, todo = {start}, deque([start])
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if walkable(rows, nx, ny) and (nx, ny) not in seen:
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen


def check_layouts():
    """Everything walkable that matters connects: doors, elevators, stairs,
    chests, NPC spots; props can be examined; the boss arena stays open."""
    all_rooms = {n: room_rows(r[3]) for n, r in ROOMS.items()}
    all_rooms.update({n: room_rows(r[1]) for n, r in STANDALONE.items()})
    for name, rows in all_rooms.items():
        exits = [(x, y) for y in range(9) for x in range(10) if rows[y][x] in "dBwES"]
        assert exits, name
        for x, y in exits:
            assert walkable(rows, x, y), (name, "door not walkable", x, y)
        seen = reach(rows, exits[0])
        targets = exits + [(x, y) for y in range(9) for x in range(10) if rows[y][x] == "C"]
        for t in targets:
            assert t in seen, (name, "unreachable", t)
        for p in PROPS_HINT[name]:
            x, y = p["pos"]
            assert TILES[rows[y][x]][-1], (name, p["name"], "prop should be solid")
            assert any((x + ax, y + ay) in seen for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1))), (name, p["name"], "can't be examined")

    def clear(name, cells):
        rows = all_rooms[name]
        seen = reach(rows, next((x, y) for y in range(9) for x in range(10) if rows[y][x] in "dBwES"))
        for c in cells:
            assert walkable(rows, *c) and c in seen, (name, c)

    # boss arena: rows 2-7 between columns 3 and 6 stay open
    clear("espresso_room", [(x, y) for x in range(3, 7) for y in range(2, 8)])
    clear("lounge", [(6, 3), (5, 3), (7, 3), (6, 2), (6, 4)])
    clear("snack_storage", [(x, y) for x in range(3, 7) for y in range(3, 6)])
    clear("lobby", [tuple(LOBBY_MARKERS["receptionist"])])
    assert all_rooms["lobby"][0][4:6] == "EE" and all_rooms["lobby"][8][4:6] == "SS"
    assert all_rooms["elevator_landing"][8][4:6] == "EE"
    assert all_rooms["kitchenette"][0][4:6] == "BB"
    assert all_rooms["pantry"][8][4:6] == "ww" and all_rooms["vending_alley"][0][4:6] == "ww"
    rx, ry = LOBBY_MARKERS["receptionist"]
    assert TILES[all_rooms["lobby"][ry + 1][rx]][0] is TILES["k"][0], "receptionist must stand behind the desk"


def bufo_frame(index):
    sprite = Image.open(ROOT / "assets/sprites/bufo.png").convert("RGB")
    colors = {
        (0x07, 0x18, 0x21): (0x1C, 0x2A, 0x1C, 255),
        (0x86, 0xC0, 0x6C): (0x6B, 0x9B, 0x4B, 255),
        (0xE0, 0xF8, 0xCF): (0xDF, 0xE8, 0xA8, 255),
    }
    frame = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            c = sprite.getpixel((16 * index + x, y))
            if c in colors:
                frame.putpixel((x, y), colors[c])
    return frame


def main():
    check_doors()
    check_layouts()
    out_dir = ROOT / "assets/backgrounds"

    rendered, collision, errors = {}, [], []
    jobs = [(n, title, layout, f"break_{n}.png") for n, (_, _, title, layout) in ROOMS.items()]
    jobs += [(n, title, layout, f"{n}.png") for n, (title, layout) in STANDALONE.items()]
    for name, title, layout, fname in jobs:
        rows, img = render_room(layout, ROOM_FLOOR[name], name)
        rendered[name] = img
        try:
            n, pals = validate(name, img)
        except AssertionError as e:
            errors.append(e)
            print("FAIL", e)
            continue
        img.save(out_dir / fname)
        print(f"{fname} OK: unique tiles {n}/384, palettes {len(pals)}/8 ({', '.join(pals)})")
        coll = ["".join("X" if TILES[ch][-1] else "." for ch in row) for row in rows]
        collision.append(f"{title} ({fname})\n" + "\n".join(coll))

    (ROOT / "previews/break-room-collision.txt").write_text(
        "Break Room floor collision (X = solid), one cell per 16x16 metatile (2x2 GB tiles)\n"
        "Walkable specials: d door, B boss door, w cracked wall (breakable actor), E elevator, S stairs, C chest\n\n"
        + "\n\n".join(collision)
        + "\n"
    )

    # Floor overview: rooms on their grid at 2x; the lobby sits in a spare cell.
    scale, gap = 2, 12
    cells = {n: (gx, gy, t) for n, (gx, gy, t, _) in ROOMS.items()}
    cells["lobby"] = (0, 3, "Lobby (standalone)")
    cols = max(c[0] for c in cells.values()) + 1
    rows_ = max(c[1] for c in cells.values()) + 1
    cw, ch = 160 * scale + gap, 144 * scale + gap
    ov = Image.new("RGB", (cols * cw + gap, rows_ * ch + gap), (0x0F, 0x13, 0x1A))
    draw = ImageDraw.Draw(ov)
    for name, (gx, gy, title) in cells.items():
        x0, y0 = gap + gx * cw, gap + gy * ch
        ov.paste(rendered[name].resize((160 * scale, 144 * scale), Image.NEAREST), (x0, y0))
        tw = draw.textlength(title)
        draw.rectangle([x0 + 4, y0 + 4, x0 + 12 + tw, y0 + 18], fill=(0x0F, 0x13, 0x1A))
        draw.text((x0 + 8, y0 + 5), title, fill=(0xF4, 0xF4, 0xEC))
    # Bufo stepping out of the elevator.
    sx, sy = ROOMS["elevator_landing"][:2]
    f = bufo_frame(2).resize((32, 32), Image.NEAREST)
    ov.paste(f, (gap + sx * cw + 4 * 32 + 16, gap + sy * ch + 7 * 32), f)
    ov.save(ROOT / "previews/break-room-preview.png")
    print("overview:", ov.size)
    if errors:
        raise SystemExit(f"{len(errors)} room(s) failed validation")


if __name__ == "__main__":
    main()
