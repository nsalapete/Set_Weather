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
    "Respond ONLY with a JSON object containing these exact fields: set_title, duration_minutes, setlist. "
    "Do NOT wrap the response in any outer object or key."
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
        super().__init__(system_prompt=STRATEGIST_SYSTEM_PROMPT, max_tokens=3072)
        self._library_agent = library_agent
        self._transition_agent = transition_agent

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
        json_text = extract_json_from_text(text_blocks[-1])
        payload = json.loads(json_text)
        # Unwrap if Claude nested the response
        if "setlist_report" in payload:
            payload = payload["setlist_report"]
        return validate_setlist_report(payload)

    def _handle_library_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tracks = self._library_agent.fetch_tracks(arguments)
        return {"tracks": [track.model_dump() for track in tracks]}

    def _handle_transition_analysis(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        track_a = TrackData.model_validate(arguments["track_a"])
        track_b = TrackData.model_validate(arguments["track_b"])
        proposal = self._transition_agent.analyze(track_a, track_b)
        return proposal.model_dump()
