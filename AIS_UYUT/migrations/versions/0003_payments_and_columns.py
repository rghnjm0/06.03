"""Payments table, maintenance column, notification title, extra rooms seed.

Revision ID: 0003_payments
Revises: 0002_extended
"""
from alembic import op

revision = "0003_payments"
down_revision = "0002_extended"
branch_labels = None
depends_on = None


def upgrade():
    # Payment records (was ensure_payment_schema)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Платежи (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Бронирования TEXT NOT NULL,
            Провайдер TEXT NOT NULL,
            ID_Платежа TEXT UNIQUE NOT NULL,
            Сумма REAL NOT NULL,
            Статус TEXT NOT NULL,
            Ссылка_на_оплату TEXT,
            Создано TEXT NOT NULL,
            Обновлено TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_booking ON Платежи(ID_Бронирования)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON Платежи(Статус)")

    # Room maintenance status (was ensure_features_schema ALTER)
    # SQLite: add column only if missing via PRAGMA check in batch-safe way.
    conn = op.get_bind()
    cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(Номера)").fetchall()]
    if "Статус_обслуживания" not in cols:
        op.execute("ALTER TABLE Номера ADD COLUMN Статус_обслуживания TEXT DEFAULT ''")

    # Notifications: ensure Заголовок exists (features schema)
    notif_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(Уведомления)").fetchall()]
    if notif_cols and "Заголовок" not in notif_cols:
        op.execute("ALTER TABLE Уведомления ADD COLUMN Заголовок TEXT DEFAULT ''")

    # Seed extra rooms (was ensure_extra_rooms) — INSERT OR IGNORE
    extra_rooms = [
        ("RM011", "402", "Люкс", 4, 9000.00, "Свободен", 4, "402.jpg"),
        ("RM012", "403", "Люкс", 4, 9500.00, "Свободен", 4, "403.jpg"),
        ("RM013", "404", "Премиум", 2, 10500.00, "Свободен", 4, "404.jpg"),
        ("RM014", "405", "Премиум", 3, 11000.00, "Свободен", 4, "405.jpg"),
        ("RM015", "406", "Апартаменты", 5, 13500.00, "Свободен", 4, "406.jpg"),
    ]
    for room in extra_rooms:
        conn.exec_driver_sql(
            """INSERT OR IGNORE INTO Номера
               (ID_Номера, Номер_Комнаты, Категория, Вместимость, Цена_за_сутки, Статус, Этаж, Изображение)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            room,
        )

    services = [
        ("SRV001", "Завтрак", "Шведский стол", 900),
        ("SRV002", "Парковка", "Место на охраняемой парковке", 500),
        ("SRV003", "Трансфер", "Трансфер из/в аэропорт", 1800),
        ("SRV004", "Поздний выезд", "Выезд до 18:00", 1500),
        ("SRV005", "Дополнительное место", "Раскладная кровать", 1200),
        ("SRV006", "Романтический пакет", "Украшение номера и комплимент", 2500),
        ("SRV007", "Кофейный набор", "Кофе и чай в номер", 450),
        ("SRV008", "Ранний заезд", "Заезд с 10:00 при наличии номера", 1200),
    ]
    for sid, name, desc, price in services:
        conn.exec_driver_sql(
            "INSERT OR IGNORE INTO Услуги(ID_Услуги,Название,Описание,Цена) VALUES(?,?,?,?)",
            (sid, name, desc, price),
        )

    for code, discount, limit in [("UYUT10", 10, 0), ("WELCOME5", 5, 100), ("FAMILY15", 15, 50)]:
        conn.exec_driver_sql(
            "INSERT OR IGNORE INTO Промокоды(Код,Скидка,Лимит) VALUES(?,?,?)",
            (code, discount, limit),
        )


def downgrade():
    op.execute('DROP TABLE IF EXISTS "Платежи"')
