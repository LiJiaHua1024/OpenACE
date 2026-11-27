import numpy as np
import pytest

from openace.core.breath import apply_breath_events, extract_breath_donor
from openace.core.models import Breath, Note, Project, TempoPoint, Track


def noise_reference(sr=24000, seconds=2.0, amplitude=0.08):
    rng = np.random.default_rng(7)
    data = np.zeros(int(sr * seconds), dtype=np.float32)
    data[int(0.15 * sr):int(0.75 * sr)] = rng.normal(0.0, amplitude, int(0.60 * sr)).astype(np.float32)
    return data


def test_extract_breath_donor_finds_real_broadband_noise_not_tone():
    sr = 24000
    reference = noise_reference(sr)
    donor = extract_breath_donor(reference, sr)
    assert donor is not None
    assert len(donor) >= sr // 8
    assert np.sqrt(np.mean(donor**2)) == pytest.approx(1.0, rel=0.2)

    t = np.arange(sr * 2) / sr
    tone = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    assert extract_breath_donor(tone, sr) is None


def test_breath_event_overlays_reference_donor_at_exact_timeline_position():
    sr = 24000
    project = Project(bpm=120, ppq=480)
    track = Track(name="Lead")
    track.notes.append(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.breaths.append(Breath(start_ticks=480, duration_ticks=240))
    audio = np.zeros((sr, 1), dtype=np.float32)
    reference = noise_reference(sr)
    processed, result = apply_breath_events(audio, sr, project, track, reference, sr)
    assert result.applied == 1
    assert result.donor_source == "reference voice"
    before = processed[int(0.15 * sr):int(0.45 * sr), 0]
    inside = processed[int(0.55 * sr):int(0.70 * sr), 0]
    after = processed[int(0.80 * sr):int(0.95 * sr), 0]
    inside_rms = float(np.sqrt(np.mean(inside**2)))
    assert inside_rms > 0.002
    assert float(np.sqrt(np.mean(before**2))) < inside_rms / 20
    assert float(np.sqrt(np.mean(after**2))) < inside_rms / 20


def test_breath_event_timing_follows_piecewise_tempo_map():
    sr = 24000
    project = Project(bpm=120, ppq=480)
    project.tempo_map = [TempoPoint(ticks=0, bpm=120), TempoPoint(ticks=960, bpm=60)]
    track = Track(name="Lead")
    track.breaths.append(Breath(start_ticks=1200, duration_ticks=240))
    audio = np.zeros((sr * 3, 1), dtype=np.float32)
    reference = noise_reference(sr)
    processed, result = apply_breath_events(audio, sr, project, track, reference, sr)
    assert result.applied == 1
    # Tick 1200 begins 0.5s after the 60 BPM boundary at 1.0s, so the breath is 1.5-2.0s.
    early = processed[int(1.05 * sr):int(1.40 * sr), 0]
    inside = processed[int(1.60 * sr):int(1.90 * sr), 0]
    late = processed[int(2.10 * sr):int(2.40 * sr), 0]
    inside_rms = float(np.sqrt(np.mean(inside**2)))
    assert inside_rms > 0.002
    assert float(np.sqrt(np.mean(early**2))) < inside_rms / 20
    assert float(np.sqrt(np.mean(late**2))) < inside_rms / 20


def test_breath_event_without_real_donor_is_honest_noop():
    sr = 24000
    project = Project()
    track = Track(name="Lead")
    track.breaths.append(Breath(start_ticks=0, duration_ticks=240))
    t = np.arange(sr) / sr
    audio = (0.08 * np.sin(2 * np.pi * 220 * t))[:, None].astype(np.float32)
    processed, result = apply_breath_events(audio, sr, project, track)
    assert result.applied == 0
    assert "no synthetic noise inserted" in result.detail
    assert np.allclose(processed, audio)
