from __future__ import annotations

import hashlib
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
from openace.core.phonemes import PhonemeError, cantonese_jyutping_syllables, ensure_note_phonemes, phonemes_for_text
from openace.core.pitch import midi_to_hz, note_expression_cents, pitch_envelope_state
from openace.core.timing import validate_absolute_beat_anchor

from .base import EngineUnavailable
from .processes import CancellationToken, run_cancellable


def _run_checked(cmd, cancellation, cwd, env, label: str) -> None:
    result = run_cancellable(cmd, cancellation, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        output = (result.stdout or "")[-6000:]
        raise EngineUnavailable(f"{label} failed with exit code {result.returncode}:\n{output}")
from .downloader import external_dir
from .vram import VRAMManager

HOP_MS = 20.0
# Score metadata gets a small leading pre-roll so pre-vowel consonants can
# begin before the symbolic project start. The production renderer trims exactly
# this duration from the generated wav, preserving project-time alignment.
SCORE_PREROLL_S = 0.1


CACHE_SCHEMA_VERSION = "soulx-preprocess-v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_revision(repo: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            check=False,
        )
        revision = result.stdout.strip()
        if result.returncode == 0 and revision:
            return revision
    except (OSError, subprocess.SubprocessError):
        pass
    pipeline = repo / "preprocess" / "pipeline.py"
    if pipeline.exists():
        stat = pipeline.stat()
        return f"pipeline-{stat.st_mtime_ns}-{stat.st_size}"
    return "unknown"


def _cache_root() -> Path:
    configured = os.environ.get("OPENACE_SOULX_CACHE")
    return Path(configured).expanduser().resolve() if configured else external_dir() / ".cache" / "soulx"


