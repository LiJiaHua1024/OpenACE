from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import tempfile
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


def export_master_wav(project: Project, output_path: Path, sample_rate: int = 48000) -> Path:
    buffers: List[Tuple[np.ndarray, int]] = []
    for track in project.tracks:
        if track.mute:
            continue
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
    mixed = mix_tracks(buffers, sample_rate=sample_rate)
    return write_standards_compliant_master(mixed, output_path, sample_rate)


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

    ass = output_path.with_suffix(".ass")
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Lyrics,Noto Sans CJK SC,66,&H0000BFFF,&H00D9D9D9,&HCC07101E,&H66000000,-1,0,0,0,100,100,1.2,0,1,4,1,2,100,100,96,1",
        "Style: Title,Noto Sans CJK SC,30,&H00E8EFFF,&H00E8EFFF,&HAA07101E,&H66000000,-1,0,0,0,100,100,1,0,1,2,0,7,72,72,44,1",
        "Style: Brand,Noto Sans CJK SC,22,&H00908EC8,&H00908EC8,&HAA07101E,&H66000000,0,0,0,0,100,100,1.5,0,1,1.5,0,9,72,72,42,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    video_end = _ass_timestamp(duration)
    lines.append(f"Dialogue: 0,0:00:00.00,{video_end},Title,,0,0,0,,{_ass_escape(project.title)}")
    lines.append(f"Dialogue: 0,0:00:00.00,{video_end},Brand,,0,0,0,,OPENACE")
    for _track_id, phrase in phrases:
        phrase_start = phrase[0][0]
        phrase_end = phrase[-1][1]
        chunks = ["{\\fad(160,140)}"]
        for note_start, note_end, lyric in phrase:
            duration_cs = max(1, int(round((note_end - note_start) * 100)))
            chunks.append(f"{{\\kf{duration_cs}}}{_ass_escape(lyric)}")
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(phrase_start)},{_ass_timestamp(phrase_end)},Lyrics,,0,0,0,,{''.join(chunks)}"
        )
    ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    filter_path = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gradient = (
        "gradients=s=1920x1080:r=30:c0=0x080C18:c1=0x191536:c2=0x05070D:"
        "nb_colors=3:x0=0:y0=0:x1=1920:y1=1080:speed=0.00001"
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
