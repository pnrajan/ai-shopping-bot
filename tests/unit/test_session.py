from ai_shopping_bot.contracts.context import SessionState
from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.session.store import InMemorySessionStore, SQLiteSessionStore


def _roundtrip(store):
    s = store.get("c1")
    assert s.last_products == [] and s.clarifications_asked == 0
    s.last_products = [Product(title="X", price=1.0)]
    s.clarifications_asked = 1
    store.put(s)
    again = store.get("c1")
    assert again.last_products[0].title == "X"
    assert again.clarifications_asked == 1
    assert again.updated_at > 0


def test_memory_store_roundtrip():
    _roundtrip(InMemorySessionStore())


def test_memory_store_returns_copies():
    store = InMemorySessionStore()
    s = store.get("c")
    s.clarifications_asked = 5
    assert store.get("c").clarifications_asked == 0


def test_sqlite_store_survives_reopen(tmp_path):
    path = str(tmp_path / "s.db")
    _roundtrip(SQLiteSessionStore(path))
    assert SQLiteSessionStore(path).get("c1").last_products[0].title == "X"


def test_session_state_defaults_independent():
    a, b = SessionState(conversation_id="a"), SessionState(conversation_id="b")
    a.turns.append({"role": "user", "content": "x"})
    assert b.turns == []
