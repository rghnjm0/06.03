"""Интерактивная утилита для восстановления доступа администратора и гостя.
Запускать из корня проекта: python reset_access.py
"""
import os
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get('UYUT_DB_PATH', os.path.join(os.path.dirname(__file__), 'hotel_management.db'))


def read_password(prompt):
    while True:
        value = getpass(prompt)
        if len(value) < 12:
            print('Пароль должен содержать не менее 12 символов.')
            continue
        confirm = getpass('Повторите пароль: ')
        if value != confirm:
            print('Пароли не совпадают.')
            continue
        return generate_password_hash(value)


def main():
    if not os.path.isfile(DB_PATH):
        raise SystemExit(f'База данных не найдена: {DB_PATH}. Укажите UYUT_DB_PATH.')
    print('ВНИМАНИЕ: будут изменены только пароли выбранных аккаунтов. Остальные данные сохраняются.')
    print(f'База: {DB_PATH}')
    choice = input('Что настроить? [1] Администратор [2] Гость [3] Оба: ').strip()
    if choice not in {'1', '2', '3'}:
        raise SystemExit('Выберите 1, 2 или 3.')

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('BEGIN IMMEDIATE')
        if choice in {'1', '3'}:
            password_hash = read_password('Новый пароль администратора: ')
            admin = conn.execute("SELECT ID_Клиента FROM Пользователи WHERE Роль='admin' LIMIT 1").fetchone()
            if not admin:
                raise RuntimeError('Администратор не найден. Сначала создайте администратора штатным способом.')
            admin_id = admin[0]
            conn.execute("UPDATE Пользователи SET Пароль=? WHERE ID_Клиента=? AND Роль='admin'", (password_hash, admin_id))
            print('Пароль администратора обновлён.')
        if choice in {'2', '3'}:
            login = input('Логин гостя (обычно номер телефона): ').strip()
            password_hash = read_password('Новый пароль гостя: ')
            cur = conn.execute("UPDATE Пользователи SET Пароль=? WHERE Логин=? AND Роль='client'", (password_hash, login))
            if cur.rowcount != 1:
                raise RuntimeError('Гость не найден по указанному логину. Изменения будут отменены.')
            print('Пароль гостя обновлён.')
        conn.commit()
        print('Готово. Теперь войдите через страницу /login.')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
