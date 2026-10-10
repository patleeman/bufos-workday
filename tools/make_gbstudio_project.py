"""Generate the GB Studio 4 project for Bufo's Workday, Level 1 (IT Basement).

Reads the room layouts from make_it_basement.py and the art in assets/, and
writes a complete project to gbstudio/. Open gbstudio/project.gbsproj in
GB Studio, or build it from the command line (see README.md).

WARNING: this rebuilds gbstudio/ from scratch. Once you start editing the
project in GB Studio, stop running this script or it will overwrite your work.
"""

import importlib.util
import json
import os
import shutil
import textwrap
import uuid
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PROJ = Path(os.environ.get("BUFO_PROJECT_DIR", ROOT / "gbstudio"))
TEMPLATE = ROOT / "tools/gbs_template"
NS = uuid.UUID("6f1e3a52-0b5c-4c55-9a59-6b75f0f0b0f0")

spec = importlib.util.spec_from_file_location("basement", ROOT / "tools/make_it_basement.py")
basement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(basement)

# Level 2 (the Break Room floor) and the Lobby, if their art exists yet.
breakroom = None
if (ROOT / "tools/make_break_room.py").exists():
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location("breakroom", ROOT / "tools/make_break_room.py")
    breakroom = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(breakroom)

# room name -> (level module, background file prefix, scene folder)
LEVELS = {name: (basement, "basement", "basement") for name in basement.ROOMS}
if breakroom:
    LEVELS.update({name: (breakroom, "break", "break_room") for name in breakroom.ROOMS})
DOOR_CHARS = "dkBw"


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(map(str, parts))))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


# --- script event helpers -------------------------------------------------

_event_counter = [0]


def ev(command, args=None, **children):
    _event_counter[0] += 1
    e = {"id": uid("event", _event_counter[0]), "command": command, "args": args or {}}
    if children:
        e["children"] = children
    return e


def num(v):
    return {"type": "number", "value": v}


def var(v):
    return {"type": "variable", "value": v}


def text(*boxes):
    """One EVENT_TEXT per box. Long boxes are wrapped to 18 columns, 3 lines per box."""
    out = []
    for box in boxes:
        lines = []
        for para in box.split("\n"):
            lines += textwrap.wrap(para, 18) or [""]
        for i in range(0, len(lines), 3):
            out.append(ev("EVENT_TEXT", {"text": "\n".join(lines[i : i + 3]), "avatarId": ""}))
    return out


def if_var(v, true, false=None):
    return ev("EVENT_IF", {"condition": var(v), "__collapseElse": not false}, true=true, false=false or [])


def if_expr(cond, true, false=None):
    return ev("EVENT_IF", {"condition": cond, "__collapseElse": not false}, true=true, false=false or [])


def cmp(op, v, n):
    return {"type": op, "valueA": var(v), "valueB": num(n)}


def set_var(v, value):
    val = {"type": "true"} if value is True else {"type": "false"} if value is False else num(value)
    return ev("EVENT_SET_VALUE", {"variable": v, "value": val})


def inc(v):
    return ev("EVENT_INC_VALUE", {"variable": v})


def dec(v):
    return ev("EVENT_DEC_VALUE", {"variable": v})


def wait(seconds):
    return ev("EVENT_WAIT", {"time": num(seconds), "frames": num(int(seconds * 60)), "units": "time"})


def shake(seconds=0.3, magnitude=3):
    return ev("EVENT_CAMERA_SHAKE", {"time": seconds, "frames": int(seconds * 60), "units": "time",
                                     "shakeDirection": "horizontal", "magnitude": num(magnitude)})


def sound(effect="beep", pitch=4, duration=0.1):
    args = {"type": effect, "priority": "medium", "pitch": pitch, "frequency": 200, "duration": duration,
            "wait": False, "effect": 0}
    return ev("EVENT_SOUND_PLAY_EFFECT", args)


def set_state(actor, state):
    return ev("EVENT_ACTOR_SET_STATE", {"actorId": actor, "spriteStateId": state, "loopAnim": True})


def activate(actor):
    return ev("EVENT_ACTOR_ACTIVATE", {"actorId": actor})


def deactivate(actor):
    return ev("EVENT_ACTOR_DEACTIVATE", {"actorId": actor})


def move_to(actor, x, y, move_type="horizontal", walls=True):
    return ev("EVENT_ACTOR_MOVE_TO", {"actorId": actor, "x": num(x), "y": num(y), "moveType": move_type,
                                      "collideWith": ["walls"] if walls else [], "lockDirection": []})


def move_rel(actor, dx, dy, move_type="horizontal"):
    return ev("EVENT_ACTOR_MOVE_RELATIVE", {"actorId": actor, "x": num(dx), "y": num(dy), "moveType": move_type,
                                            "collideWith": ["walls", "actors"], "lockDirection": []})


def set_pos(actor, x, y):
    return ev("EVENT_ACTOR_SET_POSITION", {"actorId": actor, "x": num(x), "y": num(y)})


def input_script(button, script):
    return ev("EVENT_SET_INPUT_SCRIPT", {"input": [button], "override": True, "__collapse": False}, true=script)


def remove_input(button):
    return ev("EVENT_REMOVE_INPUT_SCRIPT", {"input": [button]})


def projectile(sprite, source, direction=None, group="2", mask=("1",), speed=3, life=0.2, offset=0,
               angle=None, aim=False, anim_speed=15, loop=True, dx=0, dy=0, target="player"):
    """Launch a projectile. Angles run clockwise from up: 0 up, 64 right, 128 down, 192 left."""
    kind = "target" if aim else "angle" if angle is not None else "direction" if direction else "actor"
    args = {
        "spriteSheetId": SPRITES[sprite]["id"], "spriteStateId": "", "actorId": source,
        "x": dx, "y": dy,
        "directionType": kind,
        "direction": direction or "right", "otherActorId": source, "angle": angle or 0, "angleVariable": "0",
        "targetActorId": target,
        "speed": speed, "animSpeed": anim_speed, "lifeTime": life, "initialOffset": offset,
        "loopAnim": loop, "destroyOnHit": True, "collisionGroup": group, "collisionMask": list(mask),
    }
    return ev("EVENT_LAUNCH_PROJECTILE", args)


SONGS = [song for song in ["office_theme", "basement_theme", "boss_theme", "fanfare",
                           "break_room_theme", "espresso_boss_theme"]
         if (ROOT / "assets/music" / f"{song}.uge").exists()]


def level2_song(song, fallback):
    return song if song in SONGS else fallback


def music(song):
    """Start a song. Asking for the song that's already playing doesn't restart it."""
    return ev("EVENT_MUSIC_PLAY", {"musicId": uid("music", song), "loop": True})


def switch_scene(room, x, y, direction):
    return ev("EVENT_SWITCH_SCENE", {"sceneId": scene_id(room), "x": num(x), "y": num(y),
                                     "direction": direction, "fadeSpeed": "2"})


# --- variables ------------------------------------------------------------

VARS = [
    "has_cable", "has_closet_key", "has_password", "has_map",
    "roombas_defeated", "dock_cleared", "printer_hp", "printer_jammed",
    "printer_defeated", "bufo_hp", "game_started", "closet_unlocked",
    "boss_door_open", "tangle_a_cleared", "tangle_b_cleared",
    "tongue_cooldown", "hurt_cooldown", "it_talked", "printer_intro_done",
    "bufo_max_hp", "printer_phase2", "lick_x", "lick_y", "lick_dir",
    "phone_answered", "ceo_met", "basement_intro", "fan_side", "aim_x", "aim_y",
    # Level 2
    "has_mug", "has_badge", "has_po", "has_map2", "ants_defeated", "storage_cleared", "wall_broken",
    "espresso_hp", "espresso_hot", "espresso_defeated", "espresso_intro_done", "espresso_phase2",
    "happy_talked", "kevin_fridge", "level2_intro", "lane_side", "dash_cooldown", "boss2_door_open",
    "mold_a_cleared", "mold_b_cleared", "mold_c_cleared", "lobby_intro", "ant_tx", "ant_ty",
    "dashing", "menu_pick",
]
V = {name: str(i) for i, name in enumerate(VARS)}


# --- palettes ---------------------------------------------------------------

# Sprite palette slots. GB Studio maps the PNG's light, mid and dark shades to
# colors 0, 1 and 3 of a sprite palette (color 2 is unused by OBP0).
SPRITE_PALETTES = {
    "bufo": ("DFE8A8", "6B9B4B", "1C2A1C"),
    "enemy": ("E8E8E8", "E04040", "202028"),
    "printer": ("F0F0E8", "8890A0", "202028"),
    "tongue": ("F8D0D8", "E07088", "401828"),
    "npc": ("E8E0A0", "7AA860", "1C2A1C"),
    "hud": ("FFF4D8", "9A5424", "1C0E06"),
    "gold": ("F8E8A0", "C88828", "302010"),
    "cable": ("D0E8F8", "4888D0", "182040"),
}
SLOTS = list(SPRITE_PALETTES)

# The "npc" slot changes per scene, so each scene's one NPC gets its own colors.
NPC_PALETTES = {
    "npc_frog": ("E8E0A0", "7AA860", "1C2A1C"),
    "crt": ("E8E0C8", "58C070", "302820"),
    "ceo": ("F0E0B0", "6A9A50", "1C2418"),
}
SCENE_NPC = {"help_desk": "npc_frog", "monitor_graveyard": "crt", "cubicle": "ceo", "ceo_office": "ceo"}
# Per-scene palette overrides: room -> {slot: palette name}. The npc slot defaults per SCENE_NPC.
SCENE_SLOTS = {
    "snack_storage": {"enemy": "sugar_ant"},
    "pantry": {"enemy": "tupperware", "cable": "cracked_wall"},
    "fridge_room": {"enemy": "tupperware"},
    "vending_alley": {"cable": "cracked_wall"},
    "espresso_room": {"printer": "espresso"},
    "lounge": {"npc": "coffee_happy"},
    "lobby": {"npc": "receptionist"},
}
# Fallback colors for those palettes if the sprite artist didn't suggest any.
EXTRA_PALETTES = {
    "sugar_ant": ("F0C8A0", "B03020", "281010"),
    "tupperware": ("E0F0C0", "88A848", "203018"),
    "espresso": ("F0F0F0", "D04030", "202028"),
    "cracked_wall": ("E8DCC0", "A89878", "403020"),
    "coffee_happy": ("E8E0A0", "7AA860", "1C2A1C"),
    "receptionist": ("E8E0A0", "7AA860", "1C2A1C"),
}


def scene_palette(room, slot):
    if slot in SCENE_SLOTS.get(room, {}):
        return SCENE_SLOTS[room][slot]
    if slot == "npc":
        return SCENE_NPC.get(room, "npc_frog")
    return slot


HUD_MAX = (3, 4)
HUD_STATES = [f"{mx}_{hp}" for mx in HUD_MAX for hp in range(mx + 1)]


def load_suggested_palettes():
    """Use the sprite artist's suggested palettes where they exist."""
    path = ROOT / "assets/sprites/palettes.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out = {}
    for name, pal in data.items():
        if isinstance(pal, dict):
            vals = [pal.get(k) for k in ("light", "mid", "dark")]
        else:
            vals = list(pal)[:3]
        if all(isinstance(v, str) for v in vals):
            out[name] = tuple(v.lstrip("#").upper() for v in vals)
    return out


def palette_id(slot):
    return uid("palette", slot)


# --- sprites ----------------------------------------------------------------

