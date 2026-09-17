from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from .models import User
auth_bp=Blueprint("auth",__name__,url_prefix="/auth")

@auth_bp.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(username=request.form["username"].strip()).first()
        if u and u.active and u.check_password(request.form["password"]):
            login_user(u)
            return redirect(url_for("main.dashboard"))
        flash("Неверный логин или пароль","danger")
    return render_template("login.html")

@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
