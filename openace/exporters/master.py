from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import tempfile
import zipfile
from typing import List, Tuple

import numpy as np

from openace.core.audio import export_video_with_lyrics, mix_tracks, read_audio, resample_linear, write_wav
from openace.core.crossfade import apply_automatic_crossfades
from openace.core.models import AudioClip, Project


def _resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else Path.cwd() / path



def _apply_clip_fades(data: np.ndarray, project: Project, clip: AudioClip, sample_rate: int) -> np.ndarray:
    """Apply linear clip edge fades in the exported source slice."""
    if not len(data):
        return data
    processed = np.array(data, dtype=np.float32, copy=True)
    half = len(processed) // 2
    fade_in_seconds = project.tick_duration_seconds(clip.start_ticks, max(0, clip.fade_in_ticks))
    if clip.duration_ticks is not None:
        end_ticks = clip.start_ticks + clip.duration_ticks
        fade_out_seconds = project.tick_duration_seconds(end_ticks - max(0, clip.fade_out_ticks), max(0, clip.fade_out_ticks))
    else:
        fade_out_seconds = project.tick_duration_seconds(clip.start_ticks, max(0, clip.fade_out_ticks))
    fade_in = min(half, int(round(fade_in_seconds * sample_rate)))
    fade_out = min(half, int(round(fade_out_seconds * sample_rate)))
    if fade_in > 1:
        processed[:fade_in] *= np.linspace(0.0, 1.0, fade_in, dtype=np.float32)[:, None]
    if fade_out > 1:
        processed[-fade_out:] *= np.linspace(1.0, 0.0, fade_out, dtype=np.float32)[:, None]
    return processed



LOUDNESS_TARGET_LUFS = -14.0
# Export slightly below the user-facing -1 dBTP ceiling so codec/quantization
# rounding cannot produce an exactly-at-ceiling master.
LOUDNESS_TRUE_PEAK_TARGET_DBTP = -1.1
LOUDNESS_LRA_TARGET = 11.0


def _ffmpeg_loudness_measurement(path: Path) -> dict[str, float]:
    """Measure integrated loudness/true peak through ffmpeg's EBU R128 loudnorm filter."""
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
        "-af", f"loudnorm=I={LOUDNESS_TARGET_LUFS}:TP={LOUDNESS_TRUE_PEAK_TARGET_DBTP}:LRA={LOUDNESS_LRA_TARGET}:print_format=json", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required for standards-compliant -14 LUFS/-1 dBTP master export") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg loudness measurement failed: {exc.stderr[-500:]}") from exc
    match = re.search(r'\{\s*"input_i"\s*:.*?\}', result.stderr, re.S)
    if not match:
        raise RuntimeError("ffmpeg loudness measurement did not emit machine-readable statistics")
    raw = json.loads(match.group(0))
    return {
        "input_i": float(raw["input_i"]),
        "input_tp": float(raw["input_tp"]),
        "input_lra": float(raw["input_lra"]),
        "input_thresh": float(raw["input_thresh"]),
        "target_offset": float(raw.get("target_offset", 0.0)),
    }


def _measurement_is_compliant(measurement: dict[str, float]) -> bool:
    return (
        abs(measurement["input_i"] - LOUDNESS_TARGET_LUFS) <= 0.3
        and measurement["input_tp"] < -1.0
    )


def _write_linear_master(input_path: Path, samples: np.ndarray, output_path: Path, sample_rate: int) -> dict[str, float]:
    """Apply transparent constant-gain loudness normalization when peak headroom permits."""
    measured = _ffmpeg_loudness_measurement(input_path)
    if not all(np.isfinite(value) for value in measured.values()):
        raise RuntimeError("cannot loudness-normalize a silent or invalid master")
    gain_db = LOUDNESS_TARGET_LUFS - measured["input_i"]
    if measured["input_tp"] + gain_db > LOUDNESS_TRUE_PEAK_TARGET_DBTP:
        gain_db = LOUDNESS_TRUE_PEAK_TARGET_DBTP - measured["input_tp"]
    write_wav(output_path, samples * (10.0 ** (gain_db / 20.0)), sample_rate, normalize=False)
    return _ffmpeg_loudness_measurement(output_path)


