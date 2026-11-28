import json
import zipfile
from pathlib import Path

import mido
import numpy as np
import pytest
import yaml

from openace.core.models import AudioClip, EnvelopePoint, Note, Phoneme, PitchPoint, Project, Track, TrackType, Vibrato
from openace.exporters.master import export_master_wav, export_lyrics_video
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.exporters.svp import export_svp
from openace.exporters.ustx import export_ustx
from openace.exporters.vpr import export_vpr
from openace.importers.midi import import_midi
from openace.importers.ustx import import_ustx


def sample_project():
    project = Project(title="Interop Test", bpm=120)
    track = Track(name="Lead")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你", velocity=37))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="好"))
    project.add_track(track)
    return project


def test_midi_roundtrip_preserves_notes_and_lyrics(tmp_path):
    project = sample_project()
    path = export_midi(project, tmp_path / "song.mid")
    imported = import_midi(path)
    notes = imported.tracks[0].notes
    assert [(n.start_ticks, n.duration_ticks, n.pitch, n.velocity) for n in notes] == [(0, 480, 60, 37), (480, 480, 62, 90)]
    assert "".join(n.lyric for n in notes) == "你好"


def test_midi_channel_and_program_roundtrip(tmp_path):
    project = sample_project()
    project.tracks[0].midi_channel = 4
    project.tracks[0].midi_program = 52
    path = export_midi(project, tmp_path / "channels.mid")
    mid = mido.MidiFile(str(path))
    note_track = mid.tracks[1]
    assert next(m for m in note_track if m.type == "program_change").program == 52
    assert {m.channel for m in note_track if m.type in {"note_on", "note_off"}} == {4}
    imported = import_midi(path)
    assert imported.tracks[0].midi_channel == 4
    assert imported.tracks[0].midi_program == 52


def test_midi_import_splits_channels_without_note_collisions(tmp_path):
    path = tmp_path / "split.mid"
    mid = mido.MidiFile(ticks_per_beat=480)
    mt = mido.MidiTrack()
    mt.append(mido.MetaMessage("track_name", name="Layered", time=0))
    mt.append(mido.Message("note_on", channel=0, note=60, velocity=80, time=0))
    mt.append(mido.Message("note_on", channel=1, note=60, velocity=90, time=0))
    mt.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=240))
    mt.append(mido.Message("note_off", channel=1, note=60, velocity=0, time=240))
    mt.append(mido.MetaMessage("end_of_track", time=0))
    mid.tracks.append(mt)
    mid.save(str(path))
    imported = import_midi(path)
    assert len(imported.tracks) == 2
    assert [track.midi_channel for track in imported.tracks] == [0, 1]
    assert [track.notes[0].duration_ticks for track in imported.tracks] == [240, 480]


def test_lrc_contains_real_timed_lyrics(tmp_path):
    path = export_lrc(sample_project(), tmp_path / "song.lrc")
    text = path.read_text(encoding="utf-8")
    assert "[00:00.00]你" in text
    assert "[00:00.50]好" in text


def test_ustx_is_yaml_with_openutau_note_structure(tmp_path):
    path = export_ustx(sample_project(), tmp_path / "song.ustx")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["ustx_version"] == "0.10"
    # OpenUtau 0.10 fixes resolution at 480 and marks the property YamlIgnore.
    assert "resolution" not in data
    note = data["voice_parts"][0]["notes"][0]
    assert note["tone"] == 60
    assert note["lyric"] == "你"
    assert list(note) == [
        "position", "duration", "tone", "lyric", "pitch", "vibrato", "tuning",
        "phoneme_expressions", "phoneme_overrides",
    ]
    assert note["pitch"]["data"] == [
        {"x": -40, "y": 0, "shape": "io"},
        {"x": 40, "y": 0, "shape": "io"},
    ]
    assert note["vibrato"] == {
        "length": 0, "period": 175, "depth": 25, "in": 10, "out": 10,
        "shift": 0, "drift": 0, "vol_link": 0,
    }


