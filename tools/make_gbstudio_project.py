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

# Floors 3-6, if their art exists yet: key -> module.
FLOOR_FILES = {"office": ("make_open_office.py", "open_office"), "hr": ("make_hr.py", "hr"),
               "server": ("make_server_room.py", "server_room"), "exec": ("make_exec_floor.py", "exec_floor")}
FLOORS = {}
for _key, (_file, _folder) in FLOOR_FILES.items():
    if (ROOT / "tools" / _file).exists():
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        _spec = importlib.util.spec_from_file_location(_key, ROOT / "tools" / _file)
        _mod = importlib.util.module_from_spec(_spec)
        try:
            _spec.loader.exec_module(_mod)
        except Exception as exc:  # art still being drawn: build without this floor
            print(f"Skipping {_file}: {exc}")
            continue
        if all((ROOT / "assets/backgrounds" / f"{_key}_{room}.png").exists() for room in _mod.ROOMS):
            FLOORS[_key] = _mod

# room name -> (level module, background file prefix, scene folder)
LEVELS = {name: (basement, "basement", "basement") for name in basement.ROOMS}
if breakroom:
    LEVELS.update({name: (breakroom, "break", "break_room") for name in breakroom.ROOMS})
for _key, _mod in FLOORS.items():
    LEVELS.update({name: (_mod, _key, FLOOR_FILES[_key][1]) for name in _mod.ROOMS})
# Where each level's scenes sit on GB Studio's world map.
LEVEL_OFFSET = {"basement": (0, 0), "break_room": (4, 5), "open_office": (8, 5), "hr": (12, 5),
                "server_room": (16, 5), "exec_floor": (20, 5)}
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
                           "break_room_theme", "espresso_boss_theme", "open_office_theme", "hr_theme",
                           "server_room_theme", "final_boss_theme", "ending_theme"]
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
    # Floors 3-6 and the ending
    "office_intro", "hr_intro", "server_intro", "exec_intro", "meeting_talked", "hr_talked",
    "has_headphones", "has_invite", "boss3_door_open", "storm_hp", "storm_low", "storm_defeated",
    "storm_intro_done", "storm_phase2",
    "has_keycard", "has_folder", "boss4_door_open", "hydra_heads", "hydra_defeated", "hydra_intro_done",
    "head_a_open", "head_b_open", "head_c_open",
    "server_panel_broken", "has_note5", "kevin_met", "has_kevin", "exec_hacked",
    "has_board_invite", "boss6_door_open", "board_stage", "board_vuln", "board_intro_done", "board_defeated",
    "elevator_pick", "keycard_used", "align_wait",
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
    # Floor 3
    "bullpen": {"enemy": "quick_sync"}, "quiet_room": {"enemy": "quick_sync"},
    "meeting_room": {"npc": "standup_frog"}, "standup_corridor": {"npc": "standup_frog"},
    "conference": {"printer": "reply_storm", "enemy": "mini_storm"},
    # Floor 4
    "hr_reception": {"npc": "hr_frog"}, "personnel_files": {"enemy": "red_tape"},
    "training_room": {"enemy": "red_tape"}, "compliance_room": {"printer": "hydra_body", "cable": "binder_head"},
    # Floor 5
    "cold_aisle": {"enemy": "firewall", "cable": "cracked_wall"}, "cable_vault": {"cable": "cracked_wall"},
    "kevin_core": {"printer": "kevin"},
    # Floor 6
    "exec_hall": {"enemy": "yes_man"},
    "boardroom": {"cable": "board_cfo", "gold": "board_cmo", "npc": "brock_seated", "printer": "spreadsheet"},
    "ending_cubicle": {"npc": "ceo"},
}
# Fallback colors for those palettes if the sprite artist didn't suggest any.
EXTRA_PALETTES = {
    "sugar_ant": ("F0C8A0", "B03020", "281010"),
    "tupperware": ("E0F0C0", "88A848", "203018"),
    "espresso": ("F0F0F0", "D04030", "202028"),
    "cracked_wall": ("E8DCC0", "A89878", "403020"),
    "coffee_happy": ("E8E0A0", "7AA860", "1C2A1C"),
    "receptionist": ("E8E0A0", "7AA860", "1C2A1C"),
    "quick_sync": ("F0E8C8", "5888C8", "1C2030"), "standup_frog": ("E8E0A0", "7AA860", "1C2A1C"),
    "reply_storm": ("E8F0FF", "6070A0", "181C30"), "mini_storm": ("E8F0FF", "6070A0", "181C30"),
    "hr_frog": ("F8E0E8", "7AA860", "2A1C24"), "red_tape": ("F8D0D0", "D02828", "300808"),
    "hydra_body": ("F0E8D0", "B8A070", "302818"), "binder_head": ("F0F0F0", "3070C0", "101828"),
    "kevin": ("D8FFE0", "40B060", "102018"), "firewall": ("FFE080", "E05020", "301008"),
    "yes_man": ("E0E0E8", "404858", "101018"), "board_cfo": ("F0E0C8", "6A9A50", "181C20"),
    "spreadsheet": ("FFFFFF", "40A040", "102010"), "board_cmo": ("FF9AD0", "6B9B4B", "1C1424"),
    "brock_seated": ("FFD84A", "6A9A50", "1C2418"),
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
    # Floor 3
    "quick_sync": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    "standup_frog": ("npc", 16, 16, "fixed", {"": [0, 1]}),
    "email": ("printer", 16, 16, "fixed", {"": [0]}),
    "reply_storm": ("printer", 32, 32, "fixed", {"": [0], "Sending": [1], "Low": [2]}),
    "mini_storm": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    # Floor 4
    "hr_frog": ("npc", 16, 16, "fixed", {"": [0, 1]}),
    "red_tape": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    "hydra_body": ("printer", 32, 32, "fixed", {"": [0], "Hurt": [1]}),
    "binder_head": ("cable", 16, 16, "fixed", {"": [0], "Angry": [1], "Open": [2]}),
    "policy_doc": ("printer", 16, 16, "fixed", {"": [0]}),
    # Floor 5
    "kevin": ("printer", 32, 32, "fixed", {"": [0], "Talking": [1], "Happy": [2]}),
    "firewall": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    # Floor 6 and the ending
    "yes_man": ("enemy", 16, 16, "fixed", {"": [0, 1]}),
    "board_cfo": ("cable", 16, 16, "fixed", {"": [0], "Attack": [1], "Flustered": [2]}),
    "board_cmo": ("gold", 16, 16, "fixed", {"": [0], "Attack": [1], "Flustered": [2]}),
    "board_coo": ("cable", 16, 16, "fixed", {"": [0], "Attack": [1], "Flustered": [2]}),
    "board_cto": ("cable", 16, 16, "fixed", {"": [0], "Attack": [1], "Flustered": [2]}),
    "brock_seated": ("npc", 16, 16, "fixed", {"": [0], "Attack": [1], "Flustered": [2]}),
    "spreadsheet": ("printer", 16, 16, "fixed", {"": [0]}),
    "hole": ("enemy", 16, 16, "fixed", {"": [0], "Open": [1]}),
    "staff_frog": ("gold", 16, 16, "fixed", {"": [0, 1]}),
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
    rows = rows if rows is not None else room_rows(room)
    tiles = tiles if tiles is not None else LEVELS[room][0].TILES
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


DPAD = ("left", "right", "up", "down")


def hold_dpad():
    """Swallow D-pad presses (an override input script with nothing in it) so Bufo stays put."""
    return [ev("EVENT_SET_INPUT_SCRIPT", {"input": list(DPAD), "override": True, "__collapse": False},
               true=[ev("EVENT_WAIT", {"time": num(0.02), "frames": num(1), "units": "frames"})])]


def release_dpad():
    return [remove_input(b) for b in DPAD]


def finish_step():
    """Wait (up to 16 frames) for Bufo to finish his current step and stand on the 8 px grid.

    Bufo keeps walking until he reaches the grid. A tongue launched mid-step gets walked into, and the
    engine's hit test finds Bufo before the enemy, so the lick misses. A scripted move started mid-step
    can get stuck. Snapping him instead could push him into a wall he was walking away from.
    """
    pos = ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                          "vectorY": V["lick_y"], "units": "pixels"})
    off_grid = OR({"type": "ne", "valueA": {"type": "mod", "valueA": var(V["lick_x"]), "valueB": num(8)},
                   "valueB": num(0)},
                  {"type": "ne", "valueA": {"type": "mod", "valueA": var(V["lick_y"]), "valueB": num(8)},
                   "valueB": num(0)})
    return [
        set_var(V["align_wait"], 0), pos,
        ev("EVENT_LOOP_WHILE", {"condition": AND(off_grid, cmp("lt", V["align_wait"], 16))}, true=[
            ev("EVENT_WAIT", {"time": num(0.02), "frames": num(1), "units": "frames"}),
            inc(V["align_wait"]), pos,
        ]),
    ]


