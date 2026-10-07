from core.roku_playlist import parse_m3u_playlist


def test_parse_m3u_playlist_keeps_entries_above_previous_50k_cap():
    entry_count = 75_001
    lines = []
    for index in range(entry_count):
        lines.append(f"#EXTINF:-1,Channel {index}")
        lines.append(f"https://streams.example/{index}.m3u8")

    entries = parse_m3u_playlist("\n".join(lines))

    assert len(entries) == entry_count
