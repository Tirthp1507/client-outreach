"""Tests for AI Topic Strategist, Content Strategy models, and Strategy Director."""

from processors.models import ProcessedCandidate
from strategy.models import ContentFormat, HookType, TargetAudience
from strategy.topic_strategist import TopicStrategist
from generators.strategy_director import StrategyDirector


def test_topic_strategist_classifies_news_format():
    cand = ProcessedCandidate(
        id="cand_news_1",
        source_name="BBC News",
        source_url="https://bbc.com/article",
        raw_title="Tech giants settle landmark lawsuit for 5 billion dollars",
        clean_title="Tech giants settle landmark lawsuit for 5 billion dollars",
        topic_suggestion="Tech giants settle landmark lawsuit for 5 billion dollars",
        summary="A historic multi-billion dollar settlement was reached in federal court today.",
        clean_body="The court approved the historic deal after months of contentious negotiations.",
        score=88.0,
    )

    strategist = TopicStrategist()
    strat = strategist.develop_strategy(cand)

    assert strat.content_format == ContentFormat.NEWS
    assert strat.hook_strategy in (HookType.STATISTIC_SHOCK, HookType.CURIOSITY_GAP)
    assert strat.short_form_potential_score > 70.0
    assert len(strat.scene_plans) >= 3


def test_topic_strategist_classifies_list_format():
    cand = ProcessedCandidate(
        id="cand_list_1",
        source_name="Hacker News",
        source_url="https://news.ycombinator.com/item",
        raw_title="Top 5 productivity tools every software developer should use",
        clean_title="Top 5 productivity tools every software developer should use",
        topic_suggestion="Top 5 productivity tools every software developer should use",
        summary="Here are the top tools to speed up daily workflow.",
        clean_body="First tool is modern terminal. Second is automated testing.",
        score=75.0,
    )

    strategist = TopicStrategist()
    strat = strategist.develop_strategy(cand)

    assert strat.content_format == ContentFormat.LIST
    assert strat.target_audience == TargetAudience.TECH_ENTHUSIASTS


def test_strategy_director_builds_multi_scene_script():
    cand = ProcessedCandidate(
        id="cand_test_1",
        source_name="TechDaily",
        source_url="https://techdaily.com",
        raw_title="Why Python 3.14 changes everything for developers",
        clean_title="Why Python 3.14 changes everything for developers",
        topic_suggestion="Why Python 3.14 changes everything for developers",
        summary="Python 3.14 introduces free-threaded runtime performance gains.",
        clean_body="The release eliminates the GIL and allows true parallelism.",
        score=82.0,
    )

    strategist = TopicStrategist()
    strat = strategist.develop_strategy(cand)
    script = StrategyDirector.direct_script(cand, strat)

    assert script.hook is not None
    assert len(script.hook.text) > 10
    assert script.main is not None
    assert script.cta is not None
    assert len(script.all_scenes) >= 3
    assert script.strategy["content_format"] == strat.content_format.value