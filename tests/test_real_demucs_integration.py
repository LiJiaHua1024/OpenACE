import os
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from openace.engines.separation import DemucsStemSeparator


@pytest.mark.skipif(os.environ.get("OPENACE_RUN_REAL_DEMUCS") != "1", reason="expensive optional real Demucs integration test")
def test_real_demucs_produces_distinct_nonzero_stems(tmp_path):
    sr = 44100
    t = np.arange(sr * 2) / sr
    instrumental = 0.18 * np.sin(2 * np.pi * 180 * t)
    vocal_like = 0.12 * np.sin(2 * np.pi * 900 * t)
    mixture = (instrumental + vocal_like).astype(np.float32)
    source = tmp_path / "mixture.wav"
    sf.write(source, mixture, sr, subtype="PCM_16")

    vocal_path, accompaniment_path = DemucsStemSeparator().separate(source, tmp_path / "separated")

    assert vocal_path.exists() and accompaniment_path.exists()
    vocal, vocal_sr = sf.read(vocal_path, always_2d=True)
    accompaniment, accompaniment_sr = sf.read(accompaniment_path, always_2d=True)
    assert vocal_sr == accompaniment_sr == sr
    assert vocal.shape[0] == accompaniment.shape[0] == len(mixture)
    vocal_mono = vocal.mean(axis=1)
    accompaniment_mono = accompaniment.mean(axis=1)
    assert np.sqrt(np.mean(vocal_mono**2)) > 0.0001
    assert np.sqrt(np.mean(accompaniment_mono**2)) > 0.01
    assert not np.allclose(vocal_mono, accompaniment_mono, atol=1e-4)
