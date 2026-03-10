"""
spank_sound_mic.py — Microphone Impact Detector
================================================
Listens to the microphone for a sudden loud thud/slap.
When detected, plays a sound. Works on ALL laptops — no accelerometer needed.

Install:
    pip install sounddevice numpy pygame

Usage:
    python spank_sound_mic.py
    python spank_sound_mic.py --sound "sound moan.mp3"
    python spank_sound_mic.py --sensitivity 0.3   (0.0–1.0, lower = easier trigger)
"""

import argparse
import math
import os
import sys
import time
import threading
import struct
import random

# ── dependency check ──────────────────────────────────────────────────────────
try:
    import numpy as np
except ImportError:
    print("[!] Run:  pip install numpy"); sys.exit(1)

try:
    import sounddevice as sd
except ImportError:
    print("[!] Run:  pip install sounddevice"); sys.exit(1)

try:
    import pygame
    import pygame.sndarray
except ImportError:
    print("[!] Run:  pip install pygame"); sys.exit(1)


# ── built-in synthetic sounds ─────────────────────────────────────────────────
BUILTIN_SOUNDS = {
    "thud":   {"freq": 80,  "duration": 0.18, "wave": "sine"},
    "boing":  {"freq": 440, "duration": 0.25, "wave": "slide_down"},
    "squeak": {"freq": 900, "duration": 0.12, "wave": "slide_up"},
    "whack":  {"freq": 200, "duration": 0.10, "wave": "noise"},
    "moan":   {"freq": 300, "duration": 0.40, "wave": "slide_down"},
}

def _script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def _list_local_sound_files() -> list[str]:
    d = _script_dir()
    try:
        entries = os.listdir(d)
    except OSError:
        return []
    files = []
    for name in entries:
        lower = name.lower()
        if lower.endswith((".mp3", ".wav", ".ogg")):
            full = os.path.join(d, name)
            if os.path.isfile(full):
                files.append(name)
    files.sort(key=lambda s: s.lower())
    return files

def _generate_tone(freq, duration, wave, sample_rate=44100):
    n = int(sample_rate * duration)
    buf = []
    for i in range(n):
        t = i / sample_rate
        fade = 1.0 - (i / n)
        if wave == "sine":
            v = math.sin(2 * math.pi * freq * t)
        elif wave == "slide_down":
            f = freq * (1 - 0.5 * i / n)
            v = math.sin(2 * math.pi * f * t)
        elif wave == "slide_up":
            f = freq * (1 + 1.5 * i / n)
            v = math.sin(2 * math.pi * f * t)
        elif wave == "noise":
            v = random.uniform(-1, 1)
        else:
            v = math.sin(2 * math.pi * freq * t)
        sample = int(v * fade * 32767)
        buf.append(struct.pack("<h", max(-32768, min(32767, sample))))
    return b"".join(buf)

def load_sound(path_or_name):
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()

    if os.path.isfile(path_or_name):
        try:
            return pygame.mixer.Sound(path_or_name)
        except Exception as e:
            print(f"[!] Could not load '{path_or_name}': {e}")
            return None

    name = path_or_name.lower()
    if name in BUILTIN_SOUNDS:
        cfg = BUILTIN_SOUNDS[name]
        raw = _generate_tone(cfg["freq"], cfg["duration"], cfg["wave"])
        mono = np.frombuffer(raw, dtype="<i2")
        stereo = np.column_stack((mono, mono))
        return pygame.sndarray.make_sound(stereo)

    print(f"[!] '{path_or_name}' not found. Built-ins: {', '.join(BUILTIN_SOUNDS)}")
    return None

def _resolve_default_sound(cli_value: str) -> str:
    """
    If user didn't specify a sound, prefer a local file named 'sound moan.mp3'
    (common filename in this folder) when present.
    """
    if cli_value != "thud":
        return cli_value
    preferred = os.path.join(_script_dir(), "sound moan.mp3")
    return preferred if os.path.isfile(preferred) else cli_value


