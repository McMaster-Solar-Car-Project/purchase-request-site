import os
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.core.logging_utils import setup_logger

logger = setup_logger(__name__)


class EmailerPipeline:
    """Enhanced email pipeline for sending rich HTML confirmation emails with attachments"""

    def __init__(self) -> None:
        # Get email configuration from environment variables
        self.smtp_server: str | None = os.getenv("SMTP_SERVER")
        self.smtp_port: str | None = os.getenv("SMTP_PORT", "587")
        self.smtp_username: str | None = os.getenv("SMTP_USERNAME")
        self.smtp_password: str | None = os.getenv("SMTP_PASSWORD")
        self.from_email: str | None = os.getenv("ERROR_EMAIL_FROM")

        # Check if email is configured
        self.is_configured = all(
            [
                self.smtp_server,
                self.smtp_port,
                self.smtp_username,
                self.smtp_password,
                self.from_email,
            ]
        )

        if not self.is_configured:
            logger.warning(
                "Email configuration incomplete - email notifications will be disabled"
            )

    def send_purchase_request_confirmation(
        self,
        user_info: dict,
        submitted_forms: list[dict],
        session_folder: str,
        drive_folder_url: str = "",
    ) -> bool:
        """
        Send a rich HTML confirmation email with purchase request details and attachments

        Args:
            user_info: Dictionary containing user information (name, email, etc.)
            submitted_forms: List of submitted purchase request forms
            session_folder: Path to session folder containing generated files
            drive_folder_url: Optional Google Drive folder URL

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.info("Email not configured - skipping confirmation email")
            return False

        try:
            # Create email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"Purchase Request Confirmation - {user_info.get('name', 'Unknown')}"
            )
            msg["From"] = self.from_email
            msg["To"] = user_info.get("email", "")

            # Generate HTML content
            html_content = self._generate_confirmation_html(
                user_info, submitted_forms, drive_folder_url
            )

            # Attach HTML content
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Attach Excel files
            self._attach_excel_files(msg, session_folder)

            # Send email
            return self._send_email(msg)

        except Exception as e:
            logger.error(f"Failed to send purchase request confirmation: {e}")
            return False

    def _generate_confirmation_html(
        self, user_info: dict, submitted_forms: list[dict], drive_folder_url: str = ""
    ) -> str:
        """Generate rich HTML content for confirmation email"""

        # Calculate totals
        total_amount = sum(form.get("total_amount", 0) for form in submitted_forms)
        form_count = len(submitted_forms)

        # Get current date
        current_date = datetime.now().strftime("%B %d, %Y")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Purchase Request Confirmation</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
                .summary-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                .form-item {{ background: white; padding: 15px; margin: 10px 0; border-radius: 6px; border: 1px solid #e9ecef; }}
                .amount {{ font-weight: bold; color: #28a745; }}
                .footer {{ text-align: center; margin-top: 30px; padding: 20px; color: #6c757d; font-size: 14px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; margin: 10px 5px; }}
                .attachments {{ background: #e3f2fd; padding: 15px; border-radius: 6px; margin: 15px 0; }}
                h1, h2, h3 {{ margin-top: 0; }}
                .status {{ background: #d4edda; color: #155724; padding: 10px; border-radius: 4px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Purchase Request Submitted Successfully!</h1>
                <p>Thank you for submitting your purchase request</p>
            </div>

            <div class="content">
                <div class="status">
                    <strong>✅ Status:</strong> Your purchase request has been successfully submitted and processed on {current_date}
                </div>

                <div class="summary-box">
                    <h2>📋 Request Summary</h2>
                    <p><strong>Submitted by:</strong> {user_info.get("name", "N/A")}</p>
                    <p><strong>Email:</strong> {user_info.get("email", "N/A")}</p>
                    <p><strong>Team:</strong> {user_info.get("team", "N/A")}</p>
                    <p><strong>E-transfer Email:</strong> {user_info.get("e_transfer_email", "N/A")}</p>
                    <p><strong>Forms Submitted:</strong> {form_count}</p>
                    <p><strong>Total Amount:</strong> <span class="amount">${total_amount:.2f} CAD</span></p>
                </div>

                <h3>📝 Purchase Details</h3>
        """

        # Add details for each form
        for i, form in enumerate(submitted_forms, 1):
            currency = form.get("currency", "CAD")
            vendor = form.get("vendor_name", "Unknown Vendor")
            amount = form.get("total_amount", 0)
            item_count = len(form.get("items", []))

            html += f"""
                <div class="form-item">
                    <h4>Form {i}: {vendor}</h4>
                    <p><strong>Currency:</strong> {currency}</p>
                    <p><strong>Items:</strong> {item_count}</p>
                    <p><strong>Total:</strong> <span class="amount">${amount:.2f} {currency}</span></p>
                </div>
            """

        # Add attachments section
        html += """
                <div class="attachments">
                    <h3>📎 Attached Documents</h3>
                    <p>The following documents have been generated and attached to this email:</p>
                    <ul>
                        <li><strong>Purchase Request Form</strong> - Complete purchase request with all submitted items</li>
                        <li><strong>Expense Report</strong> - Pre-filled expense report for reimbursement</li>
                    </ul>
                    <p><em>These files are also available in your Google Drive folder (if configured).</em></p>
                </div>
        """

        # Add Google Drive link if available
        if drive_folder_url:
            html += f"""
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{drive_folder_url}" class="button">📁 View in Google Drive</a>
                </div>
            """

        # Add footer
        html += f"""
                <div class="footer">
                    <p><strong>Next Steps:</strong></p>
                    <ol style="text-align: left; display: inline-block;">
                        <li>Review the attached documents for accuracy</li>
                        <li>Submit the expense report to your team lead</li>
                        <li>Keep receipts and invoices for your records</li>
                    </ol>

                    <hr style="margin: 20px 0; border: none; border-top: 1px solid #dee2e6;">
                    <p>This is an automated confirmation from the McMaster Solar Car Purchase Request System.</p>
                    <p>Generated on {current_date}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _attach_excel_files(self, msg: MIMEMultipart, session_folder: str) -> None:
        """Attach Excel files from session folder to email"""

        session_path = Path(session_folder)
        if not session_path.exists():
            logger.warning(f"Session folder not found: {session_folder}")
            return

        # Look for Excel files to attach
        excel_files = [
            "purchase_request.xlsx",
            # Look for expense report files (they have dynamic names)
        ]

        # Find expense report file (has dynamic name)
        for file_path in session_path.glob("*ExpenseReport*.xlsx"):
            excel_files.append(file_path.name)

        for filename in excel_files:
            file_path = session_path / filename
            if file_path.exists():
                try:
                    with open(file_path, "rb") as f:
                        attachment = MIMEApplication(f.read(), _subtype="xlsx")
                        attachment.add_header(
                            "Content-Disposition", "attachment", filename=filename
                        )
                        msg.attach(attachment)
                        logger.info(f"Attached file: {filename}")
                except Exception as e:
                    logger.error(f"Failed to attach file {filename}: {e}")
            else:
                logger.warning(f"Excel file not found: {file_path}")

    def _send_email(self, msg: MIMEMultipart) -> bool:
        """Send the email message"""
        try:
            with smtplib.SMTP(self.smtp_server, int(self.smtp_port)) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                logger.info(f"Confirmation email sent successfully to {msg['To']}")
                return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_email(self, recipient_address: str, message_contents: str) -> bool:
        """Legacy method for backward compatibility"""
        if not self.is_configured:
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
            logger.error(f"Failed to send email: {e}")
            return False


# Backward compatibility
Emailer = EmailerPipeline
