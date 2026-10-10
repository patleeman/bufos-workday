"""Build Level 3, the Open-Plan Office (Floor 3), for GB Studio (Color Only,
automatic palettes).

Same module shape as make_break_room.py: ROOMS = {name: (gx, gy, title,
layout)} with triple-quoted 10x9 layouts, TILES = {char: (builder, solid)}
with the solid flag last, PROPS_HINT = {room: [{"name", "pos"}]}.

Doors: north/south at columns 4-5 of the top/bottom row, east/west at row 4.
  d  door      B  boss door (top row)      k  keycard door (walkable, a
  E  elevator (bottom row, walkable)          trigger guards it)
  C  chest spot (floor)                    y  scattered paper (floor decal)

This file also holds the small engine make_hr.py reuses: char-grid helpers,
render_room(), validate() (<=4 colors per 8x8 tile, every tile inside one of
the named palettes, <=8 palettes, <=384 unique tiles), check_doors(),
check_layouts() and the preview writer.

Outputs:
  assets/backgrounds/office_<room>.png
  previews/open-office-preview.png
  previews/open-office-collision.txt
"""

import random
import sys
from collections import deque
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent


def hexc(h):
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))


# =============================================================================
# engine (shared with make_hr.py)
# =============================================================================

CTX = {"rows": None, "floor": None, "name": None}


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
    "J": ["..K", "..K", "..K", "K.K", ".K."],
    "K": ["K.K", "K.K", "KK.", "K.K", "K.K"],
    "L": ["K..", "K..", "K..", "K..", "KKK"],
    "M": ["K...K", "KK.KK", "K.K.K", "K...K", "K...K"],
    "N": ["K..K", "KK.K", "K.KK", "K..K", "K..K"],
    "O": [".K.", "K.K", "K.K", "K.K", ".K."],
    "P": ["KK.", "K.K", "KK.", "K..", "K.."],
    "Q": [".K.", "K.K", "K.K", "KK.", ".KK"],
    "R": ["KK.", "K.K", "KK.", "K.K", "K.K"],
    "S": [".KK", "K..", ".K.", "..K", "KK."],
    "T": ["KKK", ".K.", ".K.", ".K.", ".K."],
    "U": ["K.K", "K.K", "K.K", "K.K", "KKK"],
    "V": ["K.K", "K.K", "K.K", "K.K", ".K."],
    "W": ["K...K", "K...K", "K.K.K", "KK.KK", "K...K"],
    "X": ["K.K", "K.K", ".K.", "K.K", "K.K"],
    "Y": ["K.K", "K.K", ".K.", ".K.", ".K."],
    "Z": ["KKK", "..K", ".K.", "K..", "KKK"],
    "0": ["KKK", "K.K", "K.K", "K.K", "KKK"],
    "1": [".K.", "KK.", ".K.", ".K.", "KKK"],
    "2": ["KK.", "..K", ".K.", "K..", "KKK"],
    "3": ["KK.", "..K", ".K.", "..K", "KK."],
    "4": ["K.K", "K.K", "KKK", "..K", "..K"],
    "5": ["KKK", "K..", "KK.", "..K", "KK."],
    "9": ["KKK", "K.K", "KKK", "..K", "KKK"],
    ":": [".", "K", ".", "K", "."],
    "!": ["K", "K", "K", ".", "K"],
    "?": ["KK.", "..K", ".K.", "...", ".K."],
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


def col_index(x, y, chars):
    rows = CTX["rows"]
    i = 0
    while y - i - 1 >= 0 and rows[y - i - 1][x] in chars:
        i += 1
    return i


def slice16(big, ix, iy=0):
    return [row[ix * 16 : ix * 16 + 16] for row in big[iy * 16 : iy * 16 + 16]]


def wide(art_fn, chars):
    """Builder for a multi-metatile piece drawn as one big grid. Horizontal
    runs pick the column; vertical runs pick the row."""

    def build(x, y):
        return slice16(art_fn(), run_index(x, y, chars), col_index(x, y, chars))

    return build


def framed(w_tiles, base_fn, fill="W", border="K", inset=2, top=2, bottom=12, h_tiles=1):
    """A sign/board drawn over a wall face that is w_tiles wide."""
    g = blank(".", 16 * w_tiles, 16 * h_tiles)
    for t in range(w_tiles):
        tile = base_fn()
        for yy in range(16):
            for xx in range(16):
                g[yy][t * 16 + xx] = tile[yy][xx]
    x0, x1 = inset, 16 * w_tiles - 1 - inset
    for yy in range(top, bottom + 1):
        for xx in range(x0, x1 + 1):
            g[yy][xx] = border if (yy in (top, bottom) or xx in (x0, x1)) else fill
    return g, x0, x1


