"""SMTP email bhejna + har email DB mein log karna. Gmail App Password free hai."""
import os
import smtplib
from email.message import EmailMessage

from jinja2 import Template

from app.config import settings
from app.database import db_session
from app.models import EmailLog
from app.services.email_templates import BASE, TEMPLATES


def render(template_name: str, ctx: dict) -> tuple[str, str]:
    tpl = TEMPLATES[template_name]
    ctx = {"company": settings.COMPANY_NAME, "note": "", **ctx}
    subject = Template(tpl["subject"]).render(**ctx)
    body = Template(tpl["body"]).render(**ctx)
    html = Template(BASE).render(body=body, **ctx)
    return subject, html


def send_email(to_email: str, subject: str, html: str, template: str = "custom",
               attachment: str | None = None) -> bool:
    msg = EmailMessage()
    msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("Yeh email HTML mein hai.")
    msg.add_alternative(html, subtype="html")

    if attachment and os.path.exists(attachment):
        with open(attachment, "rb") as f:
            msg.add_attachment(f.read(), maintype="text", subtype="calendar",
                               filename=os.path.basename(attachment))

    status, error = "sent", None
    try:
        if not settings.SMTP_USER:                      # dev mode: console pe print
            print(f"\n--- [DEV EMAIL] to={to_email} subject={subject} ---\n")
            status = "sent(dev)"
        elif settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as s:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
                s.starttls()
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
    except Exception as e:
        status, error = "failed", str(e)
        print(f"[email] FAIL {to_email}: {e}")

    db = db_session()
    try:
        db.add(EmailLog(to_email=to_email, subject=subject, template=template,
                        body=html, status=status, error=error))
        db.commit()
    finally:
        db.close()
    return status.startswith("sent")


def send_template(to_email: str, template: str, ctx: dict,
                  attachment: str | None = None) -> bool:
    subject, html = render(template, ctx)
    return send_email(to_email, subject, html, template=template, attachment=attachment)
