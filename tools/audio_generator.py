"""
Procedural Music Engine for VW California Trip Recaps.

Generates rich, studio-quality, polyphonic stereo soundtrack tracks for:
- vanlife_chill (Relaks)
- acoustic_sunset (Relaks)
- coastal_breeze (Relaks)
- alpine_acoustic (Relaks)
- jazz_trio (Jazz)
- folk_guitar (Folk / Gitara)
- reggae_sunshine (Folk / Gitara)
- cinematic_orchestral (Klimat)
- electronic_lofi (Klimat)

Uses physical modeling (Karplus-Strong), FM synthesis (Rhodes/Keys),
subtractive synthesis (Strings, Pads, Bass), procedural drum synthesis,
stereo panning, chorus, delay, and analog tape saturation.
"""

import os
import math
import wave
import struct
import subprocess
import numpy as np
from scipy import signal

SAMPLE_RATE = 44100


# ── DSP & Synthesis Primitives ─────────────────────────────────────────────

def note_to_freq(note_name):
    """Convert note name like 'C4', 'F#3', 'Bb2' to frequency in Hz."""
    notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    flats = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

    name = note_name.strip()
    octave = int(name[-1])
    pitch = name[:-1]
    if pitch in flats:
        pitch = flats[pitch]
    semitone = notes.index(pitch)
    # A4 is semitone 9 in octave 4, freq 440 Hz
    midi_num = (octave + 1) * 12 + semitone
    return 440.0 * (2.0 ** ((midi_num - 69) / 12.0))


def adsr(num_samples, a=0.01, d=0.1, s=0.7, r=0.2):
    """Generate ADSR envelope."""
    na = max(1, int(a * num_samples))
    nd = max(1, int(d * num_samples))
    nr = max(1, int(r * num_samples))
    ns = max(0, num_samples - na - nd - nr)

    env_a = np.linspace(0.0, 1.0, na, endpoint=False)
    env_d = np.linspace(1.0, s, nd, endpoint=False)
    env_s = np.full(ns, s)
    env_r = np.linspace(s, 0.0, nr)

    env = np.concatenate([env_a, env_d, env_s, env_r])
    if len(env) < num_samples:
        env = np.pad(env, (0, num_samples - len(env)))
    return env[:num_samples]


def karplus_strong(freq, duration_sec, sr=SAMPLE_RATE, decay=0.988, pluck_pos=0.25):
    """
    Synthesize authentic plucked acoustic string using Karplus-Strong algorithm.
    """
    num_samples = int(duration_sec * sr)
    n_period = max(2, int(sr / freq))

    # Initial pluck excitation: band-limited filtered noise
    noise = np.random.uniform(-1.0, 1.0, n_period)
    # Pick position comb filter
    comb_delay = max(1, int(n_period * pluck_pos))
    for i in range(comb_delay, n_period):
        noise[i] -= noise[i - comb_delay] * 0.5

    # Ring buffer simulation
    out = np.zeros(num_samples, dtype=np.float32)
    buf = noise.copy()
    prev = 0.0

    for i in range(num_samples):
        idx = i % n_period
        val = buf[idx]
        # Lowpass filter in loop: average of adjacent samples
        filtered = 0.5 * (val + prev) * decay
        prev = val
        buf[idx] = filtered
        out[i] = val

    # Amplitude envelope
    env = np.exp(-np.linspace(0, 3.5, num_samples))
    return out * env


def synth_rhodes(freq, duration_sec, sr=SAMPLE_RATE, velocity=0.8):
    """
    FM synthesis of warm Fender Rhodes electric piano note.
    Carrier 1:1, modulator with bell-like transient and warm sustain.
    """
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    mod_env = np.exp(-t * 6.0) * 2.5 * velocity
    amp_env = np.exp(-t * 1.8) * velocity

    mod = np.sin(2 * np.pi * freq * t) * mod_env
    carrier = np.sin(2 * np.pi * freq * t + mod)
    # Add subtle octave overtone for bell chime
    tine = np.sin(2 * np.pi * (freq * 3.0) * t) * np.exp(-t * 12.0) * 0.3 * velocity
    # Add warm fundamental
    sub = np.sin(2 * np.pi * freq * t) * 0.4

    sig = (carrier + tine + sub) * amp_env
    return sig.astype(np.float32)


def synth_bass(freq, duration_sec, sr=SAMPLE_RATE, style="warm"):
    """
    Synthesize warm electric or acoustic bass note.
    """
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    n_samples = len(t)

    if style == "acoustic":  # Double bass / upright
        f1 = np.sin(2 * np.pi * freq * t)
        f2 = np.sin(2 * np.pi * (freq * 2) * t) * 0.35
        f3 = np.sin(2 * np.pi * (freq * 3) * t) * 0.12
        env = np.exp(-t * 2.8)
        sig = (f1 + f2 + f3) * env
    elif style == "dub":  # Deep sub reggae bass
        f1 = np.sin(2 * np.pi * freq * t)
        f2 = np.sin(2 * np.pi * (freq * 2) * t) * 0.15
        env = adsr(n_samples, a=0.03, d=0.15, s=0.85, r=0.25)
        sig = (f1 + f2) * env
    else:  # Warm electric bass
        saw = 2.0 * (t * freq - np.floor(t * freq + 0.5))
        sine = np.sin(2 * np.pi * freq * t)
        env = adsr(n_samples, a=0.02, d=0.2, s=0.75, r=0.2)
        sig = (sine * 0.7 + saw * 0.3) * env

    # Butterworth low-pass filter at 450 Hz
    b, a = signal.butter(4, 450.0 / (sr / 2.0), btype="low")
    filtered = signal.lfilter(b, a, sig)
    return filtered.astype(np.float32)


