import base64

from core.irc_bridge import (
    IRCBridge,
    IRCBridgeConfig,
    parse_privmsg,
    totp_code,
    verify_totp,
)


def test_totp_accepts_current_code_and_rejects_invalid_code():
    secret = base64.b32encode(b"0123456789abcdefghij").decode("ascii").rstrip("=")
    code, counter = totp_code(secret, timestamp=1_700_000_000)

    assert verify_totp(secret, code, timestamp=1_700_000_000) == counter
    assert verify_totp(secret, "not-a-code", timestamp=1_700_000_000) is None
    assert verify_totp(secret, "000000", timestamp=1_700_000_000) is None


def test_privmsg_parser_preserves_colons_in_the_message():
    assert parse_privmsg(":alice!u@host PRIVMSG EchoBot :/ai hello: world") == (
        "alice",
        "EchoBot",
        "/ai hello: world",
    )
    assert parse_privmsg("PING :irc.example") is None


def test_masterchief_auth_command_is_rejected_in_public_channels(monkeypatch):
    bridge = IRCBridge(IRCBridgeConfig(
        server="irc.example",
        port=6697,
        nickname="EchoBot",
        channels=("#test",),
        totp_secret="JBSWY3DPEHPK3PXP",
        app_port=8080,
        echo_url="http://127.0.0.1:8080",
    ))
    sent = []
    monkeypatch.setattr(bridge, "_send", sent.append)

    bridge.handle_line(":alice!u@host PRIVMSG #test :!masterchief 123456")

    assert sent == ["PRIVMSG alice :Startup/authentication commands work only in a private message. Never post a code in a channel."]


def test_private_masterchief_auth_starts_once_and_prevents_totp_replay(monkeypatch):
    secret = base64.b32encode(b"0123456789abcdefghij").decode("ascii").rstrip("=")
    now = 1_700_000_000
    code, _ = totp_code(secret, timestamp=now)
    bridge = IRCBridge(IRCBridgeConfig(
        server="irc.example",
        port=6697,
        nickname="EchoBot",
        channels=(),
        totp_secret=secret,
        app_port=8080,
        echo_url="http://127.0.0.1:8080",
    ))
    sent = []
    launches = []
    monkeypatch.setattr("core.irc_bridge.time.time", lambda: now)
    monkeypatch.setattr(bridge, "_send", sent.append)
    monkeypatch.setattr("core.irc_bridge.start_masterchief", lambda port: (launches.append(port) is None, "MasterChief started locally."))

    auth_command = f":alice!u@host PRIVMSG EchoBot :!masterchief {code}"
    bridge.handle_line(auth_command)
    bridge.handle_line(auth_command)

    assert launches == [8080]
    assert "MasterChief started locally." in sent[0]
    assert code not in sent[0]
    assert "Authentication failed" in sent[1]


def test_irc_bridge_is_opt_in(monkeypatch):
    monkeypatch.delenv("ECHO_ENABLE_IRC", raising=False)
    try:
        IRCBridgeConfig.from_env()
    except Exception as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("IRC bridge should require explicit opt-in")
