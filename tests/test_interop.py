import json
import zipfile
from pathlib import Path

import mido
import numpy as np
import pytest
import yaml

from openace.core.models import AudioClip, Note, Project, Track
from openace.exporters.master import export_master_wav
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.exporters.svp import export_svp
from openace.exporters.ustx import export_ustx
from openace.exporters.vpr import export_vpr
from openace.importers.midi import import_midi


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


def test_lrc_contains_real_timed_lyrics(tmp_path):
    path = export_lrc(sample_project(), tmp_path / "song.lrc")
    text = path.read_text(encoding="utf-8")
    assert "[00:00.00]你" in text
    assert "[00:00.50]好" in text


def test_ustx_is_yaml_with_openutau_note_structure(tmp_path):
    path = export_ustx(sample_project(), tmp_path / "song.ustx")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["resolution"] == 480
    assert data["voice_parts"][0]["notes"][0]["tone"] == 60
    assert data["voice_parts"][0]["notes"][0]["lyric"] == "你"


def test_svp_is_json_with_notes_and_render_config(tmp_path):
    path = export_svp(sample_project(), tmp_path / "song.svp")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 153
    assert data["tracks"][0]["mainGroup"]["notes"][0]["pitch"] == 60
    assert data["renderConfig"]["sampleRate"] == 48000


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
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp4)],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert abs(float(probe.stdout.strip()) - 1.0) < 0.15


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
    audio = np.ones((sr, 2), dtype=np.float32) * 0.5
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
    assert abs(mono[0]) < peak * 0.08
    assert 0.35 * peak < mono[int(sr * 0.125)] < 0.65 * peak
    assert mono[int(sr * 0.25)] > 0.85 * peak
    assert 0.35 * peak < mono[int(sr * 0.875)] < 0.65 * peak
    assert abs(mono[-1]) < peak * 0.08


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
    sf.write(source, np.ones((sr * 2, 2), dtype=np.float32) * 0.2, sr, subtype="PCM_24")
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