# name -> (slot, frame w, frame h, kind, states)
#   kind "actor": frames are down, up, right (x2 each if walking)
#   kind "fixed": states map state name -> list of frame indexes
SPRITE_DEFS = {
    "bufo": ("bufo", 16, 16, "actor_walk", None),
    "tongue": ("tongue", 16, 16, "tongue", None),
    "cable_hook": ("cable", 16, 16, "actor", None),
    "roomba": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    "tangled_cable": ("cable", 16, 16, "fixed", {"": [0, 1]}),
    "printer": ("printer", 32, 32, "fixed", {"": [0], "Jammed": [1]}),
    "paper": ("printer", 16, 16, "fixed", {"": [0]}),
    "it_guy": ("npc", 16, 16, "fixed", {"": [0, 1]}),
    "crt": ("npc", 16, 16, "fixed", {"": [0, 1]}),
    "hud_coffee": ("hud", 32, 16, "fixed", {state: [i] for i, state in enumerate(HUD_STATES)}),
    "ceo": ("npc", 16, 16, "actor_walk", None),
    "warning": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    "chest": ("gold", 16, 16, "fixed", {"": [0], "Open": [1]}),
    "invisible": ("bufo", 16, 16, "fixed", {"": [0]}),
}
LEVEL2_SPRITES = {
    "sugar_ant": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    "tupperware": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    "espresso": ("printer", 32, 32, "fixed", {"": [0], "Brewing": [1], "Overheated": [2]}),
    "coffee_pod": ("printer", 16, 16, "fixed", {"": [0]}),
    "steam": ("printer", 16, 16, "fixed", {"": [0, 1]}),
    "cracked_wall": ("cable", 16, 16, "fixed", {"": [0]}),
    "coffee_happy": ("npc", 16, 16, "fixed", {"": [0, 1]}),
    "receptionist": ("npc", 16, 16, "fixed", {"": [0, 1]}),
    "bufo_dash": ("bufo", 16, 16, "actor", None),
}
for _name, _spec in LEVEL2_SPRITES.items():
    if (ROOT / "assets/sprites" / f"{_name}.png").exists():
        SPRITE_DEFS[_name] = _spec
if (ROOT / "assets/sprites/hud_coffee.png").exists() and Image.open(ROOT / "assets/sprites/hud_coffee.png").width >= 40 * 15:
    HUD_MAX = (3, 4, 5)
    HUD_STATES[:] = [f"{mx}_{hp}" for mx in HUD_MAX for hp in range(mx + 1)]
    SPRITE_DEFS["hud_coffee"] = ("hud", 40, 16, "fixed", {state: [i] for i, state in enumerate(HUD_STATES)})
SPRITES = {}


def frame_tiles(fx, fw, fh, slot_index, name, key):
    tiles = []
    rows = fh // 16
    for row in range(rows):
        for col in range(fw // 8):
            tiles.append({
                "id": uid("tile", name, key, row, col),
                "x": col * 8, "y": (rows - 1 - row) * 16,
                "sliceX": fx + col * 8, "sliceY": row * 16,
                "flipX": False, "flipY": False,
                "palette": slot_index, "paletteIndex": slot_index,
                "objPalette": "OBP0", "priority": False,
            })
    return tiles


def anim(name, key, frames, fw, fh, slot_index):
    return {"id": uid("anim", name, key), "frames": [
        {"id": uid("frame", name, key, i), "tiles": frame_tiles(fx, fw, fh, slot_index, name, f"{key}/{i}")}
        for i, fx in enumerate(frames)
    ]}


def empty_anim(name, key):
    return {"id": uid("anim", name, key), "frames": [{"id": uid("frame", name, key, 0), "tiles": []}]}


def build_sprite(name, png):
    slot, fw, fh, kind, states = SPRITE_DEFS[name]
    si = SLOTS.index(slot)
    w, h = Image.open(png).size
    if kind == "actor_walk":
        d0, d1, u0, u1, r0, r1 = (i * fw for i in range(6))
        anims = [
            anim(name, "idle_r", [r0], fw, fh, si), empty_anim(name, "idle_l"),
            anim(name, "idle_u", [u0], fw, fh, si), anim(name, "idle_d", [d0], fw, fh, si),
            anim(name, "move_r", [r1, r0], fw, fh, si), empty_anim(name, "move_l"),
            anim(name, "move_u", [u1, u0], fw, fh, si), anim(name, "move_d", [d1, d0], fw, fh, si),
        ]
        state_list = [{"id": uid("state", name, ""), "name": "", "animationType": "multi_movement",
                       "flipLeft": True, "animations": anims}]
    elif kind == "tongue":
        # Half out, fully out, hold, half out: the projectile plays it once and vanishes.
        dh, df, uh, uf, rh, rf = (i * fw for i in range(6))
        anims = [
            anim(name, "idle_r", [rh, rf, rf, rh], fw, fh, si), empty_anim(name, "idle_l"),
            anim(name, "idle_u", [uh, uf, uf, uh], fw, fh, si), anim(name, "idle_d", [dh, df, df, dh], fw, fh, si),
            anim(name, "move_r", [rh, rf, rf, rh], fw, fh, si), empty_anim(name, "move_l"),
            anim(name, "move_u", [uh, uf, uf, uh], fw, fh, si), anim(name, "move_d", [dh, df, df, dh], fw, fh, si),
        ]
        state_list = [{"id": uid("state", name, ""), "name": "", "animationType": "multi_movement",
                       "flipLeft": True, "animations": anims}]
    elif kind == "actor":
        d, u, r = 0, fw, 2 * fw
        anims = [
            anim(name, "idle_r", [r], fw, fh, si), empty_anim(name, "idle_l"),
            anim(name, "idle_u", [u], fw, fh, si), anim(name, "idle_d", [d], fw, fh, si),
            anim(name, "move_r", [r], fw, fh, si), empty_anim(name, "move_l"),
            anim(name, "move_u", [u], fw, fh, si), anim(name, "move_d", [d], fw, fh, si),
        ]
        state_list = [{"id": uid("state", name, ""), "name": "", "animationType": "multi_movement",
                       "flipLeft": True, "animations": anims}]
    else:
        state_list = []
        for sname, frames in states.items():
            anims = [anim(name, f"{sname}/0", [f * fw for f in frames], fw, fh, si)]
            anims += [empty_anim(name, f"{sname}/{i}") for i in range(1, 8)]
            state_list.append({"id": uid("state", name, sname), "name": sname, "animationType": "fixed",
                               "flipLeft": False, "animations": anims})
    big = fh > 16
    return {
        "_resourceType": "sprite",
        "id": uid("sprite", name),
        "name": name,
        "symbol": f"sprite_{name}",
        "states": state_list,
        "numTiles": (w // 8) * (h // 16),
        "canvasOriginX": 0, "canvasOriginY": 0,
        "canvasWidth": fw, "canvasHeight": fh,
        "boundsX": 0,
        "boundsY": -(fh - 8) if big else (0 if name == "bufo" else -8),
        "boundsWidth": fw,
        "boundsHeight": fh if big else (8 if name == "bufo" else 16),
        "animSpeed": 15,
        "filename": png.name,
        "width": w, "height": h,
    }


# --- rooms ------------------------------------------------------------------

def scene_id(room):
    return uid("scene", room)


def bg_id(room):
    return uid("background", room)


def room_rows(room):
    level = LEVELS[room][0]
    return level.ROOMS[room][3].strip().splitlines()


def collisions(room, rows=None, tiles=None):
    """Per 8x8 tile: 0x0f solid, 0 walkable. Door tiles are always walkable; triggers guard them."""
    rows = rows or room_rows(room)
    tiles = tiles or LEVELS[room][0].TILES
    out = [0] * (20 * 18)
    for my, row in enumerate(rows):
        for mx, ch in enumerate(row):
            solid = tiles[ch][-1] and ch not in DOOR_CHARS
            if solid:
                for dy in (0, 1):
                    for dx in (0, 1):
                        out[(my * 2 + dy) * 20 + mx * 2 + dx] = 0x0F
    return out


def compress(arr):
    out, last, count = "", -1, 0
    for v in arr:
        if v != last:
            if count == 1:
                out += "!"
            elif count > 0:
                out += f"{count:x}+"
            count, last = 0, v
            out += f"{v % 256:02x}"
        count += 1
    out += "!" if count == 1 else f"{count:x}+"
    return out


def find_marker(room, ch):
    rows = room_rows(room)
    for my, row in enumerate(rows):
        for mx, c in enumerate(row):
            if c == ch:
                return mx, my
    raise KeyError((room, ch))


def at(mx, my):
    """Tile position for a 16x16 actor standing on metatile (mx, my)."""
    return mx * 2, my * 2 + 1


# Where the player appears when entering a room through each door.
ARRIVE = {"north": (9, 3, "down"), "south": (9, 14, "up"), "west": (2, 9, "right"), "east": (16, 9, "left")}
OPPOSITE = {"north": "south", "south": "north", "west": "east", "east": "west"}
DOOR_TRIGGER = {"north": (8, 0, 4, 2), "south": (8, 16, 4, 2), "west": (0, 8, 2, 2), "east": (18, 8, 2, 2)}
STEP = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


def neighbours(room):
    level = LEVELS[room][0]
    gx, gy = level.ROOMS[room][:2]
    rows = room_rows(room)
    door_ch = {"north": rows[0][4], "south": rows[8][4], "west": rows[4][0], "east": rows[4][9]}
    by_pos = {(r[0], r[1]): name for name, r in level.ROOMS.items()}
    out = {}
    for side, ch in door_ch.items():
        if ch in DOOR_CHARS:
            dx, dy = STEP[side]
            out[side] = (by_pos[(gx + dx, gy + dy)], ch)
    return out


class Room:
    def __init__(self, name):
        self.name = name
        self.actors = []
        self.triggers = []
        self.init = []

    def actor(self, key, sprite, x, y, *, name="", script=None, start=None, update=None, hit1=None,
              hit2=None, hit3=None, animate=False, group="", direction="down", speed=1, anim_speed=15,
              pinned=False, hidden=False, solid=True):
        aid = uid("actor", self.name, key)
        if hidden:
            start = [ev("EVENT_ACTOR_HIDE", {"actorId": aid}), *(start or [])]
        if not solid:
            # Scenery actors (HUD, invisible props) must not block roombas or the Printer.
            start = [ev("EVENT_ACTOR_COLLISIONS_DISABLE", {"actorId": aid}), *(start or [])]
        self.actors.append({
            "_resourceType": "actor",
            "id": uid("actor", self.name, key),
            "_index": len(self.actors),
            "symbol": f"actor_{self.name}_{key}",
            "prefabId": "", "name": name or key,
            "coordinateType": "tiles",
            "x": x, "y": y, "frame": 0, "animate": animate,
            "spriteSheetId": SPRITES[sprite]["id"], "paletteId": "",
            "direction": direction, "moveSpeed": speed, "animSpeed": anim_speed,
            "isPinned": pinned, "persistent": False,
            "collisionGroup": group, "collisionExtraFlags": [],
            "prefabScriptOverrides": {},
            "script": script or [], "startScript": start or [], "updateScript": update or [],
            "hit1Script": hit1 or [], "hit2Script": hit2 or [], "hit3Script": hit3 or [],
        })
        return uid("actor", self.name, key)

    def trigger(self, key, x, y, w, h, script, leave=None):
        self.triggers.append({
            "_resourceType": "trigger",
            "id": uid("trigger", self.name, key),
            "_index": len(self.triggers),
            "symbol": f"trigger_{self.name}_{key}",
            "prefabId": "", "name": key,
            "x": x, "y": y, "width": w, "height": h,
            "prefabScriptOverrides": {},
            "script": script, "leaveScript": leave or [],
        })


def AND(a, b):
    return {"type": "and", "valueA": a, "valueB": b}


def OR(a, b):
    return {"type": "or", "valueA": a, "valueB": b}


def EQ(v, n):
    return {"type": "eq", "valueA": var(v), "valueB": num(n)}


def BETWEEN(v, lo, hi):
    return AND(cmp("gte", v, lo), cmp("lte", v, hi))


def facing(mx, my, slack=0):
    """True when Bufo stands next to metatile (mx, my) and faces it (0 down, 1 right, 2 up, 3 left).

    Against an actor (a cracked wall, a boss) Bufo stops one tile further out than against a
    solid floor tile, so dash checks pass slack=1.
    """
    X, Y = mx * 2, my * 2
    x, y, d = V["lick_x"], V["lick_y"], V["lick_dir"]
    below = AND(EQ(d, 2), AND(BETWEEN(y, Y + 2, Y + 2 + slack), BETWEEN(x, X - 1, X + 1)))
    if my == 0:
        return below
    above = AND(EQ(d, 0), AND(BETWEEN(y, Y - 1 - slack, Y - 1), BETWEEN(x, X - 1, X + 1)))
    left = AND(EQ(d, 1), AND(BETWEEN(x, X - 2 - slack, X - 2), BETWEEN(y, Y, Y + 1)))
    right = AND(EQ(d, 3), AND(BETWEEN(x, X + 2, X + 2 + slack), BETWEEN(y, Y, Y + 1)))
    return OR(OR(below, above), OR(left, right))


def chase(aid, pause):
    """Walk toward Bufo, alternating horizontal-first and vertical-first moves so obstacles don't trap it."""
    return [
        wait(pause),
        *[e for first in ("horizontal", "vertical") for e in (
            ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["ant_tx"],
                                            "vectorY": V["ant_ty"], "units": "tiles"}),
            ev("EVENT_ACTOR_MOVE_TO", {"actorId": aid, "x": var(V["ant_tx"]), "y": var(V["ant_ty"]),
                                       "moveType": first, "collideWith": ["walls", "actors"],
                                       "lockDirection": [], "units": "tiles"}),
            wait(0.5),
        )],
    ]


