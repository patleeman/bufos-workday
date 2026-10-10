"""Draw the opening cutscene art for Bufo's Workday (GB Studio Color Only,
automatic palettes).

Outputs:
  assets/backgrounds/story_cubicle.png     Bufo's cubicle, 160x144
  assets/backgrounds/story_ceo_office.png  Brock Ribbitson's corner office
  assets/backgrounds/story_title.png       BUFO'S WORKDAY title card
  assets/backgrounds/story_layouts.json    layouts, solidity, markers, props
  assets/sprites/ceo.png                   96x16 Animated Actor sheet
  assets/sprites/palettes_story.json       suggested CEO sprite palette
  previews/story-preview.png               2x backgrounds, 8x CEO frames

Backgrounds are painted as character grids (one letter per color, see COL),
then checked like make_it_basement.validate(): at most 4 colors per 8x8
tile, every tile inside one of the named 4-color palettes in PAL, at most 8
of those palettes per image, at most 384 unique tiles.
"""

import json
import math
from collections import deque
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw

from make_it_basement import bufo_frame, hexc

ROOT = Path(__file__).resolve().parent.parent

# One letter per color.
COL = {
    "K": "#0f131a",  # ink
    "W": "#f8f4e8",  # warm white
    # cubicle floor
    "C": "#6a7896",  # carpet / partition light side
    "S": "#4a5674",  # carpet tile weave, partition fabric, desk front
    "L": "#c9c9c2",  # partition cap, laminate desk top
    "w": "#e4cf9c",  # beige wall
    "v": "#a88a58",  # wall top / shadow beige
    "B": "#58a8e0",  # screen blue
    "E": "#d84040",  # red
    "g": "#2e6a30",  # dark leaf
    "G": "#78b848",  # leaf, frog green
    # ceo office
    "R": "#7a1e3c",  # plush burgundy carpet
    "Y": "#f0c030",  # gold
    "o": "#a8701c",  # dark gold
    "H": "#fff4b0",  # gold shine
    "n": "#4a2818",  # dark wood
    "t": "#8a5430",  # wood
    "b": "#9cd0f0",  # sky
    "N": "#3a4a78",  # skyline
    # title
    "Q": "#1c2648",  # title night blue
    "M": "#6b9b4b",  # Bufo mid green
    "A": "#dfe8a8",  # Bufo cream
}
RGB = {k: hexc(v) for k, v in COL.items()}

PAL = {
    # cubicle
    "office_floor": "KSCL",
    "office_wall": "KvwW",
    "frame": "KYwW",
    "monitor": "KLBS",
    "phone": "KLES",
    "paper": "KLWS",
    "plant": "KgGC",
    # ceo office
    "plush": "KoYR",
    "gold_desk": "KoYH",
    "wood_wall": "KntY",
    "window": "KbNY",
    "poster": "KWEt",
    "portrait": "KGYt",
    "putting": "KGYR",
    # title
    "logo": "KYoQ",
    "face": "KMAQ",
    "sweat": "KBWQ",
    "clock": "KWEQ",
}
PAL_RGB = {k: frozenset(RGB[c] for c in v) for k, v in PAL.items()}


# --- grid helpers -----------------------------------------------------------


def blank(c, w=16, h=16):
    return [[c] * w for _ in range(h)]


def art_rows(art):
    rows = art.strip("\n").splitlines()
    return rows


def paint(g, art, top=0, left=0):
    """Paint letter art over a char grid. '.' is transparent."""
    for y, row in enumerate(art_rows(art)):
        for x, ch in enumerate(row):
            if ch != "." and ch != " ":
                if 0 <= top + y < len(g) and 0 <= left + x < len(g[0]):
                    g[top + y][left + x] = ch
    return g


def flip(g):
    return [row[::-1] for row in g]


SMALL = {
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
    "W": ["K...K", "K...K", "K.K.K", "KK.KK", "K...K"],
    "Y": ["K.K", "K.K", ".K.", ".K.", ".K."],
    "0": ["KKK", "K.K", "K.K", "K.K", "KKK"],
    "1": [".K.", "KK.", ".K.", ".K.", "KKK"],
    "9": ["KKK", "K.K", "KKK", "..K", "KKK"],
    ":": [".", "K", ".", "K", "."],
    "#": ["K.K", "KKK", "K.K", "KKK", "K.K"],
    "!": ["K", "K", "K", ".", "K"],
    "?": ["KK.", "..K", ".K.", "...", ".K."],
    " ": ["..", "..", "..", "..", ".."],
}


def text_width(text):
    return sum(len(SMALL[ch][0]) + 1 for ch in text) - 1


def stamp(g, x, y, text, c):
    for ch in text:
        glyph = SMALL[ch]
        for gy, row in enumerate(glyph):
            for gx, px in enumerate(row):
                if px == "K":
                    g[y + gy][x + gx] = c
        x += len(glyph[0]) + 1
    return g


# --- room rendering -----------------------------------------------------------


def render_layout(layout, tiles):
    rows = layout
    canvas = blank("K", 160, 144)
    for my, row in enumerate(rows):
        for mx, ch in enumerate(row):
            g = tiles[ch][0](mx, my, rows)
            assert len(g) == 16 and all(len(r) == 16 for r in g), ch
            for y in range(16):
                for x in range(16):
                    canvas[my * 16 + y][mx * 16 + x] = g[y][x]
    return canvas


def to_image(canvas):
    img = Image.new("RGB", (len(canvas[0]), len(canvas)))
    img.putdata([RGB[c] for row in canvas for c in row])
    return img


# =============================================================================
# Bufo's cubicle
# =============================================================================


def c_carpet(mx, my, rows=None):
    """Corporate carpet tiles: a woven stripe that turns 90 degrees per tile."""
    g = blank("C")
    horiz = (mx + my) % 2 == 0
    for y in range(16):
        for x in range(16):
            a, b = (x, y) if horiz else (y, x)
            if b % 4 == 1 and a % 4 != 3:
                g[y][x] = "S"
    return g


def c_wall(mx=0, my=0, rows=None):
    g = blank("w")
    g[0] = ["K"] * 16
    g[1] = ["W"] * 16
    for y in (14, 15):
        g[y] = ["K"] * 16
    g[13] = ["W"] * 16
    return g