def test_ustx_matches_source_derived_units_and_curve_schema(tmp_path):
    project = sample_project()
    track = project.tracks[0]
    track.volume = 0.5
    track.pan = 0.25
    track.color = "#7c5cff"
    track.automation.dynamic = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=480, value=1.0)]
    track.automation.pitch_cents = [EnvelopePoint(ticks=0, value=-25), EnvelopePoint(ticks=480, value=50)]
    note = track.notes[0]
    note.pitch_curve = [PitchPoint(offset_ms=12.5, cents=30.0)]
    note.vibrato = Vibrato(start_ratio=0.25, depth_cents=40, frequency_hz=4.0, phase=1.5707963267948966)
    note.phonemes = [Phoneme(symbol="n i", start_ms=0, duration_ms=100)]
    path = export_ustx(project, tmp_path / "units.ustx")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    exported_track = data["tracks"][0]
    assert exported_track["volume"] == pytest.approx(-6.021, abs=0.001)
    assert exported_track["pan"] == 25.0
    assert exported_track["track_color"] == "Purple"
    assert exported_track["phonemizer"] == "OpenUtau.Core.DefaultPhonemizer"
    part = data["voice_parts"][0]
    assert part["duration"] == 960
    exported_note = part["notes"][0]
    assert exported_note["pitch"]["data"] == [{"x": -40, "y": 0, "shape": "io"}, {"x": 12.5, "y": 3.0, "shape": "io"}]
    assert exported_note["vibrato"]["length"] == 75.0
    assert exported_note["vibrato"]["period"] == 250.0
    assert exported_note["vibrato"]["depth"] == 40.0
    assert exported_note["vibrato"]["shift"] == pytest.approx(25.0, abs=0.01)
    assert exported_note["phoneme_overrides"] == [{"index": 0, "phoneme": "n i"}]
    assert "offset" not in exported_note["phoneme_overrides"][0]
    curves = {curve["abbr"]: curve for curve in part["curves"]}
    assert curves["dyn"]["xs"] == [0, 480]
    assert curves["dyn"]["ys"] == [0, 60]
    assert curves["pitd"]["xs"] == [0, 480]
    assert curves["pitd"]["ys"] == [-25, 50]


def test_ustx_exports_audio_clips_as_source_derived_wave_parts(tmp_path):
    import soundfile as sf

    source = tmp_path / "clip-source.wav"
    sr = 48000
    sf.write(source, np.zeros((sr, 2), dtype=np.float32), sr, subtype="PCM_24")
    project = sample_project()
    track = project.tracks[0]
    track.clips.append(AudioClip(
        path=str(source), start_ticks=480, offset_ticks=240, duration_ticks=480,
        fade_in_ticks=48, fade_out_ticks=96, label="Hook",
    ))
    out_dir = tmp_path / "export"
    data = yaml.safe_load(export_ustx(project, out_dir / "song.ustx").read_text(encoding="utf-8"))
    assert len(data["wave_parts"]) == 1
    part = data["wave_parts"][0]
    assert part["name"] == "Hook"
    assert part["track_no"] == 0
    assert part["position"] == 480
    assert Path(part["relative_path"]).as_posix().endswith("clip-source.wav")
    assert part["file_duration_ms"] == pytest.approx(1000.0)
    assert part["skip"] == 240
    assert part["trim"] == 240
    assert part["fadein"] == 48
    assert part["fadeout"] == 96
    # OpenUtau derives visible duration as full source duration minus skip/trim.
    assert 960 - part["skip"] - part["trim"] == 480
    assert "_openace_duration_ticks" not in part


