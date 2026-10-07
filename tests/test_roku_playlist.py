from core.roku_playlist import infer_stream_format, parse_json_playlist, parse_m3u_playlist


def test_parse_m3u_playlist_resolves_relative_stream_urls():
    entries = parse_m3u_playlist(
        '#EXTM3U\n#EXTINF:-1 group-title="News",Evening News\nnews.m3u8\n',
        "https://streams.example/lists/playlist.m3u",
    )

    assert len(entries) == 1
    assert entries[0]["title"] == "Evening News"
    assert entries[0]["group"] == "News"
    assert entries[0]["url"] == "https://streams.example/lists/news.m3u8"


def test_parse_json_playlist_keeps_all_supported_entries():
    entries = parse_json_playlist([
        {"title": "Demo News", "url": "https://streams.example/news.m3u8", "group": "News"},
        {"title": "Demo Sports", "url": "https://streams.example/sports.m3u8", "group": "Sports"},
    ])

    assert [entry["title"] for entry in entries] == ["Demo News", "Demo Sports"]
    assert {entry["group"] for entry in entries} == {"News", "Sports"}


def test_m3u_preserves_provider_specific_group_titles():
    entries = parse_m3u_playlist(
        '#EXTM3U\n'
        '#EXTINF:-1 group-title="US | Premium Entertainment",Channel One\n'
        'https://streams.example/provider/live/one.m3u8\n'
        '#EXTINF:-1 group-title="UK | Premium Entertainment",Channel Two\n'
        'https://streams.example/provider/live/two.m3u8\n'
    )

    assert {entry["group"] for entry in entries} == {
        "US | Premium Entertainment",
        "UK | Premium Entertainment",
    }
    assert len({entry["group"] for entry in entries}) == 2


def test_json_playlist_reads_original_group_title_from_metadata():
    entries = parse_json_playlist([
        {
            "title": "Channel One",
            "url": "https://streams.example/provider/live/one.m3u8",
            "metadata": {"group_title": "US | Premium Entertainment"},
        },
    ])

    assert entries[0]["group"] == "US | Premium Entertainment"


def test_stream_format_defaults_to_hls_and_detects_ts_with_query_strings():
    assert infer_stream_format("https://streams.example/live/index.m3u8?token=x") == "hls"
    assert infer_stream_format("https://streams.example/live/123.ts?token=x") == "mp2ts"
    assert infer_stream_format("https://streams.example/live/opaque-id") == "hls"
    assert infer_stream_format("https://streams.example/live/opaque-id?output=ts") == "mp2ts"
    assert infer_stream_format("https://streams.example/live/opaque-id?output=mp2ts") == "mp2ts"
    assert infer_stream_format("https://streams.example/live/opaque-id?container=mpeg-ts") == "mp2ts"
    assert infer_stream_format("https://streams.example/playlist?type=m3u") == "hls"
    assert infer_stream_format("https://streams.example/archive/movie.mkv") == "mkv"
    assert infer_stream_format("https://streams.example/archive/movie.avi") == "unsupported"


def test_m3u_entries_infer_format_and_group_from_title_and_url():
    entries = parse_m3u_playlist(
        "#EXTM3U\n"
        "#EXTINF:-1,Evening News\nhttps://streams.example/news/live.m3u8?key=1\n"
        "#EXTINF:-1,Match Feed\nhttps://streams.example/live/123.ts?key=2\n"
        "#EXTINF:-1,Film Title\nhttps://streams.example/movie/456.mp4?key=3\n"
    )

    assert [(entry["group"], entry["stream_format"]) for entry in entries] == [
        ("Live TV", "mp2ts"),
        ("Movies", "mp4"),
        ("News", "hls"),
    ]
    assert entries[0]["url"].startswith("https://")


def test_m3u_provider_movie_route_creates_movies_group_without_extinf_group():
    entries = parse_m3u_playlist(
        "#EXTM3U\n"
        "#EXTINF:-1,The Lord of the Rings: The Fellowship of the Ring (2001)\n"
        "https://streams.example/provider/movie/183240.avi\n"
        "#EXTINF:-1,Manhattan (1979)\n"
        "https://streams.example/provider/MOVIE/183245.avi\n"
    )

    assert [entry["group"] for entry in entries] == ["Movies", "Movies"]
    assert [entry["category"] for entry in entries] == ["movies", "movies"]
    assert [entry["stream_format"] for entry in entries] == ["unsupported", "unsupported"]


def test_json_placeholder_group_is_replaced_by_provider_route_category():
    entries = parse_json_playlist([
        {
            "title": "Movie without a movie keyword",
            "url": "https://streams.example/provider/movie/123.avi",
            "group": "Uncategorized",
        },
    ])

    assert entries[0]["group"] == "Movies"
    assert entries[0]["category"] == "movies"


def test_playlist_categories_use_series_movies_and_live_tv_labels():
    entries = parse_m3u_playlist(
        "#EXTM3U\n"
        "#EXTINF:-1,Drama episode\nhttps://streams.example/provider/series/episode.mp4\n"
        "#EXTINF:-1,Feature film\nhttps://streams.example/provider/movie/film.mp4\n"
        "#EXTINF:-1 group-title=\"Live\",News channel\nhttps://streams.example/provider/live/channel.m3u8\n"
    )

    assert {entry["group"] for entry in entries} == {"Series", "Movies", "Live TV"}
    assert {entry["category"] for entry in entries} == {"series", "movies", "live"}


