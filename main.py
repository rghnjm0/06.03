from datetime import date
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required
from .models import Room, Booking, Guest, Payment, AuditLog
from . import db
main_bp=Blueprint("main",__name__)

@main_bp.get("/")
def index():
    return render_template("home.html")

@main_bp.get("/dashboard")
@login_required
def dashboard():
    today=date.today()
    rooms=Room.query.count()
    available=Room.query.filter_by(status="available").count()
    arrivals=Booking.query.filter_by(check_in=today).filter(Booking.status.in_(["confirmed","checked_in"])).count()
    departures=Booking.query.filter_by(check_out=today).filter(Booking.status=="checked_in").count()
    revenue=sum(float(p.amount) for p in Payment.query.filter_by(status="paid").all())
    recent=Booking.query.order_by(Booking.created_at.desc()).limit(8).all()
    return render_template("dashboard.html", rooms=rooms, available=available, arrivals=arrivals, departures=departures, revenue=revenue, recent=recent)

@main_bp.get("/audit")
@login_required
def audit_log():
    logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("audit.html", logs=logs)
