sub init()
    m.iptvPanel = m.top.findNode("iptvPanel")
    m.player = m.top.findNode("iptvPlayer")
    
    ' Listen for clicks inside your custom IPTV item list
    if m.iptvPanel <> invalid
        m.iptvPanel.observeField("selectedChannel", "onChannelSelected")

        ' FIX: Call the public function directly on the node instead of callFunction()
        m.iptvPanel.load = true 
        m.iptvPanel.setFocus(true)
    end if
end sub


sub onChannelSelected(msg as Object)
    channel = msg.GetData()
    if channel <> invalid and channel.url <> ""
        streamData = CreateObject("roSGNode", "ContentNode")
        streamData.url = channel.url
        streamData.streamFormat = "hls"
        streamData.title = channel.name
        
        ' Swap panel visibility parameters
        m.iptvPanel.visible = false
        m.player.visible = true
        
        m.player.content = streamData
        m.player.control = "play"
        m.player.setFocus(true)
    end if
end sub

' Remote navigation key catcher
function onKeyEvent(key as String, press as Boolean) as Boolean
    if not press then return false
    
    if key = "back" and m.player.visible = true
        ' Kill stream and restore panel selection lists
        m.player.control = "stop"
        m.player.visible = false
        m.iptvPanel.visible = true
        m.iptvPanel.setFocus(true)
        return true
    end if
    
    return false
end function
