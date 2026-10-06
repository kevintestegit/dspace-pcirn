#!/usr/bin/env python3
"""
Build the soundtrack for the DSpace motion piece. Synthesis only, no samples.

Everything is placed on the same 60-beat, 120 BPM grid the animation is scored
against: beat n starts at (n-1) * 0.5 s. Kick, snare, hats, bass and the chord
bed are all written from that grid, and the interface sounds are placed at the
interactions in the score -- each one positioned by its own measured peak, not by
a guessed offset, so a click lands on the downbeat it belongs to.

  .venv/bin/python make_audio.py            -> out/audio.wav
"""
import os, math, struct, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SR = 48000
BPM = 120
BEAT = 60.0 / BPM            # 0.5 s, the same constant the animation uses
BEATS = 60                   # 30 s
DUR = BEATS * BEAT
N = int(SR * DUR)
T = np.arange(N) / SR

rng = np.random.default_rng(20240917)


def env(n, attack, decay, curve=2.0):
    """Percussive envelope: short attack, exponential-ish tail."""
    a = np.minimum(np.arange(n) / max(1.0, attack * SR), 1.0)
    d = np.exp(-curve * np.arange(n) / max(1.0, decay * SR))
    return a * d


def place(buf, x, at):
    """Add x into buf at time `at`, clipping at the edges."""
    i = int(round(at * SR))
    if i >= len(buf):
        return
    j = min(len(buf) - i, len(x))
    buf[i:i + j] += x[:j]


# ---------------------------------------------------------------- instruments

def kick():
    """Sine body with a pitch drop, a click transient, and a short tail."""
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    f = 52 + 92 * np.exp(-t / 0.026)                 # 143 Hz -> 52 Hz
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env(n, 0.0015, 0.20, 2.6)
    click = rng.standard_normal(n) * env(n, 0.0004, 0.006, 3.0) * 0.16
    return body * 0.92 + click


def snare():
    """Restrained: a short noise burst over a soft body, no crack."""
    n = int(0.20 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(48) / 48, mode="same")   # thin it out
    body = np.sin(2 * np.pi * 186 * t) * env(n, 0.001, 0.055, 3.0)
    top = noise * env(n, 0.0006, 0.048, 3.2)
    return (body * 0.16 + top * 0.30) * 0.62


def hat(open_=False):
    n = int((0.16 if open_ else 0.055) * SR)
    noise = rng.standard_normal(n)
    hp = noise - np.convolve(noise, np.ones(24) / 24, mode="same")
    return hp * env(n, 0.0004, 0.030 if not open_ else 0.075, 3.4) * (0.10 if not open_ else 0.075)


def bass(freq, dur):
    """A sine with one soft harmonic and a gentle release."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = np.minimum(t / 0.012, 1.0) * np.exp(-t / (dur * 0.55))
    return (np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(4 * np.pi * freq * t)) * e * 0.30


def chord(freqs, dur):
    """Soft bed: detuned partials, slow attack, long release."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = np.minimum(t / (dur * 0.30), 1.0)
    r = np.minimum((dur - t) / (dur * 0.45), 1.0)
    out = np.zeros(n)
    for k, f in enumerate(freqs):
        for det in (-0.16, 0.16):
            out += np.sin(2 * np.pi * (f + det) * t) * (0.055 / (1 + k * 0.35))
    return out * a * np.clip(r, 0, 1)


# ------------------------------------------------- interface sound design
# One short voice per interaction. Each returns (samples, peak_offset_seconds);
# events are placed by that measured peak so the transient, not the tail, is what
# lands on the beat.

def _burst(freqs, decay, seed, tilt=1.0):
    n = int(decay * 4 * SR)
    t = np.arange(n) / SR
    e = np.exp(-t / decay)
    g = np.random.default_rng(seed).standard_normal(n)
    g = g - np.convolve(g, np.ones(16) / 16, mode="same")
    x = np.zeros(n)
    for f in freqs:
        x += np.sin(2 * np.pi * f * t) * e * tilt
    x += g * e * 0.10 * tilt
    return x


