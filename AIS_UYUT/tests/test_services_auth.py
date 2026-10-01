from services.auth import find_user_by_login


def test_find_user_by_login(memory_db):
    memory_db.execute("INSERT INTO Пользователи VALUES (?,?,?,?)", ('CL001','client','hash','guest@example.test'))
    row = find_user_by_login(memory_db, 'guest@example.test')
    assert row['ID_Клиента'] == 'CL001'


def test_unknown_user_returns_none(memory_db):
    assert find_user_by_login(memory_db, 'missing') is None


def test_login_lookup_uses_parameterized_value(memory_db):
    # A SQL-looking login must be treated as data, not executable SQL.
    assert find_user_by_login(memory_db, "' OR 1=1 --") is None


def test_login_lookup_returns_none_for_empty_database(memory_db):
    assert find_user_by_login(memory_db, "guest@example.test") is None