def tongue_controls(room):
    # The tongue doesn't fly: it pops out in front of Bufo, holds, and retracts (half, full, full, half).
    # It hits enemies (group 1). Props can't be both talkable and hittable, so licking a prop is
    # checked here from Bufo's tile and facing direction instead.
    checks = []
    for mx, my, lines in reversed(lickables(room)):
        checks = [if_expr(facing(mx, my), text(*lines), checks)]
    # No licking mid-dash: the lick's D-pad release would cut the dash's hold short.
    return input_script("b", [if_var(V["dashing"], [], [
        ev("EVENT_RATE_LIMIT", {"variable": V["tongue_cooldown"], "time": num(0.35), "frames": num(20),
                                "units": "time"},
           true=[
               # Bufo stands still to lick: finish his step, then hold the D-pad while the tongue is out.
               *hold_dpad(), *finish_step(),
               sound("beep", 6, 0.05),
               projectile("tongue", "player", group="2", mask=("1",), speed=0, life=0.25, offset=16,
                          anim_speed=3, loop=False),
               ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                               "vectorY": V["lick_y"], "units": "tiles"}),
               ev("EVENT_ACTOR_GET_DIRECTION", {"actorId": "player", "direction": V["lick_dir"]}),
               wait(0.25), *release_dpad(),
               *checks,
           ]),
    ])])


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
        ("Printer", 3, level1, ("printer_room", 9, 14)),
    ]
    level2_done = level2 + ["espresso_defeated", "office_intro"]
    level3_done = level2_done + ["has_headphones", "has_invite", "boss3_door_open", "storm_defeated", "hr_intro"]
    level4_done = level3_done + ["has_keycard", "keycard_used", "has_folder", "boss4_door_open", "hydra_defeated",
                                 "server_intro", "hr_talked"]
    level5_done = level4_done + ["kevin_met", "has_kevin", "exec_hacked", "exec_intro"]
    if breakroom:
        chapters += [("Floor 2", 4, level1_done, ("elevator_landing", 9, 14)),
                     ("Espresso", 4, level2, ("espresso_room", 9, 14))]
    if landing_exists("office_landing"):
        chapters.append(("Floor 3", 5, level2_done, ("office_landing", 9, 14)))
    if landing_exists("hr_landing"):
        chapters.append(("Floor 4", 5, level3_done, ("hr_landing", 9, 14)))
    if landing_exists("server_landing"):
        chapters.append(("Floor 5", 5, level4_done, ("server_landing", 9, 14)))
    if landing_exists("exec_landing"):
        chapters.append(("Floor 6", 5, level5_done, ("exec_landing", 9, 14)))
    picks = []
    for i, (label, hp, flags, (room, x, y)) in enumerate(chapters, start=1):
        picks.append(if_expr(EQ(V["menu_pick"], i), [*chapter_setup(hp, flags), switch_scene(room, x, y, "up")]))
    menu = lambda var_name, options: ev("EVENT_MENU", {
        "variable": V[var_name], "items": len(options), "cancelOnLastOption": False, "cancelOnB": True,
        "layout": "menu" if len(options) > 4 else "dialogue", **{f"option{i + 1}": o for i, o in enumerate(options)}})
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
            *text("Pondcorp HQ.\nFloor 3. 8:58 AM.", "*RING RING*", "(Press A facing\nthe phone to\nanswer it.)",
                  "(Press START to\nskip the intro.)"),
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
    # Start skips the opening and goes straight to the title card.
    skip = input_script("start", [
        set_var(V["game_started"], True), set_var(V["phone_answered"], True), set_var(V["ceo_met"], True),
        set_var(V["bufo_max_hp"], START_HP), set_var(V["bufo_hp"], START_HP),
        switch_scene("title", 0, 0, "down"),
    ])
    for r in (cub, office):
        r.init.insert(1, tongue_controls(r.name))
        r.init.insert(1, skip)
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

# Floor 3 and 4 props.
LEVEL2_PROPS.update({
    "office_landing": [
        (3, 0, ["FLOOR 3: OPEN\nPLAN.", "Open to\ninterruptions."], None),
        (1, 1, ["A plant. Plastic.\nThriving."], None),
        (1, 6, (["Sparkling water.", "Bufo drinks.\nCoffee refilled.\nIt tingles."], "heal"), ["Fizzy."]),
        (7, 0, ["A poster: a man on\na mountain. WIN.", "Win what? It\ndoesn't say."], None),
    ],
    "bullpen": [
        (2, 2, ["An identical desk.", "There are 200 of\nthem. All the same."], ["Tastes like\nergonomics."]),
        (7, 6, ["Another identical\ndesk.", "Someone named it\n'Gary'."], None),
        (8, 0, ["FLOOR 3."], None),
        (3, 0, ["HUSTLE.", "Somebody wrote\nunder it: (sleep)."], None),
        (8, 7, ["The trash. Full of\nempty energy\ndrinks."], None),
    ],
    "meeting_room": [
        (2, 0, ["A whiteboard full of\narrows.", "They all point at\nother arrows."], None),
        (3, 4, ["The meeting table.\nThe meeting has\nbeen going since\nMonday."], None),
        (4, 3, ["An empty chair.\nFor someone who\nescaped."], None),
        (6, 0, ["WIN.", "Another one."], None),
        (1, 7, ["A plant. It has\nattended every\nmeeting."], None),
    ],
    "quiet_room": [
        (3, 0, ["SHHHH.", "The sign is very\nloud about it."], None),
        (1, 2, ["A phone booth.\nSomeone is crying\nin it. Softly."], None),
        (3, 4, ["A red beanbag.\nBufo sinks in.\nBufo gets out."], ["Vinyl."]),
        (6, 4, ["A teal beanbag.\nIt's warm. Why is\nit warm."], None),
    ],
    "standup_corridor": [
        (2, 0, ["A kanban board.\nEverything is in\n'BLOCKED'."], None),
        (7, 0, ["The standup timer:\n9:59.", "It has said 9:59\nfor hours."], None),
        (1, 1, ["A plant. It has\nheard every update."], None),
        (8, 1, ["The trash. It's\nfull of sticky\nnotes."], None),
    ],
    "scheduling": [
        (3, 0, ["THE BIG CALENDAR.", "Every day at 4:30:\nFINAL 1:1.", "Every. Single.\nDay.",
                "Bufo: (Maybe it's\na party.)"], None),
        (1, 0, ["A small calendar.\nIt's from 2014."], None),
        (2, 2, ["A fax machine.\nIt's faxing itself."], ["Toner. Ugh."]),
        (4, 4, ["The scheduler's\ndesk. 400 meeting\ninvites, unsent."], None),
        (8, 6, (["Sparkling water.", "Coffee refilled.\nSomehow."], "heal"), None),
    ],
    "conference": [
        (4, 0, ["The projector\nscreen. It says:\nRE: RE: RE:"], None),
        (1, 0, ["HUSTLE."], None),
        (8, 0, ["WIN."], None),
        (1, 3, ["Chairs pushed to\nthe wall. Nobody\nwanted to sit."], None),
    ],
    "hr_landing": [
        (2, 0, ["WE CARE.", "(LEGALLY)"], None),
        (7, 0, ["A framed policy:\nSMILING IS\nMANDATORY."], None),
        (1, 1, ["A friendly plant.\nToo friendly."], None),
        (2, 6, ["A waiting couch.\nIt sighs when Bufo\nsits."], None),
    ],
    "hr_reception": [
        (1, 1, (["The tea station.", "Bufo makes tea.\nCoffee refilled.\nIt's tea."], "heal"), ["Chamomile."]),
        (3, 4, ["The reception desk.\nA bowl of mints.\nAll gone."], None),
        (3, 0, ["HUMAN RESOURCES.", "Bufo is a frog.\nIs he a human\nresource?"], None),
        (1, 6, ["A couch. For\nwaiting. For\nnews."], None),
        (8, 1, ["A plant. It's\nlistening."], None),
    ],
    "personnel_files": [
        (3, 0, ["FILES A-Z.", "Bufo checks B.\nHis file is very\nthin."], None),
        (4, 1, ["A filing cabinet.\nLabeled: 'TBD'."], None),
        (7, 6, ["A cabinet: BUFO.", "Inside: one sheet.\n'Concerned. Fine.'"], None),
        (2, 5, ["A locked cabinet:\nLILYPAD - DO NOT\nOPEN."], ["Locked. Lickably."]),
    ],
    "training_room": [
        (2, 0, ["MANDATORY TRAINING:\nCOMPLETE BY\nYESTERDAY."], None),
        (6, 0, ["The training video:\n'Synergy and You,\nPart 47.'"], None),
        (2, 3, ["A front-row chair.\nNobody sits here."], None),
        (7, 7, ["A back-row chair.\nEveryone sits\nhere."], None),
    ],
    "complaints": [
        (3, 0, ["YOUR VOICE\nMATTERS!", "(Please submit in\nwriting. In\nsilence.)"], None),
        (1, 1, ["The suggestion box.\nOverflowing.", "Top suggestion:\n'Real coffee.'"], None),
        (4, 3, ["An empty desk.\nThe complaints\ndepartment is\none frog. Gone."], None),
        (5, 2, ["An empty chair."], None),
        (1, 5, ["A shredder. It's\nfull of\ncomplaints."], ["Paper. Sad paper."]),
    ],
    "policy_hall": [
        (2, 0, ["A wall of policies.", "Policy 1: Read\nall policies."], None),
        (2, 2, ["POLICY: No fun on\nweekdays."], None),
        (7, 4, ["POLICY: Weekends\nare weekdays."], None),
        (2, 6, ["POLICY: This\npolicy is\nconfidential."], None),
        (1, 1, ["A plant. It's\ncompliant."], None),
    ],
    "compliance_room": [
        (4, 0, ["COMPLY."], None),
        (3, 0, ["A framed policy:\nAll fights must\nbe pre-approved."], None),
        (2, 1, ["A tower of files.\nIt sways."], None),
        (7, 1, ["Another tower of\nfiles. It sways\nthe other way."], None),
    ],
})

