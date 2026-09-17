from flask import Blueprint, render_template, request, send_file
from flask_login import login_required
from io import BytesIO
from openpyxl import Workbook
from reportlab.pdfgen import canvas
from .models import Booking, Payment, Room
from . import db
reports_bp=Blueprint("reports",__name__,url_prefix="/reports")

@reports_bp.get("/")
@login_required
def index():
    bookings=Booking.query.all()
    revenue=sum(float(p.amount) for p in Payment.query.filter_by(status="paid").all())
    return render_template("reports.html", bookings=bookings, revenue=revenue, rooms=Room.query.all())

@reports_bp.get("/xlsx")
@login_required
def xlsx():
    wb=Workbook(); ws=wb.active; ws.title="Бронирования"
    ws.append(["Код","Гость","Номер","Заезд","Выезд","Статус","Сумма"])
    for b in Booking.query.all():
        ws.append([b.code,f"{b.guest.first_name} {b.guest.last_name}",b.room.number,str(b.check_in),str(b.check_out),b.status,float(b.total)])
    out=BytesIO(); wb.save(out); out.seek(0)
    return send_file(out,as_attachment=True,download_name="uyut_report.xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@reports_bp.get("/pdf")
@login_required
def pdf():
    out=BytesIO(); c=canvas.Canvas(out)
    c.setTitle("АИС Уют — отчёт")
    c.drawString(50,800,"АИС «Уют» — отчёт по бронированиям")
    y=775
    for b in Booking.query.all()[:35]:
        c.drawString(50,y,f"{b.code} | {b.room.number} | {b.guest.last_name} | {b.check_in} — {b.check_out} | {b.status} | {b.total}")
        y-=18
        if y<50: c.showPage(); y=800
    c.save(); out.seek(0)
    return send_file(out,as_attachment=True,download_name="uyut_report.pdf",mimetype="application/pdf")
