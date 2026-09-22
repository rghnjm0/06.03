ROOMS = [
    {"number": "101", "category": "Стандарт", "beds": 2, "price": 4500, "status": "Свободен"},
    {"number": "102", "category": "Стандарт", "beds": 2, "price": 4500, "status": "Занят"},
    {"number": "201", "category": "Комфорт", "beds": 2, "price": 6200, "status": "Свободен"},
    {"number": "202", "category": "Комфорт", "beds": 3, "price": 6800, "status": "Уборка"},
    {"number": "301", "category": "Люкс", "beds": 2, "price": 9500, "status": "Свободен"},
    {"number": "302", "category": "Люкс", "beds": 3, "price": 10500, "status": "Занят"},
]

BOOKINGS = [
    {"id": 1, "guest": "Иван Петров", "room": "102", "checkin": "18.09.2026", "checkout": "21.09.2026", "status": "Подтверждено", "amount": 13500},
    {"id": 2, "guest": "Анна Смирнова", "room": "302", "checkin": "20.09.2026", "checkout": "23.09.2026", "status": "Ожидает оплаты", "amount": 31500},
    {"id": 3, "guest": "Дмитрий Волков", "room": "201", "checkin": "17.09.2026", "checkout": "19.09.2026", "status": "Заезд", "amount": 12400},
]

GUESTS = [
    {"name": "Иван Петров", "phone": "+7 900 123-45-67", "visits": 4, "last": "18.09.2026"},
    {"name": "Анна Смирнова", "phone": "+7 901 222-33-44", "visits": 2, "last": "20.09.2026"},
    {"name": "Дмитрий Волков", "phone": "+7 902 555-66-77", "visits": 1, "last": "17.09.2026"},
]
