from . import db
from .models import User, RoomCategory, Room, Tariff, Guest
from werkzeug.security import generate_password_hash

def seed():
    if User.query.first():
        return
    users = [
        ("admin","admin123","Администратор","admin"),
        ("manager","manager123","Менеджер бронирования","manager"),
        ("receptionist","reception123","Сотрудник ресепшн","receptionist"),
        ("accountant","account123","Бухгалтер","accountant"),
    ]
    for u,p,n,r in users:
        db.session.add(User(username=u, password_hash=generate_password_hash(p), full_name=n, role=r))
    cats = [
        ("Стандарт", 2, "Уютный номер с двуспальной кроватью", 4500),
        ("Комфорт", 2, "Просторный номер с рабочей зоной", 6200),
        ("Люкс", 4, "Номер повышенной категории с гостиной", 9500),
    ]
    categories=[]
    for n,c,d,price in cats:
        x=RoomCategory(name=n,capacity=c,description=d,base_price=price); db.session.add(x); categories.append(x)
    db.session.flush()
    nums=[("101",1,0),("102",1,0),("103",1,1),("201",2,1),("202",2,1),("301",3,2),("302",3,2)]
    for num,f,ci in nums:
        db.session.add(Room(number=num,floor=f,category_id=categories[ci].id,status="available"))
    for cat in categories:
        db.session.add(Tariff(name=f"Базовый — {cat.name}",category_id=cat.id,price=cat.base_price))
    db.session.add(Guest(first_name="Иван",last_name="Петров",phone="+7 900 000-00-01",email="ivan@example.com"))
    db.session.commit()