def _preprocess_cache_key(audio: Path, kind: str, language: str, repo: Path, device: str) -> str:
    payload = {
        "schema": CACHE_SCHEMA_VERSION,
        "kind": kind,
        "language": language,
        "device": device,
        "audio_sha256": _sha256_file(audio),
        "repo_revision": _repo_revision(repo),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cached_artifact(audio: Path, kind: str, language: str, repo: Path, device: str, suffix: str) -> Path:
    key = _preprocess_cache_key(audio, kind, language, repo, device)
    return _cache_root() / kind / f"{key}{suffix}"


def _atomic_copy(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.{os.getpid()}.tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)
    return destination



def _valid_reference_metadata_cache(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(data, list) and bool(data) and all(
        isinstance(item, dict) and item.get("duration") and item.get("phoneme")
        for item in data
    )


def _valid_f0_cache(path: Path) -> bool:
    try:
        values = np.load(path, allow_pickle=False)
    except (OSError, ValueError):
        return False
    return isinstance(values, np.ndarray) and values.size > 0


def _cache_hit(path: Path, validator) -> bool:
    try:
        return path.exists() and validator(path)
    except OSError:
        return False


def _best_effort_atomic_copy(source: Path, destination: Path) -> Path:
    try:
        return _atomic_copy(source, destination)
    except OSError:
        return source


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
            if not re.search(r"\d$", phone) and phone in {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}:
                phone = phone + "0"
            token = "en_" + phone
            if token not in phoneset:
                raise PhonemeError(f"English phone '{token}' is not in SoulX-Singer phoneset")
            phones.append(token[3:])
        words.append("en_" + "-".join(phones))
    if not words:
        raise PhonemeError(f"no English words in '{text}'")
    return words


def _mixed_mandarin_english_tokens(text: str, phoneset: set[str]) -> List[str]:
    """Build mixed zh_/en_ tokens from explicit script segments.

    SoulX's data processor expands each token by prefix independently; it does not
    require the whole note stream to use one phone family. Cantonese is not guessed
    from Han text because its orthography is ambiguous with Mandarin.
    """
    import re

    pieces = re.findall(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?", text)
    if not pieces:
        if re.search(r"[\u3040-\u30ff]", text):
            raise PhonemeError("Japanese script is not supported in mixed Mandarin/English mode; choose a supported explicit language instead of silent substitution")
        raise PhonemeError(f"no Mandarin or English lyric units found in '{text}'")
    remainder = re.sub(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?|[\s，。！？、,.!?]+", "", text)
    if remainder:
        raise PhonemeError(f"mixed Mandarin/English lyrics contain unsupported character '{remainder[0]}'")
    tokens: List[str] = []
    for piece in pieces:
        if "\u3400" <= piece[0] <= "\u9fff" or "\uf900" <= piece[0] <= "\ufaff":
            tokens.extend(_mandarin_syllables(piece, phoneset))
        else:
            tokens.extend(_english_words(piece, phoneset))
    if not tokens:
        raise PhonemeError(f"no mixed-language SoulX tokens in '{text}'")
    return tokens


def _mixed_cantonese_english_tokens(text: str, phoneset: set[str]) -> List[str]:
    """Build explicit mixed yue_/en_ tokens without guessing Cantonese."""
    import re

    pieces = re.findall(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?", text)
    if not pieces:
        raise PhonemeError(f"no Cantonese or English lyric units found in '{text}'")
    remainder = re.sub(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?|[\s，。！？、,.!?]+", "", text)
    if remainder:
        raise PhonemeError(f"mixed Cantonese/English lyrics contain unsupported character '{remainder[0]}'")
    tokens: List[str] = []
    for piece in pieces:
        if "\u3400" <= piece[0] <= "\u9fff" or "\uf900" <= piece[0] <= "\ufaff":
            tokens.extend(_cantonese_syllables(piece, phoneset))
        else:
            tokens.extend(_english_words(piece, phoneset))
    return tokens


def _canonical_language(language: str) -> str:
    lowered = language.lower()
    if lowered.startswith("en"):
        return "English"
    if lowered in {"yue", "cantonese", "zh-hk"}:
        return "Cantonese"
    return "Mandarin"


def _metadata_language_for_track(track: Track) -> str:
    """Choose truthful dominant prompt metadata language for mixed zh/en scores."""
    lowered = track.language.lower()
    import re

    if lowered in {"mixed-yue", "yue-en", "en-yue", "cantonese-english"}:
        cjk_units = sum(len(re.findall(r"[\u3400-\u9fff\uf900-\ufaff]", note.lyric)) for note in track.notes)
        english_units = sum(len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", note.lyric)) for note in track.notes)
        return "English" if english_units > cjk_units else "Cantonese"
    if lowered not in {"mixed", "multilingual", "zh-en", "en-zh"}:
        return _canonical_language(track.language)
    cjk_units = 0
    english_units = 0
    for note in track.notes:
        cjk_units += len(re.findall(r"[\u3400-\u9fff\uf900-\ufaff]", note.lyric))
        english_units += len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", note.lyric))
    return "English" if english_units > cjk_units else "Mandarin"


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
    if language in {"mixed", "multilingual", "zh-en", "en-zh"}:
        return _mixed_mandarin_english_tokens(text, phoneset)
    if language in {"mixed-yue", "yue-en", "en-yue", "cantonese-english"}:
        return _mixed_cantonese_english_tokens(text, phoneset)
    if language in {"zh", "zh-cn", "mandarin", "cmn"}:
        return _mandarin_syllables(text, phoneset)
    if language in {"en", "en-us", "en-gb", "english"}:
        return _english_words(text, phoneset)
    if language in {"yue", "cantonese", "zh-hk"}:
        return _cantonese_syllables(text, phoneset)
    raise PhonemeError(f"SoulX-Singer score language unsupported by this adapter: {language}")


_EN_IPA_TO_ARPA = {
    "ə": ("AH0",), "ʌ": ("AH0",), "ɪ": ("IH0",), "i": ("IY0",), "u": ("UW0",),
    "ʊ": ("UH0",), "ɑ": ("AA0",), "ɒ": ("AA0",), "ɔ": ("AO0",), "ɛ": ("EH0",),
    "æ": ("AE0",), "ɝ": ("ER0",), "ɚ": ("ER0",), "aɪ": ("AY0",), "eɪ": ("EY0",),
    "aʊ": ("AW0",), "oʊ": ("OW0",), "ɔɪ": ("OY0",),
    "θ": ("TH",), "ð": ("DH",), "ʃ": ("SH",), "ʒ": ("ZH",), "tʃ": ("CH",),
    "dʒ": ("JH",), "ŋ": ("NG",), "j": ("Y",), "ɹ": ("R",), "r": ("R",),
    "ks": ("K", "S"),
}


def _english_override_tokens(symbols: List[str], phoneset: set[str]) -> List[str]:
    """Map validated custom English symbols into SoulX's grouped ARPAbet token form."""
    converted: List[str] = []
    for symbol in symbols:
        key = symbol.strip()
        replacements = _EN_IPA_TO_ARPA.get(key, (key.upper(),))
        for replacement in replacements:
            candidates = [replacement]
            if not replacement[-1:].isdigit():
                candidates.append(replacement + "0")
            match = next((candidate for candidate in candidates if "en_" + candidate in phoneset), None)
            if match is None:
                raise PhonemeError(
                    f"manual English phoneme '{symbol}' cannot be represented in the SoulX phoneset; use CMU/ARPAbet or a supported IPA symbol"
                )
            converted.append(match)
    if not converted:
        raise PhonemeError("manual English phoneme override is empty")
    return ["en_" + "-".join(converted)]


def _soulx_tokens_for_note(note: Note, language: str, phoneset: set[str]) -> List[str]:
    """Use custom pronunciation when representable, otherwise canonical lyric tokens.

    Symbol equality—not timing—is the override test because validation materializes
    automatic timed phonemes into saved projects. Upstream Mandarin/Cantonese tokens
    are syllabic, so arbitrary sub-syllable overrides cannot honestly be represented.
    """
    if not note.phonemes:
        return lyric_to_soulx_tokens(note.lyric, language, phoneset)
    try:
        automatic = [token.symbol for token in phonemes_for_text(note.lyric, language)]
    except PhonemeError:
        automatic = []
    current = [phoneme.symbol for phoneme in note.phonemes]
    if current == automatic:
        return lyric_to_soulx_tokens(note.lyric, language, phoneset)

    lowered = language.lower()
    if lowered in {"en", "en-us", "en-gb", "english"}:
        return _english_override_tokens(current, phoneset)
    if lowered in {"mixed", "multilingual", "zh-en", "en-zh"} and current and all(
        symbol in phoneset and symbol.startswith(("zh_", "en_")) for symbol in current
    ):
        return current
    if lowered in {"mixed-yue", "yue-en", "en-yue", "cantonese-english"} and current and all(
        symbol in phoneset and symbol.startswith(("yue_", "en_")) for symbol in current
    ):
        return current
    prefix = "yue_" if lowered in {"yue", "cantonese", "zh-hk"} else "zh_"
    if current and all(symbol in phoneset and symbol.startswith(prefix) for symbol in current):
        return current
    family = "Cantonese" if prefix == "yue_" else "Mandarin"
    raise PhonemeError(
        f"manual {family} sub-syllable phoneme overrides cannot be represented by SoulX's syllable-level tokens; "
        f"use exact upstream {prefix}* syllable tokens or reset the override"
    )


def _upstream_token_preonset_ms(tokens: List[str], language: str) -> float:
    """Infer whether the first upstream syllable token has a pre-vowel onset consonant."""
    if not tokens:
        return 0.0
    lowered = language.lower()
    first = tokens[0]
    if first.startswith("zh_"):
        syllable = first[3:].rstrip("123456789")
        if syllable.startswith(("zh", "ch", "sh")):
            return 45.0
        return 45.0 if syllable[:1] in set("bpmfdtnlgkhjqxrzcs") else 0.0
    if first.startswith("yue_"):
        syllable = first[4:].rstrip("123456789")
        if syllable in {"m", "ng"}:
            return 0.0
        if syllable.startswith(("gw", "kw", "ng")):
            return 45.0
        return 45.0 if syllable[:1] in set("bpmfdtnlgkhwzcsj") else 0.0
    return 0.0


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


def _f0_for_notes(project: Project, notes: Sequence[Note], end_ms: int, pitch_automation=None, leading_ms: float = 0.0) -> List[float]:
    frames = max(1, int(round(end_ms / HOP_MS)) + 1)
    f0 = np.zeros(frames, dtype=np.float64)
    for note in notes:
        note_start_ms = project.ticks_to_seconds(note.start_ticks) * 1000.0 + leading_ms
        note_end_ms = project.ticks_to_seconds(note.end_ticks) * 1000.0 + leading_ms
        note_duration_ms = max(1e-9, note_end_ms - note_start_ms)
        start = int(round(note_start_ms / HOP_MS))
        end = int(round(note_end_ms / HOP_MS))
        base = midi_to_hz(note.pitch)
        for frame in range(max(0, start), min(frames, max(start + 1, end))):
            absolute_ms = frame * HOP_MS
            t_ms = absolute_ms - note_start_ms
            cents = note_expression_cents(note, t_ms, note_duration_ms)
            voiced = True
            if pitch_automation is not None:
                project_ms = max(0.0, absolute_ms - leading_ms)
                absolute_ticks = project.seconds_to_ticks_float(project_ms / 1000.0)
                automation_cents, voiced = pitch_envelope_state(pitch_automation, absolute_ticks)
                cents += automation_cents
            if voiced:
                f0[frame] = base * (2.0 ** (cents / 1200.0))
    return [round(float(x), 1) for x in f0]


def build_soulx_target_metadata(project: Project, track: Track, phoneset_path: Path, preroll_s: float = SCORE_PREROLL_S) -> List[dict]:
    notes = track.sorted_notes()
    if not notes:
        raise ValueError("cannot render an empty vocal track")
    for note in notes:
        if note.lyric.strip() != "-":
            ensure_note_phonemes(note, track.language, project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0)
    validate_absolute_beat_anchor(notes, project.ppq, project.bpm, project=project)
    phoneset = set(json.loads(phoneset_path.read_text(encoding="utf-8")))

    durations: List[float] = []
    text: List[str] = []
    phonemes: List[str] = []
    pitches: List[int] = []
    types: List[int] = []
    cursor_s = 0.0

    def append_item(duration_s: float, text_value: str, phoneme_value: str, pitch: int, note_type: int) -> None:
        if duration_s <= 0.0005:
            return
        durations.append(float(duration_s))
        text.append(text_value)
        phonemes.append(phoneme_value)
        pitches.append(pitch)
        types.append(note_type)

    def spacer(duration_s: float) -> None:
        append_item(duration_s, "<SP>", "<SP>", 0, 1)

    def steal_time_before_onset(amount_s: float, note: Note) -> None:
        """Make room for a pre-vowel onset without overlapping the flattened stream."""
        remaining = float(amount_s)
        index = len(durations) - 1
        while remaining > 1e-9 and index >= 0:
            minimum = 0.0 if types[index] == 1 else 0.02
            reducible = max(0.0, durations[index] - minimum)
            take = min(reducible, remaining)
            durations[index] -= take
            remaining -= take
            if types[index] == 1 and durations[index] <= 0.0005:
                remaining -= durations[index]
                for values in (durations, text, phonemes, pitches, types):
                    values.pop(index)
            index -= 1
        if remaining > 1e-6:
            raise PhonemeError(
                f"note {note.id} does not have enough preceding silence or sustained tail for its consonant preonset"
            )

    continuation_token = None
    continuation_lyric = None
    for note in notes:
        project_start_s = project.ticks_to_seconds(note.start_ticks)
        duration_s = project.tick_duration_seconds(note.start_ticks, note.duration_ticks)
        project_end_s = project_start_s + duration_s
        is_continuation = note.lyric.strip() == "-"
        if is_continuation:
            if continuation_token is None or continuation_lyric is None:
                raise PhonemeError("melisma continuation '-' cannot appear before a sung lyric note")
            tokens = [continuation_token]
            text_value = continuation_lyric
            note_type = 3
            preonset_s = 0.0
        else:
            tokens = _soulx_tokens_for_note(note, track.language, phoneset)
            text_value = note.lyric
            note_type = 2
            continuation_token = tokens[-1]
            continuation_lyric = note.lyric
            negative_onsets = [p.start_ms for p in note.phonemes if not p.is_vowel and p.start_ms < 0]
            internal_preonset_ms = abs(min(negative_onsets)) if negative_onsets else 0.0
            preonset_s = max(internal_preonset_ms, _upstream_token_preonset_ms(tokens, track.language)) / 1000.0

        # Symbolic note onset is the first-vowel anchor. SoulX's public score format
        # only exposes syllable/word token durations, so the token onset is shifted
        # earlier by the validated 40-90ms pre-vowel consonant span. A leading
        # pre-roll makes that representable even at project time zero; the renderer
        # trims the pre-roll after synthesis. This is an upstream-format approximation
        # of sub-syllable timing, not a claim that SoulX exposes exact phoneme boundaries.
        desired_start_s = project_start_s - preonset_s + preroll_s
        end_s = project_end_s + preroll_s
        if desired_start_s > cursor_s:
            spacer(desired_start_s - cursor_s)
        elif desired_start_s < cursor_s:
            steal_time_before_onset(cursor_s - desired_start_s, note)
        cursor_s = desired_start_s

        total_s = end_s - desired_start_s
        if total_s <= 0.02:
            raise PhonemeError(f"note {note.id} is too short to render truthfully")
        each = total_s / len(tokens)
        for token in tokens:
            append_item(each, text_value, token, note.pitch, note_type)
        cursor_s = end_s

    project_end_timeline_s = max(
        cursor_s + 0.25,
        project.ticks_to_seconds(project.duration_ticks()) + preroll_s + 0.05,
    )
    spacer(project_end_timeline_s - cursor_s)
    end_ms = int(round(project_end_timeline_s * 1000.0))
    f0 = _f0_for_notes(project, notes, end_ms, track.automation.pitch_cents, leading_ms=preroll_s * 1000.0)
    return [
        {
            "index": f"openace_{track.id}",
            "language": _metadata_language_for_track(track),
            "time": [0, end_ms],
            "duration": " ".join(f"{x:.3f}".rstrip("0").rstrip(".") for x in durations),
            "text": " ".join(text),
            "phoneme": " ".join(phonemes),
            "note_pitch": " ".join(str(x) for x in pitches),
            "note_type": " ".join(str(x) for x in types),
            "f0": " ".join(str(x) for x in f0),
        }
    ]


def _trim_score_preroll(generated: Path, output_path: Path, preroll_s: float = SCORE_PREROLL_S) -> None:
    import soundfile as sf

    audio, sample_rate = sf.read(str(generated), always_2d=True)
    trim_samples = int(round(preroll_s * sample_rate))
    if audio.shape[0] <= trim_samples:
        raise EngineUnavailable("SoulX-Singer output is shorter than the score pre-roll")
    sf.write(str(output_path), audio[trim_samples:], sample_rate)


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

    def preprocess_reference(self, reference_voice: Path, work_dir: Path, language: str = "Mandarin", cancellation: Optional[CancellationToken] = None, progress=None) -> Path:
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
        cache_path = _cached_artifact(reference_voice, "reference-metadata", canonical_language, self.repo, self.device, ".json")
        if _cache_hit(cache_path, _valid_reference_metadata_cache):
            if progress: progress(0.22, "reference voice cache hit")
            return cache_path
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
        if progress: progress(0.12, "preprocessing reference voice")
        _run_checked(cmd, cancellation, self.repo, env, "SoulX reference preprocessing")
        if progress: progress(0.22, "reference voice prepared")
        metadata_path = work_dir / "metadata.json"
        if not metadata_path.exists():
            raise EngineUnavailable(f"preprocess did not produce expected metadata: {metadata_path}")
        return _best_effort_atomic_copy(metadata_path, cache_path)

    def render_score(self, project: Project, track: Track, output_path: Path, reference_voice: Optional[Path] = None, cancellation: Optional[CancellationToken] = None, progress=None) -> Path:
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
            if progress: progress(0.08, "waiting for SoulX-Singer VRAM slot")
            with self.vram.acquire("soulx-singer", estimated_gb=5.5):
                prompt_meta = self.preprocess_reference(reference, tmpdir / "prompt", _metadata_language_for_track(track), cancellation, progress)
                if progress: progress(0.28, "preparing SoulX-Singer inference")
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
                    "--pitch_shift",
                    "0",
                    "--control",
                    "melody",
                    "--fp16",
                ]
                if progress: progress(0.34, "running SoulX-Singer inference")
                _run_checked(cmd, cancellation, self.repo, env, "SoulX-Singer inference")
                if progress: progress(0.78, "collecting SoulX-Singer output")
            generated = save_dir / "generated.wav"
            if not generated.exists():
                raise EngineUnavailable(f"SoulX-Singer completed without output: {generated}")
            _trim_score_preroll(generated, output_path)
        return output_path

    def _extract_f0_with_preprocess(self, audio: Path, work_dir: Path, cancellation: Optional[CancellationToken] = None, progress=None) -> Path:
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
        cache_path = _cached_artifact(audio, "f0", "Mandarin", self.repo, self.device, ".npy")
        if _cache_hit(cache_path, _valid_f0_cache):
            return cache_path
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
        _run_checked(cmd, cancellation, self.repo, env, "SoulX F0 preprocessing")
        f0 = work_dir / "vocal_f0.npy"
        if not f0.exists():
            raise EngineUnavailable(f"F0 extraction did not produce {f0}")
        return _best_effort_atomic_copy(f0, cache_path)

    def convert_voice(self, source_audio: Path, reference_voice: Path, output_path: Path, cancellation: Optional[CancellationToken] = None, progress=None, pitch_shift: int = 0, auto_shift: bool = False) -> Path:
        self._require()
        model = self._model_path(svc=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="openace-svc-") as tmp:
            tmpdir = Path(tmp)
            if progress: progress(0.08, "waiting for SoulX-Singer-SVC VRAM slot")
            with self.vram.acquire("soulx-singer-svc", estimated_gb=5.5):
                if progress: progress(0.12, "extracting reference-voice F0")
                prompt_f0 = self._extract_f0_with_preprocess(reference_voice, tmpdir / "prompt", cancellation)
                if progress: progress(0.26, "extracting source-voice F0")
                target_f0 = self._extract_f0_with_preprocess(source_audio, tmpdir / "target", cancellation)
                if progress: progress(0.40, "preparing SoulX-Singer-SVC inference")
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
                    "--pitch_shift",
                    str(int(pitch_shift)),
                    "--fp16",
                ]
                if auto_shift and int(pitch_shift) == 0:
                    cmd.insert(cmd.index("--fp16"), "--auto_shift")
                if progress: progress(0.46, "running SoulX-Singer-SVC inference")
                _run_checked(cmd, cancellation, self.repo, env, "SoulX-Singer-SVC inference")
                if progress: progress(0.78, "collecting SoulX-Singer-SVC output")
            generated = save_dir / "generated.wav"
            if not generated.exists():
                raise EngineUnavailable(f"SoulX-Singer-SVC completed without output: {generated}")
            shutil.copyfile(generated, output_path)
        return output_path