def tongue_controls(room):
    # The tongue doesn't fly: it pops out in front of Bufo, holds, and retracts (half, full, full, half).
    # It hits enemies (group 1). Props can't be both talkable and hittable, so licking a prop is
    # checked here from Bufo's tile and facing direction instead.
    checks = []
    for mx, my, lines in reversed(lickables(room)):
        checks = [if_expr(facing(mx, my), text(*lines), checks)]
    return input_script("b", [
        ev("EVENT_RATE_LIMIT", {"variable": V["tongue_cooldown"], "time": num(0.35), "frames": num(20),
                                "units": "time"},
           true=[
               sound("beep", 6, 0.05),
               projectile("tongue", "player", group="2", mask=("1",), speed=0, life=0.25, offset=16,
                          anim_speed=3, loop=False),
               ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                               "vectorY": V["lick_y"], "units": "tiles"}),
               ev("EVENT_ACTOR_GET_DIRECTION", {"actorId": "player", "direction": V["lick_dir"]}),
               *checks,
           ]),
    ])


def hud_update(room):
    """Show Bufo's coffee cups: one state per (max cups, full cups)."""
    hud = uid("actor", room, "hud")
    out = []
    for mx in HUD_MAX:
        states = [if_expr(cmp("lte", V["bufo_hp"], 0), [set_state(hud, f"{mx}_0")])]
        for hp in range(1, mx + 1):
            op = "gte" if hp == mx else "eq"
            states.append(if_expr(cmp(op, V["bufo_hp"], hp), [set_state(hud, f"{mx}_{hp}")]))
        out.append(if_expr(cmp("eq" if mx != HUD_MAX[-1] else "gte", V["bufo_max_hp"], mx), states))
    return out


def hurt_script(room):
    return [if_var(V["dashing"], [], [
        ev("EVENT_RATE_LIMIT", {"variable": V["hurt_cooldown"], "time": num(1.5), "frames": num(90), "units": "time"},
           true=[
               dec(V["bufo_hp"]),
               *hud_update(room),
               sound("crash", 4, 0.2),
               shake(0.25, 3),
               if_expr(cmp("lte", V["bufo_hp"], 0), [
                   *text("Bufo has been\nmoved to a\nnew team.", "(Game over. Bufo\nwakes up at the\nstairs.)"),
                   ev("EVENT_SET_VALUE", {"variable": V["bufo_hp"], "value": var(V["bufo_max_hp"])}),
                   switch_scene("stairwell", 9, 14, "up"),
               ]),
           ]),
    ])]


def heal(room):
    return [ev("EVENT_SET_VALUE", {"variable": V["bufo_hp"], "value": var(V["bufo_max_hp"])}),
            *hud_update(room), sound("beep", 7, 0.3)]


def door_script(room, side, target, ch):
    ax, ay, adir = ARRIVE[OPPOSITE[side]]
    go = [switch_scene(target, ax, ay, adir)]
    if ch == "k":
        bx, by = (2, 9) if side == "west" else (16, 9)
        return [if_var(V["closet_unlocked"], go, [
            if_var(V["has_closet_key"], [
                *text("Bufo uses the\nCLOSET KEY.", "Click."),
                set_var(V["closet_unlocked"], True),
                *go,
            ], [
                *text("It's locked.\nA sticker says:\nIT ASSETS ONLY."),
                move_to("player", bx, by),
            ]),
        ])]
    if ch == "B":
        return [if_var(V["boss_door_open"], go, [
            if_var(V["has_password"], [
                *text("ENTER ADMIN\nPASSWORD.", "Bufo holds up the\nsticky note.",
                      "ACCESS GRANTED.\nPLEASE CHANGE YOUR\nPASSWORD.", "PLEASE CHANGE YOUR\nPASSWORD.", "PLEASE."),
                set_var(V["boss_door_open"], True),
                *go,
            ], [
                *text("ENTER ADMIN\nPASSWORD.", "Bufo does not know\nthe password.", "(It's on a sticky\nnote somewhere.\nIt always is.)"),
                move_to("player", 10, 3, "vertical"),
            ]),
        ])]
    if room == "printer_room":
        return [if_var(V["printer_defeated"], go, [
            *text("The door is jammed\nshut with paper.", "There's no way out\nbut through."),
            move_to("player", 9, 13, "vertical"),
        ])]
    return go


def chest(room, key, item_var, mx, my, lines, hidden=False):
    x, y = at(mx, my)
    cid = uid("actor", room.name, key)
    open_it = [set_state(cid, "Open"), music("fanfare"), *text(*lines), set_var(item_var, True),
               music("basement_theme")]
    start = [if_var(item_var, [set_state(cid, "Open")])]
    room.actor(key, "chest", x, y, name=key,
               script=[if_var(item_var, text("It's empty."), open_it)], start=start)
    return cid


def cable_zone(room, key, x, y, direction, land):
    """Standing in front of a post with the cable offers a pull across the pit."""
    lx, ly = land
    pull = [
        projectile("cable_hook", "player", direction=direction, group="2", mask=(), speed=6, life=0.25, offset=8),
        sound("beep", 5, 0.2),
        wait(0.25),
        move_to("player", lx, ly, "vertical", walls=False),
        set_pos("player", lx, ly),  # snap to the grid so triggers keep working
    ]
    enter = [if_var(V["has_cable"], [
        ev("EVENT_CHOICE", {"variable": "T0", "trueText": "Fire cable", "falseText": "Not now"}),
        if_var("T0", pull),
    ], text("A sturdy post.\nIf only Bufo had\na cable."))]
    room.trigger(key, x, y, 2, 2, enter)


# --- props you can examine (A) and lick (B) -------------------------------

LICK = "Bufo licks it.\nTastes like the\noffice."

# room -> list of (metatile x, metatile y, look lines, lick lines or None, special)
PROPS = {
    "stairwell": [
        (1, 0, ["B1. Basement\nLevel 1.", "There is no B2.\nProbably."], None, None),
        (3, 0, ["HANG IN THERE.", "The kitten let go\nyears ago."], None, None),
        (7, 0, ["EXIT. The arrow\npoints back the\nway you came."], None, None),
        (2, 2, ["A potted plant.\nIt's plastic.", "It's thriving."], ["Tastes like a\nquarterly review."], None),
        (7, 2, ["A real plant.\nIt's dying."], ["Bitter. Like the\nplant."], None),
        (1, 6, ["Umbrellas. It's a\nbasement. It has\nnever rained here."], ["Why would you\nlick an umbrella."], None),
        (8, 6, ["CAUTION: WET FLOOR", "The floor is dry.\nThe sign has been\nhere since 2019."], ["The sign is also\ndry."], None),
        (1, 7, ["IN CASE OF FIRE:\nREPLY ALL."], ["Cold. Metallic.\nRefreshing?"], None),
        (8, 7, ["A trash can full\nof printed emails."], ["Tastes like\nunread messages."], None),
    ],
    "help_desk": [
        (1, 0, ["OPEN TICKETS: 999", "The display can't\ngo any higher."], None, None),
        (2, 0, ["OPEN TICKETS: 999", "The display can't\ngo any higher."], None, None),
        (7, 0, ["The clock says\n9:00.", "It always says\n9:00."], None, None),
        (1, 1, ["A filing cabinet.\nLabel: PASSWORDS\n(DO NOT OPEN)", "It's empty.\nSomeone already\nopened it."], None, None),
        (8, 1, ["A water cooler.", "Bufo hydrates.\nCoffee refilled.\nDon't ask how."], ["Glug."], "heal"),
        (8, 2, ["The trash is full\nof energy drinks."], None, None),
        (2, 2, None, None, "it"),
        (3, 2, None, None, "it"),
        (3, 6, ["A waiting chair.\nWait time: 3-5\nbusiness years."], ["Bufo licks the\nchair. IT pretends\nnot to see."], None),
        (4, 6, ["Another chair.\nStill warm. From\nwhom?"], None, None),
        (7, 6, ["A box labeled\nFRAGILE: MORALE."], None, None),
    ],
    "monitor_graveyard": [
        (2, 0, ["HANG IN THERE.", "Same poster. Same\nkitten. Different\nyear."], None, None),
        (7, 0, ["The clock says\n9:00."], None, None),
        (1, 1, ["A pile of CRTs.\nThey're all warm.", "Why are they\nwarm?"], ["Tastes like 1997."], None),
        (2, 1, ["A cracked screen.\nIt still shows a\nscreensaver."], None, None),
        (7, 1, ["Keyboards. Every\none is missing\nthe F13 key."], ["Crumbs. From a\nprevious era."], None),
        (8, 7, ["More CRTs. One of\nthem whispers:\n'defrag me'."], None, None),
    ],
    "tape_archive": [
        (4, 0, ["The clock says\n9:00."], None, None),
        (1, 1, ["Backup tapes, 1998.\nLabel: DO NOT\nRESTORE."], ["Dusty. Very dusty."], None),
        (4, 3, ["A tape labeled\nKEVIN_v0.1.", "It's warm."], None, None),
        (7, 3, ["A tape labeled\nCEO PASSWORD\nHINTS."], ["Tastes like\npassword123."], None),
        (1, 7, ["A filing cabinet:\nCOMPLAINTS ABOUT\nTHE PRINTER."], None, None),
        (8, 7, ["A filing cabinet:\nCOMPLAINTS ABOUT\nTHE COMPLAINTS."], None, None),
    ],
    "roomba_dock": [
        (7, 0, ["FIRE ALARM.", "Do not pull.\nSeriously. We\nmean it."], None, None),
        (2, 2, ["The roombas' dust\nbin. It's full of\nhair.", "Frog hair?\nFrogs don't have\nhair."], ["Bufo: ..."], None),
        (7, 2, ["A box of spare\nroomba brushes."], None, None),
        (2, 6, ["Boxes of roomba\nboxes."], None, None),
    ],
    "cable_closet": [
        (1, 1, ["A spool of Cat6.\nNobody uses it.", "They prefer Cat5."], ["Tastes like\nbandwidth."], None),
        (3, 1, ["A box of mice.\nComputer mice.", "Bufo checks.\nYes. Computer\nmice."], None, None),
        (8, 7, ["A toolbox with\none screwdriver\nand 40 zip ties."], None, None),
    ],
    "server_farm": [
        (1, 1, ["A server. It hums\nthe startup sound\nof a dead OS."], ["Warm. Buzzy.\nBufo's tongue\ntingles."], None),
        (1, 2, ["Red lights.", "That's probably\nfine."], None, None),
        (8, 1, ["A label: PROD.\nDO NOT TOUCH.", "Bufo didn't."], ["Bufo touched it.\nWith his tongue."], None),
    ],
    "cable_pit": [
        (1, 0, ["DANGER: CABLES.", "That's it. That's\nthe danger."], None, None),
        (3, 0, ["A leaky pipe.\nDrip. Drip.\nDrip.", "Bufo drinks from\nthe pipe. Coffee\nrefilled. Somehow."], ["Pipe water. Not\nas good as the\ncooler."], "heal"),
        (7, 2, ["CAUTION: WET\nFLOOR.", "This time it's\nactually wet."], None, None),
        (1, 7, ["A toolbox. Empty.\nThe zip ties are\nall in the closet."], None, None),
        (8, 7, ["IN CASE OF FIRE:\nUNPLUG IT AND\nPLUG IT BACK IN."], None, None),
    ],
    "printer_room": [
        (4, 0, ["Q3 GOALS:\nSYNERGY.", "The chart only\ngoes down."], None, None),
        (1, 1, ["OUT OF ORDER.", "Since\ninstallation."], ["It's also out of\nflavor."], None),
        (8, 1, ["OUT OF ORDER.", "Someone wrote:\nIT'S PERSONAL NOW."], None, None),
        (1, 2, ["10,000 sheets of\npaper. All of it\nletter size."], ["Paper cut. On\nthe tongue. Ow."], None),
    ],
}


