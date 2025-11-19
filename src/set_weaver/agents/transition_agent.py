"""Transition Agent: provides mixing guidance between two tracks."""
from __future__ import annotations

import json
from typing import List

from anthropic.types import MessageParam

from set_weaver.agents.base import ClaudeAgentBase
from set_weaver.schemas.track_data import TrackData, TransitionProposal
from set_weaver.utils import extract_json_from_text


TRANSITION_SYSTEM_PROMPT = (
    "You are the Transition Agent. You receive JSON with two tracks (track_a, track_b). "
    "Assess Camelot key compatibility using the Camelot wheel (same key is 'Perfect Match', neighboring keys are 'Relative Key' or 'Sub-Dominant'). "
    "Return ONLY a JSON object with these exact fields: transition_id, track_a_id, track_b_id, key_compatibility, bpm_change, mix_duration_bars, mixing_technique, suggested_fx, notes_to_dj. "
    "CRITICAL: bpm_change must be a numeric value (float or integer) representing the BPM difference, NOT a string. "
    "For example, use 3 or 3.0, not '+3 BPM' or '122 to 125'. "
    "Do NOT wrap the response in any outer object or key."
)


class TransitionAgent(ClaudeAgentBase):
    """Generates structured transition instructions."""

    def __init__(self) -> None:
        super().__init__(system_prompt=TRANSITION_SYSTEM_PROMPT, max_tokens=1024)

    def analyze(self, track_a: TrackData, track_b: TrackData) -> TransitionProposal:
        print(f"🔗 Transition Agent analyzing: {track_a.artist} - {track_a.title} → {track_b.artist} - {track_b.title}")
        payload = {
            "track_a": track_a.model_dump(),
            "track_b": track_b.model_dump(),
        }
        messages: List[MessageParam] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ],
            }
        ]
        response = self._create_message(messages, tools=None)
        text_blocks = [item.text for item in response.content if item.type == "text"]
        if not text_blocks:
            msg = "Transition Agent did not return JSON content"
            raise RuntimeError(msg)
        json_text = extract_json_from_text(text_blocks[-1])
        payload = json.loads(json_text)
        # Unwrap if Claude nested the response
        if "transition_proposal" in payload:
            payload = payload["transition_proposal"]
        return TransitionProposal.model_validate(payload)
