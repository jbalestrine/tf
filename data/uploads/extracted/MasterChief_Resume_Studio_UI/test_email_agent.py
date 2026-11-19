import asyncio
import os
import smtplib
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

import app
import email_agent as agent


def message(sender="Recruiter <recruiter@example.com>", subject="Cloud architect",
            body="Company: Example\nRole: Cloud Architect\nHello", mid="<one@example.com>"):
    result = EmailMessage()
    result["From"] = sender
    result["Subject"] = subject
    result["Message-ID"] = mid
    result.set_content(body)
    return result


def request(method, path, client="127.0.0.1", host="localhost:8080", origin=None, extra=()):
    headers = [(b"host", host.encode()), (b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin.encode()))
    headers.extend(extra)
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "method": method, "scheme": "http", "path": path,
             "raw_path": path.encode(), "query_string": b"", "headers": headers,
             "server": ("localhost", 8080), "client": (client, 1234), "root_path": ""}
    messages = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": b"{}", "more_body": False}
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    async def send(value):
        messages.append(value)

    asyncio.run(app.app(scope, receive, send))
    return next(m["status"] for m in messages if m["type"] == "http.response.start")


class EmailAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = mock.patch.object(agent, "STATE", Path(self.tmp.name) / "processed_emails.json")
        self.state.start()
        self.addCleanup(self.state.stop)
        self.config = mock.patch.object(agent, "configuration", return_value={
            "GMAIL_ADDRESS": "owner@gmail.com", "GMAIL_APP_PASSWORD": "fake-password"})
        self.config.start()
        self.addCleanup(self.config.stop)

    def queued(self, email=None):
        item = agent.candidate(email or message(), "owner@gmail.com", ["architect", "devops"])
        agent.state_write({"messages": [item], "auto_send": None})
        return item

    def test_candidate_guards_and_unknown_details(self):
        for sender in ("no-reply@example.com", "noreply@example.com", "mailer-daemon@example.com",
                       "owner@gmail.com"):
            self.assertIsNone(agent.candidate(message(sender=sender), "owner@gmail.com", ["architect"]))
        for header, value in (("List-Unsubscribe", "<https://example.com>"),
                              ("Auto-Submitted", "auto-replied"), ("Precedence", "bulk")):
            email = message()
            email[header] = value
            self.assertIsNone(agent.candidate(email, "owner@gmail.com", ["architect"]))
        self.assertIsNone(agent.candidate(message(mid="invalid"), "owner@gmail.com", ["architect"]))
        self.assertIsNone(agent.candidate(message(subject="hello", body="ordinary text"), "owner@gmail.com", ["architect"]))
        result = agent.candidate(message(body="Hello"), "owner@gmail.com", ["architect"])
        self.assertEqual((result["company"], result["role_title"]), ("", ""))
        self.assertFalse(agent.auto_enabled({"auto_send": None}, {}))
        html = message(subject="Hello")
        html.set_content("<html><head><style>hidden</style></head><body><p>DevOps</p><p>Company: Example</p></body></html>", subtype="html")
        result = agent.candidate(html, "owner@gmail.com", ["devops"])
        self.assertEqual(result["company"], "Example")
        self.assertNotIn("hidden", result["snippet"])

    def test_scan_peek_deduplicates_and_queues(self):
        email = message()
        client = mock.MagicMock()
        client.__enter__.return_value = client
        client.select.return_value = ("OK", [])
        client.uid.side_effect = lambda operation, *args: (
            ("OK", [b"1"]) if operation == "search" else ("OK", [(b"header", email.as_bytes())]))
        with mock.patch.object(agent.imaplib, "IMAP4_SSL", return_value=client), mock.patch.object(agent, "send") as send:
            self.assertEqual(agent.scan_inbox()["added"], 1)
            self.assertEqual(agent.scan_inbox()["added"], 0)
            send.assert_not_called()
        client.select.assert_called_with("INBOX", readonly=True)
        client.uid.assert_any_call("fetch", b"1", "(BODY.PEEK[])")

    def test_send_builds_fresh_profile_attachments_and_crm(self):
        item = self.queued()
        smtp = mock.MagicMock()
        smtp.__enter__.return_value = smtp
        with mock.patch.object(agent.smtplib, "SMTP", return_value=smtp), \
                mock.patch.object(agent.studio_tools, "add_submission") as crm:
            result = agent.send(item["id"], "Example", "Cloud Architect")
        sent = smtp.send_message.call_args.args[0]
        self.assertEqual([part.get_filename() for part in sent.iter_attachments()],
                         [agent.EXEC, agent.PDF, "Cover_Letter.docx"])
        pdf = list(sent.iter_attachments())[1].get_payload(decode=True)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(result["crm_status"], "logged")
        self.assertEqual(crm.call_args.args[0].company, "Example")
        second = agent.candidate(message(mid="<two@example.com>"), "owner@gmail.com", ["architect"])
        state = agent.state_read()
        state["messages"].append(second)
        agent.state_write(state)
        with self.assertRaisesRegex(ValueError, "30 days"):
            agent.send(second["id"], "Example", "Cloud Architect")

    def test_unknown_role_and_uncertain_smtp_do_not_retry(self):
        item = self.queued()
        with self.assertRaisesRegex(ValueError, "Role must"):
            agent.send(item["id"], "Example", "Data Analyst")
        smtp = mock.MagicMock()
        smtp.__enter__.return_value = smtp
        smtp.send_message.side_effect = smtplib.SMTPException("mock failure")
        with mock.patch.object(agent.smtplib, "SMTP", return_value=smtp):
            with self.assertRaisesRegex(ValueError, "could not be confirmed"):
                agent.send(item["id"], "Example", "DevOps Engineer")
            with self.assertRaisesRegex(ValueError, "no longer awaiting"):
                agent.send(item["id"], "Example", "DevOps Engineer")
        self.assertEqual(agent.state_read()["messages"][0]["status"], "uncertain")
        self.assertEqual(smtp.send_message.call_count, 1)

    def test_crm_failure_does_not_resend(self):
        item = self.queued()
        smtp = mock.MagicMock()
        smtp.__enter__.return_value = smtp
        with mock.patch.object(agent.smtplib, "SMTP", return_value=smtp), \
                mock.patch.object(agent.studio_tools, "add_submission", side_effect=OSError("mock")):
            with self.assertRaisesRegex(ValueError, "CRM logging failed"):
                agent.send(item["id"], "Example", "SRE")
        self.assertEqual(agent.state_read()["messages"][0]["crm_status"], "pending")
        self.assertEqual(agent.state_read()["messages"][0]["status"], "sent")

    def test_auto_send_requires_explicit_details(self):
        client = mock.MagicMock()
        client.__enter__.return_value = client
        client.select.return_value = ("OK", [])
        client.uid.side_effect = lambda operation, *args: (
            ("OK", [b"1 2"]) if operation == "search" else
            ("OK", [(b"header", (message() if args[0] == b"1" else
                                  message(body="hello", mid="<two@example.com>")).as_bytes())]))
        agent.state_write({"messages": [], "auto_send": True})
        with mock.patch.object(agent.imaplib, "IMAP4_SSL", return_value=client), mock.patch.object(agent, "send") as send:
            self.assertEqual(agent.scan_inbox()["added"], 2)
            self.assertEqual(send.call_count, 1)
            self.assertTrue(send.call_args.kwargs["auto"])

    def test_local_same_origin_and_public_guard(self):
        with mock.patch.dict(os.environ, {"MASTERCHIEF_PUBLIC_ONLY": ""}):
            self.assertEqual(request("GET", "/api/email"), 200)
            self.assertEqual(request("GET", "/api/email", client="192.0.2.1"), 403)
            self.assertEqual(request("GET", "/api/email", host="attacker.example"), 403)
            self.assertEqual(request("GET", "/api/email", origin="http://attacker.example"), 403)
            self.assertEqual(request("POST", "/api/email/mode"), 403)
            self.assertEqual(request("POST", "/api/email/mode", origin="http://attacker.example"), 403)
            self.assertEqual(request("GET", "/api/email", extra=((b"x-forwarded-for", b"127.0.0.1"),)), 403)
            self.assertEqual(request("POST", "/api/email/mode", origin="http://localhost:8080"), 422)
        with mock.patch.dict(os.environ, {"MASTERCHIEF_PUBLIC_ONLY": "1"}):
            self.assertEqual(request("GET", "/api/email"), 404)


if __name__ == "__main__":
    unittest.main()