def test_ustx_import_roundtrip_restores_notes_units_curves_and_wave_parts(tmp_path):
    import soundfile as sf

    source = tmp_path / "ustx-roundtrip.wav"
    sr = 48000
    sf.write(source, np.zeros((sr, 2), dtype=np.float32), sr, subtype="PCM_24")
    project = sample_project()
    track = project.tracks[0]
    track.volume = 0.5
    track.pan = 0.25
    track.automation.dynamic = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=480, value=1.0)]
    track.automation.pitch_cents = [EnvelopePoint(ticks=0, value=-25), EnvelopePoint(ticks=480, value=50)]
    track.notes[0].pitch_curve = [PitchPoint(offset_ms=12.5, cents=30.0)]
    track.notes[0].vibrato = Vibrato(start_ratio=0.25, depth_cents=40, frequency_hz=4.0, phase=1.5707963267948966)
    track.notes[0].phonemes = [Phoneme(symbol="n i", start_ms=0, duration_ms=100)]
    track.clips.append(AudioClip(
        path=str(source), start_ticks=480, offset_ticks=240, duration_ticks=480,
        fade_in_ticks=48, fade_out_ticks=96, label="Hook",
    ))
    exported = export_ustx(project, tmp_path / "roundtrip.ustx")
    imported = import_ustx(exported)
    assert imported.title == project.title
    assert imported.bpm == project.bpm
    imported_track = imported.tracks[0]
    assert imported_track.volume == pytest.approx(0.5, abs=0.001)
    assert imported_track.pan == pytest.approx(0.25)
    assert [(n.start_ticks, n.duration_ticks, n.pitch, n.lyric) for n in imported_track.notes] == [
        (0, 480, 60, "你"), (480, 480, 62, "好"),
    ]
    assert imported_track.notes[0].pitch_curve[0].offset_ms == pytest.approx(12.5)
    assert imported_track.notes[0].pitch_curve[0].cents == pytest.approx(30.0)
    assert imported_track.notes[0].vibrato is not None
    assert imported_track.notes[0].vibrato.start_ratio == pytest.approx(0.25)
    assert imported_track.notes[0].vibrato.frequency_hz == pytest.approx(4.0)
    assert imported_track.notes[0].phonemes[0].symbol == "n i"
    assert [(p.ticks, p.value) for p in imported_track.automation.dynamic] == [(0, 0.5), (480, 1.0)]
    assert [(p.ticks, p.value) for p in imported_track.automation.pitch_cents] == [(0, -25.0), (480, 50.0)]
    assert len(imported_track.clips) == 1
    clip = imported_track.clips[0]
    assert (clip.start_ticks, clip.offset_ticks, clip.duration_ticks) == (480, 240, 480)
    assert (clip.fade_in_ticks, clip.fade_out_ticks) == (48, 96)
    assert Path(clip.path).resolve() == source.resolve()
    assert clip.label == "Hook"
    # Serializer-default untouched pitch points must not be mistaken for user curves.
    assert imported_track.notes[1].pitch_curve == []


def test_ustx_zip_package_import_preserves_bundled_wave_media(tmp_path):
    import soundfile as sf
    from fastapi.testclient import TestClient
    import openace.server.app as app_module

    package_source = tmp_path / "package"
    package_source.mkdir()
    source = package_source / "media.wav"
    sr = 48000
    sf.write(source, np.zeros((sr, 2), dtype=np.float32), sr, subtype="PCM_24")
    project = sample_project()
    project.tracks[0].clips.append(AudioClip(
        path=str(source), start_ticks=480, offset_ticks=240, duration_ticks=480,
        fade_in_ticks=48, fade_out_ticks=96, label="Packaged Hook",
    ))
    ustx = export_ustx(project, package_source / "song.ustx")
    archive = tmp_path / "song-package.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(ustx, "song.ustx")
        zipped.write(source, "media.wav")
    client = TestClient(app_module.app)
    with archive.open("rb") as handle:
        response = client.post("/api/import/ustx", files={"file": ("song-package.zip", handle, "application/zip")})
    assert response.status_code == 200
    clip = response.json()["tracks"][0]["clips"][0]
    assert Path(clip["path"]).exists()
    assert "ustx_packages" in clip["path"]
    assert (clip["offset_ticks"], clip["duration_ticks"], clip["label"]) == (240, 480, "Packaged Hook")


def test_ustx_zip_package_rejects_path_traversal(tmp_path):
    from fastapi.testclient import TestClient
    import openace.server.app as app_module

    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../evil.ustx", "name: evil")
    client = TestClient(app_module.app)
    with archive.open("rb") as handle:
        response = client.post("/api/import/ustx", files={"file": ("evil.zip", handle, "application/zip")})
    assert response.status_code == 422
    assert "unsafe USTX package path" in response.text


