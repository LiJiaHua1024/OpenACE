from openace.core.models import Note, Project, Track
from openace.core.render_fingerprint import canonical_json, fnv1a64, vocal_render_input_hash


def test_render_fingerprint_stable_for_ids_and_sensitive_to_musical_input():
    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    note = track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    first = vocal_render_input_hash(project, track)
    note.id = "note_completely_different"
    assert vocal_render_input_hash(project, track) == first
    note.pitch = 61
    assert vocal_render_input_hash(project, track) != first


def test_render_fingerprint_sensitive_to_tempo_automation_breath_and_voice():
    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60))
    base = vocal_render_input_hash(project, track)
    project.bpm = 121
    assert vocal_render_input_hash(project, track) != base
    project.bpm = 120
    track.automation.dynamic = []
    assert vocal_render_input_hash(project, track) == base
    track.reference_voice_path = "/tmp/reference.wav"
    assert vocal_render_input_hash(project, track) != base


def test_canonical_fingerprint_vector_is_stable():
    assert canonical_json({"b": 1.0, "a": ["x", 0.5, None]}) == '{"a":["x",0.5,null],"b":1}'
    assert fnv1a64('{"a":1}') == "9c3e82dd6fcae8b1"
