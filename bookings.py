from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import and_
from .models import Booking, Room, Guest, Payment
from . import db
from .utils import audit

bookings_bp=Blueprint("bookings",__name__,url_prefix="/bookings")

def parse_date(v): return date.fromisoformat(v)

def free_rooms(check_in,check_out):
    busy=db.session.query(Booking.room_id).filter(
        Booking.status.in_(["confirmed","checked_in"]),
        Booking.check_in < check_out,
        Booking.check_out > check_in
    ).subquery()
    return Room.query.filter(~Room.id.in_(busy)).all()

@bookings_bp.route("/",methods=["GET","POST"])
@login_required
def index():
    if request.method=="POST":
        try:
            ci,co=parse_date(request.form["check_in"]),parse_date(request.form["check_out"])
            if co<=ci: raise ValueError("Дата выезда должна быть позже даты заезда")
            room_id=int(request.form["room_id"])
            conflict=Booking.query.filter(
                Booking.room_id==room_id,
                Booking.status.in_(["confirmed","checked_in"]),
                Booking.check_in < co, Booking.check_out > ci
            ).first()
            if conflict: raise ValueError("Номер уже забронирован на пересекающиеся даты")
            guest=Guest.query.get(int(request.form["guest_id"]))
            room=Room.query.get(room_id)
            nights=(co-ci).days
            total=Decimal(str(room.category.base_price))*nights
            code="UYUT-"+str(Booking.query.count()+1001)
            b=Booking(code=code,room_id=room_id,guest_id=guest.id,check_in=ci,check_out=co,status="confirmed",source=request.form.get("source","reception"),adults=int(request.form.get("adults",1)),children=int(request.form.get("children",0)),total=total)
            db.session.add(b); db.session.commit(); audit("Создано бронирование","Booking",b.id)
            flash(f"Бронирование {code} создано","success")
        except Exception as e:
            db.session.rollback(); flash(str(e),"danger")
        return redirect(url_for("bookings.index"))
    bookings=Booking.query.order_by(Booking.check_in.desc()).all()
    guests=Guest.query.order_by(Guest.last_name).all()
    rooms=Room.query.order_by(Room.number).all()
    return render_template("bookings.html",bookings=bookings,guests=guests,rooms=rooms)

@bookings_bp.get("/availability")
@login_required
def availability():
    ci=parse_date(request.args.get("check_in",str(date.today())))
    co=parse_date(request.args.get("check_out",str(date.today())))
    return render_template("availability.html",rooms=free_rooms(ci,co),check_in=ci,check_out=co)

@bookings_bp.post("/<int:id>/status")
@login_required
def status(id):
    b=Booking.query.get_or_404(id)
    s=request.form["status"]
    if s not in ("confirmed","checked_in","checked_out","cancelled"): flash("Недопустимый статус","danger")
    else:
        b.status=s; db.session.commit(); audit(f"Изменён статус на {s}","Booking",b.id); flash("Статус обновлён","success")
    return redirect(url_for("bookings.index"))

@bookings_bp.post("/<int:id>/payment")
@login_required
def payment(id):
    b=Booking.query.get_or_404(id)
    p=Payment(booking_id=b.id,amount=Decimal(request.form["amount"]),method=request.form["method"])
    db.session.add(p); db.session.commit(); audit("Зарегистрирован платёж","Payment",p.id)
    return redirect(url_for("bookings.index"))
