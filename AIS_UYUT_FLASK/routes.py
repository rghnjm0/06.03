from flask import Blueprint, render_template, request, redirect, url_for, flash
from data import ROOMS, BOOKINGS, GUESTS
from utils import today, parse_iso_date

main = Blueprint("main", __name__)

@main.app_context_processor
def globals():
    return {
        "now": today(),
        "free_rooms": sum(r["status"] == "Свободен" for r in ROOMS),
        "occupied_rooms": sum(r["status"] == "Занят" for r in ROOMS),
        "rooms_count": len(ROOMS),
    }

@main.route("/")
def dashboard():
    return render_template("dashboard.html", active="dashboard", bookings=BOOKINGS, rooms=ROOMS)

@main.route("/bookings", methods=["GET", "POST"])
def bookings_page():
    if request.method == "POST":
        guest = request.form.get("guest", "").strip()
        room_number = request.form.get("room", "").strip()
        checkin = request.form.get("checkin", "")
        checkout = request.form.get("checkout", "")
        if not all([guest, room_number, checkin, checkout]):
            flash("Заполните все поля.", "error")
            return redirect(url_for("main.bookings_page"))
        try:
            start = parse_iso_date(checkin)
            end = parse_iso_date(checkout)
        except ValueError:
            flash("Проверьте даты.", "error")
            return redirect(url_for("main.bookings_page"))
        if end <= start:
            flash("Дата выезда должна быть позже даты заезда.", "error")
            return redirect(url_for("main.bookings_page"))
        room = next((r for r in ROOMS if r["number"] == room_number), None)
        if room is None or room["status"] != "Свободен":
            flash("Выбранный номер недоступен.", "error")
            return redirect(url_for("main.bookings_page"))
        nights = (end - start).days
        BOOKINGS.append({
            "id": max([b["id"] for b in BOOKINGS], default=0) + 1,
            "guest": guest,
            "room": room_number,
            "checkin": start.strftime("%d.%m.%Y"),
            "checkout": end.strftime("%d.%m.%Y"),
            "status": "Новое",
            "amount": nights * room["price"],
        })
        flash("Бронирование создано.", "success")
        return redirect(url_for("main.bookings_page"))
    return render_template("bookings.html", active="bookings", bookings=BOOKINGS, rooms=ROOMS)

@main.route("/rooms")
def rooms_page():
    return render_template("rooms.html", active="rooms", rooms=ROOMS)

@main.route("/guests")
def guests_page():
    return render_template("guests.html", active="guests", guests=GUESTS)

@main.route("/reports")
def reports():
    return render_template("reports.html", active="reports", bookings=BOOKINGS, rooms=ROOMS)

@main.route("/settings")
def settings():
    return render_template("settings.html", active="settings")

@main.route("/checkin/<int:booking_id>")
def checkin(booking_id):
    booking = next((b for b in BOOKINGS if b["id"] == booking_id), None)
    if booking:
        booking["status"] = "Проживает"
        for room in ROOMS:
            if room["number"] == booking["room"]:
                room["status"] = "Занят"
        flash("Гость успешно зарегистрирован.", "success")
    return redirect(url_for("main.bookings_page"))

@main.route("/checkout/<int:booking_id>")
def checkout(booking_id):
    booking = next((b for b in BOOKINGS if b["id"] == booking_id), None)
    if booking:
        booking["status"] = "Выселен"
        for room in ROOMS:
            if room["number"] == booking["room"]:
                room["status"] = "Уборка"
        flash("Выселение оформлено. Номер передан в уборку.", "success")
    return redirect(url_for("main.bookings_page"))