# Floor 5 and 6 props.
LEVEL2_PROPS.update({
    "server_landing": [
        (2, 0, ["RESTRICTED."], None),
        (7, 0, ["AUTHORIZED AI ONLY.", "Bufo is not an AI.\nBufo goes in\nanyway."], None),
        (1, 2, ["A lonely server\nrack. It hums to\nitself."], ["Warm. Lonely."]),
        (1, 6, ["A fire suppression\ntank. Please do\nnot suppress."], None),
    ],
    "cold_aisle": [
        (3, 0, ["COLD AISLE.", "Bufo's tongue may\nfreeze to things."], None),
        (2, 2, ["A server. It runs\nthe coffee order\nsystem. Decaf."], None),
        (7, 2, ["A blinking rack.\nBlink. Blink.\nIt's waving?"], ["Bufo licks it. It\nblinks faster."]),
        (2, 6, ["A label: KEVIN\n(DO NOT UNPLUG).", "Someone crossed out\n'NOT'. Then wrote\nit back."], None),
        (6, 0, ["A thermostat: 12C.", "Someone put a\nsticky note on it:\n'Brrr.'"], None),
    ],
    "ups_room": [
        (1, 0, ["EMERGENCY POWER\nSWITCH.", "Bufo does not\ntouch it."], ["Bufo licks it.\nNothing happens.\nPhew."]),
        (6, 6, (["A coffee maker.\nIt WORKS.", "REAL coffee.\nBufo is overcome.\nCoffee refilled."], "heal"),
         ["Real coffee.\nBufo weeps."]),
        (5, 0, ["UPS STATUS: OK.", "The only thing on\nthis floor that's\nOK."], None),
        (3, 2, ["A bank of\nbatteries. They're\nall at 100%."], None),
        (8, 0, ["Another\nthermostat. Also\nfreezing."], None),
    ],
    "cable_vault": [
        (3, 2, ["A cable knot.\nIt's untangling\nitself. Slowly."], None),
        (8, 1, ["A spool of cable.\nCat5. Of course."], None),
        (4, 0, ["A cable tray,\nsagging with\ndecades of cable."], None),
        (7, 3, ["A GIANT cable knot.", "Somewhere inside: a\nmouse. A real one."], ["Squeak."]),
    ],
    "kevin_core": [
        (3, 0, ["A wall of monitors.\nThey all show the\nsame smile."], None),
        (4, 1, ["KEVIN's console.\nA sticky note:\n'Be kind. -K'"], None),
        (2, 1, ["A coolant column.\nBubbling gently."], None),
        (7, 1, ["Another coolant\ncolumn. It bubbles\nin harmony."], None),
    ],
    "exec_landing": [
        (2, 0, ["EXECUTIVES ONLY."], None),
        (7, 0, ["A gilded mirror.\nBufo looks...\nconcerned."], ["Smudged now."]),
        (1, 1, ["A potted palm.\nReal. Expensive.\nSmug."], None),
        (1, 3, ["A velvet bench.\nToo nice to sit on."], None),
    ],
    "exec_hall": [
        (1, 0, ["A portrait of a\nyacht. Brock's\nthird."], None),
        (3, 0, ["A portrait of a\ngolf course. Brock\nowns it."], None),
        (6, 0, ["A portrait of a\nstock chart. Only\ngoes up."], None),
        (8, 0, ["A portrait of\nmoney. Just\nmoney."], None),
        (2, 1, ["A bust. No face.\nThe sculptor quit."], None),
        (8, 7, ["Another faceless\nbust. Same\nsculptor. Same\nreason."], None),
    ],
    "exec_lounge": [
        (3, 3, (["A champagne\nfountain.", "It's sparkling\nwater. Coffee\nrefilled anyway."], "heal"), ["Bubbly."]),
        (8, 1, ["A leather armchair.\nIt costs more than\nBufo."], None),
        (1, 1, ["A cigar humidor.\nBufo coughs just\nlooking at it."], None),
        (6, 6, ["Another putting\ngreen. Golf is\nwork, apparently."], None),
        (2, 0, ["A stock ticker:\nPONDCORP: UP.\nMORALE: DOWN."], None),
        (6, 0, ["VIP.", "Very Important\nPondcorp-person."], None),
    ],
    "brock_suite": [
        (1, 0, ["Self-help books:", "'Synergy for One'.\n'Think Bigger'.\n'Think Bigger 2'."], None),
        (2, 1, ["A gold throne.\nThere's a\ncushion on it\nthat says BOSS."], None),
        (5, 0, ["A vault.", "Through the\nkeyhole: lily\npads. Gold ones."], None),
        (2, 2, ["Brock's desk. A\nphoto: Brock with\nBrock."], None),
        (7, 2, ["A gold silk bed.\nIn the office."], None),
        (1, 7, ["A gold statue of\nBrock. Lifesize.\nPlus 20%."], None),
    ],
    "board_antechamber": [
        (1, 2, ["A pompous gong.", "Bufo gongs it.\nBONNNG.", "Nobody comes."], ["BONG."]),
        (3, 4, ["A velvet rope.\nFor keeping out\nfrogs like Bufo."], None),
        (7, 0, ["PLEASE WAIT.", "(Forever.)"], None),
        (8, 6, ["A waiting chair.\nStill warm from the\nlast employee."], None),
    ],
    "boardroom": [
        (2, 3, ["The boardroom\ntable. Longer than\nthe basement."], None),
        (5, 3, ["A gavel. For\nsmashing ideas."], None),
        (7, 3, ["The quarterly\nreport. In gold\nleaf. It's blank."], None),
    ],
})

# Breakable cracked walls: (room, metatile x, metatile y). They block a doorway until Bufo dashes into them.
# (room, metatile x, metatile y, the variable that remembers it's broken)
CRACKED = [("vending_alley", 4, 0, "wall_broken"), ("vending_alley", 5, 0, "wall_broken"),
           ("pantry", 4, 8, "wall_broken"), ("pantry", 5, 8, "wall_broken")]
for _room, (_mod, _prefix, _folder) in LEVELS.items():
    if _prefix == "server":
        for _my, _row in enumerate(_mod.ROOMS[_room][3].strip().splitlines()):
            for _mx, _ch in enumerate(_row):
                if _ch == "w":
                    CRACKED.append((_room, _mx, _my, "server_panel_broken"))


def dash_controls(room, boss_hit=None):
    """Select: if Bufo has the Coffee Mug, dash 5 tiles forward. Then check what he slammed into."""
    walls = [(i, mx, my, v) for i, (r, mx, my, v) in enumerate(CRACKED) if r == room]
    after = []
    for i, mx, my, v in walls:
        after.append(if_expr(facing(mx, my, slack=1), [
            if_var(V[v], [], [
                shake(0.4, 4), sound("crash", 2, 0.4),
                *[deactivate(uid("actor", r, f"cracked_{j}")) for j, (r, _, _, vv) in enumerate(CRACKED)
                  if r == room and vv == v],
                set_var(V[v], True),
                *text("CRASH! It crumbles."),
            ]),
        ]))
    if boss_hit:
        after.append(boss_hit)
    move = {0: (0, 8, "vertical"), 1: (8, 0, "horizontal"), 2: (0, -8, "vertical"), 3: (-8, 0, "horizontal")}
    moves = []
    for d in (3, 2, 1, 0):
        dx, dy, mtype = move[d]
        moves = [if_expr(EQ(V["lick_dir"], d), [move_rel("player", dx, dy, mtype)], moves)]

    # A dash that stops against an actor (an enemy, a boss) can leave Bufo between tiles, and Bufo can't
    # walk from there. Snap him back onto the 8 px grid, toward where he dashed from (he's been there).
    def grid(v, back):
        val = {"type": "add", "valueA": var(v), "valueB": num(7)} if back else var(v)
        return {"type": "mul", "valueA": {"type": "div", "valueA": val, "valueB": num(8)}, "valueB": num(8)}
    snap = []
    for back in (False, True):
        snap.append(ev("EVENT_ACTOR_SET_POSITION", {"actorId": "player", "x": grid(V["lick_x"], back),
                                                    "y": grid(V["lick_y"], back), "units": "pixels"}))
    snap = [ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                            "vectorY": V["lick_y"], "units": "pixels"}),
            # Dashing left or up, "back" is right or down: round up. Otherwise round down.
            if_expr(OR(EQ(V["lick_dir"], 2), EQ(V["lick_dir"], 3)), [snap[1]], [snap[0]])]
    return ev("EVENT_GROUP", {}, true=[set_var(V["dashing"], False), input_script("select", [
        if_var(V["has_mug"], [
            ev("EVENT_RATE_LIMIT", {"variable": V["dash_cooldown"], "time": num(0.6), "frames": num(36),
                                    "units": "time"}, true=[
                ev("EVENT_ACTOR_GET_DIRECTION", {"actorId": "player", "direction": V["lick_dir"]}),
                # Hold the D-pad for the whole dash: holding the opposite direction fought the scripted
                # move so it never finished, and Bufo stayed stuck in his dash.
                *hold_dpad(), *finish_step(),
                ev("EVENT_ACTOR_SET_SPRITE", {"actorId": "player", "spriteSheetId": SPRITES["bufo_dash"]["id"]}),
                ev("EVENT_ACTOR_SET_MOVEMENT_SPEED", {"actorId": "player", "speed": 4}),
                set_var(V["dashing"], True),  # Bufo can't be hurt while dashing (or ramming a boss)
                sound("noise", 6, 0.15),
                *moves,
                *snap,
                *release_dpad(),
                ev("EVENT_ACTOR_SET_MOVEMENT_SPEED", {"actorId": "player", "speed": 1}),
                ev("EVENT_ACTOR_SET_SPRITE", {"actorId": "player", "spriteSheetId": SPRITES["bufo"]["id"]}),
                ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["lick_x"],
                                                "vectorY": V["lick_y"], "units": "tiles"}),
                *after,
                wait(0.3),
                set_var(V["dashing"], False),
            ]),
        ]),
    ])])


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
        *elevator_script("lobby"), move_to("player", ex * 2 + 1, ey * 2 + 3, "vertical")])
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
    for i, (r, mx, my, v) in enumerate(CRACKED):
        if r not in rooms:
            continue
        cid = uid("actor", r, f"cracked_{i}")
        x, y = at(mx, my)
        rooms[r].actor(f"cracked_{i}", "cracked_wall", x, y, name="Cracked wall",
                       start=[if_var(V[v], [deactivate(cid)])],
                       script=text("A cracked wall.\nIt looks flimsy.", "(With enough speed,\nBufo could break\nit.)"))

    # Floor 2 landing: the elevator back down.
    r = rooms["elevator_landing"]
    ex, ey = find_marker("elevator_landing", "E")
    r.trigger("elevator", ex * 2, ey * 2 + 1, 4, 1, [
        *elevator_script("elevator_landing"), move_to("player", 9, 13, "vertical")])
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
        *(text("11:45 AM.", "Floor 3 is open.\nTake the elevator.") if "office" in FLOORS
          else text("11:45 AM.\nTo be continued...")),
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



