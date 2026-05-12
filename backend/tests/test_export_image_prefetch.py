"""Tests for Phase 6AL-Export parallel image prefetch.

The new fast-path in ``ExportService._export_pptx_sync`` fetches every
distinct ``image_url`` in parallel before rendering. These tests cover
the prefetch helper directly so they do not need a Pollinations stub.
"""
from __future__ import annotations

from unittest.mock import patch

from services.export_service import ExportService


def test_prefetch_returns_empty_when_no_images():
    slides = [{"id": "s0", "layout": "title"}, {"id": "s1", "layout": "bullets"}]
    assert ExportService._prefetch_images(slides) == {}


def test_prefetch_deduplicates_urls():
    slides = [
        {"id": "s0", "image_url": "https://example.com/a.png"},
        {"id": "s1", "image_url": "https://example.com/a.png"},
        {"id": "s2", "image_url": "https://example.com/b.png"},
    ]
    calls: list[str] = []

    def fake_fetch(url):
        calls.append(url)
        return b"fake"

    with patch.object(ExportService, "_fetch_image", staticmethod(fake_fetch)):
        cache = ExportService._prefetch_images(slides)

    # Two distinct URLs, two fetches total.
    assert sorted(calls) == ["https://example.com/a.png", "https://example.com/b.png"]
    assert cache == {
        "https://example.com/a.png": b"fake",
        "https://example.com/b.png": b"fake",
    }


def test_prefetch_handles_failing_fetch_as_none():
    slides = [{"id": "s0", "image_url": "https://example.com/x.png"}]

    def fake_fetch(_url):
        return None

    with patch.object(ExportService, "_fetch_image", staticmethod(fake_fetch)):
        cache = ExportService._prefetch_images(slides)

    assert cache == {"https://example.com/x.png": None}


def test_prefetch_skips_non_dict_entries():
    # _export_pptx_sync passes raw slides through; non-dict entries
    # (e.g. None left in by upstream defenses) must not crash prefetch.
    slides = [
        None,
        "garbage",
        {"id": "s0", "image_url": "https://example.com/a.png"},
    ]
    with patch.object(ExportService, "_fetch_image", staticmethod(lambda u: b"x")):
        cache = ExportService._prefetch_images(slides)  # type: ignore[arg-type]
    assert cache == {"https://example.com/a.png": b"x"}


def test_fetch_image_returns_none_on_falsy_url():
    assert ExportService._fetch_image(None) is None
    assert ExportService._fetch_image("") is None
