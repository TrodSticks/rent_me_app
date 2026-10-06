"""Sending email.

Four backends, chosen by MAIL_BACKEND (see config.py):
  smtp      real delivery through MAIL_SERVER
  file      development mailbox: each email is saved under mail_outbox/ and shown at /dev/mailbox
  memory    kept in a list on the app, for tests
  disabled  nothing is sent

Email bodies contain sign-in links, so they are never written to the log.
"""
import json
import os
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from flask import current_app, url_for


def mail_enabled():
    return current_app.config['MAIL_BACKEND'] != 'disabled'


def external_url(endpoint, **values):
    """A full link for use in an email."""
    base = current_app.config.get('PUBLIC_BASE_URL')
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def send_email(to, subject, body):
    """Send one plain-text email. Returns True if it was handed over, False otherwise."""
    backend = current_app.config['MAIL_BACKEND']
    try:
        if backend == 'smtp':
            _send_smtp(to, subject, body)
        elif backend == 'file':
            _save_to_outbox(to, subject, body)
        elif backend == 'memory':
            current_app.extensions.setdefault('mail_outbox', []).append(
                {'to': to, 'subject': subject, 'body': body})
        else:
            current_app.logger.warning("Email not sent (email is not configured): %s", subject)
            return False
    except (OSError, smtplib.SMTPException) as error:
        # Log what failed, never the body: it holds a sign-in link
        current_app.logger.error("Could not send email %r: %s", subject, error)
        return False
    return True


def _send_smtp(to, subject, body):
    config = current_app.config
    message = EmailMessage()
    message['From'] = config['MAIL_FROM']
    message['To'] = to
    message['Subject'] = subject
    message.set_content(body)

    if config['MAIL_USE_SSL']:
        server = smtplib.SMTP_SSL(config['MAIL_SERVER'], config['MAIL_PORT'], timeout=15)
    else:
        server = smtplib.SMTP(config['MAIL_SERVER'], config['MAIL_PORT'], timeout=15)
    with server:
        if config['MAIL_USE_TLS'] and not config['MAIL_USE_SSL']:
            server.starttls()
        if config['MAIL_USERNAME']:
            server.login(config['MAIL_USERNAME'], config['MAIL_PASSWORD'])
        server.send_message(message)


def _save_to_outbox(to, subject, body):
    folder = current_app.config['MAIL_OUTBOX_DIR']
    os.makedirs(folder, exist_ok=True)
    sent_at = datetime.now(timezone.utc)
    name = f"{sent_at.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}.json"
    with open(os.path.join(folder, name), 'w', encoding='utf-8') as f:
        json.dump({'to': to, 'subject': subject, 'body': body, 'sent_at': sent_at.isoformat()}, f)


def read_outbox(limit=30):
    """The newest emails in the development mailbox."""
    folder = current_app.config['MAIL_OUTBOX_DIR']
    if not os.path.isdir(folder):
        return []
    emails = []
    for name in sorted(os.listdir(folder), reverse=True)[:limit]:
        try:
            with open(os.path.join(folder, name), encoding='utf-8') as f:
                emails.append(json.load(f))
        except (OSError, ValueError):
            continue
    return emails