def synth_string_pad(freq, duration_sec, sr=SAMPLE_RATE):
    """
    Lush orchestral string / synth pad with chorus detuning.
    """
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    n = len(t)
    env = adsr(n, a=0.25, d=0.1, s=0.8, r=0.35)

    # Detuned oscillators for rich chorus effect
    v1 = np.sin(2 * np.pi * freq * t)
    v2 = np.sin(2 * np.pi * (freq * 1.004) * t) * 0.8
    v3 = np.sin(2 * np.pi * (freq * 0.996) * t) * 0.8
    v4 = np.sin(2 * np.pi * (freq * 2.001) * t) * 0.3
    v5 = np.sin(2 * np.pi * (freq * 0.5) * t) * 0.4

    sig = (v1 + v2 + v3 + v4 + v5) * 0.3 * env
    # Soft low-pass
    b, a = signal.butter(2, 1800.0 / (sr / 2.0), btype="low")
    return signal.lfilter(b, a, sig).astype(np.float32)


# ── Drum & Percussion Synthesis ────────────────────────────────────────────

def synth_kick(sr=SAMPLE_RATE, duration_sec=0.25, punch="warm"):
    """Synthesize punchy acoustic/lofi kick drum."""
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    freq_start = 125.0 if punch == "warm" else 150.0
    freq_end = 42.0
    # Pitch drop sweep
    pitch_env = np.exp(-t * 28.0)
    freqs = freq_end + (freq_start - freq_end) * pitch_env
    phase = 2 * np.pi * np.cumsum(freqs) / sr
    body = np.sin(phase)

    # Amplitude envelope
    amp = np.exp(-t * 14.0)
    # Click transient
    click = np.random.uniform(-0.3, 0.3, len(t)) * np.exp(-t * 120.0)
    kick = (body + click) * amp
    return np.clip(kick * 1.2, -1.0, 1.0).astype(np.float32)


def synth_snare(sr=SAMPLE_RATE, duration_sec=0.22, style="lofi"):
    """Synthesize warm snare or rimshot."""
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    # Tonal body
    body_freq = 190.0 if style == "lofi" else 220.0
    body = np.sin(2 * np.pi * body_freq * t) * np.exp(-t * 25.0)

    # Snare wire noise
    noise = np.random.uniform(-1.0, 1.0, len(t))
    b, a = signal.butter(3, [800.0 / (sr / 2.0), 6500.0 / (sr / 2.0)], btype="band")
    filtered_noise = signal.lfilter(b, a, noise)
    noise_env = np.exp(-t * 16.0)

    sig = (body * 0.5 + filtered_noise * 0.7 * noise_env)
    return (sig * 0.85).astype(np.float32)


def synth_hihat(sr=SAMPLE_RATE, duration_sec=0.06, closed=True):
    """Synthesize crisp hi-hat or shaker."""
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    noise = np.random.uniform(-1.0, 1.0, len(t))
    b, a = signal.butter(3, 7500.0 / (sr / 2.0), btype="high")
    filtered = signal.lfilter(b, a, noise)
    decay_rate = 55.0 if closed else 14.0
    env = np.exp(-t * decay_rate)
    return (filtered * env * 0.45).astype(np.float32)


def synth_reggae_rimshot(sr=SAMPLE_RATE, duration_sec=0.18):
    """Synthesize authentic reggae one-drop cross-stick / rimshot."""
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    click = np.sin(2 * np.pi * 1250.0 * t) * np.exp(-t * 60.0)
    ring = np.sin(2 * np.pi * 420.0 * t) * np.exp(-t * 22.0)
    noise = np.random.uniform(-0.5, 0.5, len(t)) * np.exp(-t * 35.0)
    return ((click * 0.6 + ring * 0.5 + noise * 0.25) * 0.8).astype(np.float32)


def synth_timpani(freq=55.0, duration_sec=1.4, sr=SAMPLE_RATE):
    """Synthesize orchestral timpani strike."""
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    freqs = freq + 25.0 * np.exp(-t * 30.0)
    phase = 2 * np.pi * np.cumsum(freqs) / sr
    body = np.sin(phase) * np.exp(-t * 3.5)
    harm = np.sin(phase * 1.5) * np.exp(-t * 5.0) * 0.3
    return ((body + harm) * 0.9).astype(np.float32)


# ── Audio Mixer & Effects ──────────────────────────────────────────────────

