from core.remote_text import (
    is_allowed_sender,
    is_twilio_enabled,
    twilio_signature,
    verify_twilio_signature,
)


def test_twilio_signature_verifies_form_parameters():
    url = 'https://example.test/api/echo/remote/twilio'
    form = [('Body', '!status'), ('From', '+15551234567')]
    signature = twilio_signature(url, form, 'test-auth-token')

    assert verify_twilio_signature(url, form, 'test-auth-token', signature)
    assert not verify_twilio_signature(url, form, 'wrong-token', signature)
    assert not verify_twilio_signature(url, form, 'test-auth-token', '')


def test_twilio_signature_parameter_order_is_irrelevant():
    url = 'https://example.test/api/echo/remote/twilio'
    form = [('From', '+15551234567'), ('Body', '!status')]
    signature = twilio_signature(url, form, 'test-auth-token')

    assert verify_twilio_signature(url, reversed(form), 'test-auth-token', signature)


def test_sender_allowlist_uses_exact_e164_match():
    assert is_allowed_sender('+15551234567', ['+15551234567'])
    assert not is_allowed_sender('+15551234567', ['+15551234568'])
    assert not is_allowed_sender('', ['+15551234567'])


def test_twilio_commands_are_opt_in_and_require_every_setting():
    assert not is_twilio_enabled('', 'token', 'https://echo.test/hook', '+15551234567')
    assert not is_twilio_enabled('true', '', 'https://echo.test/hook', '+15551234567')
    assert not is_twilio_enabled('true', 'token', '', '+15551234567')
    assert not is_twilio_enabled('true', 'token', 'https://echo.test/hook', '')
    assert is_twilio_enabled('true', 'token', 'https://echo.test/hook', '+15551234567')
