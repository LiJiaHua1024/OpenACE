from __future__ import annotations

import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class Breath(BaseModel):
    id: str = Field(default_factory=lambda: new_id("br"))
    start_ticks: int
    duration_ticks: int = 120


class AudioClip(BaseModel):
    id: str = Field(default_factory=lambda: new_id("clip"))
    path: str
    start_ticks: int = 0
    duration_ticks: Optional[int] = None
    offset_ticks: int = 0
    gain_db: float = 0.0
    label: str = ""


class Track(BaseModel):
    id: str = Field(default_factory=lambda: new_id("track"))
    name: str
    type: TrackType = TrackType.VOCAL
    color: str = "#7c5cff"
    voice_id: str = "zero-shot-reference"
    reference_voice_path: Optional[str] = None
    language: str = "zh"
    notes: List[Note] = Field(default_factory=list)
    clips: List[AudioClip] = Field(default_factory=list)
    automation: VocalAutomation = Field(default_factory=VocalAutomation)
    breaths: List[Breath] = Field(default_factory=list)
    mute: bool = False
    solo: bool = False
    volume: float = 0.8
    pan: float = 0.0
    render_path: Optional[str] = None
    render_revision: int = 0

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
    numerator: int = 4
    denominator: int = 4


class TempoPoint(BaseModel):
    ticks: int = 0
    bpm: float = 120.0


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

    def ticks_to_seconds(self, ticks: float) -> float:
        # The current project model supports a tempo map for export but intentionally
        # uses the project base tempo for editing until multiple tempo automation lands.
        return self.ticks_to_beats(ticks) * 60.0 / self.bpm

    def seconds_to_ticks(self, seconds: float) -> int:
        return int(round(seconds * self.bpm / 60.0 * self.ppq))

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


def project_to_yaml(project: Project) -> str:
    return yaml.safe_dump(project.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