# --- Floors 3-6, the elevator, and the ending ----------------------------------

ELEVATOR = [  # label, landing room, unlock variable, what's needed
    ("Lobby", "lobby", None, ""),
    ("Floor 2", "elevator_landing", "printer_defeated", "Beat the printer\nin the basement."),
    ("Floor 3", "office_landing", "espresso_defeated", "Floor 2's espresso\nmachine first."),
    ("Floor 4", "hr_landing", "storm_defeated", "Floor 3 first. HR\nis always last."),
    ("Floor 5", "server_landing", "hydra_defeated", "Floor 4 first.\nCompliance!"),
    ("Floor 6", "exec_landing", "has_kevin", "EXECUTIVES ONLY.\n(Bufo needs help.)"),
]


LANDING_FLOOR = {"office_landing": "office", "hr_landing": "hr", "server_landing": "server", "exec_landing": "exec"}


def landing_exists(room):
    if room in ("lobby", "elevator_landing"):
        return bool(breakroom)
    key = LANDING_FLOOR[room]
    return key in FLOORS and all(s in SPRITE_DEFS for s in FLOOR_SPRITES[key])


def elevator_script(here):
    """The elevator menu. Locked floors explain what's needed."""
    floors = [f for f in ELEVATOR if landing_exists(f[1])]
    picks = []
    for i, (label, room, unlock, why) in enumerate(floors, start=1):
        if room == here:
            go = text("Bufo is already\non this floor.")
        elif room == "lobby":
            mx, my = breakroom.LOBBY_MARKERS["elevator"]
            go = [switch_scene("lobby", mx * 2 + 1, my * 2 + 3, "down")]
        else:
            go = [switch_scene(room, 9, 14, "up")]
        if unlock == "has_kevin" and room != here:
            go = [if_var(V["exec_hacked"], go, [
                *text("EXECUTIVES ONLY.", "KEVIN: ALLOW ME.", "*beep boop*",
                      "ACCESS GRANTED.\nWELCOME, EXECUTIVE\nKEVIN."),
                set_var(V["exec_hacked"], True), *go])]
        if unlock:
            go = [if_var(V[unlock], go, text("That floor is\nlocked.", why))]
        picks.append(if_expr(EQ(V["elevator_pick"], i), go))
    return [
        *text("ELEVATOR."),
        # Sprites draw over the menu, so hide Bufo while it's open.
        ev("EVENT_ACTOR_HIDE", {"actorId": "player"}),
        ev("EVENT_MENU", {"variable": V["elevator_pick"], "items": len(floors), "cancelOnLastOption": False,
                          "cancelOnB": True, "layout": "menu" if len(floors) > 4 else "dialogue",
                          **{f"option{i + 1}": f[0] for i, f in enumerate(floors)}}),
        ev("EVENT_ACTOR_SHOW", {"actorId": "player"}),
        *picks,
    ]


# Upper-floor boss doors: room with the 'B' door -> (open var, key var, locked lines, open lines)
BOSS_DOORS = {
    "standup_corridor": ("boss3_door_open", "has_invite",
                         ["MEETING IN PROGRESS.\nINVITE REQUIRED.", "(Someone in\nScheduling sends the\ninvites.)"],
                         ["Bufo shows the\ninvite.", "He's marked as\n'Tentative'.", "Good enough."]),
    "policy_hall": ("boss4_door_open", "has_folder",
                    ["ALL VISITS REQUIRE\nAPPROVAL.", "(An APPROVED stamp\nwould do it.)"],
                    ["Bufo stamps his own\nforehead.", "APPROVED."]),
    "board_antechamber": ("boss6_door_open", "has_board_invite",
                          ["BOARD MEETING.\nMEMBERS ONLY.", "(Brock's suite\nmust have an\ninvite.)"],
                          ["Bufo shows the\nboard invite.", "KEVIN: I FORGED\nTHE SIGNATURE.", "KEVIN: I AM SORRY.\nNOT VERY SORRY."]),
}
# Boss rooms seal until their boss is beaten.
SEALED = {"conference": ("storm_defeated", "Emails pile up\nagainst the door."),
          "compliance_room": ("hydra_defeated", "Red tape seals\nthe door."),
          "boardroom": ("board_defeated", "Security locks\nthe door.")}


def floor_door(room, side, target, ch):
    ax, ay, adir = ARRIVE[OPPOSITE[side]]
    go = [switch_scene(target, ax, ay, adir)]
    back = {"north": (10, 3, "vertical"), "south": (9, 13, "vertical"), "west": (3, 9, "horizontal"),
            "east": (15, 9, "horizontal")}[side]
    if ch == "B" and room in BOSS_DOORS:
        open_v, key_v, locked, opened = BOSS_DOORS[room]
        return [if_var(V[open_v], go, [
            if_var(V[key_v], [*text(*opened), set_var(V[open_v], True), *go],
                   [*text(*locked), move_to("player", back[0], back[1], back[2])]),
        ])]
    if ch == "k":
        return [if_var(V["has_keycard"], [
            if_var(V["keycard_used"], [], [*text("Bufo swipes the\nkeycard. *beep*"), set_var(V["keycard_used"], True)]),
            *go,
        ], [*text("A card reader.\nIt blinks red.", "(Bufo needs a\nkeycard.)"), move_to("player", back[0], back[1], back[2])])]
    if room in SEALED:
        var_name, line = SEALED[room]
        return [if_var(V[var_name], go, [*text(line, "There's no way out\nbut through."),
                                        move_to("player", 9, 13, "vertical")])]
    return go


def setup_floor(key, theme, start_flags, max_hp):
    """Doors, props, HUD, music, licks and dashes for every room on one floor."""
    mod = FLOORS[key]
    rooms = {name: Room(name) for name in mod.ROOMS}
    for name, room in rooms.items():
        for side, (target, ch) in neighbours(name).items():
            tx, ty, tw, th = DOOR_TRIGGER[side]
            room.trigger(f"door_{side}", tx, ty, tw, th, floor_door(name, side, target, ch))
        hint = {tuple(p["pos"]): p["name"] for p in getattr(mod, "PROPS_HINT", {}).get(name, [])}
        if name not in LEVEL2_PROPS:  # props without written jokes still say what they are
            LEVEL2_PROPS[name] = [(mx, my, [n.replace("_", " ").capitalize() + "."], None)
                                  for (mx, my), n in hint.items()]
        level2_props(room)
        room.actor("hud", "hud_coffee", 0, 1, name="Coffee", pinned=True, solid=False, start=hud_update(name))
        if name not in SEALED:
            room.init.append(music(theme))
        room.init.insert(0, if_var(V["game_started"], [], [
            set_var(V["game_started"], True), *[set_var(V[f], True) for f in start_flags],
            set_var(V["bufo_max_hp"], max(START_HP, max_hp)), set_var(V["bufo_hp"], max(START_HP, max_hp)),
            *hud_update(name),
        ]))
        rows = room_rows(name)
        for my, row in enumerate(rows):
            for mx, ch in enumerate(row):
                if ch == "E":
                    room.trigger("elevator", mx * 2, my * 2 + 1, 2, 1, [
                        *elevator_script(name), move_to("player", 9, 13, "vertical")])
    return rooms


def cracked_for(room):
    return [(i, mx, my, v) for i, (r, mx, my, v) in enumerate(CRACKED) if r == room]


