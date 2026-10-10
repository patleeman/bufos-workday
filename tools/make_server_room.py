"""Build Level 5, the Server Room floor (Floor 5), for GB Studio (Color Only,
automatic palettes).

Same shape as make_break_room.py: ROOMS = {name: (gx, gy, title, layout)}
with 10x9 metatile layouts (16x16 px each, 160x144 per room), and
TILES = {char: (builder, solid)}. Builders take (x, y) in metatiles; the
room being drawn is held in CTX while rendering.

Doors: north/south doors at columns 4-5 of the top or bottom row, east/west
doors at row 4, column 0 or 9.
  d  door (walkable)
  k  keycard door with a card reader (walkable; a trigger guards it)
  w  cracked floor panel wedged in the doorway (walkable; Bufo dashes
     through it, a breakable actor sits on it)
  E  elevator doors (walkable trigger)
  C  chest spot (drawn as floor)

validate() checks GB Studio's rules per image: at most 4 colors per 8x8 tile,
all tiles covered by at most 8 four-color palettes (found automatically, the
way GB Studio's automatic palettes work), at most 384 unique 8x8 tiles.

Outputs:
  assets/backgrounds/server_<room>.png   one per room in ROOMS
  previews/server-room-preview.png       2x floor overview with Bufo
  previews/server-room-collision.txt     which tiles are solid
"""

import math
import random
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from make_break_room import FONT as _BASE_FONT, bufo_frame  # noqa: E402


def hexc(h):
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


COL = {
    "K": "#0b0e17",  # ink
    "F": "#141c30",  # deep blue-black: floor seams, rack bodies, screens
    "f": "#25304c",  # raised floor panel
    "h": "#3a4a72",  # panel bevel
    "s": "#2e3852",  # wall steel
    "L": "#8a96b8",  # light steel, trims
    "S": "#56627e",  # steel
    "W": "#eef4ff",  # white
    "B": "#3a8ee8",  # vent blue, blue LEDs, blue cables
    "I": "#bfeaff",  # ice, frost, glow highlight
    "c": "#3fe6cc",  # KEVIN cyan
    "G": "#4be36a",  # green LED
    "R": "#e8443c",  # red LED, red cables, emergency red
    "Y": "#f2c230",  # amber, hazard yellow, yellow cables
    "n": "#6a3c1e",  # coffee
}
RGB = {k: hexc(v) for k, v in COL.items()}
LETTER = {v: k for k, v in RGB.items()}

FONT = dict(_BASE_FONT)
FONT.update({
    "Z": ["KKK", "..K", ".K.", "K..", "KKK"],
    "J": ["..K", "..K", "..K", "K.K", ".K."],
    "Q": [".K.", "K.K", "K.K", "KK.", ".KK"],
    "5": ["KKK", "K..", "KK.", "..K", "KK."],
    "6": [".KK", "K..", "KK.", "K.K", ".K."],
    "7": ["KKK", "..K", ".K.", ".K.", ".K."],
    "8": [".K.", "K.K", ".K.", "K.K", ".K."],
    ":": [".", "K", ".", "K", "."],
    ".": [".", ".", ".", ".", "K"],
    "%": ["K.K", "..K", ".K.", "K..", "K.K"],
    "?": ["KK.", "..K", ".K.", "...", ".K."],
})

# The room being drawn. Set by render_room().
CTX = {"rows": None, "name": None}


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


def vflip(g):
    return [list(r) for r in g[::-1]]


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
    row = CTX["rows"][y]
    i = 0
    while x - i - 1 >= 0 and row[x - i - 1] in chars:
        i += 1
    return i


def slice16(big, i, j=0):
    return [row[i * 16 : i * 16 + 16] for row in big[j * 16 : j * 16 + 16]]


def wide(art_fn, chars):
    """Builder for a multi-metatile decoration drawn as one wide grid."""

    def build(x, y):
        return slice16(art_fn(), run_index(x, y, chars))

    return build


def over(base, art, top=0, left=0):
    return paint(base, art, top=top, left=left)


# --- floors -----------------------------------------------------------------


def plain(x=0, y=0):
    """Bare panel colour under props, so they add only K plus two colours."""
    return blank("f")


def floor(x, y):
    """Raised data-centre floor panel: bevel on top-left, dark seam on
    bottom-right, every other panel perforated."""
    if CTX["name"] == "kevin_core":
        return core_floor(x, y)
    g = blank("f")
    for i in range(16):
        g[0][i] = g[i][0] = "h"
        g[15][i] = g[i][15] = "F"
    g[0][15] = g[15][0] = "F"
    if (x + y) % 2 == 0:
        for yy in range(4, 13, 4):
            for xx in range(4, 13, 4):
                g[yy][xx] = "F"
    return g


def vent(x, y):
    """Cold-air floor grate: thin blue louvres in a dark frame, frost
    drifting up out of it (walkable)."""
    g = blank("F")
    for i in range(16):
        g[0][i] = g[15][i] = g[i][0] = g[i][15] = "K"
    for yy in range(2, 14):
        for xx in range(2, 14):
            g[yy][xx] = "B" if yy % 3 == 2 else ("K" if yy % 3 == 0 else "F")
    for yy in range(1, 15):
        g[yy][1] = g[yy][14] = "K"
    rnd = random.Random(x * 7 + y * 13)
    for _ in range(2):
        px, py = rnd.randrange(3, 11), rnd.randrange(3, 12)
        g[py][px] = g[py][px + 1] = "I"
        g[py - 1][px + 2] = "I"
    return g


