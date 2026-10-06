import smtplib
import unittest
from unittest.mock import MagicMock, patch

from app.services.email_service import EmailSendError, send_email

ARGS = {
    "subject": "Informe diario — crypto-bot",
    "body": "Fase: SIMULATION\nBalance: sin datos\n",
    "to": "owner@example.com, second@example.com",
    "host": "smtp.gmail.com",
    "port": 587,
    "user": "bot@example.com",
    "password": "app-secret-password",
}


def _send(**overrides) -> dict:
    kwargs = {**ARGS, **overrides}
    with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
        send_email(**kwargs)
        smtp_cls.assert_called_once_with(
            kwargs["host"],
            kwargs["port"],
            timeout=10,
        )
        smtp: MagicMock = smtp_cls.return_value.__enter__.return_value
        message: object = smtp.send_message.call_args.args[0]
        return {"smtp": smtp, "message": message}


class SendEmailTests(unittest.TestCase):
    def test_sends_plain_text_message_over_starttls(self) -> None:
        result = _send()
        smtp: MagicMock = result["smtp"]
        message = result["message"]
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with(ARGS["user"], ARGS["password"])
        smtp.send_message.assert_called_once()
        self.assertEqual(message["Subject"], ARGS["subject"])
        self.assertEqual(message["From"], ARGS["user"])
        self.assertEqual(message["To"], ARGS["to"])
        self.assertIn("Fase: SIMULATION", message.get_content())
        self.assertTrue(message.get_content_type().startswith("text/plain"))

    def test_recipients_split_by_comma(self) -> None:
        result = _send(to="a@example.com,b@example.com")
        message = result["message"]
        self.assertIn("a@example.com", message["To"])
        self.assertIn("b@example.com", message["To"])

    def test_html_alternative_attached_when_given(self) -> None:
        result = _send(html="<!DOCTYPE html><html><body>Hola</body></html>")
        message = result["message"]
        self.assertTrue(message.is_multipart())
        plain = message.get_body(preferencelist=("plain",))
        html_part = message.get_body(preferencelist=("html",))
        self.assertIsNotNone(plain)
        self.assertIn("Fase: SIMULATION", plain.get_content())
        self.assertIsNotNone(html_part)
        self.assertIn("<!DOCTYPE html>", html_part.get_content())

    def test_without_html_stays_plain_text(self) -> None:
        result = _send()
        self.assertFalse(result["message"].is_multipart())

    def test_missing_recipient_is_rejected(self) -> None:
        with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            with self.assertRaises(ValueError) as ctx:
                send_email(**{**ARGS, "to": ""})
        self.assertIn("REPORT_TO", str(ctx.exception))
        smtp_cls.assert_not_called()

    def test_missing_password_is_rejected(self) -> None:
        with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            with self.assertRaises(ValueError) as ctx:
                send_email(**{**ARGS, "password": ""})
        self.assertIn("SMTP_PASS", str(ctx.exception))
        smtp_cls.assert_not_called()

    def test_missing_user_is_rejected(self) -> None:
        with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            with self.assertRaises(ValueError) as ctx:
                send_email(**{**ARGS, "user": ""})
        self.assertIn("SMTP_USER", str(ctx.exception))
        smtp_cls.assert_not_called()

    def test_connection_error_wrapped_without_password(self) -> None:
        with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            smtp_cls.side_effect = OSError("[Errno 111] Connection refused")
            with self.assertRaises(EmailSendError) as ctx:
                send_email(**ARGS)
        message = str(ctx.exception)
        self.assertIn("smtp.gmail.com", message)
        self.assertNotIn(ARGS["password"], message)
        self.assertIsInstance(ctx.exception.__cause__, OSError)

    def test_login_error_wrapped_without_password(self) -> None:
        with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
            smtp: MagicMock = smtp_cls.return_value.__enter__.return_value
            smtp.login.side_effect = smtplib.SMTPAuthenticationError(
                535,
                b"5.7.8 Invalid credentials",
            )
            with self.assertRaises(EmailSendError) as ctx:
                send_email(**ARGS)
        message = str(ctx.exception)
        self.assertIn("535", message)
        self.assertNotIn(ARGS["password"], message)
        self.assertIsInstance(
            ctx.exception.__cause__,
            smtplib.SMTPAuthenticationError,
        )


if __name__ == "__main__":
    unittest.main()
