# email_utils.py
import os
from mailjet_rest import Client

MJ_API_KEY = os.getenv("MJ_API_KEY")
MJ_SECRET = os.getenv("MJ_SECRET")
#MJ_API_KEY ="9f3f97d0c89c88536ab42d207b603fcf"
#MJ_SECRET = "2ae94cb0f96194911491894fa4513f16"
MJ_SENDER = os.getenv("MJ_SENDER", "rohit@transporthub.com")
MJ_SENDER_NAME = os.getenv("MJ_SENDER_NAME", "Logistics FinApp")

if MJ_API_KEY and MJ_SECRET:
    mj_client = Client(auth=(MJ_API_KEY, MJ_SECRET), version="v3.1")
else:
    mj_client = None


def send_verification_email(to_email: str, verify_link: str):
    """
    Send email verification link using Mailjet.
    If Mailjet is not configured, just log to console (no crash).
    """
    if mj_client is None:
        print(
            "[Mailjet] MJ_API_KEY / MJ_SECRET not configured. "
            f"Would send verification to {to_email}: {verify_link}"
        )
        return

    subject = "Verify your email – Logistics FinApp"
    text_body = f"""Hi,

Thanks for signing up on Logistics FinApp.

Please click the link below to verify your email address (valid for 30 minutes):
{verify_link}

If you did not request this, you can ignore this email.

Regards,
Logistics FinApp
"""

    html_body = f"""
    <p>Hi,</p>
    <p>Thanks for signing up on <strong>Logistics FinApp</strong>.</p>
    <p>
      Please click the link below to verify your email address
      (valid for 30 minutes):
    </p>
    <p><a href="{verify_link}">{verify_link}</a></p>
    <p>If you did not request this, you can ignore this email.</p>
    <p>Regards,<br/>Logistics FinApp</p>
    """

    data = {
        "Messages": [
            {
                "From": {
                    "Email": MJ_SENDER,
                    "Name": MJ_SENDER_NAME,
                },
                "To": [{"Email": to_email}],
                "Subject": subject,
                "TextPart": text_body,
                "HTMLPart": html_body,
            }
        ]
    }

    try:
        result = mj_client.send.create(data=data)
        print("[Mailjet] Sent verification email to", to_email, "status:", result.status_code)
    except Exception as e:
        print("[Mailjet] Error sending email:", e)

# Forgot password email function can be added similarly
def send_password_reset_email(to_email: str, reset_link: str):
    """
    Password reset email – intentionally uses the SAME structure as send_verification_email
    to avoid relay/access issues.
    """
    subject = "Reset your password – Logistics FinApp"

    text_body = f"""Hi,

We received a request to reset the password for your Logistics FinApp account.

If you made this request, click the link below to set a new password (valid for 30 minutes):

{reset_link}

If you did NOT request this, you can ignore this email.

Regards,
Logistics FinApp
"""

    html_body = f"""
    <html>
      <body>
        <p>Hi,</p>
        <p>We received a request to reset the password for your
           <strong>Logistics FinApp</strong> account.</p>
        <p>If you made this request, click the link below to set a new password
           (valid for 30 minutes):</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>If you did NOT request this, you can ignore this email.</p>
        <p>Regards,<br>Logistics FinApp</p>
      </body>
    </html>
    """

    data = {
        "Messages": [
            {
                "From": {"Email": MJ_SENDER, "Name": MJ_SENDER_NAME},
                "To": [{"Email": to_email}],
                "Subject": subject,
                "TextPart": text_body,
                "HTMLPart": html_body,
                "CustomID": "PasswordReset"
            }
        ]
    }

    try:
        result = mj_client.send.create(data=data)
        print("[Mailjet] Reset status:", result.status_code)
        print("[Mailjet] Reset resp:", result.json())
    except Exception as e:
        print("[Mailjet] Error sending password reset email:", e)