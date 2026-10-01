import sqlite3
import pytest
from utils import next_id


@pytest.fixture
def id_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Клиенты (ID_Клиента TEXT PRIMARY KEY)")
    yield conn
    conn.close()


def test_next_id_starts_at_one(id_db):
    assert next_id(id_db, "Клиенты", "CL", "ID_Клиента") == "CL001"


def test_next_id_uses_maximum_not_row_count(id_db):
    id_db.executemany("INSERT INTO Клиенты VALUES (?)", [("CL001",), ("CL009",)])
    assert next_id(id_db, "Клиенты", "CL", "ID_Клиента") == "CL010"


@pytest.mark.parametrize(
    "table,field,prefix",
    [("Клиенты; DROP TABLE Клиенты", "ID_Клиента", "CL"),
     ("Клиенты", "Несуществующее", "CL"),
     ("Клиенты", "ID_Клиента", "CL-"),
     ("Клиенты", "ID_Клиента", "CL%")],
)
def test_next_id_rejects_untrusted_identifiers(id_db, table, field, prefix):
    with pytest.raises(ValueError):
        next_id(id_db, table, prefix, field)