def test_ustx_import_endpoint_returns_project(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import openace.server.app as app_module

    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    client = TestClient(app_module.app)
    exported = export_ustx(sample_project(), tmp_path / "endpoint.ustx")
    with exported.open("rb") as handle:
        response = client.post("/api/import/ustx", files={"file": ("endpoint.ustx", handle, "application/x-yaml")})
    assert response.status_code == 200
    project = response.json()
    assert project["title"] == "Interop Test"
    assert project["tracks"][0]["notes"][0]["lyric"] == "你"
    assert project["tracks"][0]["notes"][0]["pitch_curve"] == []


def test_ustx_scales_non480_project_ticks_to_openutau_resolution(tmp_path):
    project = sample_project()
    project.ppq = 240
    track = project.tracks[0]
    track.notes = [Note(start_ticks=120, duration_ticks=240, pitch=60, lyric="你")]
    track.automation.pitch_cents = [EnvelopePoint(ticks=120, value=10)]
    data = yaml.safe_load(export_ustx(project, tmp_path / "scaled.ustx").read_text(encoding="utf-8"))
    part = data["voice_parts"][0]
    assert part["notes"][0]["position"] == 240
    assert part["notes"][0]["duration"] == 480
    assert part["curves"][0]["xs"] == [240]
    assert part["duration"] == 960


def test_svp_is_json_with_notes_and_render_config(tmp_path):
    path = export_svp(sample_project(), tmp_path / "song.svp")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 153
    assert data["tracks"][0]["mainGroup"]["notes"][0]["pitch"] == 60
    assert data["renderConfig"]["sampleRate"] == 48000


def test_svp_voice_reference_vibrato_seconds_and_automation_units(tmp_path):
    project = sample_project()
    track = project.tracks[0]
    track.automation.pitch_cents = [EnvelopePoint(ticks=0, value=-50), EnvelopePoint(ticks=480, value=25)]
    track.automation.dynamic = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=480, value=1.0)]
    track.automation.tension = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=480, value=1.0)]
    track.automation.air = [EnvelopePoint(ticks=0, value=0.0), EnvelopePoint(ticks=480, value=0.5)]
    track.notes[0].vibrato = Vibrato(start_ratio=0.25, depth_cents=40, frequency_hz=4.0)
    data = json.loads(export_svp(project, tmp_path / "song.svp").read_text(encoding="utf-8"))
    exported_track = data["tracks"][0]
    group = exported_track["mainGroup"]
    ref = exported_track["mainRef"]
    assert group["uuid"] == ref["groupID"]
    assert ref["blickOffset"] == 0
    assert ref["database"] == {"name": ""}
    assert ref["voice"]["voicing"] == 1.0
    attrs = group["notes"][0]["attributes"]
    assert attrs["dF0Vbr"] == 0.4
    assert attrs["fF0Vbr"] == 4.0
    assert attrs["tF0VbrStart"] == pytest.approx(0.125)
    parameters = group["parameters"]
    assert parameters["pitchDelta"]["points"] == [0, -50.0, 705600000, 25.0]
    assert parameters["loudness"]["points"] == [0, 0.0, 705600000, 6.0]
    assert parameters["tension"]["points"] == [0, 0.0, 705600000, 1.0]
    assert parameters["breathiness"]["points"] == [0, -1.0, 705600000, 0.0]
    assert data["tracks"][0]["mainRef"]["database"]["name"] == ""


def test_vpr_is_zip_with_project_sequence(tmp_path):
    path = export_vpr(sample_project(), tmp_path / "song.vpr")
    with zipfile.ZipFile(path) as archive:
        data = json.loads(archive.read("Project/sequence.json"))
    assert data["tracks"][0]["parts"][0]["notes"][0]["noteNum"] == 60
    assert data["masterTrack"]["samplingRate"] == 48000