DOORS = set("dBwk")


def spec_of(name):
    return sys.modules[name]


def room_rows(layout):
    rows = layout.strip().splitlines()
    assert len(rows) == 9 and all(len(r) == 10 for r in rows), [len(r) for r in rows]
    return rows


def render_room(spec, layout, floor_kind, name=None):
    rows = room_rows(layout)
    CTX["rows"], CTX["floor"], CTX["name"] = rows, floor_kind, name
    canvas = blank("K", 160, 144)
    for my, row in enumerate(rows):
        for mx, ch in enumerate(row):
            g = spec.TILES[ch][0](mx, my)
            assert len(g) == 16 and all(len(r) == 16 for r in g), (name, ch)
            for y in range(16):
                for x in range(16):
                    canvas[my * 16 + y][mx * 16 + x] = g[y][x]
    rgb = {k: hexc(v) for k, v in spec.COL.items()}
    img = Image.new("RGB", (160, 144))
    img.putdata([rgb[c] for row in canvas for c in row])
    return rows, img


def validate(spec, name, img):
    rgb = {k: hexc(v) for k, v in spec.COL.items()}
    pal_rgb = {k: frozenset(rgb[c] for c in v) for k, v in spec.PAL.items()}
    tiles, colorsets = set(), set()
    assert img.size == (160, 144), name
    for ty in range(0, 144, 8):
        for tx in range(0, 160, 8):
            px = tuple(img.getpixel((tx + x, ty + y)) for y in range(8) for x in range(8))
            cs = frozenset(px)
            assert len(cs) <= 4, (name, "too many colors", tx, ty, sorted(k for k, v in rgb.items() if v in cs))
            tiles.add(px)
            colorsets.add(cs)
    assert len(tiles) <= 384, name
    sets = [cs for cs in colorsets if not any(cs < o for o in colorsets)]
    for cs in sets:
        assert any(cs <= p for p in pal_rgb.values()), (name, "no palette fits", sorted(k for k, v in rgb.items() if v in cs))
    cands = [k for k, p in pal_rgb.items() if any(cs <= p for cs in sets)]
    for n in range(1, 9):
        for combo in combinations(cands, n):
            if all(any(cs <= pal_rgb[k] for k in combo) for cs in sets):
                return len(tiles), combo
    raise AssertionError(f"{name} needs more than 8 palettes")


def check_doors_spec(spec):
    """Every door lines up with a door in the neighbouring room. N/S doors fill
    columns 4-5, E/W doors sit at row 4, B only on the top row, and k only
    meets k."""
    grid_ = {(gx, gy): room_rows(layout) for gx, gy, _, layout in spec.ROOMS.values()}
    for (gx, gy), rows in grid_.items():
        for r in (0, 8):
            if rows[r][4] in DOORS or rows[r][5] in DOORS:
                assert rows[r][4] == rows[r][5], ((gx, gy), "N/S doors need columns 4-5")
        for y in range(9):
            for x in range(10):
                if rows[y][x] in DOORS:
                    ok = (y in (0, 8) and x in (4, 5)) or (y == 4 and x in (0, 9))
                    assert ok, ((gx, gy), "door in the wrong place", x, y)
                if rows[y][x] == "B":
                    assert y == 0, ((gx, gy), "B only on the top row")
                if rows[y][x] == "E":
                    assert y == 8 and x in (4, 5), ((gx, gy), "elevator in the bottom row, columns 4-5")
        sides = {(0, -1): rows[0][4], (0, 1): rows[8][4], (-1, 0): rows[4][0], (1, 0): rows[4][9]}
        for (dx, dy), mine in sides.items():
            if mine not in DOORS:
                continue
            other = grid_.get((gx + dx, gy + dy))
            assert other, f"door at {(gx, gy)} leads nowhere"
            back = {(0, -1): other[8][4], (0, 1): other[0][4], (-1, 0): other[4][9], (1, 0): other[4][0]}[(dx, dy)]
            assert back in DOORS, f"door at {(gx, gy)} has no matching door"
            for special in "kw":
                if special in (mine, back):
                    assert mine == back, f"{special} door at {(gx, gy)} must meet a {special} door"