def c_clock(mx, my, rows):
    """Stuck at 9:00."""
    return paint(c_wall(), """
.....KKKKKK.....
....KWWWWWWK....
...KWWWWKWWWK...
...KWWWWKWWWK...
...KWWWWKWWWK...
...KWKKKKWWWK...
...KWWWWWWWWK...
....KWWWWWWK....
.....KKKKKK.....
""", top=2)


def c_frame(mx, my, rows):
    """Employee of the Month: gold frame, default grey placeholder, no photo."""
    return paint(c_wall(), """
..KKKKKKKKKKKK..
..KYYYYYYYYYYK..
..KYWWWWWWWWYK..
..KYWWWKKWWWYK..
..KYWWKwwKWWYK..
..KYWWKwwKWWYK..
..KYWWWKKWWWYK..
..KYWKKwwKKWYK..
..KYKwwwwwwKYK..
..KYYYYYYYYYYK..
..KKKKKKKKKKKK..
""", top=2)


def c_notice(mx, my, rows):
    """Memo pinned to the wall: TPS, with a cover sheet."""
    g = paint(c_wall(), """
.KKKKKKKKKKKKK..
.KWWWWWWWWWWWK..
.KWWWWWWWWWWWK..
.KWWWWWWWWWWWK..
.KWWWWWWWWWWWK..
.KWWWWWWWWWWWK..
.KWWWWWWWWWWWK..
.KWWWWWWWWWWWK..
.KWKKKKKKKKKWK..
.KWWWWWWWWWWWKK.
.KWKKKKKWWWWWWK.
.KKKKKKKKKKKKKK.
""", top=2)
    return stamp(g, 2, 4, "TPS", "K")


def c_wall_top(mx, my, rows):
    """Wall seen from above (side and bottom walls): dark ceiling panels with
    a beige lip on the room side."""
    g = blank("K")
    h, wdt = len(rows), len(rows[0])
    for x in range(16):
        g[3][x] = g[11][x] = "v"
    for y in range(4, 11):
        g[y][4] = "v"
    for y in list(range(0, 3)) + list(range(12, 16)):
        g[y][12] = "v"
    for i in range(16):
        if mx == 0:
            g[i][15], g[i][14] = "w", "K"
        if mx == wdt - 1:
            g[i][0], g[i][1] = "w", "K"
        if my == h - 1:
            g[0][i], g[1][i] = "w", "K"
    return g


def c_door(mx, my, rows):
    """Bottom-middle exit: carpet running out between two door jambs."""
    g = c_carpet(mx, my)
    left = rows[my][mx - 1] != "d"
    for y in range(16):
        if left:
            g[y][0] = "K"
            g[y][1] = "L"
            g[y][2] = "K"
        else:
            g[y][15] = "K"
            g[y][14] = "L"
            g[y][13] = "K"
    return g


PARTITION = "|"
WALLISH = set("=#QFNd")


