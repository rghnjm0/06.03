"""Extended schema: services, audit log, favorites, reviews, promocodes, gallery.

Revision ID: 0002_extended
Revises: 0001_baseline
"""
from alembic import op

revision = "0002_extended"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS Услуги (
            ID_Услуги TEXT PRIMARY KEY,
            Название TEXT NOT NULL UNIQUE,
            Описание TEXT,
            Цена REAL NOT NULL DEFAULT 0,
            Активна INTEGER NOT NULL DEFAULT 1
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Бронирование_Услуги (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Бронирования TEXT NOT NULL,
            ID_Услуги TEXT NOT NULL,
            Количество INTEGER NOT NULL DEFAULT 1,
            Цена REAL NOT NULL DEFAULT 0,
            UNIQUE(ID_Бронирования, ID_Услуги)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Журнал_действий (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Время TEXT NOT NULL,
            Пользователь TEXT,
            Роль TEXT,
            Действие TEXT NOT NULL,
            Объект TEXT,
            Детали TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON Журнал_действий(Время)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS Избранное (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Клиента TEXT NOT NULL,
            ID_Номера TEXT NOT NULL,
            UNIQUE(ID_Клиента, ID_Номера)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Отзывы (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Клиента TEXT NOT NULL,
            ID_Номера TEXT NOT NULL,
            ID_Бронирования TEXT,
            Оценка INTEGER NOT NULL,
            Текст TEXT,
            Создано TEXT,
            Опубликовано INTEGER NOT NULL DEFAULT 1
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Промокоды (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Код TEXT NOT NULL UNIQUE,
            Скидка REAL NOT NULL,
            Лимит INTEGER DEFAULT 0,
            Использовано INTEGER DEFAULT 0,
            Действует_до TEXT,
            Активен INTEGER NOT NULL DEFAULT 1
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Использованные_промокоды (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Код TEXT NOT NULL,
            ID_Клиента TEXT NOT NULL,
            ID_Бронирования TEXT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Галерея_номеров (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Номера TEXT NOT NULL,
            Файл TEXT NOT NULL,
            Подпись TEXT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS Уведомления (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_Клиента TEXT NOT NULL,
            Текст TEXT NOT NULL,
            Создано TEXT,
            Прочитано INTEGER NOT NULL DEFAULT 0
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_hits (
            key TEXT NOT NULL,
            ts REAL NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_key_ts ON rate_limit_hits(key, ts)")


def downgrade():
    for table in (
        "rate_limit_hits", "Уведомления", "Галерея_номеров",
        "Использованные_промокоды", "Промокоды", "Отзывы", "Избранное",
        "Журнал_действий", "Бронирование_Услуги", "Услуги",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