def test_mp4_lyric_video_is_timed_and_matches_audio_duration(tmp_path):
    import subprocess

    import numpy as np
    import soundfile as sf

    from openace.core.audio import write_wav
    from openace.exporters.master import export_lyrics_video

    project = sample_project()
    sr = 48000
    audio = np.zeros((sr, 2), dtype=np.float32)
    wav = tmp_path / "master.wav"
    write_wav(wav, audio, sr)
    mp4 = export_lyrics_video(project, wav, tmp_path / "lyrics.mp4")
    assert mp4.exists() and mp4.stat().st_size > 1000
    ass_text = (tmp_path / "lyrics.ass").read_text(encoding="utf-8")
    assert "{\\kf50}你{\\kf50}好" in ass_text
    assert "Style: Title" in ass_text
    assert "OPENACE" in ass_text
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp4)],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert abs(float(probe.stdout.strip()) - 1.0) < 0.15

    frame = tmp_path / "karaoke-frame.png"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.6", "-i", str(mp4), "-frames:v", "1", str(frame)],
        check=True,
    )
    import matplotlib.image as mpimg

    image = mpimg.imread(frame)
    if image.dtype != np.uint8:
        image = (image[..., :3] * 255).astype(np.uint8)
    else:
        image = image[..., :3]
    red, green, blue = image[..., 0], image[..., 1], image[..., 2]
    y_coordinates = np.arange(image.shape[0])[:, None]
    amber = (red > 180) & (green > 90) & (green < 210) & (blue < 100)
    neutral = (
        (red > 120)
        & (np.abs(red.astype(int) - green.astype(int)) < 25)
        & (np.abs(green.astype(int) - blue.astype(int)) < 25)
    )
    lyric_pixels = (amber | neutral) & (y_coordinates > 850)
    _ys, xs = np.where(lyric_pixels)
    assert len(xs) > 500
    x_start, x_end = xs.min(), xs.max() + 1
    midpoint = (x_start + x_end) // 2
    first_amber = int(amber[:, x_start:midpoint].sum())
    second_amber = int(amber[:, midpoint:x_end].sum())
    second_neutral = int(neutral[:, midpoint:x_end].sum())
    assert first_amber > 300
    assert first_amber > second_amber * 2
    assert second_neutral > 150


def test_lyrics_video_separates_overlapping_multi_track_phrases(tmp_path):
    from openace.core.audio import write_wav

    project = Project(title="Layered Karaoke", bpm=120)
    lead = Track(name="Lead")
    lead.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="主"))
    harmony = Track(name="Harmony")
    harmony.add_note(Note(start_ticks=240, duration_ticks=480, pitch=64, lyric="和"))
    project.add_track(lead)
    project.add_track(harmony)
    sr = 48000
    wav = tmp_path / "master.wav"
    write_wav(wav, np.zeros((sr, 2), dtype=np.float32), sr)
    export_lyrics_video(project, wav, tmp_path / "layered.mp4")
    ass_text = (tmp_path / "layered.ass").read_text(encoding="utf-8")
    assert "Style: Lyrics,Noto Sans CJK SC,66" in ass_text
    assert "Style: LyricsLane1,Noto Sans CJK SC,61" in ass_text
    assert "100,100,96,1" in ass_text
    assert "100,100,172,1" in ass_text
    assert ",Lyrics,," in ass_text
    assert ",LyricsLane1,," in ass_text


def test_master_export_honors_clip_source_offset_and_duration(tmp_path):
    from openace.core.audio import read_audio, write_wav
    from openace.core.models import AudioClip, Project, Track, TrackType
    from openace.exporters.master import export_master_wav

    sr = 48000
    t = np.arange(sr * 2) / sr
    audio = np.zeros((sr * 2, 2), dtype=np.float32)
    tone = np.sin(2 * np.pi * 440 * t[sr:])
    audio[sr:, 0] = tone
    audio[sr:, 1] = tone
    source = tmp_path / "source.wav"
    write_wav(source, audio, sr, normalize=False)

    project = Project(title="clip offset", bpm=120)
    track = project.add_track(Track(name="BGM", type=TrackType.ACCOMPANIMENT))
    track.volume = 1.0
    track.clips.append(AudioClip(path=str(source), start_ticks=0, duration_ticks=480, offset_ticks=960))
    output = tmp_path / "master.wav"
    export_master_wav(project, output, sample_rate=sr)
    rendered, rendered_sr = read_audio(output)
    assert rendered_sr == sr
    first_half = rendered[: int(sr * 0.45)]
    assert np.sqrt(np.mean(first_half ** 2)) > 0.05
    assert len(rendered) <= int(sr * 0.55)


