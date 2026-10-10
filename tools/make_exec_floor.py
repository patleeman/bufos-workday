"""Build Level 6, the Executive Floor (Floor 6), and the ending scenes, for
GB Studio (Color Only, automatic palettes).

Same shape as make_break_room.py: ROOMS = {name: (gx, gy, title, layout)}
with 10x9 metatile layouts (16x16 px each, 160x144 per room), and
TILES = {char: (builder, solid)}. Builders take (x, y) in metatiles; the
room being drawn is held in CTX while rendering.

Doors: north/south doors at columns 4-5 of the top or bottom row, east/west
doors at row 4, column 0 or 9.
  d  door (walkable)
  k  keycard door with a gold card reader (walkable; a trigger guards it)
  B  boss door (top row, columns 4-5)
  E  elevator doors (walkable trigger)
  C  chest spot (drawn as floor)
  ,  red carpet runner (walkable floor)

STANDALONE = {name: (title, layout)} holds the ending scenes:
  ending_cubicle  Bufo's cubicle at 5:00 PM in sunset light (built from the
                  opening cubicle's tiles in make_story_scenes.py)
  credits         a sunset over the Pondcorp tower (painted, not tiled; its
                  layout is all walkable floor)

validate() checks GB Studio's rules per image: at most 4 colors per 8x8 tile,
all tiles covered by at most 8 four-color palettes (found automatically, the
way GB Studio's automatic palettes work), at most 384 unique 8x8 tiles.

Outputs:
  assets/backgrounds/exec_<room>.png      one per room in ROOMS
  assets/backgrounds/ending_cubicle.png   the ending cubicle
  assets/backgrounds/credits.png          the credits backdrop
  previews/exec-floor-preview.png         2x floor overview plus the endings
  previews/exec-floor-collision.txt       which tiles are solid
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
import make_story_scenes as story  # noqa: E402


def hexc(h):
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


COL = {
    "K": "#0f131a",  # ink
    "M": "#ece6da",  # marble
    "V": "#b8aca0",  # marble vein
    "W": "#fffaf0",  # white
    "Y": "#f0c030",  # gold
    "o": "#a8701c",  # dark gold
    "H": "#fff4b0",  # gold shine, champagne fizz
    "t": "#8a3a24",  # mahogany
    "n": "#4a1a10",  # dark mahogany, leather shadow
    "R": "#b02838",  # red carpet, velvet
    "r": "#6e1424",  # dark red
    "G": "#58a848",  # felt green, money green
    "g": "#2e6a30",  # dark green
    "B": "#4a7ac8",  # painted sky and sea, book spines
    "I": "#c8e4f0",  # mirror glass
    "S": "#7c8494",  # vault steel
    "L": "#c8ccd4",  # light steel
}
RGB = {k: hexc(v) for k, v in COL.items()}

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
    "#": ["K.K", "KKK", "K.K", "KKK", "K.K"],
})

CTX = {"rows": None, "name": None, "floor": "marble"}


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


def text_width(text, scale=1):
    return (sum(len(FONT[ch][0]) + 1 for ch in text) - 1) * scale


def stamp(g, x, y, text, c, scale=1):
    for ch in text:
        glyph = FONT[ch]
        for gy, row in enumerate(glyph):
            for gx, px in enumerate(row):
                if px == "K":
                    for sy in range(scale):
                        for sx in range(scale):
                            yy, xx = y + gy * scale + sy, x + gx * scale + sx
                            if 0 <= yy < len(g) and 0 <= xx < len(g[0]):
                                g[yy][xx] = c
        x += (len(glyph[0]) + 1) * scale
    return g


def stamp_center(g, y, text, c, x0=0, x1=None, scale=1):
    x1 = len(g[0]) if x1 is None else x1
    return stamp(g, x0 + (x1 - x0 - text_width(text, scale)) // 2, y, text, c, scale)


def run_index(x, y, chars):
    row = CTX["rows"][y]
    i = 0
    while x - i - 1 >= 0 and row[x - i - 1] in chars:
        i += 1
    return i


def col_index(x, y, chars):
    rows = CTX["rows"]
    j = 0
    while y - j - 1 >= 0 and rows[y - j - 1][x] in chars:
        j += 1
    return j


def slice16(big, i, j=0):
    return [row[i * 16 : i * 16 + 16] for row in big[j * 16 : j * 16 + 16]]


def wide(art_fn, chars):
    """Builder for a multi-metatile decoration drawn as one wide grid."""

    def build(x, y):
        return slice16(art_fn(), run_index(x, y, chars))

    return build


def block(art_fn, ch):
    """Builder for a rectangular multi-metatile prop (w x h metatiles)."""

    def build(x, y):
        return slice16(art_fn(), run_index(x, y, ch), col_index(x, y, ch))

    return build


def overlay(g, art_grid):
    for yy in range(16):
        for xx in range(16):
            if art_grid[yy][xx] != ".":
                g[yy][xx] = art_grid[yy][xx]
    return g


# --- floors -----------------------------------------------------------------


ROOM_FLOOR = {"brock_suite": "plush"}


def floor_base():
    return "R" if CTX["floor"] == "plush" else "M"


def plain(x=0, y=0):
    return blank(floor_base())


def floor(x, y):
    if CTX["floor"] == "plush":
        return plush(x, y)
    g = blank("M")
    v = (x * 3 + y * 5) % 4
    if v in (0, 2):
        off = 3 if v == 0 else 9
        for py in range(16):
            g[py][(py // 2 + off) % 15] = "V"
    elif v == 1:
        for py in range(4, 12):
            g[py][(20 - py) % 15] = "V"
    for i in range(16):
        g[15][i] = "V"
        g[i][15] = "V"
    g[3][4] = g[4][5] = "W"
    return g


def plush(x, y):
    """Brock's deep red carpet: a dark lattice with gold studs."""
    g = blank("R")
    for yy in range(16):
        for xx in range(16):
            if (xx + yy) % 8 == 0 or (xx - yy) % 8 == 0:
                g[yy][xx] = "r"
    for yy, xx in ((4, 0), (4, 8), (12, 4), (12, 12), (0, 4), (0, 12), (8, 0), (8, 8)):
        if (xx + yy) % 8 == 4:
            g[yy][xx] = "Y"
    return g


def runner(x, y):
    """Red carpet runner with a gold border wherever it meets marble."""
    rows = CTX["rows"]
    g = blank("R")
    for yy in range(16):
        for xx in range(16):
            if (xx + yy) % 8 == 4 or (xx - yy) % 8 == 4:
                g[yy][xx] = "r"

    def carpetish(cx, cy):
        if not (0 <= cx < 10 and 0 <= cy < 9):
            return True
        return rows[cy][cx] in ",dkBE"

    if not carpetish(x - 1, y):
        for yy in range(16):
            g[yy][0], g[yy][1], g[yy][2] = "K", "Y", "R"
    if not carpetish(x + 1, y):
        for yy in range(16):
            g[yy][15], g[yy][14], g[yy][13] = "K", "Y", "R"
    if not carpetish(x, y - 1):
        for xx in range(16):
            if g[0][xx] != "K":
                g[0][xx], g[1][xx] = "K", "Y"
    if not carpetish(x, y + 1):
        for xx in range(16):
            if g[15][xx] != "K":
                g[15][xx], g[14][xx] = "K", "Y"
    return g