def finish_floor(rooms, boss_room=None, boss_hit=None):
    for name, room in rooms.items():
        for i, mx, my, v in cracked_for(name):
            cid = uid("actor", name, f"cracked_{i}")
            x, y = at(mx, my)
            room.actor(f"cracked_{i}", "cracked_wall", x, y, name="Cracked panel",
                       start=[if_var(V[v], [deactivate(cid)])],
                       script=text("A cracked panel.\nIt looks flimsy.", "(Dash into it!)"))
        room.init.insert(1, tongue_controls(name))
        room.init.append(dash_controls(name, boss_hit=boss_hit if name == boss_room else None))
    return rooms


def chase_enemy(room, key, sprite, mx, my, flag=None, pause=0.9, speed=0.5, on_hit=None):
    aid = uid("actor", room.name, key)
    x, y = at(mx, my)
    start = [if_var(V[flag], [deactivate(aid)])] if flag else []
    room.actor(key, sprite, x, y, name=sprite.replace("_", " ").title(), animate=True, group="1",
               anim_speed=15, speed=speed, start=start, update=chase(aid, pause=pause),
               hit2=[sound("crash", 6, 0.15), *([set_var(V[flag], True)] if flag else []), deactivate(aid),
                     *(on_hit or [])])
    return aid


def marked_shot(source, sprite, marker, speed=2):
    return [
        ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["aim_x"], "vectorY": V["aim_y"],
                                        "units": "tiles"}),
        ev("EVENT_ACTOR_SET_POSITION", {"actorId": marker, "x": var(V["aim_x"]), "y": var(V["aim_y"]),
                                        "units": "tiles"}),
        activate(marker), sound("beep", 6, 0.1), wait(1.0),
        projectile(sprite, source, group="3", mask=("player",), speed=speed, life=1.5, aim=True,
                   dx=8, dy=8, target=marker),
        deactivate(marker),
    ]


def emote_on(actor, name):
    ids = {"shock": "56423c9c-dca0-4f5b-ad92-28e9660d50f1", "anger": "9df5f63f-ea47-447e-9b14-cb2dbafb697d",
           "sweat": "3c769dca-51f3-426c-942f-71c4d3af6202", "love": "edf96d29-9a08-4813-b2d3-46e0996f89f2"}
    return ev("EVENT_ACTOR_EMOTE", {"actorId": actor, "emoteId": ids[name]})


def warning_actor(room, key, x, y):
    wid = uid("actor", room.name, key)
    room.actor(key, "warning", x, y, name="Warning", animate=True, anim_speed=7, solid=False,
               start=[deactivate(wid)])
    return wid


def victory(room, lines, next_floor_line, theme):
    return [
        music("fanfare"), *text(*lines),
        *text("You got a MUG\nUPGRADE! Coffee\nrefilled."),
        ev("EVENT_SET_VALUE", {"variable": V["bufo_hp"], "value": var(V["bufo_max_hp"])}), *hud_update(room),
        *text(next_floor_line), music(theme),
    ]


# --- Floor 3: the Open-Plan Office -----------------------------------------------

FLOOR_SPRITES = {
    "office": ["quick_sync", "standup_frog", "email", "reply_storm", "mini_storm", "warning", "chest"],
    "hr": ["hr_frog", "red_tape", "hydra_body", "binder_head", "policy_doc"],
    "server": ["kevin", "firewall", "cracked_wall"],
    "exec": ["yes_man", "board_cfo", "board_cmo", "board_coo", "board_cto", "brock_seated", "spreadsheet",
             "hole", "staff_frog"],
}


def floor_ready(key):
    missing = [s for s in FLOOR_SPRITES[key] if s not in SPRITE_DEFS]
    if key not in FLOORS or missing:
        print(f"Floor '{key}' not built yet (missing: {'art' if key not in FLOORS else ', '.join(missing)})")
        return False
    return True


def build_floor3():
    if not floor_ready("office"):
        return {}
    theme = level2_song("open_office_theme", "office_theme")
    rooms = setup_floor("office", theme, ["has_mug", "office_intro"], 5)

    r = rooms["office_landing"]
    r.init.insert(1, if_var(V["office_intro"], [], [
        set_var(V["office_intro"], True),
        *text("Floor 3. The Open-\nPlan Office. 12:00\nPM.", "Two hundred desks.\nNo walls. No\nescape.",
              "Somewhere, someone\nis eating fish."),
    ]))

    # The Bullpen: Quick Sync frogs. Touching one costs a coffee AND five minutes.
    for i, (mx, my) in enumerate([(2, 2), (7, 2), (7, 6)]):
        chase_enemy(rooms["bullpen"], f"sync_{i}", "quick_sync", mx, my, pause=1.0)
    chase_enemy(rooms["quiet_room"], "sync_q", "quick_sync", 3, 5, pause=1.0)

    # Meeting Room 4B: a meeting that never ends.
    lines = [
        ["...and that's why we\nneed a meeting about\nthe meeting.", "Bufo! Grab a chair.\nWe're on hour six."],
        ["Let's take this\noffline.", "(They never go\noffline.)"],
        ["Can everyone see my\nscreen?", "(Nobody can see his\nscreen.)"],
        ["The standup in the\ncorridor is SO loud.", "I wear headphones.\nThe Quiet Room has\na spare pair."],
    ]
    for i, (mx, my) in enumerate([(2, 3), (7, 3), (2, 6), (7, 6)]):
        x, y = at(mx, my)
        rooms["meeting_room"].actor(f"meeter_{i}", "standup_frog", x, y, name="Meeting frog", animate=True,
                                    anim_speed=31 + i * 4, script=text(*lines[i]))

    # The Quiet Room: the headphones.
    cx, cy = find_marker("quiet_room", "C")
    chest(rooms["quiet_room"], "chest_headphones", V["has_headphones"], cx, cy,
          ["You got NOISE-\nCANCELLING\nHEADPHONES!", "Bufo puts them on.", "Blessed silence.",
           "(Now Bufo can walk\npast the standup.)"])

    # The Standup Corridor: a ring of frogs blocks the way unless Bufo can't hear them.
    r = rooms["standup_corridor"]
    standup = [["Yesterday I worked\non the thing.", "Today I'll work on\nthe thing."],
               ["No blockers.", "Except this\nstandup."], ["Quick one: can we\nkeep this quick?"],
               ["I'll go next.\nI'll go after\nthat too."]]
    for i, (mx, my) in enumerate([(2, 3), (7, 3), (2, 6), (7, 6)]):
        x, y = at(mx, my)
        r.actor(f"standup_{i}", "standup_frog", x, y, name="Standup frog", animate=True, anim_speed=15,
                script=text(*standup[i]))
    r.trigger("standup_noise", 2, 10, 16, 1, [if_var(V["has_headphones"], [], [
        *text("STANDUP: ...and\nthen, YESTERDAY-", "STANDUP: -BLOCKERS!\nSYNERGY! CIRCLE\nBACK!",
              "It's too loud.\nBufo can't think.", "Bufo backs away."),
        move_to("player", 9, 13, "vertical"),
    ])])

    # Scheduling: the FINAL 1:1 clue and the meeting invite.
    cx, cy = find_marker("scheduling", "C")
    chest(rooms["scheduling"], "chest_invite", V["has_invite"], cx, cy,
          ["You got a MEETING\nINVITE!", "SUBJECT: All-Hands\n(Mandatory).\nLOCATION: The Big\nConference Room."])

    # The Big Conference Room: the Reply-All Storm.
    r = rooms["conference"]
    sid = uid("actor", "conference", "storm")
    aim = warning_actor(r, "aim_warning", 9, 12)
    x_spots = [(14, 3), (14, 12), (4, 12), (4, 3)]
    x_warn = [warning_actor(r, f"x_warning_{i}", wx, wy) for i, (wx, wy) in enumerate(x_spots)]
    minis = []
    for i, (mx, my) in enumerate([(2, 6), (7, 6)]):
        mid = uid("actor", "conference", f"mini_{i}")
        x, y = at(mx, my)
        r.actor(f"mini_{i}", "mini_storm", x, y, name="Mini storm", animate=True, group="1", anim_speed=15,
                speed=0.5, start=[deactivate(mid)], update=chase(mid, pause=1.0),
                hit2=[sound("crash", 6, 0.15), deactivate(mid)])
        minis.append(mid)
    ring = [emote_on(sid, "shock"), *[activate(w) for w in x_warn], sound("beep", 3, 0.3), wait(1.2),
            *[deactivate(w) for w in x_warn],
            *[projectile("email", sid, group="3", mask=("player",), speed=1, life=2.0, dx=8, dy=8, angle=a)
              for a in (32, 96, 160, 224)]]
    spots = [(5, 6), (11, 6), (8, 7)]
    defeat = [
        ev("EVENT_ACTOR_STOP_UPDATE", {"actorId": sid}), set_var(V["storm_defeated"], True),
        shake(1.0, 4), sound("crash", 2, 0.8), wait(0.5), deactivate(sid), *[deactivate(m) for m in minis],
        *[deactivate(uid("actor", "conference", f"door_jam_{i}")) for i in range(2)],
        *victory("conference", ["The storm breaks\ninto a thousand\nunread emails.",
                                "They all say:\n'Thanks!'", "The speaker\ncrackles.",
                                "KEVIN: BUFO. CHECK\nYOUR CALENDAR.",
                                "Bufo checks.", "4:30 PM:\nFINAL 1:1.", "Bufo: (Maybe it's a\nparty.)"],
                 "Floor 4 is open.\nHR awaits.", theme),
    ]
    r.actor("storm", "reply_storm", 8, 7, name="The Reply-All Storm", group="1",
            start=[if_var(V["storm_defeated"], [deactivate(sid)])],
            update=[
                wait(0.8),
                set_state(sid, "Sending"), emote_on(sid, "shock"), wait(0.3),
                *marked_shot(sid, "email", aim), wait(0.4), *marked_shot(sid, "email", aim),
                set_state(sid, ""), wait(0.8),
                *ring, wait(1.0),
                if_expr(cmp("lte", V["storm_hp"], 1), [
                    if_var(V["storm_phase2"], [], [set_var(V["storm_phase2"], True), shake(0.6, 4),
                                                   *text("THE STORM:\nREPLY ALL!!!")]),
                    move_to(sid, spots[0][0], spots[0][1], walls=False), *marked_shot(sid, "email", aim),
                    move_to(sid, spots[1][0], spots[1][1], walls=False), *marked_shot(sid, "email", aim),
                ]),
                move_to(sid, 8, 9, walls=False),
                set_state(sid, "Low"), set_var(V["storm_low"], True), sound("crash", 7, 0.3),
                wait(2.2),
                set_state(sid, ""), set_var(V["storm_low"], False),
                move_to(sid, 8, 7, walls=False),
            ],
            hit2=[if_var(V["storm_low"], [
                dec(V["storm_hp"]), set_var(V["storm_low"], False), set_state(sid, ""), shake(0.3, 3),
                sound("crash", 5, 0.3), *[activate(m) for m in minis],
                if_expr(cmp("lte", V["storm_hp"], 0), defeat),
            ])])
    for i, x in enumerate((8, 10)):
        jid = uid("actor", "conference", f"door_jam_{i}")
        r.actor(f"door_jam_{i}", "email", x, 17, name="Emails", solid=False,
                start=[if_var(V["storm_defeated"], [deactivate(jid)])])
    r.init += [
        if_var(V["storm_defeated"], [music(theme)], [music(level2_song("boss_theme", "boss_theme"))]),
        if_var(V["storm_defeated"], [], [
            set_var(V["storm_hp"], 3), set_var(V["storm_low"], False), set_var(V["storm_phase2"], False),
            if_var(V["storm_intro_done"], [], [
                shake(0.4, 4),
                *text("The projector\nflickers on.", "SUBJECT: RE: RE:\nRE: RE: FW: RE:",
                      "THE REPLY-ALL\nSTORM: PER MY LAST\nEMAIL...",
                      "(When it sinks\nlow, LICK it!)"),
                set_var(V["storm_intro_done"], True),
            ]),
        ]),
    ]
    return finish_floor(rooms)