def walkable(spec, rows, x, y):
    return 0 <= x < 10 and 0 <= y < 9 and not spec.TILES[rows[y][x]][-1]


def reach(spec, rows, start):
    seen, todo = {start}, deque([start])
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if walkable(spec, rows, nx, ny) and (nx, ny) not in seen:
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen


def check_layouts_spec(spec, clears):
    """Doors, elevators and chests connect, every prop is solid with a walkable
    neighbour, and the named clear areas are walkable and reachable."""
    for name, (_, _, _, layout) in spec.ROOMS.items():
        rows = room_rows(layout)
        exits = [(x, y) for y in range(9) for x in range(10) if rows[y][x] in "dBwkE"]
        assert exits, name
        for x, y in exits:
            assert walkable(spec, rows, x, y), (name, "door not walkable", x, y)
        seen = reach(spec, rows, exits[0])
        for t in exits + [(x, y) for y in range(9) for x in range(10) if rows[y][x] == "C"]:
            assert t in seen, (name, "unreachable", t)
        for p in spec.PROPS_HINT[name]:
            x, y = p["pos"]
            assert spec.TILES[rows[y][x]][-1], (name, p["name"], "prop should be solid")
            assert any((x + ax, y + ay) in seen for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1))), (name, p["name"], "can't be examined")
        for cell in clears.get(name, []):
            assert walkable(spec, rows, *cell) and tuple(cell) in seen, (name, "must stay clear", cell)


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


def build_all(spec, prefix, preview_name, collision_name, label, clears):
    check_doors_spec(spec)
    check_layouts_spec(spec, clears)
    out_dir = ROOT / "assets/backgrounds"
    rendered, collision, errors = {}, [], []
    for name, (gx, gy, title, layout) in spec.ROOMS.items():
        rows, img = render_room(spec, layout, spec.ROOM_FLOOR[name], name)
        rendered[name] = img
        fname = f"{prefix}_{name}.png"
        try:
            n, pals = validate(spec, name, img)
        except AssertionError as e:
            errors.append(e)
            print("FAIL", e)
            continue
        img.save(out_dir / fname)
        print(f"{fname} OK: unique tiles {n}/384, palettes {len(pals)}/8 ({', '.join(pals)})")
        coll = ["".join("X" if spec.TILES[ch][-1] else "." for ch in row) for row in rows]
        collision.append(f"{title} ({fname})\n" + "\n".join(coll))
    (ROOT / "previews" / collision_name).write_text(
        f"{label} collision (X = solid), one cell per 16x16 metatile (2x2 GB tiles)\n"
        "Walkable specials: d door, B boss door, k keycard door (trigger), E elevator, C chest\n\n"
        + "\n\n".join(collision)
        + "\n"
    )
    scale, gap = 2, 12
    cols = max(r[0] for r in spec.ROOMS.values()) + 1
    rows_ = max(r[1] for r in spec.ROOMS.values()) + 1
    cw, ch = 160 * scale + gap, 144 * scale + gap
    ov = Image.new("RGB", (cols * cw + gap, rows_ * ch + gap), (0x0F, 0x13, 0x1A))
    draw = ImageDraw.Draw(ov)
    for name, (gx, gy, title, _) in spec.ROOMS.items():
        x0, y0 = gap + gx * cw, gap + gy * ch
        ov.paste(rendered[name].resize((160 * scale, 144 * scale), Image.NEAREST), (x0, y0))
        tw = draw.textlength(title)
        draw.rectangle([x0 + 4, y0 + 4, x0 + 12 + tw, y0 + 18], fill=(0x0F, 0x13, 0x1A))
        draw.text((x0 + 8, y0 + 5), title, fill=(0xF4, 0xF4, 0xEC))
    landing = next(n for n, r in spec.ROOMS.items() if room_rows(r[3])[8][4] == "E")
    sx, sy = spec.ROOMS[landing][:2]
    f = bufo_frame(2).resize((32, 32), Image.NEAREST)
    ov.paste(f, (gap + sx * cw + 4 * 32 + 16, gap + sy * ch + 7 * 32), f)
    ov.save(ROOT / "previews" / preview_name)
    print("overview:", ov.size)
    if errors:
        raise SystemExit(f"{len(errors)} room(s) failed validation")


# =============================================================================
# Level 3: the Open-Plan Office
# =============================================================================