class TrackMixer:
    """Stereo audio mixer with panning, delay, and analog tape saturation."""

    def __init__(self, duration_sec, sr=SAMPLE_RATE):
        self.sr = sr
        self.num_samples = int(duration_sec * sr)
        self.left = np.zeros(self.num_samples, dtype=np.float32)
        self.right = np.zeros(self.num_samples, dtype=np.float32)

    def add_sample(self, sample, start_sec, pan=0.0, gain=1.0):
        """
        Add a mono sample to the mix.
        pan: -1.0 (hard left) to +1.0 (hard right). 0.0 is center.
        """
        start_idx = int(start_sec * self.sr)
        if start_idx >= self.num_samples:
            return

        length = min(len(sample), self.num_samples - start_idx)
        if length <= 0:
            return

        # Equal power pan law
        pan_clamped = max(-1.0, min(1.0, pan))
        angle = (pan_clamped + 1.0) * (np.pi / 4.0)
        gain_l = np.cos(angle) * gain
        gain_r = np.sin(angle) * gain

        chunk = sample[:length]
        self.left[start_idx:start_idx + length] += chunk * gain_l
        self.right[start_idx:start_idx + length] += chunk * gain_r

    def add_delay(self, delay_sec=0.28, feedback=0.32, mix=0.22):
        """Stereo ping-pong delay."""
        delay_samples = int(delay_sec * self.sr)
        if delay_samples <= 0 or delay_samples >= self.num_samples:
            return

        echo_l = np.zeros_like(self.left)
        echo_r = np.zeros_like(self.right)

        for i in range(delay_samples, self.num_samples):
            echo_l[i] = self.right[i - delay_samples] * feedback
            echo_r[i] = self.left[i - delay_samples] * feedback

        self.left += echo_l * mix
        self.right += echo_r * mix

    def add_reverb(self, room_size=0.4, mix=0.18):
        """Simple Schroeder all-pass / comb filter reverb."""
        delays = [int(self.sr * d) for d in [0.029, 0.037, 0.043, 0.051]]
        comb_l = np.zeros_like(self.left)
        comb_r = np.zeros_like(self.right)

        for d in delays:
            if d < self.num_samples:
                comb_l[d:] += self.left[:-d] * room_size
                comb_r[d:] += self.right[:-d] * room_size

        self.left = self.left * (1.0 - mix) + comb_l * (mix / len(delays))
        self.right = self.right * (1.0 - mix) + comb_r * (mix / len(delays))

    def master_and_export(self, wav_path, mp3_path=None, fade_sec=2.5):
        """
        Master audio with soft tape saturation, smooth exponential fade-out,
        and export to 16-bit 44.1kHz WAV + high quality MP3.
        """
        # Apply fade-out at the end
        fade_samples = int(fade_sec * self.sr)
        if fade_samples > 0 and fade_samples < self.num_samples:
            fade_curve = np.linspace(1.0, 0.0, fade_samples) ** 1.8
            self.left[-fade_samples:] *= fade_curve
            self.right[-fade_samples:] *= fade_curve

        # Analog tape saturation: soft clipping with tanh
        drive = 1.35
        left_sat = np.tanh(self.left * drive) / np.tanh(drive)
        right_sat = np.tanh(self.right * drive) / np.tanh(drive)

        # Normalize to peak -0.5 dB
        peak = max(np.max(np.abs(left_sat)), np.max(np.abs(right_sat)), 1e-5)
        target_peak = 0.94
        scale = target_peak / peak if peak > target_peak else 1.0
        left_out = left_sat * scale
        right_out = right_sat * scale

        # Convert to 16-bit PCM
        left_pcm = (left_out * 32767.0).astype(np.int16)
        right_pcm = (right_out * 32767.0).astype(np.int16)

        # Interleave stereo channels
        stereo = np.empty((self.num_samples * 2,), dtype=np.int16)
        stereo[0::2] = left_pcm
        stereo[1::2] = right_pcm

        os.makedirs(os.path.dirname(os.path.abspath(wav_path)), exist_ok=True)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(self.sr)
            wf.writeframes(stereo.tobytes())

        if mp3_path:
            os.makedirs(os.path.dirname(os.path.abspath(mp3_path)), exist_ok=True)
            cmd = [
                "ffmpeg", "-y",
                "-i", wav_path,
                "-codec:a", "libmp3lame",
                "-b:a", "320k",
                "-ar", "44100",
                mp3_path
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"  ⚠️ MP3 export failed for {mp3_path}: {e}")


# ── Song Generators by Category ────────────────────────────────────────────

