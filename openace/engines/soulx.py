from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
from pypinyin import Style, lazy_pinyin

from openace.core.models import Note, Project, Track
from openace.core.phonemes import PhonemeError, cantonese_jyutping_syllables, ensure_note_phonemes
from openace.core.pitch import midi_to_hz, note_expression_cents
from openace.core.timing import validate_absolute_beat_anchor

from .base import EngineUnavailable
from .downloader import external_dir
from .vram import VRAMManager

HOP_MS = 20.0


def soulx_repo_path() -> Path:
    return Path(os.environ.get("OPENACE_SOULX_REPO", external_dir() / "SoulX-Singer")).resolve()


def _load_phoneset(repo: Path) -> set[str]:
    path = repo / "soulxsinger/utils/phoneme/phone_set.json"
    if not path.exists():
        raise EngineUnavailable(f"SoulX-Singer phone set missing: {path}; run scripts/bootstrap_models.py")
    return set(json.loads(path.read_text(encoding="utf-8")))


def _mandarin_syllables(text: str, phoneset: set[str]) -> List[str]:
    syllables: List[str] = []
    for char in text:
        if char.isspace() or char in "，。！？、,.!?":
            continue
        values = lazy_pinyin(char, style=Style.TONE3, errors=lambda x: [])
        if not values or not values[0]:
            raise PhonemeError(f"no Mandarin pronunciation found for '{char}'")
        token = "zh_" + values[0].replace("u:", "v").replace("ü", "v")
        if token not in phoneset:
            raise PhonemeError(f"phoneme '{token}' for '{char}' is not in SoulX-Singer phoneset")
        syllables.append(token)
    if not syllables:
        raise PhonemeError(f"no Mandarin syllables in '{text}'")
    return syllables


def _english_words(text: str, phoneset: set[str]) -> List[str]:
    try:
        import cmudict  # type: ignore
    except ImportError as exc:
        raise PhonemeError("English score rendering requires the cmudict package") from exc
    import re

    lexicon = cmudict.dict()
    words: List[str] = []
    for word in re.findall(r"[A-Za-z']+", text.lower()):
        if word not in lexicon:
            raise PhonemeError(f"English word '{word}' is not in CMUdict; no fallback lyric is allowed")
        phones = []
        for phone in lexicon[word][0]:
            if not re.search(r"\d$", phone):
                phone = phone + "0"
            token = "en_" + phone
            if token not in phoneset:
                raise PhonemeError(f"English phone '{token}' is not in SoulX-Singer phoneset")
            phones.append(token[3:])
        words.append("en_" + "-".join(phones))
    if not words:
        raise PhonemeError(f"no English words in '{text}'")
    return words


def _canonical_language(language: str) -> str:
    lowered = language.lower()
    if lowered.startswith("en"):
        return "English"
    if lowered in {"yue", "cantonese", "zh-hk"}:
        return "Cantonese"
    return "Mandarin"


def _cantonese_syllables(text: str, phoneset: set[str]) -> List[str]:
    syllables = []
    for syllable in cantonese_jyutping_syllables(text):
        token = "yue_" + syllable
        if token not in phoneset:
            raise PhonemeError(f"Cantonese syllable '{token}' is not in SoulX-Singer phoneset")
        syllables.append(token)
    return syllables


def lyric_to_soulx_tokens(text: str, language: str, phoneset: set[str]) -> List[str]:
    language = language.lower()
    if language in {"zh", "zh-cn", "mandarin", "cmn"}:
        return _mandarin_syllables(text, phoneset)
    if language in {"en", "en-us", "en-gb", "english"}:
        return _english_words(text, phoneset)
    if language in {"yue", "cantonese", "zh-hk"}:
        return _cantonese_syllables(text, phoneset)
    raise PhonemeError(f"SoulX-Singer score language unsupported by this adapter: {language}")


def _envelope_cents(points, tick: float) -> float:
    if not points:
        return 0.0
    ordered = sorted(points, key=lambda p: p.ticks)
    if tick <= ordered[0].ticks:
        return float(ordered[0].value)
    if tick >= ordered[-1].ticks:
        return float(ordered[-1].value)
    for left, right in zip(ordered, ordered[1:]):
        if left.ticks <= tick <= right.ticks:
            span = max(1e-9, right.ticks - left.ticks)
            ratio = (tick - left.ticks) / span
            return float(left.value + (right.value - left.value) * ratio)
    return 0.0


