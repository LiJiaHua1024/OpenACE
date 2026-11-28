import json
import zipfile

import numpy as np
import soundfile as sf

from openace.core.models import AudioClip, EnvelopePoint, Project, Track, TrackType
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
        assert manifest["processing"].startswith("static/automated track volume")
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


def test_export_pan_matches_webaudio_stereo_panner_semantics(tmp_path):
    sr = 24000
    stereo_path = tmp_path / "stereo.wav"
    mono_path = tmp_path / "mono.wav"
    sf.write(stereo_path, np.ones((sr // 2, 2), dtype=np.float32) * 0.2, sr)
    sf.write(mono_path, np.ones(sr // 2, dtype=np.float32) * 0.2, sr)
    project = Project(title="Pan", bpm=120)
    right = project.add_track(Track(name="Right", pan=1.0))
    right.clips.append(AudioClip(path=str(stereo_path), start_ticks=0, duration_ticks=480))
    mono_right = project.add_track(Track(name="MonoRight", pan=1.0))
    mono_right.clips.append(AudioClip(path=str(mono_path), start_ticks=0, duration_ticks=480))
    out = tmp_path / "pan_stems.zip"
    export_stems_zip(project, out, sample_rate=sr)
    extract = tmp_path / "pan_extract"
    with zipfile.ZipFile(out) as archive:
        archive.extractall(extract)
    stereo_data, _ = sf.read(extract / "01_Right.wav", always_2d=True)
    assert np.max(np.abs(stereo_data[:, 0])) == 0
    assert np.max(np.abs(stereo_data[:, 1])) > 0.3  # stereo hard-right sums both input channels after default 0.8 track volume
    mono_data, _ = sf.read(extract / "02_MonoRight.wav", always_2d=True)
    assert np.max(np.abs(mono_data[:, 0])) == 0
    assert 0.14 < np.max(np.abs(mono_data[:, 1])) <= 0.17


def test_volume_and_pan_automation_export_uses_timeline_positions(tmp_path):
    sr = 24000
    source = tmp_path / "source.wav"
    sf.write(source, np.ones((sr, 2), dtype=np.float32) * 0.2, sr)
    project = Project(title="Mix automation", bpm=120)
    track = project.add_track(Track(name="Automated", type=TrackType.AUDIO, volume=0.1, pan=-1.0))
    # At 120 BPM, 960 ticks is one second. Automation is absolute and overrides static mixer values.
    track.automation.volume = [EnvelopePoint(ticks=0, value=1.0), EnvelopePoint(ticks=960, value=0.0)]
    track.automation.pan = [EnvelopePoint(ticks=0, value=-1.0), EnvelopePoint(ticks=960, value=1.0)]
    track.clips.append(AudioClip(path=str(source), start_ticks=0, duration_ticks=960))
    output = tmp_path / "mix.zip"
    export_stems_zip(project, output, sample_rate=sr)
    extract = tmp_path / "extract"
    with zipfile.ZipFile(output) as archive:
        archive.extractall(extract)
    data, _ = sf.read(extract / "01_Automated.wav", always_2d=True)
    first = slice(int(sr * 0.05), int(sr * 0.2))
    last = slice(int(sr * 0.8), int(sr * 0.95))
    assert float(np.mean(data[first, 0])) > float(np.mean(data[first, 1])) * 3
    assert float(np.mean(data[last, 1])) > float(np.mean(data[last, 0])) * 3
    assert float(np.mean(np.abs(data[first]))) > float(np.mean(np.abs(data[last]))) * 3
    assert float(np.max(np.abs(data))) > 0.15  # automation value 1.0 overrides the quieter static volume 0.1


def test_master_and_stem_export_musical_range_slices_absolute_timeline(tmp_path, monkeypatch):
    sr = 24000
    source = tmp_path / "ranged.wav"
    samples = np.zeros((sr, 2), dtype=np.float32)
    samples[sr // 2:] = 0.2
    sf.write(source, samples, sr)
    project = Project(title="Range", bpm=120)
    track = project.add_track(Track(name="Range", type=TrackType.AUDIO, volume=1.0))
    track.clips.append(AudioClip(path=str(source), start_ticks=0, duration_ticks=960))

    captured = {}
    def capture(samples_out, output_path, sample_rate):
        captured["samples"] = samples_out.copy()
        return output_path
    monkeypatch.setattr("openace.exporters.master.write_standards_compliant_master", capture)
    export_master_wav(project, tmp_path / "range.wav", sample_rate=sr, start_ticks=240, end_ticks=720)
    ranged = captured["samples"]
    assert len(ranged) == sr // 2  # 240–720 ticks is 0.25–0.75s at 120 BPM
    assert np.max(np.abs(ranged[: sr // 4])) == 0
    assert np.max(np.abs(ranged[sr // 4:])) > 0.1

    output = tmp_path / "range_stems.zip"
    export_stems_zip(project, output, sample_rate=sr, start_ticks=240, end_ticks=720)
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("stems_manifest.json"))
        assert manifest["range_ticks"] == {"start": 240, "end": 720}
        archive.extract("01_Range.wav", tmp_path / "range_extract")
    stem, stem_sr = sf.read(tmp_path / "range_extract" / "01_Range.wav", always_2d=True)
    assert stem_sr == sr
    assert len(stem) == sr // 2
    assert np.max(np.abs(stem[: sr // 4])) == 0
    assert np.max(np.abs(stem[sr // 4:])) > 0.1


def test_export_range_validation_requires_ordered_pair(tmp_path):
    project = Project(title="Invalid range", bpm=120)
    try:
        export_master_wav(project, tmp_path / "bad.wav", start_ticks=480, end_ticks=None)
        assert False, "missing end should fail"
    except ValueError as exc:
        assert "requires both" in str(exc)
    try:
        export_master_wav(project, tmp_path / "bad.wav", start_ticks=720, end_ticks=480)
        assert False, "reversed range should fail"
    except ValueError as exc:
        assert "greater than" in str(exc)