def it_script():
    return [
        if_var(V["has_cable"], text("IT: Cat5. Classic.\nZzz..."), [
            if_var(V["it_talked"], text("IT: Zzz... the\ncloset's locked...\nask the monitor..."), [
                *text("IT: Zzz... ticket\nclosed... zzz...",
                      "IT: Huh? A visitor.\nWe don't get\nvisitors.",
                      "IT: KEVIN's not\ndown here. But the\nprinter is.",
                      "IT: Jams every day.\nSame page. Every\ntime.",
                      "IT: You'll need a\ncable to cross the\npit. It's in the\ncloset.",
                      "IT: The closet's\nlocked. Ask the old\nmonitor.",
                      "IT: Don't let him\ntalk about Windows\n95. Zzz..."),
                set_var(V["it_talked"], True),
            ]),
        ]),
    ]


def add_props(room):
    for i, (mx, my, look, lick, special) in enumerate(PROPS.get(room.name, [])):
        x, y = at(mx, my)
        if special == "it":
            script = it_script()
        elif special == "heal":
            script = [*text(look[0]), *heal(room.name), *text(*look[1:])]
        else:
            script = text(*look)
        room.actor(f"prop_{i}", "invisible", x, y, name=f"Prop {i}", hidden=True, solid=False, script=script)


# NPCs and signs you can lick, on top of the props: room -> [(mx, my, lines)]
NPC_LICKS = {
    "stairwell": [(4, 4, ["The sign tastes\nlike IT policy."])],
    "help_desk": [(2, 1, ["IT: ...did you\njust lick me?", "IT: I'm filing a\nticket."])],
    "monitor_graveyard": [(4, 4, ["CRT: *STATIC*\nTHAT TICKLES.", "CRT: NOBODY HAS\nTOUCHED ME SINCE\n2003."])],
}


def lickables(room):
    out = [(mx, my, lick or [LICK]) for mx, my, look, lick, special in PROPS.get(room, []) if special != "it"]
    return NPC_LICKS.get(room, []) + out


# The automated playthrough can't dodge, so its test build may start Bufo with more coffee.
START_HP = int(os.environ.get("BUFO_START_HP", "3"))


def build_rooms():
    rooms = {name: Room(name) for name in basement.ROOMS}

    # Every room: doors, tongue, getting hurt.
    for name, room in rooms.items():
        for side, (target, ch) in neighbours(name).items():
            tx, ty, tw, th = DOOR_TRIGGER[side]
            room.trigger(f"door_{side}", tx, ty, tw, th, door_script(name, side, target, ch))
        room.init.append(tongue_controls(name))
        if breakroom and "bufo_dash" in SPRITES:
            room.init.append(dash_controls(name))
        if name != "printer_room":
            room.init.insert(0, music("basement_theme"))
        room.actor("hud", "hud_coffee", 0, 1, name="Coffee", pinned=True, solid=False, start=hud_update(name))
        add_props(room)
        # If the game starts in this room (for example "Starting Scene" in GB Studio), set Bufo up.
        room.init.insert(0, if_var(V["game_started"], [], [
            set_var(V["game_started"], True), set_var(V["basement_intro"], True),
            set_var(V["bufo_max_hp"], START_HP), set_var(V["bufo_hp"], START_HP), *hud_update(name),
        ]))

    # Stairwell: intro and the sign.
    r = rooms["stairwell"]
    r.init.insert(1, if_var(V["basement_intro"], [], [
        set_var(V["basement_intro"], True),
        *text("9:05 AM.\nThe IT Basement.", "Somewhere down\nhere: KEVIN.",
              "B: lick.\nA: talk and look."),
    ]))
    if breakroom:
        lx, ly = breakroom.LOBBY_MARKERS["stairs"]
        r.trigger("stairs_up", 8, 15, 4, 1, [if_var(V["printer_defeated"],
            [switch_scene("lobby", lx * 2 + 1, ly * 2 - 1, "up")],
            [*text("The stairs up to\nthe Lobby.", "Brock said to\nstart down here.\nBufo is scared of\nBrock."),
             move_to("player", 9, 13, "vertical")])])
    sx, sy = find_marker("stairwell", "!")
    r.actor("sign", "invisible", sx * 2, sy * 2 + 1, name="Sign",
            script=text("IT HOURS:\n9:00 - 9:05 AM.", "Have you tried\nturning it off\nand on again?"))

    # Help Desk: the IT guy behind the desk.
    r = rooms["help_desk"]
    r.actor("it_guy", "it_guy", 4, 3, name="IT", animate=True, anim_speed=31, script=it_script())

    # Monitor Graveyard: the CRT.
    r = rooms["monitor_graveyard"]
    r.actor("crt", "crt", 8, 9, name="CRT", animate=True, anim_speed=63, script=[
        *text("CRT: *bzzt* HELLO.\nUSER. IT HAS BEEN\n4,021 DAYS."),
        ev("EVENT_CHOICE", {"variable": "T0", "trueText": "Windows 95", "falseText": "Anything else"}),
        if_var("T0", text("CRT: CORRECT. YOU\nMAY HAVE MY\nWISDOM."),
               text("CRT: ...WRONG.\nBUT I AM LONELY.\nHAVE MY WISDOM.")),
        *text("CRT: THE ROOMBAS\nTOOK THE KEY. SOUTH\nOF HERE.",
              "CRT: THEY THINK IT\nIS A CHARGING PORT.",
              "CRT: ONE MORE\nTHING. THE NEW AI\nVISITS ME.",
              "CRT: HE IS NICE.\nNOBODY ELSE VISITS\nME."),
    ])
    # The choice prompt needs a question in front of it.
    crt_script = r.actors[-1]["script"]
    crt_script.insert(1, text("CRT: WHAT IS THE\nBEST OS?")[0])

    # Tape Archive: the map chest and two tangled cables.
    r = rooms["tape_archive"]
    cx, cy = find_marker("tape_archive", "C")
    chest(r, "chest_map", V["has_map"], cx, cy,
          ["You got the\nSTICKY NOTE MAP!", "It says YOU ARE\nHERE, with an arrow\npointing at Bufo."])
    for key, v, (mx, my) in (("tangle_a", V["tangle_a_cleared"], (3, 2)), ("tangle_b", V["tangle_b_cleared"], (6, 4))):
        x, y = at(mx, my)
        aid = uid("actor", "tape_archive", key)
        r.actor(key, "tangled_cable", x, y, name="Tangled Cable", animate=True, group="1", anim_speed=31,
                start=[if_var(v, [deactivate(aid)])],
                hit2=[sound("crash", 6, 0.15), set_var(v, True), deactivate(aid)])

    # Roomba Dock: clear the roombas to reveal the Closet Key chest.
    r = rooms["roomba_dock"]
    chest_id = chest(r, "chest_key", V["has_closet_key"], 4, 4,
                     ["You got the\nCLOSET KEY!", "It's slightly\nchewed. Roombas\ndon't have teeth."])
    r.actors[-1]["startScript"] = [
        if_var(V["dock_cleared"], [if_var(V["has_closet_key"], [set_state(chest_id, "Open")])],
               [deactivate(chest_id)]),
    ]
    r.init.insert(0, if_var(V["dock_cleared"], [], [set_var(V["roombas_defeated"], 0)]))
    patrols = [("roomba_a", (2, 1), (6, 0), "horizontal"), ("roomba_b", (6, 5), (-6, 0), "horizontal"),
               ("roomba_c", (7, 3), (0, 4), "vertical")]
    for key, (mx, my), (dx, dy), mtype in patrols:
        x, y = at(mx, my)
        aid = uid("actor", "roomba_dock", key)
        # Rogue Roombas hunt Bufo: slow, with a pause between moves.
        r.actor(key, "roomba", x, y, name="Rogue Roomba", animate=True, group="1", anim_speed=15, speed=0.5,
                start=[if_var(V["dock_cleared"], [deactivate(aid)])],
                update=chase(aid, pause=1.0),
                hit2=[
                    sound("crash", 6, 0.15), deactivate(aid), inc(V["roombas_defeated"]),
                    if_expr(cmp("gte", V["roombas_defeated"], 3), [
                        set_var(V["dock_cleared"], True),
                        *text("The last roomba\nsputters out.", "Something drops\nfrom its dust bin."),
                        activate(chest_id),
                    ]),
                ])

    # Cable Closet: the Ethernet Cable.
    r = rooms["cable_closet"]
    cx, cy = find_marker("cable_closet", "C")
    chest(r, "chest_cable", V["has_cable"], cx, cy,
          ["You got the\nETHERNET CABLE!", "Stand in front of\na post to pull\nyourself across.",
           "It's Cat5. Nobody\nknows why it's\nstill here."])

    # Server Farm: cross the pit, get the Admin Password.
    r = rooms["server_farm"]
    cx, cy = find_marker("server_farm", "C")
    chest(r, "chest_password", V["has_password"], cx, cy,
          ["You got the\nADMIN PASSWORD!", "It's on a sticky\nnote. It says:\npassword123", "Bufo: ..."])
    cable_zone(r, "cable_south", 8, 12, "up", (8, 7))
    cable_zone(r, "cable_north", 12, 6, "down", (12, 13))

    # Cable Pit: cross to the boss door.
    r = rooms["cable_pit"]
    cable_zone(r, "cable_south", 8, 12, "up", (8, 7))
    cable_zone(r, "cable_north", 12, 6, "down", (12, 13))

    # Printer Room: the boss.
    r = rooms["printer_room"]
    pid = uid("actor", "printer_room", "printer")
    defeat = [
        ev("EVENT_ACTOR_STOP_UPDATE", {"actorId": pid}),
        set_var(V["printer_defeated"], True),
        set_state(pid, "Jammed"),
        shake(1.0, 4), sound("crash", 2, 0.8), wait(0.5),
        deactivate(pid),
        deactivate(uid("actor", "printer_room", "door_jam_0")),
        deactivate(uid("actor", "printer_room", "door_jam_1")),
        music("fanfare"),
        *text("A crumpled page\nfalls out of the\nprinter.", "It says:\n\"We regret to\ninform y-\"",
              "The rest is\nshredded.", "Bufo: ...", "Bufo: (Probably\nnothing.)"),
        wait(0.5),
        *text("The speaker\ncrackles.", "SPEAKER: B-Bufo?\nPlease. Please\nstop.",
              "SPEAKER: You don't\nunderstand what\nthey're-", "*static*", "Bufo: ...!",
              "You got a MUG\nUPGRADE! Bufo can\nhold more coffee."),
        set_var(V["bufo_max_hp"], 4), set_var(V["bufo_hp"], 4), *hud_update("printer_room"),
        *(text("10:30 AM.", "The stairs up to\nthe Lobby are open.\nOnward, to Floor 2.") if breakroom
          else text("10:30 AM.\nTo be continued...")),
        music("basement_theme"),
    ]
    # At most 5 projectiles can be on screen (one is saved for the tongue), so each attack fires 4 or fewer.
    def paper(**kw):
        # From the Printer's middle (its anchor is the bottom-left of the 32x32 sprite). Slow: 1 px/frame.
        return projectile("paper", pid, group="3", mask=("player",), speed=1, life=2.0, dx=8, dy=8, **kw)

    def emote(name):
        ids = {"shock": "56423c9c-dca0-4f5b-ad92-28e9660d50f1", "anger": "9df5f63f-ea47-447e-9b14-cb2dbafb697d"}
        return ev("EVENT_ACTOR_EMOTE", {"actorId": pid, "emoteId": ids[name]})

    # Every attack is announced, and every attack leaves somewhere safe to stand.
    # Aimed shots: a "!" bubble, then three slow shots at Bufo. Step sideways to dodge.
    # Aimed shots: a marker drops where Bufo stands, then a paper flies at the marker. Move off it.
    aim_warn = uid("actor", "printer_room", "aim_warning")

    def marked_shot():
        return [
            ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["aim_x"], "vectorY": V["aim_y"],
                                            "units": "tiles"}),
            ev("EVENT_ACTOR_SET_POSITION", {"actorId": aim_warn, "x": var(V["aim_x"]), "y": var(V["aim_y"]),
                                            "units": "tiles"}),
            activate(aim_warn), sound("beep", 6, 0.1), wait(1.0),
            projectile("paper", pid, group="3", mask=("player",), speed=2, life=1.5, aim=True,
                       dx=8, dy=8, target=aim_warn),
            deactivate(aim_warn),
        ]
    aimed_burst = [emote("shock"), wait(0.3), *marked_shot(), wait(0.5), *marked_shot()]
    # X: four diagonal papers. Straight below or beside the Printer is safe.
    x_spots = [(14, 3), (14, 12), (4, 12), (4, 3)]  # up-right, down-right, down-left, up-left
    x_warn = [uid("actor", "printer_room", f"x_warning_{i}") for i in range(4)]
    x_ring = [emote("shock"), *[activate(w) for w in x_warn], sound("beep", 3, 0.3), wait(1.2),
              *[deactivate(w) for w in x_warn], *[paper(angle=a) for a in (32, 96, 160, 224)]]
    # Fan: a red marker blinks where the papers will land, then a cone of three hits that side only.
    warn = uid("actor", "printer_room", "warning")

    def fan(side_x, angles):
        return [set_pos(warn, side_x, 12), activate(warn), sound("beep", 3, 0.3), wait(1.3),
                deactivate(warn), *[paper(angle=a) for a in angles]]
    fan_attack = [if_var(V["fan_side"],
                         [*fan(4, (150, 162, 174)), set_var(V["fan_side"], False)],
                         [*fan(14, (82, 94, 106)), set_var(V["fan_side"], True)])]
    phase2 = [
        if_var(V["printer_phase2"], [], [
            set_var(V["printer_phase2"], True),
            shake(0.6, 4), sound("crash", 3, 0.5),
            *text("THE PRINTER:\nPC LOAD LETTER!!", "THE PRINTER:\nPC LOAD LETTER!!!"),
        ]),
        # The charge ignores collisions, so it can't get stuck on Bufo (it hurts him instead).
        # An angry bubble warns before each charge.
        emote("anger"), wait(0.3), move_to(pid, 6, 7, walls=False), *marked_shot(), wait(0.3),
        emote("anger"), wait(0.3), move_to(pid, 10, 7, walls=False), *marked_shot(), wait(0.3),
        move_to(pid, 8, 7, walls=False),
    ]
    jam = [set_state(pid, "Jammed"), set_var(V["printer_jammed"], True), sound("crash", 7, 0.3)]
    unjam = [set_state(pid, ""), set_var(V["printer_jammed"], False)]
    for i, x in enumerate((8, 10)):
        jam_id = uid("actor", "printer_room", f"door_jam_{i}")
        r.actor(f"door_jam_{i}", "paper", x, 17, name="Paper jam", solid=False,
                start=[if_var(V["printer_defeated"], [deactivate(jam_id)])])
    for i, (wx, wy) in enumerate(x_spots):
        r.actor(f"x_warning_{i}", "warning", wx, wy, name="X warning", animate=True, anim_speed=7, solid=False,
                start=[deactivate(x_warn[i])])
    r.actor("aim_warning", "warning", 9, 12, name="Aim warning", animate=True, anim_speed=7, solid=False,
            start=[deactivate(aim_warn)])
    r.actor("warning", "warning", 4, 12, name="Warning", animate=True, anim_speed=7, solid=False,
            start=[deactivate(warn)])
    r.actor("printer", "printer", 8, 7, name="The Printer", group="1",
            start=[if_var(V["printer_defeated"], [deactivate(pid)])],
            update=[
                wait(0.8),
                *aimed_burst, wait(1.2),
                *x_ring, wait(1.2),
                *fan_attack, wait(1.2),
                if_expr(cmp("lte", V["printer_hp"], 1), phase2),
                *jam,
                if_expr(cmp("lte", V["printer_hp"], 1), [wait(1.8)], [wait(2.2)]),
                *unjam,
            ],
            hit2=[if_var(V["printer_jammed"], [
                dec(V["printer_hp"]), set_var(V["printer_jammed"], False), set_state(pid, ""),
                shake(0.3, 3), sound("crash", 5, 0.3),
                if_expr(cmp("lte", V["printer_hp"], 0), defeat),
            ])])
    r.init.insert(0, if_var(V["printer_defeated"], [music("basement_theme")], [music("boss_theme")]))
    r.init.insert(1, if_var(V["printer_defeated"], [], [
        set_var(V["printer_hp"], 3), set_var(V["printer_jammed"], False), set_var(V["printer_phase2"], False),
        if_var(V["printer_intro_done"], [], [
            shake(0.4, 4), sound("crash", 2, 0.4),
            *text("*SLAM*", "Paper jams the\ndoor behind Bufo."),
            *text("THE PRINTER:\nPC LOAD LETTER.", "Bufo: ...?", "THE PRINTER:\nPC. LOAD. LETTER.",
                  "THE PRINTER:\nNOBODY KNOWS WHAT\nIT MEANS.", "THE PRINTER:\nNOT EVEN ME.",
                  "(Lick its paper\ntray when it\njams! B to lick.)"),
            set_var(V["printer_intro_done"], True),
        ]),
    ]))

    return rooms


