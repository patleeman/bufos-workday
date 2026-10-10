"""Build Level 4, HR (Floor 4), for GB Studio (Color Only, automatic palettes).

Same module shape as make_break_room.py and make_open_office.py: ROOMS =
{name: (gx, gy, title, layout)} with triple-quoted 10x9 layouts, TILES =
{char: (builder, solid)} with the solid flag last, PROPS_HINT = {room:
[{"name", "pos"}]}. The engine (render, validate, door and reachability
checks, preview) lives in make_open_office.py.

Doors: north/south at columns 4-5 of the top/bottom row, east/west at row 4.
  d  door      B  boss door (top row)      k  keycard door with a card reader
  E  elevator (bottom row, walkable)          (walkable, a trigger guards it)
  C  chest spot (floor)                    y  paperwork on the floor (decal)

Outputs:
  assets/backgrounds/hr_<room>.png
  previews/hr-preview.png
  previews/hr-collision.txt
"""

import random
import sys

from make_open_office import (
    blank,
    build_all,
    check_doors_spec,
    check_layouts_spec,
    flip,
    framed,
    paint,
    run_index,
    slice16,
    stamp_center,
    wide,
)

COL = {
    "K": "#1a1418",  # warm ink
    "W": "#fbf3ea",  # cream
    "h": "#efd3c6",  # blush wall
    "H": "#c49a8a",  # wall shade, wall top
    "R": "#c4677a",  # dusty rose
    "e": "#dcc5a2",  # beige carpet
    "E": "#c6ab84",  # carpet pattern
    "t": "#a8784e",  # wood
    "n": "#6a4630",  # dark wood
    "c": "#bdb5a5",  # filing cabinet beige
    "q": "#857d6e",  # cabinet shade, shredder
    "G": "#86b85a",  # leaf
    "g": "#3a6a34",  # dark leaf
    "B": "#6ab0d8",  # TV blue
    "Y": "#f0c030",  # brass
}

PAL = {
    "wall": "KHhW",
    "wall_rose": "KhWR",
    "wall_wood": "KhWt",
    "wall_blue": "KhWB",
    "floor": "KEeW",
    "cabinet": "KcqW",
    "plant": "KgGe",
    "tea": "KtnW",
    "chair": "KRne",
    "desk": "Ktne",
    "paper_wood": "KtWe",  # policy easels
    "shredder": "KqWe",
    "elevator": "KqcY",
    "boss_door": "KntY",
    "key_door": "KntR",
}

ROOM_FLOOR = {}


def floor(x, y):
    """Soft beige carpet with a small diamond motif."""
    g = blank("e")
    for cx, cy in ((3, 3), (11, 11)):
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            g[cy + dy][cx + dx] = "E"
    for i in range(16):
        if (i + 2) % 8 == 0:
            g[7][i] = g[i][7] = "E"
    return g


def plain(x=0, y=0):
    return blank("e")


def on_floor(art, top=0, left=0):
    return paint(plain(), art, top=top, left=left)


def paperwork(x, y):
    """Forms on the floor, signed in triplicate (walkable)."""
    g = floor(x, y)
    paint(g, """
................
..WWWWWW........
..WKKKKW...WWWWW
..WWWWWW...WKKKW
..WKKWWW...WWWWW
..WWWWWW...WKKWW
...........WWWWW
.....WWWWWW.....
.....WKKKKW.....
.....WWWWWW.....
.....WKKKWW.....
.....WWWWWW.....
""", top=2)
    return flip(g) if (x + y) % 2 else g


def wall(x=0, y=0):
    g = blank("h")
    g[0] = ["K"] * 16
    g[1] = ["W"] * 16
    for xx in range(16):
        g[10][xx] = "H"  # chair rail
    g[11] = ["W"] * 16
    g[13] = ["H"] * 16
    g[14] = ["K"] * 16
    g[15] = ["K"] * 16
    return g


def wall_plain():
    """Wall behind decorations: K, h, W only."""
    g = blank("h")
    g[0] = ["K"] * 16
    g[1] = ["W"] * 16
    g[11] = ["W"] * 16
    g[13] = ["W"] * 16
    g[14] = ["K"] * 16
    g[15] = ["K"] * 16
    return g


def wall_top(x, y):
    g = blank("H")
    for yy in range(16):
        for xx in range(16):
            if (xx + yy) % 6 == 0:
                g[yy][xx] = "h"
    for i in range(16):
        if x == 0:
            g[i][15], g[i][14] = "K", "W"
        if x == 9:
            g[i][0], g[i][1] = "K", "W"
        if y == 8:
            g[0][i], g[1][i] = "K", "W"
    return g


