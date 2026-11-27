import pytest

from openace.core.editing import validate_project
from openace.core.models import Note, Project, Track


def project_with_notes(first_duration=480, second_start=480):
    project = Project(title="overlap")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=first_duration, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=second_start, duration_ticks=480, pitch=62, lyric="好"))
    return project


def test_validate_project_rejects_overlapping_vocal_notes():
    with pytest.raises(ValueError, match="may not overlap"):
        validate_project(project_with_notes(first_duration=480, second_start=240))


def test_validate_project_allows_exactly_adjacent_vocal_notes():
    validate_project(project_with_notes(first_duration=480, second_start=480))
