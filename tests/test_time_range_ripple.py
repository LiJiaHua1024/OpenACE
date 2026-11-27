from openace.core.editing import ripple_delete_time_range
from openace.core.models import AudioClip, Breath, EnvelopePoint, Note, Project, Track, TempoPoint


def test_time_range_ripple_delete_splits_boundary_media_and_shifts_downstream():
    project = Project(bpm=120)
    track = Track(name="Lead")
    track.add_note(Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=1440, duration_ticks=480, pitch=62, lyric="好"))
    track.breaths.append(Breath(start_ticks=600, duration_ticks=120))
    track.automation.dynamic = [EnvelopePoint(ticks=0, value=0.2), EnvelopePoint(ticks=720, value=0.8), EnvelopePoint(ticks=1440, value=1.0)]
    track.clips.append(AudioClip(path="a.wav", start_ticks=0, duration_ticks=1920, offset_ticks=0))
    project.add_track(track)
    other = Track(name="BGM", type="audio")
    other.clips.append(AudioClip(path="b.wav", start_ticks=1920, duration_ticks=480, offset_ticks=0))
    project.add_track(other)
    project.tempo_map = [TempoPoint(ticks=0, bpm=120), TempoPoint(ticks=720, bpm=90), TempoPoint(ticks=1920, bpm=140)]

    result = ripple_delete_time_range(project, 480, 960)

    assert result["ripple_ticks"] == 480
    lead = project.tracks[0]
    # Boundary note split at 480/960, deleted middle, downstream note shifts once.
    assert [(n.start_ticks, n.duration_ticks, n.lyric) for n in lead.notes] == [
        (0, 480, "你"),
        (960, 480, "好"),
    ]
    # Crossing clip becomes left 0-480 plus right tail now at 480 with correct source offset.
    assert [(c.start_ticks, c.duration_ticks, c.offset_ticks) for c in lead.clips] == [
        (0, 480, 0),
        (480, 960, 960),
    ]
    assert lead.breaths == []
    assert [(p.ticks, p.value) for p in lead.automation.dynamic] == [(0, 0.2), (480, 0.8666666666666667), (960, 1.0)]
    assert [(p.ticks, p.bpm) for p in project.tempo_map] == [(0, 120), (1440, 140)]
    assert [(c.start_ticks, c.duration_ticks) for c in project.tracks[1].clips] == [(1440, 480)]


def test_time_range_ripple_delete_rejects_invalid_range():
    project = Project(bpm=120)
    project.add_track(Track(name="Lead"))
    try:
        ripple_delete_time_range(project, 960, 480)
    except ValueError as exc:
        assert "start_ticks" in str(exc)
    else:
        raise AssertionError("invalid range accepted")
