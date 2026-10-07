"""Opt-in, TLS-only IRC bridge for Echo with private-message TOTP startup auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

logger = logging.getLogger("echo.irc_bridge")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PORT_NUMBER = re.compile(r"^\d{1,5}$")


class IRCBridgeError(RuntimeError):
    """Raised when IRC bridge configuration or a requested operation is invalid."""


@dataclass(frozen=True)
class IRCBridgeConfig:
    server: str
    port: int
    nickname: str
    channels: tuple[str, ...]
    totp_secret: str
    app_port: int
    echo_url: str

    @classmethod
    def from_env(cls) -> "IRCBridgeConfig":
        if os.environ.get("ECHO_ENABLE_IRC", "").strip() != "1":
            raise IRCBridgeError("IRC bridge is disabled. Set ECHO_ENABLE_IRC=1 to opt in.")
        server = os.environ.get("ECHO_IRC_SERVER", "irc.dal.net").strip()
        nickname = os.environ.get("ECHO_IRC_NICK", "MasterChiefEcho").strip()
        channels = tuple(
            channel.strip()
            for channel in os.environ.get("ECHO_IRC_CHANNELS", "").split(",")
            if channel.strip().startswith("#")
        )
        port_text = os.environ.get("ECHO_IRC_PORT", "6697").strip()
        app_port_text = os.environ.get("ECHO_IRC_APP_PORT", "8080").strip()
        if not server or not nickname or not _PORT_NUMBER.fullmatch(port_text):
            raise IRCBridgeError("Set a valid ECHO_IRC_SERVER, ECHO_IRC_NICK, and numeric ECHO_IRC_PORT.")
        if not _PORT_NUMBER.fullmatch(app_port_text) or not 1 <= int(app_port_text) <= 65535:
            raise IRCBridgeError("ECHO_IRC_APP_PORT must be a TCP port from 1 to 65535.")
        if not 1 <= int(port_text) <= 65535:
            raise IRCBridgeError("ECHO_IRC_PORT must be a TCP port from 1 to 65535.")
        secret = os.environ.get("ECHO_IRC_TOTP_SECRET", "").strip()
        try:
            decoded_secret = _decode_totp_secret(secret)
        except (ValueError, base64.binascii.Error) as exc:
            raise IRCBridgeError(
                "Set ECHO_IRC_TOTP_SECRET to a Base32 TOTP secret (at least 20 decoded bytes)."
            ) from exc
        if len(decoded_secret) < 20:
            raise IRCBridgeError("ECHO_IRC_TOTP_SECRET must decode to at least 20 bytes.")
        return cls(
            server=server,
            port=int(port_text),
            nickname=nickname,
            channels=channels,
            totp_secret=secret,
            app_port=int(app_port_text),
            echo_url=f"http://127.0.0.1:{int(app_port_text)}",
        )


def _decode_totp_secret(secret: str) -> bytes:
    normalized = secret.replace(" ", "").upper()
    normalized += "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized, casefold=True)


def totp_code(secret: str, timestamp: float | None = None) -> tuple[str, int]:
    """Return the RFC 6238 six-digit SHA-1 code and its time counter."""
    counter = int((timestamp if timestamp is not None else time.time()) // 30)
    digest = hmac.new(_decode_totp_secret(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % 1_000_000:06d}", counter


def verify_totp(secret: str, supplied_code: str, timestamp: float | None = None) -> int | None:
    """Accept a current or adjacent 30-second TOTP window."""
    if not re.fullmatch(r"\d{6}", supplied_code):
        return None
    now = timestamp if timestamp is not None else time.time()
    for delta in (-1, 0, 1):
        code, counter = totp_code(secret, now + delta * 30)
        if hmac.compare_digest(code, supplied_code):
            return counter
    return None


def parse_privmsg(line: str) -> tuple[str, str, str] | None:
    """Parse an IRC PRIVMSG into (nick, target, text), ignoring unrelated frames."""
    if not line.startswith(":") or " PRIVMSG " not in line:
        return None
    prefix, remainder = line[1:].split(" ", 1)
    nick = prefix.split("!", 1)[0]
    command, separator, trailing = remainder.partition(" :")
    parts = command.split()
    if not separator or len(parts) != 2 or parts[0] != "PRIVMSG":
        return None
    return nick, parts[1], trailing


def _is_tcp_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _is_masterchief_running(base_url: str) -> bool:
    request = urllib.request.Request(f"{base_url}/echo-chat", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            body = response.read(8192).decode("utf-8", errors="replace").casefold()
            return response.status == 200 and ("echo" in body or "masterchief" in body)
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def start_masterchief(port: int) -> tuple[bool, str]:
    """Start only the known local Flask entry point, bound to loopback."""
    base_url = f"http://127.0.0.1:{port}"
    if _is_masterchief_running(base_url):
        return True, f"MasterChief is already running at {base_url}."
    if _is_tcp_port_open(port):
        return False, f"Port {port} is occupied by another service; refusing to start on a different port."

    log_path = PROJECT_ROOT / "data" / "logs" / "echo_irc_app.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle: TextIO = log_path.open("a", encoding="utf-8")
        creationflags = 0
        popen_options: dict[str, object] = {}
        if os.name == "nt":
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
            )
        else:
            popen_options["start_new_session"] = True
        subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "main.py"), "--port", str(port), "--host", "127.0.0.1"],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            **popen_options,
        )
        log_handle.close()
    except OSError as exc:
        logger.exception("Could not launch the local MasterChief server")
        return False, f"Could not start MasterChief: {exc}"

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _is_masterchief_running(base_url):
            return True, f"MasterChief started at {base_url} (loopback only)."
        time.sleep(0.5)
    return False, f"MasterChief did not become ready. Check {log_path}."


def _irc_line_parts(line: str) -> tuple[str, list[str], str | None]:
    prefix = ""
    if line.startswith(":"):
        prefix, _, line = line[1:].partition(" ")
    command, separator, rest = line.partition(" ")
    params: list[str] = []
    trailing = None
    while separator and rest:
        if rest.startswith(":"):
            trailing = rest[1:]
            break
        part, separator, rest = rest.partition(" ")
        params.append(part)
    return prefix, [command, *params], trailing


class IRCBridge:
    """TLS IRC client. Privileged commands are accepted only in private messages."""

    def __init__(self, config: IRCBridgeConfig):
        self.config = config
        self._socket: ssl.SSLSocket | None = None
        self._authenticated: dict[str, float] = {}
        self._last_accepted_totp_step = -1
        self._failed_attempts: dict[str, list[float]] = {}
        self._last_chat: dict[str, float] = {}
        self._last_team: dict[str, float] = {}

    def _send(self, line: str) -> None:
        if self._socket is None:
            raise IRCBridgeError("IRC connection is not active.")
        if "\r" in line or "\n" in line:
            raise IRCBridgeError("IRC frame contains a line break.")
        self._socket.sendall((line + "\r\n").encode("utf-8"))

    def _reply(self, target: str, message: str) -> None:
        encoded = message.encode("utf-8")
        if len(encoded) > 1400:
            encoded = encoded[:1150]
            message = encoded.decode("utf-8", errors="ignore") + " [truncated]"
        encoded = message.encode("utf-8")
        chunks: list[str] = []
        while encoded:
            chunk = encoded[:350]
            while chunk:
                try:
                    decoded = chunk.decode("utf-8")
                    break
                except UnicodeDecodeError:
                    chunk = chunk[:-1]
            if not chunk:
                break
            chunks.append(decoded)
            encoded = encoded[len(chunk):]
        for chunk in chunks:
            self._send(f"PRIVMSG {target} :{chunk}")

    def _is_private_target(self, target: str) -> bool:
        return target.casefold() == self.config.nickname.casefold()

    def _authorized(self, nick: str) -> bool:
        return self._authenticated.get(nick.casefold(), 0) > time.time()

    def _authenticate_and_start(self, nick: str, target: str, supplied_code: str) -> None:
        nick_key = nick.casefold()
        now = time.time()
        if not self._is_private_target(target):
            self._reply(nick, "For safety, authenticate only in a private message to this bot.")
            return
        failed = [attempt for attempt in self._failed_attempts.get(nick_key, []) if now - attempt < 300]
        self._failed_attempts[nick_key] = failed
        if len(failed) >= 5:
            self._reply(nick, "Authentication temporarily locked after repeated failures. Try again in five minutes.")
            return
        counter = verify_totp(self.config.totp_secret, supplied_code, now)
        if counter is None or counter <= self._last_accepted_totp_step:
            failed.append(now)
            self._failed_attempts[nick_key] = failed
            self._reply(nick, "Authentication failed. Use the current six-digit authenticator code in a private message.")
            return

        self._last_accepted_totp_step = counter
        self._failed_attempts.pop(nick_key, None)
        self._authenticated = {
            user: expiry for user, expiry in self._authenticated.items() if expiry > now
        }
        if len(self._authenticated) >= 100:
            self._reply(nick, "Too many active IRC operator sessions; try again later.")
            return
        self._authenticated[nick_key] = now + 900
        ok, status = start_masterchief(self.config.app_port)
        self._reply(nick, status if ok else f"Authenticated, but startup failed: {status}")

    def _chat(self, nick: str, target: str, prompt: str, *, team: bool = False) -> None:
        nick_key = nick.casefold()
        if team and (not self._is_private_target(target) or not self._authorized(nick)):
            self._reply(nick, "Model-team requests require private-message operator authentication with !masterchief.")
            return
        now = time.time()
        cooldowns = self._last_team if team else self._last_chat
        cooldown = 10 if team else 3
        if now - cooldowns.get(nick_key, 0) < cooldown:
            self._reply(target, f"Please wait {cooldown} seconds between {'team' if team else 'chat'} requests.")
            return
        cooldowns[nick_key] = now

        if team:
            try:
                from addons.echo_model_team.addon import run_team_chat
                result = run_team_chat(prompt)
                response = f"{result['response']} [candidate {result['candidate_id']}]"
            except Exception as exc:
                logger.exception("Local Echo model-team request failed")
                response = f"Model team unavailable: {exc}"
            self._reply(target, response)
            return

        session_id = "irc_" + hashlib.sha256(nick_key.encode("utf-8")).hexdigest()[:20]
        body = json.dumps({"message": prompt, "session_id": session_id}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.echo_url}/api/echo/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
            reply = data.get("response")
            if not isinstance(reply, str) or not reply.strip():
                raise IRCBridgeError("Echo returned an empty response.")
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, IRCBridgeError) as exc:
            logger.exception("Echo IRC chat request failed")
            reply = f"Echo is unavailable: {exc}"
        self._reply(target, reply.strip())

    def handle_line(self, line: str) -> None:
        if line.startswith("PING "):
            token = line.partition(" ")[2]
            self._send(f"PONG {token}")
            return
        parsed = parse_privmsg(line)
        if parsed is None:
            prefix, parts, trailing = _irc_line_parts(line)
            if parts and parts[0] == "001":
                for channel in self.config.channels:
                    self._send(f"JOIN {channel}")
                logger.info("IRC bridge connected to %s as %s", self.config.server, self.config.nickname)
            return

        nick, target, text = parsed
        private = self._is_private_target(target)
        command = text.strip()
        parts = command.split(maxsplit=1)
        verb = parts[0].casefold() if parts else ""
        argument = parts[1].strip() if len(parts) > 1 else ""

        if verb in {"!masterchief", "!op"}:
            if not private:
                self._reply(nick, "Startup/authentication commands work only in a private message. Never post a code in a channel.")
            elif re.fullmatch(r"\d{6}", argument):
                self._authenticate_and_start(nick, target, argument)
            else:
                self._reply(nick, "Usage: !masterchief <current six-digit authenticator code>")
            return
        if verb == "!status":
            if not private:
                self._reply(nick, "Status is available in a private message.")
            else:
                running = _is_masterchief_running(self.config.echo_url)
                self._reply(nick, f"MasterChief {'running' if running else 'stopped'} at {self.config.echo_url}.")
            return
        if verb in {"!team", "!models"}:
            if not argument:
                self._reply(target, "Usage: !team <prompt> (private message, authenticated operator only)")
            else:
                self._chat(nick, target, argument, team=True)
            return

        if verb in {"/ai", "!ask"}:
            if argument:
                self._chat(nick, target, argument)
            else:
                self._reply(target, "Usage: /ai <message>")
            return
        if text.startswith("/ai "):
            self._chat(nick, target, text[4:].strip())

    def run_forever(self) -> None:
        context = ssl.create_default_context()
        while True:
            try:
                raw_socket = socket.create_connection((self.config.server, self.config.port), timeout=15)
                self._socket = context.wrap_socket(raw_socket, server_hostname=self.config.server)
                self._send(f"NICK {self.config.nickname}")
                self._send(f"USER {self.config.nickname} 0 * :Echo Chat IRC bridge")
                reader = self._socket.makefile("r", encoding="utf-8", errors="replace", newline="\r\n")
                for line in reader:
                    self.handle_line(line.rstrip("\r\n"))
            except (OSError, ssl.SSLError, IRCBridgeError):
                logger.exception("IRC bridge disconnected; retrying")
            finally:
                if self._socket is not None:
                    try:
                        self._socket.close()
                    except OSError:
                        logger.exception("Could not close IRC socket")
                    self._socket = None
            time.sleep(5)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = IRCBridgeConfig.from_env()
    logger.info("Starting TLS IRC bridge for %s; channels=%s", config.nickname, ",".join(config.channels) or "(DM only)")
    IRCBridge(config).run_forever()


if __name__ == "__main__":
    main()