def door(x, y):
    g = floor(x, y)
    if y in (0, 8):
        cols = (0, 1, 2) if x == 4 else (13, 14, 15)
        for yy in range(16):
            for xx in cols:
                g[yy][xx] = "K"
    else:
        for xx in range(16):
            for yy in (0, 1, 2, 13, 14, 15):
                g[yy][xx] = "K"
    return g


DOOR_ART = """
KKKKKKKKKKKKKKKK
KnnnnnnnnnnnnnnK
KntttttttttttttK
KntKKKKKKKKKKttK
KntKttttttttKttK
KntKttttttttKttK
KntKttttttttKttK
KntKKKKKKKKKKttK
KnttttttttttttKK
KntKKKKKKKKKKtKK
KntKttttttttKttK
KntKttttttttKttK
KntKKKKKKKKKKttK
KntttttttttttttK
KnnnnnnnnnnnnnnK
KKKKKKKKKKKKKKKK
"""


def boss_door(x, y):
    """Heavy panelled double door with brass handles."""
    g = paint(blank("K"), DOOR_ART)
    g[7][13] = g[8][13] = "Y"
    g[7][14] = g[8][14] = "Y"
    return g if x == 4 else flip(g)


def key_door(x, y):
    """Locked door with a keycard reader (red light: locked)."""
    g = paint(blank("K"), DOOR_ART)
    if x == 5:
        g = flip(g)
        paint(g, """
KKKK
KnnK
KRRK
KnnK
KKKK
""", top=5, left=10)
    else:
        g[8][13] = g[8][14] = "n"
    return g


def elevator(x, y):
    g = paint(blank("K"), """
KKKKKKKKKKKKKKKK
KqqqqqqqqqqqqqqK
KqKKKKKKKKKKKKqK
KqKccccccccccKqK
KqKcqqqqqqqqcKqK
KqKcqccccccqcKqK
KqKcqcqqqqcqcKqK
KqKcqcqqqqcqcKqK
KqKcqcqqqqcqcKqK
KqKcqcqqqqcqcKqK
KqKcqccccccqcKqK
KqKcqqqqqqqqcKqK
KqKccccccccccKqK
KqKKKKKKKKKKKKqK
KqqqqqqqqqqYYqqK
KKKKKKKKKKKKKKKK
""")
    for yy in range(2, 14):
        g[yy][15] = "K"
    return g if x == 4 else flip(g)


# --- wall decorations -----------------------------------------------------------


def art_we_care():
    """WE CARE banner, hung slightly crooked."""
    g, x0, x1 = framed(2, wall_plain, fill="R", border="K", inset=1, top=3, bottom=11)
    stamp_center(g, 5, "WE CARE", "W", x0, x1 + 1)
    g[3][x0] = g[3][x0 + 1] = "h"
    g[11][x1] = g[11][x1 - 1] = "h"
    for xx in (x0 + 2, x1 - 2):
        g[2][xx] = "K"
    return g


def art_policy():
    """A framed policy: dense text, one bold line."""
    g, x0, x1 = framed(1, wall_plain, fill="W", border="t", inset=2, top=2, bottom=12)
    for xx in range(x0, x1 + 1):
        g[2][xx] = g[12][xx] = "K"
    for yy in range(2, 13):
        g[yy][x0 - 1] = g[yy][x1 + 1] = "K"
    for yy in range(4, 11, 2):
        for xx in range(x0 + 2, x1 - 1):
            g[yy][xx] = "K" if (xx + yy) % 5 else "W"
    for xx in range(x0 + 2, x1 - 4):
        g[4][xx] = "K"
    return g


def art_hr_sign():
    g, x0, x1 = framed(1, wall_plain, fill="R", border="K", inset=2, top=2, bottom=11)
    stamp_center(g, 4, "HR", "W", x0, x1 + 1)
    return g


def art_files_sign():
    g, x0, x1 = framed(2, wall_plain, fill="W", border="K", inset=3, top=3, bottom=11)
    stamp_center(g, 5, "FILES A-Z", "K", x0, x1 + 1)
    return g


def art_deadline():
    """COMPLETE BY: YESTERDAY (3 tiles)."""
    g, x0, x1 = framed(3, wall_plain, fill="W", border="K", inset=0, top=2, bottom=13)
    stamp_center(g, 3, "COMPLETE BY", "K", x0, x1 + 1)
    stamp_center(g, 8 + 0, "YESTERDAY", "R", x0, x1 + 1)
    return g


