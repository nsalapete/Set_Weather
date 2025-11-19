"""Library Agent: retrieves tracks via the music library tool."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from anthropic.types import MessageParam

from set_weaver.agents.base import ClaudeAgentBase
from set_weaver.schemas.track_data import TrackData, TrackFilter, validate_track_list
from set_weaver.tools.music_library import query_music_library, render_tracks_for_tool, tool_definition
from set_weaver.utils import extract_json_from_text


LIBRARY_SYSTEM_PROMPT = (
    "You are the Library Agent. You only respond with JSON that matches the TrackData schema. "
    "Invoke the music library tool whenever the Strategist provides filters. "
    "Do not reason about music theory; you simply fetch matching tracks."
)


class LibraryAgent(ClaudeAgentBase):
    """Anthropic-powered agent responsible for data retrieval."""

    def __init__(self) -> None:
        super().__init__(system_prompt=LIBRARY_SYSTEM_PROMPT, max_tokens=1024)

    def fetch_tracks(self, filters: Dict[str, Any] | TrackFilter) -> List[TrackData]:
        filter_payload = filters if isinstance(filters, dict) else filters.model_dump()
        print(f"🗃️  Library Agent searching: BPM {filter_payload.get('bpm_min')}-{filter_payload.get('bpm_max')}, Genre: {filter_payload.get('genre')}")
        # Skip Claude agent loop and call Spotify directly to avoid JSON encoding issues
        matches = query_music_library(filter_payload)
        return matches

    @staticmethod
    def _handle_query(arguments: Dict[str, Any]) -> Dict[str, Any]:
        matches = query_music_library(arguments)
        return render_tracks_for_tool(matches)