def test_master_export_applies_clip_fade_in_and_fade_out(tmp_path):
    from openace.core.audio import read_audio, write_wav
    from openace.core.models import AudioClip, Project, Track, TrackType
    from openace.exporters.master import export_master_wav

    sr = 48000
    tone_t = np.arange(sr) / sr
    tone = np.sin(2 * np.pi * 440 * tone_t).astype(np.float32) * 0.5
    audio = np.column_stack([tone, tone])
    source = tmp_path / "constant.wav"
    write_wav(source, audio, sr, normalize=False)
    project = Project(title="clip fades", bpm=120)
    track = project.add_track(Track(name="BGM", type=TrackType.ACCOMPANIMENT))
    track.volume = 1.0
    track.clips.append(AudioClip(path=str(source), start_ticks=0, duration_ticks=960, fade_in_ticks=240, fade_out_ticks=240))
    output = tmp_path / "master.wav"
    export_master_wav(project, output, sample_rate=sr)
    rendered, _ = read_audio(output)
    mono = rendered.mean(axis=1)
    peak = float(np.max(np.abs(mono)))
    assert peak > 0.05

    def envelope_rms(seconds: float, width: float = 0.012) -> float:
        center = int(seconds * sr)
        half = int(width * sr / 2)
        return float(np.sqrt(np.mean(mono[max(0, center - half):center + half] ** 2)))

    full_scale = envelope_rms(0.25)
    assert abs(mono[0]) < peak * 0.08
    assert 0.35 * full_scale < envelope_rms(0.125) < 0.65 * full_scale
    assert envelope_rms(0.25) > 0.85 * full_scale
    assert 0.35 * full_scale < envelope_rms(0.875) < 0.65 * full_scale
    assert abs(mono[-1]) < peak * 0.08


def test_master_export_meets_minus14_lufs_and_true_peak_ceiling(tmp_path):
    import soundfile as sf

    from openace.core.models import AudioClip, Project, Track
    from openace.exporters.master import _ffmpeg_loudness_measurement

    sr = 48000
    t = np.arange(sr * 5) / sr
    musical = (
        0.15 * np.sin(2 * np.pi * 110 * t)
        + 0.06 * np.sin(2 * np.pi * 330 * t)
        + 0.025 * np.sin(2 * np.pi * 660 * t)
    ) * (0.65 + 0.35 * np.sin(2 * np.pi * 2 * t))
    source = tmp_path / "musical.wav"
    sf.write(source, np.column_stack([musical, musical]).astype(np.float32), sr, subtype="PCM_24")
    project = Project(title="loudness compliance", bpm=120)
    track = project.add_track(Track(name="BGM", volume=1.0))
    track.clips.append(AudioClip(path=str(source), start_ticks=0, duration_ticks=9600))
    output = tmp_path / "master.wav"
    export_master_wav(project, output, sample_rate=sr)
    measurement = _ffmpeg_loudness_measurement(output)
    assert abs(measurement["input_i"] - (-14.0)) <= 0.3
    assert measurement["input_tp"] < -1.0