def art_tv():
    """Training video on a wall TV: a slide of bullet points (2 tiles)."""
    g, x0, x1 = framed(2, wall_plain, fill="B", border="K", inset=2, top=2, bottom=12)
    for yy in (4, 7, 10):
        g[yy][x0 + 3] = "W"
        for xx in range(x0 + 5, x1 - 3 - (yy % 3) * 2):
            g[yy][xx] = "W"
    for xx in range(x0 + 8, x1 - 7):
        g[13][xx] = "K"
    return g


def art_voice():
    """YOUR VOICE MATTERS (3 tiles)."""
    g, x0, x1 = framed(3, wall_plain, fill="R", border="K", inset=0, top=2, bottom=13)
    stamp_center(g, 3, "YOUR VOICE", "W", x0, x1 + 1)
    stamp_center(g, 8, "MATTERS", "W", x0, x1 + 1)
    return g


def art_comply():
    g, x0, x1 = framed(2, wall_plain, fill="W", border="K", inset=1, top=2, bottom=12)
    for xx in range(x0 + 1, x1):
        g[3][xx] = "R"
        g[11][xx] = "R"
    stamp_center(g, 5, "COMPLY", "K", x0, x1 + 1)
    return g


# --- props -------------------------------------------------------------------


def p_cabinet(x, y):
    """Filing cabinet, full tile: three drawers with label slots."""
    g = blank("c")
    for i in range(16):
        g[0][i] = g[15][i] = "K"
        g[i][0] = g[i][15] = "K"
    for top in (1, 6, 11):
        for xx in range(1, 15):
            g[top + 4 if top != 11 else 14][xx] = "q"
        paint(g, """
KKKKKK
KWWWWK
KKKKKK
""", top=top + 1, left=5)
    for xx in range(1, 15):
        g[5][xx] = g[10][xx] = "K"
    rnd = random.Random(x * 7 + y * 13)
    if rnd.random() < 0.3:  # a drawer left open a crack
        for xx in range(2, 14):
            g[9][xx] = "K"
    return g


def p_plant(x, y):
    """Big friendly potted plant. Suspiciously friendly."""
    return on_floor("""
.....KK..KK.....
...KKGGKKGGKK...
..KGGgGGGGgGGK..
.KGgGGGKGGGGgGK.
.KGGGgGGGgGGGGK.
KGGKGGGGGGGKGGGK
KGgGGgGKGgGGGgGK
.KGGGGGGGGGGGGK.
..KKGgGGGGgGKK..
....KKKKKKKK....
....KgggggggK...
.....KgKKKgK....
.....KgggggK....
......KKKKK.....
""", top=1)


def p_tea(x, y):
    """Tea station counter: kettle, mugs, a jar of sad teabags (2 wide)."""
    big = blank("t", 32, 16)
    for xx in range(32):
        big[0][xx] = "K"
        big[6][xx] = "K"
        big[15][xx] = "K"
        for yy in range(7, 15):
            big[yy][xx] = "t"
    for yy in range(16):
        big[yy][0] = big[yy][31] = "K"
    for yy in range(7, 15):
        big[yy][15] = big[yy][16] = "n"
    big[10][12] = big[10][19] = "K"
    paint(big, """
...KKKK.....KKK..KKK....KKKKK...
..KWWWWKK..KWWWKKWWWK..KWnWnK...
..KWWWWK.K.KWWWKKWWWK..KWWWWK...
..KWWWWKK..KKKK.KKKK...KKKKK....
..KKKKKK........................
""", top=1)
    return slice16(big, run_index(x, y, "T"))


def p_chair(x, y):
    """Training chair, seen from behind, facing the TV."""
    return on_floor("""
................
...KKKKKKKKKK...
..KRRRRRRRRRRK..
..KRRRRRRRRRRK..
..KRRRRRRRRRRK..
..KRRRRRRRRRRK..
...KKKKKKKKKK...
..KnnnnnnnnnnK..
..KKKKKKKKKKKK..
...Kn......nK...
...Kn......nK...
...KK......KK...
""", top=2)


def p_couch(x, y):
    """Rose couch, two tiles wide."""
    left = run_index(x, y, "o") == 0
    art = """
................
..KKKKKKKKKKKKKK
.KRRRRRRRRRRRRRR
KRKRRRRRRRRRRRRR
KRKRRRRRRRRRRRRR
KRKKKKKKKKKKKKKK
KRKRRRRRRRRRRRRR
KRKRRRRRRRRRRRRn
KRKRRRRRRRRRRRRn
KRKnnnnnnnnnnnn.
KKKKKKKKKKKKKKKK
.Kn..........KnK
"""
    g = on_floor(art, top=1)
    return g if left else flip(g)


