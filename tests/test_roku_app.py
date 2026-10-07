from io import BytesIO
import json
import zipfile
from xml.etree import ElementTree

from PIL import Image
import pytest

from core.roku_app import (
    ROKU_PLAYLIST_SHARD_SIZE,
    build_roku_project,
    load_latest_saved_playlist,
)


def test_build_roku_project_packages_all_playlist_entries(tmp_path):
    entries = [
        {
            "title": f"Channel {index}",
            "url": f"https://streams.example/{index}.m3u8",
            "group": "News",
            "category": "live",
            "logo": "",
            "tvg_id": f"channel.{index}",
            "duration": "-1",
            "metadata": {"tvg_id": f"channel.{index}", "group_title": "News"},
            "stream_format": "hls",
        }
        for index in range(1, 4)
    ]
    project = tmp_path / "masterchief-tv-build"

    archive = build_roku_project(
        project,
        {
            "channel_name": "MasterChief TV",
            "bundle_id": "com.masterchief.tv",
            "theme": "dark",
            "render_url": "https://masterchief.example",
            "logo_text": "JBTV",
            "logo_color": "blue",
            "collection_order": ["Transporter", "XXX"],
            "web_app_url": "http://192.168.1.20:8080",
        },
        entries,
    )

    playlist_index = json.loads((project / "data" / "channels_index.json").read_text(encoding="utf-8"))
    packaged = []
    for shard_name in playlist_index["shards"]:
        packaged.extend(json.loads((project / "data" / shard_name).read_text(encoding="utf-8")))
    assert playlist_index["count"] == len(entries)
    assert packaged == entries
    with zipfile.ZipFile(archive) as package:
        zip_index = json.loads(package.read("data/channels_index.json"))
        packaged_entries = []
        for shard_name in zip_index["shards"]:
            packaged_entries.extend(json.loads(package.read(f"data/{shard_name}")))
        config = json.loads(package.read("data/app_config.json"))
        assert packaged_entries == entries
        assert "data/channels.json" not in package.namelist()
        assert config["render_url"] == "https://masterchief.example"
        assert config["logo_text"] == "JBTV"
        assert config["logo_color"] == "blue"
        assert config["collection_order"] == ["Transporter", "XXX"]
        assert config["web_app_url"] == "http://192.168.1.20:8080"
        focus_icon = Image.open(BytesIO(package.read("images/icon_focus_hd.png")))
        assert focus_icon.size == (336, 210)
        assert focus_icon.getpixel((168, 105)) == (31, 111, 235, 255)
        assert "components/IPTVPanel.xml" in package.namelist()
        assert "manifest" in package.namelist()
        panel = package.read("components/IPTVPanel.xml").decode("utf-8")
        ElementTree.fromstring(panel)
        main_scene = package.read("components/MainScene.xml").decode("utf-8-sig").replace("\r\n", "\n")
        assert '<IPTVPanel\n      id="iptvPanel"' in main_scene
        assert 'id="iptvPanel"\n      translation="[0, 0]"\n      visible="true"' in main_scene
        assert '<Video' in main_scene
        assert 'id="iptvPlayer"' in main_scene
        assert "components/HomePanel.xml" not in package.namelist()
        task = package.read("components/M3UTask.xml").decode("utf-8")
        assert "openSearchDialog" in panel
        assert "MasterChiefFavorites" in panel
        assert "EXTINF attributes" in panel
        assert 'm.groups = ["About Me", "Web Tools Links", "Search", "All Channels", "Favorites"]' in panel
        assert '"XXX"' in panel
        assert '"Jackie Chan Films"' in panel
        assert '"Transporter"' in panel
        assert '"Two and a Half Men"' in panel
        assert "isAdultChannel(channel, text)" in panel
        assert 'if channelGroup = "movies" or channelCategory = "movies" then return false' in panel
        for adult_term in (
            'Instr(1, channel.name, "XXX")',
            'Instr(1, lowerText, "big ass")',
            'Instr(1, lowerText, "blow job")',
            'Instr(1, lowerText, "big tits")',
            'word = "milf"',
            'word = "anal"',
            'word = "blondes"',
            'word = "brunettes"',
            'word = "babes"',
            'word = "hustler"',
        ):
            assert adult_term in panel
        assert "isJackieChanFilm(text)" in panel
        assert '"police story"' in panel
        assert 'Instr(1, text, "transporter")' in panel
        assert "two and a half men" in panel
        assert "openAboutMe()" in panel
        assert "MASTERCHIEF - ECHO STARLITE" in panel
        assert "JOEY BALLZ" in panel
        assert "ReadAsciiFile(\"pkg:/data/app_config.json\")" in panel
        assert "m.visibleCollectionNames = configuredCollections" in panel
        assert '"Batman"' in panel
        assert '"The Big Bang Theory"' in panel
        assert '"Curb Your Enthusiasm"' in panel
        assert '"BBC Earth"' in panel
        assert '"24/7 Channels"' in panel
        assert '"HBO"' in panel
        assert '"CINEMAX"' in panel
        assert '"SHOWTIME"' in panel
        assert '"STARZ"' in panel
        assert '"NETFLIX"' in panel
        assert '"NEWS CHANNELS"' in panel
        assert "isNewsChannel(channel, text)" in panel
        for sport_collection in (
            '"Sports"',
            '"UFC"',
            '"WWE"',
            '"Boxing"',
            '"NFL"',
            '"NBA"',
            '"MLB"',
            '"NHL"',
            '"Soccer"',
            '"Motorsports"',
            '"Tennis"',
            '"Cricket"',
            '"Rugby"',
            '"Golf"',
            '"Olympics"',
        ):
            assert sport_collection in panel
        assert "addSportsCollections(channel, text)" in panel
        assert 'tokens.DoesExist("ufc")' in panel
        assert 'tokens.DoesExist("nfl")' in panel
        assert 'tokens.DoesExist("nba")' in panel
        assert 'tokens.DoesExist("soccer")' in panel
        assert '"Web Tools Links"' in panel
        assert 'path: "/web_ide"' in panel
        assert 'path: "/tf_wizard"' in panel
        assert 'path: "/arm_creator"' in panel
        assert 'path: "/masterchief_code_ui"' in panel
        assert "Roku cannot display the full pages." in panel
        assert "isTolkienMovie" in panel
        assert "prioritized = []" in panel
        assert "playbackFormatRank(ch)" in panel
        assert 'if format = "hls" then return 0' in panel
        assert 'if format = "mp2ts" then return 1' in panel
        assert 'if format = "mp4" then return 2' in panel
        assert 'Instr(1, title, "lord of the rings")' in panel
        assert 'Instr(1, title, "lotr")' not in panel
        assert "channel.metadata = item.metadata" in task
        assert 'poster.uri = s.logo' in panel
        assert 'poster = m.streamList.createChild("Poster")' in panel
        assert "tvg_genre" in panel
        assert 'genreText = " | Genre=" + genre' in panel
        assert "channel.search_text = buildSearchText(channel)" in panel
        assert "candidates = m.channelsByGroup[g]" in panel
        assert "return Instr(1, channel.search_text, m.searchQuery) > 0" in panel
        assert "m.favoriteCount = m.favoritesChannels.count()" in panel
        assert "m.channelsByPrefix[prefix].push(channel)" in panel
        assert "bestPrefix = Left(word, 3)" in panel
        assert "searchCandidates(m.searchQuery)" in panel
        assert "m.smartCollections[collectionName] = []" in panel
        assert "Play toggles Favorite" in panel
        assert 'dialog.buttons = ["Search channels", "Lord of the Rings"' in panel
        player = package.read("components/MainScene.brs").decode("utf-8")
        assert 'm.currentStreamFormat = "hls" or m.currentStreamFormat = "mp2ts"' in player
        assert "Auto-scanning with " in player
        assert "Both HLS and TS playback attempts failed" in player
        task_text = task
        assert 'ReadAsciiFile("pkg:/data/channels_index.json")' in task_text
        assert "sendChannelsBatch(channels)" in task_text
        assert 'm.task.observeField("batchIndex", "onData")' in panel
        assert 'm.task.batchAck = batchIndex' in panel
        assert 'Instr(1, normalized, "output=mp2ts")' in task_text


