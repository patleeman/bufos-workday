"""Build the IT Basement dungeon rooms for GB Studio (Color Only, automatic palettes).

Each room is one Game Boy screen: 10x9 metatiles of 16x16 px (160x144). Metatiles
are drawn straight in colors from COL. validate() then checks GB Studio's rules
per room: every 8x8 tile uses at most 4 colors and fits one of the named 4-color
palettes in PAL, the room needs at most 8 of those palettes, and it has at most
384 unique 8x8 tiles.

Outputs:
  assets/backgrounds/basement_<room>.png   import these into GB Studio
  previews/it-basement-preview.png         2x dungeon overview with Bufo
  previews/it-basement-collision.txt       which tiles are solid (paint in GB Studio)
"""

import random
from collections import deque
from itertools import combinations
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def hexc(h):
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


# One letter per color, used by the pixel art below.
COL = {
    "K": "#0f131a",  # ink
    "D": "#3a4456",  # dark concrete
    "F": "#6f7a8e",  # floor
    "L": "#a9b3c2",  # light concrete
    "P": "#b8c0cc",  # paper grey
    "W": "#f4f4ec",  # paper white
    "Y": "#e0b020",  # hazard yellow / gold
    "n": "#5c3a24",  # dark wood, coffee
    "t": "#a8743e",  # tan wood, cardboard
    "o": "#7a4a1c",  # chest brown
    "g": "#2e6a30",  # dark leaf
    "G": "#78b848",  # leaf, frog green
    "r": "#5a1620",  # dark carpet
    "R": "#9a2a38",  # carpet red
    "E": "#d84040",  # alarm red
    "B": "#58a8e0",  # cold blue, water
    "V": "#48e070",  # LED green
    "s": "#2a313c",  # rack dark
    "S": "#5c6676",  # rack grey
}
COL = {k: hexc(v) for k, v in COL.items()}

# Named 4-color palettes. Each room may use at most 8 of them.
PAL = {
    "concrete": "KDFL",
    "rack": "KsSV",
    "rack_red": "KsSE",
    "hazard": "KDYF",
    "wood": "KntF",
    "plant": "KgGF",
    "carpet": "KrRW",
    "paper": "KFPW",
    "chest": "KoYF",
    "wall_red": "KFLE",
    "wall_green": "KFLG",
    "wall_yellow": "KFLY",
    "wall_blue": "KFLB",
    "floor_blue": "KDFB",
    "floor_green": "KDFV",
    "floor_brown": "KDFn",
    "floor_paper": "KDFW",
}
PAL_RGB = {k: [COL[c] for c in v] for k, v in PAL.items()}


def grid(fill=0):
    return [[fill] * 16 for _ in range(16)]


def rect(g, x0, y0, x1, y1, c):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            g[y][x] = c


def from_art(art, key):
    rows = art.strip().splitlines()
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), art
    return [[key[ch] for ch in row] for row in rows]


# --- metatiles -------------------------------------------------------------


def t_floor(seed):
    rnd = random.Random(seed)
    g = grid(2)
    for x in range(16):
        g[15][x] = 1  # tile seam
    for y in range(16):
        g[y][15] = 1
    for _ in range(4):
        g[rnd.randrange(15)][rnd.randrange(15)] = rnd.choice([1, 3])
    return g


def t_ceiling():
    g = grid(0)
    for y in (3, 11):
        for x in range(16):
            g[y][x] = 1
    for y in range(4, 11):
        g[y][4] = 1
    for y in list(range(0, 3)) + list(range(12, 16)):
        g[y][12] = 1
    return g


def t_stairs():
    g = grid(2)
    for step in range(4):
        y = step * 4
        rect(g, 0, y, 15, y, 0)
        rect(g, 0, y + 1, 15, y + 1, 3)
        rect(g, 0, y + 2, 15, y + 3, 2 if step % 2 else 3)
    for y in range(16):
        g[y][0] = 1
        g[y][15] = 1
    return g


def t_door():
    g = grid(1)
    rect(g, 0, 0, 15, 1, 0)
    rect(g, 3, 4, 12, 15, 2)
    for y in range(4, 16):
        g[y][3] = 0
        g[y][12] = 0
    return g


def t_post():
    g = t_floor(99)
    art = """
................
.....######.....
....#333333#....
...#33222233#...
...#32211223#...
...#32133123#...
...#32133123#...
...#32211223#...
...#32222223#...
...#22222222#...
...#22122122#...
...#22222222#...
...#11111111#...
....########....
.....111111.....
................
"""
    over = from_art(art, {".": None, "#": 0, "1": 1, "2": 2, "3": 3})
    for y in range(16):
        for x in range(16):
            if over[y][x] is not None:
                g[y][x] = over[y][x]
    return g


def t_hazard_edge():
    g = grid(3)
    rect(g, 0, 8, 15, 15, 0)
    for y in range(9, 14):
        for x in range(16):
            if (x + y) % 6 < 3:
                g[y][x] = 2
    rect(g, 0, 8, 15, 8, 1)
    rect(g, 0, 14, 15, 15, 0)
    return g


def t_trench(variant):
    g = grid(0)
    rnd = random.Random(variant)
    # tangled cables: two wavy lines per tile
    for color, phase in ((2, rnd.randrange(16)), (1, rnd.randrange(16))):
        y = rnd.randrange(3, 13)
        for x in range(16):
            y = max(1, min(14, y + rnd.choice([-1, 0, 0, 1])))
            g[y][x] = color
            if (x + phase) % 5 == 0:
                g[y + 1][x] = color
    return g


