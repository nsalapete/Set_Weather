"""Strategist Agent: orchestrates the full set construction."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from anthropic.types import MessageParam

from set_weaver.agents.base import ClaudeAgentBase
from set_weaver.agents.library_agent import LibraryAgent
from set_weaver.agents.transition_agent import TransitionAgent
from set_weaver.schemas.track_data import SetlistReport, TrackData, TransitionProposal, validate_setlist_report
from set_weaver.utils import extract_json_from_text


STRATEGIST_SYSTEM_PROMPT = (
    "You are the Strategist. Translate the DJ's request into a structured set plan. "
    "You must manage total duration, energy flow, BPM envelopes, and harmonic compatibility. "
    "When you need tracks, call the library_search tool with precise filters. "
    "When sequencing, call transition_analysis with the two tracks so the Transition Agent can respond. "
    "Respond ONLY with a JSON object containing: set_title (string), duration_minutes (integer), and setlist (array). "
    "Each setlist entry must have: track_id, track_artist, track_title, start_time (MM:SS format), and mix_out_instructions (the full transition proposal object). "
    "Do NOT include extra fields like track_number or transition_to_next. Do NOT wrap the response in any outer object or key."
)


def _strategist_tool_definitions() -> List[dict[str, Any]]:
    return [
        {
            "name": "library_search",
            "description": "Request matching tracks from the Library Agent.",
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
        },
        {
            "name": "transition_analysis",
            "description": "Request a transition plan from the Transition Agent.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "track_a": {"type": "object"},
                    "track_b": {"type": "object"},
                },
                "required": ["track_a", "track_b"],
            },
        },
    ]


class StrategistAgent(ClaudeAgentBase):
    """Primary orchestrator agent."""

    def __init__(self, library_agent: LibraryAgent, transition_agent: TransitionAgent) -> None:
        super().__init__(system_prompt=STRATEGIST_SYSTEM_PROMPT, max_tokens=8182)
        self._library_agent = library_agent
        self._transition_agent = transition_agent
        self._track_cache: Dict[str, TrackData] = {}

    def plan_set(self, user_prompt: str) -> SetlistReport:
        print(f"🎧 Strategist planning set: {user_prompt}")
        messages: List[MessageParam] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt,
                    }
                ],
            }
        ]

        response = self._exchange_with_tools(
            messages,
            {
                "library_search": self._handle_library_search,
                "transition_analysis": self._handle_transition_analysis,
            },
            tools=_strategist_tool_definitions(),
        )

        text_blocks = [item.text for item in response.content if item.type == "text"]
        if not text_blocks:
            msg = "Strategist did not return the Final Setlist Report JSON"
            raise RuntimeError(msg)
        print("✅ Strategist completed setlist planning")
        
        raw_text = text_blocks[-1]
        print(f"📄 Raw response (first 500 chars): {raw_text[:500]}")
        
        json_text = extract_json_from_text(raw_text)
        print(f"🔍 Extracted JSON (first 500 chars): {json_text[:500]}")
        
        if not json_text or not json_text.strip():
            print(f"⚠️  Warning: Empty JSON after extraction. Full text blocks: {text_blocks}")
            msg = "Strategist returned empty JSON content"
            raise RuntimeError(msg)
        payload = json.loads(json_text)
        # Unwrap if Claude nested the response
        if "setlist_report" in payload:
            payload = payload["setlist_report"]
        payload = self._sanitize_setlist_payload(payload)
        return validate_setlist_report(payload)

    def _handle_library_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tracks = self._library_agent.fetch_tracks(arguments)
        for track in tracks:
            self._track_cache[track.id] = track
        return {"tracks": [track.model_dump() for track in tracks]}

    def _handle_transition_analysis(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        track_a_payload = self._hydrate_track_payload(arguments.get("track_a"))
        track_b_payload = self._hydrate_track_payload(arguments.get("track_b"))
        track_a = TrackData.model_validate(track_a_payload)
        track_b = TrackData.model_validate(track_b_payload)
        proposal = self._transition_agent.analyze(track_a, track_b)
        return proposal.model_dump()

    def _hydrate_track_payload(self, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Transition analysis requires track payloads")
        track_id = payload.get("id") or payload.get("track_id")
        cache_hit = self._track_cache.get(track_id) if track_id else None
        if cache_hit:
            merged = cache_hit.model_dump()
            merged.update({k: v for k, v in payload.items() if v is not None})
            return merged
        return payload

    @staticmethod
    def _sanitize_setlist_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure final entry mix_out_instructions are optional and consistent."""

        setlist = payload.get("setlist")
        if not isinstance(setlist, list) or not setlist:
            return payload

        for idx, entry in enumerate(setlist):
            if not isinstance(entry, dict):
                continue
            mix = entry.get("mix_out_instructions")
            track_id = entry.get("track_id")
            is_final_entry = idx == len(setlist) - 1
            if is_final_entry:
                if mix:
                    entry["mix_out_instructions"] = None
                continue

            next_track = setlist[idx + 1]
            expected_next_id = next_track.get("track_id") if isinstance(next_track, dict) else None
            if not mix:
                continue
            if not isinstance(mix, dict):
                entry["mix_out_instructions"] = None
                continue

            if track_id and mix.get("track_a_id") not in (None, track_id):
                mix["track_a_id"] = track_id
            if expected_next_id:
                mix["track_b_id"] = expected_next_id
        return payload
