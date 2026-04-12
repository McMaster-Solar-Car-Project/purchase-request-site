import logging
import smtplib
from email.mime.text import MIMEText

from src.core.settings import get_settings


class Emailer:
    def __init__(self) -> None:
        settings = get_settings()
        self.smtp_server: str | None = settings.smtp_server
        self.smtp_port: int = settings.smtp_port
        self.smtp_username: str | None = settings.smtp_username
        self.smtp_password: str | None = settings.smtp_password
        self.from_email: str | None = settings.error_email_from

    def send_email(self, recipient_address: str, message_contents: str) -> bool:
        smtp_server = self.smtp_server
        smtp_port = self.smtp_port
        smtp_username = self.smtp_username
        smtp_password = self.smtp_password
        from_email = self.from_email
        if not all([smtp_server, smtp_port, smtp_username, smtp_password, from_email]):
            return False
        assert smtp_server is not None
        assert smtp_username is not None
        assert smtp_password is not None
        assert from_email is not None
        try:
            msg = MIMEText(message_contents)
            msg["Subject"] = "Notification"
            msg["From"] = from_email
            msg["To"] = recipient_address
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.sendmail(from_email, [recipient_address], msg.as_string())
            return True
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False