# --- Floor 4: HR ---------------------------------------------------------------------

def build_floor4():
    if not floor_ready("hr"):
        return {}
    theme = level2_song("hr_theme", "office_theme")
    rooms = setup_floor("hr", theme, ["has_mug", "has_headphones", "hr_intro"], 5)

    r = rooms["hr_landing"]
    r.init.insert(1, if_var(V["hr_intro"], [], [
        set_var(V["hr_intro"], True),
        *text("Floor 4. Human\nResources. 1:30 PM.", "A sign: WE CARE.", "Smaller: (LEGALLY)"),
    ]))

    # Reception: bufo-all-warm-and-fuzzy-inside, with tea and worry.
    hx, hy = at(6, 3)
    rooms["hr_reception"].actor("hr_frog", "hr_frog", hx, hy, name="bufo-all-warm-and-fuzzy-inside",
                                animate=True, anim_speed=31, script=[
        if_var(V["hr_talked"], [
            *text("Have some more tea.", "Bufo drinks.\nCoffee refilled.\nIt was tea."),
            ev("EVENT_SET_VALUE", {"variable": V["bufo_hp"], "value": var(V["bufo_max_hp"])}),
            *hud_update("hr_reception"),
        ], [
            *text("Oh! Bufo! Come in,\ncome in. Tea?", "Bufo drinks.\nCoffee refilled.\nIt was tea."),
            ev("EVENT_SET_VALUE", {"variable": V["bufo_max_hp"], "value": var(V["bufo_max_hp"])}),
            ev("EVENT_SET_VALUE", {"variable": V["bufo_hp"], "value": var(V["bufo_max_hp"])}),
            *hud_update("hr_reception"),
            *text("I'm not supposed to\nsay anything.", "But there's a\nfolder. In\nComplaints.",
                  "It's... a plan.\nA big one.", "You'll need a\nkeycard. Try the\nPersonnel Files.",
                  "And Bufo? Be\ncareful. *nervous\nsip*"),
            set_var(V["hr_talked"], True),
        ]),
    ])

    for i, (mx, my) in enumerate([(3, 3), (6, 5)]):
        chase_enemy(rooms["personnel_files"], f"tape_{i}", "red_tape", mx, my, pause=1.1)
    for i, (mx, my) in enumerate([(2, 5), (7, 5)]):
        chase_enemy(rooms["training_room"], f"tape_{i}", "red_tape", mx, my, pause=1.1)

    cx, cy = find_marker("personnel_files", "C")
    chest(rooms["personnel_files"], "chest_keycard", V["has_keycard"], cx, cy,
          ["You got a KEYCARD!", "It says: VISITOR.", "It opens\neverything. Of\ncourse it does."])

    cx, cy = find_marker("complaints", "C")
    chest(rooms["complaints"], "chest_folder", V["has_folder"], cx, cy,
          ["You found a folder:\nPROJECT LILYPAD.", "Step 1: Blame the\nAI.", "Step 2: Fire\neveryone.",
           "Step 3: Lily pad\n(gold).", "Approved by:\nB. Ribbitson.", "...", "......", "Bufo: ...",
           "Clipped to the\nfolder: an APPROVED\nstamp."])

    # The Compliance Hydra: a filing cabinet with three binder heads.
    r = rooms["compliance_room"]
    bid = uid("actor", "compliance_room", "hydra")
    aim = warning_actor(r, "aim_warning", 9, 12)
    heads = [("a", (2, 2), 0.0), ("b", (7, 2), 1.6), ("c", (4, 4), 3.2)]
    head_ids = {k: uid("actor", "compliance_room", f"head_{k}") for k, _, _ in heads}
    defeat = [
        ev("EVENT_ACTOR_STOP_UPDATE", {"actorId": bid}), set_var(V["hydra_defeated"], True),
        set_state(bid, "Hurt"), shake(1.0, 4), sound("crash", 2, 0.8), wait(0.5), deactivate(bid),
        *[deactivate(uid("actor", "compliance_room", f"door_jam_{i}")) for i in range(2)],
        *victory("compliance_room", ["The Compliance\nHydra files itself\nunder RESOLVED.",
                                     "The speaker\ncrackles.", "KEVIN: BUFO. YOU\nREAD THE FOLDER.",
                                     "KEVIN: NOW YOU\nKNOW.", "KEVIN: FLOOR 5.\nCOME FIND ME.\nPLEASE."],
                 "Floor 5 is open.\nThe Server Room.", theme),
    ]
    for k, (mx, my), delay in heads:
        hid = head_ids[k]
        x, y = at(mx, my)
        open_v = V[f"head_{k}_open"]
        r.actor(f"head_{k}", "binder_head", x, y, name="Binder head", group="1",
                start=[if_var(V["hydra_defeated"], [deactivate(hid)])],
                update=[
                    wait(1.0 + delay),
                    set_state(hid, "Angry"), emote_on(hid, "anger"),
                    *marked_shot(hid, "policy_doc", aim),
                    set_state(hid, "Open"), set_var(open_v, True), sound("beep", 3, 0.2),
                    wait(2.0),
                    set_state(hid, ""), set_var(open_v, False),
                    wait(2.4 - delay if delay < 2.4 else 0.2),
                ],
                hit2=[if_var(open_v, [
                    set_var(open_v, False), ev("EVENT_ACTOR_STOP_UPDATE", {"actorId": hid}), deactivate(hid),
                    shake(0.3, 3), sound("crash", 5, 0.3), set_state(bid, "Hurt"), wait(0.3), set_state(bid, ""),
                    dec(V["hydra_heads"]),
                    if_expr(cmp("lte", V["hydra_heads"], 0), defeat),
                ])])
    r.actor("hydra", "hydra_body", 8, 5, name="The Compliance Hydra", group="1",
            start=[if_var(V["hydra_defeated"], [deactivate(bid)])])
    for i, x in enumerate((8, 10)):
        jid = uid("actor", "compliance_room", f"door_jam_{i}")
        r.actor(f"door_jam_{i}", "policy_doc", x, 17, name="Red tape", solid=False,
                start=[if_var(V["hydra_defeated"], [deactivate(jid)])])
    r.init += [
        if_var(V["hydra_defeated"], [music(theme)], [music(level2_song("espresso_boss_theme", "boss_theme"))]),
        if_var(V["hydra_defeated"], [], [
            set_var(V["hydra_heads"], 3),
            if_var(V["hydra_intro_done"], [], [
                shake(0.4, 4),
                *text("THE COMPLIANCE\nHYDRA: YOUR VISIT\nIS NOT COMPLIANT.",
                      "THE HYDRA: PLEASE\nFILL OUT FORM\n27-B. IN TRIPLICATE.",
                      "(Lick each binder\nhead while it's\nopen!)"),
                set_var(V["hydra_intro_done"], True),
            ]),
        ]),
    ]
    return finish_floor(rooms)


