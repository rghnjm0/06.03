from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(40), nullable=False, default="receptionist")
    active = db.Column(db.Boolean, default=True)

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)

class RoomCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=2)
    description = db.Column(db.Text, default="")
    base_price = db.Column(db.Numeric(10,2), nullable=False, default=0)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=False)
    floor = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default="available")
    category_id = db.Column(db.Integer, db.ForeignKey("room_category.id"), nullable=False)
    category = db.relationship("RoomCategory", backref="rooms")

class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(160), default="")
    document = db.Column(db.String(100), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey("guest.id"), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), default="confirmed")
    source = db.Column(db.String(40), default="website")
    adults = db.Column(db.Integer, default=1)
    children = db.Column(db.Integer, default=0)
    total = db.Column(db.Numeric(10,2), default=0)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    room = db.relationship("Room")
    guest = db.relationship("Guest")
    payments = db.relationship("Payment", backref="booking", cascade="all, delete-orphan")

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    amount = db.Column(db.Numeric(10,2), nullable=False)
    method = db.Column(db.String(30), default="cash")
    status = db.Column(db.String(30), default="paid")
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)

class Tariff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("room_category.id"))
    price = db.Column(db.Numeric(10,2), nullable=False)
    season = db.Column(db.String(80), default="Базовый")
    active = db.Column(db.Boolean, default=True)
    category = db.relationship("RoomCategory")

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(160), nullable=False)
    entity = db.Column(db.String(80), default="")
    entity_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User")
