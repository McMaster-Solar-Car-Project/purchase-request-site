import logging
import os
import smtplib
from email.mime.text import MIMEText


class Emailer:
    def __init__(
        self, smtp_server, smtp_port, smtp_username, smtp_password, from_email
    ) -> None:
        # Get email configuration from environment variables
        self.smtp_server: str | None = smtp_server
        self.smtp_port: str | None = smtp_port
        self.smtp_username: str | None = smtp_username
        self.smtp_password: str | None = smtp_password
        self.from_email: str | None = from_email

    @classmethod
    def from_env(cls):
        return cls(
            os.getenv("SMTP_SERVER"),
            os.getenv("SMTP_PORT", "587"),
            os.getenv("SMTP_USERNAME"),
            os.getenv("SMTP_PASSWORD"),
            os.getenv("ERROR_EMAIL_FROM"),
        )

    def send_email(self, recipient_address: str, message_contents: str) -> bool:
        # Check if all required email settings are provided
        if not all(
            [
                self.smtp_server,
                self.smtp_port,
                self.smtp_username,
                self.smtp_password,
                self.from_email,
            ]
        ):
            return False
        try:
            msg = MIMEText(message_contents)
            msg["Subject"] = "Notification"
            msg["From"] = self.from_email
            msg["To"] = recipient_address
            with smtplib.SMTP(self.smtp_server, int(self.smtp_port)) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.from_email, [recipient_address], msg.as_string())
            return True
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False
