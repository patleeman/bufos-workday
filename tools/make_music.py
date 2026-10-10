#!/usr/bin/env python3
"""Compose Bufo's Workday music and write hUGETracker (.uge v6) files.

Usage:
    python3 tools/make_music.py            # write assets/music/*.uge
    python3 tools/make_music.py --verify   # also round-trip each file through
                                           # GB Studio's own loadUGESong/saveUGESong
    python3 tools/make_music.py --previews # also build a test ROM per song in
                                           # /tmp/musictest and render previews/music/*.wav

The output is deterministic: the songs are written note by note below, and the
binary layout follows GB Studio's saveUGESong (src/shared/lib/uge/ugeHelper.ts)
field for field, so loading and re-saving a file in GB Studio gives the same bytes.

Songs:
    office_theme    F major swing, 116 BPM, 20 bars (41 s), loops. Elevator jazz
                    with a minor iv, a b9 and a tritone-sub bridge for menace.
    basement_theme  D minor, 120 BPM, 28 bars (56 s), loops. Bouncy octave bass,
                    offbeat plucks, a worried chromatic hook.
    boss_theme      E minor, 192 BPM, 24 bars (5 s intro + 25 s loop). The intro plays
                    once, then the body loops. Galloping saw bass, printer "error beep" bridge.
    fanfare         C major, ~3.5 s, bVI-bVII-I cadence then silence (never repeats).

Tempo: GB Studio calls hUGEDriver 64 times a second, so rows/s = 64 / ticks per row.

Pitch names are scientific (C4 = middle C). Pulse note index = MIDI - 36, wave
index = MIDI - 24 (the wave channel sounds an octave below the pulse channels for
the same index, so this keeps written pitch = heard pitch).
"""

import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import uuid
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "music"
PREVIEW_DIR = ROOT / "previews" / "music"
GBS_SRC = Path("/tmp/gbs-src")
TEST_DIR = Path("/tmp/musictest")

NO_NOTE = 90
# GB Studio runs hUGEDriver from a 256 Hz timer interrupt, every 4th call: 64 ticks/s.
DRIVER_HZ = 64.0
FX_ARP, FX_VIB, FX_VOL, FX_CUT, FX_JUMP, FX_BREAK = 0x0, 0x4, 0xC, 0xE, 0xB, 0xD

# --------------------------------------------------------------------------
# Pitch helpers
# --------------------------------------------------------------------------

_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    """'C4' -> 60, 'Bb3' -> 58, 'F#5' -> 78."""
    letter, rest = name[0], name[1:]
    acc = 0
    while rest and rest[0] in "#b":
        acc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + _SEMI[letter] + acc


def pulse_idx(m):
    i = m - 36
    assert 0 <= i <= 71, f"pulse note out of range: {m}"
    return i


def wave_idx(m):
    i = m - 24
    assert 0 <= i <= 71, f"wave note out of range: {m}"
    return i


# --------------------------------------------------------------------------
# Instruments and waves
# --------------------------------------------------------------------------

def empty_sub():
    return [dict(note=None, jump=0, effectCode=None, effectParam=None) for _ in range(64)]


def duty(name, duty_cycle, vol, sweep=0, length=None):
    return dict(name=name, length=length, dutyCycle=duty_cycle, initialVolume=vol,
                volumeSweepChange=sweep, frequencySweepTime=0, frequencySweepShift=0,
                subpatternEnabled=False, subpattern=empty_sub())


def wave_inst(name, wave_index, volume=1, length=None):
    # volume is the NR32 code: 1 = 100%, 2 = 50%, 3 = 25%
    return dict(name=name, length=length, volume=volume, waveIndex=wave_index,
                subpatternEnabled=False, subpattern=empty_sub())


def noise(name, vol, sweep, length=None, offsets=None):
    """offsets: per-tick pitch offsets (semitones relative to the pattern note)."""
    sub = empty_sub()
    if offsets:
        for i, off in enumerate(offsets):
            sub[i]["note"] = 36 + off
        hold = len(offsets)
        sub[hold]["jump"] = hold + 1  # jump to itself: hold the last pitch
    return dict(name=name, length=length, initialVolume=vol, volumeSweepChange=sweep,
                bitCount=15, subpatternEnabled=bool(offsets), subpattern=sub)


def unused_duty():
    return duty("", 2, 15)


def unused_wave():
    return wave_inst("", 0)


def unused_noise():
    return noise("", 15, 0)


def make_wave(fn):
    return [max(0, min(15, int(round(fn(i / 32.0))))) for i in range(32)]


WAVES = [
    make_wave(lambda t: 7.5 + 7.5 * math.sin(2 * math.pi * t)),                    # 0 sine
    make_wave(lambda t: 15 * (1 - abs(2 * t - 1))),                                 # 1 triangle
    # 2 rounded square: short ramps at the edges keep it bouncy but not harsh
    [8, 11, 13, 14] + [14] * 11 + [13, 8, 5, 3, 2] + [1] * 11 + [3],
    make_wave(lambda t: 15 * (1 - t)),                                              # 3 saw
    make_wave(lambda t: 7.5 + 5 * math.sin(2 * math.pi * t) + 2.5 * math.sin(4 * math.pi * t)),  # 4 warm
]
assert all(len(w) == 32 and all(0 <= v <= 15 for v in w) for w in WAVES)

# Shared drum kit (noise channel). Pattern note -> pitch (higher = brighter).
KIT = [
    noise("Kick", 12, -7, offsets=[27, 14, 6, -2, -8]),   # 0 played at note 24
    noise("Snare", 11, -6, offsets=[18, 24, 22]),         # 1 played at note 24
    noise("Hat closed", 7, -7, length=6),                 # 2 note 58
    noise("Ride", 5, -4, length=24),                      # 3 note 60
    noise("Crash", 10, -2),                               # 4 note 50
    noise("Brush chick", 4, -7, length=8),                # 5 note 52
    noise("Hat soft", 5, -7, length=4),                   # 6 note 60
]
DRUM = {  # char -> (instrument, note)
    "K": (0, 24), "S": (1, 24), "h": (2, 58), "r": (3, 60), "C": (4, 50),
    "c": (5, 52), "t": (6, 61), "s": (1, 30),  # s = ghost/higher snare for rolls
}


# --------------------------------------------------------------------------
# Song building
# --------------------------------------------------------------------------

class Track:
    """A single channel laid out as one long row timeline."""

    def __init__(self, kind):
        self.kind = kind  # "pulse", "wave", "noise"
        self.cells = {}

    def put(self, row, note=None, inst=None, fx=None, param=None):
        cell = self.cells.setdefault(row, [None, None, None, None])
        if note is not None:
            cell[0], cell[1] = note, inst
        if fx is not None:
            cell[2], cell[3] = fx, param

    def fx(self, row, fx, param):
        cell = self.cells.setdefault(row, [None, None, None, None])
        if cell[2] is None:
            cell[2], cell[3] = fx, param


def parse_tokens(text):
    out = []
    for tok in text.split():
        name, dur = tok.split(":")
        out.append((name, int(dur)))
    return out


