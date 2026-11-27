import json
import zipfile

import numpy as np
import soundfile as sf

from openace.core.models import AudioClip, Project, Track, TrackType
from openace.exporters.master import export_master_wav, export_stems_zip


def test_export_stems_zip_preserves_track_separation_offsets_and_mixer_audibility(tmp_path):
    sr = 24000
    source_a = tmp_path / "a.wav"
    source_b = tmp_path / "b.wav"
    muted_source = tmp_path / "muted.wav"
    sf.write(source_a, np.ones((sr, 2), dtype=np.float32) * 0.2, sr)
    sf.write(source_b, np.ones((sr, 2), dtype=np.float32) * 0.1, sr)
    sf.write(muted_source, np.ones((sr, 2), dtype=np.float32) * 0.4, sr)

    project = Project(title="Stems", bpm=120)
    lead = project.add_track(Track(name="Lead Vocal", type=TrackType.VOCAL, volume=0.5))
    lead.clips.append(AudioClip(path=str(source_a), start_ticks=480, duration_ticks=480, offset_ticks=240))
    bgm = project.add_track(Track(name="BGM", type=TrackType.ACCOMPANIMENT, volume=0.8))
    bgm.clips.append(AudioClip(path=str(source_b), start_ticks=0, duration_ticks=960))
    muted = project.add_track(Track(name="Muted", type=TrackType.AUDIO, mute=True))
    muted.clips.append(AudioClip(path=str(muted_source), start_ticks=0, duration_ticks=960))

    output = tmp_path / "stems.zip"
    export_stems_zip(project, output, sample_rate=sr)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert "01_Lead_Vocal.wav" in names
        assert "02_BGM.wav" in names
        assert not any("Muted" in name for name in names)
        manifest = json.loads(archive.read("stems_manifest.json"))
        assert manifest["processing"].startswith("track volume")
        assert [item["track_name"] for item in manifest["tracks"]] == ["Lead Vocal", "BGM"]
        archive.extract("01_Lead_Vocal.wav", tmp_path / "extracted")
        lead_data, lead_sr = sf.read(tmp_path / "extracted" / "01_Lead_Vocal.wav", always_2d=True)
        assert lead_sr == sr
        assert not (tmp_path / "stems").exists()
        # Quarter-note timeline offset at 120 BPM plus quarter-note clip duration.
        assert len(lead_data) == sr
        assert np.max(np.abs(lead_data[: sr // 2])) == 0
        assert np.max(np.abs(lead_data[sr // 2 :])) > 0.05


def test_master_export_honors_solo_semantics(tmp_path, monkeypatch):
    sr = 24000
    loud = tmp_path / "loud.wav"
    quiet = tmp_path / "quiet.wav"
    sf.write(loud, np.ones((sr // 2, 2), dtype=np.float32) * 0.2, sr)
    sf.write(quiet, np.ones((sr // 2, 2), dtype=np.float32) * 0.2, sr)
    project = Project(title="Solo", bpm=120)
    solo = project.add_track(Track(name="Solo", solo=True, volume=0.5))
    solo.clips.append(AudioClip(path=str(loud), start_ticks=0, duration_ticks=480))
    other = project.add_track(Track(name="Other", volume=1.0))
    other.clips.append(AudioClip(path=str(quiet), start_ticks=0, duration_ticks=480))
    captured = {}
    def capture(samples, output_path, sample_rate):
        captured["samples"] = samples.copy()
        return output_path
    monkeypatch.setattr("openace.exporters.master.write_standards_compliant_master", capture)
    export_master_wav(project, tmp_path / "master.wav", sample_rate=sr)
    peak = float(np.max(np.abs(captured["samples"])))
    assert 0.09 < peak < 0.11