def _run_two_pass_loudnorm(input_path: Path, output_path: Path, sample_rate: int) -> dict[str, float]:
    measured = _ffmpeg_loudness_measurement(input_path)
    if not all(np.isfinite(value) for value in measured.values()):
        raise RuntimeError("cannot loudness-normalize a silent or invalid master")
    loudnorm = (
        f"loudnorm=I={LOUDNESS_TARGET_LUFS}:TP={LOUDNESS_TRUE_PEAK_TARGET_DBTP}:LRA={LOUDNESS_LRA_TARGET}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true"
    )
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(input_path),
        "-af", loudnorm, "-ar", str(sample_rate), "-c:a", "pcm_s24le", str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required for standards-compliant -14 LUFS/-1 dBTP master export") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg loudness normalization failed: {exc.stderr[-700:]}") from exc
    output = _ffmpeg_loudness_measurement(output_path)
    if not _measurement_is_compliant(output):
        raise RuntimeError(
            "ffmpeg loudness normalization validation failed: "
            f"{output['input_i']:.2f} LUFS, {output['input_tp']:.2f} dBTP"
        )
    return output


def write_standards_compliant_master(samples: np.ndarray, output_path: Path, sample_rate: int) -> Path:
    """Write a master whose loudness is validated with ffmpeg rather than approximation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not len(samples) or float(np.max(np.abs(samples))) < 1e-8:
        write_wav(output_path, samples, sample_rate, normalize=False)
        return output_path
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(prefix="openace-premaster-", suffix=".wav", dir=output_path.parent, delete=False) as handle:
            temporary_name = handle.name
        temporary = Path(temporary_name)
        write_wav(temporary, samples, sample_rate, normalize=False)
        linear_measurement = _write_linear_master(temporary, samples, output_path, sample_rate)
        if _measurement_is_compliant(linear_measurement):
            return output_path
        _run_two_pass_loudnorm(temporary, output_path, sample_rate)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    return output_path



def audible_tracks(project: Project):
    """Tracks audible in the current mixer state under standard solo/mute semantics."""
    soloed = any(track.solo for track in project.tracks)
    return [track for track in project.tracks if not track.mute and (not soloed or track.solo)]


def _track_audio_buffers(project: Project, track, sample_rate: int) -> List[Tuple[np.ndarray, int]]:
    """Decode one track's render/clips into timeline-positioned export buffers."""
    buffers: List[Tuple[np.ndarray, int]] = []
    clip_paths = {str(_resolve(clip.path)) for clip in track.clips}
    sources: List[Tuple[Path, AudioClip | None]] = []
    if track.render_path:
        render_path = _resolve(track.render_path)
        if str(render_path) not in clip_paths:
            sources.append((render_path, None))
    sources.extend((_resolve(clip.path), clip) for clip in track.clips)
    for path, clip in sources:
        if not path.exists():
            continue
        data, sr = read_audio(path)
        if sr != sample_rate:
            data = resample_linear(data, sr, sample_rate)
            sr = sample_rate
        if data.ndim == 1:
            data = data[:, None]
        start_ticks = getattr(clip, "start_ticks", 0) if clip is not None else 0
        source_offset_ticks = getattr(clip, "offset_ticks", 0) if clip is not None else 0
        duration_ticks = getattr(clip, "duration_ticks", None) if clip is not None else None
        source_offset_seconds = project.seconds_between_ticks(start_ticks - source_offset_ticks, start_ticks) if clip is not None else project.ticks_to_seconds(source_offset_ticks)
        source_start = int(round(source_offset_seconds * sample_rate))
        source_end = len(data)
        if duration_ticks is not None:
            duration_seconds = project.tick_duration_seconds(start_ticks, duration_ticks) if clip is not None else project.ticks_to_seconds(duration_ticks)
            source_end = min(source_end, source_start + int(round(duration_seconds * sample_rate)))
        data = data[max(0, source_start):max(0, source_end)]
        if not len(data):
            continue
        if clip is not None:
            data = _apply_clip_fades(data, project, clip, sample_rate)
            data = apply_automatic_crossfades(data, project, track, clip, sample_rate)
        timeline_offset = int(round(project.ticks_to_seconds(start_ticks) * sample_rate))
        if timeline_offset:
            padding = np.zeros((timeline_offset, data.shape[1]), dtype=data.dtype)
            data = np.concatenate([padding, data], axis=0)
        clip_gain = 10.0 ** ((getattr(clip, "gain_db", 0.0) if clip is not None else 0.0) / 20.0)
        buffers.append((data * track.volume * clip_gain, sr))
    return buffers