# --- KEVIN's round core room -----------------------------------------------

CORE_C = (80.0, 76.0)
CORE_R = (74.0, 64.0)


def core_inside(px, py, pad=0.0):
    cx, cy = CORE_C
    rx, ry = CORE_R
    return ((px - cx) / (rx - pad)) ** 2 + ((py - cy) / (ry - pad)) ** 2 <= 1.0


def core_floor(x, y):
    """Dark floor with cyan circuit traces running toward the centre, a ring
    pad where KEVIN stands, and the round wall cutting the corners."""
    g = blank("F")
    for yy in range(16):
        for xx in range(16):
            px, py = x * 16 + xx + 0.5, y * 16 + yy + 0.5
            if not core_inside(px, py):
                g[yy][xx] = "K"
                continue
            if not core_inside(px, py, pad=2.0):
                g[yy][xx] = "c"
                continue
            if not core_inside(px, py, pad=4.0):
                g[yy][xx] = "K"
                continue
            # floor grid: dark seams every 16 px
            if xx == 15 or yy == 15:
                g[yy][xx] = "K"
            # KEVIN's pad: two rings around his feet
            d = math.hypot((px - 80) / 1.0, (py - 60) / 0.62)
            if 26 <= d < 28 or 33 <= d < 34:
                g[yy][xx] = "c"
            elif 28 <= d < 29:
                g[yy][xx] = "I"
            # circuit traces: straight lines from the pad to the walls
            gx, gy = x * 16 + xx, y * 16 + yy
            if d >= 34:
                if gy in (60,) or gx in (40, 120) and gy > 60 or gx in (72, 88) and gy > 80:
                    g[yy][xx] = "c"
                if (gx, gy) in ((40, 60), (120, 60), (72, 80), (88, 80), (40, 108), (120, 108)):
                    pass
    # trace nodes (little squares where traces turn)
    for nx, ny in ((40, 60), (120, 60), (72, 81), (88, 81)):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                lx, ly = nx + dx - x * 16, ny + dy - y * 16
                if 0 <= lx < 16 and 0 <= ly < 16 and g[ly][lx] in "cF":
                    g[ly][lx] = "I" if dx == dy == 0 else "c"
    return g


def core_corner(x, y):
    """Corner of the round room: the curved wall (solid)."""
    return core_floor(x, y)


# --- walls ------------------------------------------------------------------


def wall(x=0, y=0):
    """Wall face: ink edge, light trim, steel panels with seams, baseboard."""
    g = blank("s")
    g[0] = ["K"] * 16
    g[1] = ["L"] * 16
    for yy in range(2, 14):
        g[yy][7] = "K"
    g[4][3] = g[4][11] = "L"
    g[14] = ["K"] * 16
    g[15] = ["K"] * 16
    return g


def wall_top(x, y):
    """Wall seen from above (side and bottom walls)."""
    g = blank("K")
    for i in range(16):
        g[3][i] = g[11][i] = "s"
    for i in range(4, 11):
        g[i][4] = "s"
    for i in list(range(0, 3)) + list(range(12, 16)):
        g[i][12] = "s"
    for i in range(16):
        if x == 0:
            g[i][15], g[i][14] = "L", "K"
        if x == 9:
            g[i][0], g[i][1] = "L", "K"
        if y == 8:
            g[0][i], g[1][i] = "L", "K"
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


def keycard_door(x, y):
    """Security door: steel leaves, hazard chevrons, card reader with a red
    light on the outer jamb (walkable; a trigger checks the keycard)."""
    left = x == 4
    g = blank("S")
    paint(g, """
KKKKKKKKKKKKKKKK
KFFFFFFFFFFFFFFK
KFKKKKKKKKKKKKKK
KFKSSSSSSSSSSSSK
KFKSFFFFFFFFFFSK
KFKSFSSSSSSSSFSK
KFKSFSSSSSSSSFSK
KFKSSSSSSSSSSSSK
KFKSSSSSSSSSSSSK
KFKSSSSSSSSSSSSK
KFKKKKKKKKKKKKKK
KFKYYKKYYKKYYKKY
KFKKYYKKYYKKYYKK
KFKKKKKKKKKKKKKK
KFFFFFFFFFFFFFFK
KKKKKKKKKKKKKKKK
""")
    if left:
        # card reader on the left jamb
        paint(g, """
KKKK
KSSK
KRRK
KSSK
KFFK
KKKK
""", top=3, left=0)
        g[4][1] = g[4][2] = "S"
    g[3][15] = g[4][15] = "K"
    return g if left else flip(g)


