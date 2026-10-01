import sqlite3
import pytest


@pytest.fixture
def memory_db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE Бронирования (
        ID_Бронирования TEXT PRIMARY KEY, ID_Номера TEXT NOT NULL,
        Дата_заезда TEXT NOT NULL, Дата_выезда TEXT NOT NULL, Статус TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE Пользователи (
        ID_Клиента TEXT, Роль TEXT, Пароль TEXT, Логин TEXT
    )''')
    conn.execute('''CREATE TABLE Клиенты (
        ID_Клиента TEXT, Фамилия TEXT, Имя TEXT, Отчество TEXT
    )''')
    conn.execute('''CREATE TABLE Сотрудники (
        ID_Сотрудника TEXT, Фамилия TEXT, Имя TEXT, Отчество TEXT,
        Телефон TEXT, Должность TEXT, Пароль TEXT
    )''')
    yield conn
    conn.close()
