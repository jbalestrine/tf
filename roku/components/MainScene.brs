sub init()
    m.iptvPanel = m.top.findNode("iptvPanel")
    m.player = m.top.findNode("iptvPlayer")
    m.channelPreview = m.top.findNode("channelPreview")
    m.channelPreviewBackground = m.top.findNode("channelPreviewBackground")
    m.channelPreviewLabel = m.top.findNode("channelPreviewLabel")
    m.playerStatusBackground = m.top.findNode("playerStatusBackground")
    m.playerStatus = m.top.findNode("playerStatus")
    m.currentChannel = invalid
    m.currentStreamFormat = ""
    m.fallbackAttempted = false

    if m.iptvPanel <> invalid
        m.iptvPanel.observeField("selectedChannel", "onChannelSelected")
        m.iptvPanel.observeField("previewChannel", "onPreviewChannelChanged")
        m.iptvPanel.callFunc("load", invalid)
        m.iptvPanel.setFocus(true)
    end if
    if m.player <> invalid
        m.player.observeField("state", "onPlayerStateChanged")
    end if
end sub

sub onPreviewChannelChanged(msg as Object)
    channel = msg.GetData()
    if channel = invalid or channel.url = "" or m.player.visible then return
    streamFormat = channel.stream_format
    if streamFormat = invalid or streamFormat = "" then streamFormat = inferStreamFormat(channel.url)
    if streamFormat = "unsupported" then
        m.channelPreview.control = "stop"
        m.channelPreview.visible = false
        m.channelPreviewBackground.visible = false
        m.channelPreviewLabel.visible = false
        return
    end if
    preview = CreateObject("roSGNode", "ContentNode")
    preview.url = channel.url
    preview.streamFormat = streamFormat
    preview.title = channel.name
    if channel.http_headers <> invalid and type(channel.http_headers) = "roAssociativeArray"
        preview.httpHeaders = channel.http_headers
    end if
    m.channelPreview.content = preview
    m.channelPreview.control = "play"
    m.channelPreview.visible = true
    m.channelPreviewBackground.visible = true
    m.channelPreviewLabel.visible = true
    m.channelPreviewLabel.text = "PREVIEW: " + channel.name
end sub

sub onChannelSelected(msg as Object)
    channel = msg.GetData()
    if channel = invalid or channel.url = "" then return

    streamFormat = channel.stream_format
    if streamFormat = invalid or streamFormat = "" then
        streamFormat = inferStreamFormat(channel.url)
    end if
    if streamFormat = "unsupported"
        showPlayerStatus("Roku cannot play this file type. Choose an HLS (.m3u8), transport-stream (.ts), MP4, or MKV entry.")
        return
    end if

    m.currentChannel = channel
    m.currentStreamFormat = streamFormat
    m.fallbackAttempted = false
    m.channelPreview.control = "stop"
    m.channelPreview.visible = false
    m.channelPreviewBackground.visible = false
    m.channelPreviewLabel.visible = false
    m.playerStatusBackground.visible = false
    m.iptvPanel.visible = false
    m.player.visible = true
    startChannelPlayback(streamFormat)
    m.player.setFocus(true)
end sub

sub startChannelPlayback(streamFormat as String)
    streamData = CreateObject("roSGNode", "ContentNode")
    streamData.url = m.currentChannel.url
    streamData.streamFormat = streamFormat
    streamData.title = m.currentChannel.name
    if m.currentChannel.http_headers <> invalid and type(m.currentChannel.http_headers) = "roAssociativeArray"
        streamData.httpHeaders = m.currentChannel.http_headers
    end if
    m.currentStreamFormat = streamFormat
    showPlayerStatus("Trying playback as " + UCase(streamFormat) + "...")
    m.player.content = streamData
    m.player.control = "play"
end sub

sub onPlayerStateChanged()
    state = m.player.state
    if state = "playing"
        m.playerStatusBackground.visible = false
        return
    end if
    if state <> "error" then return

    if not m.fallbackAttempted and (m.currentStreamFormat = "hls" or m.currentStreamFormat = "mp2ts")
        m.fallbackAttempted = true
        if m.currentStreamFormat = "hls"
            alternateFormat = "mp2ts"
        else
            alternateFormat = "hls"
        end if
        showPlayerStatus(UCase(m.currentStreamFormat) + " failed. Auto-scanning with " + UCase(alternateFormat) + "...")
        startChannelPlayback(alternateFormat)
        return
    end if

    detail = "Roku playback failed"
    if m.fallbackAttempted then detail = "Both HLS and TS playback attempts failed"
    code = m.player.errorCode
    if code <> invalid then detail = detail + " (error " + stri(code).trim() + ")"
    showPlayerStatus(detail + ". Check the stream format, codec support, or provider headers.")
end sub

sub showPlayerStatus(message as String)
    m.playerStatus.text = message
    m.playerStatusBackground.visible = true
end sub

function inferStreamFormat(url as String) as String
    normalized = LCase(url)
    if Instr(1, normalized, "output=ts") > 0 or Instr(1, normalized, "format=ts") > 0 or
        Instr(1, normalized, "output=mp2ts") > 0 or Instr(1, normalized, "format=mp2ts") > 0 or
        Instr(1, normalized, "container=mp2ts") > 0 or Instr(1, normalized, "stream_format=mp2ts") > 0
        return "mp2ts"
    end if
    if Instr(1, normalized, "output=m3u8") > 0 or Instr(1, normalized, "format=hls") > 0 or
        Instr(1, normalized, "output=hls") > 0 or Instr(1, normalized, "container=m3u8") > 0 or
        Instr(1, normalized, "stream_format=hls") > 0
        return "hls"
    end if
    queryStart = Instr(1, normalized, "?")
    if queryStart > 0 then normalized = Left(normalized, queryStart - 1)
    fragmentStart = Instr(1, normalized, "#")
    if fragmentStart > 0 then normalized = Left(normalized, fragmentStart - 1)
    if Right(normalized, 5) = ".m3u8" then return "hls"
    if Right(normalized, 3) = ".ts" then return "mp2ts"
    if Right(normalized, 4) = ".mp4" or Right(normalized, 4) = ".m4v" then return "mp4"
    if Right(normalized, 4) = ".mkv" then return "mkv"
    if Right(normalized, 4) = ".mov" then return "mov"
    if Right(normalized, 4) = ".mp3" then return "mp3"
    if Right(normalized, 4) = ".mpd" then return "dash"
    if Right(normalized, 4) = ".avi" or Right(normalized, 4) = ".m3u" then return "unsupported"
    return "hls"
end function

function onKeyEvent(key as String, press as Boolean) as Boolean
    if not press then return false
    if key = "back" and m.player.visible = true
        m.player.control = "stop"
        m.player.visible = false
        m.playerStatusBackground.visible = false
        m.iptvPanel.visible = true
        m.iptvPanel.setFocus(true)
        return true
    end if
    return false
end function