def t_rack():
    g = grid(1)
    rect(g, 0, 0, 15, 1, 2)
    for y in range(16):
        g[y][0] = 0
        g[y][15] = 0
    rect(g, 0, 15, 15, 15, 0)
    for unit in range(3):
        y = 3 + unit * 4
        rect(g, 2, y, 13, y + 2, 2)
        rect(g, 3, y + 1, 9, y + 1, 1)
        g[y + 1][11] = 3
        if unit != 1:
            g[y + 1][12] = 3
    return g


def t_desk():
    art = """
################
#22222222222222#
#21222222122222#
#22222122222212#
#22122222222222#
#22222221222222#
################
#11111111111111#
#11#111111111#1#
#11#11000011#11#
#11111111111111#
################
#1##33333333##1#
#1#3333333333#1#
###3333333333###
3333333333333333
"""
    return from_art(art, {"#": 0, "1": 1, "2": 2, "3": 3, "0": 0})


def t_box():
    art = """
3333333333333333
3##############3
3#222222112222#3
3#222222112222#3
3#111111111111#3
3#222222222222#3
3#222222222222#3
3#221222222222#3
3#222222222122#3
3#222222222222#3
3#212222222222#3
3#222222222222#3
3##############3
3330000000000033
3333333333333333
3333333333333333
"""
    return from_art(art, {"#": 0, "0": 0, "1": 1, "2": 2, "3": 3})


def t_plant():
    art = """
3333331113333333
3333112221133333
3331222212213333
3312221222221333
3122122221222133
3122212212222133
3312222122221333
3331122222113333
3333311211333333
3333300000033333
3333011111103333
3333011111103333
3333301111033333
3333301111033333
3333330000333333
3333333333333333
"""
    return from_art(art, {"0": 0, "1": 1, "2": 2, "3": 3})


def t_monitors():
    art = """
1111111111111111
1100000000000111
1022222222222011
1023000000003201
1020011111100201
1020011111100201
1020010000100201
1022222222222001
1100022222000011
1000000000000001
0222222202222220
0230000202300020
0201110202011020
0222222202222220
1000000010000001
1111111111111111
"""
    return from_art(art, {"0": 0, "1": 1, "2": 2, "3": 3})


def t_sign():
    art = """
1111111111111111
1000000000000001
1033333333333301
1030003000300301
1033333333333301
1030303300030301
1033333333333301
1030030003330301
1033333333333301
1000000000000001
1111022220111111
1111022220111111
1110222222011111
1102221122201111
1102211112201111
1111111111111111
"""
    return from_art(art, {"0": 0, "1": 1, "2": 2, "3": 3})


def t_locked_door():
    art = """
0000000000000000
0111111111111110
0121111111111210
0111111111111110
0111100000111110
0111022222011110
0110222222201110
0110220002201110
0110222022201110
0110222022201110
0110222222201110
0111000000011110
0111111111111110
0121111111111210
0111111111111110
0000000000000000
"""
    return from_art(art, {"0": 0, "1": 1, "2": 2, "3": 3})


def t_boss_door():
    art = """
0000000000000000
0222222222222220
0211111111111120
0212222222222120
0212111111112120
0212122222212120
0212120000212120
0212120220212120
0212120220212120
0212120000212120
0212122222212120
0212111111112120
0212222222222120
0211111111111120
0222222222222220
0000000000000000
"""
    return from_art(art, {"0": 0, "1": 1, "2": 2, "3": 3})


def t_tape_shelf():
    art = """
0000000000000000
0111111111111110
0122212221222110
0120212021202110
0122212221222110
0111111111111110
0000000000000000
0111111111111110
0122212221222110
0120212021202110
0122212221222110
0111111111111110
0000000000000000
0101111111111010
0101111111111010
1111111111111111
"""
    return from_art(art, {"0": 0, "1": 1, "2": 2, "3": 3})


# --- color helpers ----------------------------------------------------------


def ipal(g, pal):
    """Index grid (0-3) -> color grid using a named palette."""
    cols = PAL_RGB[pal]
    return [[cols[v] for v in row] for row in g]


def fill(c):
    return [[COL[c]] * 16 for _ in range(16)]


def over(base, art, top=0, left=0):
    """Paint letter art over a color grid. '.' is transparent."""
    g = [row[:] for row in base]
    for y, row in enumerate(art.strip("\n").splitlines()):
        for x, ch in enumerate(row):
            if ch != ".":
                g[top + y][left + x] = COL[ch]
    return g


FONT = {
    "B": ["KK.", "K.K", "KK.", "K.K", "KK."],
    "1": [".K.", "KK.", ".K.", ".K.", "KKK"],
    "E": ["KKK", "K..", "KK.", "K..", "KKK"],
    "X": ["K.K", "K.K", ".K.", "K.K", "K.K"],
    "I": ["K", "K", "K", "K", "K"],
    "T": ["KKK", ".K.", ".K.", ".K.", ".K."],
    "9": ["KKK", "K.K", "KKK", "..K", "KKK"],
    "!": ["K", "K", "K", ".", "K"],
}


def stamp(g, x, y, text, c):
    for ch in text:
        glyph = FONT[ch]
        for gy, row in enumerate(glyph):
            for gx, px in enumerate(row):
                if px == "K":
                    g[y + gy][x + gx] = COL[c]
        x += len(glyph[0]) + 1
    return g


# --- floors ----------------------------------------------------------------


def floor(x, y):
    return ipal(t_floor((x * 3 + y * 5) % 4), "concrete")


def floor_clean():
    """Floor with seams but no specks, the base for floor decals."""
    g = fill("F")
    for i in range(16):
        g[15][i] = COL["D"]
        g[i][15] = COL["D"]
    return g


def d_cable_h(x, y):
    g = floor_clean()
    for i in range(16):
        g[6][i] = g[7][i] = COL["K"]
        g[8][i] = COL["D"]
    return over(g, """
..LLLL......LLLL
..LLLL......LLLL
..LLLL......LLLL
..LLLL......LLLL
""", top=5)


