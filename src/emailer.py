import logging
import os
import smtplib
from email.mime.text import MIMEText


class Emailer:
    def __init__(self) -> None:
        # Get email configuration from environment variables
        self.smtp_server: str | None = os.getenv("SMTP_SERVER")
        self.smtp_port: str | None = os.getenv("SMTP_PORT", "587")
        self.smtp_username: str | None = os.getenv("SMTP_USERNAME")
        self.smtp_password: str | None = os.getenv("SMTP_PASSWORD")
        self.from_email: str | None = os.getenv("ERROR_EMAIL_FROM")

    def send_email(self, recipient_address: str, message_contents: str) -> bool:
        smtp_server = self.smtp_server
        smtp_port = self.smtp_port
        smtp_username = self.smtp_username
        smtp_password = self.smtp_password
        from_email = self.from_email
        if not all([smtp_server, smtp_port, smtp_username, smtp_password, from_email]):
            return False
        assert smtp_server is not None
        assert smtp_port is not None
        assert smtp_username is not None
        assert smtp_password is not None
        assert from_email is not None
        try:
            msg = MIMEText(message_contents)
            msg["Subject"] = "Notification"
            msg["From"] = from_email
            msg["To"] = recipient_address
            with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.sendmail(from_email, [recipient_address], msg.as_string())
            return True
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False
