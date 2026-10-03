from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

from secret_store import encrypt_secret, decrypt_secret, mask_secret


DEFAULT_EMAIL_CONFIG = {
    "enabled": False,
    "host": "",
    "port": 587,
    "username": "",
    "from_email": "",
    "from_name": "Elios Tech",
    "security": "starttls",  # starttls | ssl | none
}


async def get_email_config(db, include_secret: bool = False) -> Dict[str, Any]:
    doc = await db.settings.find_one({"_id": "email_config"}) or {}
    cfg = dict(DEFAULT_EMAIL_CONFIG)
    for k in DEFAULT_EMAIL_CONFIG:
        if doc.get(k) is not None:
            cfg[k] = doc.get(k)
    password = decrypt_secret(doc.get("password_encrypted") or "")
    cfg["configured"] = bool(cfg.get("host") and cfg.get("port") and cfg.get("from_email") and (password or not cfg.get("username")))
    cfg["password_configured"] = bool(password)
    cfg["password_masked"] = mask_secret(password)
    if include_secret:
        cfg["password"] = password
    return cfg


async def save_email_config(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    for k in ("enabled", "host", "port", "username", "from_email", "from_name", "security"):
        if k in payload and payload[k] is not None:
            updates[k] = payload[k].strip() if isinstance(payload[k], str) else payload[k]
    password = payload.get("password")
    if isinstance(password, str) and password.strip():
        updates["password_encrypted"] = encrypt_secret(password.strip())
    if updates:
        await db.settings.update_one({"_id": "email_config"}, {"$set": updates}, upsert=True)
    return await get_email_config(db)


def _send_sync(cfg: Dict[str, Any], recipient: str, subject: str, html_content: str) -> str:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{cfg.get("from_name") or "Elios Tech"} <{cfg["from_email"]}>'
    msg["To"] = recipient
    msg.set_content("Questa email contiene contenuto HTML. Aprila con un client compatibile.")
    msg.add_alternative(html_content, subtype="html")

    host = cfg["host"]
    port = int(cfg.get("port") or 587)
    security = cfg.get("security") or "starttls"
    if security == "ssl":
        smtp = smtplib.SMTP_SSL(host, port, timeout=25)
    else:
        smtp = smtplib.SMTP(host, port, timeout=25)
    try:
        smtp.ehlo()
        if security == "starttls":
            smtp.starttls()
            smtp.ehlo()
        if cfg.get("username"):
            smtp.login(cfg["username"], cfg.get("password") or "")
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    return "smtp-sent"


async def send_email(db, recipient: str, subject: str, html_content: str) -> str:
    cfg = await get_email_config(db, include_secret=True)
    if not cfg.get("enabled"):
        raise RuntimeError("Invio email disattivato nelle Impostazioni")
    if not cfg.get("configured"):
        raise RuntimeError("Configurazione SMTP incompleta")
    return await asyncio.to_thread(_send_sync, cfg, recipient, subject, html_content)


def _send_sync_attachment(cfg: Dict[str, Any], recipient: str, subject: str, html_content: str, attachment_path, attachment_name: str, mime_type: str = "application/pdf") -> str:
    from pathlib import Path
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{cfg.get("from_name") or "Elios Tech"} <{cfg["from_email"]}>'
    msg["To"] = recipient
    msg.set_content("Questa email contiene contenuto HTML. Aprila con un client compatibile.")
    msg.add_alternative(html_content, subtype="html")
    maintype, _, subtype = (mime_type or "application/octet-stream").partition("/")
    if not subtype:
        maintype, subtype = "application", "octet-stream"
    raw = Path(attachment_path).read_bytes()
    msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=attachment_name)

    host = cfg["host"]
    port = int(cfg.get("port") or 587)
    security = cfg.get("security") or "starttls"
    if security == "ssl":
        smtp = smtplib.SMTP_SSL(host, port, timeout=25)
    else:
        smtp = smtplib.SMTP(host, port, timeout=25)
    try:
        smtp.ehlo()
        if security == "starttls":
            smtp.starttls(); smtp.ehlo()
        if cfg.get("username"):
            smtp.login(cfg["username"], cfg.get("password") or "")
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    return "smtp-sent"


async def send_email_with_attachment(db, recipient: str, subject: str, html_content: str, attachment_path, attachment_name: str, mime_type: str = "application/pdf") -> str:
    cfg = await get_email_config(db, include_secret=True)
    if not cfg.get("enabled"):
        raise RuntimeError("Invio email disattivato nelle Impostazioni")
    if not cfg.get("configured"):
        raise RuntimeError("Configurazione SMTP incompleta")
    return await asyncio.to_thread(_send_sync_attachment, cfg, recipient, subject, html_content, attachment_path, attachment_name, mime_type)
