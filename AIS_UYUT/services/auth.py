"""Запросы авторизации, отделённые от HTTP-маршрутов."""


def find_user_by_login(conn, login_value: str, normalized_phone: str = ""):
    """Находит пользователя по логину или нормализованному телефону."""
    cursor = conn.cursor()
    if login_value.casefold() == "admin":
        cursor.execute("""
            SELECT u.ID_Клиента, u.Роль, u.Пароль,
                   s.Фамилия, s.Имя, s.Отчество
            FROM Пользователи u
            LEFT JOIN Сотрудники s ON s.ID_Сотрудника = u.ID_Клиента
            WHERE u.Роль = 'admin'
            ORDER BY u.ID_Клиента
            LIMIT 1
        """)
        return cursor.fetchone()

    cursor.execute("""
        SELECT u.ID_Клиента, u.Роль, u.Пароль,
               c.Фамилия, c.Имя, c.Отчество
        FROM Пользователи u
        LEFT JOIN Клиенты c ON u.ID_Клиента = c.ID_Клиента
        WHERE u.Логин = ?
    """, (login_value,))
    user = cursor.fetchone()
    if user or not normalized_phone:
        return user

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
    """, (normalized_phone,))
    user = cursor.fetchone()
    if user:
        return user

    cursor.execute("""
        SELECT ID_Сотрудника AS ID_Клиента, 'admin' AS Роль, Пароль,
               Фамилия, Имя, Отчество
        FROM Сотрудники
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            Телефон,' ',''),'-',''),'(',''),')',''),'.',''), '+', '') = REPLACE(?, '+', '')
          AND Должность IN ('Администратор','Управляющий')
    """, (normalized_phone,))
    return cursor.fetchone()
