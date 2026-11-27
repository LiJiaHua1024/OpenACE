import numpy as np

from openace.core.expression import _seconds_to_ticks_array
from openace.core.models import Project, TempoPoint


def test_vectorized_tempo_inversion_matches_exact_scalar_step_and_linear_ramps():
    project = Project(title="tempo inverse", bpm=120)
    project.tempo_map = [
        TempoPoint(ticks=480, bpm=90, curve="step"),
        TempoPoint(ticks=960, bpm=180, curve="linear"),
        TempoPoint(ticks=1920, bpm=60, curve="step"),
    ]
    probe = np.linspace(-0.25, project.ticks_to_seconds(2400) + 0.3, 2000)
    vector = _seconds_to_ticks_array(project, probe)
    scalar = np.array([project.seconds_to_ticks_float(float(value)) for value in probe])
    assert np.max(np.abs(vector - scalar)) < 1e-7

    ramp_start = project.ticks_to_seconds(960)
    ramp_end = project.ticks_to_seconds(1920)
    inside = probe[(probe > ramp_start + 0.01) & (probe < ramp_end - 0.01)]
    assert len(inside)
    # A constant-BPM inversion would materially misplace samples inside the ramp.
    naive = 960 + (inside - ramp_start) * 90 / 60 * project.ppq
    actual = _seconds_to_ticks_array(project, inside)
    assert np.max(np.abs(actual - naive)) > 5.0