def cracked_panel(x, y):
    """A side doorway blocked by a cracked steel floor panel leaning in the
    gap (walkable: a breakable actor sits here, Bufo dashes through it)."""
    g = blank("K")
    for xx in range(16):
        for yy in (0, 1, 2, 13, 14, 15):
            g[yy][xx] = "K"
    for yy in range(3, 13):
        for xx in range(16):
            g[yy][xx] = "L"
    for xx in range(16):
        g[3][xx] = "K"
        g[12][xx] = "K"
    for yy in range(3, 13):
        g[yy][0] = g[yy][15] = "K"
    paint(g, """
................
................
................
................
.....K..........
.....KK.....s...
....K..K...K....
...K....KKK.....
..KK.....s.K....
.K........K.KK..
..........K...K.
................
................
""", top=0)
    # shading on the lower lip of the panel
    for xx in range(1, 15):
        g[11][xx] = "s" if g[11][xx] == "L" else g[11][xx]
    # crumbs on the floor seam
    g[13][4] = g[14][9] = "s"
    left = x == 0
    return g if left else flip(g)


def elevator(x, y):
    """Brushed steel doors with an amber call light."""
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
    for yy in range(2, 15):
        g[yy][15] = "K"
    return g if left else flip(g)


# --- wall decorations (row 0) -------------------------------------------------


def big_wall(w_tiles):
    g = blank("s", 16 * w_tiles, 16)
    g[0] = ["K"] * len(g[0])
    g[1] = ["L"] * len(g[0])
    g[14] = ["K"] * len(g[0])
    g[15] = ["K"] * len(g[0])
    return g


def framed_sign(w_tiles, fill="L", border="K", inset=2, top=2, bottom=13):
    g = big_wall(w_tiles)
    x0, x1 = inset, 16 * w_tiles - 1 - inset
    for yy in range(top, bottom + 1):
        for xx in range(x0, x1 + 1):
            edge = yy in (top, bottom) or xx in (x0, x1)
            g[yy][xx] = border if edge else fill
    return g, x0, x1