def test_build_roku_project_splits_large_playlists_into_small_shards(tmp_path):
    entries = [
        {"title": f"Channel {index}", "url": f"https://streams.example/{index}.m3u8"}
        for index in range(ROKU_PLAYLIST_SHARD_SIZE + 1)
    ]

    archive = build_roku_project(
        tmp_path / "sharded-build",
        {
            "channel_name": "MasterChief TV",
            "bundle_id": "com.masterchief.tv",
            "theme": "dark",
        },
        entries,
    )

    index = json.loads((tmp_path / "sharded-build" / "data" / "channels_index.json").read_text())
    assert index["count"] == len(entries)
    assert len(index["shards"]) == 2
    shard_sizes = [
        len(json.loads((tmp_path / "sharded-build" / "data" / name).read_text()))
        for name in index["shards"]
    ]
    assert shard_sizes == [ROKU_PLAYLIST_SHARD_SIZE, 1]
    with zipfile.ZipFile(archive) as package:
        assert json.loads(package.read("data/channels_index.json"))["shards"] == index["shards"]
        assert sum(
            len(json.loads(package.read(f"data/{name}")))
            for name in index["shards"]
        ) == len(entries)


def test_load_latest_saved_playlist_skips_empty_or_invalid_builds(tmp_path):
    older_data = tmp_path / "older" / "data"
    newer_data = tmp_path / "newer" / "data"
    older_data.mkdir(parents=True)
    newer_data.mkdir(parents=True)
    older_data.joinpath("channels.json").write_text(
        json.dumps([{"title": "Saved Channel", "url": "https://streams.example/live.m3u8"}])
    )
    newer_data.joinpath("channels.json").write_text("[]")

    loaded = load_latest_saved_playlist(tmp_path)

    assert len(loaded) == 1
    assert loaded[0]["title"] == "Saved Channel"


