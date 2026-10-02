sub init()
    m.player = m.top.findNode("iptvPlayer")
    
    ' Set up your stream configuration block
    streamData = CreateObject("roSGNode", "ContentNode")
    streamData.url = "http://1tv41.icu:8080/get.php?username=3022207888&password=leonmatthews60@gmail.com&type=m3u" ' <-- Paste your live M3U8 link here
    streamData.streamFormat = "hls" ' <-- Use "hls" for typical IPTV live streams
    
    ' Assign data to player and trigger playback
    m.player.content = streamData
    m.player.control = "play"
    m.player.setFocus(true)
end sub