def d_cable_v(x, y):
    g = floor_clean()
    for i in range(16):
        g[i][7] = COL["K"]
        g[i][8] = COL["D"]
    return over(g, """
......LLLL......
......LLLL......
......LLLL......
""", top=6)


def d_coffee(x, y):
    return over(floor_clean(), """
................
................
....nnnn........
...nnnnnnn......
..nnnnnnnnn.....
..nnnnnnnnnn....
..nnnnnDDnnn....
...nnnnnnnnn....
....nnnnnnn.....
......nnn.......
...........nn...
............nn..
................
""")


def d_drain(x, y):
    return over(floor_clean(), """
................
................
................
....KKKKKKKK....
...KDDDDDDDDK...
...KDKKKKKKDK...
...KDLLLLLLDK...
...KDKKKKKKDK...
...KDLLLLLLDK...
...KDKKKKKKDK...
...KDLLLLLLDK...
...KDKKKKKKDK...
...KDDDDDDDDK...
....KKKKKKKK....
................
""")


def d_puddle(x, y):
    return over(floor_clean(), """
................
.......B........
................
.......B........
.....BBBBB......
...BBBBBBBBBB...
..BBBFFBBBBBBB..
.BBBBBBBBBFFBBB.
.BBBBBBBBBBBBB..
..BBBBBBBBBBB...
...BBBBBBBB.....
.....BBBB.......
................
""")


def d_scuff(x, y):
    if (x + y) % 2:
        art = """
................
................
.DDD............
....DDD.........
.......DD.......
.........DD.....
...........D....
................
................
......KK........
....KK..........
...K............
................
................
"""
    else:
        art = """
................
................
.........DDDD...
.............D..
..............D.
..............D.
................
................
..DD............
....DDDD........
........DDD.....
................
................
"""
    return over(floor_clean(), art)


def d_charge_pad(x, y):
    """Floor paint for an empty charging spot: dashed box and a bolt."""
    return over(floor_clean(), """
................
.VV.VVV..VVV.VV.
.V............V.
................
.V......VVV...V.
.V.....VVV....V.
.......VVV......
......VVVVVV....
........VVV.....
.V.....VVV....V.
.V.....VV.....V.
......VV........
................
.V............V.
.VV.VVV..VVV.VV.
................
""")


def d_cold_vent(x, y):
    return over(floor_clean(), """
................
....B....B......
.....B....B.....
..KKKKKKKKKKKK..
..KBBBBBBBBBBK..
..KKKKKKKKKKKK..
..KBBBBBBBBBBK..
..KKKKKKKKKKKK..
..KBBBBBBBBBBK..
..KKKKKKKKKKKK..
..KBBBBBBBBBBK..
..KKKKKKKKKKKK..
................
""")


PAPER_SCRAPS = """
................
.WWWWWWW........
.WSSSSWWS.......
.WWWWWWWS.......
.WSSSSSWS.......
.WWWWWWWS.......
.WSSSWWWS.......
.WWWWWWWS.......
..SSSSSSS.......
................
........WWWWWW..
........WSSSWWS.
........WWWWWWS.
........WSSSSWS.
........WWWWWWS.
.........SSSSSS.
"""


def d_paper(x, y):
    art = PAPER_SCRAPS.replace("S", "D")
    if x % 2:
        art = "\n".join(r[::-1] for r in art.strip("\n").splitlines())
    return over(floor_clean(), art)


def d_paper_carpet(x, y):
    art = PAPER_SCRAPS.replace("S", "r")
    if x % 2:
        art = "\n".join(r[::-1] for r in art.strip("\n").splitlines())
    return over(carpet(x, y), art)


def d_dust(x, y):
    g = floor_clean()
    rnd = random.Random(x * 7 + y)
    for _ in range(6):
        g[rnd.randrange(15)][rnd.randrange(15)] = COL["L"]
    return over(g, """
................
................
................
................
................
.........LL.....
........LLLL....
.......LLDLLL...
........LLLL....
................
................
...LL...........
..LLLL..........
...LL...........
................
""")


def d_mat(x, y, right):
    left = not right
    art = """
................
................
................
..KKKKKKKKKKKKKK
..KnnnnnnnnnnnnD
..KnDDDDDDDDDDDD
..KnnnnnnnnnnnnD
..KnDDDDDDDDDDDD
..KnnnnnnnnnnnnD
..KnDDDDDDDDDDDD
..KnnnnnnnnnnnnD
..KKKKKKKKKKKKKK
................
"""
    if not left:
        art = "\n".join(r[::-1] for r in art.strip("\n").splitlines())
    g = over(floor_clean(), art)
    if left:  # the mat is one piece: no seam through its middle
        for yy in range(3, 12):
            g[yy][15] = COL["n"] if yy in (4, 6, 8, 10) else (COL["K"] if yy in (3, 11) else COL["D"])
    return g


def carpet(x, y):
    g = fill("R")
    for yy in range(16):
        for xx in range(16):
            d = abs((xx % 8) - 3.5) + abs((yy % 8) - 3.5)
            if d < 1.5:
                g[yy][xx] = COL["K"]
            elif d < 2.5 or d > 5.5:
                g[yy][xx] = COL["r"]
    return g


# --- walls -----------------------------------------------------------------


def wall(x=0, y=0):
    """Bevelled block wall in K/F/L so wall decorations can add one accent color."""
    g = fill("K")
    for xx in range(16):
        g[0][xx] = COL["L"]
    for yy in range(2, 14):
        course, ly = divmod(yy - 2, 4)
        off = 4 if course % 2 else 0
        for xx in range(16):
            lx = (xx + off) % 8
            if ly == 3 or lx == 7:
                c = "K"
            elif ly == 0 or lx == 0:
                c = "L"
            else:
                c = "F"
            g[yy][xx] = COL[c]
    return g


