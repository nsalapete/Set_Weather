"""Utilities for parsing LLM outputs."""
import re

def extract_json_from_text(text: str) -> str:
    """Extract JSON content from a string, handling markdown code blocks."""
    # Try to find JSON inside markdown code blocks
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    
    # If no code blocks, assume the whole text is JSON (or try to find the first { or [)
    # Simple heuristic: if it looks like it starts with { or [, return it.
    # Otherwise, just return the text and let json.loads fail if it's bad.
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
        
    return text
