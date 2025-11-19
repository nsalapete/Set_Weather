"""Transition Agent: provides mixing guidance between two tracks."""
from __future__ import annotations

import json
from typing import List, Tuple

import httpx
from anthropic import APIError
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
        try:
            response = self._create_message(messages, tools=None)
        except (httpx.HTTPError, APIError) as exc:
            print(
                "⚠️ Transition Agent offline, generating heuristic fallback "
                f"({exc.__class__.__name__}: {exc})",
            )
            return self._fallback_transition(track_a, track_b, str(exc))
        text_blocks = [item.text for item in response.content if item.type == "text"]
        if not text_blocks:
            msg = "Transition Agent did not return JSON content"
            raise RuntimeError(msg)
        json_text = extract_json_from_text(text_blocks[-1])
        payload = json.loads(json_text)
        # Unwrap if Claude nested the response
        if "transition_proposal" in payload:
            payload = payload["transition_proposal"]
        payload["key_compatibility"] = self._describe_key_relation(
            track_a.key_camelot,
            track_b.key_camelot,
        )
        return TransitionProposal.model_validate(payload)

    def _fallback_transition(self, track_a: TrackData, track_b: TrackData, reason: str) -> TransitionProposal:
        """Generate deterministic instructions when Anthropic is unreachable."""

        bpm_change = float(track_b.bpm - track_a.bpm)
        key_compatibility = self._describe_key_relation(track_a.key_camelot, track_b.key_camelot)
        notes = (
            "Anthropic transition service unavailable ("
            f"{reason}). Blend manually using EQ rides and prudently align phrasing."
        )
        return TransitionProposal(
            transition_id=f"offline_{track_a.id}_{track_b.id}",
            track_a_id=track_a.id,
            track_b_id=track_b.id,
            key_compatibility=key_compatibility,
            bpm_change=bpm_change,
            mix_duration_bars=32,
            mixing_technique="Layer intro/outro over ~32 bars, trim highs on incoming track",
            suggested_fx="Gentle low-pass on outgoing, short reverb throw",
            notes_to_dj=notes,
        )

    @staticmethod
    def _describe_key_relation(key_a: str, key_b: str) -> str:
        """Approximate Camelot relationship for offline fallbacks."""

        number_a, mode_a = TransitionAgent._parse_camelot(key_a)
        number_b, mode_b = TransitionAgent._parse_camelot(key_b)
        if number_a is None or number_b is None:
            return "Unknown (offline fallback)"
        if key_a == key_b:
            return "Perfect Match"
        if number_a == number_b and mode_a != mode_b:
            return "Mode Swap"  # Same number, A/B flip
        distance = min((number_a - number_b) % 12, (number_b - number_a) % 12)
        if distance == 1:
            return "Adjacent Key"
        if distance == 2:
            return "Compatible 2-step"
        return "Creative Mix"

    @staticmethod
    def _parse_camelot(key: str) -> Tuple[int | None, str | None]:
        try:
            number = int(key[:-1]) % 12 or 12
            mode = key[-1].upper()
            if mode not in {"A", "B"}:
                return None, None
            return number, mode
        except (ValueError, IndexError):
            return None, None
