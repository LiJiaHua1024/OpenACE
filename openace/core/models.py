from __future__ import annotations

import math
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

PPQ = 480
MIN_PITCH = 41  # F2, lower guard for malformed MIDI input only
MAX_PITCH = 84  # C6, upper guard for malformed MIDI input only


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class TrackType(str, Enum):
    VOCAL = "vocal"
    ACCOMPANIMENT = "accompaniment"
    AUDIO = "audio"


class RenderMode(str, Enum):
    SVS_SCORE = "svs_score"
    SVS_MELODY = "svs_melody"
    SVC = "svc"
    SEPARATE = "separate"
    VOCAL2BGM = "vocal2bgm"
    REPAINT = "repaint"


class Phoneme(BaseModel):
    symbol: str
    start_ms: float = 0.0
    duration_ms: float = 0.0
    is_vowel: bool = False
    locked: bool = False


class PitchPoint(BaseModel):
    offset_ms: float
    cents: float


class Vibrato(BaseModel):
    start_ratio: float = 0.55
    depth_cents: float = 35.0
    frequency_hz: float = 5.4
    phase: float = 0.0


class Note(BaseModel):
    id: str = Field(default_factory=lambda: new_id("note"))
    start_ticks: int
    duration_ticks: int
    pitch: int
    lyric: str = ""
    velocity: int = 90
    phonemes: List[Phoneme] = Field(default_factory=list)
    pitch_curve: List[PitchPoint] = Field(default_factory=list)
    pitch_snap_first: bool = True
    vibrato: Optional[Vibrato] = None
    techniques: List[str] = Field(default_factory=list)

    @field_validator("duration_ticks")
    @classmethod
    def positive_duration(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("note duration must be positive")
        return value

    @field_validator("pitch")
    @classmethod
    def pitch_not_clamped(cls, value: int) -> int:
        if not 0 <= value <= 127:
            raise ValueError("MIDI pitch must be in [0, 127]")
        return value

    @property
    def end_ticks(self) -> int:
        return self.start_ticks + self.duration_ticks


class EnvelopePoint(BaseModel):
    ticks: int
    value: float
    curve: str = "linear"


class VocalAutomation(BaseModel):
    """ACE-style continuous performance automation.

    Values are normalized except pitch deviation, which is cents.
    Empty lanes mean AI/auto mode rather than a silently invented default.
    """

    pitch_cents: List[EnvelopePoint] = Field(default_factory=list)
    dynamic: List[EnvelopePoint] = Field(default_factory=list)
    air: List[EnvelopePoint] = Field(default_factory=list)
    falsetto: List[EnvelopePoint] = Field(default_factory=list)
    tension: List[EnvelopePoint] = Field(default_factory=list)
    energy: List[EnvelopePoint] = Field(default_factory=list)
    volume: List[EnvelopePoint] = Field(default_factory=list)
    pan: List[EnvelopePoint] = Field(default_factory=list)


class Breath(BaseModel):
    id: str = Field(default_factory=lambda: new_id("br"))
    start_ticks: int
    duration_ticks: int = 120
    intensity: float = Field(default=1.0, ge=0.0, le=2.0)
    timbre: Literal["soft", "natural", "strong"] = "natural"


class TimedLyric(BaseModel):
    text: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class AudioClip(BaseModel):
    id: str = Field(default_factory=lambda: new_id("clip"))
    path: str
    start_ticks: int = 0
    duration_ticks: Optional[int] = None
    offset_ticks: int = 0
    fade_in_ticks: int = 0
    fade_out_ticks: int = 0
    gain_db: float = 0.0
    label: str = ""
    transcribed_lyrics: List[TimedLyric] = Field(default_factory=list)
    created_by_job_id: Optional[str] = None
    updated_by_job_id: Optional[str] = None


class Track(BaseModel):
    id: str = Field(default_factory=lambda: new_id("track"))
    name: str
    type: TrackType = TrackType.VOCAL
    color: str = "#7c5cff"
    voice_id: str = "zero-shot-reference"
    reference_voice_path: Optional[str] = None
    openutau_singer: str = ""
    openutau_phonemizer: str = ""
    language: str = "zh"
    notes: List[Note] = Field(default_factory=list)
    clips: List[AudioClip] = Field(default_factory=list)
    automation: VocalAutomation = Field(default_factory=VocalAutomation)
    breaths: List[Breath] = Field(default_factory=list)
    mute: bool = False
    solo: bool = False
    volume: float = 0.8
    pan: float = 0.0
    midi_channel: Optional[int] = Field(default=None, ge=0, le=15)
    midi_program: Optional[int] = Field(default=None, ge=0, le=127)
    created_by_job_id: Optional[str] = None
    render_path: Optional[str] = None
    render_revision: int = 0
    render_fingerprint: Optional[str] = None

    def sorted_notes(self) -> List[Note]:
        return sorted(self.notes, key=lambda n: (n.start_ticks, n.pitch))

    def add_note(self, note: Note) -> Note:
        self.notes.append(note)
        self.notes.sort(key=lambda n: (n.start_ticks, n.pitch))
        return note

    def delete_note(self, note_id: str) -> bool:
        before = len(self.notes)
        self.notes = [n for n in self.notes if n.id != note_id]
        return len(self.notes) != before

    def note(self, note_id: str) -> Note:
        for note in self.notes:
            if note.id == note_id:
                return note
        raise KeyError(f"note not found: {note_id}")


class TimeSignature(BaseModel):
    numerator: int = Field(default=4, ge=1, le=32)
    denominator: int = Field(default=4, ge=1, le=32)

    @field_validator("denominator")
    @classmethod
    def denominator_is_power_of_two(cls, value: int) -> int:
        if value & (value - 1):
            raise ValueError("time signature denominator must be a power of two")
        return value


class TempoPoint(BaseModel):
    ticks: int = Field(default=0, ge=0)
    bpm: float = Field(default=120.0, gt=0)
    # `linear` means the tempo ramps into this point across the preceding segment.
    curve: str = "step"

    @field_validator("curve")
    @classmethod
    def supported_curve(cls, value: str) -> str:
        if value not in {"step", "linear"}:
            raise ValueError("tempo point curve must be 'step' or 'linear'")
        return value


class Project(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: new_id("project"))
    schema_version: int = 1
    title: str = "Untitled OpenACE Project"
    ppq: int = PPQ
    bpm: float = 120.0
    tempo_map: List[TempoPoint] = Field(default_factory=lambda: [TempoPoint()])
    time_signature: TimeSignature = Field(default_factory=TimeSignature)
    tracks: List[Track] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_track(self, track: Track) -> Track:
        self.tracks.append(track)
        self.touch()
        return track

    def track(self, track_id: str) -> Track:
        for track in self.tracks:
            if track.id == track_id:
                return track
        raise KeyError(f"track not found: {track_id}")

    def vocal_tracks(self) -> List[Track]:
        return [track for track in self.tracks if track.type == TrackType.VOCAL]

    def duration_ticks(self) -> int:
        ends = [note.end_ticks for track in self.tracks for note in track.notes]
        for track in self.tracks:
            for clip in track.clips:
                if clip.duration_ticks is not None:
                    ends.append(clip.start_ticks + clip.duration_ticks)
        return max(ends, default=self.ppq * 16)

    def beats_to_ticks(self, beats: float) -> int:
        return int(round(beats * self.ppq))

    def ticks_to_beats(self, ticks: float) -> float:
        return ticks / self.ppq

    def normalized_tempo_map(self) -> List[TempoPoint]:
        """Return sorted tempo points with a deterministic anchor at tick zero."""
        points = sorted((point for point in (self.tempo_map or []) if point.ticks > 0), key=lambda point: point.ticks)
        deduped: List[TempoPoint] = []
        for point in points:
            bpm = max(1.0, float(point.bpm))
            if deduped and deduped[-1].ticks == point.ticks:
                deduped[-1] = TempoPoint(ticks=int(point.ticks), bpm=bpm, curve=point.curve)
            else:
                deduped.append(TempoPoint(ticks=int(point.ticks), bpm=bpm, curve=point.curve))
        # Project.bpm is the editing surface's canonical tick-zero tempo. Later
        # tempo points automate after that anchor; this preserves existing projects
        # whose default tempo map was not updated when the BPM transport changed.
        return [TempoPoint(ticks=0, bpm=max(1.0, float(self.bpm)))] + deduped

    def _segment_seconds(self, start_ticks: float, end_ticks: float, start_bpm: float, end_bpm: float, linear: bool) -> float:
        span = end_ticks - start_ticks
        if span == 0:
            return 0.0
        if not linear or abs(end_bpm - start_bpm) < 1e-9:
            return span / self.ppq * 60.0 / start_bpm
        # Integrate 1/bpm while BPM itself interpolates linearly across ticks.
        return (60.0 / self.ppq) * span / (end_bpm - start_bpm) * math.log(end_bpm / start_bpm)

    def _invert_linear_segment(self, seconds: float, start_ticks: float, end_ticks: float, start_bpm: float, end_bpm: float) -> float:
        span = end_ticks - start_ticks
        if abs(end_bpm - start_bpm) < 1e-9:
            return start_ticks + seconds * start_bpm / 60.0 * self.ppq
        # Invert the exact logarithmic integral of reciprocal linear BPM.
        bpm = start_bpm * math.exp(seconds * self.ppq / 60.0 * (end_bpm - start_bpm) / span)
        return start_ticks + span * (bpm - start_bpm) / (end_bpm - start_bpm)

    def bpm_at(self, ticks: float) -> float:
        """Return active tempo, linearly interpolating across ramp segments."""
        points = self.normalized_tempo_map()
        if ticks <= points[0].ticks:
            return points[0].bpm
        for index, point in enumerate(points[1:], 1):
            if ticks <= point.ticks:
                previous = points[index - 1]
                if ticks < point.ticks:
                    if point.curve == "linear" and point.ticks > previous.ticks:
                        ratio = (ticks - previous.ticks) / (point.ticks - previous.ticks)
                        return float(previous.bpm + (point.bpm - previous.bpm) * max(0.0, min(1.0, ratio)))
                    return float(previous.bpm)
                return float(point.bpm)
        return float(points[-1].bpm)

    def ticks_to_seconds(self, ticks: float) -> float:
        """Convert absolute musical ticks to seconds through step/linear tempo segments."""
        points = self.normalized_tempo_map()
        first = points[0]
        if ticks <= first.ticks:
            return (ticks - first.ticks) / self.ppq * 60.0 / first.bpm
        elapsed = 0.0
        previous = first
        for point in points[1:]:
            if ticks <= point.ticks:
                if point.curve == "linear":
                    ratio = (ticks - previous.ticks) / max(1e-9, point.ticks - previous.ticks)
                    end_bpm = previous.bpm + (point.bpm - previous.bpm) * ratio
                    return elapsed + self._segment_seconds(previous.ticks, ticks, previous.bpm, end_bpm, True)
                return elapsed + (ticks - previous.ticks) / self.ppq * 60.0 / previous.bpm
            elapsed += self._segment_seconds(previous.ticks, point.ticks, previous.bpm, point.bpm, point.curve == "linear")
            previous = point
        return elapsed + (ticks - previous.ticks) / self.ppq * 60.0 / previous.bpm

    def seconds_to_ticks_float(self, seconds: float) -> float:
        """Invert absolute seconds through step/linear tempo segments without rounding."""
        points = self.normalized_tempo_map()
        first = points[0]
        if seconds <= 0.0:
            return first.ticks + seconds * first.bpm / 60.0 * self.ppq
        elapsed = 0.0
        previous = first
        for point in points[1:]:
            segment_seconds = self._segment_seconds(previous.ticks, point.ticks, previous.bpm, point.bpm, point.curve == "linear")
            if seconds <= elapsed + segment_seconds:
                if point.curve == "linear":
                    return float(self._invert_linear_segment(seconds - elapsed, previous.ticks, point.ticks, previous.bpm, point.bpm))
                return previous.ticks + (seconds - elapsed) * previous.bpm / 60.0 * self.ppq
            elapsed += segment_seconds
            previous = point
        return previous.ticks + (seconds - elapsed) * previous.bpm / 60.0 * self.ppq

    def seconds_to_ticks(self, seconds: float) -> int:
        return int(round(self.seconds_to_ticks_float(seconds)))

    def seconds_between_ticks(self, start_ticks: float, end_ticks: float) -> float:
        return self.ticks_to_seconds(end_ticks) - self.ticks_to_seconds(start_ticks)

    def tick_duration_seconds(self, start_ticks: float, duration_ticks: float) -> float:
        return self.seconds_between_ticks(start_ticks, start_ticks + duration_ticks)

    def seconds_to_ticks_from(self, start_ticks: float, seconds: float) -> int:
        """Convert a duration in seconds starting at a timeline position into ticks."""
        start_seconds = self.ticks_to_seconds(start_ticks)
        return int(round(self.seconds_to_ticks_float(start_seconds + seconds) - start_ticks))

    def dump_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def load_json(cls, text: str) -> "Project":
        return cls.model_validate_json(text)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.dump_json() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Project":
        return cls.load_json(path.read_text(encoding="utf-8"))


class RenderJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class RenderJob(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    project_id: str
    track_id: Optional[str] = None
    mode: RenderMode
    status: RenderJobStatus = RenderJobStatus.QUEUED
    progress: float = 0.0
    message: str = "queued"
    output_path: Optional[str] = None
    diagnostic_path: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    finished_at: Optional[float] = None
    error: Optional[str] = None
    engine: Optional[str] = None
    fixture: bool = False
    source_audio: Optional[str] = None
    reference_voice: Optional[str] = None
    caption: str = ""
    start_s: Optional[float] = None
    end_s: Optional[float] = None
    clip_id: Optional[str] = None
    source_start_s: Optional[float] = None
    source_end_s: Optional[float] = None


def project_to_yaml(project: Project) -> str:
    return yaml.safe_dump(project.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