def melody(track, start, text, inst, vib=None, vib_after=4, cut_gap=0, transpose=0):
    """Lay out 'C5:2 r:2 E5:4 _:2' (rows). r = rest (cuts the note), _ = tie.
    vib: vibrato param applied from `vib_after` rows into notes longer than that.
    cut_gap: cut each note this many ticks into its final row (articulation)."""
    row = start
    to_idx = pulse_idx if track.kind == "pulse" else wave_idx
    for name, dur in parse_tokens(text):
        if name == "r":
            track.put(row, fx=FX_CUT, param=0)
        elif name == "_":
            pass
        else:
            track.put(row, to_idx(midi(name) + transpose), inst)
            if vib is not None and dur > vib_after:
                for r in range(row + vib_after, row + dur):
                    track.fx(r, FX_VIB, vib)
            if cut_gap:
                track.fx(row + dur - 1, FX_CUT, cut_gap)
        row += dur
    return row


def _len(text, rows):
    total = sum(d for _, d in parse_tokens(text))
    assert total == rows, f"phrase is {total} rows, expected {rows}: {text.split()[:4]}"


def chord_stab(track, row, root, arp, inst, rows=2):
    """Arpeggiated chord stab: root note + 0xy arpeggio held for `rows` rows."""
    track.put(row, pulse_idx(midi(root)), inst)
    for r in range(row, row + rows):
        track.fx(r, FX_ARP, arp)


def drums(track, start, pattern, step=1, kit=None):
    """pattern string, one char per `step` rows: K S h r C c t s, '.' = nothing."""
    for i, ch in enumerate(pattern.replace(" ", "")):
        kit_map = DRUM if kit is None else kit
        if ch in kit_map:
            inst, note = kit_map[ch]
            track.put(start + i * step, note, inst)


