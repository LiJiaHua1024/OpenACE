import json

import numpy as np
import pytest
from pathlib import Path
from types import SimpleNamespace

from openace.core.models import Note, Project, Track
from openace.engines.soulx import SoulXSingerEngine


def _write_generated_wav(path: Path) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.linspace(0.0, 1.0, 7200, dtype=np.float32), 24000)


def _fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "soulx"
    (repo / "cli").mkdir(parents=True)
    (repo / "cli/inference.py").write_text("", encoding="utf-8")
    (repo / "soulxsinger/utils/phoneme").mkdir(parents=True)
    (repo / "soulxsinger/utils/phoneme/phone_set.json").write_text(
        json.dumps(["<PAD>", "<SP>", "<BOW>", "<EOW>", "<SEP>", "zh_ni3", "zh_hao3"]),
        encoding="utf-8",
    )
    model = repo / "pretrained_models/SoulX-Singer/model.pt"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"checkpoint")
    return repo


def test_score_render_uses_melody_f0_control_without_auto_transpose(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    engine = SoulXSingerEngine(repo_path=repo)
    project = Project(bpm=120)
    track = Track(name="Lead", language="zh")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    project.add_track(track)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"wav")
    commands = []

    monkeypatch.setattr(SoulXSingerEngine, "preprocess_reference", lambda self, *args, **kwargs: tmp_path / "prompt.json")

    def fake_run(cmd, cancellation, **kwargs):
        commands.append(cmd)
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        _write_generated_wav(save_dir / "generated.wav")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    output = engine.render_score(project, track, tmp_path / "out.wav", reference_voice=reference)

    import soundfile as sf
    rendered, sample_rate = sf.read(str(output))
    assert sample_rate == 24000
    assert len(rendered) == 4800
    assert rendered[0] == pytest.approx(1.0 / 3.0, abs=0.002)

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd[cmd.index("--control") + 1] == "melody"
    assert "--auto_shift" not in cmd
    assert cmd[cmd.index("--pitch_shift") + 1] == "0"


