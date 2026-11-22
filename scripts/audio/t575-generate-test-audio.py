#!/usr/bin/env python3

import math
import struct
import wave
import sys
from pathlib import Path

RATE = 48000

OUT = Path(sys.argv[1] if len(sys.argv) > 1
           else "t575-audio-test-assets")

OUT.mkdir(parents=True, exist_ok=True)

def tone(t, duration, frequency, db):
    amplitude = 32767 * 10 ** (db / 20)
    fade = min(0.05, duration / 2)
    envelope = min(1, t / fade, (duration - t) / fade)
    envelope = max(0, envelope)

    return round(
        amplitude * envelope *
        math.sin(2 * math.pi * frequency * t)
    )

def generate(name, duration, fn):
    target = OUT / name
    frames = bytearray()
    peak = 0

    for i in range(round(RATE * duration)):
        l, r = fn(i / RATE)

        peak = max(peak, abs(l), abs(r))
        assert -32768 <= l <= 32767
        assert -32768 <= r <= 32767

        frames.extend(struct.pack("<hh", l, r))

    with wave.open(str(target), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(frames)

    print(f"{name}: {duration}s peak={peak}")

generate(
    "01-silence.wav",
    2,
    lambda t: (0, 0)
)

def stereo(t):
    if t < 1:
        return tone(t, 1, 1000, -40), 0

    return 0, tone(t - 1, 1, 1500, -40)

generate("02-stereo-identification.wav", 2, stereo)

def short_tone(t):
    v = tone(t, 1, 1000, -30)
    return v, v

generate("03-speaker-tone.wav", 1, short_tone)

def chime(t):
    frequencies = (523.25, 659.25, 783.99)
    section = min(int(t / 0.4), 2)
    local = t - section * 0.4

    v = tone(local, 0.4, frequencies[section], -30)
    return v, v

generate("04-test-chime.wav", 1.2, chime)

print("PASS: deterministic audio assets generated")