def w_vent(x, y):
    return over(wall(), """
..KKKKKKKKKKKK..
..KFFFFFFFFFFK..
..KKKKKKKKKKKK..
..KLLLLLLLLLLK..
..KKKKKKKKKKKK..
..KLLLLLLLLLLK..
..KKKKKKKKKKKK..
..KLLLLLLLLLLK..
..KKKKKKKKKKKK..
""", top=3)


def w_poster(x, y):
    """HANG IN THERE: a kitten silhouette dangling from a branch (no faces:
    frogs are actor sprites)."""
    return over(wall(), """
..KKKKKKKKKKKK..
..KGGGGGGGGGGK..
..KKKKKKKKKKKK..
..KGGGKGGKGGGK..
..KGGGKGGKGGGK..
..KGGKKGGKKGGK..
..KGKKKKKKKKGK..
..KGKKKKKKKKGK..
..KGGKKKKKKGGK..
..KGGGKGGKGGGK..
..KGGGGGGGGGGK..
..KGLLGLGLLGLK..
..KKKKKKKKKKKK..
""", top=1)


def w_clock(x, y):
    """Stuck at 9:00."""
    return over(wall(), """
.....KKKKKK.....
....KLLLLLLK....
...KLLLLKLLLK...
..KLLLLLKLLLLK..
..KLLLLLKLLLLK..
..KLKKKKKLLLLK..
..KLLLLLLLLLLK..
..KLLLLLLLLLLK..
...KLLLLKLLLK...
....KLLLLLLK....
.....KKKKKK.....
""", top=2)


def w_alarm(x, y):
    return over(wall(), """
.....KKKKKK.....
....KEEEEEEK....
...KEELLEEEEK...
...KELEEEEEEK...
...KEEEEEEEEK...
....KKKKKKKK....
................
.....KKKKKK.....
.....KEEEEK.....
.....KELLEK.....
.....KEEEEK.....
.....KKKKKK.....
""", top=1)


def w_whiteboard(x, y, right):
    """Two tiles wide: a chart that only goes down."""
    if right:
        art = """
KKKKKKKKKKKKKK..
LLLLLLLLLLLLLK..
LLLLLLLLKKLKLK..
LLLLLLLLLLLLLK..
LLLLLLLLKLKKLK..
LLLLLLLLLLLLLK..
EELLLLLLLLLLLK..
LLEELLLLLLLLLK..
KKKKEKKKKKKKKK..
LLLLLELLLLLLLK..
KKKKKEKKKKKKKK..
"""
    else:
        art = """
..KKKKKKKKKKKKKK
..KLLLLLLLLLLLLL
..KLKLLLLLLLLLLL
..KLKEELLLLLLLLL
..KLKLLEELLLLLLL
..KLKLLLLEELLLLL
..KLKLLLLLLEELLL
..KLKLLLLLLLLEEL
..KLKKKKKKKKKKKK
..KLLLLLLLLLLLLL
..KKKKKKKKKKKKKK
"""
    return over(wall(), art, top=2)


def w_tickets(x, y, right):
    """Two tiles wide: the help desk ticket queue, 999 and counting."""
    if right:
        g = over(wall(), """
KKKKKKKKKKKKKK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
LLLLLLLLLLLLLK..
KKKKKKKKKKKKKK..
""", top=2)
        return stamp(g, 1, 4, "999", "E")
    return over(wall(), """
..KKKKKKKKKKKKKK
..KLLLLLLLLLLLLL
..KLEEEEEEEELLLL
..KLLLLLLLLLLLLL
..KLEKLKKKKLKKLL
..KLLLLLLLLLLLLL
..KLEKLKKKLKKKLL
..KLLLLLLLLLLLLL
..KLEKLKKKKKLKLL
..KLLLLLLLLLLLLL
..KKKKKKKKKKKKKK
""", top=2)


def w_plate(x, y):
    """B1 floor plate."""
    g = over(wall(), """
..KKKKKKKKKKKK..
..KLLLLLLLLLLK..
..KLLLLLLLLLLK..
..KLLLLLLLLLLK..
..KLLLLLLLLLLK..
..KLLLLLLLLLLK..
..KLLLLLLLLLLK..
..KLLLLLLLLLLK..
..KKKKKKKKKKKK..
""", top=3)
    return stamp(g, 5, 5, "B1", "K")


def w_exit(x, y):
    g = over(wall(), """
...K........K...
...K........K...
KKKKKKKKKKKKKKKK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KGGGGGGGGGGGGGGK
KKKKKKKKKKKKKKKK
""", top=1)
    return stamp(g, 2, 5, "EXIT", "L")


def w_danger(x, y):
    return over(wall(), """
.......KK.......
......KYYK......
......KYYK......
.....KYKKYK.....
.....KYKKYK.....
....KYYKKYYK....
....KYYKKYYK....
...KYYYYYYYYK...
...KYYYKKYYYK...
..KYYYYYYYYYYK..
..KKKKKKKKKKKK..
""", top=2)


def w_cable_tray(x, y):
    return over(wall(), """
KKKKKKKKKKKKKKKK
LLKLLLKLLLKLLLKL
KKKKKKKKKKKKKKKK
.KK....YY....KK.
..KK...YY...KK..
...KK...YY.KK...
....KKK.YYKK....
......KKKK......
""", top=2)


def w_pipe(x, y):
    """A leaky pipe; the puddle decal sits on the floor below it."""
    return over(wall(), """
.....KLLLFK.....
.....KLLLFK.....
.....KLLLFK.....
....KKKKKKKK....
....KLLLLLFK....
....KKKKKKKK....
.....KLLLFK.....
.....KLLLFK.....
.....KLLLFK.....
.....KKKKKK.....
.......B........
................
.......B........
.......B........
""", top=0)