def generate_vanlife_chill(duration_sec=38.0):
    """
    🚐 Vanlife Chill: Warm acoustic guitar arpeggios, mellow Rhodes electric piano,
    relaxed lo-fi drum groove, warm walking bassline.
    """
    bpm = 84.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # Chord Progression: Cmaj7 - Em7 - Fmaj7 - G7
    chords = [
        {"root": "C2", "bass": "C2", "guitar": ["C3", "E3", "G3", "B3", "E4"], "rhodes": ["C4", "E4", "G4", "B4"]},
        {"root": "E2", "bass": "E2", "guitar": ["E3", "G3", "B3", "D4", "G4"], "rhodes": ["E4", "G4", "B4", "D5"]},
        {"root": "F2", "bass": "F2", "guitar": ["F3", "A3", "C4", "E4", "A4"], "rhodes": ["F4", "A4", "C5", "E5"]},
        {"root": "G2", "bass": "G2", "guitar": ["G3", "B3", "D4", "F4", "B4"], "rhodes": ["G4", "B4", "D5", "F5"]},
    ]

    kick = synth_kick(punch="warm")
    snare = synth_snare(style="lofi")
    hh_c = synth_hihat(duration_sec=0.05, closed=True)
    hh_o = synth_hihat(duration_sec=0.20, closed=False)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        c = chords[b_idx % len(chords)]

        # Drums
        for i in range(4):
            t_beat = bar_start + i * beat
            # Kick on 1 and 2.5
            if i == 0:
                mixer.add_sample(kick, t_beat, pan=0.0, gain=0.95)
            elif i == 2:
                mixer.add_sample(kick, t_beat + beat * 0.5, pan=0.0, gain=0.75)
            # Snare on 2 and 4
            if i == 1 or i == 3:
                mixer.add_sample(snare, t_beat, pan=-0.1, gain=0.85)

            # Hi-hats 8th notes with swing
            mixer.add_sample(hh_c, t_beat, pan=0.3, gain=0.45)
            mixer.add_sample(hh_o if (i == 3) else hh_c, t_beat + beat * 0.56, pan=0.35, gain=0.38)

        # Bass
        b_freq = note_to_freq(c["bass"])
        b_sample = synth_bass(b_freq, beat * 1.8, style="warm")
        mixer.add_sample(b_sample, bar_start, pan=0.0, gain=0.9)
        # Walking bass passing note on beat 3
        b_pass = synth_bass(b_freq * 1.12, beat * 1.4, style="warm")
        mixer.add_sample(b_pass, bar_start + beat * 2.0, pan=0.0, gain=0.75)

        # Rhodes Chords
        for r_note in c["rhodes"]:
            rf = note_to_freq(r_note)
            r_samp = synth_rhodes(rf, bar * 0.85, velocity=0.75)
            mixer.add_sample(r_samp, bar_start + 0.02, pan=-0.35, gain=0.45)

        # Acoustic Guitar Arpeggio (8th-note fingerpicking pattern)
        for g_idx, g_note in enumerate(c["guitar"]):
            gf = note_to_freq(g_note)
            g_samp = karplus_strong(gf, beat * 1.6, decay=0.989)
            g_time = bar_start + (g_idx * beat * 0.5)
            pan_pos = 0.25 if g_idx % 2 == 0 else 0.45
            mixer.add_sample(g_samp, g_time, pan=pan_pos, gain=0.55)

        # Subtle String Pad
        pad_root = note_to_freq(c["rhodes"][0]) * 0.5
        pad_samp = synth_string_pad(pad_root, bar * 1.05)
        mixer.add_sample(pad_samp, bar_start, pan=0.0, gain=0.22)

    mixer.add_delay(delay_sec=0.32, feedback=0.25, mix=0.18)
    mixer.add_reverb(room_size=0.35, mix=0.15)
    return mixer


def generate_acoustic_sunset(duration_sec=38.0):
    """
    🌅 Acoustic Sunset: Intimate dual fingerpicked guitars, gentle ambient pad,
    soft shaker, warm acoustic bass.
    """
    bpm = 74.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # G Major - D/F# - Em7 - Cadd9
    chords = [
        {"bass": "G2", "notes": ["G3", "B3", "D4", "G4", "B4"]},
        {"bass": "F#2", "notes": ["F#3", "A3", "D4", "F#4", "A4"]},
        {"bass": "E2", "notes": ["E3", "G3", "B3", "E4", "G4"]},
        {"bass": "C2", "notes": ["C3", "E3", "G3", "C4", "E4"]},
    ]

    shaker = synth_hihat(duration_sec=0.08, closed=True)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        c = chords[b_idx % len(chords)]

        # Soft acoustic bass
        b_freq = note_to_freq(c["bass"])
        b_samp = synth_bass(b_freq, bar * 0.9, style="acoustic")
        mixer.add_sample(b_samp, bar_start, pan=0.0, gain=0.8)

        # Warm ambient pad
        pad_freq = note_to_freq(c["notes"][0])
        pad_samp = synth_string_pad(pad_freq, bar * 1.05)
        mixer.add_sample(pad_samp, bar_start, pan=0.0, gain=0.32)

        # Left & Right acoustic guitar fingerpicking
        notes = c["notes"]
        for step in range(8):
            t_step = bar_start + step * (beat * 0.5)
            # Shaker on 8th notes
            mixer.add_sample(shaker, t_step, pan=0.3, gain=0.22)

            # Guitar Left (low-mid arpeggio)
            n_left = notes[step % len(notes)]
            g_l = karplus_strong(note_to_freq(n_left), beat * 1.8, decay=0.991)
            mixer.add_sample(g_l, t_step, pan=-0.4, gain=0.5)

            # Guitar Right (high melodic counterpoint)
            if step % 2 == 1:
                n_right = notes[(step * 2) % len(notes)]
                g_r = karplus_strong(note_to_freq(n_right) * 1.5, beat * 1.4, decay=0.988)
                mixer.add_sample(g_r, t_step + 0.03, pan=0.45, gain=0.42)

    mixer.add_delay(delay_sec=0.38, feedback=0.35, mix=0.22)
    mixer.add_reverb(room_size=0.45, mix=0.22)
    return mixer