COL = {
    "K": "#0f131a",  # ink
    "W": "#fafcfc",  # bright white
    "a": "#e3e8ee",  # white-grey wall
    "A": "#8c97a6",  # steel grey, wall top
    "f": "#c3cbd5",  # cool vinyl floor
    "p": "#a3adba",  # vinyl seams
    "T": "#2fa39a",  # corporate teal
    "B": "#58a8e0",  # screen blue
    "R": "#d84848",  # red marker / alarm
    "Y": "#f0c030",  # sticky-note yellow
    "G": "#78b848",  # leaf
    "g": "#2e6a30",  # dark leaf
}

PAL = {
    "wall": "KAaW",
    "wall_teal": "KaWT",
    "wall_red": "KaWR",
    "wall_blue": "KaWB",
    "wall_yellow": "KaWY",
    "floor": "KpfW",
    "desk_top": "KWBA",
    "chair": "KAfT",
    "white_floor": "KWAf",
    "plant": "KgGf",
    "beanbag_red": "KRWf",
    "beanbag_teal": "KTWf",
    "booth": "KABW",
    "glass_door": "KTBW",
    "elevator": "KAWY",
}

ROOM_FLOOR = {}  # one floor type on this level


def floor(x, y):
    """Big glossy vinyl tiles with a glint."""
    g = blank("f")
    for i in range(16):
        g[15][i] = "p"
        g[i][15] = "p"
    if (x * 7 + y * 3) % 5 == 0:
        g[3][3] = g[4][4] = g[3][4] = "W"
    return g


def plain(x=0, y=0):
    return blank("f")


def on_floor(art, top=0, left=0):
    return paint(plain(), art, top=top, left=left)


def scatter(x, y):
    """Paper everywhere: the ping of chaos (walkable)."""
    g = floor(x, y)
    art = """
................
.WWWWW..........
.WKKKW......WWW.
.WWWWWW....WKKW.
.WKKKKW....WWWW.
..WWWWW....WKWW.
............WWW.
................
....WWWWWW......
....WKKKKW......
....WWWWWW......
....WKKWWW......
....WWWWWW......
................
"""
    paint(g, art, top=1)
    return flip(g) if x % 2 else g


def wall(x=0, y=0):
    """Wall face: ink edge, white crown, pale grey, grey baseboard."""
    g = blank("a")
    g[0] = ["K"] * 16
    g[1] = ["W"] * 16
    g[13] = ["A"] * 16
    g[14] = ["K"] * 16
    g[15] = ["K"] * 16
    return g


def wall_plain():
    """Wall behind a decoration: the decoration's palette carries K, a, W
    and one accent, so the baseboard is drawn in ink."""
    g = wall()
    g[13] = ["K"] * 16
    return g


def wall_top(x, y):
    g = blank("A")
    for i in range(0, 16, 4):
        for j in range(16):
            g[i][j] = "K" if j % 8 else "A"
    for i in range(16):
        if x == 0:
            g[i][15], g[i][14] = "a", "K"
        if x == 9:
            g[i][0], g[i][1] = "a", "K"
        if y == 8:
            g[0][i], g[1][i] = "a", "K"
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


def boss_door(x, y):
    """Frosted glass double doors with teal frames."""
    g = paint(blank("K"), """
KKKKKKKKKKKKKKKK
KTTTTTTTTTTTTTTK
KTKKKKKKKKKKKTTK
KTKBBBBBBBBBKTTK
KTKBWBBBBBBBKTTK
KTKBBWBBBBBBKTTK
KTKBBBWBBBBBKTTK
KTKBBBBBBBBBKTKK
KTKBBBBBBBBBKTKK
KTKBBBBWBBBBKTTK
KTKBBBBBWBBBKTTK
KTKBBBBBBBBBKTTK
KTKKKKKKKKKKKTTK
KTTTTTTTTTTTTTTK
KTTTTTTTTTTTTTTK
KKKKKKKKKKKKKKKK
""")
    return g if x == 4 else flip(g)


def elevator(x, y):
    g = paint(blank("K"), """
KKKKKKKKKKKKKKKK
KAAAAAAAAAAAAAAK
KAKKKKKKKKKKKKAK
KAKWWWWWWWWWWKAK
KAKWAAAAAAAAWKAK
KAKWAWWWWWWAWKAK
KAKWAWAAAAWAWKAK
KAKWAWAAAAWAWKAK
KAKWAWAAAAWAWKAK
KAKWAWAAAAWAWKAK
KAKWAWWWWWWAWKAK
KAKWAAAAAAAAWKAK
KAKWWWWWWWWWWKAK
KAKKKKKKKKKKKKAK
KAAAAAAAAAAYYAAK
KKKKKKKKKKKKKKKK
""")
    for yy in range(2, 14):
        g[yy][15] = "K"
    return g if x == 4 else flip(g)


