"""Utilities for parsing LLM outputs."""
import re

def extract_json_from_text(text: str) -> str:
    """Extract JSON content from a string, handling markdown code blocks."""
    # Try to find JSON inside markdown code blocks
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    matches = re.findall(pattern, text)
    if matches:
        # Return the last match (often the complete JSON after explanations)
        return matches[-1].strip()
    
    # If no code blocks, try to find the first { or [ and extract from there to the matching closing bracket
    stripped = text.strip()
    
    # Find first { or [
    start_brace = stripped.find("{")
    start_bracket = stripped.find("[")
    
    if start_brace == -1 and start_bracket == -1:
        return text
    
    # Determine which comes first
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        start = start_brace
        open_char = "{"
        close_char = "}"
    else:
        start = start_bracket
        open_char = "["
        close_char = "]"
    
    # Find matching closing bracket
    depth = 0
    for i in range(start, len(stripped)):
        if stripped[i] == open_char:
            depth += 1
        elif stripped[i] == close_char:
            depth -= 1
            if depth == 0:
                return stripped[start:i+1]
    
    # If we couldn't find a matching bracket, return from start to end
    return stripped[start:]