def _f0_for_notes(project: Project, notes: Sequence[Note], end_ms: int, pitch_automation=None) -> List[float]:
    frames = max(1, int(round(end_ms / HOP_MS)) + 1)
    f0 = np.zeros(frames, dtype=np.float64)
    for note in notes:
        note_start_ms = project.ticks_to_seconds(note.start_ticks) * 1000.0
        note_end_ms = project.ticks_to_seconds(note.end_ticks) * 1000.0
        note_duration_ms = max(1e-9, note_end_ms - note_start_ms)
        start = int(round(note_start_ms / HOP_MS))
        end = int(round(note_end_ms / HOP_MS))
        base = midi_to_hz(note.pitch)
        for frame in range(max(0, start), min(frames, max(start + 1, end))):
            absolute_ms = frame * HOP_MS
            t_ms = absolute_ms - note_start_ms
            cents = note_expression_cents(note, t_ms, note_duration_ms)
            if pitch_automation is not None:
                absolute_ticks = project.seconds_to_ticks_float(absolute_ms / 1000.0)
                cents += _envelope_cents(pitch_automation, absolute_ticks)
            f0[frame] = base * (2.0 ** (cents / 1200.0))
    return [round(float(x), 1) for x in f0]


def build_soulx_target_metadata(project: Project, track: Track, phoneset_path: Path) -> List[dict]:
    notes = track.sorted_notes()
    if not notes:
        raise ValueError("cannot render an empty vocal track")
    for note in notes:
        ensure_note_phonemes(note, track.language, project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0)
    validate_absolute_beat_anchor(notes, project.ppq, project.bpm, project=project)
    phoneset = set(json.loads(phoneset_path.read_text(encoding="utf-8")))

    durations: List[float] = []
    text: List[str] = []
    phonemes: List[str] = []
    pitches: List[int] = []
    types: List[int] = []
    cursor_s = 0.0

    def spacer(duration_s: float) -> None:
        if duration_s <= 0.001:
            return
        durations.append(round(duration_s, 3))
        text.append("<SP>")
        phonemes.append("<SP>")
        pitches.append(0)
        types.append(1)

    for note in notes:
        start_s = project.ticks_to_seconds(note.start_ticks)
        duration_s = project.tick_duration_seconds(note.start_ticks, note.duration_ticks)
        spacer(start_s - cursor_s)
        tokens = lyric_to_soulx_tokens(note.lyric, track.language, phoneset)
        each = duration_s / len(tokens)
        for token in tokens:
            durations.append(round(each, 3))
            text.append(note.lyric)
            phonemes.append(token)
            pitches.append(note.pitch)
            types.append(2)
        cursor_s = start_s + duration_s

    end_s = max(cursor_s + 0.25, project.ticks_to_seconds(project.duration_ticks()) + 0.05)
    spacer(end_s - cursor_s)
    end_ms = int(round(end_s * 1000.0))
    f0 = _f0_for_notes(project, notes, end_ms, track.automation.pitch_cents)
    return [
        {
            "index": f"openace_{track.id}",
            "language": _canonical_language(track.language),
            "time": [0, end_ms],
            "duration": " ".join(f"{x:.3f}".rstrip("0").rstrip(".") for x in durations),
            "text": " ".join(text),
            "phoneme": " ".join(phonemes),
            "note_pitch": " ".join(str(x) for x in pitches),
            "note_type": " ".join(str(x) for x in types),
            "f0": " ".join(str(x) for x in f0),
        }
    ]