def generate_coastal_breeze(duration_sec=38.0):
    """
    🌊 Coastal Breeze: Tropical kalimba, rhythmic acoustic strumming,
    sun-drenched upbeat surf bass, ocean atmosphere.
    """
    bpm = 98.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # D Major - A - Bm - G
    prog = [
        {"root": "D3", "bass": "D2", "lead": ["F#4", "A4", "D5", "A4"]},
        {"root": "A2", "bass": "A2", "lead": ["E4", "A4", "C#5", "A4"]},
        {"root": "B2", "bass": "B2", "lead": ["D4", "F#4", "B4", "F#4"]},
        {"root": "G2", "bass": "G2", "lead": ["D4", "G4", "B4", "G4"]},
    ]

    kick = synth_kick(punch="punchy")
    snare = synth_snare(style="snappy")
    hh = synth_hihat(duration_sec=0.06, closed=True)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        p = prog[b_idx % len(prog)]

        # Energetic Beach Drums
        for i in range(4):
            t_b = bar_start + i * beat
            mixer.add_sample(hh, t_b, pan=0.25, gain=0.4)
            mixer.add_sample(hh, t_b + beat * 0.5, pan=0.3, gain=0.35)
            if i == 0 or i == 2:
                mixer.add_sample(kick, t_b, pan=0.0, gain=0.9)
            if i == 1 or i == 3:
                mixer.add_sample(snare, t_b, pan=-0.1, gain=0.8)

        # Surf Bassline (dotted syncopation)
        bf = note_to_freq(p["bass"])
        mixer.add_sample(synth_bass(bf, beat * 1.2, style="warm"), bar_start, pan=0.0, gain=0.85)
        mixer.add_sample(synth_bass(bf, beat * 0.8, style="warm"), bar_start + beat * 1.5, pan=0.0, gain=0.75)
        mixer.add_sample(synth_bass(bf * 1.33, beat * 0.8, style="warm"), bar_start + beat * 2.5, pan=0.0, gain=0.8)

        # Kalimba / Marimba Lead
        for m_idx, m_note in enumerate(p["lead"]):
            mf = note_to_freq(m_note)
            kalimba = synth_rhodes(mf * 1.2, beat * 1.2, velocity=0.85)
            mixer.add_sample(kalimba, bar_start + m_idx * beat, pan=0.35, gain=0.55)

        # Strummed Guitar Chord
        root_f = note_to_freq(p["root"])
        for str_i in range(4):
            chord_note = karplus_strong(root_f * (1.0 + str_i * 0.25), beat * 1.5, decay=0.985)
            mixer.add_sample(chord_note, bar_start + beat * 0.5 + str_i * 0.02, pan=-0.4, gain=0.35)
            mixer.add_sample(chord_note, bar_start + beat * 2.5 + str_i * 0.02, pan=-0.4, gain=0.35)

    mixer.add_delay(delay_sec=0.24, feedback=0.28, mix=0.18)
    mixer.add_reverb(room_size=0.3, mix=0.16)
    return mixer


def generate_alpine_acoustic(duration_sec=38.0):
    """
    🌲 Alpine Acoustic: Crisp steel-string mountain fingerpicking, wooden percussion,
    expansive reverbed pine forest atmosphere, cello bass foundation.
    """
    bpm = 86.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # Em - G - D - C
    prog = [
        {"bass": "E2", "notes": ["E3", "B3", "E4", "G4", "B4", "E5"]},
        {"bass": "G2", "notes": ["G3", "B3", "D4", "G4", "B4", "D5"]},
        {"bass": "D2", "notes": ["D3", "A3", "D4", "F#4", "A4", "D5"]},
        {"bass": "C2", "notes": ["C3", "G3", "C4", "E4", "G4", "C5"]},
    ]

    stomp = synth_kick(punch="warm")
    wood = synth_hihat(duration_sec=0.08, closed=True)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        p = prog[b_idx % len(prog)]

        # Wooden Mountain Stomp on beat 1 and 3
        mixer.add_sample(stomp, bar_start, pan=0.0, gain=0.85)
        mixer.add_sample(stomp, bar_start + beat * 2.0, pan=0.0, gain=0.7)
        for s in range(4):
            mixer.add_sample(wood, bar_start + s * beat + beat * 0.5, pan=0.2, gain=0.3)

        # Cello-like deep acoustic bass
        bf = note_to_freq(p["bass"])
        mixer.add_sample(synth_bass(bf, bar * 0.85, style="acoustic"), bar_start, pan=0.0, gain=0.85)

        # Expansive mountain string pad
        pad_samp = synth_string_pad(bf * 2.0, bar * 1.05)
        mixer.add_sample(pad_samp, bar_start, pan=0.0, gain=0.28)

        # Fast Crisp Steel String Picking (16th notes)
        notes = p["notes"]
        for step in range(8):
            t_s = bar_start + step * (beat * 0.5)
            nf = note_to_freq(notes[step % len(notes)])
            g_str = karplus_strong(nf, beat * 2.0, decay=0.992)
            pan = -0.35 if step % 2 == 0 else 0.35
            mixer.add_sample(g_str, t_s, pan=pan, gain=0.48)

    mixer.add_delay(delay_sec=0.42, feedback=0.38, mix=0.25)
    mixer.add_reverb(room_size=0.55, mix=0.28)
    return mixer