# --- props -----------------------------------------------------------------


def p_cabinet(x, y):
    return over(floor_clean(), """
..KKKKKKKKKKKK..
..KLLLLLLLLLLK..
..KDDDDDDDDDDK..
..KLLLLLLLLLLK..
..KLLLLKKLLLLK..
..KLLLLLLLLLLK..
..KDDDDDDDDDDK..
..KLLLLLLLLLLK..
..KLLLLKKLLLLK..
..KLLLLLLLLLLK..
..KDDDDDDDDDDK..
..KLLLLKKLLLLK..
..KLLLLLLLLLLK..
..KKKKKKKKKKKK..
...DDDDDDDDDDDD.
""", top=0)


def p_trash(x, y):
    return over(floor_clean(), """
.....WW.WWW.....
....WKWWWWKW....
...WWWWWWWWWWW..
...WKWWWWKWWKW..
..KKKKKKKKKKKK..
..KDDDDDDDDDDK..
...KDFDDDFDDK...
...KDFDDDFDDK...
...KDFDDDFDDK...
...KDFDDDFDDK...
....KDFDDFDK....
....KDFDDFDK....
....KKKKKKKK....
.....DDDDDDDD...
""", top=1)


def p_cooler(x, y):
    return over(fill("F"), """
.....KKKKKK.....
....KBBBBLBK....
...KBBBBBBLBK...
...KBBBBBBLBK...
...KBBBBBBBBK...
....KBBBBBBK....
.....KKKKKK.....
...KKKKKKKKKK...
...KLLLLLLLLK...
...KLBKLLKBLK...
...KLLLLLLLLK...
...KLFFFFFFLK...
...KLLLLLLLLK...
...KLLLLLLLLK...
...KKKKKKKKKK...
""", top=0)


def p_extinguisher(x, y):
    return over(fill("F"), """
.......KKK......
......KLLLKK....
.......KK..KK...
.....KKKKK..K...
....KEEEEEK.K...
....KELEEEKK....
....KELEEEK.....
....KEEEEEK.....
....KLLLLLK.....
....KLKKKLK.....
....KLLLLLK.....
....KEEEEEK.....
....KEEEEEK.....
.....KKKKK......
""", top=1)


def p_wet_sign(x, y):
    return over(fill("F"), """
.......KK.......
......KYYK......
......KYYK......
.....KYKKYK.....
.....KYKKYK.....
....KYYKYYYK....
....KYKKKYYK....
...KYYYKYYYYK...
...KYYKYKYYYK...
..KYYKYYYKYYYK..
..KKKKKKKKKKKK..
..K..........K..
.K............K.
.K............K.
""", top=1)


def p_mop_bucket(x, y):
    return over(fill("F"), """
...........KK...
..........KDK...
.........KDK....
........KDK.....
.......KDK......
......KDK.......
..KKKKKDKKKKKK..
..KDDDKDKDDDDK..
..KKKKKKKKKKKK..
...KYYYYYYYYK...
...KYKKKKKKYK...
...KYYYYYYYYK...
...KYYYYYYYYK...
....KKKKKKKK....
....KK....KK....
""", top=0)


def p_toolbox(x, y):
    return over(fill("F"), """
......KKKK......
.....KK..KK.....
.....K....K.....
..KKKKKKKKKKKK..
..KEEEEEEEEEEK..
..KELLEEEEEEEK..
..KEEEEEEEEEEK..
..KKKKKLLKKKKK..
..KEEEEEEEEEEK..
..KEEEEEEEEEEK..
..KKKKKKKKKKKK..
""", top=3)


def p_box_stack(x, y):
    return over(fill("F"), """
.....KKKKKKK....
.....KttFttK....
.....KttFttK....
.....KKKKKKK....
..KKKKKKKKKKKK..
..KttttFFttttK..
..KttttFFttttK..
..KnnnnnnnnnnK..
..KttttttttttK..
..KttttttKKKKK..
..KttttttKFFFK..
..KttttttKFKFK..
..KttttttKKKKK..
..KKKKKKKKKKKK..
...nnnnnnnnnnnn.
""", top=0)


def p_keyboards(x, y):
    art = """
................
...KKKKKKKKKKK..
...KPWPWPWPWPK..
.KKKKKKKKKKKKK..
.KPWPWPWPWPWK...
.KPPPPPPPPPPK...
.KKKKKKKKKKKKK..
...KPWPWPWPWPWK.
...KPWPWWWWPWPK.
...KKKKKKKKKKKK.
..KKKKKKKKKKK...
..KPWPWPWPWPK.K.
..KPPPPPPPPPKK..
..KKKKKKKKKKK...
................
................
"""
    if (x + y) % 2:
        art = "\n".join(r[::-1] for r in art.strip("\n").splitlines())
    return over(fill("F"), art)


def p_printer(x, y):
    """OUT OF ORDER: red tape X across the front, a sheet still jammed in it."""
    return over(fill("F"), """
...KKKKKKKKKK...
...KLLLLLLLLK...
.KKKKKKKKKKKKKK.
.KEELLLLLLLLEEK.
.KLEELLLLLLEELK.
.KLLEELLLLEELLK.
.KLLLEELLEELLLK.
.KLLLLEEEELLLLK.
.KLLLEELLEELLLK.
.KLLEELLLLEELLK.
.KLEELLLLLLEELK.
.KFKKKKKKKKKKFK.
.KFFKLLLLLLKFFK.
.KKKKLLLLLLKKKK.
.....LLLKLL.....
""", top=1)


