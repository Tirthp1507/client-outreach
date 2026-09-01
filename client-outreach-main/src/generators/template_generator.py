"""Deterministic template-based script provider.

Produces a structured 3-part script from a topic without any external API.
Used as the default provider so the pipeline is runnable offline and testable
without keys; swap in an LLM provider (see ``openai_generator.py``) for richer
content.
"""

from __future__ import annotations

import random
import re
from typing import Sequence

from generators.base import ScriptProvider
from generators.models import ScriptSegment, ShortScript

_HOOKS: Sequence[str] = (
    "Here's what almost nobody tells you about {topic}.",
    "Stop scrolling — this completely changes how you look at {topic}.",
    "{topic}: you've probably been approaching this all wrong.",
    "If you only remember one single thing today, make it this about {topic}.",
    "Why is everyone suddenly talking about {topic}? Here's the real breakdown.",
    "Watch this before you waste another minute on {topic} — I'll show you the shortcut.",
    "Nobody explains {topic} like this. This is the 60-second breakdown you needed.",
    "There are two ways to handle {topic}: the hard way, and the way you'll learn in ten seconds.",
    "Quick reality check: most advice on {topic} is wrong. Here's what actually works.",
    "You scroll past a hundred videos about {topic}. This is the only one you need to save.",
)

_MAIN_TEMPLATES: Sequence[str] = (
    "Let's break it down. First: focus on the single highest-impact lever around "
    "{topic} and execute that before anything else. Second: strip away the "
    "friction — batch your focus, protect your energy, and eliminate secondary distractions. "
    "Third: constantly review what moves the needle so you only double down on what works.",
    "Here is the truth. Most people overcomplicate {topic}. But when you look closer, "
    "success comes down to two simple rules: consistency in the fundamentals, and relentless "
    "removal of wasted effort. Focus on what actually produces results.",
    "Here's the three-step system. Step one: define what {topic} actually means for you today. "
    "Step two: test the smallest possible version this week and track the result. "
    "Step three: scale what beat your baseline and drop what didn't.",
    "Most people start {topic} at the wrong end. Instead, flip it: find the one mistake "
    "everyone around you makes, avoid it, and suddenly the rest falls into place. "
    "It sounds small, but it compounds fast.",
    "The fastest way to get results with {topic} is counterintuitive — slow down. "
    "Do one thing correctly instead of five things halfway. Then repeat it until "
    "it becomes automatic, and only then add the next layer.",
    "Here are the numbers. People who take {topic} seriously improve within the first week "
    "simply by measuring it every single morning. Track it, review it weekly, and adjust "
    "one thing at a time. Progress follows focus.",
    "Let's simplify {topic}. There are exactly three things that matter: how you prepare, "
    "how you execute, and how you review. Nail each one in order and the results take care "
    "of themselves.",
)

_CTAS: Sequence[str] = (
    "If that gave you value, follow for daily breakdowns — and start today.",
    "Drop your take in the comments, share with a friend, and follow for more.",
    "Save this for later, test it out, and subscribe for part two.",
    "Comment 'one' if you're in, follow so you don't miss the next breakdown, and try it tonight.",
    "Turn on notifications, bookmark this, and let me know which step you'll start with.",
)


class TemplateScriptProvider(ScriptProvider):
    name = "template"

    def generate(
        self,
        topic: str,
        *,
        target_seconds: int = 40,
        seed: int | None = None,
        **kwargs,
    ) -> ShortScript:
        topic = topic.strip()
        if not topic:
            raise ValueError("topic must not be empty")

        rng = random.Random(seed)
        words_per_minute = kwargs.get("words_per_minute", 150)
        total_words = max(50, int(target_seconds / 60 * words_per_minute))
        main_words = max(25, int(total_words * 0.6))
        cta_words = max(8, int(total_words * 0.15))

        hook = _trim_words(rng.choice(_HOOKS).format(topic=topic), int(total_words * 0.2))
        main_template = rng.choice(_MAIN_TEMPLATES)
        main = _trim_words(main_template.format(topic=topic.lower()), main_words)
        cta = _trim_words(rng.choice(_CTAS), cta_words)

        title = _title_case(topic)
        keywords = _topic_keywords(topic)
        return ShortScript(
            topic=topic,
            title=title,
            provider=self.name,
            target_seconds=target_seconds,
            segments=[
                ScriptSegment(
                    kind="hook",
                    text=hook,
                    visual_prompt=f"Cinematic high-contrast hook visual highlighting {topic}",
                    broll_keywords=[keywords[0], "attention"] if keywords else ["news", "tech"],
                    tone="urgent",
                ),
                ScriptSegment(
                    kind="main",
                    text=main,
                    visual_prompt=f"Clean dynamic B-roll visual demonstrating {topic} concept in action",
                    broll_keywords=keywords[1:3] or ["laptop", "workspace"],
                    tone="informative",
                ),
                ScriptSegment(
                    kind="cta",
                    text=cta,
                    visual_prompt="Modern motion graphic outro with follow and subscribe icon",
                    broll_keywords=["social", "follow"],
                    tone="compelling",
                ),
            ],
        )


def _topic_keywords(topic: str) -> list[str]:
    """Derive short B-roll search keywords from a topic string."""
    words = [w.lower() for w in re.findall(r"\b[a-z][a-z0-9'-]{3,}\b", topic)]
    stop = {
        "with", "that", "this", "from", "your", "have", "there", "about",
        "what", "when", "where", "which", "while", "then", "than", "into",
        "they", "them", "their", "these", "those", "will", "would", "could",
    }
    seen: list[str] = []
    for w in words:
        if w not in stop and w not in seen:
            seen.append(w)
        if len(seen) >= 4:
            break
    return seen or ["tech", "analysis"]


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    trimmed = " ".join(words[:max_words]).rstrip(".,;: ")
    return trimmed + "..."


def _title_case(topic: str) -> str:
    words = topic.split()
    if not words:
        return topic
    stopwords = {"a", "an", "the", "and", "or", "of", "to", "in", "for"}
    result = [words[0].capitalize()]
    for word in words[1:]:
        result.append(word if word.lower() in stopwords else word.capitalize())
    return " ".join(result)