def art_restricted():
    """Hazard-striped RESTRICTED sign, three tiles wide."""
    g, x0, x1 = framed_sign(3, fill="Y", border="K", inset=1, top=2, bottom=13)
    for xx in range(x0 + 1, x1):
        if (xx // 2) % 2 == 0:
            g[3][xx] = "K"
            g[12][xx] = "K"
    stamp_center(g, 6, "RESTRICTED", "K", x0, x1 + 1)
    return g


def art_ai_only():
    """AUTHORIZED / AI ONLY in a red frame (the AI may have written this sign)."""
    g, x0, x1 = framed_sign(3, fill="L", border="R", inset=1, top=2, bottom=14)
    for yy in range(3, 14):
        g[yy][x0 + 1] = g[yy][x1 - 1] = "R"
    stamp_center(g, 3, "AUTHORIZED", "K", x0, x1 + 1)
    stamp_center(g, 9, "AI ONLY", "R", x0, x1 + 1)
    return g


def art_thermostat():
    """Thermostat set to a brutal 12 degrees."""
    g = wall()
    paint(g, """
...KKKKKKKKKK...
...KLLLLLLLLK...
...KLKKKKKKLK...
...KLKKKKKKLK...
...KLKKKKKKLK...
...KLKKKKKKLK...
...KLKKKKKKLK...
...KLLLBBLLLK...
...KKKKKKKKKK...
""", top=3)
    stamp(g, 6, 5, "12", "B")
    return g


def art_cold_sign():
    """COLD AISLE sign with a little snowflake."""
    g, x0, x1 = framed_sign(2, fill="L", border="K", inset=2, top=2, bottom=14)
    stamp_center(g, 3, "COLD", "B", x0, x1 + 1)
    stamp_center(g, 9, "AISLE", "K", x0, x1 + 1)
    return g


def art_cable_tray():
    """Wall cable tray: blue cables sagging out of it."""
    g = wall()
    for xx in range(16):
        g[3][xx] = "K"
        g[4][xx] = "L"
        g[5][xx] = "K"
    rnd = random.Random(CTX.get("seed", 0))
    for base in (2, 7, 12):
        sag = rnd.choice([3, 5, 7])
        for xx in range(-2, 3):
            yy = 6 + int(sag * (1 - (xx / 2.5) ** 2))
            cx = base + xx
            if 0 <= cx < 16:
                for d in range(6, yy + 1):
                    pass
                g[yy][cx] = "B"
                if yy + 1 < 14:
                    g[yy + 1][cx] = "K"
    return g


def art_ups_panel():
    """UPS status panel: ON BATTERY, with a battery-bar that is nearly empty."""
    g, x0, x1 = framed_sign(2, fill="F", border="K", inset=0, top=1, bottom=13)
    stamp_center(g, 3 + 1, "UPS", "G", x0, x1 + 1)
    for xx in range(x0 + 3, x1 - 2):
        g[10][xx] = "G" if xx < x0 + 6 else "s"
        g[11][xx] = "G" if xx < x0 + 6 else "s"
    g[10][x1 - 2] = g[11][x1 - 2] = "K"
    return g


def art_emergency():
    """The big red EMERGENCY POWER OFF button, three tiles wide: DO NOT PUSH."""
    g, x0, x1 = framed_sign(3, fill="R", border="K", inset=0, top=1, bottom=13)
    for xx in range(x0 + 1, x1):
        if (xx // 2) % 2 == 0:
            g[2][xx] = "Y"
    paint(g, """
...KKKKKK...
..KYYYYYYK..
.KYKKKKKKYK.
.KYKRRRRKYK.
.KYKRRRRKYK.
.KYKKKKKKYK.
..KYYYYYYK..
...KKKKKK...
""", top=3, left=34)
    stamp(g, x0 + 4, 4, "DO NOT", "W")
    stamp(g, x0 + 8, 10, "PUSH", "W")
    return g


def art_monitor_bank():
    """KEVIN's monitor wall: six screens of glowing cyan graphs and code, and
    a friendly greeting in the middle. No faces."""
    w = 8
    g = blank("F", 16 * w, 16)
    g[0] = ["K"] * (16 * w)
    for yy in range(16):
        for xx in range(0, 16 * w, 16):
            g[yy][xx] = "K"
            g[yy][xx + 15] = "K"
    for xx in range(16 * w):
        g[1][xx] = "K"
        g[14][xx] = "K"
        g[15][xx] = "K"
    rnd = random.Random(5)
    for i in range(w):
        x0 = i * 16
        kind = ["code", "wave", "bars", "hello", "hello2", "bars", "wave", "code"][i]
        if kind == "code":
            for yy in range(3, 13, 2):
                ln = rnd.randrange(4, 12)
                ind = rnd.choice([2, 2, 4])
                for xx in range(ind, min(ind + ln, 13)):
                    g[yy][x0 + xx] = "c" if rnd.random() < 0.85 else "I"
        elif kind == "wave":
            for xx in range(2, 14):
                yy = 8 + round(3.5 * math.sin((xx + i) * 0.9))
                g[yy][x0 + xx] = "c"
            for xx in range(2, 14, 2):
                g[12][x0 + xx] = "c"
        elif kind == "bars":
            for j, hgt in enumerate([4, 7, 5, 9, 6]):
                for yy in range(12 - hgt, 12):
                    g[yy][x0 + 3 + j * 2] = "c"
            g[3][x0 + 12] = "I"
        elif kind in ("hello", "hello2"):
            pass
    # The two middle screens together read HI BUFO.
    stamp(g, 3 * 16 + 4, 4, "HI", "I")
    stamp(g, 3 * 16 + 14, 4, "BUFO", "I")
    for xx in range(3 * 16 + 3, 5 * 16 - 3):
        if xx % 3 == 0:
            g[11][xx] = "c"
    # wipe the bezel line that crossed the middle of the two-screen pair
    for yy in range(2, 14):
        g[yy][3 * 16 + 15] = "F"
        g[yy][4 * 16] = "F"
    for yy in range(4, 9):
        for xx in range(3 * 16 + 14, 4 * 16 + 3):
            pass
    stamp(g, 3 * 16 + 14, 4, "BUFO", "I")
    return g


# --- props --------------------------------------------------------------------


def on_floor(art, top=0, left=0):
    return paint(plain(), art, top=top, left=left)


def rack(x, y, lower):
    """Server rack, two tiles tall, full of blinking LEDs. Each 8x8 corner
    gets one LED colour so it fits one palette."""
    rnd = random.Random(x * 31 + y * 17 + sum(map(ord, CTX["name"])) % 97)
    leds = CTX.get("leds", "GR")
    q = {(i, j): rnd.choice(leds) for i in (0, 1) for j in (0, 1)}
    g = blank("F")
    for i in range(16):
        g[i][0] = g[i][15] = "K"
        g[i][1] = g[i][14] = "S"
    start = 0
    if not lower:
        g[0] = ["K"] * 16
        g[1] = ["K"] + ["S"] * 14 + ["K"]
        start = 2
    yy = start
    while yy < 16:
        for xx in range(2, 14):
            g[yy][xx] = "K"
        kind = rnd.choice(["leds", "bays", "vents", "leds"])
        for r in (1, 2):
            if yy + r >= 16:
                break
            for xx in range(2, 14):
                if kind == "bays":
                    g[yy + r][xx] = "S" if xx % 3 else "K"
                elif kind == "vents":
                    g[yy + r][xx] = "K" if (xx + r) % 2 else "F"
        if kind == "leds" and yy + 1 < 16:
            for xx in range(3, 13, 2):
                if rnd.random() < 0.6:
                    g[yy + 1][xx] = "*"
        elif kind in ("bays", "vents") and yy + 1 < 16:
            g[yy + 1][12] = "*"
        yy += 3
    if lower:
        g[14] = ["K"] + ["S"] * 14 + ["K"]
        g[15] = ["K"] * 16
    for yy in range(16):
        for xx in range(16):
            if g[yy][xx] == "*":
                g[yy][xx] = q[(xx // 8, yy // 8)]
    # a sticky label on some racks
    if lower and rnd.random() < 0.3:
        paint(g, """
KKKK
KSSK
KKKK
""", top=9, left=5)
    return g


def battery(x, y, lower):
    """UPS battery cabinet: big black cells with amber terminals behind a
    steel frame, and a green charge readout on top."""
    cell = """
KSKYKSSSKYKSSKYK
KSKKKKKKKKKKKKKK
KSKFFFFFKFFFFFFK
KSKFFFFFKFFFFFFK
KSKFFFFFKFFFFFFK
KSKKKKKKKKKKKKKK
"""
    g = blank("S")
    for i in range(16):
        g[i][0] = g[i][15] = "K"
    if not lower:
        g[0] = ["K"] * 16
        paint(g, """
................
.KKKKKKKKKKKKKK.
.KGGGGGGGGFFFFK.
.KKKKKKKKKKKKKK.
""", top=1)
        if x % 2:
            g[3][7] = g[3][8] = g[3][9] = "F"
        paint(g, cell, top=8)
        g[14] = ["K"] + ["S"] * 14 + ["K"]
        g[15] = ["K"] + ["S"] * 14 + ["K"]
    else:
        paint(g, cell, top=0)
        paint(g, cell, top=7)
        g[14] = ["K"] * 16
        g[15] = ["K"] * 16
    for i in range(16):
        g[i][0] = g[i][15] = "K"
    return g


def p_coffee_maker(x, y):
    """The one coffee maker in the building that works. A full pot. A green
    light. Steam."""
    return on_floor("""
................
....KKKKKKKK....
...KSSSSSSSSK...
...KSKKKKKKSK...
...KSSSSSSSSK...
...KSSSSSSGSK...
...KSKKKKKKSK...
...KSKnnnnKSK...
...KSKnnnnKSK...
...KSKnnnnKSK...
...KSKKKKKKSK...
..KKKKKKKKKKKK..
..KSSSSSSSSSSK..
..KKKKKKKKKKKK..
""", top=1)


def p_steam(x, y):
    pass


def p_tank(x, y):
    """Fire suppression gas cylinder, red, with a stern pressure gauge."""
    return on_floor("""
.....KKKKK......
....KRRRRRK.....
...KRRLRRRRK....
...KRRLRRRRK....
...KRRLRRRRK....
...KRRLRRRRK....
...KRRRRRRRK....
...KKKKKKKKK....
...KLLLLLLLK....
...KLKKLKKLK....
...KLLLLLLLK....
...KKKKKKKKK....
""", top=3)


def p_coolant(x, y):
    """Glass coolant column glowing blue, bubbles rising."""
    g = blank("F")
    paint(g, """
KKKKKKKKKKKKKKKK
KFFFFFFFFFFFFFFK
KKKKKKKKKKKKKKKK
.KBBBBBBBBBBBBK.
.KBIBBBBBBBBBBK.
.KBIBBBBBIBBBBK.
.KBIBBBBBBBBBBK.
.KBIBBBIBBBBBBK.
.KBIBBBBBBBBIBK.
.KBIBBBBBBBBBBK.
.KBIBBBBBIBBBBK.
.KBIBBBBBBBBBBK.
KKKKKKKKKKKKKKKK
KFFFFFFFFFFFFFFK
KKKKKKKKKKKKKKKK
................
""")
    for yy in range(16):
        for xx in range(16):
            if g[yy][xx] == ".":
                g[yy][xx] = "F"
    # the lower lip sits on the round floor: keep a dark base
    g[15] = ["K"] * 16
    return g


def p_console(x, y):
    """KEVIN's console desk: glowing cyan keys and readouts."""
    i = run_index(x, y, "n")
    big = blank("F", 64, 16)
    paint(big, """
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSK
KSKKKKKKKKKKKKKKKKKSSSSSSSSSSSSSSSSSSSSSSSSSSSSKKKKKKKKKKKKKKKSK
KSKcKcKcKcKcKcKcKcKSSSKKKKKKKKKKKKKKKKKKKKKSSSSKFFcFFFcFFFFcFKSK
KSKKKKKKKKKKKKKKKKKSSSKFFFFFFFFFFFFFFFFFFFKSSSSKFcFcFcFcFcFFFKSK
KSKcKcKcKcKcKcKcKcKSSSKFccccccccccFFFFFFFFKSSSSKFFFFcFFFFFFcFKSK
KSKKKKKKKKKKKKKKKKKSSSKFFFFFFFFFFFFFFFFFFFKSSSSKKKKKKKKKKKKKKKSK
KSSSSSSSSSSSSSSSSSSSSSKKKKKKKKKKKKKKKKKKKKKSSSSSSSSSSSSSSSSSSSSK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFK
KFKKKKKFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFKKKKKFFK
KFKSSKFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFKSSKFFFK
KFKKKKKFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFKKKKFFFK
KFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
................................................................
""")
    for xx in range(64):
        big[15][xx] = "F"
    row = CTX["rows"][y]
    length = i
    while x - i + length < 10 and row[x - i + length] == "n":
        length += 1
    return slice16(big, i if length == 4 else (0, 3)[i])


def cable_map():
    """A periodic tangle of yellow and red cables (48 px period both ways, so
    the floor reuses a small set of tiles)."""
    if "cables" in CTX:
        return CTX["cables"]
    P = 48
    m = [["f"] * P for _ in range(P)]

    def draw(points, col):
        # points: list of (x, y) centre pixels; draw 2 px wide with K outline
        body = set()
        for x, y in points:
            for dx in (0, 1):
                for dy in (0, 1):
                    body.add(((x + dx) % P, (y + dy) % P))
        for x, y in body:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = ((x + ox) % P, (y + oy) % P)
                if q not in body:
                    m[q[1]][q[0]] = "K"
        for x, y in body:
            m[y][x] = col

    # yellow cables run left-right, red ones top-bottom, crossing over
    for base, ph in ((6, 0.0), (30, 2.1)):
        draw([(x, round(base + 4 * math.sin(2 * math.pi * x / P + ph))) for x in range(P)], "Y")
    for base, ph in ((14, 1.0), (38, 3.6)):
        draw([(round(base + 4 * math.sin(2 * math.pi * y / P + ph)), y) for y in range(P)], "R")
    # one stray running diagonally across everything
    draw([(t, round(t + 5 * math.sin(2 * math.pi * t / P))) for t in range(P)], "Y")
    CTX["cables"] = m
    return m


def cable_floor(x, y):
    """Walkable floor buried in cables."""
    m = cable_map()
    P = len(m)
    return [[m[(y * 16 + yy) % P][(x * 16 + xx) % P] for xx in range(16)] for yy in range(16)]


def cable_knot(x, y):
    """A waist-high knot of cables nobody will ever untangle (solid)."""
    g = cable_floor(x, y)
    rnd = random.Random(x * 3 + y * 11)
    knot = blank(".")
    cx, cy = 7.5, 8.5
    for yy in range(16):
        for xx in range(16):
            d = math.hypot((xx - cx) / 7.2, (yy - cy) / 6.2)
            if d <= 1.0:
                knot[yy][xx] = "K" if d > 0.86 else "f"
    # loops of cable inside the knot
    for k in range(7):
        col = "YR"[k % 2]
        r = rnd.uniform(2, 5.5)
        ox, oy = rnd.uniform(-2.5, 2.5), rnd.uniform(-2, 2)
        a0 = rnd.uniform(0, 6.28)
        for t in range(0, 40):
            a = a0 + t * 0.16
            px, py = round(cx + ox + r * math.cos(a)), round(cy + oy + r * 0.8 * math.sin(a))
            if 0 <= px < 16 and 0 <= py < 16 and knot[py][px] == "f":
                knot[py][px] = col
                if py + 1 < 16 and knot[py + 1][px] == "f":
                    knot[py + 1][px] = "K"
    for yy in range(16):
        for xx in range(16):
            if knot[yy][xx] != ".":
                g[yy][xx] = knot[yy][xx]
    return g


def p_spool(x, y):
    """Giant cable spool on its side, still half full."""
    return on_floor("""
....KKKKKKKK....
..KKSSSSSSSSKK..
.KSSKKKKKKKKSSK.
.KSKYYYYYYYYKSK.
KSKYKYKYKYKYYKSK
KSKYYYYYYYYYYKSK
KSKYKYKYKYKYYKSK
KSKYYYYYYYYYYKSK
KSKYKYKYKYKYYKSK
.KSKYYYYYYYYKSK.
.KSSKKKKKKKKSSK.
..KKSSSSSSSSKK..
....KKKKKKKK....
""", top=2)


# char -> (metatile builder(x, y) -> 16x16 char grid, solid?)
TILES = {
    # structure
    ".": (floor, False),
    "C": (lambda x, y: cable_floor(x, y) if CTX["name"] == "cable_vault" else floor(x, y), False),  # chest
    "v": (vent, False),
    "~": (cable_floor, False),
    "=": (wall, True),
    "#": (wall_top, True),
    "d": (door, False),
    "k": (keycard_door, False),
    "w": (cracked_panel, False),
    "E": (elevator, False),
    "o": (core_corner, True),
    # wall decorations (row 0)
    "[": (wide(art_restricted, "[^]"), True),
    "^": (wide(art_restricted, "[^]"), True),
    "]": (wide(art_restricted, "[^]"), True),
    "{": (wide(art_ai_only, "{|}"), True),
    "|": (wide(art_ai_only, "{|}"), True),
    "}": (wide(art_ai_only, "{|}"), True),
    "t": (lambda x, y: art_thermostat(), True),
    "a": (wide(art_cold_sign, "a"), True),
    "-": (lambda x, y: art_cable_tray(), True),
    "u": (wide(art_ups_panel, "u"), True),
    "!": (wide(art_emergency, "!"), True),
    "M": (wide(art_monitor_bank, "M"), True),
    # props (solid)
    "R": (lambda x, y: rack(x, y, False), True),
    "r": (lambda x, y: rack(x, y, True), True),
    "U": (lambda x, y: battery(x, y, False), True),
    "b": (lambda x, y: battery(x, y, True), True),
    "m": (p_coffee_maker, True),
    "T": (p_tank, True),
    "z": (p_coolant, True),
    "n": (p_console, True),
    "X": (cable_knot, True),
    "p": (p_spool, True),
}

# Each room is one Game Boy screen: 10 x 9 metatiles = 160 x 144 px.
# (grid x, grid y, title, layout)
ROOMS = {
    "kevin_core": (1, 0, "KEVIN's Core", """
=MMMMMMMM=
#oz.nn.zo#
#........#
#........#
#........#
#........#
#........#
#o......o#
####kk####
"""),
    "ups_room": (0, 1, "UPS Room", """
=!!!=uu=t=
#..UU..U.#
#..bb..b.#
#........#
#........d
#........#
#UU...m.U#
#bb.....b#
##########
"""),
    "cold_aisle": (1, 1, "Cold Aisle", """
=-aakkt--=
#RR.vv.RR#
#rr.vv.rr#
#........#
d........w
#........#
#RR.vv.RR#
#rr.vv.rr#
####dd####
"""),
    "cable_vault": (2, 1, "Cable Vault", """
=-------t=
#X~~~~~~p#
#~~X~~~~~#
#~~~~~~X~#
w~~~C~~~~#
#~X~~~~~~#
#~~~~~X~~#
#p~~~~~~X#
##########
"""),
    "server_landing": (1, 2, "Floor 5 Landing", """
=[^]dd{|}=
#Rv....vR#
#r......r#
#........#
#........#
#........#
#T......T#
#........#
####EE####
"""),
}

# Which LED colours each room's racks blink in (one palette per colour).
ROOM_LEDS = {"cold_aisle": "GRB", "server_landing": "G"}

PROPS_HINT = {
    "kevin_core": [
        {"name": "kevin_monitor_wall", "pos": [3, 0]},
        {"name": "kevin_console", "pos": [4, 1]},
        {"name": "coolant_column", "pos": [2, 1]},
        {"name": "coolant_column_right", "pos": [7, 1]},
    ],
    "ups_room": [
        {"name": "emergency_power_switch", "pos": [1, 0]},
        {"name": "working_coffee_maker", "pos": [6, 6]},
        {"name": "ups_status_panel", "pos": [5, 0]},
        {"name": "battery_bank", "pos": [3, 2]},
        {"name": "thermostat", "pos": [8, 0]},
    ],
    "cold_aisle": [
        {"name": "cold_aisle_sign", "pos": [3, 0]},
        {"name": "server_rack", "pos": [2, 2]},
        {"name": "blinking_rack", "pos": [7, 2]},
        {"name": "labelled_rack", "pos": [2, 6]},
        {"name": "thermostat", "pos": [6, 0]},
    ],
    "cable_vault": [
        {"name": "cable_knot", "pos": [3, 2]},
        {"name": "cable_spool", "pos": [8, 1]},
        {"name": "wall_cable_tray", "pos": [4, 0]},
        {"name": "giant_cable_knot", "pos": [7, 3]},
    ],
    "server_landing": [
        {"name": "restricted_sign", "pos": [2, 0]},
        {"name": "authorized_ai_only_sign", "pos": [7, 0]},
        {"name": "lonely_rack", "pos": [1, 2]},
        {"name": "fire_suppression_tank", "pos": [1, 6]},
    ],
}

DOORS = set("dBwk")
EXITS = "dBwkE"


# --- rendering and checks -----------------------------------------------------


def room_rows(layout):
    rows = layout.strip().splitlines()
    assert len(rows) == 9 and all(len(r) == 10 for r in rows), [len(r) for r in rows]
    return rows


def render_room(layout, name=None):
    rows = room_rows(layout)
    CTX["rows"] = rows
    CTX["name"] = name
    CTX["leds"] = ROOM_LEDS.get(name, "GR")
    canvas = blank("K", 160, 144)
    for my, row in enumerate(rows):
        for mx, ch in enumerate(row):
            CTX["seed"] = mx * 7 + my
            g = TILES[ch][0](mx, my)
            assert len(g) == 16 and all(len(r) == 16 for r in g), ch
            for y in range(16):
                for x in range(16):
                    canvas[my * 16 + y][mx * 16 + x] = g[y][x]
    img = Image.new("RGB", (160, 144))
    img.putdata([RGB[c] for row in canvas for c in row])
    return rows, img


def cover_palettes(colorsets, limit=8):
    """Group tile colour sets into at most `limit` palettes of 4 colours, the
    way GB Studio's automatic palettes share them. Returns the palettes or
    None."""
    sets = sorted({cs for cs in colorsets if not any(cs < o for o in colorsets)}, key=len, reverse=True)
    groups = []

    def place(i):
        if i == len(sets):
            return True
        cs = sets[i]
        tried = set()
        for gi, gset in enumerate(groups):
            u = gset | cs
            if len(u) <= 4 and u not in tried:
                tried.add(u)
                groups[gi] = u
                if place(i + 1):
                    return True
                groups[gi] = gset
        if len(groups) < limit:
            groups.append(cs)
            if place(i + 1):
                return True
            groups.pop()
        return False

    return groups if place(0) else None


def validate(name, img):
    """GB Studio rules per image: <=4 colors per 8x8 tile, <=8 palettes per
    image, <=384 unique tiles."""
    tiles, colorsets = set(), set()
    w, h = img.size
    assert (w, h) == (160, 144), name
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            px = tuple(img.getpixel((tx + x, ty + y)) for y in range(8) for x in range(8))
            cs = frozenset(px)
            assert len(cs) <= 4, (name, "too many colors", tx // 8, ty // 8, sorted(LETTER[c] for c in cs))
            tiles.add(px)
            colorsets.add(cs)
    assert len(tiles) <= 384, (name, "too many tiles", len(tiles))
    pals = cover_palettes(colorsets)
    if pals is None:
        sets = {"".join(sorted(LETTER[c] for c in cs)) for cs in colorsets if not any(cs < o for o in colorsets)}
        raise AssertionError(f"{name} needs more than 8 palettes: {sorted(sets)}")
    return len(tiles), ["".join(sorted(LETTER[c] for c in p)) for p in pals]


def door_sides(rows):
    return {
        (0, -1): rows[0][4],
        (0, 1): rows[8][4],
        (-1, 0): rows[4][0],
        (1, 0): rows[4][9],
    }


def check_doors():
    """Every door lines up with a door of the same kind in the neighbouring
    room; N/S doors fill both columns 4-5."""
    grid_ = {(gx, gy): room_rows(layout) for gx, gy, _, layout in ROOMS.values()}
    for (gx, gy), rows in grid_.items():
        for r in (0, 8):
            if rows[r][4] in DOORS or rows[r][5] in DOORS:
                assert rows[r][4] == rows[r][5], ((gx, gy), "N/S doors need columns 4-5")
        for x in range(10):
            for y in range(9):
                ch = rows[y][x]
                if ch in DOORS or ch == "E":
                    ok = (y in (0, 8) and x in (4, 5)) or (y == 4 and x in (0, 9) and ch not in "BE")
                    assert ok, ((gx, gy), "door in the wrong place", x, y)
        assert "B" not in "".join(rows[1:]), ((gx, gy), "B only on the top row")
        assert "E" not in "".join(rows[:8]), ((gx, gy), "E only on the bottom row")
        for (dx, dy), mine in door_sides(rows).items():
            if mine not in DOORS:
                continue
            other = grid_.get((gx + dx, gy + dy))
            assert other, f"door at {(gx, gy)} leads nowhere"
            back = door_sides(other)[(-dx, -dy)]
            assert back in DOORS, f"door at {(gx, gy)} has no matching door"
            if "w" in (mine, back) or "k" in (mine, back):
                assert mine == back, f"{mine!r} door at {(gx, gy)} must meet the same kind, got {back!r}"
        # no door may lead off the grid
    return True


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
    """Doors, elevators and chests connect; every prop is solid and has a
    walkable neighbour; KEVIN's floor and the chest's neighbours stay open."""
    all_rooms = {n: room_rows(r[3]) for n, r in ROOMS.items()}
    for name, rows in all_rooms.items():
        exits = [(x, y) for y in range(9) for x in range(10) if rows[y][x] in EXITS]
        assert exits, name
        for x, y in exits:
            assert walkable(rows, x, y), (name, "door not walkable", x, y)
        seen = reach(rows, exits[0])
        targets = exits + [(x, y) for y in range(9) for x in range(10) if rows[y][x] == "C"]
        for t in targets:
            assert t in seen, (name, "unreachable", t)
        assert 3 <= len(PROPS_HINT[name]) <= 6, name
        for p in PROPS_HINT[name]:
            x, y = p["pos"]
            assert TILES[rows[y][x]][-1], (name, p["name"], "prop should be solid")
            assert any((x + ax, y + ay) in seen for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1))), (name, p["name"], "can't be examined")

    def clear(name, cells):
        rows = all_rooms[name]
        seen = reach(rows, next((x, y) for y in range(9) for x in range(10) if rows[y][x] in EXITS))
        for c in cells:
            assert walkable(rows, *c) and c in seen, (name, c)

    # KEVIN (32x32) stands at columns 4-5, rows 2-3; the floor around him is open.
    clear("kevin_core", [(x, y) for x in range(3, 7) for y in range(2, 8)])
    cx, cy = next((x, y) for y in range(9) for x in range(10) if all_rooms["cable_vault"][y][x] == "C")
    clear("cable_vault", [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])
    assert all_rooms["server_landing"][8][4:6] == "EE"
    assert all_rooms["cold_aisle"][0][4:6] == "kk" and all_rooms["kevin_core"][8][4:6] == "kk"
    assert all_rooms["cold_aisle"][4][9] == "w" and all_rooms["cable_vault"][4][0] == "w"


def preview(rendered, cells, out, bufo_at=None, scale=2, gap=12):
    """Rooms on their grid at 2x with titles, like the other floor previews."""
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
    if bufo_at:
        (gx, gy), (mx, my) = bufo_at
        f = bufo_frame(2).resize((16 * scale, 16 * scale), Image.NEAREST)
        ov.paste(f, (gap + gx * cw + mx * 16 * scale + 8 * scale, gap + gy * ch + my * 16 * scale), f)
    ov.save(out)
    return ov.size


def main():
    check_doors()
    check_layouts()
    out_dir = ROOT / "assets/backgrounds"

    rendered, collision, errors = {}, [], []
    for name, (_, _, title, layout) in ROOMS.items():
        fname = f"server_{name}.png"
        rows, img = render_room(layout, name)
        rendered[name] = img
        try:
            n, pals = validate(name, img)
        except AssertionError as e:
            errors.append(e)
            print("FAIL", e)
            continue
        img.save(out_dir / fname)
        print(f"{fname} OK: unique tiles {n}/384, palettes {len(pals)}/8 ({' '.join(pals)})")
        coll = ["".join("X" if TILES[ch][-1] else "." for ch in row) for row in rows]
        collision.append(f"{title} ({fname})\n" + "\n".join(coll))

    (ROOT / "previews/server-room-collision.txt").write_text(
        "Server Room floor collision (X = solid), one cell per 16x16 metatile (2x2 GB tiles)\n"
        "Walkable specials: d door, k keycard door (trigger), w cracked panel (breakable actor), "
        "E elevator, C chest\n\n"
        + "\n\n".join(collision)
        + "\n"
    )
    cells = {n: (gx, gy, t) for n, (gx, gy, t, _) in ROOMS.items()}
    size = preview(rendered, cells, ROOT / "previews/server-room-preview.png",
                   bufo_at=(ROOMS["server_landing"][:2], (4, 7)))
    print("overview:", size)
    if errors:
        raise SystemExit(f"{len(errors)} room(s) failed validation")


if __name__ == "__main__":
    main()