def p_reams(x, y):
    return over(fill("F"), """
...KKKKKKKKKK...
...KWWWWWWWWK...
...KPPPPPPPPK...
...KKKKKKKKKK...
..KKKKKKKKKKKK..
..KWWWWWWWWWWK..
..KPPPKKKKPPPK..
..KWWWWWWWWWWK..
..KKKKKKKKKKKK..
..KWWWWWWWWWWK..
..KPPPPPPPPPPK..
..KWWWWWWWWWWK..
..KKKKKKKKKKKK..
""", top=2)


def p_spool(x, y):
    g = fill("F")
    for yy in range(16):
        for xx in range(16):
            r = ((xx - 7.5) ** 2 + (yy - 7.5) ** 2) ** 0.5
            if r > 7.6:
                continue
            if r > 6.6:
                c = "K"
            elif r > 5.4:
                c = "t"
            elif r > 2.6:
                c = "K" if 3.9 < r < 4.6 else "n"
            elif r > 1.4:
                c = "t"
            else:
                c = "K"
            g[yy][xx] = COL[c]
    return g


def p_crt_cracked(x, y):
    return over(fill("F"), """
.KKKKKKKKKKKKKK.
.KPPPPPPPPPPPPK.
.KPKKKKKKKKKKPK.
.KPKWWKKKKKKKPK.
.KPKWKKKKWKKKPK.
.KPKKKKKKKWKKPK.
.KPKKKWWKWWWKPK.
.KPKKKKKWKKKWPK.
.KPKKKKWKKKKKPK.
.KPKKKKWKKKKKPK.
.KPKKKKKKKKKKPK.
.KPPPPPPPPPPWPK.
.KKKKKKKKKKKKKK.
....KPPPPPPK....
...KKKKKKKKKK...
""", top=1)


def p_umbrellas(x, y):
    return over(fill("F"), """
.....KK....KK...
....K..K..K..K..
....K..K..K.....
.......K..K.....
......KEK.KEK...
.....KEEKKEEEK..
.....KEEKKEEK...
...KKKKKKKKKKK..
...KLLLLLLLLFK..
...KKKKKKKKKKK..
...KLLLLLLLLFK..
...KLLLLLLLLFK..
...KLLLLLLLLFK..
...KKKKKKKKKKK..
""", top=1)


def p_dust_bin(x, y):
    """The Roomba Dock's overflowing dust bin (no face: roombas are actors)."""
    return over(floor_clean(), """
.....L.LL.L.....
...LLLLLLLLLL...
..KKKKKKKKKKKK..
..KDDDDDDDDDDK..
...KDFDDDDDDK...
...KDFDDDDDDK...
...KDFDDDDDDK...
...KDFDDDDDDK...
...KDFDDDDDDK...
...KDDDDDDDDK...
....KKKKKKKK....
.....DDDDDDDLL..
...........L.L..
""", top=1)


def p_chair(x, y):
    return over(floor_clean(), """
.....KKKKKK.....
....KDDDDDDK....
....KDLDDDDK....
....KDLDDDDK....
....KDDDDDDK....
.....KKKKKK.....
.......KK.......
..KKKKKKKKKKKK..
..KDLLLLLLLLDK..
..KKKKKKKKKKKK..
.......KK.......
....KKKKKKKK....
...KK..KK..KK...
................
""", top=1)


def p_desk(x, y):
    g = ipal(t_desk(), "wood")
    if x % 2:  # cold coffee
        return over(g, """
................
.........KKKK...
........KnnnnKK.
........KFFFFK.K
........KFFFFKK.
.........KKKK...
""")
    return over(g, """
................
..KKKKKK........
..KFFFFFK.......
..KFKKKFK.......
..KFFFFFK.......
..KKKKKKK.......
""")


def p_rack(x, y, red=False):
    g = t_rack()
    rnd = random.Random(x * 11 + y * 7)
    for unit in range(3):
        yy = 3 + unit * 4
        g[yy + 1][11] = 3 if rnd.random() < 0.8 else 2
        g[yy + 1][12] = 3 if rnd.random() < 0.5 else 2
    return ipal(g, "rack_red" if red else "rack")


def p_tape_shelf(x, y):
    g = t_tape_shelf()
    rnd = random.Random(x * 5 + y * 13)
    for row in (2, 8):
        for col in (2, 6, 10):
            if rnd.random() < 0.2:
                rect(g, col, row, col + 2, row + 2, 0)  # missing reel
    if x % 2 == 0:  # dust on the left half of each shelf pair
        g[0][3] = g[0][4] = g[6][9] = 3
    return ipal(g, "paper")