def test_master_export_dynamic_fallback_handles_peaky_material(tmp_path):
    import soundfile as sf

    from openace.core.models import AudioClip, Project, Track
    from openace.exporters.master import _ffmpeg_loudness_measurement

    sr = 48000
    t = np.arange(sr * 5) / sr
    musical = (0.1 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    for index in range(5):
        start = int(index * sr + 1000)
        length = int(0.008 * sr)
        envelope = np.hanning(length)
        musical[start:start + length] += 0.85 * envelope * np.sin(2 * np.pi * 1800 * np.arange(length) / sr)
    source = tmp_path / "peaky.wav"
    sf.write(source, np.column_stack([musical, musical]), sr, subtype="PCM_24")
    input_measurement = _ffmpeg_loudness_measurement(source)
    assert input_measurement["input_tp"] + (-14.0 - input_measurement["input_i"]) > -1.1

    project = Project(title="peaky loudness compliance", bpm=120)
    track = project.add_track(Track(name="BGM", volume=1.0))
    track.clips.append(AudioClip(path=str(source), start_ticks=0, duration_ticks=9600))
    output = tmp_path / "master.wav"
    export_master_wav(project, output, sample_rate=sr)
    measurement = _ffmpeg_loudness_measurement(output)
    assert abs(measurement["input_i"] - (-14.0)) <= 0.3
    assert measurement["input_tp"] < -1.0


def test_automatic_crossfade_gain_is_equal_power():
    from openace.core.crossfade import crossfade_gain_at
    from openace.core.models import AudioClip, Project, Track

    project = Project(bpm=120)
    track = project.add_track(Track(name="BGM"))
    first = AudioClip(path="a.wav", start_ticks=0, duration_ticks=480)
    second = AudioClip(path="b.wav", start_ticks=240, duration_ticks=480)
    track.clips.extend([first, second])
    assert crossfade_gain_at(track, first, 240) == pytest.approx(1.0)
    assert crossfade_gain_at(track, second, 240) == pytest.approx(0.0)
    assert crossfade_gain_at(track, first, 360) == pytest.approx(0.5 ** 0.5, abs=0.01)
    assert crossfade_gain_at(track, second, 360) == pytest.approx(0.5 ** 0.5, abs=0.01)
    first_power = crossfade_gain_at(track, first, 400) ** 2
    second_power = crossfade_gain_at(track, second, 400) ** 2
    assert first_power + second_power == pytest.approx(1.0)


def test_master_export_applies_automatic_overlap_crossfade(tmp_path):
    import soundfile as sf

    source = tmp_path / "constant.wav"
    sr = 48000
    t = np.arange(sr * 2) / sr
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32) * 0.2
    sf.write(source, np.column_stack([tone, tone]), sr, subtype="PCM_24")
    project = Project(title="xfade", bpm=120)
    track = project.add_track(Track(name="BGM", volume=1.0))
    track.clips.extend([
        AudioClip(path=str(source), start_ticks=0, duration_ticks=480),
        AudioClip(path=str(source), start_ticks=240, duration_ticks=480),
    ])
    output = tmp_path / "master.wav"
    export_master_wav(project, output, sample_rate=sr)
    data, out_sr = sf.read(output, always_2d=True)
    assert out_sr == sr

    def rms_at(seconds, width=0.012):
        center = int(seconds * sr)
        half = int(width * sr / 2)
        return float(np.sqrt(np.mean(data[center - half:center + half] ** 2)))

    outside = rms_at(0.15)
    boundary = rms_at(0.26)
    middle = rms_at(0.375)
    assert boundary / outside < 1.15
    assert 1.25 < middle / outside < 1.55

def test_project_duplicate_and_delete_endpoints(tmp_path):
    from fastapi.testclient import TestClient
    import openace.server.app as app_module

    client = TestClient(app_module.app)
    created = client.post("/api/projects", json={"title": "Project Ops"})
    assert created.status_code == 200
    project_id = created.json()["id"]
    duplicated = client.post(f"/api/projects/{project_id}/duplicate")
    assert duplicated.status_code == 200
    copy = duplicated.json()
    assert copy["id"] != project_id
    assert copy["title"] == "Project Ops Copy"
    deleted = client.delete(f"/api/projects/{copy['id']}")
    assert deleted.status_code == 200
    assert client.delete(f"/api/projects/{copy['id']}").status_code == 404


def test_karaoke_style_customization_changes_ass_and_visibility(tmp_path):
    from openace.core.audio import write_wav

    project = sample_project()
    project.metadata = {
        "karaoke_style": {
            "font_size": 80,
            "lane_spacing": 100,
            "sung_color": "#12ab34",
            "unsung_color": "#eeeeee",
            "background_theme": "ember",
            "background_motion": False,
            "show_title": False,
            "show_brand": False,
        }
    }
    harmony = Track(name="Harmony")
    harmony.add_note(Note(start_ticks=0, duration_ticks=480, pitch=64, lyric="和"))
    project.add_track(harmony)
    sr = 48000
    wav = tmp_path / "master.wav"
    write_wav(wav, np.zeros((sr, 2), dtype=np.float32), sr)
    export_lyrics_video(project, wav, tmp_path / "custom.mp4")
    ass_text = (tmp_path / "custom.ass").read_text(encoding="utf-8")
    assert "Style: Lyrics,Noto Sans CJK SC,80,&H0034AB12,&H00EEEEEE" in ass_text
    assert "100,100,96,1" in ass_text
    assert "100,100,196,1" in ass_text
    assert "Style: Title" in ass_text  # style definition remains available
    assert ",Title,," not in ass_text
    assert ",Brand,," not in ass_text