# ── microphone impact detector ────────────────────────────────────────────────
class MicImpactDetector:
    """
    Streams mic audio in real-time.
    Detects sudden volume SPIKES (impact = loud thud that drops off quickly).

    sensitivity: 0.0–1.0  (lower = triggers more easily)
                 Maps to an RMS threshold: 0.5 → needs a firm slap,
                 0.2 → triggers on a gentle tap.
    """

    SAMPLE_RATE   = 44100
    BLOCK_SIZE    = 512          # samples per callback (~12ms)
    HISTORY_SECS  = 0.15         # baseline calculated over this window
    SPIKE_RATIO   = 6.0          # how many times louder than baseline = spike

    def __init__(self, sensitivity: float, cooldown: float, on_impact):
        # sensitivity 0–1 → threshold 0.02–0.4 (RMS, normalised 0–1)
        self.threshold  = 0.02 + (1.0 - sensitivity) * 0.38
        self.cooldown   = cooldown
        self.on_impact  = on_impact
        self._history   = []
        self._hist_max  = int(self.SAMPLE_RATE / self.BLOCK_SIZE * self.HISTORY_SECS)
        self._last_fire = 0.0
        self._stream    = None

    def _rms(self, block):
        return float(np.sqrt(np.mean(block.astype(np.float64) ** 2))) / 32768.0

    def _callback(self, indata, frames, time_info, status):
        rms = self._rms(indata[:, 0])

        # maintain rolling baseline
        self._history.append(rms)
        if len(self._history) > self._hist_max:
            self._history.pop(0)
        baseline = max(np.mean(self._history), 1e-6)

        now = time.time()
        is_spike   = rms > self.threshold
        is_loud    = rms > baseline * self.SPIKE_RATIO
        off_cooldown = (now - self._last_fire) >= self.cooldown

        if is_spike and is_loud and off_cooldown:
            self._last_fire = now
            threading.Thread(target=self.on_impact, args=(rms,), daemon=True).start()

    def start(self):
        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            blocksize=self.BLOCK_SIZE,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()


# ── calibration helper ────────────────────────────────────────────────────────
def calibrate(seconds=2):
    """Measure ambient noise for 2 seconds, return average RMS."""
    print(f"\n  Calibrating... stay quiet for {seconds}s ", end="", flush=True)
    samples = []

    def cb(indata, frames, t, status):
        rms = float(np.sqrt(np.mean(indata.astype(np.float64)**2))) / 32768.0
        samples.append(rms)

    with sd.InputStream(samplerate=44100, channels=1, dtype="int16",
                        blocksize=512, callback=cb):
        for _ in range(seconds * 10):
            time.sleep(0.1)
            print(".", end="", flush=True)

    ambient = float(np.mean(samples)) if samples else 0.0
    print(f"  ambient RMS = {ambient:.4f}")
    return ambient


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Mic-based spank sound player")
    ap.add_argument("--sound",       default="thud",
                    help=f"Sound file or built-in ({', '.join(BUILTIN_SOUNDS)}). Default: thud")
    ap.add_argument("--sensitivity", type=float, default=0.5,
                    help="0.0 (hair-trigger) – 1.0 (needs hard hit). Default: 0.5")
    ap.add_argument("--cooldown",    type=float, default=0.5,
                    help="Seconds between triggers. Default: 0.5")
    ap.add_argument("--no-calibrate", action="store_true",
                    help="Skip ambient noise calibration")
    ap.add_argument("--list-sounds", action="store_true")
    args = ap.parse_args()

    if args.list_sounds:
        print("Built-in sounds:", ", ".join(BUILTIN_SOUNDS))
        local = _list_local_sound_files()
        if local:
            print("Local sound files:", ", ".join(local))
            if "sound moan.mp3" in local:
                print('Tip: use `--sound "sound moan.mp3"` (quotes required because of the space).')
        return

    # Load sound first
    sound_choice = _resolve_default_sound(args.sound)
    sound = load_sound(sound_choice)
    if sound is None:
        sys.exit(1)

    print(f"\n  🎤 Microphone Impact Mode")
    print(f"  Sound      : {sound_choice}")
    print(f"  Sensitivity: {args.sensitivity}  (0=hair-trigger, 1=hard hit)")
    print(f"  Cooldown   : {args.cooldown}s")

    if not args.no_calibrate:
        calibrate(2)

    hit_count = [0]

    def on_impact(rms):
        hit_count[0] += 1
        print(f"  💥 IMPACT #{hit_count[0]}!  (mic RMS={rms:.4f})")
        sound.play()

    detector = MicImpactDetector(
        sensitivity=args.sensitivity,
        cooldown=args.cooldown,
        on_impact=on_impact,
    )
    detector.start()

    print("\n  ✅ Listening! Slap/tap your laptop to trigger the sound.")
    print("     Too sensitive? add --sensitivity 0.8")
    print("     Not triggering? add --sensitivity 0.2")
    print("     Press Ctrl+C to quit.\n")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        detector.stop()
        print(f"\n  Stopped. Total impacts: {hit_count[0]}")


if __name__ == "__main__":
    main()