# char -> (metatile builder(x, y) -> 16x16 color grid, solid?)
TILES = {
    # structure
    ".": (floor, False),
    "C": (floor, False),  # chest actor stands here
    "#": (lambda x, y: ipal(t_ceiling(), "concrete"), True),
    "=": (wall, True),
    "S": (lambda x, y: ipal(t_stairs(), "concrete"), False),
    "d": (lambda x, y: ipal(t_door(), "concrete"), False),
    "o": (lambda x, y: ipal(t_post(), "concrete"), True),
    "^": (lambda x, y: ipal(t_hazard_edge(), "hazard"), False),
    "~": (lambda x, y: ipal(t_trench((x + y) % 3), "hazard"), True),
    "k": (lambda x, y: ipal(t_locked_door(), "chest"), True),
    "B": (lambda x, y: ipal(t_boss_door(), "chest"), True),
    "K": (carpet, False),
    # wall faces (top row only, never on door tiles)
    "v": (w_vent, True),
    "H": (w_poster, True),
    "Q": (w_clock, True),
    "A": (w_alarm, True),
    "[": (lambda x, y: w_whiteboard(x, y, False), True),
    "]": (lambda x, y: w_whiteboard(x, y, True), True),
    "{": (lambda x, y: w_tickets(x, y, False), True),
    "}": (lambda x, y: w_tickets(x, y, True), True),
    "N": (w_plate, True),
    "X": (w_exit, True),
    "Z": (w_danger, True),
    "|": (w_cable_tray, True),
    "L": (w_pipe, True),
    # flat floor decals (walkable)
    "-": (d_cable_h, False),
    "i": (d_cable_v, False),
    "c": (d_coffee, False),
    "g": (d_drain, False),
    "w": (d_puddle, False),
    "s": (d_scuff, False),
    "_": (d_charge_pad, False),
    "f": (d_cold_vent, False),
    "y": (d_paper, False),
    "%": (d_paper_carpet, False),
    "u": (d_dust, False),
    "e": (lambda x, y: d_mat(x, y, False), False),
    "E": (lambda x, y: d_mat(x, y, True), False),
    # props (solid)
    "R": (p_rack, True),
    "r": (lambda x, y: p_rack(x, y, red=True), True),
    "D": (p_desk, True),
    "b": (lambda x, y: ipal(t_box(), "wood"), True),
    "a": (p_box_stack, True),
    "P": (lambda x, y: ipal(t_plant(), "plant"), True),
    "m": (lambda x, y: ipal(t_monitors(), "paper"), True),
    "M": (p_crt_cracked, True),
    "!": (lambda x, y: ipal(t_sign(), "paper"), True),
    "T": (p_tape_shelf, True),
    "F": (p_cabinet, True),
    "t": (p_trash, True),
    "j": (p_cooler, True),
    "x": (p_extinguisher, True),
    "Y": (p_wet_sign, True),
    "q": (p_mop_bucket, True),
    "l": (p_toolbox, True),
    "z": (p_keyboards, True),
    "p": (p_printer, True),
    "8": (p_reams, True),
    "O": (p_spool, True),
    "G": (p_dust_bin, True),
    "h": (p_chair, True),
    "U": (p_umbrellas, True),
}


# Each room is one Game Boy screen: 10 x 9 metatiles = 160 x 144 px.
# Doors sit in the middle of each wall: north/south at columns 4-5, east/west at row 4.
# 'C' marks where a chest actor stands (drawn as floor).
# (grid x, grid y, title, layout)
ROOMS = {
    "printer_room": (1, 0, "Printer Room", """
==A=[]=Q==
#p..%%..p#
#8.KKKK.8#
#y.KKKK..#
#..KKKK.y#
#8.KKKK.8#
#p..%%..p#
#.y....t.#
####dd####
"""),
    "server_farm": (0, 1, "Server Farm", """
=v||==||v=
#R.fC.f.R#
#r..o...r#
#^^^^^^^^#
#~~~~~~~~#
#~~~~~~~~#
#R.f..f.r#
#r....o.R#
####dd####
"""),
    "cable_pit": (1, 1, "Cable Pit", """
=Z=LBB=vZ=
#R.w....R#
#...o..Y.#
#^^^^^^^^#
#~~~~~~~~#
#~~~~~~~~#
#.g......#
#l....o.x#
####dd####
"""),
    "tape_archive": (2, 1, "Tape Archive", """
=v==Q==v==
#TT.TT.TT#
#u.......#
#TT.TT.TT#
#....u...#
#TT.TT.C.#
#.u......#
#F......F#
####dd####
"""),
    "cable_closet": (0, 2, "Cable Closet", """
=||=dd=||=
#O.b..a.O#
#........#
#a......b#
#...C....d
#b......O#
#.------.#
#O.a..b.l#
##########
"""),
    "help_desk": (1, 2, "Help Desk", """
={}=dd=Q==
#F......j#
#.DD....t#
#..c.....#
k........d
#........#
#.Phh..b.#
#......c.#
####dd####
"""),
    "monitor_graveyard": (2, 2, "Monitor Graveyard", """
==H=dd=Qv=
#mM....zm#
#z......M#
#........#
d---.....#
#........#
#M......z#
#mz....Mm#
####dd####
"""),
    "stairwell": (1, 3, "Stairwell", """
=N=Hdd=X==
#........#
#.P....P.#
#........#
#...!....#
#........#
#U..eE..Y#
#x..SS..t#
##########
"""),
    "roomba_dock": (2, 3, "Roomba Dock", """
=v==dd=A==
#_......_#
#.G....b.#
#....s...#
#..s.....#
#.....s..#
#.a....b.#
#^^^^^^^^#
##########
"""),
}


def room_rows(layout):
    rows = layout.strip().splitlines()
    assert len(rows) == 9 and all(len(r) == 10 for r in rows), [len(r) for r in rows]
    return rows


def render_room(layout):
    rows = room_rows(layout)
    img = Image.new("RGB", (160, 144))
    for my, row in enumerate(rows):
        for mx, ch in enumerate(row):
            g = TILES[ch][0](mx, my)
            assert len(g) == 16 and all(len(r) == 16 for r in g), ch
            for y in range(16):
                for x in range(16):
                    img.putpixel((mx * 16 + x, my * 16 + y), g[y][x])
    return rows, img


def validate(name, img):
    """GB Studio rules per room: <=4 colors per 8x8 tile, each tile inside one of
    the room's palettes, <=8 palettes per room, <=384 unique tiles."""
    tiles, colorsets = set(), set()
    w, h = img.size
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            px = tuple(img.getpixel((tx + x, ty + y)) for y in range(8) for x in range(8))
            cs = frozenset(px)
            assert len(cs) <= 4, (name, tx, ty, cs)
            tiles.add(px)
            colorsets.add(cs)
    assert len(tiles) <= 384, name
    pals = {k: frozenset(v) for k, v in PAL_RGB.items()}
    # Keep only maximal color sets, and palettes that can hold at least one of them.
    sets = [cs for cs in colorsets if not any(cs < o for o in colorsets)]
    for cs in sets:
        assert any(cs <= p for p in pals.values()), (name, "no palette fits", cs)
    cands = [k for k, p in pals.items() if any(cs <= p for cs in sets)]
    for n in range(1, 9):
        for combo in combinations(cands, n):
            if all(any(cs <= pals[k] for k in combo) for cs in sets):
                return len(tiles), combo
    raise AssertionError(f"{name} needs more than 8 palettes")