def voice(kind):
    if kind == "click":                       # press: a dry, low tick
        return _burst([1180, 2360], 0.011, 11, 1.0)
    if kind == "select":                      # hover: the softest thing here
        return _burst([2050, 4100], 0.020, 12, 0.55)
    if kind == "type":                        # keystroke: small and mid
        return _burst([1620, 3240], 0.014, 13, 0.72)
    if kind == "toggle":                      # filter chip: two-part switch
        x = _burst([880, 2640], 0.016, 14, 0.85)
        y = _burst([1320, 1980], 0.030, 15, 0.60)
        return np.concatenate([x, np.zeros(int(0.012 * SR)), y])
    if kind == "open":                        # preview opening: a filtered swell
        n = int(0.26 * SR)
        t = np.arange(n) / SR
        e = np.minimum(t / 0.05, 1.0) * np.minimum((0.26 - t) / 0.12, 1.0)
        return (np.sin(2 * np.pi * 300 * t) + 0.5 * np.sin(2 * np.pi * 600 * t)) * e * 0.5
    if kind == "download":                    # transfer: a descending pair
        n = int(0.30 * SR)
        t = np.arange(n) / SR
        f = 1500 * np.exp(-t / 0.09) + 520
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.13) * 0.5
    if kind == "palette":                     # cmd-k: a soft rising fifth
        n = int(0.24 * SR)
        t = np.arange(n) / SR
        e = np.minimum(t / 0.02, 1.0) * np.minimum((0.24 - t) / 0.14, 1.0)
        return (np.sin(2 * np.pi * 523 * t) + 0.7 * np.sin(2 * np.pi * 784 * t)) * e * 0.42
    if kind == "enter":                       # submit: one clean confirmation
        n = int(0.34 * SR)
        t = np.arange(n) / SR
        e = np.minimum(t / 0.006, 1.0) * np.exp(-t / 0.11)
        return (np.sin(2 * np.pi * 392 * t) + 0.6 * np.sin(2 * np.pi * 587 * t)) * e * 0.5
    if kind == "toast":                       # success: a warm major third
        n = int(0.52 * SR)
        t = np.arange(n) / SR
        e = np.minimum(t / 0.03, 1.0) * np.exp(-t / 0.26)
        return (np.sin(2 * np.pi * 523.25 * t) + 0.55 * np.sin(2 * np.pi * 659.25 * t)
                + 0.25 * np.sin(2 * np.pi * 1046.5 * t)) * e * 0.42
    raise ValueError(kind)


VOICES = {k: voice(k) for k in
          ("click", "select", "type", "toggle", "open", "download",
           "palette", "enter", "toast")}
PEAK = {k: float(np.argmax(np.abs(v))) / SR for k, v in VOICES.items()}
VOICE_GAIN = {"click": 0.18, "select": 0.13, "type": 0.20, "toggle": 0.18,
              "open": 0.20, "download": 0.36, "palette": 0.26,
              "enter": 0.30, "toast": 0.30}


def ui(kind, at):
    """Place a voice so its own peak lands exactly on `at`."""
    place(track, VOICES[kind] * VOICE_GAIN[kind], at - PEAK[kind])


# ---------------------------------------------------------------- score

track = np.zeros(N)

K, S_, H = kick(), snare(), hat()
HO = hat(True)

# Kick: downbeats, plus a light pickup before each section change. Sparse on
# purpose -- the piece is calm and the visuals carry the weight.
KICKS = {1, 9, 17, 25, 33, 41, 49, 57} | {5, 13, 21, 29, 37, 45, 53}
KICKS |= {3, 11, 19, 27, 35, 43, 51, 59}
SNARES = {6, 14, 22, 30, 38, 46, 54}          # restrained: on the 2 and 4
SNARES |= {8, 16, 24, 32, 40, 48, 56}
for b in sorted(KICKS):
    place(track, K, (b - 1) * BEAT)
for b in sorted(SNARES):
    place(track, S_, (b - 1) * BEAT)

# Hats: eighths, quieter on the offbeat.
for b in range(1, BEATS + 1):
    off = (b - 1) * BEAT + BEAT / 2
    place(track, H * (0.55 if b % 4 == 0 else 0.85), off)
    if b % 8 == 0:
        place(track, HO, (b - 1) * BEAT)

# Bass and chord bed follow a slow four-bar progression in A minor.
ROOT = {"A2": 110.00, "F2": 87.31, "C3": 130.81, "G2": 98.00}
BASS_BEATS = [(1, 1, 3), (9, 1, 3), (17, 2, 2), (25, 3, 2), (33, 1, 3), (41, 2, 2), (49, 3, 2)]
BASS_NOTE = {1: ROOT["A2"], 2: ROOT["F2"], 3: ROOT["C3"]}
for bar, root, length in BASS_BEATS:
    f = BASS_NOTE[root]
    place(track, bass(f, length * BEAT), (bar - 1) * BEAT)
    place(track, bass(f * 2, length * BEAT * 0.5), (bar - 1) * BEAT + BEAT * 1.5)