def p_desk(x, y):
    """A wood desk (runs join). Empty: no papers, no plant, no person."""
    rows = CTX_rows()
    left_end = rows[y][x - 1] not in "Dr"
    right_end = rows[y][x + 1] not in "Dr"
    g = plain()
    for yy in range(1, 13):
        for xx in range(16):
            g[yy][xx] = "t"
    for xx in range(16):
        g[1][xx] = "K"
        g[9][xx] = "K"
        g[10][xx] = g[11][xx] = "n"
        g[12][xx] = "K"
    if left_end:
        for yy in range(1, 15):
            g[yy][0] = "K"
        g[13][1] = g[14][1] = "n"
        g[13][0] = g[14][0] = "K"
        g[13][2] = g[14][2] = "K"
    if right_end:
        for yy in range(1, 15):
            g[yy][15] = "K"
        g[13][14] = g[14][14] = "n"
        g[13][15] = g[14][15] = "K"
        g[13][13] = g[14][13] = "K"
    return g


def CTX_rows():
    from make_open_office import CTX

    return CTX["rows"]


def p_reception(x, y):
    """Reception desk with a tiny bell and a sign-in sheet."""
    g = p_desk(x, y)
    if run_index(x, y, "r") == 0:
        paint(g, """
KKKKKK
KWWWWK
KWKKWK
KWWWWK
KKKKKK
""", top=3, left=5)
    return g


def p_suggestion_box(x, y):
    """Suggestion box, overflowing onto the floor."""
    return on_floor("""
...WWW.WWWW.WW..
..WWWWWWWWWWWWW.
..WWWWWWWWWWWW..
..KKKKKKKKKKKK..
..KqqqqqqqqqqK..
..KqqKKKKKKqqK..
..KqqqqqqqqqqK..
..KqqqqqqqqqqK..
..KqqqqqqqqqqK..
..KKKKKKKKKKKK..
WW.........WW...
WW...WW....WW...
.....WW.........
""", top=1)


def p_shredder(x, y):
    """Shredder on a bin, full of confetti that used to be complaints."""
    return on_floor("""
................
...KKKKKKKKKK...
...KqqqqqqqqK...
...KqKKKKKKqK...
...KKKKKKKKKK...
...KWqWqWWqWK...
...KqWWqWqWqK...
...KWWqWWWqWK...
...KqWqWqWWqK...
...KWWWqWqWWK...
...KKKKKKKKKK...
.....W.W..W.....
""", top=2)


def p_policy_stand(x, y):
    """A framed policy on an easel."""
    return on_floor("""
..KKKKKKKKKKKK..
..KttttttttttK..
..KtWWWWWWWWtK..
..KtWKKKKKKWtK..
..KtWWWWWWWWtK..
..KtWKKKKKWWtK..
..KtWWWWWWWWtK..
..KtWKKKKKKWtK..
..KtWWWWWWWWtK..
..KttttttttttK..
..KKKKKKKKKKKK..
....Kt....tK....
...Kt......tK...
..KK........KK..
""", top=1)


TILES = {
    # structure
    ".": (floor, False),
    "C": (floor, False),
    "y": (paperwork, False),
    "=": (wall, True),
    "#": (wall_top, True),
    "d": (door, False),
    "B": (boss_door, False),
    "k": (key_door, False),  # keycard door: a trigger guards it
    "E": (elevator, False),
    # wall decorations (row 0)
    "V": (wide(art_we_care, "V"), True),
    "p": (lambda x, y: art_policy(), True),
    "H": (lambda x, y: art_hr_sign(), True),
    "A": (wide(art_files_sign, "A"), True),
    "[": (wide(art_deadline, "[_]"), True),
    "_": (wide(art_deadline, "[_]"), True),
    "]": (wide(art_deadline, "[_]"), True),
    "<": (wide(art_tv, "<>"), True),
    ">": (wide(art_tv, "<>"), True),
    "(": (wide(art_voice, "(*)"), True),
    "*": (wide(art_voice, "(*)"), True),
    ")": (wide(art_voice, "(*)"), True),
    "M": (wide(art_comply, "M"), True),
    # props
    "F": (p_cabinet, True),
    "G": (p_plant, True),
    "T": (p_tea, True),
    "h": (p_chair, True),
    "o": (p_couch, True),
    "D": (p_desk, True),
    "r": (p_reception, True),
    "s": (p_suggestion_box, True),
    "x": (p_shredder, True),
    "P": (p_policy_stand, True),
}