class Song:
    def __init__(self, name, ticks_per_row, pattern_rows, duties, waves_inst, noises=None):
        self.name = name
        self.tpr = ticks_per_row
        self.prow = pattern_rows
        self.duty_insts = duties
        self.wave_insts = waves_inst
        self.noise_insts = noises if noises is not None else KIT
        self.waves = WAVES
        self.tracks = [Track("pulse"), Track("pulse"), Track("wave"), Track("noise")]
        self.jumps = {}  # pattern index -> order to jump to after it (0-based)
        self.total_rows = 0

    def build(self):
        """Chop the timelines into patterns and an order list."""
        n_pat = -(-self.total_rows // self.prow)
        blocks, order = [], []
        for p in range(n_pat):
            block = []
            for c, tr in enumerate(self.tracks):
                pat = [[None, None, None, None] for _ in range(64)]
                for r in range(self.prow):
                    cell = tr.cells.get(p * self.prow + r)
                    if cell:
                        pat[r] = list(cell)
                block.append(pat)
            last = self.prow - 1
            if p in self.jumps:
                self._global_fx(block, last, FX_JUMP, self.jumps[p] + 1)  # Bxx is 1-based
            elif self.prow < 64:
                self._global_fx(block, last, FX_BREAK, 1)  # Dxx: row xx-1 of next order
            key = json.dumps(block)
            for i, b in enumerate(blocks):
                if json.dumps(b) == key:
                    order.append(i)
                    break
            else:
                blocks.append(block)
                order.append(len(blocks) - 1)
        return blocks, order

    @staticmethod
    def _global_fx(block, row, fx, param):
        for c in (3, 2, 1, 0):
            if block[c][row][2] is None:
                block[c][row][2], block[c][row][3] = fx, param
                return
        raise ValueError("no free effect column for global effect")


# --------------------------------------------------------------------------
# UGE v6 writer (mirrors GB Studio saveUGESong byte for byte)
# --------------------------------------------------------------------------

class Writer:
    def __init__(self):
        self.b = bytearray()

    def u8(self, v):
        self.b += struct.pack("<B", v & 0xFF)

    def i8(self, v):
        self.b += struct.pack("<b", v)

    def u32(self, v):
        self.b += struct.pack("<I", v & 0xFFFFFFFF)

    def sstr(self, s):
        data = s.encode("utf-8")[:255]
        self.u8(len(s))
        self.b += data + bytes(255 - len(data))

    def sub(self, inst):
        self.i8(1 if inst["subpatternEnabled"] else 0)
        for n in range(64):
            c = inst["subpattern"][n]
            self.u32(NO_NOTE if c["note"] is None else c["note"])
            self.u32(0)
            self.u32(c["jump"] or 0)
            self.u32(c["effectCode"] or 0)
            self.u8(c["effectParam"] or 0)


def env_bytes(w, inst):
    w.u32(64 - inst["length"] if inst["length"] is not None else 0)
    w.u8(0 if inst["length"] is None else 1)
    w.u8(inst["initialVolume"])
    w.u32(1 if inst["volumeSweepChange"] < 0 else 0)
    w.u8(8 - abs(inst["volumeSweepChange"]) if inst["volumeSweepChange"] else 0)


def write_uge(song, path):
    blocks, order = song.build()
    w = Writer()
    w.u32(6)
    w.sstr(song.name)
    w.sstr("Bufo's Workday")
    w.sstr("Generated by tools/make_music.py")

    duties = (song.duty_insts + [unused_duty() for _ in range(15)])[:15]
    for i in duties:
        w.u32(0)
        w.sstr(i["name"])
        env_bytes(w, i)
        w.u32(i["frequencySweepTime"])
        w.u32(1 if i["frequencySweepShift"] < 0 else 0)
        w.u32(abs(i["frequencySweepShift"]))
        w.u8(i["dutyCycle"])
        w.u32(0); w.u32(0); w.u32(0)
        w.sub(i)
    wavs = (song.wave_insts + [unused_wave() for _ in range(15)])[:15]
    for i in wavs:
        w.u32(1)
        w.sstr(i["name"])
        w.u32(256 - i["length"] if i["length"] is not None else 0)
        w.u8(0 if i["length"] is None else 1)
        w.u8(0); w.u32(0); w.u8(0)
        w.u32(0); w.u32(0); w.u32(0)
        w.u8(0)
        w.u32(i["volume"])
        w.u32(i["waveIndex"])
        w.u32(0)
        w.sub(i)
    noises = (song.noise_insts + [unused_noise() for _ in range(15)])[:15]
    for i in noises:
        w.u32(2)
        w.sstr(i["name"])
        env_bytes(w, i)
        w.u32(0); w.u32(0); w.u32(0)
        w.u8(0)
        w.u32(0); w.u32(0)
        w.u32(1 if i["bitCount"] == 7 else 0)
        w.sub(i)
    for n in range(16):
        data = song.waves[n] if n < len(song.waves) else [0] * 32
        for v in data:
            w.u8(v)
    w.u32(song.tpr)
    w.i8(0)   # timer disabled
    w.u32(0)  # timer divider

    w.u32(len(blocks) * 4)
    key = 0
    for block in blocks:
        for pat in block:
            w.u32(key)
            key += 1
            for note, inst, fx, param in pat:
                w.u32(NO_NOTE if note is None else note)
                w.u32(0 if inst is None else inst + 1)
                w.u32(0)
                w.u32(0 if fx is None else fx)
                w.u8(0 if param is None else param)
    for c in range(4):
        w.u32(len(order) + 1)
        for o in order:
            w.u32(o * 4 + c)
        w.u32(0)
    for _ in range(16):
        w.u32(0)
    path.write_bytes(bytes(w.b))
    return blocks, order


# --------------------------------------------------------------------------
# Song 1: office_theme  (F major, swing, tpr 11, 3 rows per beat, 4 bars per pattern)
# --------------------------------------------------------------------------

def office_theme():
    s = Song("Corporate Elevator", 11, 48,
             [duty("Lead 25%", 1, 10), duty("Rhodes 50%", 2, 6, sweep=-2)],
             [wave_inst("Sine bass", 0)])
    bar = 12
    lead, comp, bass, drm = s.tracks

    lead_text = """
      r:3 A4:2 C5:1 E5:6        D5:2 C5:1 A4:3 F5:6
      r:3 Bb4:2 D5:1 F5:3 E5:2 F5:1   G5:6 E5:3 C5:3
      r:3 C5:2 E5:1 G5:6        F#5:3 Eb5:3 D5:3 C5:3
      Bb4:2 A4:1 Bb4:2 D5:1 F5:6      E5:3 D5:2 C5:1 Bb4:3 r:3

      r:3 A4:2 C5:1 E5:6        D5:2 C5:1 A4:3 F5:6
      r:3 Bb4:2 D5:1 F5:3 A5:2 G5:1   E5:2 C5:1 G5:6 r:3
      A5:6 F5:3 D5:3            Db5:6 Bb4:3 G4:3
      C5:3 E5:3 D5:3 B4:3       Bb4:2 A4:1 G4:3 E4:3 C5:3

      F5:6 C5:3 Ab4:3           Bb4:6 Ab4:3 E4:3
      D5:2 F5:1 A5:6 G5:3       E5:3 Db5:3 C5:6
    """
    assert melody(lead, 0, lead_text, 0, vib=0x31, vib_after=3) == 20 * bar

    # (root for bass, chord tones for the walk, comp root, comp arp) per half bar
    M7, m7, D7, m6, dim, b9 = "M7", "m7", "7", "m6", "dim", "7b9"
    chords = [
        ("F", M7), ("F", M7), ("D", m7), ("D", m7), ("G", m7), ("G", m7), ("C", D7), ("C", D7),
        ("A", m7), ("A", m7), ("D", b9), ("D", b9), ("G", m7), ("G", m7), ("C", D7), ("C", D7),
        ("F", M7), ("F", M7), ("D", m7), ("D", m7), ("G", m7), ("G", m7), ("C", D7), ("C", D7),
        ("Bb", M7), ("Bb", M7), ("Bb", m6), ("Bb", m6), ("A", m7), ("Ab", dim), ("G", m7), ("C", D7),
        ("Db", M7), ("Db", M7), ("Gb", D7), ("Gb", D7), ("G", m7), ("G", m7), ("C", b9), ("C", b9),
    ]
    third = {M7: 4, m7: 3, D7: 4, m6: 3, dim: 3, b9: 4}
    fifth = {M7: 7, m7: 7, D7: 7, m6: 7, dim: 6, b9: 7}
    arp = {M7: 0x37, m7: 0x47, D7: 0x36, m6: 0x46, dim: 0x36, b9: 0x69}

    def root_midi(r, octave=2):
        m = midi(r + str(octave))
        return m if m <= midi("Bb2") else m - 12  # keep the bass between B1 and Bb2

    # Walking bass: one note per beat (3 rows). Root, chord tone, chord tone, approach.
    n_half = len(chords)
    for h in range(n_half):
        r, q = chords[h]
        nr, _ = chords[(h + 1) % n_half]
        root = root_midi(r)
        nxt = root_midi(nr)
        start = h * 6
        same_next = (nr == r)
        if same_next:
            notes = [root, root + third[q]]
        else:
            prev_same = chords[h - 1][0] == r
            a = root + fifth[q] if prev_same else root
            approach = nxt - 1 if nxt > a else nxt + 1
            notes = [a, approach]
        for i, m in enumerate(notes):
            bass.put(start + i * 3, wave_idx(m), 0)
            bass.fx(start + i * 3 + 2, FX_CUT, 7)  # tiny gap = plucked upright feel

    # Comp: arpeggiated shell voicings (3rd-7th) on the Rhodes. One chord per bar:
    # Charleston rhythm (beat 1, swung "and" of 2). Two chords per bar: beats 1 and 3.
    def stab_root(r, q):
        m = midi(r + "4") + (0 if q == dim else third[q])
        while m > midi("C5"):
            m -= 12
        while m < midi("E4"):
            m += 12
        return _name(m)

    for b in range(len(chords) // 2):
        (r1, q1), (r2, q2) = chords[b * 2], chords[b * 2 + 1]
        chord_stab(comp, b * bar, stab_root(r1, q1), arp[q1], 1, rows=2)
        if (r1, q1) == (r2, q2):
            chord_stab(comp, b * bar + 5, stab_root(r1, q1), arp[q1], 1, rows=1)
        else:
            chord_stab(comp, b * bar + 6, stab_root(r2, q2), arp[q2], 1, rows=2)

    # Ride: "ding, ding-a ding, ding-a" with a brush chick on 2 and 4.
    for b in range(len(chords) // 2):
        drums(drm, b * bar, "r..c.rr..c.r")
        if b % 4 == 3:
            drums(drm, b * bar, "r..c.rr.ccsc")  # little brush fill into the next phrase
    s.total_rows = len(chords) * 6
    return s


def _name(m):
    names = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
    return f"{names[m % 12]}{m // 12 - 1}"


# --------------------------------------------------------------------------
# Song 2: basement_theme  (D minor, tpr 8, 16th grid, 4 bars per pattern)
# --------------------------------------------------------------------------

def basement_theme():
    s = Song("IT Basement", 8, 64,
             [duty("Lead 50%", 2, 10, sweep=-1), duty("Pluck 12.5%", 0, 8, sweep=-6),
              duty("Drip 12.5%", 0, 9, sweep=-7), duty("Harmony 25%", 1, 6, sweep=-1)],
             [wave_inst("Bouncy bass", 2)])
    lead, pluck, bass, drm = s.tracks
    bar = 16

    # Chords per bar (root, quality). 7 patterns x 4 bars.
    prog = [
        ("D", "m"), ("C", "M"), ("Bb", "M"), ("A", "7"),     # P0 intro
        ("D", "m"), ("C", "M"), ("Bb", "M"), ("A", "7"),     # P1 A
        ("D", "m"), ("C", "M"), ("Bb", "A"), ("D", "m"),     # P2 A'  (bar 3 = Bb | A7)
        ("Bb", "M"), ("C", "M"), ("A", "m"), ("D", "m"),     # P3 B
        ("G", "m"), ("C", "M"), ("F", "M"), ("A", "7"),      # P4 B'
        ("D", "m"), ("C", "M"), ("Bb", "M"), ("A", "7"),     # P5 A + harmony
        ("G", "m"), ("A", "7"), ("D", "m"), ("A", "7"),      # P6 turnaround
    ]

    hook_a = """
      D5:2 F5:2 A5:4 G#5:2 A5:2 r:4
      G5:2 E5:2 C5:4 r:2 E5:2 G5:2 E5:2
      F5:2 D5:2 Bb4:4 r:2 C5:2 D5:2 F5:2
      E5:6 C#5:2 A4:4 r:4
    """
    hook_a2 = """
      D5:2 F5:2 A5:4 G#5:2 A5:2 D6:4
      C6:2 Bb5:2 A5:2 G5:2 E5:4 C5:4
      D5:4 F5:4 E5:4 C#5:4
      D5:8 r:8
    """
    part_b = """
      F5:2 F5:2 G5:2 A5:2 Bb5:4 A5:2 G5:2
      E5:2 E5:2 F5:2 G5:2 C6:6 r:2
      A5:2 G5:2 E5:2 C5:2 E5:4 A5:4
      F5:4 E5:2 D5:2 A4:8
      Bb5:2 A5:2 G5:2 D5:2 G5:4 Bb5:4
      C6:2 Bb5:2 G5:2 E5:2 C5:8
      A5:4 F5:2 C5:2 F5:2 A5:2 C6:4
      C#6:4 A5:2 E5:2 G5:4 C#5:4
    """
    turnaround = """
      G5:2 Bb5:2 D6:4 C6:2 Bb5:2 A5:4
      G5:2 E5:2 C#5:4 E5:2 G5:2 Bb5:4
      A5:4 F5:4 D5:4 r:4
      E5:2 F5:2 E5:2 D5:2 C#5:4 A4:4
    """
    P = 4 * bar
    _len(hook_a, 4 * bar)
    melody(lead, 1 * P, hook_a, 0, vib=0x21, vib_after=4, cut_gap=5)
    _len(hook_a2, 4 * bar)
    melody(lead, 2 * P, hook_a2, 0, vib=0x21, vib_after=4, cut_gap=5)
    _len(part_b, 8 * bar)
    melody(lead, 3 * P, part_b, 0, vib=0x21, vib_after=4, cut_gap=5)
    _len(hook_a, 4 * bar)
    melody(lead, 5 * P, hook_a, 0, vib=0x21, vib_after=4, cut_gap=5)
    _len(turnaround, 4 * bar)
    melody(lead, 6 * P, turnaround, 0, vib=0x21, vib_after=4, cut_gap=5)

    # Intro: water drips on the 12.5% channel (sparse, a little lonely).
    drips = """
      r:6 A5:4 D6:6
      r:8 E6:2 C6:6
      r:6 F5:4 D6:6
      r:4 E6:2 C#6:2 A5:8
    """
    _len(drips, 4 * bar)
    melody(lead, 0, drips, 2)

    # Harmony a diatonic third below the hook in the reprise (P5).
    harm = """
      Bb4:2 D5:2 F5:4 E5:2 F5:2 r:4
      E5:2 C5:2 G4:4 r:2 C5:2 E5:2 C5:2
      D5:2 Bb4:2 F4:4 r:2 A4:2 Bb4:2 D5:2
      C#5:6 A4:2 E4:4 r:4
    """
    _len(harm, 4 * bar)
    melody(pluck, 5 * P, harm, 3, cut_gap=5)

    # Offbeat plucks (arpeggiated triads) everywhere except the harmony reprise.
    arps = {"m": 0x37, "M": 0x47, "7": 0x47}
    for b, (r, q) in enumerate(prog):
        if 5 * 4 <= b < 6 * 4:
            continue
        for off in (2, 6, 10, 14):
            rr, qq = r, q
            if q == "A":  # split bar Bb | A7
                rr, qq = ("Bb", "M") if off < 8 else ("A", "7")
            root = midi(rr + "4")
            if root > midi("G4"):
                root -= 12
            chord_stab(pluck, b * bar + off, _name(root), arps[qq], 1, rows=1)

    # Bouncy octave bass (staccato 8ths) with a chromatic pickup into the next bar.
    def low(r):
        m = midi(r + "2")
        return m - 12 if m > midi("A2") else m

    for b, (r, q) in enumerate(prog):
        halves = [("Bb", "M"), ("A", "7")] if q == "A" else [(r, q), (r, q)]
        for h, (rr, _) in enumerate(halves):
            root = low(rr)
            for k, m in enumerate([root, root + 12, root + 7, root + 12]):
                bass.put(b * bar + h * 8 + k * 2, wave_idx(m), 0, FX_CUT, 4)
        target = low(prog[(b + 1) % len(prog)][0])
        bass.put(b * bar + 14, wave_idx(target + 12 + (1 if b % 2 else -1)), 0, FX_CUT, 4)

    # Drums: kick 1 & 3 (+ the "and" of 3), snare 2 & 4, hats on offbeats.
    for b in range(len(prog)):
        pat = "K.h.S.h.K.hKS.ht"
        if b < 4:
            pat = "K...t.h.K...t.h." if b < 3 else "K...t.h.K.K.SsSs"
        elif b % 8 == 7:
            pat = "K.h.S.h.K.SsS.SS"
        elif b % 4 == 3:
            pat = "K.h.S.h.K.hKSsht"
        drums(drm, b * bar, pat)
    s.total_rows = len(prog) * bar
    return s


# --------------------------------------------------------------------------
# Song 3: boss_theme  (E minor, tpr 5, 16th grid, 4 bars per pattern)
# --------------------------------------------------------------------------

def boss_theme():
    s = Song("The Printer", 5, 64,
             [duty("Lead 50%", 2, 11), duty("Chug 25%", 1, 7, sweep=-5),
              duty("Alarm 12.5%", 0, 10), duty("Harmony 25%", 1, 7, sweep=-1)],
             [wave_inst("Saw bass", 3)])
    lead, chug, bass, drm = s.tracks
    bar = 16
    P = 4 * bar

    prog = [
        ("E", "m"), ("E", "m"), ("C", "M"), ("B", "M"),          # P0 intro (alarm)
        ("E", "m"), ("C", "M"), ("D", "M"), ("B", "M"),          # P1 A
        ("E", "m"), ("C", "M"), ("A", "x"), ("E", "m"),          # P2 A' (bar 3 = Am | B)
        ("C", "M"), ("D", "M"), ("E", "m"), ("E", "m"),          # P3 B
        ("A", "m"), ("B", "M"), ("C", "M"), ("B", "7"),          # P4 B'
        ("E", "m"), ("F", "M"), ("E", "m"), ("B", "M"),          # P5 printer jam bridge
    ]

    intro = """
      E6:2 r:2 F6:2 r:2 E6:2 r:2 F6:2 r:2
      E6:2 r:2 F6:2 r:2 E6:2 r:2 F6:2 r:2
      E6:2 r:2 F6:2 r:2 E6:2 r:2 F6:2 r:2
      B5:4 D#6:4 F#6:4 r:4
    """
    a1 = """
      E5:4 G5:4 B5:4 A#5:2 B5:2
      C6:6 B5:2 G5:4 E5:4
      F#5:4 A5:4 D6:4 C6:2 A5:2
      B5:8 D#5:4 F#5:4
    """
    a2 = """
      E5:4 G5:4 B5:4 E6:4
      D6:2 C6:2 B5:2 A5:2 G5:4 E5:4
      A5:4 C6:4 B5:4 D#6:4
      E6:8 r:4 B4:2 D5:2
    """
    b = """
      G5:2 G5:2 E5:2 G5:2 C6:8
      A5:2 A5:2 F#5:2 A5:2 D6:8
      B5:4 G5:4 E5:4 G5:4
      B5:16
      C6:4 B5:4 A5:4 E5:4
      F#5:4 A5:4 B5:4 D#6:4
      E6:4 D6:4 C6:4 G5:4
      A5:4 F#5:4 D#5:4 B4:4
    """
    jam = """
      E6:2 r:2 F6:2 r:2 E6:2 r:2 F6:2 r:2
      F6:2 r:2 E6:2 r:2 F6:2 r:2 G6:2 r:2
      E5:2 F#5:2 G5:2 A5:2 B5:2 C6:2 D6:2 D#6:2
      E6:2 F#6:2 D#6:2 B5:2 F#5:2 D#5:2 B4:4
    """
    _len(intro, 4 * bar)
    melody(lead, 0, intro, 2)
    _len(a1, 4 * bar)
    melody(lead, 1 * P, a1, 0, vib=0x42, vib_after=4)
    _len(a2, 4 * bar)
    melody(lead, 2 * P, a2, 0, vib=0x42, vib_after=4)
    _len(b, 8 * bar)
    melody(lead, 3 * P, b, 0, vib=0x42, vib_after=4)
    _len(jam, 4 * bar)
    melody(lead, 5 * P, jam, 2, cut_gap=0)
    # bars 3-4 of the jam run use the lead voice
    for r in range(5 * P + 2 * bar, 6 * P):
        c = lead.cells.get(r)
        if c and c[0] is not None:
            c[1] = 0

    # Harmony in the second half of the B section: the lead a 3rd lower, down an octave.
    harm = """
      A4:4 G4:4 E4:4 C4:4
      D#4:4 F#4:4 F#4:4 B4:4
      C5:4 B4:4 G4:4 E4:4
      F#4:4 D#4:4 B3:4 F#3:4
    """
    _len(harm, 4 * bar)
    melody(chug, 4 * P, harm, 3)

    # Chug: arpeggiated power chords on every beat (skipped while harmony plays).
    arps = {"m": 0x37, "M": 0x47, "7": 0x4A, "x": 0x37}
    for bi, (r, q) in enumerate(prog):
        if 16 <= bi < 20:
            continue
        for beat in range(4):
            rr, qq = r, q
            if q == "x":
                rr, qq = ("A", "m") if beat < 2 else ("B", "M")
            root = midi(rr + "4")
            if root > midi("A4"):
                root -= 12
            chord_stab(chug, bi * bar + beat * 4, _name(root), arps[qq], 1, rows=3)

    # Galloping saw bass: 8th notes with an octave hop.
    for bi, (r, q) in enumerate(prog):
        for half in range(2):
            rr = r
            if q == "x":
                rr = "A" if half == 0 else "B"
            root = midi(rr + "2")
            if root > midi("F#2"):
                root -= 12
            for k, m in enumerate([root, root, root + 12, root]):
                bass.put(bi * bar + half * 8 + k * 2, wave_idx(m), 0, FX_CUT, 4)

    # Drums: driving rock beat; intro is kick-only "machine" pulse; fills every 4th bar.
    for bi in range(len(prog)):
        if bi < 3:
            pat = "K.h.K.h.K.h.K.hh"
        elif bi == 3:
            pat = "K.S.K.S.KSKSSsSs"
        elif bi % 4 == 3:
            pat = "K.hhS.hKK.hhSsSs"
        else:
            pat = "K.h.S.hKK.h.S.h."
        if bi in (4, 12):
            pat = "C" + pat[1:]
        drums(drm, bi * bar, pat)
    s.total_rows = len(prog) * bar
    s.jumps[5] = 1  # after the jam, loop back to A (skip the intro)
    return s


# --------------------------------------------------------------------------
# Song 4: fanfare  (C major, tpr 5, plays once then stays silent)
# --------------------------------------------------------------------------

def fanfare():
    s = Song("Item Get", 5, 64,
             [duty("Fanfare 50%", 2, 12, sweep=-1), duty("Fanfare 25%", 1, 9, sweep=-1)],
             [wave_inst("Warm bass", 4)])
    lead, harm, bass, drm = s.tracks
    melody(lead, 0, "G4:2 C5:2 E5:2 G5:2 Ab5:4 Bb5:4 C6:24 r:4", 0, vib=0x32, vib_after=6)
    melody(harm, 0, "E4:2 G4:2 C5:2 E5:2 Eb5:4 F5:4 E5:24 r:4", 1)
    melody(bass, 0, "C3:8 Ab2:4 Bb2:4 C3:20 r:4", 0)
    drums(drm, 0, "K.......ssssSSSSC...............")
    # Pattern 1 is empty and jumps to itself, so the song ends in silence.
    s.total_rows = 128
    s.jumps[1] = 1
    return s


# --------------------------------------------------------------------------
# Song 5: break_room_theme  (G major bossa, tpr 7, 16th grid, 4 bars per pattern)
# --------------------------------------------------------------------------

BREAK_KIT = [
    noise("Kick soft", 9, -7, offsets=[27, 14, 6, -2, -8]),  # 0 note 24
    noise("Rim click", 8, -7, length=3),                     # 1 note 48
    noise("Shaker", 4, -7, length=3),                        # 2 note 60
    noise("Snare", 10, -6, offsets=[18, 24, 22]),            # 3 note 24
    noise("Crash", 9, -2),                                   # 4 note 50
]
BREAK_DRUM = {"K": (0, 24), "r": (1, 48), "t": (2, 60), "S": (3, 24), "s": (3, 30), "C": (4, 50)}


def break_room_theme():
    s = Song("Break Room", 7, 64,
             [duty("Lead 25%", 1, 10), duty("Comp 50%", 2, 6, sweep=-5),
              duty("Harmony 12.5%", 0, 7, sweep=-1)],
             [wave_inst("Round bass", 1)],
             BREAK_KIT)
    lead, comp, bass, drm = s.tracks
    bar = 16
    P = 4 * bar

    # One chord per half bar (root, quality). 7 patterns x 4 bars.
    G, A7, Am, D7, Bm, E7 = ("G", "M7"), ("A", "7"), ("A", "m7"), ("D", "7"), ("B", "m7"), ("E", "7")
    C, Cm, F7, Eb = ("C", "M7"), ("C", "m7"), ("F", "7"), ("Eb", "M7")
    bars = [
        (G, G), (A7, A7), (Am, D7), (G, G),          # P0 A
        (G, G), (A7, A7), (Am, D7), (Bm, E7),        # P1 A'
        (C, C), (Cm, F7), (Bm, Bm), (E7, E7),        # P2 B
        (Am, Am), (D7, D7), (Bm, E7), (Am, D7),      # P3 B'
        (Eb, Eb), (D7, D7), (Eb, Eb), (D7, D7),      # P4 C: the coffee jitters
        (G, G), (A7, A7), (Am, D7), (G, G),          # P5 A + harmony
        (G, G), (A7, A7), (Am, D7), (Am, D7),        # P6 A' turnaround
    ]

    hook = """
      B5:2 B5:1 B5:1 D6:3 B5:3 A5:2 G5:4
      C#6:2 C#6:1 C#6:1 E6:3 C#6:3 B5:2 A5:4
      C6:3 B5:3 A5:2 F#5:3 A5:3 C6:2
      B5:6 r:2 D5:2 E5:2 F#5:2 G5:2
    """
    hook2 = """
      B5:2 B5:1 B5:1 D6:3 B5:3 A5:2 G5:4
      C#6:2 C#6:1 C#6:1 E6:3 G6:3 F#6:2 E6:4
      E6:3 C6:3 A5:2 D6:3 C6:3 A5:2
      F#5:4 D5:4 G#5:4 B5:4
    """
    bridge = """
      E6:3 D6:3 B5:2 G5:6 r:2
      Eb6:3 D6:3 C6:2 A5:3 Eb6:3 C6:2
      D6:4 F#5:2 A5:2 B5:6 r:2
      G#5:2 G#5:1 G#5:1 B5:3 D6:3 E6:6
      C6:2 C6:1 C6:1 E6:3 C6:3 A5:2 G5:4
      F#5:2 F#5:1 F#5:1 A5:3 C6:3 D6:4 r:2
      D6:3 B5:3 A5:2 G#5:3 B5:3 D6:2
      C6:4 A5:4 F#5:2 A5:2 D6:4
    """
    jitters = """
      G5:1 Bb5:1 G5:1 Bb5:1 D6:2 r:2 G5:1 Bb5:1 G5:1 Bb5:1 D6:2 r:2
      F#5:1 A5:1 F#5:1 A5:1 C6:2 r:2 F#5:1 A5:1 F#5:1 A5:1 C6:4
      Bb5:1 D6:1 Bb5:1 D6:1 G6:4 D6:2 Eb6:2 D6:2 Bb5:2
      A5:2 C6:2 F#6:4 E6:2 D6:2 C6:2 A5:2
    """
    ending = """
      B5:2 B5:1 B5:1 D6:3 B5:3 A5:2 G5:4
      C#6:2 C#6:1 C#6:1 E6:3 G6:3 F#6:2 E6:4
      E6:3 C6:3 A5:2 D6:3 C6:3 A5:2
      C6:4 A5:4 F#5:2 A5:2 C6:2 D6:2
    """
    harm = """
      G5:2 G5:1 G5:1 B5:3 G5:3 F#5:2 E5:4
      A5:2 A5:1 A5:1 C#6:3 A5:3 G5:2 E5:4
      A5:3 G5:3 E5:2 D5:3 F#5:3 A5:2
      G5:6 r:2 B4:2 C5:2 D5:2 E5:2
    """
    for start, text, rows in ((0, hook, 4), (P, hook2, 4), (2 * P, bridge, 8),
                              (4 * P, jitters, 4), (5 * P, hook, 4), (6 * P, ending, 4)):
        _len(text, rows * bar)
        melody(lead, start, text, 0, vib=0x51, vib_after=3, cut_gap=5)
    _len(harm, 4 * bar)
    melody(comp, 5 * P, harm, 2, cut_gap=5)

    third = {"M7": 4, "7": 4, "m7": 3}
    arp = {"M7": 0x37, "7": 0x36, "m7": 0x47}

    def shell(r, q):
        m = midi(r + "4") + third[q]
        while m > midi("C5"):
            m -= 12
        while m < midi("E4"):
            m += 12
        return _name(m)

    # Bossa comp: syncopated stabs (rows 0, 3, 6 | 10, 12 of the bar), skipped under harmony.
    for b, halves in enumerate(bars):
        if 20 <= b < 24:
            continue
        for row in (0, 3, 6, 10, 12):
            r, q = halves[0] if row < 8 else halves[1]
            chord_stab(comp, b * bar + row, shell(r, q), arp[q], 1, rows=2)

    # Bass: root (dotted quarter) then fifth, per half bar.
    def low(r):
        m = midi(r + "2")
        return m - 12 if m > midi("B2") else m

    for b, halves in enumerate(bars):
        for h, (r, q) in enumerate(halves):
            root = low(r)
            fifth = root + 7 if root + 7 <= midi("D3") else root - 5
            bass.put(b * bar + h * 8, wave_idx(root), 0)
            bass.fx(b * bar + h * 8 + 5, FX_CUT, 5)
            bass.put(b * bar + h * 8 + 6, wave_idx(fifth), 0, FX_CUT, 6)

    # Drums: kick 1 & 3, rim clave, jittery 16th shaker.
    for b in range(len(bars)):
        pat = "KttrttrtKtrtrttt"
        if 16 <= b < 20:
            pat = "KtSrtSrtKtSrSsSs" if b == 19 else "KtSrtSrtKtSrSttt"
        elif b % 4 == 3:
            pat = "KttrttrtKtrtSsSs"
        if b in (0, 8, 20):
            pat = "C" + pat[1:]
        drums(drm, b * bar, pat, kit=BREAK_DRUM)
    s.total_rows = len(bars) * bar
    return s


# --------------------------------------------------------------------------
# Song 6: espresso_boss_theme  (C minor 12/8 shuffle, tpr 6, 3 rows per beat,
#         4 bars per 48-row pattern; intro plays once)
# --------------------------------------------------------------------------

ESPRESSO_KIT = [
    noise("Kick", 12, -7, offsets=[27, 14, 6, -2, -8]),     # 0 note 24
    noise("Snare", 11, -6, offsets=[18, 24, 22]),           # 1 note 24
    noise("Gurgle", 7, -7, length=6, offsets=[10, 4, -2]),  # 2 note 30: low "blub"
    noise("Steam tss", 8, -6, length=14),                   # 3 note 63
    noise("Steam hiss", 10, -1),                            # 4 note 62 (long, cut it)
    noise("Crash", 10, -2),                                 # 5 note 50
]
ESPRESSO_DRUM = {"K": (0, 24), "S": (1, 24), "s": (1, 30), "b": (2, 30), "B": (2, 26),
                 "x": (3, 63), "H": (4, 62), "C": (5, 50)}
# "Squelch" wave: a fat pulse with a sagging top, for the percolating bass.
ESPRESSO_WAVES = WAVES + [[15, 15, 14, 13, 12, 11, 10, 9, 8, 7, 7, 6, 6, 5, 5, 4]
                          + [0, 0, 1, 1, 2, 2, 3, 3, 3, 2, 2, 1, 1, 0, 0, 0]]


def espresso_boss_theme():
    s = Song("Sentient Espresso", 6, 48,
             [duty("Lead 12.5%", 0, 11), duty("Bubbles 25%", 1, 6, sweep=-7),
              duty("Whistle 50%", 2, 10), duty("Harmony 25%", 1, 7, sweep=-1)],
             [wave_inst("Squelch bass", len(WAVES))],
             ESPRESSO_KIT)
    s.waves = ESPRESSO_WAVES
    lead, bub, bass, drm = s.tracks
    bar = 12
    P = 4 * bar

    prog = [
        "Cm", "Cm", "Cm", "G",       # P0 intro (steam whistle)
        "Cm", "Ab", "Fm", "G",       # P1 A
        "Cm", "Ab", "FmG", "Cm",     # P2 A'
        "Eb", "Bb", "Ab", "G",       # P3 B
        "Fm", "G", "Ab", "G",        # P4 B'
        "Cm", "Db", "Cm", "G",       # P5 C: steam valve breakdown
        "Cm", "Ab", "FmG", "Cm",     # P6 A' + harmony
    ]
    chord = {"Cm": ("C", 3), "Ab": ("Ab", 4), "Fm": ("F", 3), "G": ("G", 4), "Eb": ("Eb", 4),
             "Bb": ("Bb", 4), "Db": ("Db", 4)}

    intro = """
      r:6 G6:6
      _:12
      r:6 Ab6:3 G6:3
      F6:3 D6:3 B5:6
    """
    a1 = """
      G5:1 Ab5:1 G5:1 Eb5:3 C5:3 G5:3
      Ab5:1 Bb5:1 Ab5:1 Eb5:3 C5:3 Ab5:3
      F5:3 Ab5:3 C6:3 Bb5:2 Ab5:1
      B5:6 D6:3 F6:3
    """
    a2 = """
      C6:1 D6:1 C6:1 G5:3 Eb5:3 C6:3
      C6:1 Db6:1 C6:1 Ab5:3 Eb5:3 C6:3
      Ab5:3 F5:3 B5:3 D6:3
      C6:6 r:3 G5:1 Ab5:1 B5:1
    """
    b = """
      Bb5:2 G5:1 Bb5:2 G5:1 Eb6:6
      D6:2 Bb5:1 D6:2 Bb5:1 F6:6
      Eb6:2 C6:1 Ab5:2 C6:1 Eb6:3 F6:3
      D6:3 B5:3 G5:3 F5:3
      F5:2 Ab5:1 C6:2 F6:1 Eb6:3 C6:3
      D6:2 B5:1 G5:2 B5:1 D6:3 F6:3
      Eb6:3 C6:3 Ab5:3 C6:3
      B5:1 C6:1 D6:1 F6:3 B5:3 G5:3
    """
    breakdown = """
      G6:9 r:3
      Ab6:9 r:3
      G6:3 F6:3 Eb6:3 D6:3
      B5:3 C6:1 D6:1 Eb6:1 F6:3 G6:3
    """
    harm = """
      Ab5:1 Bb5:1 Ab5:1 Eb5:3 C5:3 Ab5:3
      Ab5:1 Bb5:1 Ab5:1 F5:3 C5:3 Ab5:3
      F5:3 C5:3 G5:3 B5:3
      G5:6 r:3 Eb5:1 F5:1 G5:1
    """
    _len(intro, 4 * bar)
    melody(lead, 0, intro, 2, vib=0x44, vib_after=2)
    for start, text, rows in ((P, a1, 4), (2 * P, a2, 4), (3 * P, b, 8), (6 * P, a2, 4)):
        _len(text, rows * bar)
        melody(lead, start, text, 0, vib=0x42, vib_after=3)
    _len(breakdown, 4 * bar)
    melody(lead, 5 * P, breakdown, 2, vib=0x44, vib_after=2)
    _len(harm, 4 * bar)
    melody(bub, 6 * P, harm, 3)

    def tones(name, half):
        if name == "FmG":
            name = "Fm" if half == 0 else "G"
        r, third = chord[name]
        return r, third

    # Percolator bubbles: short blips on the 2nd and 3rd triplet of every beat,
    # walking up and down the chord like water bubbling through the grounds.
    shape = [0, 7, 12, 7, 3, 12, 7, 0]
    for bi, name in enumerate(prog):
        if 24 <= bi < 28:
            continue
        for beat in range(4):
            r, third = tones(name, beat // 2)
            root = midi(r + "4")
            if root > midi("G4"):
                root -= 12
            for k, row in enumerate((1, 2)):
                iv = shape[(beat * 2 + k + bi) % len(shape)]
                iv = third if iv == 3 else iv
                bub.put(bi * bar + beat * 3 + row, pulse_idx(root + 12 + iv), 1)

    # Squelchy shuffle bass: root on the beat, octave on the last triplet.
    for bi, name in enumerate(prog):
        for beat in range(4):
            r, _ = tones(name, beat // 2)
            root = midi(r + "2")
            if root > midi("G2"):
                root -= 12
            bass.put(bi * bar + beat * 3, wave_idx(root), 0, FX_CUT, 8)
            bass.put(bi * bar + beat * 3 + 2, wave_idx(root + 12), 0, FX_CUT, 4)

    # Drums: kick/snare backbeat with gurgles in between; steam hiss "tss tss TSSSS"
    # closes every 4-bar phrase and fills the breakdown.
    hiss_bar = "x..x..H....."
    for bi in range(len(prog)):
        if bi < 4:
            pat = ["Kbb.bbKbb.bB", hiss_bar, "Kbb.bbKbb.bB", "Kbb.bbx..x.."][bi]
        elif 20 <= bi < 24:
            pat = [hiss_bar, "x..x..H.....", "KbbSbbKbbSbb", "KbbSbbSsSsSs"][bi - 20]
        elif bi % 4 == 3:
            pat = "KbbSbbx..x.."
        else:
            pat = "KbbSbbKbBSbb"
        if bi in (4, 12, 24):
            pat = "C" + pat[1:]
        drums(drm, bi * bar, pat, kit=ESPRESSO_DRUM)
        # cut the long hiss after 5 rows so it does not smear into the next bar
        if "H" in pat:
            drm.fx(bi * bar + pat.index("H") + 5, FX_CUT, 0)
    s.total_rows = len(prog) * bar
    s.jumps[6] = 1  # loop to A, skipping the intro
    return s


SONGS = {
    "office_theme": office_theme,
    "basement_theme": basement_theme,
    "boss_theme": boss_theme,
    "fanfare": fanfare,
    "break_room_theme": break_room_theme,
    "espresso_boss_theme": espresso_boss_theme,
}

# Preview render lengths (seconds): two loops of the short songs, ~a minute max.
PREVIEW_SECONDS = {"office_theme": 45, "basement_theme": 59, "boss_theme": 40, "fanfare": 6,
                   "break_room_theme": 54, "espresso_boss_theme": 40}


# --------------------------------------------------------------------------
# Verification helpers (need /tmp/gbs-src, node, PyBoy)
# --------------------------------------------------------------------------

UGE_BUNDLE = Path("/tmp/ugetools/uge.js")


def ensure_uge_bundle():
    if UGE_BUNDLE.exists():
        return
    UGE_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    entry = UGE_BUNDLE.parent / "entry.ts"
    entry.write_text('export { loadUGESong, saveUGESong } from "shared/lib/uge/ugeHelper";\n')
    subprocess.run([str(GBS_SRC / "node_modules/.bin/esbuild"), str(entry), "--bundle",
                    "--platform=node", "--format=cjs", f"--tsconfig={GBS_SRC / 'tsconfig.json'}",
                    f"--outfile={UGE_BUNDLE}", "--log-level=warning"], check=True, cwd=GBS_SRC)


def verify(paths):
    ensure_uge_bundle()
    js = r"""
const {loadUGESong, saveUGESong} = require(process.argv[1]);
const fs = require('fs');
let ok = true;
for (const f of process.argv.slice(2)) {
  const buf = fs.readFileSync(f);
  const song = loadUGESong(buf);
  const again = saveUGESong(song);
  const same = Buffer.compare(buf, again) === 0;
  ok = ok && same;
  const rows = song.sequence.length;
  console.log(`${f.split('/').pop()}: v${song.version} tpr=${song.ticksPerRow} orders=${rows} ` +
              `patterns=${song.patterns.length} roundtrip=${same ? 'identical' : 'DIFFERENT'}`);
}
process.exit(ok ? 0 : 1);
"""
    subprocess.run(["node", "-e", js, str(UGE_BUNDLE)] + [str(p) for p in paths], check=True)


def gbsres(obj):
    return json.dumps(obj, indent=2) + "\n"


def build_test_rom(song_name):
    """Copy the project template, add one scene that plays the song, compile."""
    proj = TEST_DIR / song_name
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(ROOT / "tools" / "gbs_template", proj)
    (proj / "project.gbsproj").write_text(
        (proj / "project.gbsproj").read_text().replace("___PROJECT_NAME___", "musictest")
        .replace("___AUTHOR___", "make_music"))
    ns = uuid.UUID("6b1d7c1e-4a8c-4c8e-9a51-7b0f6a3f1c00")
    bg_id = str(uuid.uuid5(ns, "bg"))
    music_id = str(uuid.uuid5(ns, song_name))
    scene_id = str(uuid.uuid5(ns, "scene"))
    shutil.copy(ROOT / "assets/backgrounds/basement_stairwell.png", proj / "assets/backgrounds/stairwell.png")
    (proj / "assets/backgrounds/stairwell.png.gbsres").write_text(gbsres({
        "_resourceType": "background", "id": bg_id, "name": "stairwell",
        "symbol": "bg_stairwell", "filename": "stairwell.png", "width": 20, "height": 18,
        "imageWidth": 160, "imageHeight": 144, "tileColors": "", "autoColor": False}))
    shutil.copy(OUT_DIR / f"{song_name}.uge", proj / f"assets/music/{song_name}.uge")
    (proj / f"assets/music/{song_name}.uge.gbsres").write_text(gbsres({
        "_resourceType": "music", "id": music_id, "name": song_name,
        "symbol": f"song_{song_name}", "settings": {}, "filename": f"{song_name}.uge",
        "type": "uge"}))
    scene_dir = proj / "project/scenes/test"
    scene_dir.mkdir(parents=True, exist_ok=True)
    (scene_dir / "scene.gbsres").write_text(gbsres({
        "_resourceType": "scene", "id": scene_id, "_index": 0, "type": "TOPDOWN",
        "name": "Test", "symbol": "scene_test", "x": 0, "y": 0, "width": 20, "height": 18,
        "backgroundId": bg_id, "tilesetId": "", "colorModeOverride": "none",
        "paletteIds": [], "spritePaletteIds": [], "autoFadeSpeed": 1,
        "script": [{"id": str(uuid.uuid5(ns, "play")), "command": "EVENT_MUSIC_PLAY",
                    "args": {"musicId": music_id, "loop": True}}],
        "playerHit1Script": [], "playerHit2Script": [], "playerHit3Script": [],
        "collisions": ""}))
    settings_path = proj / "project/settings.gbsres"
    settings = json.loads(settings_path.read_text())
    settings["startSceneId"] = scene_id
    settings_path.write_text(gbsres(settings))
    rom = proj / "out.gb"
    env = dict(os.environ, TMPDIR=str(TEST_DIR / "tmp" / song_name))
    Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    subprocess.run(["node", str(GBS_SRC / "out/cli/gb-studio-cli.js"), "make:rom",
                    str(proj / "project.gbsproj"), str(rom)], check=True, env=env,
                   stdout=subprocess.DEVNULL)
    return rom


RENDER_PY = r"""
import sys, wave, numpy as np
from pyboy import PyBoy
rom, out, seconds = sys.argv[1], sys.argv[2], float(sys.argv[3])
rate = 24000
pb = PyBoy(rom, window="null", sound_emulated=True, sound_sample_rate=rate, cgb=True)
pb.set_emulation_speed(0)
chunks = []
for _ in range(int(seconds * 59.7275) + 30):
    pb.tick(1, False, True)
    chunks.append(pb.sound.ndarray.copy())
pb.stop(save=False)
audio = np.concatenate(chunks).astype(np.int16)
nz = np.nonzero(np.abs(audio).max(axis=1) > 0)[0]
start = max(0, nz[0] - 200) if len(nz) else 0  # trim boot silence
audio = audio[start:start + int(seconds * rate)]
peak = int(np.abs(audio).max())
pcm = (audio.mean(axis=1) * 256).clip(-32768, 32767).astype(np.int16)  # mono: the mix is centred
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())
mono = audio.mean(axis=1)
rms = float(np.sqrt((mono ** 2).mean()))
sec = [float(np.sqrt((mono[i:i + rate] ** 2).mean())) for i in range(0, len(mono) - rate + 1, rate)]
silent_secs = sum(1 for v in sec if v < 1)
print(f"len={len(audio)/rate:.1f}s peak={peak}/127 rms={rms:.1f} clipped={int((np.abs(audio) >= 127).sum())} "
      f"silent_seconds={silent_secs} sec_rms_min={min(sec) if sec else 0:.1f}")
"""


def render(song_name, rom):
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = PREVIEW_DIR / f"{song_name}.wav"
    script = TEST_DIR / "render.py"
    script.write_text(RENDER_PY)
    res = subprocess.run(["/tmp/pyboy-venv/bin/python", str(script), str(rom), str(out),
                          str(PREVIEW_SECONDS[song_name])], check=True, capture_output=True, text=True)
    print(f"{song_name}.wav: {res.stdout.strip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--previews", action="store_true")
    ap.add_argument("songs", nargs="*", default=list(SONGS))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in args.songs:
        song = SONGS[name]()
        path = OUT_DIR / f"{name}.uge"
        blocks, order = write_uge(song, path)
        secs = song.total_rows * song.tpr / DRIVER_HZ
        print(f"{path.relative_to(ROOT)}: {len(order)} orders, {len(blocks)} unique patterns, "
              f"tpr {song.tpr}, {secs:.1f} s per pass")
        paths.append(path)
    if args.verify or args.previews:
        verify(paths)
    if args.previews:
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        for name in args.songs:
            render(name, build_test_rom(name))


if __name__ == "__main__":
    sys.exit(main())
