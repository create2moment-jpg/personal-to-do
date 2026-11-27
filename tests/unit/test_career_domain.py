from ppos.domain.career import level_from_section, match_score, stem, tokens


def test_level_from_section() -> None:
    assert level_from_section("L5 — Senior Software Engineer") == "L5"
    assert level_from_section("Level 6: Staff") == "LEVEL6"
    assert level_from_section("ic4 expectations") == "IC4"
    assert level_from_section("Summary") is None
    assert level_from_section(None) is None


def test_tokens_drop_stopwords_and_singularise() -> None:
    assert {stem(w) for w in ("leads", "led", "leading")} == {"lead"}
    assert stem("improves") == stem("improved") == stem("improve")
    assert tokens("Leads the designs of systems across teams") == {
        "lead",
        "design",
        "system",
        "team",
    }


def test_match_is_explainable() -> None:
    m = match_score(
        "Leads technical design of systems used by several teams",
        "Led the retrieval system design adopted by two teams",
    )
    assert m is not None and set(m.shared) == {"leads", "design", "systems", "teams"}
    assert 0 < m.score < 1
    assert match_score("Mentors engineers", "Improved recall at 10") is None


def test_meaning_matches_is_relative_to_the_pool() -> None:
    from ppos.domain.career import meaning_matches

    assert meaning_matches({}) == {}
    # one clear match among unrelated ones, on a model with a high baseline
    sims = {"a": 0.82, "b": 0.51, "c": 0.48, "d": 0.5, "e": 0.47}
    assert meaning_matches(sims) == {"a": 0.82}
    # nothing stands out above the typical similarity → no suggestion
    assert meaning_matches({"a": 0.52, "b": 0.5, "c": 0.49, "d": 0.5}) == {}
    # small pools: near the best and above the floor
    assert meaning_matches({"a": 0.3, "b": 0.26, "c": 0.1}) == {"a": 0.3, "b": 0.26}
    assert meaning_matches({"a": 0.15}) == {}