def export_master_wav(project: Project, output_path: Path, sample_rate: int = 48000) -> Path:
    buffers: List[Tuple[np.ndarray, int]] = []
    for track in audible_tracks(project):
        buffers.extend(_track_audio_buffers(project, track, sample_rate))
    mixed = mix_tracks(buffers, sample_rate=sample_rate)
    return write_standards_compliant_master(mixed, output_path, sample_rate)


def export_stems_zip(project: Project, output_path: Path, sample_rate: int = 48000) -> Path:
    """Export audible tracks as individual post-volume WAV stems plus a truthful manifest."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix="openace-stems-", dir=output_path.parent)
    stem_dir = Path(temporary.name)
    manifest = {"sample_rate": sample_rate, "format": "pcm_s24le wav", "processing": "track volume, clip gain, clip fades, automatic same-track crossfades; no per-stem loudness normalization", "tracks": [], "skipped": []}
    used_names: set[str] = set()
    for index, track in enumerate(audible_tracks(project), 1):
        buffers = _track_audio_buffers(project, track, sample_rate)
        mixed = mix_tracks(buffers, sample_rate=sample_rate)
        peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
        if not len(mixed) or peak < 1e-8:
            manifest["skipped"].append({"track_id": track.id, "track_name": track.name, "reason": "no audible decoded audio"})
            continue
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", track.name).strip("._") or f"track_{index}"
        name = f"{index:02d}_{base}.wav"
        while name in used_names:
            name = f"{index:02d}_{base}_{len(used_names)}.wav"
        used_names.add(name)
        path = stem_dir / name
        write_wav(path, mixed, sample_rate, normalize=False)
        rms = float(np.sqrt(np.mean(np.square(mixed)))) if mixed.size else 0.0
        manifest["tracks"].append({"track_id": track.id, "track_name": track.name, "type": track.type.value, "file": name, "peak": peak, "rms": rms, "volume": track.volume, "pan": track.pan, "solo": track.solo, "mute": track.mute})
    if not manifest["tracks"]:
        raise RuntimeError("no audible track audio available for stem export")
    manifest_path = stem_dir / "stems_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(manifest_path, "stems_manifest.json")
            for item in manifest["tracks"]:
                archive.write(stem_dir / item["file"], item["file"])
    finally:
        temporary.cleanup()
    return output_path


def _ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    h, rem = divmod(centiseconds, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


KARAOKE_THEMES = {
    "midnight": ("0x080C18", "0x191536", "0x05070D"),
    "ember": ("0x160806", "0x3B1512", "0x070404"),
    "forest": ("0x06130D", "0x123326", "0x030806"),
    "monochrome": ("0x080808", "0x202020", "0x030303"),
}


def _hex_color(value: object, default: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.lower()
    return default


def _ass_color(hex_color: str) -> str:
    red = int(hex_color[1:3], 16)
    green = int(hex_color[3:5], 16)
    blue = int(hex_color[5:7], 16)
    return f"&H00{blue:02X}{green:02X}{red:02X}"


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def karaoke_style_settings(project: Project) -> dict[str, object]:
    raw = (project.metadata or {}).get("karaoke_style") or {}
    if not isinstance(raw, dict):
        raw = {}
    theme = str(raw.get("background_theme") or "midnight")
    return {
        "font_size": _bounded_int(raw.get("font_size", 66), 66, 36, 96),
        "lane_spacing": _bounded_int(raw.get("lane_spacing", 76), 76, 52, 112),
        "sung_color": _hex_color(raw.get("sung_color"), "#ffb000"),
        "unsung_color": _hex_color(raw.get("unsung_color"), "#d9d9d9"),
        "background_theme": theme if theme in KARAOKE_THEMES else "midnight",
        "background_motion": bool(raw.get("background_motion", True)),
        "show_title": bool(raw.get("show_title", True)),
        "show_brand": bool(raw.get("show_brand", True)),
    }


def export_lyrics_video(project: Project, master_wav: Path, output_path: Path) -> Path:
    """Render a subtitle-burned karaoke lyric video with timed lyric sweeps."""
    import subprocess

    from openace.core.audio import read_audio

    audio, sr = read_audio(master_wav)
    duration = len(audio) / sr

    phrases = []
    for track in project.vocal_tracks():
        current = []
        previous_end = None
        for note in track.sorted_notes():
            if not note.lyric.strip():
                continue
            note_start = project.ticks_to_seconds(note.start_ticks)
            note_end = project.ticks_to_seconds(note.end_ticks)
            if current and previous_end is not None and note_start - previous_end <= 0.02:
                current.append((note_start, note_end, note.lyric.strip()))
            else:
                if current:
                    phrases.append((track.id, current))
                current = [(note_start, note_end, note.lyric.strip())]
            previous_end = note_end
        if current:
            phrases.append((track.id, current))
    phrases.sort(key=lambda item: item[1][0][0])
    lane_ends: list[float] = []
    laned_phrases = []
    for track_id, phrase in phrases:
        phrase_start = phrase[0][0]
        phrase_end = phrase[-1][1]
        lane = next((index for index, end in enumerate(lane_ends) if end <= phrase_start + 0.001), len(lane_ends))
        if lane == len(lane_ends):
            lane_ends.append(phrase_end)
        else:
            lane_ends[lane] = phrase_end
        laned_phrases.append((lane, track_id, phrase))
    lane_count = max(1, max((lane for lane, _track_id, _phrase in laned_phrases), default=0) + 1)
    style = karaoke_style_settings(project)

    ass = output_path.with_suffix(".ass")
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Title,Noto Sans CJK SC,{max(20, int(style['font_size'] * 0.46))},&H00E8EFFF,&H00E8EFFF,&HAA07101E,&H66000000,-1,0,0,0,100,100,1,0,1,2,0,7,72,72,44,1",
        f"Style: Brand,Noto Sans CJK SC,{max(16, int(style['font_size'] * 0.34))},&H00908EC8,&H00908EC8,&HAA07101E,&H66000000,0,0,0,0,100,100,1.5,0,1,1.5,0,9,72,72,42,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lyric_style_names = []
    for lane in range(lane_count):
        style_name = "Lyrics" if lane == 0 else f"LyricsLane{lane}"
        lyric_style_names.append(style_name)
        font_size = max(30, int(style['font_size']) - lane * 5)
        margin_v = 96 + lane * int(style['lane_spacing'])
        lines.insert(8 + lane, f"Style: {style_name},Noto Sans CJK SC,{font_size},{_ass_color(str(style['sung_color']))},{_ass_color(str(style['unsung_color']))},&HCC07101E,&H66000000,-1,0,0,0,100,100,1.2,0,1,4,1,2,100,100,{margin_v},1")
    video_end = _ass_timestamp(duration)
    if style["show_title"]:
        lines.append(f"Dialogue: 0,0:00:00.00,{video_end},Title,,0,0,0,,{_ass_escape(project.title)}")
    if style["show_brand"]:
        lines.append(f"Dialogue: 0,0:00:00.00,{video_end},Brand,,0,0,0,,OPENACE")
    for lane, _track_id, phrase in laned_phrases:
        phrase_start = phrase[0][0]
        phrase_end = phrase[-1][1]
        chunks = ["{\\fad(160,140)}"]
        for note_start, note_end, lyric in phrase:
            duration_cs = max(1, int(round((note_end - note_start) * 100)))
            chunks.append(f"{{\\kf{duration_cs}}}{_ass_escape(lyric)}")
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(phrase_start)},{_ass_timestamp(phrase_end)},{lyric_style_names[lane]},,0,0,0,,{''.join(chunks)}"
        )
    ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    filter_path = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c0, c1, c2 = KARAOKE_THEMES[str(style["background_theme"])]
    gradient = (
        f"gradients=s=1920x1080:r=30:c0={c0}:c1={c1}:c2={c2}:"
        f"nb_colors=3:x0=0:y0=0:x1=1920:y1=1080:speed={0.025 if style['background_motion'] else 0.00001}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", gradient,
        "-i", str(master_wav),
        "-t", f"{duration:.3f}",
        "-vf", f"subtitles='{filter_path}'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
        "-metadata", f"title={project.title}",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError("ffmpeg MP4 export failed; install ffmpeg with libx264/libass") from exc
    return output_path