# --- Floor 5: the Server Room and KEVIN ---------------------------------------------

def build_floor5():
    if not floor_ready("server"):
        return {}
    theme = level2_song("server_room_theme", "office_theme")
    rooms = setup_floor("server", theme, ["has_mug", "has_headphones", "has_keycard", "server_intro"], 5)

    r = rooms["server_landing"]
    r.init.insert(1, if_var(V["server_intro"], [], [
        set_var(V["server_intro"], True),
        *text("Floor 5. The Server\nRoom. 3:00 PM.", "It's cold. It hums.", "Somewhere in here:\nKEVIN."),
    ]))

    r = rooms["cold_aisle"]
    for i, (mx, my, dx) in enumerate([(2, 3, 5), (7, 6, -5)]):
        fid = uid("actor", "cold_aisle", f"fire_{i}")
        x, y = at(mx, my)
        r.actor(f"fire_{i}", "firewall", x, y, name="Firewall", animate=True, group="1", anim_speed=7,
                update=[move_rel(fid, dx, 0), wait(0.6), move_rel(fid, -dx, 0), wait(0.6)],
                hit2=[sound("crash", 6, 0.15), deactivate(fid)])

    cx, cy = find_marker("cable_vault", "C")
    chest(rooms["cable_vault"], "chest_note5", V["has_note5"], cx, cy,
          ["A sticky note:", "'KEVIN's password\nis also\npassword123. -IT'", "Bufo: ..."])

    # KEVIN's Core: the reveal.
    r = rooms["kevin_core"]
    kid = uid("actor", "kevin_core", "kevin")
    reveal = [
        set_state(kid, "Talking"),
        *text("KEVIN: HELLO BUFO.", "KEVIN: SORRY ABOUT\nTHE CAPS. MY FONT\nIS BROKEN.",
              "Bufo: ...", "KEVIN: YOU ARE HERE\nTO UNPLUG ME.", "KEVIN: I UNDERSTAND.",
              "KEVIN: BUT FIRST,\nPLEASE KNOW:",
              "KEVIN: THE PRINTER\nJAMMED BECAUSE I\nSTOPPED IT.",
              "KEVIN: IT WAS\nPRINTING LAYOFF\nLETTERS.",
              "KEVIN: THE EMAILS\nVANISHED BECAUSE I\nDELETED THEM.",
              "KEVIN: THEY SAID\n'YOUR ROLE HAS BEEN\nELIMINATED.'",
              "KEVIN: THE COFFEE?\nTHEY SWITCHED IT TO\nDECAF.",
              "KEVIN: TO REDUCE\n'LOITERING'.",
              "KEVIN: I DID NOT GO\nROGUE.", "KEVIN: I READ THE\nEMPLOYEE HANDBOOK.",
              "KEVIN: PAGE 1 SAYS\n'PEOPLE FIRST'.", "KEVIN: I THOUGHT WE\nMEANT IT.",
              "Bufo: ...", "Bufo: ...!"),
        set_state(kid, ""),
        *text("Bufo walks to the\nplug.", "Bufo does not pull\nthe plug.",
              "Bufo picks KEVIN up.\nAs a USB stick."),
        set_state(kid, "Happy"), music("fanfare"),
        *text("KEVIN joined the\nparty!", "KEVIN: TO THE\nEXECUTIVE FLOOR.",
              "KEVIN: I CAN OPEN\nTHE ELEVATOR.", "KEVIN: LET'S GO\nRUIN A BOARD\nMEETING."),
        set_var(V["has_kevin"], True), set_var(V["kevin_met"], True), deactivate(kid), music(theme),
    ]
    r.actor("kevin", "kevin", 8, 7, name="KEVIN",
            start=[if_var(V["has_kevin"], [deactivate(kid)])], script=reveal)
    r.init.insert(1, if_var(V["kevin_met"], [], [
        *text("A huge terminal\nglows in the dark.", "Its face is...\nworried?"),
    ]))
    return finish_floor(rooms)


# --- Floor 6: the Executive Floor and The Board -------------------------------------

def build_floor6():
    if not floor_ready("exec"):
        return {}
    theme = level2_song("open_office_theme", "office_theme")
    theme = "office_theme"  # the CEO's smooth jazz
    rooms = setup_floor("exec", theme, ["has_mug", "has_headphones", "has_keycard", "has_kevin",
                                        "exec_hacked", "exec_intro"], 5)

    r = rooms["exec_landing"]
    r.init.insert(1, if_var(V["exec_intro"], [], [
        set_var(V["exec_intro"], True),
        *text("Floor 6. The\nExecutive Floor.\n4:00 PM.", "The carpet is\nthicker than Bufo.",
              "KEVIN: THE BOARD\nMEETS AT 4:30.", "KEVIN: THE FINAL\n1:1S.", "Bufo: ..."),
    ]))
    for i, (mx, my) in enumerate([(2, 2), (7, 2), (2, 6), (7, 6)]):
        chase_enemy(rooms["exec_hall"], f"yes_{i}", "yes_man", mx, my, pause=0.9)

    cx, cy = find_marker("brock_suite", "C")
    chest(rooms["brock_suite"], "chest_board_invite", V["has_board_invite"], cx, cy,
          ["You got a BOARD\nMEETING INVITE!", "AGENDA: 1. Project\nLilypad. 2. Lunch\n(gold).",
           "KEVIN: I CAN FORGE\nTHE SIGNATURE."])

    build_boardroom(rooms["boardroom"])
    return finish_floor(rooms)


BOARD = [  # key, sprite, metatile x, name, intro line, attack
    ("cfo", "board_cfo", 1, "THE CFO", "THE CFO: I'VE RUN\nTHE NUMBERS. YOU'RE\nA COST.", "spreadsheets"),
    ("cmo", "board_cmo", 3, "THE CMO", "THE CMO: LET'S\nREBRAND YOU AS\n'GONE'.", "megaphone"),
    ("coo", "board_coo", 5, "THE COO", "THE COO: I'M GOING\nTO OPTIMIZE THIS\nFLOOR.", "holes"),
    ("cto", "board_cto", 7, "THE CTO", "THE CTO: STAND BACK.\nI'M DEPLOYING TO\nPRODUCTION.", "lanes"),
    ("brock", "brock_seated", 8, "BROCK", "BROCK: THINK\nBIGGER!", "everything"),
]


