from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .models import Guest
from . import db
from .utils import audit
guests_bp=Blueprint("guests",__name__,url_prefix="/guests")

@guests_bp.route("/",methods=["GET","POST"])
@login_required
def index():
    if request.method=="POST":
        g=Guest(first_name=request.form["first_name"],last_name=request.form["last_name"],phone=request.form.get("phone",""),email=request.form.get("email",""),document=request.form.get("document",""))
        db.session.add(g); db.session.commit(); audit("Добавлен гость","Guest",g.id); flash("Гость добавлен","success")
        return redirect(url_for("guests.index"))
    return render_template("guests.html", guests=Guest.query.order_by(Guest.created_at.desc()).all())