def generate_jazz_trio(duration_sec=38.0):
    """
    🎷 Jazz Trio: Swing ride cymbal, acoustic walking double bass,
    lush Rhodes 7th/9th chords, smooth vibraphone melodic improvisations.
    """
    bpm = 112.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # Classic Jazz ii - V - I - VI: Dm7 - G7 - Cmaj7 - A7
    prog = [
        {"chord": ["D4", "F4", "A4", "C5"], "bass_line": ["D2", "F2", "G#2", "A2"]},
        {"chord": ["G3", "B3", "F4", "B4"], "bass_line": ["G2", "B2", "C3", "C#3"]},
        {"chord": ["C4", "E4", "G4", "B4"], "bass_line": ["C2", "E2", "G2", "G#2"]},
        {"chord": ["A3", "C#4", "G4", "C#5"], "bass_line": ["A2", "C#3", "D3", "D#3"]},
    ]

    ride = synth_hihat(duration_sec=0.18, closed=False)
    pedal_hh = synth_hihat(duration_sec=0.04, closed=True)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        p = prog[b_idx % len(prog)]

        # Swing Ride Cymbal ("ding, ding-a-ding, ding-a-ding")
        for i in range(4):
            t_b = bar_start + i * beat
            mixer.add_sample(ride, t_b, pan=0.4, gain=0.4)
            # Swing skip beat at 66%
            mixer.add_sample(ride, t_b + beat * 0.66, pan=0.42, gain=0.28)
            # Hi-hat pedal "chick" on 2 and 4
            if i == 1 or i == 3:
                mixer.add_sample(pedal_hh, t_b, pan=-0.3, gain=0.45)

        # Walking Double Bass (4 quarter notes per bar)
        for i, b_note in enumerate(p["bass_line"]):
            bf = note_to_freq(b_note)
            bass_hit = synth_bass(bf, beat * 1.1, style="acoustic")
            mixer.add_sample(bass_hit, bar_start + i * beat, pan=0.0, gain=0.92)

        # Comping Jazz Rhodes Chords (syncopated on beats 1 and 2.66)
        for r_note in p["chord"]:
            rf = note_to_freq(r_note)
            r_chord = synth_rhodes(rf, beat * 2.2, velocity=0.7)
            mixer.add_sample(r_chord, bar_start, pan=-0.35, gain=0.42)
            mixer.add_sample(r_chord, bar_start + beat * 2.66, pan=-0.35, gain=0.36)

        # Vibraphone melody snippet
        vibe_notes = [p["chord"][2], p["chord"][3], p["chord"][1]]
        for vi, vn in enumerate(vibe_notes):
            vf = note_to_freq(vn) * 1.5
            v_hit = synth_rhodes(vf, beat * 1.4, velocity=0.85)
            mixer.add_sample(v_hit, bar_start + beat * (1.0 + vi * 0.66), pan=0.25, gain=0.45)

    mixer.add_delay(delay_sec=0.26, feedback=0.25, mix=0.16)
    mixer.add_reverb(room_size=0.4, mix=0.2)
    return mixer


def generate_folk_guitar(duration_sec=38.0):
    """
    🎸 Folk Guitar: Driving acoustic strumming, banjo/mandolin arpeggios,
    foot-stomping rhythm, energetic road trip feel.
    """
    bpm = 108.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # A Major - E - F#m - D
    prog = [
        {"bass": "A2", "strum": ["A3", "C#4", "E4", "A4"], "lead": ["C#5", "E5", "A5"]},
        {"bass": "E2", "strum": ["G#3", "B3", "E4", "B4"], "lead": ["B4", "E5", "G#5"]},
        {"bass": "F#2", "strum": ["A3", "C#4", "F#4", "C#5"], "lead": ["A4", "C#5", "F#5"]},
        {"bass": "D2", "strum": ["A3", "D4", "F#4", "D5"], "lead": ["F#4", "A4", "D5"]},
    ]

    stomp = synth_kick(punch="punchy")
    tambourine = synth_hihat(duration_sec=0.12, closed=False)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        p = prog[b_idx % len(prog)]

        # Rhythm: Stomp on 1 and 3, Tambourine on 2 and 4
        mixer.add_sample(stomp, bar_start, pan=0.0, gain=0.9)
        mixer.add_sample(stomp, bar_start + beat * 2.0, pan=0.0, gain=0.85)
        mixer.add_sample(tambourine, bar_start + beat * 1.0, pan=0.25, gain=0.45)
        mixer.add_sample(tambourine, bar_start + beat * 3.0, pan=0.25, gain=0.45)

        # Folk Bass (root - fifth)
        bf = note_to_freq(p["bass"])
        mixer.add_sample(synth_bass(bf, beat * 1.2, style="warm"), bar_start, pan=0.0, gain=0.85)
        mixer.add_sample(synth_bass(bf * 1.5, beat * 1.2, style="warm"), bar_start + beat * 2.0, pan=0.0, gain=0.8)

        # Strummed Acoustic Guitar (Down-Down-Up-Up-Down-Up pattern)
        strum_times = [0.0, 1.0, 1.5, 2.5, 3.0, 3.5]
        for st in strum_times:
            t_str = bar_start + st * beat
            for s_idx, s_note in enumerate(p["strum"]):
                sf = note_to_freq(s_note)
                str_samp = karplus_strong(sf, beat * 1.2, decay=0.985)
                mixer.add_sample(str_samp, t_str + s_idx * 0.015, pan=-0.35, gain=0.4)

        # Fast Banjo / Mandolin Picking Fill
        for l_idx, l_note in enumerate(p["lead"]):
            lf = note_to_freq(l_note) * 1.2
            b_hit = karplus_strong(lf, beat * 0.9, decay=0.982)
            mixer.add_sample(b_hit, bar_start + beat * 2.0 + l_idx * (beat * 0.5), pan=0.4, gain=0.45)

    mixer.add_delay(delay_sec=0.22, feedback=0.25, mix=0.15)
    mixer.add_reverb(room_size=0.35, mix=0.16)
    return mixer