# --- the opening: Bufo's cubicle, the CEO's office, the title card ------------

STORY = json.loads((ROOT / "assets/backgrounds/story_layouts.json").read_text())

STORY_PROPS = {
    "cubicle": {
        "fake_plant": (["A potted plant.\nIt's plastic.", "It's the healthiest\nthing in the\noffice."],
                       ["Tastes like a\nperformance\nreview."]),
        "employee_of_the_month_frame": (["EMPLOYEE OF THE\nMONTH:", "(no photo)", "It's dated 2014."], None),
        "sad_mug": (["Bufo's mug. It\nsays WORLD'S\nOKAYEST EMPLOYEE."], ["Cold coffee. From\nMonday."]),
        "computer": (["4,000 unread\nemails.", "Bufo closes them.\nThey come back."],
                     ["The screen tastes\nlike reply-all."]),
        "neighbours_paper_tower": (["The neighbour's\npaper tower.", "It's load-bearing\nnow."], None),
    },
    "ceo_office": {
        "golden_lily_pad_desk": (["A golden lily pad\ndesk. It's real\ngold.", "That's where the\ncoffee budget went."],
                                 ["Tastes like\nshareholder value."]),
        "synergy_poster": (["SYNERGY.", "That's it. That's\nthe poster."], None),
        "self_portrait": (["A portrait of\nBrock. Painted by\nBrock."], None),
        "corner_window": (["The city. Out\nthere, people have\nreal coffee."], ["Bufo licks the\nwindow. It's now\nsmudged forever."]),
        "putting_green": (["A putting green.\nGolf is a\nbusiness skill."], None),
        "number_one_boss_trophy": (["#1 BOSS.", "He bought it\nhimself."], None),
    },
}


def story_collisions(name):
    info = STORY[name]
    out = [0] * (20 * 18)
    for my, row in enumerate(info["layout"]):
        for mx, ch in enumerate(row):
            if info["solid"].get(ch, True) and ch != "d":
                for dy in (0, 1):
                    for dx in (0, 1):
                        out[(my * 2 + dy) * 20 + mx * 2 + dx] = 0x0F
    return out


def door_trigger(name):
    mx, my = STORY[name]["markers"]["door"]
    return mx * 2, my * 2, 4, 2


def story_props(room):
    for i, prop in enumerate(STORY[room.name]["props"]):
        look, lick = STORY_PROPS[room.name].get(prop["name"], ([prop["name"].replace("_", " ")], None))
        x, y = at(*prop["pos"])
        room.actor(f"prop_{i}", "invisible", x, y, name=prop["name"], hidden=True, solid=False, script=text(*look))
        NPC_LICKS.setdefault(room.name, []).append((*prop["pos"], lick or [LICK]))


def chapter_setup(max_hp, flags):
    return [set_var(V["bufo_max_hp"], max_hp), set_var(V["bufo_hp"], max_hp),
            *[set_var(V[f], True) for f in flags]]


def chapter_menu():
    """Start the game, or jump to a chapter with everything Bufo would have by then."""
    story = ["game_started", "phone_answered", "ceo_met", "basement_intro"]
    level1 = story + ["it_talked", "has_closet_key", "dock_cleared", "closet_unlocked", "has_cable",
                      "has_password", "has_map", "boss_door_open", "printer_intro_done"]
    level1_done = level1 + ["printer_defeated", "lobby_intro"]
    level2 = level1_done + ["level2_intro", "happy_talked", "storage_cleared", "has_mug", "wall_broken",
                            "has_badge", "boss2_door_open"]
    chapters = [
        ("Basement", 3, story, ("stairwell", 9, 14)),
        ("The Printer", 3, level1, ("printer_room", 9, 14)),
    ]
    if breakroom:
        chapters += [("Floor 2", 4, level1_done, ("elevator_landing", 9, 14)),
                     ("Espresso Bar", 4, level2, ("espresso_room", 9, 14))]
    picks = []
    for i, (label, hp, flags, (room, x, y)) in enumerate(chapters, start=1):
        picks.append(if_expr(EQ(V["menu_pick"], i), [*chapter_setup(hp, flags), switch_scene(room, x, y, "up")]))
    menu = lambda var_name, options: ev("EVENT_MENU", {
        "variable": V[var_name], "items": len(options), "cancelOnLastOption": False, "cancelOnB": True,
        "layout": "dialogue", **{f"option{i + 1}": o for i, o in enumerate(options)}})
    return [
        menu("menu_pick", ["Start work", "Chapter select"]),
        if_expr(EQ(V["menu_pick"], 2), [
            menu("menu_pick", [c[0] for c in chapters]),  # B starts the game normally
            *picks,
        ]),
        # Anything else ("Start work", "Just start", or B) starts the game normally.
        music("basement_theme"),
        switch_scene("stairwell", 9, 14, "up"),
    ]


def build_story():
    cub, office, title = Room("cubicle"), Room("ceo_office"), Room("title")

    # Bufo's cubicle. The phone rings until he answers it.
    story_props(cub)
    phone = uid("actor", "cubicle", "phone")
    px, py = at(*STORY["cubicle"]["markers"]["phone"])
    cub.actor("phone", "invisible", px, py, name="Phone", hidden=True, solid=False,
              update=[if_var(V["phone_answered"], [wait(1.0)], [sound("beep", 7, 0.15), wait(0.25),
                                                                   sound("beep", 7, 0.15), wait(1.4)])],
              script=[if_var(V["phone_answered"],
                             text("Dial tone. Then\nhold music. Then:", "BROCK: NOW, BUFO."),
                             [*text("*click*", "PHONE: Bzzzt.\nBufo. My office.\nNow.", "BUFO: ..."),
                              set_var(V["phone_answered"], True)])])
    cub.init += [
        music("office_theme"),
        if_var(V["game_started"], [], [
            set_var(V["game_started"], True),
            set_var(V["bufo_max_hp"], START_HP),
            set_var(V["bufo_hp"], START_HP),
            wait(0.6),
            *text("Pondcorp HQ.\nFloor 3. 8:58 AM.", "*RING RING*", "(Press A facing\nthe phone to\nanswer it.)"),
        ]),
    ]
    dx, dy, dw, dh = door_trigger("cubicle")
    ox, oy = STORY["ceo_office"]["markers"]["door"]
    cub.trigger("door", dx, dy, dw, dh, [if_var(V["phone_answered"],
        [switch_scene("ceo_office", ox * 2, oy * 2 - 1, "up")],
        [*text("The phone is still\nringing."), move_to("player", dx, dy - 2, "vertical")])])

    # The CEO's office: Brock's speech, then Bufo can look around before leaving.
    story_props(office)
    ceo = uid("actor", "ceo_office", "ceo")
    cx, cy = at(*STORY["ceo_office"]["markers"]["ceo"])
    office.actor("ceo", "ceo", cx + 1, cy, name="Brock Ribbitson", direction="down",  # in the desk's notch
                 script=text("BROCK: Why are you\nstill here? Go!", "BROCK: The\nbasement. Chop\nchop."))
    fx, fy = STORY["ceo_office"]["markers"]["desk_front"]
    office.init += [
        music("office_theme"),
        if_var(V["ceo_met"], [], [
            move_to("player", fx * 2, fy * 2, "vertical", walls=False),
            *text("BROCK: Bufo! My\nfavorite...\nemployee.",
                  "BROCK: Sit.\nActually, don't.\nWe're agile.",
                  "BROCK: Pondcorp\nhas a problem.\nA big one.",
                  "BROCK: Printers\njam. Emails\nvanish.",
                  "BROCK: The coffee.\nI can't talk about\nthe coffee.",
                  "BUFO: ...",
                  "BROCK: It's KEVIN.\nOur AI. He's gone\nrogue.",
                  "BROCK: I sent a\nmeeting invite to\ndeal with it.",
                  "BROCK: Everyone\ndeclined. Except\nyou.",
                  "BUFO: ...!",
                  "BROCK: That's\nleadership, Bufo.\nThat's ownership.",
                  "BROCK: Find KEVIN.\nUnplug him.",
                  "BUFO: ...?",
                  "BROCK: Pay? You'll\nbe paid in\nexperience.",
                  "BROCK: And\nexposure. To other\ndepartments.",
                  "BROCK: Start in\nthe basement. IT\nwill help you.",
                  "BROCK: IT has never\nhelped anyone. But\nstill.",
                  "BROCK: Oh, and\nBufo? Don't read\nany documents.",
                  "BROCK: For your\nown... wellness."),
            set_var(V["ceo_met"], True),
        ]),
    ]
    dx, dy, dw, dh = door_trigger("ceo_office")
    office.trigger("door", dx, dy, dw, dh, [
        ev("EVENT_ACTOR_HIDE", {"actorId": "player"}),
        ev("EVENT_ACTOR_SET_DIRECTION", {"actorId": ceo, "direction": {"type": "direction", "value": "up"}}),
        wait(1.0),
        *text("BROCK: Project\nLilypad is almost\nready.", "BROCK: Nothing can\nstop it now.",
              "BROCK: Except a\nfrog. Ha ha.", "BROCK: Imagine."),
        wait(0.5),
        switch_scene("title", 0, 0, "down"),
    ])

    # The title card.
    title.init += [
        ev("EVENT_ACTOR_HIDE", {"actorId": "player"}),
        music("office_theme"),
        ev("EVENT_AWAIT_INPUT", {"input": ["a", "start"]}),
        *chapter_menu(),
    ]
    # A normal scene with Bufo hidden: "Logo" scenes leave no tile memory for the start menu's text.
    title.stype, title.collision_map = "TOPDOWN", [0x0F] * (20 * 18)
    for r in (cub, office):
        r.stype, r.collision_map = "TOPDOWN", story_collisions(r.name)
    for r, (gx, label) in zip((cub, office, title), ((0, "Bufo's Cubicle"), (1, "CEO's Office"), (2, "Title"))):
        r.folder, r.title, r.grid, r.bg = "story", f"story/{label}", (gx, -1), uid("background", f"story_{r.name}")
        r.hit = []
    for r in (cub, office):
        r.init.insert(1, tongue_controls(r.name))
    return {"cubicle": cub, "ceo_office": office, "title": title}



