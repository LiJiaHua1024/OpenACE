import numpy as np

from openace.core.expression import apply_dynamic_envelope, envelope_value
from openace.core.models import EnvelopePoint, Project, Track


def test_dynamic_envelope_interpolates_and_applies_gain():
    project = Project(bpm=120)
    track = Track(name="Lead")
    track.automation.dynamic = [
        EnvelopePoint(ticks=0, value=0.0),
        EnvelopePoint(ticks=960, value=1.0),
    ]
    sr = 48000
    t = np.arange(sr) / sr
    audio = np.column_stack([np.sin(2 * np.pi * 220 * t), np.sin(2 * np.pi * 220 * t)]).astype(np.float32)
    rendered, applied = apply_dynamic_envelope(audio, sr, project, track)
    assert applied
    assert rendered.shape == audio.shape
    first = np.sqrt(np.mean(rendered[: sr // 4] ** 2))
    last = np.sqrt(np.mean(rendered[-sr // 4:] ** 2))
    assert last / first > 2.0
    assert np.max(np.abs(np.diff(rendered[:, 0], axis=0))) < 0.25


def test_empty_dynamic_envelope_is_transparent():
    project = Project()
    track = Track(name="Lead")
    audio = np.ones((100, 2), dtype=np.float32) * 0.2
    rendered, applied = apply_dynamic_envelope(audio, 48000, project, track)
    assert not applied
    assert np.array_equal(rendered, audio)


def test_envelope_value_interpolates_linearly():
    points = [EnvelopePoint(ticks=480, value=1.0), EnvelopePoint(ticks=0, value=0.0)]
    assert envelope_value(points, 240) == 0.5
    assert envelope_value(points, -10) == 0.0
    assert envelope_value(points, 999) == 1.0


def test_dynamic_envelope_prevents_output_clipping():
    project = Project(bpm=120)
    track = Track(name="Lead")
    track.automation.dynamic = [EnvelopePoint(ticks=0, value=1.0)]
    audio = np.ones((4800, 2), dtype=np.float32) * 0.9
    rendered, applied = apply_dynamic_envelope(audio, 48000, project, track)
    assert applied
    assert np.max(np.abs(rendered)) <= 0.980001


def test_air_envelope_emphasizes_existing_high_frequency_content():
    from openace.core.expression import apply_air_envelope
    from openace.core.models import EnvelopePoint, Project, Track

    sr = 48000
    t = np.arange(sr) / sr
    audio = (0.08 * np.sin(2 * np.pi * 5000 * t))[:, None].astype(np.float32)
    project = Project(title="air", bpm=120)
    track = Track(name="Lead")
    track.automation.air = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=960, value=1.0)]
    processed, applied = apply_air_envelope(audio, sr, project, track)
    assert applied
    first = processed[: sr // 4, 0]
    last = processed[-sr // 4 :, 0]
    assert np.sqrt(np.mean(last ** 2)) > np.sqrt(np.mean(first ** 2)) * 1.5


def test_air_envelope_is_transparent_when_empty():
    from openace.core.expression import apply_air_envelope
    from openace.core.models import Project, Track

    audio = np.ones((128, 2), dtype=np.float32) * 0.1
    processed, applied = apply_air_envelope(audio, 48000, Project(), Track(name="Lead"))
    assert not applied
    assert np.array_equal(processed, audio)


def test_energy_envelope_increases_existing_harmonic_density():
    from openace.core.expression import apply_energy_envelope
    from scipy import signal

    sr = 48000
    t = np.arange(sr) / sr
    audio = (0.18 * np.sin(2 * np.pi * 220 * t))[:, None].astype(np.float32)
    project = Project(title="energy", bpm=120)
    track = Track(name="Lead")
    track.automation.energy = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=960, value=1.0)]
    processed, applied = apply_energy_envelope(audio, sr, project, track)
    assert applied
    sos = signal.butter(2, 1000, btype="highpass", fs=sr, output="sos")
    harmonic = signal.sosfiltfilt(sos, processed[:, 0])
    first_ratio = np.sqrt(np.mean(harmonic[: sr // 4] ** 2)) / np.sqrt(np.mean(processed[: sr // 4, 0] ** 2))
    last_ratio = np.sqrt(np.mean(harmonic[-sr // 4 :] ** 2)) / np.sqrt(np.mean(processed[-sr // 4 :, 0] ** 2))
    assert last_ratio > first_ratio * 1.25


def test_tension_envelope_modulates_presence_band():
    from openace.core.expression import apply_tension_envelope

    sr = 48000
    t = np.arange(sr) / sr
    audio = (0.12 * np.sin(2 * np.pi * 2200 * t))[:, None].astype(np.float32)
    project = Project(title="tension", bpm=120)
    track = Track(name="Lead")
    track.automation.tension = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=960, value=1.0)]
    processed, applied = apply_tension_envelope(audio, sr, project, track)
    assert applied
    first = np.sqrt(np.mean(processed[: sr // 4, 0] ** 2))
    last = np.sqrt(np.mean(processed[-sr // 4 :, 0] ** 2))
    assert last > first * 1.35


def test_empty_energy_and_tension_are_transparent():
    from openace.core.expression import apply_energy_envelope, apply_tension_envelope

    audio = np.ones((256, 2), dtype=np.float32) * 0.1
    for apply in (apply_energy_envelope, apply_tension_envelope):
        processed, applied = apply(audio, 48000, Project(), Track(name="Lead"))
        assert not applied
        assert np.array_equal(processed, audio)
