"""Запросы авторизации, отделённые от HTTP-маршрутов."""


def find_user_by_login(conn, login_value: str, normalized_phone: str = ""):
    """Находит пользователя по точному логину или нормализованному телефону.

    Специальный shortcut «любой admin по слову admin» убран: ищем только
    по полю Логин (и телефону), чтобы при нескольких администраторах
    не отдавать первого попавшегося.
    """
    cursor = conn.cursor()

    # 1) Точное совпадение логина (гости и сотрудники в таблице Пользователи)
    cursor.execute("""
        SELECT u.ID_Клиента, u.Роль, u.Пароль,
               COALESCE(c.Фамилия, s.Фамилия) AS Фамилия,
               COALESCE(c.Имя, s.Имя) AS Имя,
               COALESCE(c.Отчество, s.Отчество) AS Отчество
        FROM Пользователи u
        LEFT JOIN Клиенты c ON u.ID_Клиента = c.ID_Клиента
        LEFT JOIN Сотрудники s ON s.ID_Сотрудника = u.ID_Клиента
        WHERE u.Логин = ?
        LIMIT 1
    """, (login_value,))
    user = cursor.fetchone()
    if user:
        return user

    # 2) Логин без учёта регистра для не-телефонных значений (например Admin)
    if login_value and not any(ch.isdigit() for ch in login_value):
        cursor.execute("""
            SELECT u.ID_Клиента, u.Роль, u.Пароль,
                   COALESCE(c.Фамилия, s.Фамилия) AS Фамилия,
                   COALESCE(c.Имя, s.Имя) AS Имя,
                   COALESCE(c.Отчество, s.Отчество) AS Отчество
            FROM Пользователи u
            LEFT JOIN Клиенты c ON u.ID_Клиента = c.ID_Клиента
            LEFT JOIN Сотрудники s ON s.ID_Сотрудника = u.ID_Клиента
            WHERE lower(u.Логин) = lower(?)
            LIMIT 1
        """, (login_value,))
        user = cursor.fetchone()
        if user:
            return user

    if not normalized_phone:
        return None

    # 3) Нормализованный телефон как логин
    cursor.execute("""
        SELECT u.ID_Клиента, u.Роль, u.Пароль,
               COALESCE(c.Фамилия, s.Фамилия) AS Фамилия,
               COALESCE(c.Имя, s.Имя) AS Имя,
               COALESCE(c.Отчество, s.Отчество) AS Отчество
        FROM Пользователи u
        LEFT JOIN Клиенты c ON u.ID_Клиента = c.ID_Клиента
        LEFT JOIN Сотрудники s ON s.ID_Сотрудника = u.ID_Клиента
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            u.Логин,' ',''),'-',''),'(',''),')',''),'.',''), '+', '') = REPLACE(?, '+', '')
        LIMIT 1
    """, (normalized_phone,))
    user = cursor.fetchone()
    if user:
        return user

    # 4) Сотрудник-админ по телефону (если учётки ещё нет в Пользователи)
    cursor.execute("""
        SELECT ID_Сотрудника AS ID_Клиента, 'admin' AS Роль, Пароль,
               Фамилия, Имя, Отчество
        FROM Сотрудники
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            Телефон,' ',''),'-',''),'(',''),')',''),'.',''), '+', '') = REPLACE(?, '+', '')
          AND Должность IN ('Администратор','Управляющий')
        LIMIT 1
    """, (normalized_phone,))
    return cursor.fetchone()
