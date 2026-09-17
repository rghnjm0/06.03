from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .models import Room, RoomCategory, Tariff
from . import db
from .utils import roles_required, audit
rooms_bp=Blueprint("rooms",__name__,url_prefix="/rooms")

@rooms_bp.get("/")
@login_required
def index():
    return render_template("rooms.html", rooms=Room.query.order_by(Room.number).all(), categories=RoomCategory.query.all())

@rooms_bp.post("/add")
@login_required
@roles_required("admin","manager")
def add():
    num=request.form["number"].strip()
    if Room.query.filter_by(number=num).first():
        flash("Такой номер уже существует","danger")
    else:
        r=Room(number=num,floor=int(request.form.get("floor",1)),category_id=int(request.form["category_id"]))
        db.session.add(r); db.session.commit(); audit("Добавлен номер","Room",r.id); flash("Номер добавлен","success")
    return redirect(url_for("rooms.index"))

@rooms_bp.get("/tariffs")
@login_required
def tariffs():
    return render_template("tariffs.html", tariffs=Tariff.query.all(), categories=RoomCategory.query.all())

@rooms_bp.post("/tariffs/add")
@login_required
@roles_required("admin","manager")
def add_tariff():
    t=Tariff(name=request.form["name"],category_id=int(request.form["category_id"]),price=float(request.form["price"]),season=request.form.get("season","Базовый"))
    db.session.add(t); db.session.commit(); audit("Добавлен тариф","Tariff",t.id)
    return redirect(url_for("rooms.tariffs"))
