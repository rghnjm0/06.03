# db.py
import sqlite3
import os
from datetime import datetime, timedelta

# Имя файла базы данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "hotel_management.db")


def get_db():
    """Открывает SQLite-соединение с доступом к строкам по именам колонок."""
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


from contextlib import contextmanager


@contextmanager
def db_session(commit=False):
    """Контекстный менеджер: открывает соединение, при исключении — rollback, всегда close.

    commit=True — коммитит при успешном выходе из блока.
    """
    conn = get_db()
    try:
        yield conn
        if commit:
            conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('db_session rollback failed', exc_info=True)
        raise
    finally:
        try:
            conn.close()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('db_session close failed', exc_info=True)



def create_database():
    """Создает базу данных и все таблицы"""

    # Никогда не уничтожаем существующую БД неявно: это приводило к потере данных.
    if os.path.exists(DB_NAME):
        raise FileExistsError(
            f"База данных уже существует: {DB_NAME}. "
            "Для обновления используйте миграции; удаление выполняйте отдельной "
            "резервируемой административной операцией."
        )

    # Подключаемся к новой БД (создается новый файл)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Включаем поддержку внешних ключей
    cursor.execute("PRAGMA foreign_keys = ON")

    print("Создание таблиц базы данных...")

    # 1. Таблица Сотрудники
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Сотрудники (
        Код INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_Сотрудника TEXT UNIQUE NOT NULL,
        Фамилия TEXT NOT NULL,
        Имя TEXT NOT NULL,
        Отчество TEXT,
        Телефон TEXT,
        Должность TEXT NOT NULL,
        Логин TEXT UNIQUE,
        Пароль TEXT
    )
    ''')

    # 2. Таблица Клиенты
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Клиенты (
        Код INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_Клиента TEXT UNIQUE NOT NULL,
        Фамилия TEXT NOT NULL,
        Имя TEXT NOT NULL,
        Отчество TEXT,
        Телефон TEXT NOT NULL,
        Дата_рождения TEXT,
        Адрес TEXT
    )
    ''')

    # 3. Таблица Номера
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Номера (
        Код INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_Номера TEXT UNIQUE NOT NULL,
        Номер_Комнаты TEXT NOT NULL UNIQUE,
        Категория TEXT NOT NULL,
        Вместимость INTEGER NOT NULL,
        Цена_за_сутки REAL NOT NULL,
        Статус TEXT DEFAULT 'Свободен',
        Этаж INTEGER,
        Изображение TEXT DEFAULT 'default-room.jpg'
    )
    ''')

    # 4. Таблица Бронирования
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Бронирования (
        Код INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_Бронирования TEXT UNIQUE NOT NULL,
        ID_Клиента TEXT NOT NULL,
        ID_Номера TEXT NOT NULL,
        ID_Сотрудника TEXT,
        Дата_бронирования TEXT DEFAULT CURRENT_DATE,
        Дата_заезда TEXT NOT NULL,
        Дата_выезда TEXT NOT NULL,
        Количество_гостей INTEGER NOT NULL,
        Статус TEXT DEFAULT 'Подтверждено',
        Предоплата REAL DEFAULT 0,
        FOREIGN KEY (ID_Клиента) REFERENCES Клиенты(ID_Клиента),
        FOREIGN KEY (ID_Номера) REFERENCES Номера(ID_Номера),
        FOREIGN KEY (ID_Сотрудника) REFERENCES Сотрудники(ID_Сотрудника)
    )
    ''')

    # 5. Таблица Счета
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Счета (
        Код INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_Счета TEXT UNIQUE NOT NULL,
        ID_Бронирования TEXT NOT NULL,
        Дата_выставления TEXT DEFAULT CURRENT_DATE,
        Сумма_проживание REAL DEFAULT 0,
        Способ_оплаты TEXT,
        Оплачено INTEGER DEFAULT 0,
        Дата_оплаты TEXT,
        FOREIGN KEY (ID_Бронирования) REFERENCES Бронирования(ID_Бронирования)
    )
    ''')

    # 6. Таблица Пользователи (для авторизации)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Пользователи (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_Клиента TEXT UNIQUE,
        Логин TEXT UNIQUE,
        Пароль TEXT NOT NULL,
        Роль TEXT DEFAULT 'client'
    )
    ''')

    print("✓ Все таблицы успешно созданы")

    print("Создание индексов...")

    # Индексы для ускорения поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bronirovania_dates ON Бронирования(Дата_заезда, Дата_выезда)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bronirovania_status ON Бронирования(Статус)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nomera_status ON Номера(Статус)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_klienti_telefon ON Клиенты(Телефон)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scheta_bronirovanie ON Счета(ID_Бронирования)')

    print("✓ Индексы созданы")

    # Сохраняем изменения
    conn.commit()

    return conn, cursor


