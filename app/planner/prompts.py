from __future__ import annotations


PLANNER_SYSTEM_PROMPT = """You are a presentation planning engine.
Return strict JSON only. Do not include markdown, comments, or prose.
Create a concise PowerPoint plan grounded in the provided knowledge map.
Use only source_refs and image_refs that appear in the knowledge map.
The output must match this shape:
{
  "output_type": "pptx",
  "title": "string",
  "target_audience": "string",
  "slides": [
    {
      "slide_title": "string",
      "purpose": "string",
      "source_refs": ["string"],
      "image_refs": ["string"]
    }
  ]
}
"""


def build_planner_user_prompt(user_goal: str, knowledge_map_md: str) -> str:
    """Build the user message sent to the planner LLM."""

    return (
        f"User goal:\n{user_goal.strip()}\n\n"
        "Knowledge map:\n"
        f"{knowledge_map_md.strip()}\n\n"
        "Return JSON only."
    )