# --- wall decorations -----------------------------------------------------------


def art_poster_teamwork():
    """Motivational poster: a mountain with a flag on top, WIN."""
    g, x0, x1 = framed(1, wall_plain, fill="W", inset=1, top=2, bottom=12)
    paint(g, """
.....K....
.....KTT..
.....KT...
.....K....
....TTT...
...TTTTT..
..TTTTTTT.
""", top=3, left=2)
    return g


def art_poster_hustle():
    g, x0, x1 = framed(1, wall_plain, fill="T", inset=1, top=2, bottom=12)
    paint(g, """
....WW..
...WWW..
..WWWW..
.WWWWW..
...WW...
...W....
""", top=3, left=4)
    stamp_center(g, 9 + 0, "GO!", "W", x0, x1 + 1)
    return g


def art_floor_sign():
    g, x0, x1 = framed(1, wall_plain, fill="T", inset=3, top=2, bottom=12)
    stamp_center(g, 4, "3", "W", x0, x1 + 1)
    paint(g, """
WWWW
""", top=10, left=6)
    return g


def art_whiteboard():
    """Whiteboard full of arrows that go nowhere (3 tiles)."""
    g, x0, x1 = framed(3, wall_plain, fill="W", inset=1, top=2, bottom=12)
    art = """
.KKK...........RR....KKKK.....KK.......
.K.K..RRRRRRRRRR.....K..K....K..K......
.KKK...........RR....KKKK....K..K......
...R..................R.......KK.......
...R..................R........R.......
...RR.......KKKK......RRRRRRRRRR.......
....RRRRRRRRK..K........................
............KKKK..........RRRRRR..KKKK.
.............R...........R.......RK..K.
.............RRRRRRRRRRRR.........KKKK.
"""
    paint(g, art, top=3, left=x0 + 2)
    return g


def art_shhh():
    g, x0, x1 = framed(2, wall_plain, fill="T", inset=2, top=2, bottom=12)
    stamp_center(g, 5, "SHHHH", "W", x0, x1 + 1)
    return g


def art_kanban():
    """Kanban board: a wall of sticky notes, all in TO DO."""
    g, x0, x1 = framed(2, wall_plain, fill="W", inset=1, top=2, bottom=12)
    for xx in (x0 + 10, x0 + 20):
        for yy in range(3, 12):
            g[yy][xx] = "K"
    rnd = random.Random(4)
    for col0 in (x0 + 2,):
        for yy in range(3, 11, 3):
            for xx in range(col0, x0 + 9, 3):
                g[yy][xx] = g[yy][xx + 1] = g[yy + 1][xx] = g[yy + 1][xx + 1] = "Y"
    g[4][x0 + 13] = g[4][x0 + 14] = "Y"
    return g


def art_timer():
    """Standup timer: 0:00 and still going."""
    g, x0, x1 = framed(1, wall_plain, fill="K", inset=1, top=3, bottom=11)
    stamp(g, 3, 5, "9:59", "R")
    return g


def art_calendar():
    g, x0, x1 = framed(1, wall_plain, fill="W", inset=3, top=2, bottom=13)
    for xx in range(x0 + 1, x1):
        g[3][xx] = g[4][xx] = "R"
    for yy in range(6, 13, 2):
        for xx in range(x0 + 1, x1, 2):
            g[yy][xx] = "K"
    return g


def art_big_calendar():
    """Giant wall calendar: every single day is FINAL 1:1."""
    g, x0, x1 = framed(3, wall_plain, fill="W", inset=1, top=1, bottom=14)
    for yy in (2, 3):
        for xx in range(x0 + 1, x1):
            g[yy][xx] = "R"
    stamp_center(g, 5, "FINAL 1:1", "R", x0, x1 + 1)
    for xx in range(x0, x1 + 1, 6):
        for yy in range(11, 14):
            g[yy][xx] = "K"
    for xx in range(x0, x1 + 1):
        g[11][xx] = "K"
    for xx in range(x0 + 2, x1, 6):
        g[12][xx] = g[12][xx + 1] = "R"
    return g