def test_m3u_leading_247_title_prefix_becomes_category():
    entries = parse_m3u_playlist(
        "#EXTM3U\n"
        "#EXTINF:-1,24/7 X-MEN\n"
        "https://streams.example/provider/movie/123.mp4\n"
    )

    assert len(entries) == 1
    assert entries[0]["group"] == "24/7"
    assert entries[0]["category"] == "24-7"
    assert entries[0]["title"] == "X-MEN"


def test_json_leading_247_title_prefix_becomes_category():
    entries = parse_json_playlist([
        {
            "title": "24/7 X-MEN",
            "url": "https://streams.example/provider/movie/123.mp4",
            "group": "Uncategorized",
            "category": "uncategorized",
        },
    ])

    assert entries[0]["group"] == "24/7"
    assert entries[0]["category"] == "24-7"
    assert entries[0]["title"] == "X-MEN"


def test_m3u_explicit_group_title_takes_precedence_over_title_prefix():
    entries = parse_m3u_playlist(
        '#EXTM3U\n#EXTINF:-1 group-title="Movies",24/7 X-MEN\n'
        "https://streams.example/provider/movie/123.mp4\n"
    )

    assert entries[0]["group"] == "Movies"
    assert entries[0]["title"] == "24/7 X-MEN"


def test_direct_hls_manifest_is_not_misread_as_a_channel_per_segment():
    source_url = "https://streams.example/live/index.m3u8"
    entries = parse_m3u_playlist(
        "#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\nsegment-1.ts\n#EXTINF:6,\nsegment-2.ts\n",
        source_url,
    )

    assert len(entries) == 1
    assert entries[0]["url"] == source_url
    assert entries[0]["stream_format"] == "hls"


def test_m3u_preserves_stream_request_headers():
    entries = parse_m3u_playlist(
        '#EXTM3U\n#EXTINF:-1 group-title="News",Secure News\n'
        '#EXTVLCOPT:http-user-agent=RokuTest\n'
        '#EXTHTTP:{"Referer":"https://guide.example"}\n'
        "https://streams.example/news/index.m3u8\n"
    )

    assert entries[0]["http_headers"] == {
        "User-Agent": "RokuTest",
        "Referer": "https://guide.example",
    }


def test_m3u_preserves_extinf_fields_for_roku_details():
    entries = parse_m3u_playlist(
        '#EXTM3U\n'
        '#EXTINF:-1 tvg-id="news.one" tvg-name="Evening News" '
        'tvg-logo="https://logos.example/news.png" group-title="News" tvg-language="English",Evening News\n'
        'https://streams.example/news/index.m3u8\n'
    )

    assert len(entries) == 1
    assert entries[0]["tvg_id"] == "news.one"
    assert entries[0]["duration"] == "-1"
    assert entries[0]["logo"] == "https://logos.example/news.png"
    assert entries[0]["metadata"]["group_title"] == "News"
    assert entries[0]["metadata"]["tvg_name"] == "Evening News"


def test_m3u_extgrp_after_extinf_preserves_category_and_icon():
    entries = parse_m3u_playlist(
        '#EXTM3U\n'
        '#EXTINF:-1 tvg-id="bbc.one" tvg-logo="../logos/bbc.png" genre="News",BBC One\n'
        '#EXTGRP:UK Channels\n'
        'https://streams.example/live/bbc-one.m3u8\n'
        '#EXTINF:-1,Uncategorized entry\n'
        'https://streams.example/channel/other.m3u8\n'
    , "https://streams.example/lists/channels.m3u")

    bbc = next(entry for entry in entries if entry["title"] == "BBC One")
    other = next(entry for entry in entries if entry["title"] == "Uncategorized entry")
    assert bbc["group"] == "UK Channels"
    assert bbc["category"] == "uk-channels"
    assert bbc["tvg_id"] == "bbc.one"
    assert bbc["logo"] == "https://streams.example/logos/bbc.png"
    assert bbc["metadata"]["tvg_logo"] == "../logos/bbc.png"
    assert bbc["metadata"]["genre"] == "News"
    assert other["group"] == "Uncategorized"


def test_json_relative_logo_uses_playlist_base_url_and_keeps_genre():
    entries = parse_json_playlist(
        [{
            "title": "BBC One",
            "url": "live/bbc-one.m3u8",
            "group": "UK Channels",
            "logo": "../logos/bbc.png",
            "metadata": {"genre": "News"},
        }],
        "https://streams.example/lists/playlist.json",
    )

    assert entries[0]["logo"] == "https://streams.example/logos/bbc.png"
    assert entries[0]["metadata"]["genre"] == "News"


def test_parser_sorts_groups_and_removes_only_exact_duplicate_streams():
    entries = parse_m3u_playlist(
        "#EXTM3U\n"
        '#EXTINF:-1 group-title="Sports",Zeta\nhttps://streams.example/zeta.ts\n'
        '#EXTINF:-1 group-title="News",Alpha News\nhttps://streams.example/news.m3u8\n'
        '#EXTINF:-1 group-title="Sports",Zeta duplicate\nhttps://streams.example/zeta.ts\n'
    )

    assert [(entry["group"], entry["title"]) for entry in entries] == [
        ("News", "Alpha News"),
        ("Sports", "Zeta"),
    ]