def on_carpet_inward(x, y):
    """True when the tile one step into the room is carpet runner."""
    rows = CTX["rows"]
    ix, iy = x, y
    if y == 0:
        iy = 1
    elif y == 8:
        iy = 7
    elif x == 0:
        ix = 1
    elif x == 9:
        ix = 8
    return rows[iy][ix] == ","


# --- walls ------------------------------------------------------------------


def wall(x=0, y=0):
    """Mahogany panelling with a gold crown moulding and a gold rail."""
    g = blank("t")
    g[0] = ["K"] * 16
    g[1] = ["Y"] * 16
    g[2] = ["n"] * 16
    for yy in range(4, 11):
        g[yy][2] = g[yy][13] = "n"
    for xx in range(2, 14):
        g[4][xx] = g[10][xx] = "n"
    g[12] = ["Y"] * 16
    g[13] = ["n"] * 16
    g[14] = ["K"] * 16
    g[15] = ["K"] * 16
    return g


def wall_top(x, y):
    """Wall seen from above (side and bottom walls)."""
    g = blank("K")
    for i in range(16):
        g[3][i] = g[11][i] = "n"
    for i in range(4, 11):
        g[i][4] = "n"
    for i in list(range(0, 3)) + list(range(12, 16)):
        g[i][12] = "n"
    for i in range(16):
        if x == 0:
            g[i][15], g[i][14] = "Y", "K"
        if x == 9:
            g[i][0], g[i][1] = "Y", "K"
        if y == 8:
            g[0][i], g[1][i] = "Y", "K"
    return g


def door(x, y):
    """Open doorway: the floor (or the runner) runs through between jambs."""
    g = runner(x, y) if on_carpet_inward(x, y) else floor(x, y)
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
    """Mahogany door with a gold card reader (walkable; a trigger checks for
    Brock's keycard)."""
    if y in (0, 8):
        left = x == 4
        g = paint(blank("t"), """
KKKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYK
KYKKKKKKKKKKKKKK
KYKtttttttttttnK
KYKtnnnnnnnnttnK
KYKtnttttttnttnK
KYKtnttttttnttnK
KYKtnnnnnnnnttnK
KYKttttttttttYnK
KYKtnnnnnnnnttnK
KYKtnttttttnttnK
KYKtnnnnnnnnttnK
KYKtttttttttttnK
KYKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYK
KKKKKKKKKKKKKKKK
""")
        if left:
            paint(g, """
KKKK
KYYK
KRRK
KYYK
KKKK
""", top=4, left=0)
        return g if left else flip(g)
    # side door (row 4): seen from above, a door leaf filling the gap
    g = blank("K")
    for yy in range(3, 13):
        for xx in range(16):
            g[yy][xx] = "t"
    for xx in range(16):
        g[3][xx] = g[12][xx] = "K"
        g[7][xx] = "n"
    for yy in range(3, 13):
        g[yy][0] = g[yy][15] = "K"
    # card reader on the corridor side of the door
    side = 2 if x == 9 else 11
    paint(g, """
KKK
KYK
KRK
KKK
""", top=8, left=side)
    g[5][7] = g[5][8] = "Y"
    return g


def boss_door(x, y):
    """The Boardroom's double doors: mahogany with a gold crown."""
    left = x == 4
    art = """
KKKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYY
KYnnnnnnnnnnnnnn
KYntttttttttttnK
KYntKKKKKKKKKtnK
KYntKttttttttKnK
KYntKttKtttKtKnK
KYntKtKYKtKYKKnK
KYntKtKYYKYYKKnK
KYntKtKYYYYYKKnK
KYntKtKYYYYYKKnK
KYntKttKKKKKtKnK
KYntKttttttttKYK
KYntKKKKKKKKKKYK
KYnttttttttttnnK
KKKKKKKKKKKKKKKK
"""
    g = paint(blank("K"), art)
    return g if left else flip(g)


def elevator(x, y):
    """Gold-plated elevator doors."""
    left = x == 4
    art = """
KKKKKKKKKKKKKKKK
KHHHKKKKKKKKKKKK
KHKHKooooooooooK
KKKKKoYYYYYYYYoK
KoooooYooooooYoK
KoYYYoYoYYYYoYoK
KoYoooYoYooYoYoK
KoYoooYoYooYoYoK
KoYoooYoYooYoYoK
KoYoooYoYooYoYoK
KoYoooYoYooYoYoK
KoYoooYoYYYYoYoK
KoYoooYooooooYoK
KoYoooYYYYYYYYoK
KooooooooooooooK
KKKKKKKKKKKKKKKK
"""
    g = paint(blank("K"), art)
    for yy in range(2, 15):
        g[yy][15] = "K"
    return g if left else flip(g)


# --- wall decorations (row 0) -------------------------------------------------


def full_frame(w_tiles, frame="Y", fill="W", top=1, bottom=13):
    """A decoration that covers the whole wall face (no wall colours left)."""
    g = blank(fill, 16 * w_tiles, 16)
    g[0] = ["K"] * (16 * w_tiles)
    g[14] = ["K"] * (16 * w_tiles)
    g[15] = ["K"] * (16 * w_tiles)
    x1 = 16 * w_tiles - 1
    for yy in range(top, bottom + 1):
        for xx in range(16 * w_tiles):
            if yy in (top, bottom) or xx in (0, x1):
                g[yy][xx] = "K"
            elif yy in (top + 1, bottom - 1) or xx in (1, x1 - 1):
                g[yy][xx] = frame
    return g


def art_plaque():
    """Gold EXECUTIVES ONLY plaque, three tiles wide."""
    g = full_frame(3, frame="o", fill="Y", top=0, bottom=14)
    g[2][44] = g[3][45] = g[11][3] = "H"
    stamp_center(g, 2, "EXECUTIVES", "K")
    stamp_center(g, 8, "ONLY", "K")
    return g


def art_vip():
    g = full_frame(1, frame="o", fill="Y")
    stamp_center(g, 5, "VIP", "K")
    g[3][3] = g[4][4] = "H"
    return g


def art_please_wait():
    g = full_frame(2, frame="o", fill="Y", top=0, bottom=14)
    stamp_center(g, 2, "PLEASE", "K")
    stamp_center(g, 8, "WAIT", "K")
    g[11][4] = g[11][27] = "H"
    return g


def art_mirror():
    """Gilded mirror. It only shows your good side."""
    g = full_frame(2, frame="Y", fill="I")
    for i in range(3, 11):
        for d in (0, 1):
            xx = 8 + i + d
            if 2 <= xx < 30:
                g[i + 0][xx] = "W"
        xx = 18 + i
        g[i][xx] = "W"
    return g


PORTRAITS = ["yacht", "golf", "stocks", "money"]


