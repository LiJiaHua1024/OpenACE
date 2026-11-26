from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np

from openace.core.audio import export_video_with_lyrics, mix_tracks, read_audio, resample_linear, write_wav
from openace.core.models import AudioClip, Project


def _resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else Path.cwd() / path


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
            source_start = int(round(project.ticks_to_seconds(source_offset_ticks) * sample_rate))
            source_end = len(data)
            if duration_ticks is not None:
                source_end = min(source_end, source_start + int(round(project.ticks_to_seconds(duration_ticks) * sample_rate)))
            data = data[max(0, source_start):max(0, source_end)]
            if not len(data):
                continue
            timeline_offset = int(round(project.ticks_to_seconds(start_ticks) * sample_rate))
            if timeline_offset:
                padding = np.zeros((timeline_offset, data.shape[1]), dtype=data.dtype)
                data = np.concatenate([padding, data], axis=0)
            buffers.append((data * track.volume, sr))
    mixed = mix_tracks(buffers, sample_rate=sample_rate)
    write_wav(output_path, mixed, sample_rate, normalize=True)
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


def export_lyrics_video(project: Project, master_wav: Path, output_path: Path) -> Path:
    """Render a real subtitle-burned lyric video rather than displaying raw LRC tags."""
    import subprocess

    from openace.core.audio import read_audio

    events = []
    for track in project.vocal_tracks():
        for note in track.sorted_notes():
            if not note.lyric.strip():
                continue
            start = project.ticks_to_seconds(note.start_ticks)
            end = project.ticks_to_seconds(note.end_ticks)
            events.append((start, end, note.lyric.strip()))
    events.sort()
    ass = output_path.with_suffix(".ass")
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Lyrics,Noto Sans CJK SC,62,&H00FFFFFF,&H000000FF,&HAA111111,&H66000000,-1,0,0,0,100,100,0,0,1,3,0,2,90,90,92,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for start, end, lyric in events:
        lines.append(f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Lyrics,,0,0,0,,{_ass_escape(lyric)}")
    ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    audio, sr = read_audio(master_wav)
    duration = len(audio) / sr
    filter_path = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=0x111118:s=1920x1080",
        "-i", str(master_wav),
        "-t", f"{duration:.3f}",
        "-vf", f"subtitles='{filter_path}'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError("ffmpeg MP4 export failed; install ffmpeg with libx264/libass") from exc
    return output_path