def generate_reggae_sunshine(duration_sec=38.0):
    """
    ☀️ Reggae Sunshine: Offbeat guitar skank, deep dub bassline,
    one-drop rimshot and kick on beat 3, sunny holiday feeling.
    """
    bpm = 76.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # G Major - C Major - D Major - G Major
    prog = [
        {"root": "G3", "bass": "G1", "skank": ["B3", "D4", "G4"]},
        {"root": "C3", "bass": "C2", "skank": ["C4", "E4", "G4"]},
        {"root": "D3", "bass": "D2", "skank": ["D4", "F#4", "A4"]},
        {"root": "G3", "bass": "G1", "skank": ["B3", "D4", "G4"]},
    ]

    kick = synth_kick(punch="warm")
    rim = synth_reggae_rimshot()
    hh = synth_hihat(duration_sec=0.04, closed=True)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        p = prog[b_idx % len(prog)]

        # Reggae "One Drop": Kick AND Rimshot together on beat 3!
        t_drop = bar_start + beat * 2.0
        mixer.add_sample(kick, t_drop, pan=0.0, gain=0.95)
        mixer.add_sample(rim, t_drop, pan=0.1, gain=0.85)

        # 16th-note subtle Hi-Hat groove
        for step in range(8):
            mixer.add_sample(hh, bar_start + step * (beat * 0.5), pan=0.25, gain=0.32)

        # Deep Dub Bass Riff (syncopated, heavy fundamental)
        bf = note_to_freq(p["bass"])
        b1 = synth_bass(bf, beat * 0.9, style="dub")
        b2 = synth_bass(bf * 1.5, beat * 0.8, style="dub")
        mixer.add_sample(b1, bar_start, pan=0.0, gain=0.95)
        mixer.add_sample(b2, bar_start + beat * 1.0, pan=0.0, gain=0.85)
        mixer.add_sample(b1, bar_start + beat * 2.5, pan=0.0, gain=0.9)

        # Reggae Skank / Chops: Strictly on offbeats (2 and 4)
        for offbeat in [1, 3]:
            t_skank = bar_start + offbeat * beat
            for s_n in p["skank"]:
                sf = note_to_freq(s_n)
                # Staccato muted guitar pluck
                chop = karplus_strong(sf, beat * 0.35, decay=0.94)
                mixer.add_sample(chop, t_skank, pan=-0.35, gain=0.5)
                # Rhodes organ bubble layering
                organ = synth_rhodes(sf, beat * 0.4, velocity=0.8)
                mixer.add_sample(organ, t_skank, pan=0.35, gain=0.4)

    # Dub spring delay & reverb
    mixer.add_delay(delay_sec=0.39, feedback=0.45, mix=0.24)
    mixer.add_reverb(room_size=0.45, mix=0.22)
    return mixer


def generate_cinematic_orchestral(duration_sec=38.0):
    """
    🎬 Cinematic Orchestral: Swelling string ensemble, dramatic timpani,
    French horn harmony, emotional travel crescendo.
    """
    bpm = 78.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # Dm - Bb - F - C
    prog = [
        {"root": "D3", "bass": "D1", "pad": ["D3", "F3", "A3", "D4"], "brass": "A3"},
        {"root": "Bb2", "bass": "Bb1", "pad": ["Bb2", "D3", "F3", "Bb3"], "brass": "F3"},
        {"root": "F3", "bass": "F1", "pad": ["F3", "A3", "C4", "F4"], "brass": "C4"},
        {"root": "C3", "bass": "C1", "pad": ["C3", "E3", "G3", "C4"], "brass": "G3"},
    ]

    timpani = synth_timpani(freq=55.0)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        p = prog[b_idx % len(prog)]

        # Dramatic Timpani roll on bar start
        mixer.add_sample(timpani, bar_start, pan=0.0, gain=0.85)

        # Deep orchestral bass foundation
        bf = note_to_freq(p["bass"])
        mixer.add_sample(synth_bass(bf, bar * 0.95, style="warm"), bar_start, pan=0.0, gain=0.9)

        # Swelling String Section
        for s_note in p["pad"]:
            sf = note_to_freq(s_note)
            str_samp = synth_string_pad(sf, bar * 1.1)
            mixer.add_sample(str_samp, bar_start, pan=-0.25, gain=0.42)

        # French Horn / Brass warmth
        br_f = note_to_freq(p["brass"])
        horn = synth_rhodes(br_f, bar * 0.8, velocity=0.8)
        mixer.add_sample(horn, bar_start + 0.1, pan=0.25, gain=0.4)

        # Staccato string ostinato (16th notes building momentum)
        for st in range(8):
            t_ost = bar_start + st * (beat * 0.5)
            ost_note = karplus_strong(bf * 4.0, beat * 0.45, decay=0.97)
            mixer.add_sample(ost_note, t_ost, pan=0.35, gain=0.32)

    mixer.add_delay(delay_sec=0.35, feedback=0.3, mix=0.2)
    mixer.add_reverb(room_size=0.6, mix=0.3)
    return mixer