def c_partition(mx, my, rows):
    """Cubicle partition that joins its neighbours: a light top cap with the
    fabric front face showing wherever the cap is open to the south."""
    def at(x, y):
        if 0 <= y < len(rows) and 0 <= x < len(rows[0]):
            return rows[y][x]
        return "="

    n = at(mx, my - 1) == PARTITION or at(mx, my - 1) in WALLISH
    s = at(mx, my + 1) == PARTITION
    w = at(mx - 1, my) == PARTITION or (at(mx - 1, my) in WALLISH and mx - 1 == 0)
    e = at(mx + 1, my) == PARTITION or (at(mx + 1, my) in WALLISH and mx + 1 == len(rows[0]) - 1)
    g = c_carpet(mx, my)
    cap = set()
    if w or e:
        x0 = 0 if w else 5
        x1 = 15 if e else 10
        for y in range(1, 5):
            for x in range(x0, x1 + 1):
                cap.add((x, y))
    if n or s or not (w or e):
        y0 = 0 if n else 1
        y1 = 15 if s else 4
        for y in range(y0, y1 + 1):
            for x in range(5, 11):
                cap.add((x, y))

    def inside(x, y):
        if (x, y) in cap:
            return True
        # connected edges continue into the next tile
        if x < 0 and w and (0, y) in cap:
            return True
        if x > 15 and e and (15, y) in cap:
            return True
        if y < 0 and n and (x, 0) in cap:
            return True
        if y > 15 and s and (x, 15) in cap:
            return True
        return False

    for x, y in cap:
        edge = any(not inside(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        g[y][x] = "K" if edge else "L"
    # front face below the cap wherever the cap is open to the south
    for x in range(16):
        col = [y for y in range(16) if (x, y) in cap]
        if not col:
            continue
        bottom = max(col)
        if bottom == 15:
            continue
        for y in range(bottom + 1, min(bottom + 9, 16)):
            g[y][x] = "S"
        if bottom + 9 < 16:
            g[bottom + 9][x] = "K"
        if x in (0, 15):
            continue
        # face side edges
        if (x - 1, bottom) not in cap and not (x == 0 and w):
            for y in range(bottom + 1, min(bottom + 10, 16)):
                g[y][x] = "K"
        if (x + 1, bottom) not in cap and not (x == 15 and e):
            for y in range(bottom + 1, min(bottom + 10, 16)):
                g[y][x] = "K"
    # pinstripe on the fabric
    for y in range(16):
        for x in range(16):
            if g[y][x] == "S" and y % 3 == 0 and 0 < x < 15 and g[y][x - 1] == "S" and g[y][x + 1] == "S" and x % 2:
                g[y][x] = "C"
    return g


def c_desk(mx, my, rows):
    """Grey laminate desk against the wall."""
    deskish = set("MTUnD")
    g = blank("L")
    for x in range(16):
        g[11][x] = "K"
        g[12][x] = g[13][x] = g[14][x] = "S"
        g[15][x] = "K"
    if rows[my][mx - 1] not in deskish:
        for y in range(16):
            g[y][0] = "K"
    if rows[my][mx + 1] not in deskish:
        for y in range(16):
            g[y][15] = "K"
    return g


def c_monitor(mx, my, rows):
    return paint(c_desk(mx, my, rows), """
..KKKKKKKKKKKK..
..KSSSSSSSSSSK..
..KSBBBBBBBLSK..
..KSBBBBBBLBSK..
..KSBBBBBBBBSK..
..KSBBBBBBBBSK..
..KSSSSSSSSSSK..
..KKKKKKKKKKKK..
.......KK.......
..KKKKKKKKKKKK..
..KSKSKSKSKSKK..
""")


def c_phone(mx, my, rows):
    """The desk phone, ringing: handset jumping on its cradle."""
    return paint(c_desk(mx, my, rows), """
.K.KKKKKKKKKK.K.
K.KLLLLLLLLLLK.K
..KKKKKKKKKKKK..
.K.KK......KK.K.
K.KKKKKKKKKKKK.K
..KEKLLLLLLLLK..
..KKKLKLKLKLLK..
..KLLLLLLLLLLK..
..KLLLKLKLKLLK..
..KLLLLLLLLLLK..
..KKKKKKKKKKKK..
""", top=0)


def c_mug(mx, my, rows):
    """A sad mug with a frown, and one sad sheet of paper."""
    return paint(c_desk(mx, my, rows), """
................
.KKKKKKKK.......
.KSSSSSSK.......
.KWWWWWWKKK.....
.KWKWWKWK.K.....
.KWWWWWWK.K.....
.KWWKKWWKKK.....
.KWKWWKWK.......
.KWWWWWWK.......
..KKKKKK........
""", top=0)


def c_neighbour_desk(mx, my, rows):
    """Neighbour's desk: a monitor turned away and a leaning tower of paper."""
    g = c_desk(mx, my, rows)
    left = mx < 5
    art = """
KKKKKKKK........
KSSSSSSK........
KSBBBBSK........
KSBBBBSK........
KSSSSSSK........
KKKKKKKK........
...KK...........
................
.........KKKKKK.
.........KWWWWK.
.........KKKKKK.
"""
    g = paint(g, art, top=0, left=1)
    paint(g, """
KKKKKK
KWWWWK
KKKKKK
KWWWWK
KKKKKK
""", top=1, left=9)
    return flip(g) if not left else g


def c_chair(mx, my, rows):
    return paint(c_carpet(mx, my), """
....KKKKKKKK....
...KSSSSSSSSK...
...KSLLLLLLSK...
...KSSSSSSSSK...
...KKKKKKKKKK...
..KSK......KSK..
..KSKKKKKKKKSK..
..KSSSSSSSSSSK..
..KSSSSSSSSSSK..
..KKKKKKKKKKKK..
.......KK.......
....KKKKKKKK....
...KK..KK..KK...
""", top=1)


def c_plant(mx, my, rows):
    """The fake plant. It is thriving."""
    return paint(blank("C"), """
.....KK.KK.KK...
..KKKGGKGGKGGKK.
.KGGKGGgGGgGGGGK
KGGgGKGGGKGGgGGK
KGgGGGgGgGGGKGgK
.KGGKGGGGGgGGGGK
KGGGGgGKGGGGgGK.
KgGKGGGGGgGKGGGK
.KGGGgGGKGGGGgGK
KGgGGGKGGGGgGGGK
.KKGgGGGGgGGGKK.
...KKKKKKKKKK...
...KggggggggK...
....KgKKKKgK....
....KggggggK....
.....KKKKKK.....
""")


CUBICLE_TILES = {
    "=": (c_wall, True),
    "Q": (c_clock, True),
    "F": (c_frame, True),
    "N": (c_notice, True),
    "#": (c_wall_top, True),
    "d": (c_door, False),
    ".": (c_carpet, False),
    "|": (c_partition, True),
    "D": (c_desk, True),
    "M": (c_monitor, True),
    "T": (c_phone, True),
    "U": (c_mug, True),
    "n": (c_neighbour_desk, True),
    "h": (c_chair, True),
    "P": (c_plant, True),
}

CUBICLE_LAYOUT = [
    "=N==Q=F===",
    "#n|MTU.|n#",
    "#.|....|.#",
    "#.|...P|.#",
    "#.||..||.#",
    "#........#",
    "#|||..|||#",
    "#nh....hn#",
    "####dd####",
]

CUBICLE = {
    "background": "story_cubicle.png",
    "layout": CUBICLE_LAYOUT,
    "markers": {
        "bufo_start": [4, 2],
        "phone": [4, 1],
        "door": [4, 8],
    },
    "props": [
        {"name": "fake_plant", "pos": [6, 3]},
        {"name": "employee_of_the_month_frame", "pos": [6, 0]},
        {"name": "sad_mug", "pos": [5, 1]},
        {"name": "computer", "pos": [3, 1]},
        {"name": "neighbours_paper_tower", "pos": [8, 1]},
    ],
}


# =============================================================================
# CEO office
# =============================================================================


def e_carpet(mx, my, rows=None):
    """Plush burgundy carpet with a small gold motif."""
    g = blank("R")
    for cx, cy in ((3, 3), (11, 11)):
        g[cy][cx] = "Y"
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            g[cy + dy][cx + dx] = "o"
    return g


def e_wall(mx=0, my=0, rows=None):
    """Wood panelling with a gold crown rail."""
    g = blank("t")
    g[0] = ["K"] * 16
    g[1] = ["Y"] * 16
    g[2] = ["K"] * 16
    for y in range(3, 13):
        g[y][0] = "n"
        g[y][8] = "n"
    g[13] = ["n"] * 16
    g[14] = ["n"] * 16
    g[15] = ["K"] * 16
    return g


def e_wall_plain():
    """Wall behind framed things: wood and ink only."""
    g = blank("t")
    g[0] = ["K"] * 16
    g[15] = ["K"] * 16
    return g


def e_poster(mx, my, rows):
    """SYNERGY: two metatiles wide, motivational-poster black with a sunrise."""
    g = blank("K", 32, 16)
    paint(g, """
................................
.WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW.
................................
..............EEEE..............
.............EEEEEE.............
............EEEEEEEE............
..WWWWWWWWWWWWWWWWWWWWWWWWWWWW..
................................
................................
................................
................................
................................
................................
................................
.WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW.
................................
""")
    stamp(g, 2, 8, "SYNERGY", "W")
    half = 0 if rows[my][mx - 1] != "S" else 16
    return [row[half : half + 16] for row in g]


def e_portrait(mx, my, rows):
    """A gold-framed oil portrait of the CEO, by the CEO."""
    return paint(e_wall_plain(), """
.YYYYYYYYYYYYYY.
.YKKKKKKKKKKKKY.
.YKKGGKKKKGGKKY.
.YKGGGGKKGGGGKY.
.YKKKKKKKKKKKKY.
.YKGYYKGGKYYGKY.
.YKGGGGGGGGGGKY.
.YKGGGGGGGGKGKY.
.YKGKKKKKKKGGKY.
.YKKGGGGGGGGKKY.
.YKKKYKKKKYKKKY.
.YKKKKYYYYKKKKY.
.YYYYYYYYYYYYYY.
""", top=1)


def e_window(mx, my, rows):
    """Floor-to-ceiling glass, city skyline. Drawn per pixel from a skyline
    function so the top row and the side column join up."""
    g = blank("b")
    for y in range(16):
        for x in range(16):
            px, py = mx * 16 + x, my * 16 + y
            g[y][x] = skyline(px, py)
    if my == 0:
        g[0] = ["K"] * 16
        g[15] = ["K"] * 16
        if rows[0][mx - 1] != "W":
            for y in range(16):
                g[y][0] = "K"
                g[y][1] = "Y"
                g[y][2] = "K"
        # mullion every two tiles
        if mx % 2 == 0 and rows[0][mx - 1] == "W":
            for y in range(16):
                g[y][0] = "K"
    else:
        for y in range(16):
            g[y][0] = "K"
            g[y][1] = "Y"
            g[y][2] = "K"
        if my % 2 == 1:
            for x in range(16):
                g[0][x] = "K"
    return g


def skyline(px, py):
    """City skyline through the glass. The top window and each pane of the side
    window show upright towers rising from the bottom of the pane."""
    if py < 16:
        h = TOWERS[(px // 6) % len(TOWERS)]
        top = 15 - h
        if py > top:
            lx, ly = px % 6, py
            if lx in (1, 3) and ly % 3 == 1 and (px * 7 + py) % 5 != 0:
                return "Y"
            if lx == 5:
                return "K"
            return "N"
        return "b"
    # Side window: panes are 32 px tall (a mullion every two tiles).
    pane, ly = (py - 16) // 32, (py - 16) % 32
    pane_h = min(32, 128 - (16 + pane * 32))  # the bottom pane is cut off by the floor
    tx = px - 147
    if tx < 0:
        return "b"
    h = (TOWERS[(tx // 5 + pane * 3) % len(TOWERS)] + 6) * pane_h // 32
    if ly >= pane_h - h:
        lx = tx % 5
        if lx == 4:
            return "K"
        if lx in (1, 2) and ly % 3 == 1 and (px * 7 + py) % 5 != 0:
            return "Y"
        return "N"
    return "b"


TOWERS = [9, 12, 7, 13, 10, 6, 11, 13, 8, 12, 5, 10, 13, 9, 7, 12, 11]


def e_wall_top(mx, my, rows):
    """Dark wood wall seen from above."""
    g = blank("n")
    h, wdt = len(rows), len(rows[0])
    for i in range(16):
        if mx == 0:
            g[i][15] = "K"
            g[i][14] = "t"
        if my == h - 1:
            g[0][i] = "K"
            g[1][i] = "t"
    if my == h - 1 and mx == 0:
        g[0][15] = "K"
    for i in range(2, 16, 5):
        if mx == 0:
            g[i][6] = "t"
        if my == h - 1:
            g[8][i] = "t"
    return g


def e_door(mx, my, rows):
    g = e_carpet(mx, my)
    left = rows[my][mx - 1] != "d"
    for y in range(16):
        if left:
            g[y][0], g[y][1], g[y][2] = "K", "Y", "K"
        else:
            g[y][13], g[y][14], g[y][15] = "K", "Y", "K"
    return g


def e_putting(mx, my, rows):
    """The CEO's indoor putting green: 2x2 metatiles, flag in the cup and a
    gold golf ball."""
    big = blank("R", 32, 32)
    for y in range(32):
        for x in range(32):
            big[y][x] = e_carpet(x // 16, y // 16)[y % 16][x % 16]
    paint(big, """
.....................K..........
.....................KYK........
.....................KYYK.......
.....................KYYYK......
.....................KYYK.......
.......KKKKKKKKKKKKKKKYKKKKK....
.....KKGGGGGGGGGGGGGGKGGGGGGKK..
...KKGGGGGGGGGGGGGGGGKGGGGGGGGK.
..KGGGGGGGGGGGGGGGGGGKGGGGGGGGGK
.KGGGGGGGGGGGGGGGGGGGKGGGGGGGGGK
.KGGGGGGGGGGGGGGGGGKKKKKGGGGGGGK
KGGGGGGGGGGGGGGGGGGKKKKKGGGGGGGK
KGGGGGGGGGGGGGGGGGGGKKKGGGGGGGGK
KGGGKGGGKGGGGGGGGGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGK
KGGGGGGKKGGGGGGGGGGGGGGGGGGGGGGK
KGGGGGKYYKGGGGGGGGGGGGGGGGGGGGK.
.KGGGGKYYKGGGGGGGGGGGGGGGGGGGGK.
.KGGGGGKKGGGGGGGGGGGGGGGGGGGGK..
..KKGGGGGGGGGGGGGGGGGGGGGGGKK...
....KKKKKKKKKKKKKKKKKKKKKKK.....
""", top=4, left=0)
    big = [["R" if ch == "o" else ch for ch in row] for row in big]
    ox = 0 if rows[my][mx - 1] != "g" else 16
    oy = 0 if rows[my - 1][mx] != "g" else 16
    return [row[ox : ox + 16] for row in big[oy : oy + 16]]


def e_trophy(mx, my, rows):
    """#1 BOSS trophy. He bought it."""
    return paint(e_carpet(mx, my), """
...KKKKKKKKKK...
.KKYYYYYYYYYYKK.
KYKYYYoYYYYYYKYK
KYKYYooYYYYYYKYK
KYKYYYoYYYYYYKYK
.KKYYYoYYYYYoKK.
...KYooooYYoK...
....KYYYYYoK....
.....KKYoKK.....
......KYoK......
......KYoK......
....KKKKKKKK....
...KooooooooK...
...KoYYYYYYoK...
...KKKKKKKKKK...
""", top=1)


def e_runner(mx, my, rows):
    """Gold-edged runner from the door to the desk."""
    g = blank("R")
    left = rows[my][mx - 1] != ","
    for y in range(16):
        for x in range(16):
            gx = x + (0 if left else 16)  # position across the 32px runner
            if 4 <= gx <= 27 and ((gx + y) % 8 == 0 or (gx - y) % 8 == 0):
                g[y][x] = "o"
        edge = (1, 2, 3) if left else (14, 13, 12)
        g[y][edge[0]], g[y][edge[1]], g[y][edge[2]] = "K", "Y", "o"
        if left:
            g[y][0] = "R"
        else:
            g[y][15] = "R"
    return g


def e_desk_cell(mx, my, rows):
    # Drawn later as one big overlay; underneath it is carpet.
    return e_carpet(mx, my)


CEO_TILES = {
    "=": (e_wall, True),
    "S": (e_poster, True),
    "P": (e_portrait, True),
    "W": (e_window, True),
    "#": (e_wall_top, True),
    "d": (e_door, False),
    ".": (e_carpet, False),
    "D": (e_desk_cell, True),
    ",": (lambda mx, my, rows: e_runner(mx, my, rows), False),
    "g": (e_putting, True),
    "t": (e_trophy, True),
}

CEO_LAYOUT = [
    "=SSPWWWWWW",
    "#........W",
    "#..DDDD..W",
    "#..DDDD..W",
    "#...,,...W",
    "#...,,...W",
    "#gg.,,.t.W",
    "#gg.,,...W",
    "####dd####",
]

CEO = {
    "background": "story_ceo_office.png",
    "layout": CEO_LAYOUT,
    "markers": {
        "ceo": [4, 1],
        "desk_front": [4, 4],
        "door": [4, 8],
    },
    "props": [
        {"name": "golden_lily_pad_desk", "pos": [4, 3]},
        {"name": "synergy_poster", "pos": [1, 0]},
        {"name": "self_portrait", "pos": [3, 0]},
        {"name": "corner_window", "pos": [9, 4]},
        {"name": "putting_green", "pos": [2, 6]},
        {"name": "number_one_boss_trophy", "pos": [7, 6]},
    ],
}


def draw_lily_desk(canvas):
    """Golden lily pad desk over metatiles (3..6, 2..3): an ellipse with the
    lily pad's notch pointing at the CEO's spot, radial veins and a nameplate."""
    cx, cy, rx, ry = 79.5, 44.0, 30.5, 10.5
    thick = 4
    x0, x1, y0, y1 = 48, 111, 32, 63

    def in_top(x, y):
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0

    def in_notch(x, y):
        # the lily pad's wedge points at the CEO's spot behind the desk
        dx, dy = (x - cx) / rx, (y - cy) / ry
        if dy >= 0:
            return False
        ang = math.degrees(math.atan2(dx, -dy))  # 0 = straight up
        return -9 <= ang <= 9

    top, side = set(), set()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if in_top(x, y) and not in_notch(x, y):
                top.add((x, y))
            elif any(in_top(x, y - k) for k in range(1, thick + 1)) and not in_notch(x, y) and not in_notch(x, y - thick):
                side.add((x, y))
    body = top | side
    for x, y in body:
        canvas[y][x] = "Y" if (x, y) in top else "o"
    # centre where the veins meet, and a few short veins
    for ang in (-150, -100, -50, 0, 50, 100, 150):
        a = math.radians(ang)
        for r in range(3, 22):
            x = round(cx + math.sin(a) * r * rx / 30)
            y = round(cy + math.cos(a) * r * ry / 30)
            if (x, y) in top and not in_notch(x, y):
                canvas[y][x] = "o"
    # shine
    for x, y in top:
        d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
        if 0.3 < d < 0.5 and x < cx - 6 and y < cy - 2:
            canvas[y][x] = "H"
    # rim highlight line between top and side
    for x, y in top:
        if (x, y + 1) in side:
            canvas[y][x] = "Y"
    # outline
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if (x, y) in body and edge_of(body, x, y):
                canvas[y][x] = "K"
            elif (x, y) in top and (x, y + 1) in side and x % 1 == 0:
                pass
    # side/top separation
    for x, y in side:
        if (x, y - 1) in top and canvas[y][x] != "K":
            canvas[y][x] = "K"
    # nameplate on the desk: CEO
    px, py = 72, 45
    paint(canvas, """
KKKKKKKKKKKKKKK
KoooooooooooooK
KoKKKKKKKKKKKoK
KoKKKKKKKKKKKoK
KoKKKKKKKKKKKoK
KoKKKKKKKKKKKoK
KoKKKKKKKKKKKoK
KoooooooooooooK
KKKKKKKKKKKKKKK
""", top=py, left=px)
    stamp(canvas, px + 2, py + 2, "CEO", "Y")
    # shine only in tiles that don't also show carpet
    for ty in range(y0, y1 + 1, 8):
        for tx in range(x0, x1 + 1, 8):
            cells = [(tx + i, ty + j) for j in range(8) for i in range(8)]
            if any(canvas[y][x] == "R" for x, y in cells):
                for x, y in cells:
                    if canvas[y][x] == "H":
                        canvas[y][x] = "Y"


def stamp3(canvas, x, y):
    """3-row tall 'CEO' for the nameplate."""
    glyphs = [["KKK", "K..", "KKK"], ["KKK", "KK.", "KKK"], ["KKK", "K.K", "KKK"]]
    for gph in glyphs:
        for gy, row in enumerate(gph):
            for gx, p in enumerate(row):
                if p == "K":
                    canvas[y + gy][x + gx] = "K"
        x += 4


def edge_of(region, x, y):
    return any((x + dx, y + dy) not in region for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


# =============================================================================
# Title card
# =============================================================================

BIG = {
    "B": ["KKKK.", "K...K", "K...K", "KKKK.", "K...K", "K...K", "KKKK."],
    "U": ["K...K", "K...K", "K...K", "K...K", "K...K", "K...K", ".KKK."],
    "F": ["KKKKK", "K....", "K....", "KKKK.", "K....", "K....", "K...."],
    "O": [".KKK.", "K...K", "K...K", "K...K", "K...K", "K...K", ".KKK."],
    "'": ["K", "K", ".", ".", ".", ".", "."],
    "S": [".KKKK", "K....", "K....", ".KKK.", "....K", "....K", "KKKK."],
    "W": ["K...K", "K...K", "K...K", "K.K.K", "K.K.K", "KK.KK", "K...K"],
    "R": ["KKKK.", "K...K", "K...K", "KKKK.", "K.K..", "K..K.", "K...K"],
    "K": ["K...K", "K..K.", "K.K..", "KK...", "K.K..", "K..K.", "K...K"],
    "D": ["KKKK.", "K...K", "K...K", "K...K", "K...K", "K...K", "KKKK."],
    "A": [".KKK.", "K...K", "K...K", "KKKKK", "K...K", "K...K", "K...K"],
    "Y": ["K...K", "K...K", ".K.K.", "..K..", "..K..", "..K..", "..K.."],
}


def big_text(canvas, text, y, sx=3, sy=3, gap=3):
    glyphs = [BIG[ch] for ch in text]
    width = sum(len(gl[0]) * sx for gl in glyphs) + gap * (len(glyphs) - 1)
    x = (160 - width) // 2
    mask = set()
    for gl in glyphs:
        for gy, row in enumerate(gl):
            for gx, p in enumerate(row):
                if p == "K":
                    for dy in range(sy):
                        for dx in range(sx):
                            mask.add((x + gx * sx + dx, y + gy * sy + dy))
        x += len(gl[0]) * sx + gap
    h = 7 * sy
    # drop shadow then outline
    shadow = {(px + 1, py + 2) for px, py in mask} | {(px + 2, py + 2) for px, py in mask}
    outline = set()
    for px, py in mask | shadow:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                outline.add((px + dx, py + dy))
    for px, py in outline:
        canvas[py][px] = "K"
    for px, py in mask:
        ly = py - y
        canvas[py][px] = "o" if ly >= h - sy - 1 else "Y"
    return width


def disc(canvas, cx, cy, rx, ry, c):
    pts = set()
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                pts.add((x, y))
    if c:
        for x, y in pts:
            canvas[y][x] = c
    return pts


def thick_line(canvas, x0, y0, x1, y1, c, w=2):
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(n + 1):
        x = round(x0 + (x1 - x0) * i / n)
        y = round(y0 + (y1 - y0) * i / n)
        for dx in range(w):
            for dy in range(w):
                canvas[y + dy][x + dx] = c


def draw_title():
    c = blank("Q", 160, 144)
    big_text(c, "BUFO'S", 5)
    big_text(c, "WORKDAY", 32)

    # --- Bufo's big worried face -------------------------------------
    fx = 80
    head = disc(None, fx - 0.5, 101, 37, 20, None)
    bump_l = disc(None, fx - 20.5, 80, 15, 14, None)
    bump_r = disc(None, fx + 19.5, 80, 15, 14, None)
    face = head | bump_l | bump_r
    for x, y in face:
        c[y][x] = "M"
    # cream throat under the mouth
    for x, y in head:
        if y >= 109:
            c[y][x] = "A"
    # outline 2px
    for x, y in face:
        if any((x + dx, y + dy) not in face for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (-1, 1), (1, -1), (-1, -1))):
            c[y][x] = "K"
    # eyes
    for ex in (fx - 20.5, fx + 19.5):
        eye = disc(None, ex, 82, 9.5, 8.5, None)
        for x, y in eye:
            c[y][x] = "A"
        for x, y in eye:
            if edge_of(eye, x, y):
                c[y][x] = "K"
    # small worried pupils, glancing to the side (at the phone)
    for px in (fx - 19, fx + 21):
        for dy in range(4):
            for dx in range(3):
                c[83 + dy][px + dx] = "K"
    # worried brows: inner ends raised
    thick_line(c, fx - 33, 72, fx - 12, 66, "K", 3)
    thick_line(c, fx + 10, 66, fx + 31, 72, "K", 3)
    # nostrils
    for nx in (fx - 6, fx + 4):
        c[96][nx] = c[96][nx + 1] = "K"
    # wobbly mouth
    for i, x in enumerate(range(fx - 22, fx + 22)):
        y = 105 + round(1.6 * math.sin(i / 3.2))
        c[y][x] = "K"
        c[y + 1][x] = "K"
    # cheek line between face and throat
    # sweat drop off the right eye bump (own tiles: K B W Q)
    paint(c, """
...K...
..KBK..
.KBBBK.
KBWBBBK
KBWBBBK
KBBBBBK
.KBBBK.
..KKK..
""", top=64, left=114)

    # --- the clock: 9:00 AM ---------------------------------------
    cl = disc(None, 21.5, 92.5, 13, 13, None)
    for x, y in cl:
        c[y][x] = "W"
    for x, y in cl:
        if any((x + dx, y + dy) not in cl for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2))):
            c[y][x] = "K"
    # bells
    paint(c, """
.KKKK..............KKKK.
KEEEEK............KEEEEK
KEEEK..............KEEEK
.KKK................KKK.
""", top=76, left=10)
    # hands at 9:00
    for y in range(84, 93):
        c[y][21] = c[y][22] = "K"
    for x in range(13, 22):
        c[92][x] = c[93][x] = "K"
    c[92][21] = "E"
    for t in range(12):
        a = math.radians(t * 30)
        x = round(21.5 + math.sin(a) * 9.5)
        y = round(92.5 - math.cos(a) * 9.5)
        if t % 3 == 0:
            c[y][x] = "K"
    # legs
    c[106][11] = c[107][10] = c[106][31] = c[107][32] = "K"
    stamp(c, 7, 112, "9:00", "W")
    stamp(c, 27, 112, "AM", "W")

    # --- the desk phone, ringing ---------------------------------------
    paint(c, """
..KKKKKKKKKKKKKKKK..
.KEEEEEEEEEEEEEEEEK.
KEEKKKKKKKKKKKKKKEEK
KEK..............KEK
KKK.KKKKKKKKKKKK.KKK
....KWWWWWWWWWWK....
...KWWKKWWKKWWWWK...
...KWWWWWWWWWWWWK...
..KEEEEEEEEEEEEEEK..
..KEWKWKWKWEEEEEEK..
..KEEEEEEEEEEEEEEK..
..KEWKWKWKWEEKKEEK..
..KEEEEEEEEEEEEEEK..
..KKKKKKKKKKKKKKKK..
""", top=86, left=124)
    paint(c, """
W.....W
.W...W.
..W.W..
""", top=78, left=130)
    stamp(c, 126, 112, "RING!", "W")

    # --- press start ------------------------------------------------
    msg = "PRESS START"
    stamp(c, (160 - text_width(msg)) // 2, 130, msg, "W")
    return c


# =============================================================================
# Brock Ribbitson, CEO (sprite)
# =============================================================================

GBS = {
    ".": (0x65, 0xFF, 0x00),
    "D": (0x07, 0x18, 0x21),
    "M": (0x86, 0xC0, 0x6C),
    "L": (0xE0, 0xF8, 0xCF),
}

# light: gold (eyes, collar, power tie), mid: frog green, dark: navy suit/ink
CEO_PALETTE = ["#ffd84a", "#4f9a44", "#141a38"]

CEO_DOWN_A = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
DMMMMMMDDMMMMMMD
DMDDDDMMMMDDDDMD
DDLLDLDMMDLLDLDD
DMDDDDMMMMDDDDMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMMMMMMMMMDDMMD
DMMDDDDDDDDMMMMD
.DDMMMMMMMMMMDD.
DDDDDDDLLDDDDDDD
DMDDDDDLLDDDDDMD
DMDDDDDLLDDDDDMD
.DDDDDDLLDDDDDD.
..DDDD....DDDD..
"""

CEO_DOWN_B = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
DMMMMMMDDMMMMMMD
DMDDDDMMMMDDDDMD
DDLLDLDMMDLLDLDD
DMDDDDMMMMDDDDMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMMMMMMMMMDDMMD
DMMDDDDDDDDMMMMD
.DDMMMMMMMMMMDD.
DDDDDDDLLDDDDDDD
DMDDDDDLLDDDDDMD
DMDDDDDLLDDDDDMD
.DDDDDDLLDDDDDD.
.DDDD......DDD..
"""

CEO_UP_A = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
DMMMMMMDDMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMD.
.DDDMMMMMMMMDDD.
DDDDDDLLLLDDDDDD
DMDDDDDDDDDDDDMD
DMDDDDDDDDDDDDMD
.DDDDDDDDDDDDDD.
..DDDD....DDDD..
"""

CEO_UP_B = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
DMMMMMMDDMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
DMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMD.
.DDDMMMMMMMMDDD.
DDDDDDLLLLDDDDDD
DMDDDDDDDDDDDDMD
DMDDDDDDDDDDDDMD
.DDDDDDDDDDDDDD.
..DDDD.....DDD..
"""

CEO_RIGHT_A = """
........DDDD....
.......DMMMMD...
....DDDMMMMMMD..
...DMMDDDDDDDD..
..DMMMMDLLLDLD..
.DMMMMMMDDDDDMD.
.DMMMMMMMMMMMMMD
DMMMMMMMMMMMMDMD
DMMMMMMMMMMMDMMD
DMMMMMMMMDDDDMD.
.DMMMMMMMMMMMD..
DDDDDDDDDLLDD...
DMDDDDDDDLLLD...
DMMDDDDDDDLD....
.DDDDDDDDDDD....
..DDDD..DDDD....
"""

CEO_RIGHT_B = """
........DDDD....
.......DMMMMD...
....DDDMMMMMMD..
...DMMDDDDDDDD..
..DMMMMDLLLDLD..
.DMMMMMMDDDDDMD.
.DMMMMMMMMMMMMMD
DMMMMMMMMMMMMDMD
DMMMMMMMMMMMDMMD
DMMMMMMMMDDDDMD.
.DMMMMMMMMMMMD..
DDDDDDDDDLLDD...
DMDDDDDDDLLLD...
.DMMDDDDDDLD....
.DDDDDDDDDDD....
DDDD.....DDDD...
"""


def sprite_rows(art):
    rows = art.strip("\n").splitlines()
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), [len(r) for r in rows]
    assert all(set(r) <= set(".DML") for r in rows)
    return rows


CEO_FRAMES = [sprite_rows(a) for a in (CEO_DOWN_A, CEO_DOWN_B, CEO_UP_A, CEO_UP_B, CEO_RIGHT_A, CEO_RIGHT_B)]


def render_frames(frames, colors, scale=1, bg=None):
    img = Image.new("RGBA", (16 * len(frames) * scale, 16 * scale), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for f, rows in enumerate(frames):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                col = colors[ch]
                if col is None:
                    continue
                x0, y0 = (f * 16 + x) * scale, y * scale
                d.rectangle([x0, y0, x0 + scale - 1, y0 + scale - 1], fill=(*col, 255))
    return img


def ceo_colors():
    light, mid, dark = (hexc(h) for h in CEO_PALETTE)
    return {".": None, "D": dark, "M": mid, "L": light}


# =============================================================================
# checks
# =============================================================================


def validate(name, img):
    """make_it_basement.validate() with this file's palettes, plus a count of
    the distinct maximal tile color sets (what GB Studio's automatic palette
    pass has to merge)."""
    tiles, colorsets = set(), set()
    w, h = img.size
    assert (w, h) == (160, 144), (name, img.size)
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            px = tuple(img.getpixel((tx + x, ty + y)) for y in range(8) for x in range(8))
            cs = frozenset(px)
            assert len(cs) <= 4, (name, "too many colors in tile", tx, ty, [k for k, v in RGB.items() if v in cs])
            tiles.add(px)
            colorsets.add(cs)
    assert len(tiles) <= 384, name
    sets = [cs for cs in colorsets if not any(cs < o for o in colorsets)]
    for cs in sets:
        assert any(cs <= p for p in PAL_RGB.values()), (name, "no palette fits", sorted(k for k, v in RGB.items() if v in cs))
    cands = [k for k, p in PAL_RGB.items() if any(cs <= p for cs in sets)]
    for n in range(1, 9):
        for combo in combinations(cands, n):
            if all(any(cs <= PAL_RGB[k] for k in combo) for cs in sets):
                return len(tiles), combo, len(sets)
    raise AssertionError(f"{name} needs more than 8 palettes")


def check_room(name, room, tiles):
    rows = room["layout"]
    assert len(rows) == 9 and all(len(r) == 10 for r in rows), name
    solid = {ch: tiles[ch][1] for ch in sorted(set("".join(rows)))}

    def walk(x, y):
        return 0 <= x < 10 and 0 <= y < 9 and not solid[rows[y][x]]

    dx, dy = room["markers"]["door"]
    assert rows[dy][dx] == "d" and rows[dy][dx + 1] == "d" and dx == 4 and dy == 8, name
    seen, todo = {(dx, dy)}, deque([(dx, dy)])
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if walk(nx, ny) and (nx, ny) not in seen:
                seen.add((nx, ny))
                todo.append((nx, ny))
    for key, (mx, my) in room["markers"].items():
        if key in ("phone",):
            assert solid[rows[my][mx]], (name, key)
            continue
        assert walk(mx, my), (name, key, "not walkable")
        if key != "ceo":
            assert (mx, my) in seen, (name, key, "unreachable")
    for p in room["props"]:
        mx, my = p["pos"]
        assert solid[rows[my][mx]], (name, p["name"], "prop tile should be solid")
        assert any((mx + ax, my + ay) in seen for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1))), (name, p["name"], "can't be examined")
    return solid


def main():
    out_bg = ROOT / "assets/backgrounds"
    out_sp = ROOT / "assets/sprites"

    # --- rooms ---------------------------------------------------------
    cub = render_layout(CUBICLE_LAYOUT, CUBICLE_TILES)
    ceo = render_layout(CEO_LAYOUT, CEO_TILES)
    draw_lily_desk(ceo)
    title = draw_title()

    images = {
        "story_cubicle": to_image(cub),
        "story_ceo_office": to_image(ceo),
        "story_title": to_image(title),
    }
    errors = []
    for name, img in images.items():
        try:
            n, pals, nsets = validate(name, img)
        except AssertionError as e:
            errors.append(e)
            print("FAIL", e)
            continue
        img.save(out_bg / f"{name}.png")
        print(f"{name}.png OK: unique tiles {n}/384, palettes {len(pals)}/8 ({', '.join(pals)}), max color sets {nsets}")

    layouts = {}
    for key, room, tiles in (("cubicle", CUBICLE, CUBICLE_TILES), ("ceo_office", CEO, CEO_TILES)):
        solid = check_room(key, room, tiles)
        layouts[key] = {
            "background": room["background"],
            "layout": room["layout"],
            "solid": solid,
            "markers": room["markers"],
            "props": room["props"],
        }
    # The CEO stands behind his desk: keep a 2-wide strip clear for him.
    ceo_rows = CEO_LAYOUT
    for x in (4, 5):
        assert not CEO_TILES[ceo_rows[1][x]][1]
    assert CEO_TILES[ceo_rows[2][4]][1] and CEO_TILES[ceo_rows[3][4]][1]
    (out_bg / "story_layouts.json").write_text(json.dumps(layouts, indent=2) + "\n")

    # --- CEO sprite ------------------------------------------------------
    sheet = render_frames(CEO_FRAMES, {k: v for k, v in GBS.items()}).convert("RGB")
    used = {sheet.getpixel((x, y)) for x in range(96) for y in range(16)}
    assert used <= set(GBS.values()), used
    assert (0x30, 0x68, 0x50) not in used
    sheet.save(out_sp / "ceo.png")
    (out_sp / "palettes_story.json").write_text(json.dumps({"ceo": CEO_PALETTE}, indent=2) + "\n")
    print("ceo.png OK:", sheet.size, "colors:", len(used))

    # --- preview ---------------------------------------------------------
    scale, gap = 2, 12
    bg = (0x0F, 0x13, 0x1A)
    W = 3 * 160 * scale + 4 * gap
    sprite_h = 16 * 8
    H = gap + 144 * scale + gap + 144 * scale + gap + 16 + sprite_h + gap
    pv = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(pv)

    # row 1: raw backgrounds; row 2: with actors at their markers
    bufo_down = bufo_frame(0)
    bufo_up = bufo_frame(2)
    ceo_img = render_frames([CEO_FRAMES[0]], ceo_colors())
    for i, name in enumerate(images):
        x0 = gap + i * (160 * scale + gap)
        pv.paste(images[name].resize((160 * scale, 144 * scale), Image.NEAREST), (x0, gap))
        staged = images[name].copy().convert("RGBA")
        if name == "story_cubicle":
            mx, my = CUBICLE["markers"]["bufo_start"]
            staged.paste(bufo_up, (mx * 16, my * 16), bufo_up)
        elif name == "story_ceo_office":
            mx, my = CEO["markers"]["ceo"]
            staged.paste(ceo_img, (mx * 16 + 8, my * 16), ceo_img)
            mx, my = CEO["markers"]["desk_front"]
            staged.paste(bufo_up, (mx * 16 + 8, my * 16), bufo_up)
        y1 = gap * 2 + 144 * scale
        pv.paste(staged.convert("RGB").resize((160 * scale, 144 * scale), Image.NEAREST), (x0, y1))
    ys = gap * 3 + 144 * scale * 2
    d.text((gap, ys), "ceo.png (8x, suggested palette)  vs  bufo", fill=(0xF4, 0xF4, 0xEC))
    frames = render_frames(CEO_FRAMES, ceo_colors(), 8, bg=(*RGB["R"], 255))
    pv.paste(frames, (gap, ys + 16))
    bf = bufo_down.resize((128, 128), Image.NEAREST)
    bx = gap + frames.width + gap
    pv.paste(Image.new("RGB", (128, 128), RGB["R"]), (bx, ys + 16))
    pv.paste(bf, (bx, ys + 16), bf)
    pv.save(ROOT / "previews/story-preview.png")
    print("preview:", pv.size)
    if errors:
        raise SystemExit(f"{len(errors)} background(s) failed validation")


if __name__ == "__main__":
    main()