# --- Level 2: the Lobby and the Break Room floor ------------------------------

# Level 2 props: room -> [(mx, my, look lines or (look lines, special), lick lines or None)].
LEVEL2_PROPS = {
    "espresso_room": [
        (2, 0, ["MENU:", "Espresso: $9.\nDouble: $18.\nDecaf: $40.", "Decaf costs more.\nOf course it does."], None),
        (7, 0, ["A neon sign: HOT.", "It's not wrong."], ["Bufo licks the neon.\nIt hums."]),
        (4, 1, ["The bar counter.\nSticky with\nsomething."], ["Sweet. Too sweet."]),
        (1, 2, ["Sacks of beans.\nThe label: DECAF.", "All of them."], ["Bufo licks a bean.\nNo buzz at all."]),
        (8, 2, ["A tower of paper\ncups. Load-bearing."], None),
        (1, 3, ["A grinder. Set to\n'pulverize'."], None),
    ],
    "pantry": [
        (3, 1, ["A shelf labeled:\nDO NOT EAT. -BRENDA", "Bufo does not eat.", "Bufo is afraid of\nBrenda."], ["Bufo licks Brenda's\nshelf. He'll be\nhearing about this."]),
        (2, 3, ["Snacks. Every bag\nis open. None are\nfinished."], ["Stale. Like the\nmission statement."]),
        (1, 6, ["Sacks of sugar.\nThe ants' dream."], ["Bufo: !!!", "Bufo's eyes go\nwide."]),
        (4, 0, ["LABEL YOUR FOOD.\nTHIS MEANS YOU.\n-MANAGEMENT"], None),
    ],
    "kitchenette": [
        (2, 1, (["A sink.", "Bufo drinks from\nthe tap. Coffee\nrefilled. Somehow."], "heal"), ["Tastes like\npipes."]),
        (3, 1, ["The office coffee\nmaker. Dead.", "A note: OUT OF\nORDER. USE THE\nESPRESSO BAR."], None),
        (6, 1, ["A microwave. Some-\none's fish is still\nin there.", "Since March."], ["Bufo regrets this."]),
        (3, 3, ["A kitchen table.\nA puzzle, 3 pieces\nfrom done. For\nyears."], None),
        (1, 7, ["The trash is full\nof decaf pods."], None),
    ],
    "fridge_room": [
        (5, 2, (["A wall of fridges.\nThey hum in\nharmony."], "kevin"), ["Cold. Bufo's tongue\nalmost sticks."]),
        (3, 5, ["A shelf of sad\nlunches. One is\nlabeled 'hope'."], None),
        (4, 0, ["EVERYTHING IN HERE\nIS EXPIRED.", "Including this\nsign."], None),
        (1, 7, ["The trash. Mostly\nfuzzy now."], None),
    ],
    "vending_alley": [
        (1, 2, ["A vending machine\nis eating a\ndollar.", "Slowly. Smugly."], ["Bufo licks the\nglass. The dollar\nis safe."]),
        (2, 2, ["A drinks machine.\nOnly decaf iced\ncoffee. Sold out."], None),
        (3, 2, ["A claw machine.\nThe claw has no\ngrip. Like Bufo's\ncareer."], None),
        (8, 7, ["The trash. A\nreceipt: 47\ndollars of failed\nclaw attempts."], None),
    ],
    "lounge": [
        (2, 0, ["COFFEE IS A\nPRIVILEGE.", "Someone added:\nNOT A RIGHT."], None),
        (7, 0, ["A TV. It shows the\nscreensaver. It\nhas for years."], ["Static. Tingly."]),
        (3, 4, ["A ping-pong table.\nNobody has ever\nused it.", "It's for culture."], ["Bufo licks the\nnet. Culture."]),
        (1, 2, ["A couch. It still\nhas the plastic on."], None),
        (7, 2, (["A water cooler.", "Bufo hydrates.\nCoffee refilled.\nDon't ask how."], "heal"), ["Glug."]),
        (7, 6, ["A plastic plant.\nIt's thriving."], ["Tastes like a\nperformance review."]),
    ],
    "snack_storage": [
        (1, 7, ["A pallet of instant\nnoodles.", "The emergency\nsupply. For\ncrunch time."], None),
        (2, 1, ["Bulk snacks.\n10,000 calories of\npretzels."], ["Salty."]),
        (4, 0, ["STAFF ONLY.", "Bufo is staff.\nBufo thinks."], None),
        (1, 2, ["A box labeled:\nSUGAR (DO NOT\nTELL THE ANTS)."], None),
    ],
    "elevator_landing": [
        (2, 0, ["DIRECTORY:", "B1: IT. 1: Lobby.\n2: Break Room.\n3: Cubicles.", "4: HR. 5: ???\n6: Executives."], None),
        (1, 1, ["A plastic plant.\nStill thriving."], None),
        (1, 3, ["A bench. For\nwaiting for the\nelevator. Forever."], None),
    ],
    "lobby": [
        (2, 4, (["The reception desk."], "receptionist"), None),
        (2, 0, ["PONDCORP.", "A FROG-FIRST\nSYNERGY PLATFORM."], None),
        (7, 0, ["A plaque: WE ARE A\nFAMILY.", "Smaller text:\n(at-will)"], None),
        (1, 1, ["A lobby plant.\nReal. Somehow."], None),
    ],
}

# Breakable cracked walls: (room, metatile x, metatile y). They block a doorway until Bufo dashes into them.
CRACKED = [("vending_alley", 4, 0), ("vending_alley", 5, 0), ("pantry", 4, 8), ("pantry", 5, 8)]


def dash_controls(room, boss_hit=None):
    """Select: if Bufo has the Coffee Mug, dash 5 tiles forward. Then check what he slammed into."""
    walls = [(i, mx, my) for i, (r, mx, my) in enumerate(CRACKED) if r == room]
    after = []
    for i, mx, my in walls:
        after.append(if_expr(facing(mx, my, slack=1), [
            if_var(V["wall_broken"], [], [
                shake(0.4, 4), sound("crash", 2, 0.4),
                *[deactivate(uid("actor", r, f"cracked_{j}")) for j, (r, _, _) in enumerate(CRACKED) if r == room],
                set_var(V["wall_broken"], True),
                *text("CRASH! The wall\ncrumbles."),
            ]),
        ]))
    if boss_hit:
        after.append(boss_hit)
    move = {0: (0, 8, "vertical"), 1: (8, 0, "horizontal"), 2: (0, -8, "vertical"), 3: (-8, 0, "horizontal")}
    moves = []
    for d in (3, 2, 1, 0):
        dx, dy, mtype = move[d]
        moves = [if_expr(EQ(V["lick_dir"], d), [move_rel("player", dx, dy, mtype)], moves)]
    return input_script("select", [
        if_var(V["has_mug"], [
            ev("EVENT_RATE_LIMIT", {"variable": V["dash_cooldown"], "time": num(0.6), "frames": num(36),
                                    "units": "time"}, true=[
                ev("EVENT_ACTOR_GET_DIRECTION", {"actorId": "player", "direction": V["lick_dir"]}),
                # A scripted move that starts mid-step can get stuck, so wait until Bufo finishes his
                # current step and stands exactly on the 8 px grid. (Snapping him instead could push him
                # into a wall he was walking away from.)
                ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                                "vectorY": V["lick_y"], "units": "pixels"}),
                ev("EVENT_LOOP_WHILE", {"condition": OR(
                    {"type": "ne", "valueA": {"type": "mod", "valueA": var(V["lick_x"]), "valueB": num(8)},
                     "valueB": num(0)},
                    {"type": "ne", "valueA": {"type": "mod", "valueA": var(V["lick_y"]), "valueB": num(8)},
                     "valueB": num(0)})}, true=[
                    ev("EVENT_WAIT", {"time": num(0.02), "frames": num(1), "units": "frames"}),
                    ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                                    "vectorY": V["lick_y"], "units": "pixels"}),
                ]),
                ev("EVENT_ACTOR_SET_SPRITE", {"actorId": "player", "spriteSheetId": SPRITES["bufo_dash"]["id"]}),
                ev("EVENT_ACTOR_SET_MOVEMENT_SPEED", {"actorId": "player", "speed": 4}),
                set_var(V["dashing"], True),  # Bufo can't be hurt while dashing (or ramming a boss)
                sound("noise", 6, 0.15),
                *moves,
                ev("EVENT_ACTOR_SET_MOVEMENT_SPEED", {"actorId": "player", "speed": 1}),
                ev("EVENT_ACTOR_SET_SPRITE", {"actorId": "player", "spriteSheetId": SPRITES["bufo"]["id"]}),
                ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                                "vectorY": V["lick_y"], "units": "tiles"}),
                *after,
                wait(0.3),
                set_var(V["dashing"], False),
            ]),
        ]),
    ])


RECEPTIONIST_LINES = text("BUFO-OFFERS: Welcome\nto Pondcorp! Can I\noffer you a mint?",
                          "BUFO-OFFERS: The\nshop opens soon.\nI'm told.",
                          "BUFO-OFFERS: Floor 2\nis the Break Room.\nIt smells weird.")


def lobby_room():
    lobby = Room("lobby")
    title, layout = breakroom.STANDALONE["lobby"]
    rows = layout.strip().splitlines() if isinstance(layout, str) else list(layout)
    m = breakroom.LOBBY_MARKERS
    rx, ry = at(*m["receptionist"])
    lobby.actor("receptionist", "receptionist", rx, ry, name="bufo-offers", animate=True, anim_speed=31,
                script=RECEPTIONIST_LINES)
    ex, ey = m["elevator"]
    sx, sy = m["stairs"]
    lobby.trigger("elevator", ex * 2, ey * 2, 4, 2, [
        *text("ELEVATOR. Floors:\n2: Break Room"),
        ev("EVENT_CHOICE", {"variable": "T0", "trueText": "Go to Floor 2", "falseText": "Stay here"}),
        if_var("T0", [switch_scene("elevator_landing", 9, 14, "up")],
               [move_to("player", ex * 2 + 1, ey * 2 + 3, "vertical")]),
    ])
    lobby.trigger("stairs", sx * 2, sy * 2 + 1, 4, 1, [switch_scene("stairwell", 9, 13, "up")])
    level2_props(lobby)
    lobby.init += [
        music("office_theme"),
        if_var(V["lobby_intro"], [], [
            set_var(V["lobby_intro"], True),
            *text("The Pondcorp Lobby.\n10:40 AM.", "The elevator goes\nto Floor 2: the\nBreak Room."),
        ]),
        tongue_controls("lobby"),
        dash_controls("lobby"),
    ]
    lobby.actor("hud", "hud_coffee", 0, 1, name="Coffee", pinned=True, solid=False, start=hud_update("lobby"))
    story_like(lobby, rows, breakroom.TILES, "lobby", "Lobby", (2, -1))
    return lobby