def art_projector():
    """Huge projector screen with a chart that only goes up (4 tiles)."""
    g, x0, x1 = framed(4, wall_plain, fill="W", inset=1, top=1, bottom=13)
    for xx in range(x0, x1 + 1):
        g[1][xx] = "K"
    bars = [2, 3, 3, 4, 5, 5, 6, 7, 8]
    for i, hgt in enumerate(bars):
        bx = x0 + 6 + i * 6
        for yy in range(12 - hgt, 12):
            for xx in range(bx, bx + 4):
                g[yy][xx] = "B"
    stamp(g, x0 + 3, 3, "Q3", "K")
    for xx in range(x0 + 2, x1 - 1):
        g[12][xx] = "K"
    g[14] = ["K"] * len(g[0])
    for xx in (30, 33):
        g[14][xx] = "K"
    return g


# --- props -------------------------------------------------------------------


def p_desk(x, y):
    """Bench desks, all identical: a white desktop with a monitor, a teal chair
    tucked in. Neighbouring desks join into one long bench."""
    rows = CTX["rows"]
    left_end = rows[y][x - 1] != "M"
    right_end = rows[y][x + 1] != "M"
    g = plain()
    # desktop (rows 0..7 white with monitor), front edge grey
    for yy in range(0, 8):
        for xx in range(16):
            g[yy][xx] = "W"
    paint(g, """
...KKKKKKKKKK...
...KBBBBBBBBK...
...KBBBBBBBWK...
...KBBBBBBBBK...
...KKKKKKKKKK...
......KAAK......
....KKKKKKKK....
................
""".replace(".", "W"))
    for xx in range(16):
        g[8][xx] = "A"
        g[9][xx] = "K"
    if left_end:
        for yy in range(0, 10):
            g[yy][0] = "K"
    if right_end:
        for yy in range(0, 10):
            g[yy][15] = "K"
    for xx in range(16):
        if left_end and xx == 0 or right_end and xx == 15:
            continue
    # chair in front
    paint(g, """
.....KKKKKK.....
....KTTTTTTK....
....KTTTTTTK....
.....KKKKKK.....
.......KK.......
....KK.KK.KK....
""", top=10)
    return g


def p_table(x, y):
    """Long white meeting table, 4x2 metatiles."""
    big = blank("f", 64, 32)
    for yy in range(2, 30):
        for xx in range(1, 63):
            big[yy][xx] = "W"
    for xx in range(1, 63):
        big[2][xx] = "K"
        big[27][xx] = "A"
        big[28][xx] = "A"
        big[29][xx] = "K"
    for yy in range(2, 30):
        big[yy][1] = big[yy][62] = "K"
    # forgotten papers and a conference phone
    paint(big, """
KKKKKKK
KAAAAAK
KAKKKAK
KAAAAAK
KKKKKKK
""", top=12, left=29)
    for px, py in ((8, 8), (48, 18)):
        paint(big, """
KKKKK
KWWWK
KAAWK
KWWWK
KKKKK
""", top=py, left=px)
    return slice16(big, run_index(x, y, "T"), col_index(x, y, "T"))


def p_chair(x, y):
    return on_floor("""
................
....KKKKKKKK....
...KTTTTTTTTK...
...KTTTTTTTTK...
...KTTTTTTTTK...
....KKKKKKKK....
...KTTTTTTTTK...
...KTTTTTTTTK...
....KKKKKKKK....
.......KK.......
....KKKKKKKK....
...KA..KK..AK...
""", top=1)


def p_plant(x, y):
    """One plant. Sterile, but alive."""
    return on_floor("""
.......K........
......KGK.......
...K..KGK..K....
..KGK.KgK.KGK...
..KGGKKGKKGGK...
...KgGKGKGgK....
....KKGGGKK.....
.....KKKKK......
.....KgggK......
....KgKKKgK.....
....KgggggK.....
.....KKKKK......
""", top=2)


def p_trash(x, y):
    return on_floor("""
....W..WW.W.....
...WKWWKWWKW....
..KKKKKKKKKKKK..
..KAAAAAAAAAAK..
...KAWAAAWAAK...
...KAWAAAWAAK...
...KAWAAAWAAK...
...KAWAAAWAAK...
....KAAAAAAK....
....KKKKKKKK....
""", top=3)