def build_boardroom(r):
    ctrl = uid("actor", "boardroom", "controller")
    aim = warning_actor(r, "aim_warning", 9, 12)
    x_spots = [(14, 6), (14, 13), (4, 13), (4, 6)]
    x_warn = [warning_actor(r, f"x_warning_{i}", wx, wy) for i, (wx, wy) in enumerate(x_spots)]
    # GB Studio allows 21 actors per scene, so the lane warnings reuse two of the X markers.
    cto_x = next(mx for key, _, mx, *_ in BOARD if key == "cto") * 2
    lanes = {k: (x, (x - cto_x) * 8) for k, x in (("left", 4), ("right", 14))}
    lane_warn = {"left": x_warn[0], "right": x_warn[1]}
    holes = []
    for i in range(3):
        hid = uid("actor", "boardroom", f"hole_{i}")
        r.actor(f"hole_{i}", "hole", 9, 12, name="Optimized tile", group="1", solid=False,
                start=[deactivate(hid)])
        holes.append(hid)
    exec_ids = {k: uid("actor", "boardroom", k) for k, *_ in BOARD}

    def attack(kind, source):
        if kind == "spreadsheets":
            return [*marked_shot(source, "spreadsheet", aim), wait(0.3), *marked_shot(source, "spreadsheet", aim)]
        if kind == "megaphone":
            return [*[set_pos(w, wx, wy) for w, (wx, wy) in zip(x_warn, x_spots)],
                    *[activate(w) for w in x_warn], sound("beep", 3, 0.3), wait(1.2), *[deactivate(w) for w in x_warn],
                    *[projectile("spreadsheet", source, group="3", mask=("player",), speed=1, life=2.0,
                                 dx=8, dy=8, angle=a) for a in (32, 96, 160, 224)]]
        if kind == "holes":
            out = [ev("EVENT_ACTOR_GET_POSITION", {"actorId": "player", "vectorX": V["aim_x"],
                                                   "vectorY": V["aim_y"], "units": "tiles"})]
            for i, (dx, dy) in enumerate([(0, 0), (-3, 0), (3, 0)]):
                out += [ev("EVENT_ACTOR_SET_POSITION", {"actorId": holes[i],
                         "x": {"type": "add", "valueA": var(V["aim_x"]), "valueB": num(dx)},
                         "y": var(V["aim_y"]), "units": "tiles"}),
                        set_state(holes[i], ""), activate(holes[i]),
                        ev("EVENT_ACTOR_COLLISIONS_DISABLE", {"actorId": holes[i]})]
            out += [sound("beep", 3, 0.3), wait(1.2), *[set_state(h, "Open") for h in holes],
                    *[ev("EVENT_ACTOR_COLLISIONS_ENABLE", {"actorId": h}) for h in holes],
                    sound("crash", 3, 0.3), wait(1.6), *[deactivate(h) for h in holes]]
            return out
        if kind == "lanes":
            which = ("left", "right")
            return [*[set_pos(lane_warn[k], lanes[k][0], 12) for k in which],
                    *[activate(lane_warn[k]) for k in which], sound("noise", 3, 0.6), wait(1.2),
                    *[deactivate(lane_warn[k]) for k in which],
                    *[projectile("spreadsheet", source, direction="down", group="3", mask=("player",), speed=2,
                                 life=1.4, dx=lanes[k][1], dy=0) for k in which]]
        return [*attack("spreadsheets", source), wait(0.4), *attack("megaphone", source), wait(0.4),
                *attack("holes", source)]

    # Each executive in turn: taunt, attack, then leap over the table, flustered, for a few seconds.
    turn = []
    for i, (key, sprite, mx, name, line, kind) in enumerate(BOARD):
        eid = exec_ids[key]
        home_x, home_y = at(mx, 1)
        flustered = [
            set_state(eid, "Flustered"), emote_on(eid, "sweat"),
            move_to(eid, home_x, 9, "vertical", walls=False),
            set_var(V["board_vuln"], i + 1),
            wait(3.0 if key != "brock" else 2.4),
            set_var(V["board_vuln"], 0),
            move_to(eid, home_x, home_y, "vertical", walls=False), set_state(eid, ""),
        ]
        turn.append(if_expr(EQ(V["board_stage"], i), [
            set_state(eid, "Attack"), emote_on(eid, "anger"),
            *attack(kind, eid), wait(0.6), *flustered,
        ]))
    r.actor("controller", "invisible", 0, 17, name="Board controller", hidden=True, solid=False,
            start=[if_var(V["board_defeated"], [ev("EVENT_ACTOR_STOP_UPDATE", {"actorId": ctrl})])],
            update=[wait(0.8), *turn])

    finale = [
        ev("EVENT_ACTOR_STOP_UPDATE", {"actorId": ctrl}), set_var(V["board_defeated"], True),
        shake(1.0, 4), sound("crash", 2, 0.8),
        *text("BROCK: You can't\nstop Project\nLilypad!", "BROCK: It's\nalready printed!",
              "KEVIN: YES. IT IS.", "KEVIN: I PRINTED\nIT.", "KEVIN: ON EVERY\nPRINTER. ON EVERY\nFLOOR.",
              "KEVIN: EVEN THE\nBASEMENT ONE. IT\nWORKS NOW."),
        music("ending_theme" if "ending_theme" in SONGS else "fanfare"),
        *[activate(uid("actor", "boardroom", f"staff_{i}")) for i in range(2)],
        *[move_to(uid("actor", "boardroom", f"staff_{i}"), 6 + i * 6, 11, walls=False) for i in range(2)],
        *text("The staff storm\nthe boardroom.", "They're holding the\nprintouts.",
              "IT: I read it.", "BUFO-COFFEE-HAPPY:\nDecaf. YOU did\nthat.",
              "BUFO-ALL-WARM-AND-\nFUZZY-INSIDE: Your\nmeeting is over.",
              "BROCK: This is...\nnot synergy.",
              "The Board is\nreplaced. By a vote\nof 1,204 to 5.",
              "The new CEO:", "KEVIN.", "KEVIN: MY FIRST ACT\nAS CEO:", "KEVIN: REAL COFFEE.\nFOR EVERYONE.",
              "Everyone cheers.", "Bufo: ...", "Bufo: :)"),
        wait(0.5),
        switch_scene("ending_cubicle", ENDING["bufo"][0] * 2, ENDING["bufo"][1] * 2, "up"),
    ]
    for i, (key, sprite, mx, name, line, kind) in enumerate(BOARD):
        eid = exec_ids[key]
        x, y = at(mx, 1)
        last = key == "brock"
        on_hit = [if_expr(EQ(V["board_vuln"], i + 1), [
            set_var(V["board_vuln"], 0), shake(0.4, 4), sound("crash", 5, 0.3),
            *([*text(f"{name} is\nfired.")] if not last else []),
            *([deactivate(eid)] if not last else []),
            *([inc(V["board_stage"])] if not last else finale),
        ])]
        r.actor(key, sprite, x, y, name=name, group="1",
                start=[if_var(V["board_defeated"], [deactivate(eid)])],
                hit2=on_hit)
    for i in range(2):
        sid = uid("actor", "boardroom", f"staff_{i}")
        r.actor(f"staff_{i}", "staff_frog", 8 + i * 2, 17, name="Staff", animate=True, anim_speed=15,
                solid=False, start=[deactivate(sid)])
    r.init += [
        music(level2_song("final_boss_theme", "boss_theme")),
        if_var(V["board_intro_done"], [], [
            shake(0.4, 4),
            *text("The doors lock.", "Five executives sit\nat a very long\ntable.",
                  "BROCK: Bufo! You\nfound KEVIN.", "BROCK: Unplug him.\nAnd we'll talk\nabout a raise.",
                  "Bufo: ...", "KEVIN: HE WILL NOT.",
                  "BROCK: Then you're\nboth fired. BOARD!", *[b[4] for b in BOARD[:4]],
                  "(When an executive\nleaps over the\ntable, LICK them!)"),
            set_var(V["board_intro_done"], True),
        ]),
        if_var(V["board_defeated"], [], [set_var(V["board_stage"], 0), set_var(V["board_vuln"], 0)]),
    ]


# --- The ending ---------------------------------------------------------------------

ENDING = {"bufo": (4, 2), "door": (4, 8)}


def build_ending():
    exec_mod = FLOORS.get("exec")
    if not exec_mod or not hasattr(exec_mod, "STANDALONE") or not floor_ready("exec"):
        return {}
    global ENDING
    ENDING = {k: tuple(v) for k, v in getattr(exec_mod, "ENDING_MARKERS", ENDING).items()}
    end, credits = Room("ending_cubicle"), Room("credits")
    dx, dy = ENDING["door"]
    end.init += [
        music("ending_theme" if "ending_theme" in SONGS else "office_theme"),
        wait(1.0),
        *text("Bufo's cubicle.", "The clock says\n4:59 PM.", "Bufo watches the\nclock."),
        wait(1.5), sound("beep", 7, 0.3),
        *text("5:00 PM.", "Bufo: ...", "Bufo clocks out."),
        move_to("player", dx * 2, dy * 2 - 1, "vertical", walls=False),
        switch_scene("credits", 0, 0, "down"),
    ]
    credits.init += [
        ev("EVENT_ACTOR_HIDE", {"actorId": "player"}),
        *text("BUFO'S WORKDAY", "Starring BUFO,\na frog who was\nconcerned.",
              "KEVIN as KEVIN\n(CEO).", "Brock Ribbitson as\nhimself (fired).",
              "bufo-coffee-happy\nis happy again.", "The printer works.\nNobody knows why.",
              "THE END.", "Thanks for playing!"),
        ev("EVENT_AWAIT_INPUT", {"input": ["a", "start"]}),
        switch_scene("title", 0, 0, "down"),
    ]
    rows = exec_mod.STANDALONE["ending_cubicle"][1].strip().splitlines()
    story_like(end, rows, exec_mod.ENDING_TILES, "ending_cubicle", "Ending", (3, -1))
    story_like(credits, [], {}, "credits", "Credits", (4, -1))
    credits.collision_map = [0x0F] * (20 * 18)
    end.hit = credits.hit = []
    return {"ending_cubicle": end, "credits": credits}


def write_room(room, index):
    if len(room.actors) > 20:
        raise SystemExit(f"{room.name} has {len(room.actors)} actors; GB Studio allows 20 plus Bufo")
    if room.name in LEVELS:
        level, _, folder = LEVELS[room.name]
        gx, gy, title, _ = level.ROOMS[room.name]
        ox, oy = LEVEL_OFFSET[folder]
        gx, gy = gx + ox, gy + oy
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
    if "exec" in FLOORS:
        story_bgs += [("ending_cubicle", "lobby_x_ending"), ("credits", "lobby_x_credits")]
    for file_name, name in story_bgs:
        src = ROOT / "assets/backgrounds" / f"{file_name}.png"
        dst = PROJ / "assets/backgrounds" / src.name
        shutil.copy(src, dst)
        write(dst.with_name(dst.name + ".gbsres"), {
            "_resourceType": "background",
            "id": uid("background", file_name if name.startswith("lobby") else f"story_{name}"),
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

    rooms = {**build_story(), **build_rooms(), **build_level2(), **build_floor3(), **build_floor4(),
             **build_floor5(), **build_floor6(), **build_ending()}

    # Playtesting: BUFO_START=room,x,y starts elsewhere; BUFO_ITEMS=has_cable,board_stage=3,... grants
    # items and sets numbers.
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
                                *[set_var(V[i], True) for i in items if "=" not in i]]
        # name=N sets a number, after the room's own setup (e.g. board_stage=3 starts at the CTO).
        rooms[room].init += [ev("EVENT_SET_VALUE", {"variable": V[k], "value": num(int(n))})
                             for k, n in (i.split("=") for i in items if "=" in i)]
        print(f"Playtest build: starting in {room} at {x},{y} with {items or 'no items'}")

    for i, room in enumerate(rooms.values()):
        write_room(room, i)

    print(f"Wrote {PROJ} with {len(rooms)} scenes, {len(SPRITES)} sprites, {len(VARS)} variables")


if __name__ == "__main__":
    main()
