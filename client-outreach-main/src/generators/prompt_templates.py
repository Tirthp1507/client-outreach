"""Prompt templates for the LLM script provider."""

SYSTEM_PROMPT = (
    "You write short-form vertical video scripts (YouTube Shorts / IG Reels). "
    "Every script has exactly three parts: a HOOK that grabs attention in the "
    "first 2 seconds, MAIN CONTENT with 1-3 punchy points, and a CTA asking for "
    "a follow. Keep it under 50 seconds spoken (roughly 120-130 words total), "
    "plain conversational language, no markdown, no emoji."
)

USER_PROMPT_TEMPLATE = (
    'Write a short-form video script for the topic: "{topic}".\n'
    "Return ONLY valid JSON in this exact shape, do not wrap it in code fences:\n"
    '{\n'
    '  "title": "a punchy on-screen title for the video",\n'
    '  "segments": [\n'
    '    {"kind": "hook", "text": "..."},\n'
    '    {"kind": "main", "text": "..."},\n'
    '    {"kind": "cta", "text": "..."}\n'
    "  ]\n"
    "}\n"
    "Constraints: hook <= 20 words, main 40-60 words, cta <= 20 words. "
    'The "text" fields must be plain spoken sentences without stage directions.'
)


def build_user_prompt(topic: str) -> str:
    return USER_PROMPT_TEMPLATE.format(topic=topic.strip())