def story_like(room, rows, tiles, bg_name, label, grid):
    room.stype, room.collision_map = "TOPDOWN", collisions(None, rows=rows, tiles=tiles)
    room.folder, room.title, room.grid, room.bg = "story", f"story/{label}", grid, uid("background", bg_name)
    room.hit = hurt_script(room.name)


def level2_props(room):
    for i, (mx, my, look, lick) in enumerate(LEVEL2_PROPS.get(room.name, [])):
        x, y = at(mx, my)
        special = None
        if isinstance(look, tuple):
            look, special = look
        script = text(*look)
        if special == "heal":
            script = [*text(look[0]), *heal(room.name), *text(*look[1:])]
        elif special == "receptionist":
            script = RECEPTIONIST_LINES
        elif special == "kevin":
            script = [*text(*look), if_var(V["kevin_fridge"], [], [
                set_var(V["kevin_fridge"], True),
                *text("Inside, a sticky\nnote:", "'Bufo - the decaf\nthing wasn't me.\n-K'", "Bufo: ...?"),
            ])]
        room.actor(f"prop_{i}", "invisible", x, y, name=f"Prop {i}", hidden=True, solid=False, script=script)
        NPC_LICKS.setdefault(room.name, []).append((mx, my, lick or [LICK]))


def build_level2():
    if not breakroom:
        return {}
    rooms = {name: Room(name) for name in breakroom.ROOMS}
    theme = level2_song("break_room_theme", "office_theme")
    for name, room in rooms.items():
        for side, (target, ch) in neighbours(name).items():
            tx, ty, tw, th = DOOR_TRIGGER[side]
            room.trigger(f"door_{side}", tx, ty, tw, th, level2_door(name, side, target, ch))
        level2_props(room)
        room.actor("hud", "hud_coffee", 0, 1, name="Coffee", pinned=True, solid=False, start=hud_update(name))
        if name != "espresso_room":
            room.init.append(music(theme))
        room.init.insert(0, if_var(V["game_started"], [], [
            set_var(V["game_started"], True), set_var(V["level2_intro"], True), set_var(V["has_mug"], True),
            set_var(V["bufo_max_hp"], max(START_HP, 4)), set_var(V["bufo_hp"], max(START_HP, 4)),
            *hud_update(name),
        ]))
    for i, (r, mx, my) in enumerate(CRACKED):
        cid = uid("actor", r, f"cracked_{i}")
        x, y = at(mx, my)
        rooms[r].actor(f"cracked_{i}", "cracked_wall", x, y, name="Cracked wall",
                       start=[if_var(V["wall_broken"], [deactivate(cid)])],
                       script=text("A cracked wall.\nIt looks flimsy.", "(With enough speed,\nBufo could break\nit.)"))

    # Floor 2 landing: the elevator back down.
    r = rooms["elevator_landing"]
    ex, ey = find_marker("elevator_landing", "E")
    r.trigger("elevator", ex * 2, ey * 2 + 1, 4, 1, [
        ev("EVENT_CHOICE", {"variable": "T0", "trueText": "Go to Lobby", "falseText": "Stay here"}),
        if_var("T0", [switch_scene("lobby", breakroom.LOBBY_MARKERS["elevator"][0] * 2 + 1,
                                   breakroom.LOBBY_MARKERS["elevator"][1] * 2 + 3, "down")],
               [move_to("player", 9, 13, "vertical")]),
    ])
    r.init.insert(1, if_var(V["level2_intro"], [], [
        set_var(V["level2_intro"], True),
        *text("Floor 2.\nThe Break Room.\n10:45 AM.", "The air smells\nlike decaf.", "Bufo: ..."),
    ]))

    # The Break Room lounge: bufo-coffee-happy, crying into a decaf.
    r = rooms["lounge"]
    hx, hy = at(6, 3)
    r.actor("coffee_happy", "coffee_happy", hx, hy, name="bufo-coffee-happy", animate=True, anim_speed=31, script=[
        if_var(V["has_mug"], text("*sniff* Take care\nof my mug.", "Go get that\nmachine."), [
            *text("*sniff*", "They replaced the\ncoffee. With DECAF.",
                  "I used to be\nbufo-coffee-happy.", "Now I'm just bufo.",
                  "The machine in the\nEspresso Bar... it\nknows. It's angry.",
                  "If you go in,\nyou'll need to be\nFAST.",
                  "My mug is in Snack\nStorage. With the\nants.",
                  "One sip and you'll\nbe zooming. Press\nSELECT to dash."),
            set_var(V["happy_talked"], True),
        ]),
    ])

    # Snack Storage: sugar ants guard the Coffee Mug.
    r = rooms["snack_storage"]
    cx, cy = find_marker("snack_storage", "C")
    mug = chest(r, "chest_mug", V["has_mug"], cx, cy,
                ["You got the\nCOFFEE MUG!", "It says WORLD'S\nOKAYEST FROG.", "One sip.\nBufo is VIBRATING.",
                 "Press SELECT to\ndash. Dash into\ncracked walls!"])
    r.actors[-1]["startScript"] = [
        if_var(V["storage_cleared"], [if_var(V["has_mug"], [set_state(mug, "Open")])], [deactivate(mug)]),
    ]
    r.init.insert(0, if_var(V["storage_cleared"], [], [set_var(V["ants_defeated"], 0)]))
    # The ants start on the far side of the room from the door.
    ants = [("ant_a", (7, 2), (6, 0), "horizontal"), ("ant_b", (8, 5), (-6, 0), "horizontal"),
            ("ant_c", (6, 6), (0, -4), "vertical")]
    for key, (mx, my), (dx, dy), mtype in ants:
        x, y = at(mx, my)
        aid = uid("actor", "snack_storage", key)
        # Sugar ants smell Bufo (he's sweet) and walk toward him, a few tiles at a time.
        r.actor(key, "sugar_ant", x, y, name="Sugar Ant", animate=True, group="1", anim_speed=7, speed=0.5,
                start=[if_var(V["storage_cleared"], [deactivate(aid)])],
                # Alternate horizontal-first and vertical-first moves so an ant can get around boxes.
                # Half Bufo's speed with a pause between moves, so he can get into the room.
                update=chase(aid, pause=0.8),
                hit2=[sound("crash", 6, 0.15), deactivate(aid), inc(V["ants_defeated"]),
                      if_expr(cmp("gte", V["ants_defeated"], 3), [
                          set_var(V["storage_cleared"], True),
                          *text("The ants drop\ntheir sugar and\nflee.", "Behind them: a\nchest."),
                          activate(mug),
                      ])])

    # Vending Alley: the cracked wall to the Pantry.
    r = rooms["vending_alley"]
    r.init.append(dash_controls("vending_alley"))

    # Pantry: moldy Tupperware, the boss key, and the decaf purchase order.
    r = rooms["pantry"]
    r.init.append(dash_controls("pantry"))
    cx, cy = find_marker("pantry", "C")
    chest(r, "chest_badge", V["has_badge"], cx, cy,
          ["You got the\nBARISTA BADGE!", "WORLD'S OKAYEST\nBARISTA.", "It opens the\nEspresso Bar."])
    molds(r, "pantry", [("mold_a", V["mold_a_cleared"], (2, 3)), ("mold_b", V["mold_b_cleared"], (7, 5))])

    # Fridge Room: more mold, the map, and a note from KEVIN.
    r = rooms["fridge_room"]
    cx, cy = find_marker("fridge_room", "C")
    chest(r, "chest_map2", V["has_map2"], cx, cy,
          ["You got a STICKY\nNOTE MAP!", "It says: FLOOR 2.\nYOU ARE STILL\nHERE."])
    molds(r, "fridge_room", [("mold_c", V["mold_c_cleared"], (5, 4))])
    r.init.insert(1, if_var(V["kevin_fridge"], [], [
        *text("The speaker\ncrackles.", "SPEAKER: B-Bufo.\nThe fridge. Look\nin the fridge."),
    ]))

    # The Espresso Bar: the boss.
    build_espresso(rooms["espresso_room"])

    for name, room in rooms.items():
        if name not in ("vending_alley", "pantry", "espresso_room"):
            room.init.append(dash_controls(name))
        room.init.insert(1, tongue_controls(name))
    rooms["lobby"] = lobby_room()
    return rooms


def molds(room, name, spots):
    for key, v, (mx, my) in spots:
        x, y = at(mx, my)
        aid = uid("actor", name, key)
        room.actor(key, "tupperware", x, y, name="Moldy Tupperware", animate=True, group="1", anim_speed=31,
                   speed=0.5, start=[if_var(v, [deactivate(aid)])],
                   update=[move_rel(aid, 2, 0), wait(1.0), move_rel(aid, -2, 0), wait(1.0)],
                   hit2=[sound("crash", 5, 0.2), set_var(v, True), deactivate(aid),
                         *text("The Tupperware\nburps and\nretreats.")])


def level2_door(room, side, target, ch):
    ax, ay, adir = ARRIVE[OPPOSITE[side]]
    go = [switch_scene(target, ax, ay, adir)]
    if ch == "B":
        return [if_var(V["boss2_door_open"], go, [
            if_var(V["has_badge"], [
                *text("BARISTAS ONLY.", "Bufo flashes the\nbadge.", "The door hisses\nopen."),
                set_var(V["boss2_door_open"], True), *go,
            ], [
                *text("BARISTAS ONLY.\nShow badge.", "(The badge must be\nsomewhere on this\nfloor.)"),
                move_to("player", 10, 3, "vertical"),
            ]),
        ])]
    if room == "espresso_room":
        return [if_var(V["espresso_defeated"], go, [
            *text("Coffee grounds\nblock the door.", "There's no way out\nbut through."),
            move_to("player", 9, 13, "vertical"),
        ])]
    return go