def test_karaoke_style_settings_clamp_invalid_metadata():
    from openace.exporters.master import karaoke_style_settings

    project = sample_project()
    project.metadata = {"karaoke_style": {"font_size": "bad", "lane_spacing": 999, "sung_color": "red", "background_theme": "unknown"}}
    style = karaoke_style_settings(project)
    assert style["font_size"] == 66
    assert style["lane_spacing"] == 112
    assert style["sung_color"] == "#ffb000"
    assert style["background_theme"] == "midnight"



def test_ustx_export_uses_empty_host_singer_for_unmapped_openace_voice(tmp_path):
    import yaml

    project = sample_project()
    path = export_ustx(project, tmp_path / "host_singer.ustx")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["tracks"][0]["singer"] == ""
    assert "zero-shot-reference" in data["voice_parts"][0]["comment"]


def test_ustx_host_singer_mapping_roundtrip_preserves_openace_voice(tmp_path):
    project = sample_project()
    track = project.tracks[0]
    track.voice_id = "zero-shot-reference"
    track.openutau_singer = "友人"
    track.openutau_phonemizer = "OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer"
    exported = export_ustx(project, tmp_path / "mapped.ustx")
    data = yaml.safe_load(exported.read_text(encoding="utf-8"))
    assert data["tracks"][0]["singer"] == "友人"
    assert data["tracks"][0]["phonemizer"] == "OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer"
    imported = import_ustx(exported)
    assert imported.tracks[0].openutau_singer == "友人"
    assert imported.tracks[0].openutau_phonemizer == "OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer"
    assert imported.tracks[0].voice_id == track.voice_id


def test_ustx_snap_first_transitions_are_regenerated_not_frozen(tmp_path):
    project = Project(title="snap", ppq=480, bpm=120)
    track = Track(name="lead", type=TrackType.VOCAL)
    track.notes = [
        Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="a"),
        Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="ka"),
    ]
    project.tracks = [track]
    exported = export_ustx(project, tmp_path / "snap.ustx")
    data = yaml.safe_load(exported.read_text(encoding="utf-8"))
    assert data["voice_parts"][0]["notes"][1]["pitch"]["data"][0]["y"] == -20
    imported = import_ustx(exported)
    assert imported.tracks[0].notes[1].pitch_curve == []
    assert imported.tracks[0].notes[1].pitch_snap_first is True
    imported.tracks[0].notes[0].pitch = 64
    reexported = export_ustx(imported, tmp_path / "snap-reordered.ustx")
    regenerated = yaml.safe_load(reexported.read_text(encoding="utf-8"))
    assert regenerated["voice_parts"][0]["notes"][1]["pitch"]["data"][0]["y"] == 20


def test_cli_and_mcp_export_atoms_support_mp4(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import openace.cli as cli
    import openace.mcp_server as mcp
    from openace.core.project_store import ProjectStore

    project = sample_project()
    store = ProjectStore(tmp_path / "projects")
    store.save(project)
    calls = []

    def fake_mp4_export(target, output):
        calls.append((target.id, output))
        output.write_bytes(b"ftyp-mp4")
        return output

    monkeypatch.setattr(cli, "services", lambda: (store, None))
    monkeypatch.setattr(cli, "export_lyrics_video_master", fake_mp4_export)
    monkeypatch.setattr(mcp, "store", store)
    monkeypatch.setattr(mcp, "export_lyrics_video_master", fake_mp4_export)

    cli_output = tmp_path / "cli.mp4"
    cli.cmd_export(SimpleNamespace(project=project.id, format="mp4", output=str(cli_output), start_ticks=None, end_ticks=None))
    assert cli_output.read_bytes() == b"ftyp-mp4"

    mcp_output = tmp_path / "mcp.mp4"
    payload = json.loads(mcp.export_project(project.id, "mp4", str(mcp_output)))
    assert payload["bytes"] == len(b"ftyp-mp4")
    assert mcp_output.read_bytes() == b"ftyp-mp4"
    assert [call[0] for call in calls] == [project.id, project.id]