def check_doors():
    """Every door must line up with a door in the neighbouring room."""
    grid_ = {(gx, gy): layout.strip().splitlines() for gx, gy, _, layout in ROOMS.values()}
    doors = set("dkB")
    for (gx, gy), rows in grid_.items():
        sides = {
            (0, -1): rows[0][4] in doors,
            (0, 1): rows[8][4] in doors,
            (-1, 0): rows[4][0] in doors,
            (1, 0): rows[4][9] in doors,
        }
        for (dx, dy), has_door in sides.items():
            if not has_door:
                continue
            other = grid_.get((gx + dx, gy + dy))
            assert other, f"door at {(gx, gy)} leads nowhere"
            back = {(0, -1): other[8][4], (0, 1): other[0][4], (-1, 0): other[4][9], (1, 0): other[4][0]}
            assert back[(dx, dy)] in doors, f"door at {(gx, gy)} has no matching door"


def walkable(rows, x, y):
    return not TILES[rows[y][x]][1]


def check_layouts():
    """Doors open onto floor, every door and chest connects (pits count as
    crossable by hookshot), and the NPC and boss spots stay clear."""
    for name, (_, _, _, layout) in ROOMS.items():
        rows = room_rows(layout)
        assert all(ch in "=dkB" or TILES[ch][1] for ch in rows[0] if ch != "="), name
        inside = []
        for x in range(10):
            if rows[0][x] in "dkB":
                inside.append((x, 1))
            if rows[8][x] in "dkB":
                inside.append((x, 7))
        for y in range(9):
            if rows[y][0] in "dkB":
                inside.append((1, y))
            if rows[y][9] in "dkB":
                inside.append((8, y))
        for x, y in inside:
            assert walkable(rows, x, y), (name, "blocked door", x, y)
        seen, todo = {inside[0]}, deque([inside[0]])
        while todo:
            x, y = todo.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 1 <= nx <= 8 and 1 <= ny <= 7 and (nx, ny) not in seen:
                    if walkable(rows, nx, ny) or rows[ny][nx] == "~":
                        seen.add((nx, ny))
                        todo.append((nx, ny))
        targets = inside + [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "C"]
        for t in targets:
            assert t in seen, (name, "unreachable", t)

    def clear(name, cells):
        rows = room_rows(ROOMS[name][3])
        for x, y in cells:
            assert walkable(rows, x, y), (name, x, y)

    clear("help_desk", [(2, 1), (3, 1)])
    assert room_rows(ROOMS["help_desk"][3])[2][2:4] == "DD"
    clear("monitor_graveyard", [(4, 4), (3, 4), (5, 4), (4, 3), (4, 5)])
    clear("printer_room", [(x, y) for x in range(3, 7) for y in range(2, 6)])
    for room in ("server_farm", "cable_pit"):  # hookshot launch/landing tiles
        clear(room, [(6, 6), (4, 3), (6, 3), (4, 7)])
    clear("roomba_dock", [(x, y) for x in range(3, 7) for y in range(3, 6)])


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
    from PIL import ImageDraw

    check_doors()
    check_layouts()
    out_dir = ROOT / "assets/backgrounds"
    for old in out_dir.glob("it_basement*.png"):
        old.unlink()

    rendered, collision = {}, []
    for name, (gx, gy, title, layout) in ROOMS.items():
        rows, img = render_room(layout)
        n, pals = validate(name, img)
        img.save(out_dir / f"basement_{name}.png")
        rendered[name] = img
        print(f"basement_{name}.png OK: unique tiles {n}/384, palettes {len(pals)}/8 ({', '.join(pals)})")
        coll = ["".join("X" if TILES[ch][1] else "." for ch in row) for row in rows]
        collision.append(f"{title} (basement_{name}.png)\n" + "\n".join(coll))

    (ROOT / "previews/it-basement-collision.txt").write_text(
        "IT Basement collision (X = solid), one cell per 16x16 metatile (2x2 GB tiles)\n\n"
        + "\n\n".join(collision)
        + "\n"
    )

    # Dungeon overview: rooms on their grid at 2x, with gaps and labels.
    scale, gap = 2, 12
    cols = max(r[0] for r in ROOMS.values()) + 1
    rows_ = max(r[1] for r in ROOMS.values()) + 1
    cw, ch = 160 * scale + gap, 144 * scale + gap
    ov = Image.new("RGB", (cols * cw + gap, rows_ * ch + gap), (0x0F, 0x13, 0x1A))
    draw = ImageDraw.Draw(ov)
    for name, (gx, gy, title, _) in ROOMS.items():
        x0, y0 = gap + gx * cw, gap + gy * ch
        ov.paste(rendered[name].resize((160 * scale, 144 * scale), Image.NEAREST), (x0, y0))
        tw = draw.textlength(title)
        draw.rectangle([x0 + 4, y0 + 4, x0 + 12 + tw, y0 + 18], fill=(0x0F, 0x13, 0x1A))
        draw.text((x0 + 8, y0 + 5), title, fill=(0xF4, 0xF4, 0xEC))
    # Bufo arriving on the stairs.
    sx, sy = ROOMS["stairwell"][:2]
    f = bufo_frame(2).resize((32, 32), Image.NEAREST)
    ov.paste(f, (gap + sx * cw + 4 * 32 + 16, gap + sy * ch + 6 * 32), f)
    ov.save(ROOT / "previews/it-basement-preview.png")
    print("overview:", ov.size)


if __name__ == "__main__":
    main()