def art_portrait(x, y):
    """Faceless gilt-framed oil paintings of the things executives love."""
    order = [i for i, ch in enumerate(CTX["rows"][0]) if ch == "p"]
    subject = CTX.get("portraits", PORTRAITS)[order.index(x) % 4]
    g = full_frame(1, frame="Y", fill="W")
    if subject == "yacht":
        for yy in range(3, 12):
            for xx in range(2, 14):
                g[yy][xx] = "B"
        paint(g, """
.....K......
.....KW.....
.....KWW....
.....KWWW...
.....KWWWW..
.KKKKKKKKKKK
..KWWWWWWWK.
BBBKKKKKKKBB
B.W.BB.W..B.
""".replace(".", "B"), top=3, left=2)
        g[11][3] = g[11][9] = "W"
    elif subject == "golf":
        for yy in range(3, 12):
            for xx in range(2, 14):
                g[yy][xx] = "W" if yy < 8 else "G"
        paint(g, """
.......K....
.......KKK..
.......KKKK.
.......K....
GGG....K....
GGGGGGGKGGGG
""", top=4, left=2)
        g[9][5] = g[9][6] = "W"
        g[10][9] = "K"
    elif subject == "stocks":
        for yy in range(3, 12):
            for xx in range(2, 14):
                g[yy][xx] = "W"
        for yy in range(3, 12):
            g[yy][3] = "K"
        for xx in range(3, 14):
            g[11][xx] = "K"
        pts = [(4, 10), (6, 9), (8, 9), (10, 7), (12, 4)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for t in range(9):
                px = round(x0 + (x1 - x0) * t / 8)
                py = round(y0 + (y1 - y0) * t / 8)
                g[py][px] = "G"
        g[3][12] = g[3][11] = g[4][13] = "G"
    else:  # money
        for yy in range(3, 12):
            for xx in range(2, 14):
                g[yy][xx] = "G"
        stamp(g, 6, 5, "$", "W")
        g[3][3] = g[11][12] = "W"
    return g


def art_ticker():
    """Stock ticker TV: the line only goes up."""
    g = full_frame(2, frame="K", fill="n")
    pts = [(3, 10), (8, 9), (12, 10), (17, 7), (22, 6), (28, 3)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for t in range(12):
            g[round(y0 + (y1 - y0) * t / 11)][round(x0 + (x1 - x0) * t / 11)] = "G"
    stamp(g, 3, 3, "UP", "Y")
    g[3][27] = g[4][28] = g[4][26] = "G"
    return g


def art_books():
    """A wall of self-help books, all by the same author."""
    w = 3
    g = blank("n", 16 * w, 16)
    g[0] = ["K"] * (16 * w)
    for yy in (1, 7, 13):
        g[yy] = ["K"] * (16 * w)
    g[14] = ["K"] * (16 * w)
    g[15] = ["K"] * (16 * w)
    rnd = random.Random(11)
    for top in (2, 8):
        xx = 1
        while xx < 16 * w - 2:
            wd = rnd.choice([2, 2, 3])
            hgt = rnd.choice([4, 5, 5])
            pal = "RY" if (xx // 8) % 2 == 0 else "BW"
            col = rnd.choice(pal)
            for yy in range(top + 5 - hgt, top + 5):
                for i in range(wd):
                    if xx + i < 16 * w - 1 and (xx + i) // 8 == xx // 8:
                        g[yy][xx + i] = col
            xx += wd + (1 if rnd.random() < 0.3 else 0)
            # never let a book straddle two 8 px tiles
            if xx % 8 == 7:
                xx += 1
    for yy in range(16):
        g[yy][0] = g[yy][16 * w - 1] = "K"
    return g


def art_vault():
    """Brock's wall vault: a round steel door with a gold wheel."""
    g = blank("S", 32, 16)
    g[0] = ["K"] * 32
    g[14] = ["K"] * 32
    g[15] = ["K"] * 32
    for yy in range(16):
        g[yy][0] = g[yy][31] = "K"
    for yy in range(1, 14):
        for xx in range(1, 31):
            if yy in (1, 13) or xx in (1, 30):
                g[yy][xx] = "L"
    cx, cy = 15.5, 7.0
    for yy in range(2, 13):
        for xx in range(2, 30):
            d = math.hypot((xx - cx) / 1.25, yy - cy)
            if d <= 6.0:
                g[yy][xx] = "K" if d > 5.2 else ("L" if d > 4.4 else "S")
    for a in range(0, 360, 45):
        for r in range(1, 5):
            px = round(cx + math.cos(math.radians(a)) * r * 1.25)
            py = round(cy + math.sin(math.radians(a)) * r)
            g[py][px] = "Y"
    g[7][15] = g[7][16] = "K"
    for yy in (4, 10):
        g[yy][5] = g[yy][26] = "K"
    return g


def art_banner():
    """The giant SYNERGY banner, six tiles wide."""
    w = 6
    g = blank("R", 16 * w, 16)
    g[0] = ["K"] * (16 * w)
    g[1] = ["Y"] * (16 * w)
    g[2] = ["K"] * (16 * w)
    for yy in range(3, 14):
        g[yy][0] = g[yy][16 * w - 1] = "K"
        g[yy][1] = g[yy][16 * w - 2] = "r"
    g[13] = ["Y" if xx % 2 else "r" for xx in range(16 * w)]
    g[14] = ["K"] * (16 * w)
    g[15] = ["K"] * (16 * w)
    stamp_center(g, 4, "SYNERGY", "r", 1, 16 * w + 1, scale=2)
    stamp_center(g, 3, "SYNERGY", "Y", 0, 16 * w, scale=2)
    return g


def art_pie():
    """Pie chart: 100% of the pie, labelled US."""
    g = full_frame(1, frame="Y", fill="W")
    cx, cy = 7.5, 7.0
    for yy in range(3, 12):
        for xx in range(2, 14):
            d = math.hypot(xx - cx, yy - cy)
            if d <= 4.6:
                g[yy][xx] = "K" if d > 3.7 else "R"
    g[7][8] = g[6][8] = "W"
    return g


def art_chart():
    """Quarterly chart, the bars only get taller."""
    g = full_frame(1, frame="Y", fill="W")
    for i, hgt in enumerate([2, 3, 5, 8]):
        for yy in range(11 - hgt, 11):
            g[yy][3 + i * 3] = "G"
            g[yy][4 + i * 3] = "G"
    for xx in range(2, 14):
        g[11][xx] = "K"
    return g


# --- props --------------------------------------------------------------------


def on_floor(art, top=0, left=0):
    return paint(plain(), art, top=top, left=left)


def p_palm(x, y):
    """Potted palm. Fake. Expensive."""
    return on_floor("""
..K..KK..K......
.KGK.KGK.KGKK...
KGgGKGgGKGGgGK..
.KKGGGgGGgKKGGK.
..KgKGGGgGK.KgK.
.KGGKgGgKGGK.K..
KGgK.KgK..KgK...
.KK...Kg.K..K...
......KgK.......
....KKKKKKK.....
....KgggggK.....
.....KgggK......
.....KKKKK......
""", top=2)


def p_bust(x, y):
    """Faceless marble bust of the founder, on a fluted pedestal."""
    return on_floor("""
......KKKK......
.....KWWWMK.....
.....KWWMMK.....
.....KWMMVK.....
......KMVK......
...KKKKMMKKKK...
..KWWWMMMMMVVK..
..KKKKKKKKKKKK..
....KMVMVMVK....
....KMVMVMVK....
....KMVMVMVK....
...KKKKKKKKKK...
...KMMMMMMMVK...
...KKKKKKKKKK...
""", top=1)


def p_bench(x, y):
    """Velvet-and-mahogany bench."""
    return on_floor("""
................
.KKKKKKKKKKKKKK.
KtttttttttttttnK
KtntntntntntntnK
KnnnnnnnnnnnnnnK
KKKKKKKKKKKKKKKK
.KnK........KnK.
.KnK........KnK.
.KKK........KKK.
""", top=4)


def p_armchair(x, y):
    """Wing-back leather armchair."""
    g = on_floor("""
...KKKKKKKKKK...
..KttttttttttK..
..KtnttnttnttK..
.KKttttttttttKK.
KtKtnttnttnttKtK
KtKttttttttttKtK
KtKKKKKKKKKKKKtK
KtKttttttttttKtK
KnKttttttttttKnK
KnKnnnnnnnnnnKnK
KKKKKKKKKKKKKKKK
.Kn..........nK.
.KK..........KK.
""", top=2)
    return g


def p_humidor(x, y):
    """Cigar humidor cabinet: glass door, rows of cigars, a gold latch."""
    return paint(blank("t"), """
KKKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYK
KtttttttttttttnK
KtKKKKKKKKKKKtnK
KtKnnnnnnnnnKtnK
KtKtttttttttKtnK
KtKnnnnnnnnnKYnK
KtKtttttttttKYnK
KtKnnnnnnnnnKtnK
KtKtttttttttKtnK
KtKnnnnnnnnnKtnK
KtKKKKKKKKKKKtnK
KtttttttttttttnK
KnnnnnnnnnnnnnnK
KKKKKKKKKKKKKKKK
.KK..........KK.
""".replace(".", floor_base()))


def art_fountain():
    """Champagne fountain: a pyramid of coupes overflowing (2x2 tiles)."""
    g = blank("M", 32, 32)
    rnd = random.Random(3)

    def coupe(cx, top):
        paint(g, """
KKKKKKK
KHYYYYK
.KYYYK.
..KYK..
...K...
""", top=top, left=cx - 3)

    rows_ = [(16, 2, 1), (16, 8, 2), (16, 14, 3), (16, 20, 4)]
    for cx, top, n in rows_:
        width = n * 7 + (n - 1)
        x0 = cx - width // 2 + 3
        for i in range(n):
            coupe(x0 + i * 8, top)
    # champagne spilling down the sides
    for yy in range(4, 24):
        for side in (-1, 1):
            xx = 16 + side * (yy // 2 + 2)
            if 0 <= xx < 32 and g[yy][xx] == "M" and rnd.random() < 0.6:
                g[yy][xx] = "Y"
    # gold tray and base
    paint(g, """
KKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYK
.KKKKKKKKKKKKKKKKKKKKKKKKKKK.
.........KYYYYYYYYYK.........
.........KKKKKKKKKKK.........
""", top=25, left=2)
    # fizz
    for px, py in ((10, 1), (21, 3), (5, 12), (26, 9), (8, 18), (24, 16)):
        if g[py][px] == "M":
            g[py][px] = "H"
    return g


def art_putting():
    """Indoor putting green, 3x2 tiles: mowing stripes, a flag, one ball."""
    g = blank("M", 48, 32)
    for yy in range(2, 30):
        for xx in range(1, 47):
            corner = (yy < 5 or yy > 26) and (xx < 4 or xx > 43)
            if corner:
                continue
            g[yy][xx] = "G" if (xx // 8) % 2 == 0 else "g"
    for yy in range(32):
        for xx in range(48):
            if g[yy][xx] in "Gg":
                if any(not (0 <= xx + dx < 48 and 0 <= yy + dy < 32) or g[yy + dy][xx + dx] == "M"
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    g[yy][xx] = "K"
    # the hole and flag (inside one green stripe tile, x 32-39)
    paint(g, """
.K......
.KRRR...
.KRRRR..
.KRR....
.K......
.K......
.W......
KKK.....
""", top=11, left=33)
    # the ball, on a dark stripe
    g[22][12] = g[22][13] = g[23][12] = g[23][13] = "W"
    return g


def art_desk():
    """Brock's desk: mahogany with gold trim, a gold nameplate and a golden
    stapler (2 tiles wide)."""
    g = blank("t", 32, 16)
    paint(g, """
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYK
KtttttttttttttttttttttttttttttnK
KtttKKKKKKKKKtttttttttttKKKKKtnK
KtttKYYYYYYYKtttttttttttKYYYKtnK
KtttKKKKKKKKKtttttttttttKKKKKtnK
KtttttttttttttttttttttttttttttnK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnK
KnttttttttnnnnnnnnnnnnttttttttnK
KntnnnnntnnnYYYYYYnnnntnnnnntnnK
KntnnYnntnnnYKKKKYnnnntnnYnntnnK
KntnnnnntnnnYYYYYYnnnntnnnnntnnK
KnttttttttnnnnnnnnnnnnttttttttnK
KnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
""")
    return g


def art_bed():
    """Brock's bed (2x2): tufted headboard, gold silk sheets."""
    g = blank("Y", 32, 32)
    paint(g, """
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYK
KtttttttttttttttttttttttttttttnK
KtnttnttnttnttnttnttnttnttnttnnK
KtttttttttttttttttttttttttttttnK
KtnttnttnttnttnttnttnttnttnttnnK
KnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KoKKKKKKKKKKKoooKKKKKKKKKKKKKoYK
KoKWWWWWWWWWKoooKWWWWWWWWWKoooYK
KoKWWWWWWWWWKoooKWWWWWWWWWKoooYK
KoKKKKKKKKKKKoooKKKKKKKKKKKoooYK
KooooooooooooooooooooooooooooooK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KYYYYYYoYYYYYYYYYYYYYYYYoYYYYYoK
KYYYYYYYoYYYYYYYYYYYYYYYYoYYYYoK
KYYYYYYYYoYYYYYYYYYYYYYYYYoYYYoK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KooooooooooooooooooooooooooooooK
KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYoK
KooooooooooooooooooooooooooooooK
KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK
KoK..........................KoK
KKK..........................KKK
................................
""".replace(".", "R"))
    return g


def p_statue(x, y):
    """Gold statue of an executive (faceless), arms raised in triumph."""
    return paint(plain(), """
.....KKK.KKK....
....KYK.KYoK....
....KYoKKYoK....
.....KYYYYK.....
.....KYYYoK.....
......KYoK......
.....KYYYoK.....
.....KYYYoK.....
......KYoK......
.....KYKKYK.....
....KKKKKKKK....
...KYYYYYYYoK...
...KooooooooK...
...KKKKKKKKKK...
""", top=1)


def p_throne(x, y):
    """Brock's desk chair is a gold throne. Of course it is."""
    return paint(plain(), """
...K..KK..K.....
..KYKKYYKKYK....
..KYYYYYYYYK....
..KYoooooooYK...
..KYoYYYYYoYK...
..KYoYYYYYoYK...
..KYoYYYYYoYK...
.KKYoooooooYKK..
KYYYYYYYYYYYYYK.
KYooooooooooYoK.
KKKKKKKKKKKKKKK.
.KoK.......KoK..
.KKK.......KKK..
""", top=2)


def art_gong():
    """The pompous gong (2x2): a gold disc in a gold frame."""
    g = blank("M", 32, 32)
    for yy in range(1, 31):
        for xx in (2, 3, 4, 27, 28, 29):
            g[yy][xx] = "K" if xx in (2, 29) else ("Y" if xx in (3, 28) else "o")
    for xx in range(2, 30):
        g[1][xx] = "K"
        g[2][xx] = "Y"
        g[3][xx] = "o"
        g[4][xx] = "K"
    for yy in range(28, 31):
        for xx in range(0, 7):
            g[yy][xx] = "K" if yy in (28, 30) or xx in (0, 6) else "o"
        for xx in range(25, 32):
            g[yy][xx] = "K" if yy in (28, 30) or xx in (25, 31) else "o"
    cx, cy, r = 15.5, 15.5, 9.5
    for yy in range(5, 28):
        for xx in range(5, 27):
            d = math.hypot(xx - cx, yy - cy)
            if d <= r:
                if d > r - 1:
                    g[yy][xx] = "K"
                elif d > r - 2.5:
                    g[yy][xx] = "o"
                elif 4.5 < d < 5.5:
                    g[yy][xx] = "o"
                else:
                    g[yy][xx] = "Y"
    # strings holding the disc
    for yy in range(5, 8):
        g[yy][11] = g[yy][20] = "K"
    # the mallet leaning on the frame
    paint(g, """
KK.
KoK
KoK
.Ko
""", top=24, left=8)
    return g


def p_rope(x, y):
    """Velvet rope: a brass post, the red rope running on to the next post."""
    g = plain()
    paint(g, """
.....KKKKK......
....KYYYYYK.....
....KYHYYYK.....
....KYYYYYK.....
.....KKKKK......
......KYK.......
......KYK.......
......KRK.......
......KRRK......
......KRRK......
......KRRK......
......KRRK......
......KRRK......
......KRRK......
......KRRK......
......KRRK......
""".replace("H", "Y"))
    return g


def art_table():
    """The Boardroom table: 8 x 2 tiles of mahogany with gold inlay, a gold
    nameplate before every seat and a gavel at the head."""
    w, h = 128, 32
    g = blank("t", w, h)
    for xx in range(w):
        g[0][xx] = "K"
        g[h - 1][xx] = "K"
        g[22][xx] = "K"
        g[23][xx] = "Y"
        for yy in range(24, h - 1):
            g[yy][xx] = "n"
    for yy in range(h):
        g[yy][0] = g[yy][w - 1] = "K"
    for xx in range(3, w - 3):
        g[3][xx] = g[19][xx] = "Y"
    for yy in range(3, 20):
        g[yy][3] = g[yy][w - 4] = "Y"
    # wood grain
    rnd = random.Random(8)
    for yy in range(6, 18, 3):
        xx = 6
        while xx < w - 8:
            ln = rnd.randrange(6, 16)
            for i in range(ln):
                if xx + i < w - 6:
                    g[yy][xx + i] = "n"
            xx += ln + rnd.randrange(4, 10)
    # nameplates in front of each executive's seat (columns 1,3,5,7,8 -> local 0,2,4,6,7)
    for col in (0, 2, 4, 6, 7):
        x0 = col * 16 + 4
        for yy in (5, 6, 7):
            for xx in range(x0, x0 + 8):
                g[yy][xx] = "K" if yy in (5, 7) or xx in (x0, x0 + 7) else "Y"
    # gavel at local column 4, front half (room cell (5, 3))
    paint(g, """
.KKKKK....
KnnnnnK...
KtttttKKKK
KnnnnnKtYK
.KKKKK.KKK
""", top=17 - 4, left=4 * 16 + 3)
    # the quarterly report, bound in gold leaf (room cell (7, 3))
    paint(g, """
KKKKKKKK.
KYYYYYYKK
KYKKKKYKn
KYYYYYYKn
KKKKKKKKn
.nnnnnnnn
""", top=14, left=6 * 16 + 4)
    # front panel posts
    for xx in range(15, w - 1, 16):
        for yy in range(24, h - 1):
            g[yy][xx] = "K"
            g[yy][xx + 1] = "t"
    return g


def p_exec_chair(x, y):
    """High-backed leather executive chair behind the table (walkable: an
    executive stands here)."""
    return on_floor("""
....KKKKKKKK....
...KttttttttK...
...KtnttnttnK...
...KttttttttK...
...KtnttnttnK...
...KttttttttK...
...KtnttnttnK...
...KttttttttK...
..KKKKKKKKKKKK..
..KtnnnnnnnntK..
..KKKKKKKKKKKK..
....KnK..KnK....
....KKK..KKK....
""", top=2)


def floor_or_runner(x, y):
    return runner(x, y)


# char -> (metatile builder(x, y) -> 16x16 char grid, solid?)
TILES = {
    # structure
    ".": (floor, False),
    "C": (floor, False),  # chest actor stands here
    ",": (runner, False),
    "=": (wall, True),
    "#": (wall_top, True),
    "d": (door, False),
    "k": (keycard_door, False),
    "B": (boss_door, False),
    "E": (elevator, False),
    "n": (p_exec_chair, False),  # an executive stands on each chair
    # wall decorations (row 0)
    "[": (wide(art_plaque, "[_]"), True),
    "_": (wide(art_plaque, "[_]"), True),
    "]": (wide(art_plaque, "[_]"), True),
    "V": (lambda x, y: art_vip(), True),
    "q": (wide(art_please_wait, "q"), True),
    "m": (wide(art_mirror, "m"), True),
    "p": (art_portrait, True),
    "t": (wide(art_ticker, "t"), True),
    "b": (wide(art_books, "b"), True),
    "v": (wide(art_vault, "v"), True),
    "S": (wide(art_banner, "S"), True),
    "%": (lambda x, y: art_pie(), True),
    "$": (lambda x, y: art_chart(), True),
    # props (solid)
    "P": (p_palm, True),
    "a": (p_bust, True),
    "e": (p_bench, True),
    "c": (p_armchair, True),
    "h": (p_humidor, True),
    "f": (block(art_fountain, "f"), True),
    "g": (block(art_putting, "g"), True),
    "D": (wide(art_desk, "D"), True),
    "z": (block(art_bed, "z"), True),
    "Z": (p_statue, True),
    "Y": (lambda x, y: p_throne(x, y), True),
    "G": (block(art_gong, "G"), True),
    "r": (p_rope, True),
    "T": (block(art_table, "T"), True),
}

# Each room is one Game Boy screen: 10 x 9 metatiles = 160 x 144 px.
# (grid x, grid y, title, layout)
ROOMS = {
    "boardroom": (1, 0, "The Boardroom", """
=%SSSSSS$=
#n.n.n.nn#
#TTTTTTTT#
#TTTTTTTT#
#...,,...#
#...,,...#
#...,,...#
#...,,...#
####dd####
"""),
    "board_antechamber": (1, 1, "Antechamber", """
====BB=qq=
#GG.,,...#
#GGr,,r..#
#..r,,r..#
#..r,,r..#
#..r,,r..#
#..r,,r.c#
#c..,,..c#
####dd####
"""),
    "exec_lounge": (0, 2, "Executive Lounge", """
==tt==V===
#h.....cc#
#........#
#..ff....#
#..ff....d
#........#
#.....ggg#
#cc...ggg#
##########
"""),
    "exec_hall": (1, 2, "Executive Hallway", """
=p=pddp=p=
#.a.,,.a.#
#...,,...#
#...,,...#
d,,,,,,,,k
#...,,...#
#...,,...#
#a..,,..a#
####dd####
"""),
    "brock_suite": (2, 2, "Brock's Private Suite", """
=bbb=vv===
#.Y....zz#
#.DD...zz#
#........#
k........#
#........#
#....C...#
#Z......Z#
##########
"""),
    "exec_landing": (1, 3, "Floor 6 Landing", """
=[_]dd=mm=
#P..,,..P#
#...,,...#
#e..,,..e#
#...,,...#
#...,,...#
#...,,...#
#P..,,..P#
####EE####
"""),
}

PROPS_HINT = {
    "boardroom": [
        # Row 1 (behind the table) is the executives' row and Bufo can't reach
        # it, so the banner and charts on the north wall can't be examined;
        # the table's front edge carries the jokes instead.
        {"name": "boardroom_table", "pos": [2, 3]},
        {"name": "gavel", "pos": [5, 3]},
        {"name": "gold_leaf_quarterly_report", "pos": [7, 3]},
    ],
    "board_antechamber": [
        {"name": "pompous_gong", "pos": [1, 2]},
        {"name": "velvet_rope", "pos": [3, 4]},
        {"name": "please_wait_sign", "pos": [7, 0]},
        {"name": "waiting_chair", "pos": [8, 6]},
    ],
    "exec_lounge": [
        {"name": "champagne_fountain", "pos": [3, 3]},
        {"name": "leather_armchair", "pos": [8, 1]},
        {"name": "cigar_humidor", "pos": [1, 1]},
        {"name": "putting_green", "pos": [6, 6]},
        {"name": "stock_ticker", "pos": [2, 0]},
        {"name": "vip_plaque", "pos": [6, 0]},
    ],
    "exec_hall": [
        {"name": "portrait_of_a_yacht", "pos": [1, 0]},
        {"name": "portrait_of_a_golf_course", "pos": [3, 0]},
        {"name": "portrait_of_a_stock_chart", "pos": [6, 0]},
        {"name": "portrait_of_money", "pos": [8, 0]},
        {"name": "faceless_bust", "pos": [2, 1]},
        {"name": "another_faceless_bust", "pos": [8, 7]},
    ],
    "brock_suite": [
        {"name": "self_help_books", "pos": [1, 0]},
        {"name": "gold_throne", "pos": [2, 1]},
        {"name": "vault", "pos": [5, 0]},
        {"name": "brocks_desk", "pos": [2, 2]},
        {"name": "gold_silk_bed", "pos": [7, 2]},
        {"name": "gold_statue", "pos": [1, 7]},
    ],
    "exec_landing": [
        {"name": "executives_only_plaque", "pos": [2, 0]},
        {"name": "gilded_mirror", "pos": [7, 0]},
        {"name": "potted_palm", "pos": [1, 1]},
        {"name": "velvet_bench", "pos": [1, 3]},
    ],
}

DOORS = set("dBwk")
EXITS = "dBwkE"


# =============================================================================
# Ending scenes
# =============================================================================

# Sunset recolour of the opening cubicle (letters from make_story_scenes).
SUNSET = {
    "K": "#1a0f18",  # ink, warmed
    "W": "#fff0d8",  # warm white
    "C": "#a8606a",  # carpet in shadow
    "S": "#6a3450",  # carpet weave, partition fabric, desk front
    "L": "#f4bc94",  # partition caps, desk tops, lit peach
    "w": "#f4a050",  # wall, lit orange
    "v": "#4a2a6a",  # wall tops in dusk shadow (same as Q, shares its palette)
    "B": "#6a3450",  # screens are off: same as S
    "E": "#e04a3a",  # red
    "g": "#3a5a28",  # dark leaf
    "G": "#90a83c",  # leaf in warm light
    # new: the sunbeam on the carpet and the sky in the window
    "A": "#e8906c",  # carpet in the sunbeam
    "a": "#b05860",  # weave in the sunbeam
    "Q": "#4a2a6a",  # dusk purple
    "P": "#e0607a",  # pink
    "O": "#f89848",  # orange
    "Y": "#ffd870",  # sun
    "N": "#3a1a3a",  # skyline silhouette
}
SUNSET_RGB = {k: hexc(v) for k, v in SUNSET.items()}


def e_digital_clock(mx, my, rows):
    """Red LED wall clock: 5:00."""
    g = story.c_wall()
    paint(g, """
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
KKKKKKKKKKKKKKKK
""", top=3)
    stamp(g, 1, 5, "5:00", "E")
    return g


def e_clock(mx, my, rows):
    """The wall clock, finally at 5:00."""
    return paint(story.c_wall(), """
.....KKKKKK.....
....KWWWWWWK....
...KWWWWKWWWK...
...KWWWWKWWWK...
...KWWWWKWWWK...
...KWWWWWKWWK...
...KWWWWWWKWK...
....KWWWWWWK....
.....KKKKKK.....
""", top=2)


def e_window(mx, my, rows):
    """Window onto the sunset (3 tiles wide): bands of purple, pink and
    orange, the sun going down behind the skyline."""
    i = 0
    while mx - i - 1 >= 0 and rows[my][mx - i - 1] == "F":
        i += 1
    big = blank("K", 48, 16)
    for yy in range(1, 14):
        for xx in range(48):
            if yy == 1 or yy == 13 or xx in (0, 47):
                big[yy][xx] = "K"
            elif yy < 4:
                big[yy][xx] = "Q"
            elif yy < 8:
                big[yy][xx] = "P" if (yy > 5 or (xx + yy) % 2) else "Q"
            else:
                big[yy][xx] = "O"
    big[0] = ["K"] * 48
    # the sun
    cx, cy = 30, 13
    for yy in range(8, 13):
        for xx in range(48):
            if math.hypot(xx - cx, (yy - cy) * 1.1) <= 6:
                big[yy][xx] = "Y"
    # skyline silhouette
    heights = [3, 3, 5, 5, 2, 2, 4, 4, 4, 1, 1, 3, 3, 3, 5, 5, 2, 2, 4, 4, 2, 2, 3, 3]
    for xx in range(1, 47):
        hgt = heights[(xx // 2) % len(heights)]
        for yy in range(13 - hgt, 13):
            big[yy][xx] = "N"
    # mullions
    for yy in range(1, 14):
        big[yy][16] = big[yy][31] = "K"
    big[7] = [c if c != "Q" else "Q" for c in big[7]]
    for xx in range(48):
        big[14][xx] = "K"
        big[15][xx] = "K"
    return [row[i * 16 : i * 16 + 16] for row in big]


def e_mug_desk(mx, my, rows):
    """Bufo's desk, mug empty, ready to go home."""
    return paint(story.c_desk(mx, my, rows), """
................
.KKKKKKK........
.KWWWWWKK.......
.KWWWWWK.K......
.KWWWWWK.K......
.KWWWWWKK.......
..KKKKK.........
""", top=2)


ENDING_TILES = dict(story.CUBICLE_TILES)
ENDING_TILES.update({
    "N": (e_digital_clock, True),
    "Q": (e_clock, True),
    "F": (e_window, True),
    "U": (e_mug_desk, True),
})

ENDING_LAYOUT = """
=N==Q=FFF=
#n|MTU.|n#
#.|....|.#
#.|...P|.#
#.||..||.#
#........#
#|||..|||#
#nh....hn#
####dd####
"""

ENDING_MARKERS = {"bufo": [4, 2], "door": [4, 8]}

CREDITS_LAYOUT = "\n".join(["." * 10] * 9)

STANDALONE = {
    "ending_cubicle": ("Bufo's Cubicle, 5:00 PM", ENDING_LAYOUT),
    "credits": ("Credits", CREDITS_LAYOUT),
}

STANDALONE_PROPS = {
    "ending_cubicle": [
        {"name": "desk_phone", "pos": [4, 1]},
        {"name": "empty_mug", "pos": [5, 1]},
        {"name": "computer_shut_down", "pos": [3, 1]},
        {"name": "fake_plant", "pos": [6, 3]},
        {"name": "sunset_window", "pos": [6, 0]},
    ],
}


def render_ending():
    rows = ENDING_LAYOUT.strip().splitlines()
    canvas = blank("K", 160, 144)
    for my, row in enumerate(rows):
        for mx, ch in enumerate(row):
            g = ENDING_TILES[ch][0](mx, my, rows)
            for y in range(16):
                for x in range(16):
                    canvas[my * 16 + y][mx * 16 + x] = g[y][x]
    # The sunbeam from the window falls down and to the left over the carpet.
    for py in range(16, 144):
        for px in range(160):
            mx, my = px // 16, py // 16
            if rows[my][mx] != ".":
                continue
            shift = (py - 16) * 0.55
            if 96 - shift <= px <= 140 - shift and not (118 - shift <= px <= 121 - shift):
                canvas[py][px] = {"C": "A", "S": "a"}.get(canvas[py][px], canvas[py][px])
    img = Image.new("RGB", (160, 144))
    img.putdata([SUNSET_RGB[c] for row in canvas for c in row])
    return rows, img


CREDITS_COL = {
    "K": "#1a1028",  # night ink
    "Q": "#2c1e52",  # high sky indigo
    "U": "#6a2e72",  # violet
    "P": "#d8566e",  # pink
    "O": "#f48c48",  # orange
    "Y": "#ffd060",  # yellow
    "H": "#fff4c8",  # sun core, stars
    "N": "#241434",  # silhouettes
    "G": "#78b848",  # lily pad green
    "g": "#2e6a30",  # dark green
}
CREDITS_RGB = {k: hexc(v) for k, v in CREDITS_COL.items()}


def render_credits():
    """A sunset over the Pondcorp tower; a tiny frog walks home along the
    pond. Painted in 8 px bands so every tile keeps to 4 colours."""
    W_, H_ = 160, 144
    c = blank("Q", W_, H_)
    rnd = random.Random(42)
    horizon = 96
    # sky bands with dithered seams inside single tile rows
    for y in range(horizon):
        for x in range(W_):
            if y < 24:
                col = "Q"
            elif y < 32:
                col = "U" if (x + y) % 2 == 0 and y >= 28 or y >= 31 else "Q"
            elif y < 48:
                col = "U"
            elif y < 56:
                col = "P" if (x + y) % 2 == 0 and y >= 52 or y >= 55 else "U"
            elif y < 72:
                col = "P"
            elif y < 80:
                col = "O" if (x + y) % 2 == 0 and y >= 76 or y >= 79 else "P"
            else:
                col = "O"
            c[y][x] = col
    # stars in the high sky
    for _ in range(14):
        x, y = rnd.randrange(60, 158), rnd.randrange(2, 22)
        c[y][x] = "H"
    # the sun, sitting on the horizon
    sx, sy, sr = 112, 96, 22
    for y in range(64, horizon):
        for x in range(W_):
            d = math.hypot(x - sx, y - sy)
            if d <= sr:
                c[y][x] = "H" if d < sr - 5 else "Y"
    # heat bands across the sun
    for y in (86, 90, 93):
        for x in range(W_):
            if c[y][x] in "HY":
                c[y][x] = "O"
    # distant skyline on the horizon (right side)
    xs = 60
    while xs < W_:
        wd = rnd.choice([6, 8, 10])
        hgt = rnd.choice([4, 6, 8, 10])
        if sx - sr - 2 <= xs <= sx + sr:
            xs += 2
            continue
        for x in range(xs, min(xs + wd, W_)):
            for y in range(horizon - hgt, horizon):
                c[y][x] = "N"
        xs += wd + rnd.choice([0, 2, 4])
    # The Pondcorp tower: x 24..55, top at y 24, antenna to y 4.
    for y in range(24, horizon):
        for x in range(24, 56):
            c[y][x] = "N"
    for y in range(16, 24):
        for x in range(32, 48):
            c[y][x] = "N"
    for y in range(4, 16):
        c[y][39] = c[y][40] = "N"
    c[3][39] = c[3][40] = "P"
    # lit office windows (one person always works late)
    for y in range(40, horizon - 4, 6):
        for x in range(27, 53, 4):
            if rnd.random() < 0.35 or (x, y) == (43, 70):
                c[y][x] = c[y][x + 1] = "Y"
                c[y + 1][x] = c[y + 1][x + 1] = "Y"
    # the lily pad logo near the top of the tower
    cx, cy = 39.5, 31.5
    for y in range(26, 38):
        for x in range(32, 48):
            d = math.hypot(x - cx, y - cy)
            ang = math.degrees(math.atan2(x - cx, -(y - cy)))
            notch = 150 <= ang <= 180 or -180 <= ang <= -165
            if d <= 5.2 and not (notch and d > 1):
                c[y][x] = "G" if d < 4.3 else "g"
    # ground strip and the path along the pond
    for y in range(horizon, horizon + 8):
        for x in range(W_):
            c[y][x] = "N"
    # tiny frog silhouette walking home, briefcase in hand, in front of the sun
    frog = """
..KK.KK...
.KKKKKKK..
.KKKKKKK..
..KKKKK...
.KKKKKKKK.
..KKKKK.KK
..K...K.KK
.KK..KK...
"""
    paint(c, frog, top=horizon - 8, left=107)
    # the pond, reflecting the sky
    for y in range(horizon + 8, H_):
        for x in range(W_):
            band = (y - horizon - 8) // 8
            c[y][x] = "U" if band % 2 == 0 else "Q"
            if band >= 3:
                c[y][x] = "Q"
            # ripples
            if (y + band) % 4 == 0 and (x // 6 + y) % 3 == 0:
                c[y][x] = "Q" if c[y][x] == "U" else "U"
    # sun's reflection: broken streaks of yellow and orange under the sun
    for y in range(horizon + 9, H_, 3):
        half = max(2, 18 - (y - horizon) // 3)
        for x in range(sx - half, sx + half):
            if 0 <= x < W_ and rnd.random() < 0.8:
                c[y][x] = "Y" if abs(x - sx) < half // 2 else "O"
    # tower reflection: a dark column with a lit window or two
    for y in range(horizon + 8, H_):
        for x in range(24, 56):
            if (y + x // 3) % 3 != 0 and y < horizon + 40:
                c[y][x] = "N"
    # lily pads in the foreground (bottom left)
    for (px, py, r) in ((10, 132, 6), (24, 138, 4), (72, 128, 5)):
        for y in range(py - r, py + r + 1):
            for x in range(px - r * 2, px + r * 2 + 1):
                if 0 <= x < W_ and 0 <= y < H_:
                    d = math.hypot((x - px) / 2, y - py)
                    if d <= r and not (x > px and abs(y - py) <= 0):
                        c[y][x] = "G" if d < r - 1 else "g"
    img = Image.new("RGB", (W_, H_))
    img.putdata([CREDITS_RGB[ch] for row in c for ch in row])
    return img


# --- rendering and checks -----------------------------------------------------


def room_rows(layout):
    rows = layout.strip().splitlines()
    assert len(rows) == 9 and all(len(r) == 10 for r in rows), [len(r) for r in rows]
    return rows


def render_room(layout, name=None):
    rows = room_rows(layout)
    CTX["rows"] = rows
    CTX["name"] = name
    CTX["floor"] = ROOM_FLOOR.get(name, "marble")
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


def validate(name, img, colors=None):
    """GB Studio rules per image: <=4 colors per 8x8 tile, <=8 palettes per
    image, <=384 unique tiles."""
    letter = {v: k for k, v in (colors or RGB).items()}
    tiles, colorsets = set(), set()
    w, h = img.size
    assert (w, h) == (160, 144), name
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            px = tuple(img.getpixel((tx + x, ty + y)) for y in range(8) for x in range(8))
            cs = frozenset(px)
            assert len(cs) <= 4, (name, "too many colors", tx // 8, ty // 8, sorted(letter[c] for c in cs))
            tiles.add(px)
            colorsets.add(cs)
    assert len(tiles) <= 384, (name, "too many tiles", len(tiles))
    pals = cover_palettes(colorsets)
    if pals is None:
        sets = {"".join(sorted(letter[c] for c in cs)) for cs in colorsets if not any(cs < o for o in colorsets)}
        raise AssertionError(f"{name} needs more than 8 palettes: {sorted(sets)}")
    return len(tiles), ["".join(sorted(letter[c] for c in p)) for p in pals]


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
            if "B" in (mine, back):
                assert {mine, back} <= {"B", "d"}, f"boss door at {(gx, gy)}"
            elif "w" in (mine, back) or "k" in (mine, back):
                assert mine == back, f"{mine!r} door at {(gx, gy)} must meet the same kind, got {back!r}"
    return True


def walkable(rows, x, y, tiles=None):
    tiles = tiles or TILES
    return 0 <= x < 10 and 0 <= y < 9 and not tiles[rows[y][x]][-1]


def reach(rows, start, tiles=None):
    seen, todo = {start}, deque([start])
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if walkable(rows, nx, ny, tiles) and (nx, ny) not in seen:
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen


def check_props(name, rows, seen, props, tiles=None):
    tiles = tiles or TILES
    assert 3 <= len(props) <= 6, name
    for p in props:
        x, y = p["pos"]
        assert tiles[rows[y][x]][-1], (name, p["name"], "prop should be solid")
        assert any((x + ax, y + ay) in seen for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1))), (name, p["name"], "can't be examined")


def check_layouts():
    """Doors, elevators and chests connect; props are solid and examinable;
    the executives' row and the boss arena stay open; the ending has a path
    from Bufo's desk to the door."""
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
        check_props(name, rows, seen, PROPS_HINT[name])

    def clear(name, cells):
        rows = all_rooms[name]
        seen = reach(rows, next((x, y) for y in range(9) for x in range(10) if rows[y][x] in EXITS))
        for c in cells:
            assert walkable(rows, *c) and c in seen, (name, c)

    br = all_rooms["boardroom"]
    # five executives stand on row 1, columns 1-8; chairs at 1, 3, 5, 7, 8
    clear("boardroom", [(x, y) for x in range(1, 9) for y in range(4, 8)])
    assert all(walkable(br, x, 1) for x in range(1, 9)), "executives' row must be walkable"
    assert [x for x in range(10) if br[1][x] == "n"] == [1, 3, 5, 7, 8]
    assert all(TILES[br[y][x]][-1] for x in range(1, 9) for y in (2, 3)), "table spans rows 2-3, cols 1-8"
    assert br[0][4:6] == "SS" or "S" in br[0], "SYNERGY banner on the north wall"
    assert all_rooms["board_antechamber"][0][4:6] == "BB"
    assert all_rooms["exec_landing"][8][4:6] == "EE"
    assert all_rooms["brock_suite"][4][0] == "k" and "C" in "".join(all_rooms["brock_suite"])

    # Ending: Bufo's desk spot connects to the door.
    rows = ENDING_LAYOUT.strip().splitlines()
    tiles = ENDING_TILES
    bx, by = ENDING_MARKERS["bufo"]
    dx, dy = ENDING_MARKERS["door"]
    assert rows[dy][dx] == "d" and rows[dy][dx + 1] == "d"
    seen = reach(rows, (bx, by), tiles)
    assert (dx, dy) in seen, "ending: no path from Bufo's desk to the door"
    check_props("ending_cubicle", rows, seen, STANDALONE_PROPS["ending_cubicle"], tiles)


def main():
    check_doors()
    check_layouts()
    out_dir = ROOT / "assets/backgrounds"

    rendered, collision, errors = {}, [], []
    jobs = []
    for name, (_, _, title, layout) in ROOMS.items():
        rows, img = render_room(layout, name)
        jobs.append((name, title, f"exec_{name}.png", rows, img, RGB, TILES))
    rows, img = render_ending()
    jobs.append(("ending_cubicle", STANDALONE["ending_cubicle"][0], "ending_cubicle.png", rows, img, SUNSET_RGB, ENDING_TILES))
    jobs.append(("credits", "Credits", "credits.png", None, render_credits(), CREDITS_RGB, None))
    for name, title, fname, rows, img, colors, tiles in jobs:
        rendered[name] = img
        try:
            n, pals = validate(name, img, colors)
        except AssertionError as e:
            errors.append(e)
            print("FAIL", e)
            continue
        img.save(out_dir / fname)
        print(f"{fname} OK: unique tiles {n}/384, palettes {len(pals)}/8 ({' '.join(pals)})")
        if rows:
            coll = ["".join("X" if tiles[ch][-1] else "." for ch in row) for row in rows]
            collision.append(f"{title} ({fname})\n" + "\n".join(coll))

    (ROOT / "previews/exec-floor-collision.txt").write_text(
        "Executive Floor collision (X = solid), one cell per 16x16 metatile (2x2 GB tiles)\n"
        "Walkable specials: d door, k keycard door (trigger), B boss door, E elevator, C chest,\n"
        "  n executive chair (an executive stands on it), ',' red carpet\n"
        f"Ending markers: {ENDING_MARKERS}\n\n"
        + "\n\n".join(collision)
        + "\n"
    )

    # Floor overview at 2x; the ending scenes sit in spare grid cells.
    scale, gap = 2, 12
    cells = {n: (gx, gy, t) for n, (gx, gy, t, _) in ROOMS.items()}
    cells["ending_cubicle"] = (0, 3, "Ending: cubicle, 5:00 PM")
    cells["credits"] = (2, 3, "Credits backdrop")
    cols = max(c[0] for c in cells.values()) + 1
    rows_ = max(c[1] for c in cells.values()) + 1
    cw, chh = 160 * scale + gap, 144 * scale + gap
    ov = Image.new("RGB", (cols * cw + gap, rows_ * chh + gap), (0x0F, 0x13, 0x1A))
    draw = ImageDraw.Draw(ov)
    for name, (gx, gy, title) in cells.items():
        x0, y0 = gap + gx * cw, gap + gy * chh
        ov.paste(rendered[name].resize((160 * scale, 144 * scale), Image.NEAREST), (x0, y0))
        tw = draw.textlength(title)
        draw.rectangle([x0 + 4, y0 + 4, x0 + 12 + tw, y0 + 18], fill=(0x0F, 0x13, 0x1A))
        draw.text((x0 + 8, y0 + 5), title, fill=(0xF4, 0xF4, 0xEC))
    f = bufo_frame(2).resize((32, 32), Image.NEAREST)
    sx, sy = ROOMS["exec_landing"][:2]
    ov.paste(f, (gap + sx * cw + 4 * 32 + 16, gap + sy * chh + 7 * 32), f)
    bx, by = ENDING_MARKERS["bufo"]
    ov.paste(f, (gap + 0 * cw + bx * 32, gap + 3 * chh + by * 32), f)
    ov.save(ROOT / "previews/exec-floor-preview.png")
    print("overview:", ov.size)
    if errors:
        raise SystemExit(f"{len(errors)} image(s) failed validation")


if __name__ == "__main__":
    main()
