## Laptop Spank Sound (Mic Triggered)
Note: Many modern Macs have built‑in accelerometers that can be used to trigger fun “spank your laptop” scripts based on motion. My Windows laptop doesn’t expose an accelerometer (or any usable motion sensor), so this project takes a different approach: it listens to the microphone for short, loud impact sounds (taps/slaps/knocks) and triggers the audio purely from sound, not from motion.

Simple Python script that listens to your laptop microphone for sudden impact (a tap, slap, or desk knock) and plays a sound effect (built‑in tone or your own audio file).

### Features

- **Mic impact detection**: Detects short, loud spikes from the microphone.
- **Custom sounds**: Play any `.mp3` / `.wav` / `.ogg` file (e.g. `sound moan.mp3`).
- **Built‑in tones**: Includes synthetic sounds like `thud`, `boing`, `squeak`, `whack`, `moan`.
- **Adjustable sensitivity**: Tune how hard you have to hit to trigger.

### Requirements

- Python 3.9+
- Packages:
  - `numpy`
  - `sounddevice`
  - `pygame`

Install dependencies:

```bash
pip install numpy sounddevice pygame
```

### Usage

From this folder:

```bash
python spank_sound_mic.py
```

If a file named `sound moan.mp3` is in the same folder, it will be used automatically by default.

To explicitly choose a sound file (quotes needed because of the space):

```bash
python spank_sound_mic.py --sound "sound moan.mp3"
```

Use a built‑in tone instead:

```bash
python spank_sound_mic.py --sound thud
```

Adjust sensitivity (0.0 = very sensitive, 1.0 = needs hard hit):

```bash
python spank_sound_mic.py --sensitivity 0.3
```

List available sounds and local audio files:

```bash
python spank_sound_mic.py --list-sounds
```