def test_svc_preserves_source_absolute_pitch_without_auto_transpose(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    (repo / "pretrained_models/SoulX-Singer/model-svc.pt").write_bytes(b"checkpoint")
    engine = SoulXSingerEngine(repo_path=repo)
    source = tmp_path / "source.wav"
    reference = tmp_path / "reference.wav"
    source.write_bytes(b"source")
    reference.write_bytes(b"reference")
    commands = []

    monkeypatch.setattr(SoulXSingerEngine, "_extract_f0_with_preprocess", lambda self, audio, work_dir, *args, **kwargs: tmp_path / f"{audio.stem}_f0.npy")

    def fake_run(cmd, cancellation, **kwargs):
        commands.append(cmd)
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        _write_generated_wav(save_dir / "generated.wav")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    engine.convert_voice(source, reference, tmp_path / "converted.wav")

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd[cmd.index("-m") + 1] == "cli.inference_svc"
    assert "--auto_shift" not in cmd
    assert cmd[cmd.index("--pitch_shift") + 1] == "0"


def test_reference_preprocess_cache_reuses_content_language_and_revision_key(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    cache_root = tmp_path / "cache"
    monkeypatch.setenv("OPENACE_SOULX_CACHE", str(cache_root))
    engine = SoulXSingerEngine(repo_path=repo)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"voice-bytes")
    commands = []

    def fake_run(cmd, cancellation, **kwargs):
        commands.append(list(cmd))
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / "metadata.json").write_text('[{"duration": "1", "phoneme": "zh_ni3"}]', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    first = engine.preprocess_reference(reference, tmp_path / "first", "Mandarin")
    second = engine.preprocess_reference(reference, tmp_path / "second", "Mandarin")

    assert len(commands) == 1
    assert first == second
    assert first.exists()
    assert cache_root in first.parents
    assert first.read_text(encoding="utf-8").startswith('[{"duration"')

    english = engine.preprocess_reference(reference, tmp_path / "english", "English")
    assert len(commands) == 2
    assert english != first

    reference.write_bytes(b"changed-voice-bytes")
    changed = engine.preprocess_reference(reference, tmp_path / "changed", "Mandarin")
    assert len(commands) == 3
    assert changed != first


def test_svc_f0_preprocess_cache_reuses_identical_audio(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    cache_root = tmp_path / "cache"
    monkeypatch.setenv("OPENACE_SOULX_CACHE", str(cache_root))
    engine = SoulXSingerEngine(repo_path=repo)
    audio = tmp_path / "vocal.wav"
    audio.write_bytes(b"same-audio")
    commands = []

    def fake_run(cmd, cancellation, **kwargs):
        commands.append(list(cmd))
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        np.save(save_dir / "vocal_f0.npy", np.array([0.0, 220.0], dtype=np.float32))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    first = engine._extract_f0_with_preprocess(audio, tmp_path / "first")
    second = engine._extract_f0_with_preprocess(audio, tmp_path / "second")

    assert len(commands) == 1
    assert first == second
    assert first.exists()
    assert cache_root in first.parents
    assert np.load(first).tolist() == [0.0, 220.0]

    audio.write_bytes(b"different-audio")
    changed = engine._extract_f0_with_preprocess(audio, tmp_path / "changed")
    assert len(commands) == 2
    assert changed != first


def test_repeated_score_render_reuses_reference_preprocess_cache(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    monkeypatch.setenv("OPENACE_SOULX_CACHE", str(tmp_path / "cache"))
    engine = SoulXSingerEngine(repo_path=repo)
    project = Project(bpm=120)
    track = Track(name="Lead", language="zh")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    project.add_track(track)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"voice-bytes")
    commands = []

    def fake_run(cmd, cancellation, **kwargs):
        commands.append(list(cmd))
        if "preprocess.pipeline" in cmd:
            save_dir = Path(cmd[cmd.index("--save_dir") + 1])
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / "metadata.json").write_text('[{"duration": "1", "phoneme": "zh_ni3"}]', encoding="utf-8")
        else:
            save_dir = Path(cmd[cmd.index("--save_dir") + 1])
            save_dir.mkdir(parents=True, exist_ok=True)
            _write_generated_wav(save_dir / "generated.wav")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    engine.render_score(project, track, tmp_path / "first.wav", reference_voice=reference)
    engine.render_score(project, track, tmp_path / "second.wav", reference_voice=reference)

    preprocess_count = sum(1 for cmd in commands if "preprocess.pipeline" in cmd)
    inference_count = sum(1 for cmd in commands if "cli.inference" in cmd)
    assert preprocess_count == 1
    assert inference_count == 2


def test_invalid_reference_cache_is_recomputed_and_cache_write_failure_is_nonfatal(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    monkeypatch.setenv("OPENACE_SOULX_CACHE", str(tmp_path / "cache"))
    engine = SoulXSingerEngine(repo_path=repo)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"voice-bytes")
    commands = []

    def fake_run(cmd, cancellation, **kwargs):
        commands.append(list(cmd))
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / "metadata.json").write_text('[{"duration": "1", "phoneme": "zh_ni3"}]', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    cached = engine.preprocess_reference(reference, tmp_path / "first", "Mandarin")
    cached.write_text("corrupt", encoding="utf-8")
    recomputed = engine.preprocess_reference(reference, tmp_path / "second", "Mandarin")
    assert len(commands) == 2
    assert recomputed == cached
    assert recomputed.read_text(encoding="utf-8").startswith('[{"duration"')

    def broken_copy(source, destination):
        raise OSError("cache read-only")

    monkeypatch.setattr("openace.engines.soulx._atomic_copy", broken_copy)
    reference.write_bytes(b"uncacheable-voice")
    fallback_workdir = tmp_path / "fallback"
    fallback = engine.preprocess_reference(reference, fallback_workdir, "Mandarin")
    assert len(commands) == 3
    assert fallback == fallback_workdir / "metadata.json"
    assert fallback.exists()


def test_score_preprocess_and_inference_share_one_vram_reservation(tmp_path, monkeypatch):
    from contextlib import contextmanager

    repo = _fake_repo(tmp_path)
    engine = SoulXSingerEngine(repo_path=repo)
    events = []

    class RecordingVRAM:
        @contextmanager
        def acquire(self, engine_name, estimated_gb):
            events.append("vram-enter")
            yield
            events.append("vram-exit")

    engine.vram = RecordingVRAM()
    project = Project(bpm=120)
    track = Track(name="Lead", language="zh")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    project.add_track(track)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"wav")

    def preprocess(*args, **kwargs):
        events.append("preprocess")
        return tmp_path / "prompt.json"

    def infer(cmd, cancellation, **kwargs):
        events.append("inference")
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        _write_generated_wav(save_dir / "generated.wav")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(SoulXSingerEngine, "preprocess_reference", preprocess)
    monkeypatch.setattr("openace.engines.soulx.run_cancellable", infer)
    engine.render_score(project, track, tmp_path / "out.wav", reference_voice=reference)

    assert events == ["vram-enter", "preprocess", "inference", "vram-exit"]


