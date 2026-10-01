from flask import Blueprint, current_app, redirect, url_for, flash, session
from datetime import datetime
import uuid
from db import get_db
from security import login_required
from hotel_logic import log_action

payments_bp = Blueprint("payments", __name__)


def ensure_payment_schema():
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Платежи (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ID_Бронирования TEXT NOT NULL,
                Провайдер TEXT NOT NULL,
                ID_Платежа TEXT UNIQUE NOT NULL,
                Сумма REAL NOT NULL,
                Статус TEXT NOT NULL,
                Ссылка_на_оплату TEXT,
                Создано TEXT NOT NULL,
                Обновлено TEXT,
                FOREIGN KEY (ID_Бронирования) REFERENCES Бронирования(ID_Бронирования) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_booking ON Платежи(ID_Бронирования)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON Платежи(Статус)")
        conn.commit()
    finally:
        conn.close()


@payments_bp.post("/payment/create/<string:booking_id>")
@login_required
def create_payment(booking_id):
    """Учебная оплата: никаких внешних сервисов и реального списания денег."""
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        booking = conn.execute("""
            SELECT b.*, n.Номер_Комнаты
            FROM Бронирования b
            JOIN Номера n ON n.ID_Номера=b.ID_Номера
            WHERE b.ID_Бронирования=? AND b.ID_Клиента=?
              AND b.Статус NOT IN ('Отменено', 'Завершено')
        """, (booking_id, session.get("client_id"))).fetchone()
        invoice = conn.execute("SELECT * FROM Счета WHERE ID_Бронирования=?", (booking_id,)).fetchone()
        if not booking or not invoice:
            flash("Бронирование или счёт не найден.", "danger")
            return redirect(url_for("profile"))
        if invoice["Оплачено"] or conn.execute(
            "SELECT 1 FROM Платежи WHERE ID_Бронирования=? AND Статус='succeeded' LIMIT 1",
            (booking_id,)
        ).fetchone():
            conn.rollback()
            flash("Эта бронь уже оплачена.", "info")
            return redirect(url_for("booking_confirmation", booking_id=booking_id))

        amount = float(booking["Предоплата"] or round(float(invoice["Сумма_проживание"]) * 0.30, 2))
        payment_id = "DEMO-" + uuid.uuid4().hex[:12].upper()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            INSERT INTO Платежи(ID_Бронирования,Провайдер,ID_Платежа,Сумма,Статус,Ссылка_на_оплату,Создано,Обновлено)
            VALUES(?,?,?,?,?,?,?,?)
        """, (booking_id, "Внутренняя оплата", payment_id, amount, "succeeded", None, now, now))
        conn.execute("""
            UPDATE Счета
            SET Оплачено=1, Способ_оплаты='Онлайн (демо)', Дата_оплаты=date('now')
            WHERE ID_Бронирования=?
        """, (booking_id,))
        conn.execute("UPDATE Бронирования SET Предоплата=? WHERE ID_Бронирования=?", (amount, booking_id))
        conn.commit()
        log_action("Оплата получена", booking_id, f"Демо-оплата, {amount:.2f} ₽")
        flash(f"Оплата прошла в демо-режиме. Реальные деньги не списывались: {amount:.0f} ₽.", "success")
        return redirect(url_for("booking_confirmation", booking_id=booking_id))
    except Exception:
        conn.rollback()
        current_app.logger.exception("demo payment error")
        flash("Не удалось отметить оплату.", "danger")
        return redirect(url_for("booking_confirmation", booking_id=booking_id))
    finally:
        conn.close()


@payments_bp.get("/payment/return/<string:booking_id>")
@login_required
def payment_return(booking_id):
    return redirect(url_for("booking_confirmation", booking_id=booking_id))


@payments_bp.post("/payment/webhook")
def payment_webhook():
    # Endpoint is intentionally disabled until a provider signature is configured.
    return "Not Implemented", 501
