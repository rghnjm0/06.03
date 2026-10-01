"""Расширенная бизнес-логика АИС «Уют»."""
from datetime import datetime


def _sanitize_audit_text(value, max_len=500):
    """Ограничивает длину и убирает управляющие символы из полей журнала."""
    if value is None:
        return ''
    text = str(value)
    # Убираем управляющие символы, кроме табуляции и перевода строки.
    text = ''.join(ch for ch in text if ch == '\t' or ch == '\n' or ord(ch) >= 32)
    text = ' '.join(text.split())  # схлопываем пробелы
    if len(text) > max_len:
        text = text[: max_len - 1] + '…'
    return text


def log_action(action, obj='', details=''):
    try:
        from flask import session
        user = session.get('user_name') or session.get('admin_name') or 'Система'
        role = session.get('user_role') or 'system'
    except Exception:
        user, role = 'Система', 'system'
    action = _sanitize_audit_text(action, 120)
    obj = _sanitize_audit_text(obj, 120)
    details = _sanitize_audit_text(details, 500)
    user = _sanitize_audit_text(user, 120)
    role = _sanitize_audit_text(role, 40)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO Журнал_действий(Время,Пользователь,Роль,Действие,Объект,Детали) VALUES(?,?,?,?,?,?)",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user, role, action, obj, details),
        )
        conn.commit()
    finally:
        conn.close()
