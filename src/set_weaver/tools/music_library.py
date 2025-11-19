"""Simulated music library tool for Claude tool-use demos."""
from __future__ import annotations

from typing import Any, Iterable, List

from set_weaver.schemas.track_data import TrackData, TrackFilter, asdict_sequence


MUSIC_LIBRARY: List[TrackData] = [
    TrackData(
        id="TRK_00001",
        artist="Peggy Gou",
        title="Starry Night",
        genre="Deep House",
        bpm=122,
        key_camelot="2A",
        energy_level=7,
        duration_sec=393,
    ),
    TrackData(
        id="TRK_00002",
        artist="Ben Böhmer",
        title="Beyond Beliefs",
        genre="Deep House",
        bpm=120,
        key_camelot="10A",
        energy_level=6,
        duration_sec=428,
    ),
    TrackData(
        id="TRK_00003",
        artist="Charlotte de Witte",
        title="Selected",
        genre="Techno",
        bpm=128,
        key_camelot="7B",
        energy_level=9,
        duration_sec=360,
    ),
    TrackData(
        id="TRK_00004",
        artist="Green Velvet",
        title="La La Land",
        genre="Tech House",
        bpm=125,
        key_camelot="10B",
        energy_level=8,
        duration_sec=347,
    ),
    TrackData(
        id="TRK_00005",
        artist="Honey Dijon",
        title="Not About You",
        genre="House",
        bpm=123,
        key_camelot="3A",
        energy_level=8,
        duration_sec=377,
    ),
    TrackData(
        id="TRK_00006",
        artist="ARTBAT",
        title="Horizon",
        genre="Melodic Techno",
        bpm=124,
        key_camelot="9A",
        energy_level=8,
        duration_sec=410,
    ),
    TrackData(
        id="TRK_00007",
        artist="ANNA",
        title="Hidden Beauties",
        genre="Techno",
        bpm=127,
        key_camelot="11A",
        energy_level=9,
        duration_sec=478,
    ),
    TrackData(
        id="TRK_00008",
        artist="Disclosure",
        title="Latch",
        genre="Deep House",
        bpm=122,
        key_camelot="6B",
        energy_level=7,
        duration_sec=260,
    ),
]


def query_music_library(filters: dict | TrackFilter) -> List[TrackData]:
    """Return tracks that match the requested filter envelope."""

    filter_model = filters if isinstance(filters, TrackFilter) else TrackFilter.model_validate(filters)
    matches: List[TrackData] = []
    for track in MUSIC_LIBRARY:
        if not (filter_model.bpm_min <= track.bpm <= filter_model.bpm_max):
            continue
        if track.genre.lower() != filter_model.genre.lower():
            continue
        if filter_model.key_camelot and track.key_camelot != filter_model.key_camelot:
            continue
        if filter_model.energy_min and track.energy_level < filter_model.energy_min:
            continue
        if filter_model.energy_max and track.energy_level > filter_model.energy_max:
            continue
        matches.append(track)
    matches.sort(key=lambda t: (t.bpm, t.energy_level))
    return matches


def tool_definition() -> dict[str, Any]:
    """Anthropic tool definition describing the query API."""

    return {
        "name": "query_music_library",
        "description": "Searches the music database based on criteria. Filters must include BPM range, Key, and Genre for best results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bpm_min": {"type": "integer"},
                "bpm_max": {"type": "integer"},
                "genre": {"type": "string"},
                "key_camelot": {"type": "string"},
                "energy_min": {"type": "integer"},
                "energy_max": {"type": "integer"},
            },
            "required": ["bpm_min", "bpm_max", "genre"],
        },
    }


def render_tracks_for_tool(tracks: Iterable[TrackData]) -> dict[str, Any]:
    """Convert matches into a dict that Claude can consume via tool results."""

    return {"tracks": asdict_sequence(list(tracks))}
