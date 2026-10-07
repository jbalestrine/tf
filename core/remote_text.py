"""Authentication helpers for inbound Twilio text-command webhooks."""

import base64
import hashlib
import hmac
from collections import defaultdict
from collections.abc import Iterable


def twilio_signature(url: str, form_values: Iterable[tuple[str, str]], auth_token: str) -> str:
    """Compute Twilio's X-Twilio-Signature for a form-encoded request."""
    values_by_key: dict[str, list[str]] = defaultdict(list)
    for key, value in form_values:
        values_by_key[str(key)].append(str(value))

    signed_data = [url]
    for key in sorted(values_by_key):
        signed_data.append(key)
        signed_data.extend(sorted(values_by_key[key]))

    digest = hmac.new(
        auth_token.encode('utf-8'),
        ''.join(signed_data).encode('utf-8'),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode('ascii')


def verify_twilio_signature(
    url: str,
    form_values: Iterable[tuple[str, str]],
    auth_token: str,
    supplied_signature: str,
) -> bool:
    if not auth_token or not supplied_signature:
        return False
    expected = twilio_signature(url, form_values, auth_token)
    return hmac.compare_digest(expected, supplied_signature)


def is_allowed_sender(sender: str, configured_senders: Iterable[str]) -> bool:
    normalized_sender = (sender or '').strip()
    if not normalized_sender:
        return False
    return any(normalized_sender == (allowed or '').strip() for allowed in configured_senders)


def is_twilio_enabled(
    enabled_flag: str,
    auth_token: str,
    webhook_url: str,
    allowed_senders: str,
) -> bool:
    return bool(
        (enabled_flag or '').strip().casefold() in {'1', 'true', 'yes', 'on'}
        and (auth_token or '').strip()
        and (webhook_url or '').strip()
        and any(number.strip() for number in (allowed_senders or '').split(','))
    )