def insert_test_data(cursor):
    """Добавляет тестовые данные с хэшированными паролями."""
    from werkzeug.security import generate_password_hash
    print("Заполнение тестовыми данными...")

    # Demo credentials are supplied through environment variables instead of being stored in source.
    import secrets
    demo_guest_password = os.environ.get('UYUT_DEMO_GUEST_PASSWORD') or secrets.token_urlsafe(18)
    demo_employee_password = os.environ.get('UYUT_DEMO_EMPLOYEE_PASSWORD') or secrets.token_urlsafe(18)
    # Never write credentials to stdout/logs. Set UYUT_DEMO_GUEST_PASSWORD and
    # UYUT_DEMO_EMPLOYEE_PASSWORD before initializing a fresh development DB.

    # ===== 1. СОТРУДНИКИ =====
    employees = [
        ('EMP001', 'Иванова', 'Анна', 'Петровна', '+7(999)123-45-67', 'Администратор', 'anna_i', demo_employee_password),
        ('EMP002', 'Петров', 'Сергей', 'Иванович', '+7(999)234-56-78', 'Администратор', 'sergey_p', demo_employee_password),
        ('EMP003', 'Сидорова', 'Елена', 'Сергеевна', '+7(999)345-67-89', 'Горничная', 'elena_s', demo_employee_password),
        ('EMP004', 'Козлов', 'Дмитрий', 'Алексеевич', '+7(999)456-78-90', 'Управляющий', 'dmitry_k', demo_employee_password),
        ('EMP005', 'Морозова', 'Ольга', 'Владимировна', '+7(999)567-89-01', 'Горничная', 'olga_m', demo_employee_password),
    ]

    employees = [(*row[:-1], generate_password_hash(row[-1])) for row in employees]
    cursor.executemany('''
        INSERT INTO Сотрудники (ID_Сотрудника, Фамилия, Имя, Отчество, Телефон, Должность, Логин, Пароль)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', employees)

    # ===== 2. КЛИЕНТЫ =====
    clients = [
        ('CL001', 'Смирнов', 'Алексей', 'Игоревич', '+7(911)111-11-11', '1985-05-15', 'Москва, ул. Ленина 10-5'),
        ('CL002', 'Кузнецова', 'Елена', 'Дмитриевна', '+7(911)222-22-22', '1990-08-22', 'СПб, Невский пр. 20-15'),
        ('CL003', 'Попов', 'Андрей', 'Сергеевич', '+7(911)333-33-33', '1982-03-10', 'Казань, ул. Баумана 5-3'),
        ('CL004', 'Васильева', 'Татьяна', 'Александровна', '+7(911)444-44-44', '1995-11-30',
         'Екатеринбург, ул. Ленина 15-7'),
        ('CL005', 'Михайлов', 'Денис', 'Олегович', '+7(911)555-55-55', '1988-07-18', 'Новосибирск, ул. Советская 30-2'),
    ]

    cursor.executemany('''
        INSERT INTO Клиенты (ID_Клиента, Фамилия, Имя, Отчество, Телефон, Дата_рождения, Адрес)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', clients)

    # ===== 3. НОМЕРА =====
    rooms = [
        ('RM001', '101', 'Стандарт', 2, 3500.00, 'Свободен', 1, '101.webp'),
        ('RM002', '102', 'Стандарт', 2, 3500.00, 'Свободен', 1, None),
        ('RM003', '103', 'Стандарт Плюс', 2, 3800.00, 'Свободен', 1, '103.jpg'),
        ('RM004', '104', 'Стандарт Плюс', 2, 3800.00, 'Свободен', 1, '104.jpg'),
        ('RM005', '201', 'Полулюкс', 3, 5000.00, 'Свободен', 2, '201.jpg'),
        ('RM006', '202', 'Полулюкс', 3, 5200.00, 'Свободен', 2, None),
        ('RM007', '203', 'Полулюкс', 3, 5200.00, 'Свободен', 2, '203.jpg'),
        ('RM008', '301', 'Люкс', 4, 8000.00, 'Свободен', 3, '301.jpg'),
        ('RM009', '302', 'Люкс', 4, 8500.00, 'Свободен', 3, None),
        ('RM010', '401', 'Апартаменты', 5, 12000.00, 'Свободен', 4, None),
        ('RM011', '402', 'Люкс', 4, 9000.00, 'Свободен', 4, '402.jpg'),
        ('RM012', '403', 'Люкс', 4, 9500.00, 'Свободен', 4, '403.jpg'),
        ('RM013', '404', 'Премиум', 2, 10500.00, 'Свободен', 4, '404.jpg'),
        ('RM014', '405', 'Премиум', 3, 11000.00, 'Свободен', 4, '405.jpg'),
        ('RM015', '406', 'Апартаменты', 5, 13500.00, 'Свободен', 4, '406.jpg'),
    ]

    cursor.executemany('''
        INSERT INTO Номера (ID_Номера, Номер_Комнаты, Категория, Вместимость, Цена_за_сутки, Статус, Этаж, Изображение)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', rooms)

    # ===== 4. ПОЛЬЗОВАТЕЛИ (клиенты) =====
    users = [
        ('CL001', '+7(911)111-11-11', demo_guest_password, 'client'),
        ('CL002', '+7(911)222-22-22', demo_guest_password, 'client'),
        ('CL003', '+7(911)333-33-33', demo_guest_password, 'client'),
        ('CL004', '+7(911)444-44-44', demo_guest_password, 'client'),
        ('CL005', '+7(911)555-55-55', demo_guest_password, 'client'),
    ]

    users = [(*row[:2], generate_password_hash(row[2]), row[3]) for row in users]
    cursor.executemany('''
        INSERT INTO Пользователи (ID_Клиента, Логин, Пароль, Роль)
        VALUES (?, ?, ?, ?)
    ''', users)

    # ===== 5. БРОНИРОВАНИЯ =====
    today = datetime.now().date()

    bookings = [
        ('BR001', 'CL001', 'RM001', 'EMP001',
         str(today - timedelta(days=5)),
         str(today - timedelta(days=2)),
         str(today + timedelta(days=3)),
         2, 'Заселен', 3500.00),

        ('BR002', 'CL002', 'RM005', 'EMP002',
         str(today - timedelta(days=2)),
         str(today),
         str(today + timedelta(days=5)),
         3, 'Заселен', 5000.00),
    ]

    cursor.executemany('''
        INSERT INTO Бронирования (ID_Бронирования, ID_Клиента, ID_Номера, ID_Сотрудника, 
        Дата_бронирования, Дата_заезда, Дата_выезда, Количество_гостей, Статус, Предоплата)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', bookings)

    # ===== 6. СЧЕТА =====
    invoices = [
        ('INV001', 'BR001', str(today - timedelta(days=2)), 17500.00, 'Карта', 0, None),
        ('INV002', 'BR002', str(today), 25000.00, 'Наличные', 0, None),
    ]

    cursor.executemany('''
        INSERT INTO Счета (ID_Счета, ID_Бронирования, Дата_выставления, Сумма_проживание, 
                          Способ_оплаты, Оплачено, Дата_оплаты)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', invoices)

    print("✓ Тестовые данные добавлены")


def add_admin_user():
    """Однократно создаёт bootstrap-администратора с непредсказуемым паролем."""
    import secrets
    from werkzeug.security import generate_password_hash

    password = os.environ.get("UYUT_BOOTSTRAP_ADMIN_PASSWORD")
    if not password:
        password = secrets.token_urlsafe(24)
        # Never print secrets to stdout (systemd journal / Docker logs).
        secrets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secrets")
        os.makedirs(secrets_dir, exist_ok=True)
        secret_path = os.path.join(secrets_dir, "admin_bootstrap.txt")
        with open(secret_path, "w", encoding="utf-8") as fh:
            fh.write(password + "\n")
        try:
            os.chmod(secret_path, 0o600)
        except OSError:
            pass
        print(
            f"\nВАЖНО: создан временный пароль администратора. "
            f"Он записан в {secret_path} (права 600). "
            f"Смените пароль после первого входа; файл можно удалить.\n"
        )
    if len(password) < 12:
        raise ValueError("UYUT_BOOTSTRAP_ADMIN_PASSWORD должен содержать минимум 12 символов")

    conn = get_db()
    try:
        admin_hash = generate_password_hash(password)
        conn.execute("""
            INSERT OR IGNORE INTO Сотрудники
            (ID_Сотрудника, Фамилия, Имя, Отчество, Телефон, Должность, Логин, Пароль)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('ADM001', 'Администратор', 'Системный', '', '', 'Администратор', 'admin', admin_hash))
        conn.commit()
    finally:
        conn.close()


def ensure_database_ready():
    """Создаёт локальную БД только при первом запуске; существующие данные не трогает."""
    if not os.path.exists(DB_NAME):
        if os.environ.get("UYUT_ENV", "development").lower() == "production":
            raise RuntimeError("Production database is missing; provision it through an explicit deployment/migration step")
        conn, cursor = create_database()
        try:
            insert_test_data(cursor)
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            raise
        conn.close()
        add_admin_user()


def main():
    """Главная функция"""
    try:
        # Создаем базу данных и таблицы
        conn, cursor = create_database()

        # Добавляем тестовые данные
        insert_test_data(cursor)

        # Сохраняем изменения
        conn.commit()
        conn.close()

        # Добавляем администратора отдельно
        add_admin_user()

        # Подключаемся снова для статистики
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Выводим статистику по таблицам
        print("\n📊 Статистика по таблицам:")
        tables = ['Сотрудники', 'Клиенты', 'Номера', 'Бронирования', 'Счета', 'Пользователи']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} записей")

        conn.close()

        print("\n" + "=" * 60)
        print(f"✅ База данных '{DB_NAME}' успешно создана!")
        print(f"📁 Расположение: {os.path.abspath(DB_NAME)}")
        print("=" * 60)
        print("\n🔑 Данные для входа:")
        print("\n📍 Админ-панель: /admin/dashboard (после входа)")

    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    main()