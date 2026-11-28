from ppos.domain.wikilinks import (
    headings,
    link_first_mention,
    parse_links,
    rename_links,
    render_template,
    unlinked_mentions,
)


def test_parse_plain_escaped_alias_heading_and_code() -> None:
    body = (
        "See [[Hybrid retrieval]] and \\[\\[Eval harness\\]\\].\n"
        "Also [[Hybrid retrieval#Decision|the decision]].\n"
        "`[[not a link]]`\n```\n[[also not]]\n```\n"
    )
    links = parse_links(body)
    assert [(lk.target, lk.heading, lk.alias) for lk in links] == [
        ("Hybrid retrieval", None, None),
        ("Eval harness", None, None),
        ("Hybrid retrieval", "Decision", "the decision"),
    ]
    assert links[0].key == "hybrid retrieval"


def test_rename_keeps_headings_aliases_and_escaping() -> None:
    body = "[[Old name]] · \\[\\[old  NAME#Part\\|shown\\]\\] · [[Other]] · `[[Old name]]`"
    new, n = rename_links(body, "Old name", "New name")
    assert n == 2
    assert new == "[[New name]] · \\[\\[New name#Part\\|shown\\]\\] · [[Other]] · `[[Old name]]`"


def test_unlinked_mentions_and_linking_them() -> None:
    body = "Eval harness is slow. [[Eval harness]] fixed. eval harness again."
    assert len(unlinked_mentions(body, "Eval harness")) == 2
    linked = link_first_mention(body, "Eval harness")
    assert linked == "[[Eval harness]] is slow. [[Eval harness]] fixed. eval harness again."
    again = link_first_mention(linked or "", "Eval harness")
    assert again and again.endswith("[[Eval harness|eval harness]] again.")
    assert unlinked_mentions("Evaluation harnesses", "Eval harness") == []


def test_outline_and_templates() -> None:
    assert headings("# A\ntext\n## B ##\n```\n# no\n```") == [(1, "A"), (2, "B")]
    assert render_template(
        "{{title}} on {{ date }} {{unknown}}", {"title": "1:1", "date": "2026-11-28"}
    ) == ("1:1 on 2026-11-28 {{unknown}}")