def test_build_roku_project_rejects_empty_playlists(tmp_path):
    with pytest.raises(ValueError, match="at least one playable playlist channel"):
        build_roku_project(
            tmp_path / "empty-build",
            {
                "channel_name": "MasterChief TV",
                "bundle_id": "com.masterchief.tv",
                "theme": "dark",
            },
            [],
        )


@pytest.mark.parametrize(
    "render_url",
    [
        "http://masterchief.example",
        "https://user:password@masterchief.example",
        "https://masterchief.example/?token=secret",
    ],
)
def test_build_roku_project_rejects_unsafe_render_urls(tmp_path, render_url):
    with pytest.raises(ValueError, match="HTTPS base URL"):
        build_roku_project(
            tmp_path / "invalid-build",
            {
                "channel_name": "MasterChief TV",
                "bundle_id": "com.masterchief.tv",
                "theme": "dark",
                "render_url": render_url,
            },
            [],
        )


@pytest.mark.parametrize(
    "web_app_url",
    [
        "ftp://masterchief.example",
        "http://localhost:8080",
        "https://masterchief.example/web_ide",
        "https://user:password@masterchief.example",
        "https://masterchief.example/?token=secret",
    ],
)
def test_build_roku_project_rejects_unreachable_or_non_base_web_app_urls(
    tmp_path, web_app_url
):
    with pytest.raises(ValueError, match="Web app URL must be an HTTP"):
        build_roku_project(
            tmp_path / "invalid-build",
            {
                "channel_name": "MasterChief TV",
                "bundle_id": "com.masterchief.tv",
                "theme": "dark",
                "web_app_url": web_app_url,
            },
            [],
        )