CHORDS = [
    (1,  [220.00, 261.63, 329.63]),    # Am
    (9,  [174.61, 220.00, 261.63]),    # F
    (17, [196.00, 261.63, 329.63]),    # G
    (25, [130.81, 196.00, 261.63]),    # C
    (33, [220.00, 261.63, 329.63]),    # Am
    (41, [174.61, 220.00, 261.63]),    # F
    (49, [196.00, 261.63, 329.63]),    # G
]
for bar, freqs in CHORDS:
    place(track, chord(freqs, 7.4 * BEAT), (bar - 1) * BEAT)

# ------------------------------------------------ interface events on the grid
# Beat numbers match the animation's score, so a sound and the action that causes
# it share a downbeat.

for b in (1, 8, 13, 14, 18, 21, 28, 37, 40, 55, 58):
    ui("click", (b - 1) * BEAT + BEAT * 0.40)
for b in (7, 10, 11, 12, 16, 19, 20, 22, 23, 25, 27, 29, 30, 31, 32, 33, 36, 39, 49, 52, 54, 57):
    ui("select", (b - 1) * BEAT + BEAT * 0.30)
for b in (2, 3, 4, 5, 6):
    for i in range(3 if b >= 4 else (2 if b == 3 else 1)):
        ui("type", (b - 1) * BEAT + BEAT * 0.10 + i * 0.052)
for b, sub in ((13, 0.36), (14, 0.36)):
    ui("toggle", (b - 1) * BEAT + BEAT * sub)
ui("open", 33 * BEAT - 0.10)
ui("download", 40 * BEAT - 0.14)
ui("palette", 44 * BEAT + 0.26)
ui("enter", 8 * BEAT + 0.54)
ui("toast", 52 * BEAT + 0.10)

# ------------------------------------------------------- sidechain ducking
# Everything but the kick dips briefly after each kick. Computed from the kick
# envelope so the duck follows the actual transient, not a separate grid.

duck = np.ones(N)
DUCK_DEPTH = 0.30
DUCK_HOLD = 0.055
DUCK_REL = 0.165
for b in sorted(KICKS):
    at = (b - 1) * BEAT
    i0 = int(at * SR)
    hold = int(DUCK_HOLD * SR)
    rel = np.exp(-np.arange(int(DUCK_REL * SR)) / (DUCK_REL * 0.45 * SR))
    span = hold + len(rel)
    seg = np.ones(span)
    seg[hold:] = 1 - DUCK_DEPTH * rel
    seg[:hold] = 1 - DUCK_DEPTH * (np.arange(hold) / max(1, hold))
    j1 = min(N, i0 + span)
    duck[i0:j1] = np.minimum(duck[i0:j1], seg[:j1 - i0])

# the kick keeps its own level, so the bed moves and the pulse stays put
kick_bus = np.zeros(N)
for b in sorted(KICKS):
    place(kick_bus, K, (b - 1) * BEAT)
other = track - kick_bus
track = kick_bus * 0.95 + other * duck

# ---------------------------------------------------------------- master

# gentle high shelf off the top, and the whole bed warmed slightly
b, a = 0.86, 0.10
trace = np.zeros(N)
shelved = np.empty(N)
y1 = y2 = 0.0
for i in range(N):
    x = track[i]
    y1 = b * y1 + (1 - b) * x
    y2 = b * y2 + (1 - b) * y1
    trace[i] = y1 - y2 * 0.35
    shelved[i] = x - 0.55 * trace[i]          # take air off the top
mix = 0.86 * shelved + 0.14 * track

# Level to a musical RMS rather than to peak: a sparse, ducked bed has a high crest
# factor, so peak-normalising it would leave the whole piece far too quiet.
rms_in = float(np.sqrt(np.mean(mix ** 2)))
if rms_in > 0:
    mix *= 0.185 / rms_in
# Soft-clip only the top of the range. A blanket tanh would pull the whole bed
# down with the transients and undo the level we just set.
a_mix = np.abs(mix)
KNEE = 0.62
st = np.sign(mix) * np.where(a_mix <= KNEE, a_mix,
                             KNEE + np.tanh((a_mix - KNEE) * 2.4) * 0.355)

stereo = np.stack([st, np.roll(st, 37)], axis=1)   # hair of width on the bed

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "audio.wav")
with wave.open(path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.clip(stereo, -1, 1) * 32767).astype("<i2").tobytes())

rms = float(np.sqrt(np.mean(st ** 2)))
print(f"ok -> {path}")
print(f"{DUR:.1f}s  {BEATS} beats @ {BPM} BPM  peak={np.max(np.abs(st)):.3f}  rms={rms:.3f}")
print("ui voices placed by measured peak:")
for k in sorted(PEAK):
    print(f"  {k:<9} peak at {PEAK[k]*1000:6.2f} ms   gain {VOICE_GAIN[k]:.2f}")
