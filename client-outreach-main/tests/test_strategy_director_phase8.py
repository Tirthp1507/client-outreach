"""Tests for upgraded hook and storytelling engine in StrategyDirector."""

from generators.strategy_director import StrategyDirector
from processors.models import ProcessedCandidate
from strategy.models import ContentFormat, ContentStrategy, HookType, ScenePlan, TargetAudience


def test_strategy_director_extracts_statistic_in_hook():
    cand = ProcessedCandidate(
        id="cand_stat_1",
        source_name="Ars Technica",
        source_url="https://arstechnica.com",
        raw_title="OpenAI signs landmark $10 billion computing partnership",
        clean_title="OpenAI signs landmark $10 billion computing partnership",
        topic_suggestion="OpenAI signs landmark $10 billion computing partnership",
        summary="A historic multi-billion dollar deal was confirmed today.",
        clean_body="The agreement provides high-density computing clusters across global data centers.",
        score=92.0,
    )

    strat = ContentStrategy(
        candidate_id="cand_stat_1",
        topic=cand.clean_title,
        content_format=ContentFormat.NEWS,
        recommended_angle="The massive computing expansion",
        target_audience=TargetAudience.TECH_ENTHUSIASTS,
        hook_strategy=HookType.STATISTIC_SHOCK,
        scene_plans=[
            ScenePlan(scene_number=1, kind="hook", purpose="Hook", visual_style="Bold headline", broll_keywords=["ai"]),
            ScenePlan(scene_number=2, kind="main", purpose="Story", visual_style="Context B-roll", broll_keywords=["server"]),
            ScenePlan(scene_number=3, kind="cta", purpose="CTA", visual_style="Outro card", broll_keywords=["social"]),
        ],
    )

    script = StrategyDirector.direct_script(cand, strat)
    assert "$10 billion" in script.hook.text
    assert "Save this to stay ahead" in script.cta.text