class SoulXSingerEngine:
    def __init__(self, repo_path: Optional[Path] = None, device: str = "cuda", vram: Optional[VRAMManager] = None):
        self.repo = (repo_path or soulx_repo_path()).resolve()
        self.device = device
        self.vram = vram or VRAMManager()

    def _require(self) -> None:
        if not (self.repo / "cli/inference.py").exists():
            raise EngineUnavailable(
                f"SoulX-Singer source is missing at {self.repo}; run scripts/bootstrap_models.py"
            )

    def _model_path(self, svc: bool = False) -> Path:
        name = "model-svc.pt" if svc else "model.pt"
        path = self.repo / "pretrained_models/SoulX-Singer" / name
        if not path.exists():
            raise EngineUnavailable(
                f"Missing SoulX-Singer checkpoint {path}. Download public weights with scripts/bootstrap_models.py"
            )
        return path

    def preprocess_reference(self, reference_voice: Path, work_dir: Path, language: str = "Mandarin") -> Path:
        work_dir.mkdir(parents=True, exist_ok=True)
        canonical_language = _canonical_language(language)
        cmd = [
            sys.executable,
            "-m",
            "preprocess.pipeline",
            "--audio_path",
            str(reference_voice),
            "--save_dir",
            str(work_dir),
            "--language",
            canonical_language,
            "--device",
            self.device,
            "--vocal_sep",
            "False",
            "--max_merge_duration",
            "30000",
            "--midi_transcribe",
            "True",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.run(cmd, cwd=self.repo, env=env, check=True)
        metadata_path = work_dir / "metadata.json"
        if not metadata_path.exists():
            raise EngineUnavailable(f"preprocess did not produce expected metadata: {metadata_path}")
        return metadata_path

    def render_score(self, project: Project, track: Track, output_path: Path, reference_voice: Optional[Path] = None) -> Path:
        self._require()
        model = self._model_path(svc=False)
        reference = reference_voice or (Path(track.reference_voice_path) if track.reference_voice_path else None)
        if reference is None or not reference.exists():
            raise EngineUnavailable("zero-shot SVS requires a reference voice audio file")
        phoneset = self.repo / "soulxsinger/utils/phoneme/phone_set.json"
        metadata = build_soulx_target_metadata(project, track, phoneset)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="openace-soulx-") as tmp:
            tmpdir = Path(tmp)
            target_path = tmpdir / "target.json"
            target_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            prompt_meta = self.preprocess_reference(reference, tmpdir / "prompt", track.language)
            save_dir = tmpdir / "generated"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
            cmd = [
                sys.executable,
                "-m",
                "cli.inference",
                "--device",
                self.device,
                "--model_path",
                str(model),
                "--config",
                "soulxsinger/config/soulxsinger.yaml",
                "--prompt_wav_path",
                str(reference),
                "--prompt_metadata_path",
                str(prompt_meta),
                "--target_metadata_path",
                str(target_path),
                "--phoneset_path",
                "soulxsinger/utils/phoneme/phone_set.json",
                "--save_dir",
                str(save_dir),
                "--auto_shift",
                "--pitch_shift",
                "0",
                "--control",
                "score",
                "--fp16",
            ]
            with self.vram.acquire("soulx-singer", estimated_gb=5.5):
                subprocess.run(cmd, cwd=self.repo, env=env, check=True)
            generated = save_dir / "generated.wav"
            if not generated.exists():
                raise EngineUnavailable(f"SoulX-Singer completed without output: {generated}")
            shutil.copyfile(generated, output_path)
        return output_path

    def _extract_f0_with_preprocess(self, audio: Path, work_dir: Path) -> Path:
        work_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            "-m",
            "preprocess.pipeline",
            "--audio_path",
            str(audio),
            "--save_dir",
            str(work_dir),
            "--language",
            "Mandarin",
            "--device",
            self.device,
            "--vocal_sep",
            "False",
            "--midi_transcribe",
            "False",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.run(cmd, cwd=self.repo, env=env, check=True)
        f0 = work_dir / "vocal_f0.npy"
        if not f0.exists():
            raise EngineUnavailable(f"F0 extraction did not produce {f0}")
        return f0

    def convert_voice(self, source_audio: Path, reference_voice: Path, output_path: Path) -> Path:
        self._require()
        model = self._model_path(svc=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="openace-svc-") as tmp:
            tmpdir = Path(tmp)
            prompt_f0 = self._extract_f0_with_preprocess(reference_voice, tmpdir / "prompt")
            target_f0 = self._extract_f0_with_preprocess(source_audio, tmpdir / "target")
            save_dir = tmpdir / "generated"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
            cmd = [
                sys.executable,
                "-m",
                "cli.inference_svc",
                "--device",
                self.device,
                "--model_path",
                str(model),
                "--config",
                "soulxsinger/config/soulxsinger.yaml",
                "--prompt_wav_path",
                str(reference_voice),
                "--target_wav_path",
                str(source_audio),
                "--prompt_f0_path",
                str(prompt_f0),
                "--target_f0_path",
                str(target_f0),
                "--save_dir",
                str(save_dir),
                "--auto_shift",
                "--pitch_shift",
                "0",
                "--fp16",
            ]
            with self.vram.acquire("soulx-singer-svc", estimated_gb=5.5):
                subprocess.run(cmd, cwd=self.repo, env=env, check=True)
            generated = save_dir / "generated.wav"
            if not generated.exists():
                raise EngineUnavailable(f"SoulX-Singer-SVC completed without output: {generated}")
            shutil.copyfile(generated, output_path)
        return output_path