def test_svc_f0_extraction_and_inference_share_one_vram_reservation(tmp_path, monkeypatch):
    from contextlib import contextmanager

    repo = _fake_repo(tmp_path)
    (repo / "pretrained_models/SoulX-Singer/model-svc.pt").write_bytes(b"checkpoint")
    engine = SoulXSingerEngine(repo_path=repo)
    events = []

    class RecordingVRAM:
        @contextmanager
        def acquire(self, engine_name, estimated_gb):
            events.append("vram-enter")
            yield
            events.append("vram-exit")

    engine.vram = RecordingVRAM()
    source = tmp_path / "source.wav"
    reference = tmp_path / "reference.wav"
    source.write_bytes(b"source")
    reference.write_bytes(b"reference")

    def extract(self, audio, work_dir, *args, **kwargs):
        events.append(f"f0:{audio.stem}")
        return tmp_path / f"{audio.stem}.npy"

    def infer(cmd, cancellation, **kwargs):
        events.append("inference")
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        _write_generated_wav(save_dir / "generated.wav")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(SoulXSingerEngine, "_extract_f0_with_preprocess", extract)
    monkeypatch.setattr("openace.engines.soulx.run_cancellable", infer)
    engine.convert_voice(source, reference, tmp_path / "converted.wav")

    assert events == ["vram-enter", "f0:reference", "f0:source", "inference", "vram-exit"]


def test_svc_manual_and_auto_transpose_map_to_upstream_contract(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    (repo / "pretrained_models/SoulX-Singer/model-svc.pt").write_bytes(b"checkpoint")
    engine = SoulXSingerEngine(repo_path=repo)
    source = tmp_path / "source.wav"
    reference = tmp_path / "reference.wav"
    source.write_bytes(b"source")
    reference.write_bytes(b"reference")
    commands = []
    monkeypatch.setattr(SoulXSingerEngine, "_extract_f0_with_preprocess", lambda self, audio, work_dir, *args, **kwargs: tmp_path / f"{audio.stem}_f0.npy")

    def fake_run(cmd, cancellation, **kwargs):
        commands.append(list(cmd))
        save_dir = Path(cmd[cmd.index("--save_dir") + 1])
        save_dir.mkdir(parents=True, exist_ok=True)
        _write_generated_wav(save_dir / "generated.wav")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    engine.convert_voice(source, reference, tmp_path / "down.wav", pitch_shift=-3)
    engine.convert_voice(source, reference, tmp_path / "auto.wav", auto_shift=True)

    manual, automatic = commands
    assert manual[manual.index("--pitch_shift") + 1] == "-3"
    assert "--auto_shift" not in manual
    assert automatic[automatic.index("--pitch_shift") + 1] == "0"
    assert "--auto_shift" in automatic