def p_fax(x, y):
    """Fax machine on a stand, mid-fax since 1998."""
    return on_floor("""
.....KKKKKK.....
.....KWWWWK.....
.....KWKKWK.....
..KKKKKKKKKKKK..
..KAAAAAAAAAAK..
..KAKKKAWAWAAK..
..KAAAAAAAAAAK..
..KKKKKKKKKKKK..
..KWWWWWWWWWK...
...KKKKKKKKK....
....KA....AK....
....KA....AK....
....KK....KK....
""", top=1)


def p_booth(x, y, lower):
    """Phone booth: glass box, nobody inside."""
    g = blank("A")
    for i in range(16):
        g[i][0] = g[i][15] = "K"
    if not lower:
        g[0] = ["K"] * 16
        for yy in range(3, 16):
            for xx in range(2, 14):
                g[yy][xx] = "B"
        for xx in range(2, 14):
            g[2][xx] = "K"
        for yy in range(3, 16):
            g[yy][2] = g[yy][13] = "K"
        g[5][4] = g[6][5] = g[7][6] = "W"
        g[1][6] = g[1][7] = g[1][8] = g[1][9] = "W"
    else:
        for yy in range(0, 12):
            for xx in range(2, 14):
                g[yy][xx] = "B"
        for yy in range(0, 12):
            g[yy][2] = g[yy][13] = "K"
        for xx in range(2, 14):
            g[12][xx] = "K"
        g[6][11] = g[7][11] = "K"
        g[3][9] = g[4][10] = "W"
        g[15] = ["K"] * 16
    return g


def p_beanbag(x, y, color):
    return on_floor("""
................
.....KKKKKK.....
...KKCCCCCCKK...
..KCCWCCCCCCCK..
.KCCWCCCCCCCCCK.
.KCCCCCCCCCCCCK.
.KCCCCCCCCCCCCK.
.KCCCCCCCCCCCCK.
..KCCCCCCCCCCK..
...KKKKKKKKKK...
""".replace("C", color), top=3)


def p_water(x, y):
    """Sparkling water dispenser, teal."""
    return on_floor("""
................
....KKKKKKKK....
....KTTTTTTK....
....KTKKKKTK....
....KTTTTTTK....
....KKKKKKKK....
....KAAAAAAK....
....KAKKKKAK....
....KAAAAAAK....
....KKKKKKKK....
""", top=2)


TILES = {
    # structure
    ".": (floor, False),
    "C": (floor, False),
    "y": (scatter, False),
    "=": (wall, True),
    "#": (wall_top, True),
    "d": (door, False),
    "B": (boss_door, False),
    "E": (elevator, False),
    # wall decorations (row 0)
    "P": (lambda x, y: art_poster_teamwork(), True),
    "H": (lambda x, y: art_poster_hustle(), True),
    "3": (lambda x, y: art_floor_sign(), True),
    "[": (wide(art_whiteboard, "[_]"), True),
    "_": (wide(art_whiteboard, "[_]"), True),
    "]": (wide(art_whiteboard, "[_]"), True),
    "S": (wide(art_shhh, "S"), True),
    "K": (wide(art_kanban, "K"), True),
    "Z": (lambda x, y: art_timer(), True),
    "c": (lambda x, y: art_calendar(), True),
    "{": (wide(art_big_calendar, "{^}"), True),
    "^": (wide(art_big_calendar, "{^}"), True),
    "}": (wide(art_big_calendar, "{^}"), True),
    "<": (wide(art_projector, "<~>"), True),
    "~": (wide(art_projector, "<~>"), True),
    ">": (wide(art_projector, "<~>"), True),
    # props
    "M": (p_desk, True),
    "T": (p_table, True),
    "h": (p_chair, True),
    "G": (p_plant, True),
    "t": (p_trash, True),
    "x": (p_fax, True),
    "U": (lambda x, y: p_booth(x, y, False), True),
    "u": (lambda x, y: p_booth(x, y, True), True),
    "r": (lambda x, y: p_beanbag(x, y, "R"), True),
    "b": (lambda x, y: p_beanbag(x, y, "T"), True),
    "j": (p_water, True),
}

