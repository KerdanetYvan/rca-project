import pytest
from datetime import datetime, timezone

import psycopg2

from app import app, search_history


class DummyCursor:
    def __init__(self, fetchone=None, fetchall=None, rowcount=0, fail_execute=False):
        self._fetchone = fetchone
        self._fetchall = fetchall
        self.rowcount = rowcount
        self.queries = []
        self.params = []
        self.fail_execute = fail_execute

    def execute(self, query, params=None):
        if self.fail_execute:
            raise Exception("db error")
        self.queries.append(query)
        self.params.append(params)

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall


class DummyDB:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def close(self):
        pass


class DummyRedis:
    def __init__(self, **kw):
        self.store = {}
        self.locked = False
        self.ping_ok = True
        self.stats = None

    def setnx(self, key, value):
        if self.locked:
            return False
        self.locked = True
        return True

    def expire(self, key, seconds):
        pass

    def delete(self, key):
        self.locked = False
        if key in self.store:
            del self.store[key]

    def ping(self):
        if not self.ping_ok:
            raise Exception("redis down")
        return True

    def get(self, key):
        return self.stats

    def setex(self, key, ttl, value):
        self.stats = value


@pytest.fixture(autouse=True)
def disable_logging(monkeypatch):
    monkeypatch.setattr(app, "logger", app.logger or type("l", (), {"info": lambda *a, **k: None, "warning": lambda *a, **k: None, "error": lambda *a, **k: None}))


@pytest.fixture

def client(monkeypatch):
    client = app.test_client()
    return client



def patch_db_redis(monkeypatch, db_cursor=None, redis_instance=None):
    if db_cursor is None:
        db_cursor = DummyCursor(fetchone={}, fetchall=[], rowcount=0)
    db = DummyDB(db_cursor)
    monkeypatch.setattr(app, "get_db", lambda: db)
    if redis_instance is None:
        redis_instance = DummyRedis()
    monkeypatch.setattr(app, "get_redis", lambda: redis_instance)
    return db_cursor, redis_instance



def test_health_ok(client, monkeypatch):
    patch_db_redis(monkeypatch)
    rv = client.get("/health")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"


def test_health_db_down(client, monkeypatch):
    cursor = DummyCursor(fail_execute=True)
    patch_db_redis(monkeypatch, db_cursor=cursor)
    rv = client.get("/health")
    assert rv.status_code == 503
    data = rv.get_json()
    assert data["status"] == "error"
    assert data["database"] == "down"


def test_health_redis_down(client, monkeypatch):
    redis_inst = DummyRedis()
    redis_inst.ping_ok = False
    patch_db_redis(monkeypatch, redis_instance=redis_inst)
    rv = client.get("/health")
    assert rv.status_code == 503
    data = rv.get_json()
    assert data["status"] == "error"
    assert data["redis"] == "down"


def test_list_tasks_filters(client, monkeypatch):
    cursor = DummyCursor(fetchone=None, fetchall=[{"id": 5, "title": "foo", "description": "", "is_active": True, "created_at": datetime(2026,1,1, tzinfo=timezone.utc), "updated_at": None}])
    patch_db_redis(monkeypatch, db_cursor=cursor)

    # no params
    rv = client.get("/api/tasks")
    assert rv.status_code == 200
    assert len(rv.get_json()) == 1
    assert "ORDER BY" in cursor.queries[-1]

    rv = client.get("/api/tasks?status=active")
    assert "is_active = true" in cursor.queries[-1]

    # filter today with invalid tz -> fallback
    rv = client.get("/api/tasks?today=2026-03-05&tz=NotATZ")
    assert "DATE(created_at) = CURRENT_DATE" in cursor.queries[-1]


def test_create_task_missing_title(client, monkeypatch):
    patch_db_redis(monkeypatch)
    rv = client.post("/api/tasks", json={})
    assert rv.status_code == 400
    assert "Title is required" in rv.get_json()["error"]


def test_create_task_redis_lock(client, monkeypatch):
    redis_inst = DummyRedis()
    redis_inst.locked = True
    patch_db_redis(monkeypatch, redis_instance=redis_inst)
    rv = client.post("/api/tasks", json={"title": "foo"})
    assert rv.status_code == 409


def test_create_task_db_duplicate(client, monkeypatch):
    # make insert raise IntegrityError
    class C(DummyCursor):
        def execute(self, query, params=None):
            raise psycopg2.IntegrityError()
    cursor = C()
    patch_db_redis(monkeypatch, db_cursor=cursor)
    rv = client.post("/api/tasks", json={"title": "foo"})
    assert rv.status_code == 409


def test_update_task_not_found(client, monkeypatch):
    cursor = DummyCursor(fetchone=None)
    patch_db_redis(monkeypatch, db_cursor=cursor)
    rv = client.put("/api/tasks/999", json={"title": "bar"})
    assert rv.status_code == 404


def test_delete_task_not_found(client, monkeypatch):
    cursor = DummyCursor(rowcount=0)
    patch_db_redis(monkeypatch, db_cursor=cursor)
    rv = client.delete("/api/tasks/123")
    assert rv.status_code == 404


def test_search_tasks_history_and_results(client, monkeypatch):
    cursor = DummyCursor(fetchall=[{"id":1,"title":"abc","description":"","is_active":True,"created_at":datetime.now(timezone.utc)}])
    patch_db_redis(monkeypatch, db_cursor=cursor)
    # clear history
    search_history.clear()
    rv = client.get("/api/search?q=abc")
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data) == 1
    assert len(search_history) == 1
    assert search_history[0]["query"] == "abc"


def test_get_stats_cached_and_db(client, monkeypatch):
    cursor = DummyCursor(fetchone={"total":5,"active":2,"done":3})
    redis_inst = DummyRedis()
    patch_db_redis(monkeypatch, db_cursor=cursor, redis_instance=redis_inst)
    rv = client.get("/api/stats")
    assert rv.status_code == 200
    first = rv.get_json()
    assert first["total"] == 5
    rv2 = client.get("/api/stats")
    assert rv2.get_json() == first
