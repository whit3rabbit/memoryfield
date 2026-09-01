import pytest

from mf import db, schema


def test_init_field_creates_sqlite_file(tmp_path):
    db_path = db.init_field(tmp_path)
    assert db_path == tmp_path / "mf.sqlite3"
    assert db_path.exists()


def test_init_field_sets_config(tmp_path):
    db.init_field(tmp_path, model_code="nomic-embed-text-v1.5", embedding_dim=768)
    conn = db.open_field(tmp_path)
    assert schema.get_config(conn, "model_code") == "nomic-embed-text-v1.5"
    assert schema.get_config(conn, "embedding_dim") == "768"
    assert schema.get_config(conn, "schema_version") == str(schema.SCHEMA_VERSION)
    conn.close()


def test_init_field_refuses_to_overwrite_existing(tmp_path):
    db.init_field(tmp_path)
    with pytest.raises(db.FieldExistsError):
        db.init_field(tmp_path)


def test_open_field_without_init_raises(tmp_path):
    with pytest.raises(db.FieldNotFoundError):
        db.open_field(tmp_path)


def test_connect_loads_sqlite_vec(tmp_path):
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    version, = conn.execute("select vec_version()").fetchone()
    assert version
    conn.close()
