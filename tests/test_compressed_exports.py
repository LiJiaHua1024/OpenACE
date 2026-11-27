import json
import subprocess

import numpy as np
import soundfile as sf

import openace.exporters.master as master_module
from openace.core.models import AudioClip, Project, Track
from openace.exporters.master import export_compressed_master


def test_compressed_master_formats_use_master_pipeline_and_real_codecs(tmp_path, monkeypatch):
    sr = 24000
    t = np.arange(sr, dtype=np.float32) / sr
    tone = (np.sin(2 * np.pi * 220 * t) * 0.25).astype(np.float32)
    source = tmp_path / "source.wav"
    sf.write(source, np.stack([tone, tone], axis=1), sr)

    def passthrough_master(samples, output_path, sample_rate):
        sf.write(output_path, samples, sample_rate)
        return output_path

    monkeypatch.setattr(master_module, "write_standards_compliant_master", passthrough_master)
    project = Project(title="Compressed", bpm=120)
    track = project.add_track(Track(name="Tone"))
    track.clips.append(AudioClip(path=str(source), start_ticks=0, duration_ticks=960))

    expectations = {"mp3": "mp3", "flac": "flac", "ogg": "vorbis"}
    for fmt, codec in expectations.items():
        output = tmp_path / f"master.{fmt}"
        export_compressed_master(project, output, fmt, sample_rate=sr)
        assert output.stat().st_size > 100
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name:format=duration", "-of", "json", str(output)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        info = json.loads(probe.stdout)
        assert info["streams"][0]["codec_name"] == codec
        duration = float(info["format"].get("duration", 0))
        assert 0.7 < duration < 1.5
        assert not (tmp_path / f"openace-encode-test").exists()
    flac, flac_sr = sf.read(tmp_path / "master.flac", always_2d=True)
    assert flac_sr == sr
    assert float(np.sqrt(np.mean(np.square(flac)))) > 0.05
