from datetime import datetime

def today():
    return datetime.now().strftime("%d.%m.%Y")

def parse_iso_date(value):
    return datetime.strptime(value, "%Y-%m-%d")

def format_rub(value):
    return f"{value:,.0f}".replace(",", " ") + " ₽"
