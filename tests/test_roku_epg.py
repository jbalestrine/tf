from datetime import datetime, timezone

import pytest

from core.roku_epg import apply_xmltv_listings, parse_xmltv_listings


def test_parse_xmltv_preserves_programme_titles_and_matches_channel_ids():
    content = """<?xml version="1.0" encoding="UTF-8"?>
    <tv>
      <channel id="news.one"><display-name>Evening News</display-name></channel>
      <programme start="20260101120000 +0000" stop="20260101130000 +0000" channel="news.one">
        <title>Current <b>News</b></title><desc>Top stories today</desc>
      </programme>
      <programme start="20260101130000 +0000" stop="20260101140000 +0000" channel="news.one">
        <title>Weather</title>
      </programme>
    </tv>
    """

    guide = parse_xmltv_listings(
        content,
        now=datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc),
    )
    entries = [{"tvg_id": "news.one"}, {"tvg_id": "other"}]

    assert guide["news.one"]["now"]["title"] == "Current News"
    assert guide["news.one"]["now"]["description"] == "Top stories today"
    assert guide["news.one"]["next"]["title"] == "Weather"
    assert apply_xmltv_listings(entries, guide) == 1
    assert entries[0]["program_now"]["title"] == "Current News"
    assert "program_now" not in entries[1]


def test_parse_xmltv_rejects_entity_declarations():
    with pytest.raises(ValueError, match="entity declarations"):
        parse_xmltv_listings(
            '<!DOCTYPE tv [<!ENTITY x "unsafe">]><tv><programme>&x;</programme></tv>'
        )


def test_parse_xmltv_reports_invalid_xml():
    with pytest.raises(ValueError, match="not valid XML"):
        parse_xmltv_listings("<tv><programme></tv>")