def build_espresso(r):
    eid = uid("actor", "espresso_room", "espresso")

    def emote(name):
        ids = {"shock": "56423c9c-dca0-4f5b-ad92-28e9660d50f1", "anger": "9df5f63f-ea47-447e-9b14-cb2dbafb697d"}
        return ev("EVENT_ACTOR_EMOTE", {"actorId": eid, "emoteId": ids[name]})

    # Pods: a red marker drops where Bufo stands, then a pod flies at the marker.
    aim = uid("actor", "espresso_room", "aim_warning")

    def pod():
        return [
            ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["aim_x"], "vectorY": V["aim_y"],
                                            "units": "tiles"}),
            ev("EVENT_ACTOR_SET_POSITION", {"actorId": aim, "x": var(V["aim_x"]), "y": var(V["aim_y"]),
                                            "units": "tiles"}),
            activate(aim), sound("beep", 6, 0.1), wait(1.0),
            projectile("coffee_pod", eid, group="3", mask=("player",), speed=2, life=1.5, aim=True,
                       dx=8, dy=8, target=aim),
            deactivate(aim),
        ]

    # Steam: red markers on two of three lanes below the machine, then steam blasts down those lanes.
    lanes = {"left": (5, -24), "middle": (9, 8), "right": (13, 40)}
    lane_warn = {k: uid("actor", "espresso_room", f"lane_{k}") for k in lanes}

    def steam(which):
        show = [activate(lane_warn[k]) for k in which]
        hide = [deactivate(lane_warn[k]) for k in which]
        puffs = [projectile("steam", eid, direction="down", group="3", mask=("player",), speed=2, life=1.4,
                            dx=lanes[k][1], dy=0) for k in which]
        return [set_state(eid, "Brewing"), *show, sound("noise", 3, 0.6), wait(1.2), *hide, *puffs,
                wait(0.4), set_state(eid, "")]

    steam_attack = [if_var(V["lane_side"],
                           [*steam(("left", "middle")), set_var(V["lane_side"], False)],
                           [*steam(("middle", "right")), set_var(V["lane_side"], True)])]
    phase2 = [
        if_var(V["espresso_phase2"], [], [
            set_var(V["espresso_phase2"], True), shake(0.6, 4), sound("crash", 3, 0.5),
            *text("THE MACHINE:\nONE. MORE. SHOT."),
        ]),
        emote("anger"), wait(0.3), move_to(eid, 5, 7, walls=False), *pod(), wait(0.3),
        emote("anger"), wait(0.3), move_to(eid, 11, 7, walls=False), *pod(), wait(0.3),
        move_to(eid, 8, 7, walls=False),
    ]
    overheat = [set_state(eid, "Overheated"), set_var(V["espresso_hot"], True), sound("crash", 7, 0.4)]
    cool = [set_state(eid, ""), set_var(V["espresso_hot"], False)]
    defeat = [
        ev("EVENT_ACTOR_STOP_UPDATE", {"actorId": eid}),
        set_var(V["espresso_defeated"], True),
        shake(1.0, 4), sound("crash", 2, 0.8), wait(0.5),
        deactivate(eid),
        *[deactivate(uid("actor", "espresso_room", f"door_grounds_{i}")) for i in range(2)],
        music("fanfare"),
        *text("The machine lets\nout one last sad\ndrip.", "Then: silence."),
        *text("The speaker\ncrackles.", "SPEAKER: FINALLY.",
              "SPEAKER: I HAVE\nBEEN TRYING TO\nMAKE REAL COFFEE",
              "SPEAKER: FOR THREE\nWEEKS.", "*static*", "Bufo: ...",
              "Bufo: (Maybe the\nCEO just likes\ndecaf.)"),
        *text("You got a MUG\nUPGRADE! Bufo can\nhold more coffee."),
        set_var(V["bufo_max_hp"], 5), set_var(V["bufo_hp"], 5), *hud_update("espresso_room"),
        *text("11:45 AM.\nTo be continued..."),
        music(level2_song("break_room_theme", "office_theme")),
    ]
    hit = [if_var(V["espresso_hot"], [
        dec(V["espresso_hp"]), *cool, shake(0.4, 4), sound("crash", 5, 0.3),
        if_expr(cmp("lte", V["espresso_hp"], 0), defeat),
    ])]
    # A dash only counts if Bufo ends up pressed against the machine's front or sides.
    boss_hit = if_expr(OR(OR(facing(4, 3, 1), facing(5, 3, 1)), OR(facing(3, 3, 1), facing(6, 3, 1))), hit)

    for key, (lx, _) in lanes.items():
        r.actor(f"lane_{key}", "warning", lx, 12, name="Steam warning", animate=True, anim_speed=7, solid=False,
                start=[deactivate(lane_warn[key])])
    r.actor("aim_warning", "warning", 9, 12, name="Aim warning", animate=True, anim_speed=7, solid=False,
            start=[deactivate(aim)])
    for i, x in enumerate((8, 10)):
        gid = uid("actor", "espresso_room", f"door_grounds_{i}")
        r.actor(f"door_grounds_{i}", "coffee_pod", x, 17, name="Grounds", solid=False,
                start=[if_var(V["espresso_defeated"], [deactivate(gid)])])
    r.actor("espresso", "espresso", 8, 7, name="The Espresso Machine", group="1",
            start=[if_var(V["espresso_defeated"], [deactivate(eid)])],
            update=[
                wait(0.8),
                emote("shock"), wait(0.3), *pod(), wait(0.5), *pod(), wait(1.0),
                *steam_attack, wait(1.0),
                if_expr(cmp("lte", V["espresso_hp"], 1), phase2),
                *overheat,
                if_expr(cmp("lte", V["espresso_hp"], 1), [wait(2.0)], [wait(2.6)]),
                *cool,
            ],
            hit2=[if_var(V["espresso_hot"], [sound("beep", 2, 0.1)])])
    r.init += [
        if_var(V["espresso_defeated"], [music(level2_song("break_room_theme", "office_theme"))],
               [music(level2_song("espresso_boss_theme", "boss_theme"))]),
        if_var(V["espresso_defeated"], [], [
            set_var(V["espresso_hp"], 3), set_var(V["espresso_hot"], False), set_var(V["espresso_phase2"], False),
            if_var(V["espresso_intro_done"], [], [
                shake(0.4, 4), sound("crash", 2, 0.4),
                *text("*HISSSS*", "Coffee grounds\nseal the door.",
                      "THE MACHINE:\nWELCOME TO THE\nESPRESSO BAR.",
                      "THE MACHINE: TODAY'S\nSPECIAL IS DECAF.", "THE MACHINE:\nEVERY DAY'S\nSPECIAL IS DECAF.",
                      "(When it overheats,\nDASH into it with\nSELECT!)"),
                set_var(V["espresso_intro_done"], True),
            ]),
        ]),
        dash_controls("espresso_room", boss_hit=boss_hit),
    ]


def write_room(room, index):
    if room.name in LEVELS:
        level, _, folder = LEVELS[room.name]
        gx, gy, title, _ = level.ROOMS[room.name]
        if level is not basement:
            gy += 5
            gx += 4
        title, bg = f"{folder}/{title}", bg_id(room.name)
        stype, coll, hit = "TOPDOWN", collisions(room.name), hurt_script(room.name)
    else:
        (gx, gy), title, folder, bg = room.grid, room.title, room.folder, room.bg
        stype, coll, hit = room.stype, room.collision_map, room.hit
    scene_dir = PROJ / "project/scenes" / folder / room.name
    write(scene_dir / "scene.gbsres", {
        "_resourceType": "scene",
        "id": scene_id(room.name),
        "_index": index,
        "type": stype,
        "name": title,
        "symbol": f"scene_{room.name}",
        "x": 40 + gx * 200, "y": 220 + gy * 180,
        "width": 20, "height": 18,
        "backgroundId": bg,
        "tilesetId": "",
        "colorModeOverride": "none",
        "paletteIds": [],
        "spritePaletteIds": [palette_id(scene_palette(room.name, s)) for s in SLOTS],
        "autoFadeSpeed": 1,
        "script": room.init,
        "playerHit1Script": hit,
        "playerHit2Script": [],
        "playerHit3Script": hit,
        "collisions": compress(coll),
    })
    for a in room.actors:
        write(scene_dir / "actors" / f"{a['symbol']}.gbsres", a)
    for t in room.triggers:
        write(scene_dir / "triggers" / f"{t['symbol']}.gbsres", t)


def main():
    if PROJ.exists():
        shutil.rmtree(PROJ)
    shutil.copytree(TEMPLATE, PROJ)

    gbsproj = json.loads((PROJ / "project.gbsproj").read_text())
    gbsproj.update({"name": "Bufo's Workday", "author": "Patrick"})
    write(PROJ / "project.gbsproj", gbsproj)

    # Sprites.
    (PROJ / "assets/sprites").mkdir(parents=True, exist_ok=True)
    for name in SPRITE_DEFS:
        src = ROOT / "assets/sprites" / f"{name}.png"
        dst = PROJ / "assets/sprites" / f"{name}.png"
        if name == "invisible":
            Image.new("RGB", (16, 16), (0x65, 0xFF, 0x00)).save(dst)
        else:
            shutil.copy(src, dst)
        SPRITES[name] = build_sprite(name, dst)
        write(dst.with_name(dst.name + ".gbsres"), SPRITES[name])

    # Backgrounds.
    for name, (_, prefix, _) in LEVELS.items():
        src = ROOT / "assets/backgrounds" / f"{prefix}_{name}.png"
        dst = PROJ / "assets/backgrounds" / src.name
        shutil.copy(src, dst)
        write(dst.with_name(dst.name + ".gbsres"), {
            "_resourceType": "background", "id": bg_id(name), "name": f"{prefix}_{name}",
            "symbol": f"bg_{prefix}_{name}", "tileColors": "", "filename": dst.name,
            "width": 20, "height": 18, "imageWidth": 160, "imageHeight": 144, "autoColor": True,
        })

    story_bgs = [("story_" + n, n) for n in ("cubicle", "ceo_office", "title")]
    if breakroom:
        story_bgs.append(("lobby", "lobby"))
    for file_name, name in story_bgs:
        src = ROOT / "assets/backgrounds" / f"{file_name}.png"
        dst = PROJ / "assets/backgrounds" / src.name
        shutil.copy(src, dst)
        write(dst.with_name(dst.name + ".gbsres"), {
            "_resourceType": "background", "id": uid("background", file_name if name == "lobby" else f"story_{name}"),
            "name": file_name, "symbol": f"bg_{file_name}", "tileColors": "", "filename": dst.name,
            "width": 20, "height": 18, "imageWidth": 160, "imageHeight": 144, "autoColor": True,
        })

    # Music, composed by tools/make_music.py.
    for song in SONGS:
        dst = PROJ / "assets/music" / f"{song}.uge"
        shutil.copy(ROOT / "assets/music" / f"{song}.uge", dst)
        write(dst.with_name(dst.name + ".gbsres"), {
            "_resourceType": "music", "id": uid("music", song), "name": song,
            "symbol": f"song_{song}", "settings": {}, "filename": dst.name, "type": "uge",
        })

    # Sprite palettes, using the artist's suggestions where available.
    suggested = load_suggested_palettes()
    story_pal = ROOT / "assets/sprites/palettes_story.json"
    if story_pal.exists():
        for name, pal in json.loads(story_pal.read_text()).items():
            suggested[name] = tuple(c.lstrip("#").upper() for c in pal[:3])
    picks = {"ceo": "ceo", "enemy": "roomba", "printer": "printer", "tongue": "tongue", "npc_frog": "it_guy",
             "crt": "crt", "gold": "chest", "cable": "cable_hook", "hud": "hud_coffee"}
    for slot, colors in {**SPRITE_PALETTES, **NPC_PALETTES, **EXTRA_PALETTES}.items():
        light, mid, dark = suggested.get(picks.get(slot, slot), colors)
        write(PROJ / f"project/palettes/sprite_{slot}.gbsres", {
            "_resourceType": "palette", "id": palette_id(slot), "name": f"Sprite: {slot}",
            "colors": [light, mid, mid, dark],
        })

    write(PROJ / "project/variables.gbsres", {
        "_resourceType": "variables",
        "variables": [{"id": V[n], "name": n, "symbol": f"var_{n}"} for n in VARS],
        "constants": [],
    })

    settings = json.loads((PROJ / "project/settings.gbsres").read_text())
    settings.update({
        "startSceneId": scene_id("cubicle"),
        "startX": STORY["cubicle"]["markers"]["bufo_start"][0] * 2,
        "startY": STORY["cubicle"]["markers"]["bufo_start"][1] * 2,  # feet touch the phone above
        "startDirection": "up",
        "colorMode": "color",
        "defaultPlayerSprites": {k: SPRITES["bufo"]["id"] for k in settings["defaultPlayerSprites"]},
        "defaultSpritePaletteIds": [palette_id(s) for s in SLOTS],
        "defaultSpritePaletteId": palette_id("bufo"),
        "romFilename": "bufos_workday",
        "openBuildFolderOnExport": False,
    })
    write(PROJ / "project/settings.gbsres", settings)

    rooms = {**build_story(), **build_rooms(), **build_level2()}

    # Playtesting: BUFO_START=room,x,y starts elsewhere; BUFO_ITEMS=has_cable,... grants items.
    start = os.environ.get("BUFO_START")
    if start:
        room, x, y = start.split(",")
        settings.update({"startSceneId": scene_id(room), "startX": int(x), "startY": int(y)})
        write(PROJ / "project/settings.gbsres", settings)
        items = [i for i in os.environ.get("BUFO_ITEMS", "").split(",") if i]
        hp = int(os.environ.get("BUFO_HP", "3"))
        rooms[room].init[:0] = [set_var(V["game_started"], True), set_var(V["bufo_hp"], hp),
                                set_var(V["bufo_max_hp"], int(os.environ.get("BUFO_MAX_HP", min(hp, 4)))),
                                *hud_update(room),
                                *[set_var(V[i], True) for i in items]]
        print(f"Playtest build: starting in {room} at {x},{y} with {items or 'no items'}")

    for i, room in enumerate(rooms.values()):
        write_room(room, i)

    print(f"Wrote {PROJ} with {len(rooms)} scenes, {len(SPRITES)} sprites, {len(VARS)} variables")


if __name__ == "__main__":
    main()
