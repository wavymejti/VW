"""
Unit tests for the procedural music engine (tools/audio_generator.py).

Tests:
- Note to frequency translation
- ADSR envelope generation
- Physical string synthesis (Karplus-Strong)
- Instrument synthesizers (Rhodes, Bass, Drums)
- Stereo TrackMixer and mastering
- Procedural song generation for categories
"""

import os
import wave
import pytest
import numpy as np

from tools.audio_generator import (
    note_to_freq,
    adsr,
    karplus_strong,
    synth_rhodes,
    synth_bass,
    synth_kick,
    synth_snare,
    synth_hihat,
    synth_reggae_rimshot,
    synth_timpani,
    synth_string_pad,
    TrackMixer,
    generate_vanlife_chill,
    generate_jazz_trio,
    generate_reggae_sunshine,
    SAMPLE_RATE,
)


class TestDSPPrimitives:
    """Tests for core DSP and musical primitives."""

    def test_note_to_freq(self):
        """Standard musical pitch frequencies should match 12-TET tuning."""
        assert abs(note_to_freq("A4") - 440.0) < 1e-2
        assert abs(note_to_freq("A3") - 220.0) < 1e-2
        assert abs(note_to_freq("A5") - 880.0) < 1e-2
        assert abs(note_to_freq("C4") - 261.63) < 0.1

    def test_adsr_envelope(self):
        """ADSR envelope should be well-formed without NaNs."""
        env = adsr(1000, a=0.1, d=0.2, s=0.6, r=0.2)
        assert len(env) == 1000
        assert np.max(env) <= 1.01
        assert np.min(env) >= -0.01
        assert not np.isnan(env).any()

    def test_karplus_strong_string(self):
        """Karplus-Strong algorithm should synthesize decaying acoustic string."""
        sample = karplus_strong(freq=220.0, duration_sec=0.5, sr=SAMPLE_RATE)
        assert len(sample) == int(0.5 * SAMPLE_RATE)
        assert not np.isnan(sample).any()
        # Early energy should be higher than tail energy (natural acoustic decay)
        head_energy = np.mean(sample[:500] ** 2)
        tail_energy = np.mean(sample[-500:] ** 2)
        assert head_energy > tail_energy

    def test_instrument_synthesizers(self):
        """Synthesizers should generate valid audio signals within amplitude bounds."""
        rhodes = synth_rhodes(freq=440.0, duration_sec=0.5)
        assert len(rhodes) == int(0.5 * SAMPLE_RATE)
        assert np.max(np.abs(rhodes)) > 0.05

        bass = synth_bass(freq=110.0, duration_sec=0.5, style="warm")
        assert len(bass) == int(0.5 * SAMPLE_RATE)
        assert np.max(np.abs(bass)) > 0.05

        pad = synth_string_pad(freq=330.0, duration_sec=0.5)
        assert len(pad) == int(0.5 * SAMPLE_RATE)

    def test_percussion_synthesizers(self):
        """Drum synthesizers should produce punchy transients."""
        kick = synth_kick()
        assert len(kick) > 1000
        assert np.max(np.abs(kick)) > 0.5

        snare = synth_snare()
        assert len(snare) > 1000

        hihat = synth_hihat()
        assert len(hihat) > 500


class TestTrackMixerAndExport:
    """Tests for stereo mixing, effects, and file mastering."""

    def test_stereo_mixer_and_export(self, tmp_path):
        """Mixer should create valid 16-bit 44.1kHz stereo WAV file."""
        mixer = TrackMixer(duration_sec=2.0)
        kick = synth_kick()
        mixer.add_sample(kick, start_sec=0.0, pan=-0.5, gain=0.8)
        mixer.add_sample(kick, start_sec=1.0, pan=0.5, gain=0.8)

        wav_file = str(tmp_path / "test_out.wav")
        mixer.master_and_export(wav_file, mp3_path=None, fade_sec=0.5)

        assert os.path.exists(wav_file)
        with wave.open(wav_file, "r") as wf:
            assert wf.getnchannels() == 2
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnframes() == int(2.0 * SAMPLE_RATE)

    def test_song_generators_structure(self):
        """Procedural song generator should return populated stereo TrackMixer."""
        # Test 4 seconds snippet of vanlife_chill
        mixer = generate_vanlife_chill(duration_sec=4.0)
        assert mixer.num_samples == int(4.0 * SAMPLE_RATE)
        # Should have substantial stereo audio energy
        rms_l = np.sqrt(np.mean(mixer.left ** 2))
        rms_r = np.sqrt(np.mean(mixer.right ** 2))
        assert rms_l > 0.01
        assert rms_r > 0.01