ROOMS = {
    "compliance_room": (1, 0, "Compliance Office", """
==ppMMpp==
#FF....FF#
#F......F#
#........#
#........#
#...y....#
#F......F#
#F......F#
####dd####
"""),
    "policy_hall": (1, 1, "Policy Hall", """
==ppBBpp==
#G......G#
#.P....P.#
#........#
#.P....P.#
#........#
#.P....P.#
#G......G#
####dd####
"""),
    "complaints": (2, 1, "Complaints Department", """
==(*)=====
#s......C#
#y...h...#
#...DD...#
#........#
#x.......#
#........#
#y.......#
####kk####
"""),
    "personnel_files": (0, 2, "Personnel Files", """
===AA=====
#C..F....#
#FF.F.FF.#
#...F..F.#
#.FFF.FF.d
#.F......#
#.F.FFFF.#
#...F....#
##########
"""),
    "hr_reception": (1, 2, "HR Reception", """
===Hdd=VV=
#TT.....G#
#........#
#........#
d..rr....d
#........#
#oo....G.#
#........#
####dd####
"""),
    "training_room": (2, 2, "Mandatory Training", """
=[_]kk<>==
#........#
#........#
#.hhh.hh.#
d........#
#.hhh.hh.#
#........#
#.hhh.hh.#
##########
"""),
    "hr_landing": (1, 3, "Floor 4 Landing", """
=VV=dd=pp=
#G......G#
#........#
#........#
#........#
#y.......#
#Goo....G#
#........#
####EE####
"""),
}
for _n in ROOMS:
    ROOM_FLOOR[_n] = "carpet"

PROPS_HINT = {
    "compliance_room": [
        {"name": "comply_sign", "pos": [4, 0]},
        {"name": "framed_policy", "pos": [3, 0]},
        {"name": "filing_tower", "pos": [2, 1]},
        {"name": "filing_tower_east", "pos": [7, 1]},
    ],
    "policy_hall": [
        {"name": "framed_policy_wall", "pos": [2, 0]},
        {"name": "policy_on_easel_1", "pos": [2, 2]},
        {"name": "policy_on_easel_2", "pos": [7, 4]},
        {"name": "policy_on_easel_3", "pos": [2, 6]},
        {"name": "friendly_plant", "pos": [1, 1]},
    ],
    "complaints": [
        {"name": "your_voice_matters_poster", "pos": [3, 0]},
        {"name": "overflowing_suggestion_box", "pos": [1, 1]},
        {"name": "empty_desk", "pos": [4, 3]},
        {"name": "empty_chair", "pos": [5, 2]},
        {"name": "shredder", "pos": [1, 5]},
    ],
    "personnel_files": [
        {"name": "files_a_z_sign", "pos": [3, 0]},
        {"name": "filing_cabinet", "pos": [4, 1]},
        {"name": "your_personnel_file_cabinet", "pos": [7, 6]},
        {"name": "locked_cabinet", "pos": [2, 5]},
    ],
    "hr_reception": [
        {"name": "tea_station", "pos": [1, 1]},
        {"name": "reception_desk", "pos": [3, 4]},
        {"name": "hr_sign", "pos": [3, 0]},
        {"name": "waiting_couch", "pos": [1, 6]},
        {"name": "friendly_plant", "pos": [8, 1]},
    ],
    "training_room": [
        {"name": "complete_by_yesterday_poster", "pos": [2, 0]},
        {"name": "training_video_tv", "pos": [6, 0]},
        {"name": "front_row_chair", "pos": [2, 3]},
        {"name": "back_row_chair", "pos": [7, 7]},
    ],
    "hr_landing": [
        {"name": "we_care_banner", "pos": [2, 0]},
        {"name": "framed_policy", "pos": [7, 0]},
        {"name": "friendly_plant", "pos": [1, 1]},
        {"name": "waiting_couch", "pos": [2, 6]},
    ],
}

CLEARS = {
    "compliance_room": [(x, y) for x in range(2, 8) for y in range(2, 8)] + [(4, 1), (5, 1)],
    "hr_reception": [(6, 3), (5, 3), (7, 3), (6, 2), (6, 4)],
}


def spec():
    return sys.modules[__name__]


def check_doors():
    check_doors_spec(spec())


def check_layouts():
    check_layouts_spec(spec(), CLEARS)


def main():
    build_all(spec(), "hr", "hr-preview.png", "hr-collision.txt", "HR (Floor 4)", CLEARS)


if __name__ == "__main__":
    main()
