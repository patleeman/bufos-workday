"""Build Bufo's GB Studio actor sprite sheet.

Output: assets/sprites/bufo.png, a 96x16 "Animated Actor" sheet with six
16x16 frames: down A, down B, up A, up B, right A, right B. GB Studio flips
the right-facing frames to make left.

Pixel key:  . transparent   D darkest   M middle   L lightest
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# GB Studio's fixed sprite shades. The scene's sprite palette recolors them.
GBS = {
    ".": (0x65, 0xFF, 0x00),
    "D": (0x07, 0x18, 0x21),
    "M": (0x86, 0xC0, 0x6C),
    "L": (0xE0, 0xF8, 0xCF),
}

# Suggested in-game Bufo palette, used for the preview only.
BUFO = {
    ".": None,
    "D": (0x1C, 0x2A, 0x1C),
    "M": (0x6B, 0x9B, 0x4B),
    "L": (0xDF, 0xE8, 0xA8),
}

DOWN_A = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
.DMMDDDDDDDDMMD.
DDDLLLDMMDLLLDDD
DMLLDDDMMDDDLLMD
DMMLLLMMMMLLLMMD
DMMMMMMMMMMMMMMD
DMMMMMDMMDMMMMMD
DMMMMMMMMMMMMMMD
DMMDDDDDDDDDDMMD
.DDMLLLLLLLLMDD.
DMDLLLLLLLLLLDMD
DMDLLLLLLLLLLDMD
.DDMLLLLLLLLMDD.
.DMMDDDDDDDDDMD.
.DDDD.......DD..
"""

UP_A = """
..DDDD....DDDD..
.DMMMMD..DMMMMD.
.DMMMMDDDDMMMMD.
DMMMMMMMMMMMMMMD
DMMMLMMMMMMLMMMD
DMMMMMMMMMMMMMMD
DMMMMMMLMMMMMMMD
DMLMMMMMMMMMLMMD
DMMMMMMMMMMMMMMD
.DMMMMMMMMMMMMD.
.DMMMMMLMMMMMMD.
DMDMMMMMMMMMMDMD
DMDMMMMMMMMMMDMD
.DDMMMMMMMMMMDD.
.DMMDDDDDDDDDMD.
.DDDD.......DD..
"""

RIGHT_A = """
........DDDD....
.......DMMMMD...
.......DDDDDD...
....DDDDLLLDLD..
...DMMMDLLLDDMD.
..DMMMMMDLLLLMMD
.DMMMLMMMMMMMMMD
.DMMMMMMMMMMMDMD
DMMLMMMMMMMMMMMD
DMMMMMMMMDDDDDD.
DMMMMMMMLLLLLLD.
DMMMMMMDLLLLLD..
.DMMMMDMLLLLD...
..DMMDDMMDDD....
..DMMD..DMMD....
..DDDD...DDDD...
"""

RIGHT_B = """
........DDDD....
.......DMMMMD...
.......DDDDDD...
....DDDDLLLDLD..
...DMMMDLLLDDMD.
..DMMMMMDLLLLMMD
.DMMMLMMMMMMMMMD
.DMMMMMMMMMMMDMD
DMMLMMMMMMMMMMMD
DMMMMMMMMDDDDDD.
DMMMMMMMLLLLLLD.
DMMMMMMDLLLLLD..
.DMMMMDMLLLLD...
.DMMDDDMMDDD....
DMMD....DMMD....
DDDD.....DDD....
"""


def parse(art):
    rows = [r for r in art.strip().splitlines()]
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), art
    return rows


def mirror(rows):
    return [r[::-1] for r in rows]


FRAMES = [
    parse(DOWN_A),
    mirror(parse(DOWN_A)),
    parse(UP_A),
    mirror(parse(UP_A)),
    parse(RIGHT_A),
    parse(RIGHT_B),
]


def render(colors, scale=1, bg=None):
    img = Image.new("RGBA", (96 * scale, 16 * scale), bg or (0, 0, 0, 0))
    for f, rows in enumerate(FRAMES):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                c = colors[ch]
                if c is None:
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        img.putpixel((f * 16 * scale + x * scale + dx, y * scale + dy), (*c, 255))
    return img


def main():
    sheet = render(GBS).convert("RGB")
    sheet.save(ROOT / "assets/sprites/bufo.png")

    # Preview: frames in Bufo colors on the basement floor color, 8x scale.
    render(BUFO, scale=8, bg=(0x6F, 0x7A, 0x8E, 255)).save(ROOT / "previews/bufo-sprite-preview.png")

    used = {sheet.getpixel((x, y)) for x in range(96) for y in range(16)}
    assert used <= set(GBS.values()), used
    print("bufo.png OK:", sheet.size, "colors:", len(used))


if __name__ == "__main__":
    main()