ROOMS = {
    "conference": (1, 0, "The Big Conference Room", """
=H=<~~>=P=
#.h....h.#
#........#
#h......h#
#h......h#
#........#
#h......h#
#h......h#
####dd####
"""),
    "scheduling": (0, 1, "Scheduling Office", """
=c{^}c=cc=
#........#
#.x....C.#
#........#
#...MM...d
#...MM...#
#t......j#
#y.......#
##########
"""),
    "standup_corridor": (1, 1, "Standup Corridor", """
=KK=BB=Z==
#G......t#
#........#
#........#
d........#
#........#
#........#
#h.y..y.h#
####dd####
"""),
    "meeting_room": (0, 2, "Meeting Room 4B", """
=[_]==P===
#........#
#........#
#...hh...#
#..TTTT..d
#..TTTT..#
#...hh...#
#G......t#
##########
"""),
    "bullpen": (1, 2, "The Bullpen", """
=P=Hdd=P3=
#........#
#.MM..MM.#
#.MM..MM.#
d........d
#.MM..MM.#
#.MM..MM.#
#y......t#
####dd####
"""),
    "quiet_room": (2, 2, "Quiet Room", """
==SS==H===
#UU.C..UU#
#uu....uu#
#........#
d..r..b..#
#........#
#UU....UU#
#uu.rb.uu#
##########
"""),
    "office_landing": (1, 3, "Floor 3 Landing", """
=H=3dd=P==
#G......G#
#........#
#........#
#.y......#
#........#
#j......t#
#........#
####EE####
"""),
}
for _n in ROOMS:
    ROOM_FLOOR[_n] = "vinyl"

PROPS_HINT = {
    "conference": [
        {"name": "projector_screen", "pos": [4, 0]},
        {"name": "hustle_poster", "pos": [1, 0]},
        {"name": "mountain_win_poster", "pos": [8, 0]},
        {"name": "pushed_aside_chairs", "pos": [1, 3]},
    ],
    "scheduling": [
        {"name": "final_one_on_one_calendar", "pos": [3, 0]},
        {"name": "small_calendar", "pos": [1, 0]},
        {"name": "fax_machine", "pos": [2, 2]},
        {"name": "scheduler_desk", "pos": [4, 4]},
        {"name": "sparkling_water", "pos": [8, 6]},
    ],
    "standup_corridor": [
        {"name": "kanban_board", "pos": [2, 0]},
        {"name": "standup_timer", "pos": [7, 0]},
        {"name": "office_plant", "pos": [1, 1]},
        {"name": "trash_can", "pos": [8, 1]},
    ],
    "meeting_room": [
        {"name": "whiteboard_of_arrows", "pos": [2, 0]},
        {"name": "long_meeting_table", "pos": [3, 4]},
        {"name": "empty_chair", "pos": [4, 3]},
        {"name": "mountain_win_poster", "pos": [6, 0]},
        {"name": "office_plant", "pos": [1, 7]},
    ],
    "bullpen": [
        {"name": "identical_desk", "pos": [2, 2]},
        {"name": "another_identical_desk", "pos": [7, 6]},
        {"name": "floor_3_sign", "pos": [8, 0]},
        {"name": "hustle_poster", "pos": [3, 0]},
        {"name": "overflowing_trash", "pos": [8, 7]},
    ],
    "quiet_room": [
        {"name": "shhhh_sign", "pos": [3, 0]},
        {"name": "phone_booth", "pos": [1, 2]},
        {"name": "red_beanbag", "pos": [3, 4]},
        {"name": "teal_beanbag", "pos": [6, 4]},
    ],
    "office_landing": [
        {"name": "floor_3_sign", "pos": [3, 0]},
        {"name": "office_plant", "pos": [1, 1]},
        {"name": "sparkling_water", "pos": [1, 6]},
        {"name": "mountain_win_poster", "pos": [7, 0]},
    ],
}

CLEARS = {
    "conference": [(x, y) for x in range(2, 8) for y in range(2, 8)],
    "meeting_room": [c for (x, y) in ((2, 3), (7, 3), (2, 6), (7, 6))
                     for c in ((x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))],
    "standup_corridor": [(x, y) for x in range(1, 9) for y in range(3, 7)],
    "bullpen": [(x, 1) for x in range(1, 9)] + [(x, 7) for x in range(1, 8)]
               + [(1, y) for y in range(1, 8)] + [(8, y) for y in range(1, 7)]
               + [(4, y) for y in range(1, 8)] + [(5, y) for y in range(1, 8)],
}


def check_doors():
    check_doors_spec(spec_of(__name__))


def check_layouts():
    check_layouts_spec(spec_of(__name__), CLEARS)


def main():
    build_all(spec_of(__name__), "office", "open-office-preview.png", "open-office-collision.txt",
              "Open-Plan Office (Floor 3)", CLEARS)


if __name__ == "__main__":
    main()
