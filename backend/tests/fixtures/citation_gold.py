"""Phase 6K - Offline gold corpus for the claim-citation mapper.

Five deterministic deck/slide cases. Each case has:

* ``id``: stable case id.
* ``description``: one-line intent.
* ``deck``: the deck dict that the mapper sees as input.
* ``expected``: a mapping ``{(slide_index, path): expectation}`` where
  expectation is a dict with ``supported`` (bool), an optional set
  ``source_ids`` of acceptable best-match source ids (any one of them
  may be picked), and an optional ``basis`` constraint (str or set).

The corpus is intentionally small. It is not a benchmark; it is a
contract for the mapper's behaviour on representative cases.
"""

from __future__ import annotations

from typing import Any


def gold_cases() -> list[dict[str, Any]]:
    return [
        # ------------------------------------------------------------------
        # Case 1: simple bullet supported by a single source via keyword
        # overlap. The other (irrelevant) source must NOT be picked.
        # ------------------------------------------------------------------
        {
            "id": "C1-bullet-keyword-overlap",
            "description": "Bullet about renewable solar capacity supported by IRENA snippet only.",
            "deck": {
                "sources": [
                    {
                        "url": "https://irena.org/renewable-capacity-2024",
                        "title": "IRENA Renewable Capacity 2024",
                        "snippet": "Global solar photovoltaic capacity grew strongly in 2024 driven by utility-scale deployments.",
                    },
                    {
                        "url": "https://example.com/cooking-recipes",
                        "title": "Best Pasta Recipes",
                        "snippet": "Boil salted water, cook pasta al dente, and toss with sauce.",
                    },
                ],
                "slides": [
                    {
                        "layout": "bullets",
                        "title": "Renewable Energy Trends",
                        "bullets": [
                            "Global solar photovoltaic capacity grew strongly in 2024",
                        ],
                    },
                ],
            },
            "expected": {
                (0, "bullets[0]"): {
                    "supported": True,
                    "source_ids": {"https://irena.org/renewable-capacity-2024"},
                    "basis": {"exact_phrase", "keyword_overlap"},
                },
            },
        },

        # ------------------------------------------------------------------
        # Case 2: numeric stats matched to a source containing the same
        # numbers and overlapping vocabulary.
        # ------------------------------------------------------------------
        {
            "id": "C2-stats-numeric-match",
            "description": "Stats slide whose values are present in a single source.",
            "deck": {
                "sources": [
                    {
                        "url": "https://example.com/q1-report",
                        "title": "Q1 Sales Report",
                        "snippet": "Q1 revenue reached 42 million with 77 net new logos and 93 percent retention.",
                    }
                ],
                "slides": [
                    {
                        "layout": "stats",
                        "title": "Q1 Highlights",
                        "stats": [
                            {"value": "42M", "label": "Revenue"},
                            {"value": "77", "label": "New Logos"},
                            {"value": "93%", "label": "Retention"},
                        ],
                    }
                ],
            },
            "expected": {
                (0, "stats[0]"): {
                    "supported": True,
                    "source_ids": {"https://example.com/q1-report"},
                },
                (0, "stats[1]"): {
                    "supported": True,
                    "source_ids": {"https://example.com/q1-report"},
                },
                (0, "stats[2]"): {
                    "supported": True,
                    "source_ids": {"https://example.com/q1-report"},
                },
            },
        },

        # ------------------------------------------------------------------
        # Case 3: an unsupported claim - no source mentions it. Must be
        # marked supported=False with basis="no_match".
        # ------------------------------------------------------------------
        {
            "id": "C3-unsupported-claim",
            "description": "Bullet has no supporting source in the deck.",
            "deck": {
                "sources": [
                    {
                        "url": "https://example.com/weather",
                        "title": "Weekly Weather Outlook",
                        "snippet": "Mostly sunny with afternoon thunderstorms midweek.",
                    }
                ],
                "slides": [
                    {
                        "layout": "bullets",
                        "title": "Engineering Roadmap",
                        "bullets": [
                            "Quantum compiler shipped to production customers",
                        ],
                    }
                ],
            },
            "expected": {
                (0, "bullets[0]"): {
                    "supported": False,
                    "basis": "no_match",
                    "source_ids": set(),
                },
            },
        },

        # ------------------------------------------------------------------
        # Case 4: multi-source - a claim has overlap with TWO sources;
        # both should appear in `supports`, the best one is picked first.
        # ------------------------------------------------------------------
        {
            "id": "C4-multi-source-support",
            "description": "Claim about EV battery costs supported by two distinct sources.",
            "deck": {
                "sources": [
                    {
                        "url": "https://bnef.example/ev-battery-costs-2024",
                        "title": "BNEF EV Battery Price Survey",
                        "snippet": "Average lithium-ion battery pack prices declined again in 2024 across major regions.",
                    },
                    {
                        "url": "https://iea.example/ev-outlook-2024",
                        "title": "IEA EV Outlook 2024",
                        "snippet": "Lithium-ion battery pack prices continued declining in 2024 supporting EV adoption.",
                    },
                ],
                "slides": [
                    {
                        "layout": "bullets",
                        "title": "EV Cost Trends",
                        "bullets": [
                            "Lithium-ion battery pack prices declined in 2024",
                        ],
                    }
                ],
            },
            "expected": {
                (0, "bullets[0]"): {
                    "supported": True,
                    # Either source is acceptable as best; both must be in supports.
                    "source_ids": {
                        "https://bnef.example/ev-battery-costs-2024",
                        "https://iea.example/ev-outlook-2024",
                    },
                    "min_supports": 2,
                },
            },
        },

        # ------------------------------------------------------------------
        # Case 5: numeric guard - claim says 32% but source only has 12%.
        # The mapper MUST NOT mark this as a numeric match. Token overlap
        # is also low, so the expected outcome is unsupported (no_match).
        # ------------------------------------------------------------------
        {
            "id": "C5-wrong-number-guard",
            "description": "Claim percent does not appear in source - must not numeric-match.",
            "deck": {
                "sources": [
                    {
                        "url": "https://example.com/yoy",
                        "title": "Industry YoY Update",
                        "snippet": "Sector grew approximately 12 percent year over year in the prior period.",
                    }
                ],
                "slides": [
                    {
                        "layout": "bullets",
                        "title": "Growth",
                        "bullets": [
                            "Solar capacity rose 32% YoY",
                        ],
                    }
                ],
            },
            "expected": {
                (0, "bullets[0]"): {
                    "supported": False,
                    "basis": "no_match",
                },
            },
        },
    ]
