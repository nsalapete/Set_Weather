"""Music library tool that can hit Spotify or fall back to static data."""
from __future__ import annotations

from typing import Any, Iterable, List

from set_weaver.schemas.track_data import TrackData, TrackFilter, asdict_sequence
from set_weaver.tools.spotify_library import query_spotify_library, spotify_enabled


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
    if not spotify_enabled():
        msg = "Spotify credentials are required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to use the library tool."
        raise RuntimeError(msg)
    try:
        spotify_results = query_spotify_library(filter_model)
    except Exception as exc:  # pragma: no cover - logging only
        raise RuntimeError(f"Spotify query failed: {exc}") from exc
    if not spotify_results:
        raise RuntimeError("Spotify did not return any tracks for the requested filters")
    return spotify_results


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
