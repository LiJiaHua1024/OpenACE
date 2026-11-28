import json
from pathlib import Path
from types import SimpleNamespace

from openace.core.models import Note, Project, Track
from openace.engines.soulx import SoulXSingerEngine


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
        (save_dir / "generated.wav").write_bytes(b"generated")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    engine.render_score(project, track, tmp_path / "out.wav", reference_voice=reference)

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
        (save_dir / "generated.wav").write_bytes(b"generated")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("openace.engines.soulx.run_cancellable", fake_run)
    engine.convert_voice(source, reference, tmp_path / "converted.wav")

    assert len(commands) == 1
    cmd = commands[0]
    assert cmd[cmd.index("-m") + 1] == "cli.inference_svc"
    assert "--auto_shift" not in cmd
    assert cmd[cmd.index("--pitch_shift") + 1] == "0"