def generate_electronic_lofi(duration_sec=38.0):
    """
    🎧 Electronic Lo-Fi: Dusty vinyl atmosphere, tape-warbled Rhodes piano,
    relaxed boom-bap kick/snare, smooth 808 sub-bass.
    """
    bpm = 75.0
    beat = 60.0 / bpm
    bar = beat * 4.0
    mixer = TrackMixer(duration_sec)

    # Ebmaj7 - Cm7 - Fm7 - Bb7
    prog = [
        {"bass": "Eb2", "rhodes": ["Eb4", "G4", "Bb4", "D5"], "lead": "G5"},
        {"bass": "C2", "rhodes": ["C4", "Eb4", "G4", "Bb4"], "lead": "Eb5"},
        {"bass": "F2", "rhodes": ["F4", "Ab4", "C5", "Eb5"], "lead": "C5"},
        {"bass": "Bb2", "rhodes": ["Bb3", "D4", "Ab4", "D5"], "lead": "Bb4"},
    ]

    kick = synth_kick(punch="warm")
    snare = synth_snare(style="lofi")
    hh = synth_hihat(duration_sec=0.04, closed=True)

    num_bars = int(duration_sec / bar) + 1
    for b_idx in range(num_bars):
        bar_start = b_idx * bar
        p = prog[b_idx % len(prog)]

        # Boom-Bap Drums with swing
        mixer.add_sample(kick, bar_start, pan=0.0, gain=0.95)
        mixer.add_sample(kick, bar_start + beat * 1.5, pan=0.0, gain=0.7)
        mixer.add_sample(snare, bar_start + beat * 1.0, pan=-0.1, gain=0.85)
        mixer.add_sample(snare, bar_start + beat * 3.0, pan=-0.1, gain=0.85)

        for i in range(4):
            t_b = bar_start + i * beat
            mixer.add_sample(hh, t_b, pan=0.25, gain=0.4)
            mixer.add_sample(hh, t_b + beat * 0.58, pan=0.28, gain=0.35)

        # 808 Deep Sub Bass
        bf = note_to_freq(p["bass"])
        mixer.add_sample(synth_bass(bf, beat * 1.8, style="dub"), bar_start, pan=0.0, gain=0.9)
        mixer.add_sample(synth_bass(bf, beat * 1.8, style="dub"), bar_start + beat * 2.0, pan=0.0, gain=0.85)

        # Lush Lo-Fi Rhodes with tape warmth
        for r_note in p["rhodes"]:
            rf = note_to_freq(r_note)
            r_samp = synth_rhodes(rf, bar * 0.9, velocity=0.8)
            mixer.add_sample(r_samp, bar_start + 0.03, pan=-0.3, gain=0.45)

        # Chill bell lead
        lf = note_to_freq(p["lead"])
        bell = synth_rhodes(lf * 1.0, beat * 1.5, velocity=0.85)
        mixer.add_sample(bell, bar_start + beat * 2.0, pan=0.35, gain=0.4)

    # Lo-fi vinyl dust
    vinyl_noise = np.random.uniform(-0.015, 0.015, mixer.num_samples)
    mixer.left += vinyl_noise
    mixer.right += vinyl_noise

    mixer.add_delay(delay_sec=0.3, feedback=0.3, mix=0.2)
    mixer.add_reverb(room_size=0.35, mix=0.18)
    return mixer


# ── Batch Generation Pipeline ──────────────────────────────────────────────

GENERATORS = {
    "vanlife_chill": generate_vanlife_chill,
    "acoustic_sunset": generate_acoustic_sunset,
    "coastal_breeze": generate_coastal_breeze,
    "alpine_acoustic": generate_alpine_acoustic,
    "jazz_trio": generate_jazz_trio,
    "folk_guitar": generate_folk_guitar,
    "reggae_sunshine": generate_reggae_sunshine,
    "cinematic_orchestral": generate_cinematic_orchestral,
    "electronic_lofi": generate_electronic_lofi,
}


def generate_all_soundtracks(duration_sec=38.0):
    """
    Generate all 9 soundtrack tracks and write both WAV and MP3
    to frontend/assets/audio/ and tools/assets/audio/.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dirs = [
        os.path.join(project_root, "frontend", "assets", "audio"),
        os.path.join(project_root, "tools", "assets", "audio"),
    ]

    print("🎵 Starting VW California Procedural Music Engine...")
    results = {}

    for name, gen_fn in GENERATORS.items():
        print(f"  🎶 Synthesizing '{name}' ({duration_sec}s)...")
        mixer = gen_fn(duration_sec=duration_sec)

        # Primary paths in frontend/assets/audio
        primary_dir = target_dirs[0]
        wav_path = os.path.join(primary_dir, f"{name}.wav")
        mp3_path = os.path.join(primary_dir, f"{name}.mp3")

        mixer.master_and_export(wav_path, mp3_path)

        # Also copy/export to tools/assets/audio
        secondary_dir = target_dirs[1]
        sec_wav = os.path.join(secondary_dir, f"{name}.wav")
        sec_mp3 = os.path.join(secondary_dir, f"{name}.mp3")
        os.makedirs(secondary_dir, exist_ok=True)
        import shutil
        if os.path.exists(wav_path):
            shutil.copyfile(wav_path, sec_wav)
        if os.path.exists(mp3_path):
            shutil.copyfile(mp3_path, sec_mp3)

        results[name] = {"wav": wav_path, "mp3": mp3_path}
        print(f"    ✓ Generated {name}.mp3 and {name}.wav")

    print("✅ All 9 soundtrack tracks generated successfully!")
    return results


if __name__ == "__main__":
    generate_all_soundtracks(duration_sec=38.0)
