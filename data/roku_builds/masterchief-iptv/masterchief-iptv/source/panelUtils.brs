' ============================================================
'  panelUtils.brs - shared helpers included by all panels
' ============================================================

' Map a status string to a colour
function statusColor(s as String) as String
    sl = LCase(s)
    if sl = "running" or sl = "active" or sl = "healthy" or sl = "ok" or sl = "success" or sl = "passed" or sl = "connected" or sl = "ready" or sl = "loaded"
        return "0x3FB950FF"   ' green
    else if sl = "failed" or sl = "error" or sl = "unhealthy" or sl = "critical" or sl = "disconnected"
        return "0xF85149FF"   ' red
    else if sl = "pending" or sl = "queued" or sl = "warning" or sl = "degraded" or sl = "loading" or sl = "initializing" or sl = "waiting"
        return "0xD29922FF"   ' yellow
    else
        return "0x8B949EFF"   ' subtext grey
    end if
end function

' Safely get a string from an assocarray
function safeStr(aa as Dynamic, key as String, fallback = "" as String) as String
    if type(aa) = "roAssociativeArray" and aa.doesExist(key)
        v = aa[key]
        if v = invalid then return fallback
        if type(v) = "roString" or type(v) = "String" then return v
        return str(v).trim()
    end if
    return fallback
end function

' Format epoch seconds as HH:MM MM/DD
function formatTs(ts as Dynamic) as String
    if ts = invalid or ts = "" then return ""
    n = val(str(ts).trim())
    if n <= 0 then return str(ts).trim()
    dt = CreateObject("roDateTime")
    dt.FromISO8601String(str(n))
    dt.ToLocalTime()
    return rp(dt.GetHours()) + ":" + rp(dt.GetMinutes()) + " " + str(dt.GetMonth()).trim() + "/" + str(dt.GetDayOfMonth()).trim()
end function

function rp(n as Integer) as String
    s = str(n).trim()
    if len(s) = 1 then s = "0" + s
    return s
end function
