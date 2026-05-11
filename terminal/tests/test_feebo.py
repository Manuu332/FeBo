"""
tests/test_feebo.py
-------------------
FeBo Terminal v0 — test suite.
Tests: persistence, memory, emotion, reflection, identity, API routes.
"""

import json
import sys
import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Point tests at a temp data directory
TMP_DIR = None

def setup_module(module):
    """Create a temp directory and redirect data/log paths."""
    global TMP_DIR
    TMP_DIR = tempfile.mkdtemp()
    os.environ["FEEBO_DATA_DIR"] = TMP_DIR
    os.environ["FEEBO_LOG_DIR"] = TMP_DIR

    # Make sure project root is importable
    ROOT = Path(__file__).parent.parent
    sys.path.insert(0, str(ROOT))

    # Override paths in modules under test
    import memory.store as ms
    ms.DB_PATH = Path(TMP_DIR) / "memory.db"

    import emotion.state as es
    es.EMOTION_PATH = Path(TMP_DIR) / "emotion.json"

    import identity.profile as ip
    ip.IDENTITY_PATH = Path(TMP_DIR) / "identity.json"

    import reflection.engine as re
    re.LOG_PATH = Path(TMP_DIR) / "reflections.log"


def teardown_module(module):
    shutil.rmtree(TMP_DIR, ignore_errors=True)


# ── Memory tests ──────────────────────────────────────────────────────────────

class TestMemory:
    def setup_method(self):
        from memory.store import init_db
        init_db()

    def test_insert_and_retrieve(self):
        from memory.store import save_memory, get_recent_memories
        rid = save_memory("user", "This is a test memory.", importance=0.7)
        assert isinstance(rid, int) and rid > 0

        memories = get_recent_memories(limit=5)
        texts = [m["message"] for m in memories]
        assert "This is a test memory." in texts

    def test_importance_ordering(self):
        from memory.store import save_memory, get_important_memories
        save_memory("user", "Low importance.", importance=0.1)
        save_memory("user", "High importance!", importance=0.9)

        top = get_important_memories(limit=1)
        assert top[0]["message"] == "High importance!"

    def test_search(self):
        from memory.store import save_memory, search_memories
        save_memory("feebo", "I find quantum mechanics fascinating.")
        results = search_memories("quantum")
        assert any("quantum" in m["message"] for m in results)

    def test_emotion_snapshot_stored(self):
        from memory.store import save_memory, get_recent_memories
        snapshot = {"curiosity": 0.8, "warmth": 0.6}
        save_memory("user", "Emotional memory.", emotion_snapshot=snapshot)
        mems = get_recent_memories(limit=5)
        found = next((m for m in mems if m["message"] == "Emotional memory."), None)
        assert found is not None
        assert found["emotion"].get("curiosity") == 0.8

    def test_memory_count(self):
        from memory.store import save_memory, memory_count
        before = memory_count()
        save_memory("user", "Count test memory.")
        assert memory_count() == before + 1

    def test_retrieve_for_context(self):
        from memory.store import save_memory, retrieve_for_context
        save_memory("user", "I love philosophy and consciousness.", importance=0.8)
        results = retrieve_for_context("philosophy questions", limit=3)
        assert isinstance(results, list)


# ── Emotion tests ─────────────────────────────────────────────────────────────

class TestEmotion:
    def test_load_creates_default(self):
        from emotion.state import load_emotion, BASELINE
        state = load_emotion()
        for key in BASELINE:
            assert key in state
            assert 0.0 <= state[key] <= 1.0

    def test_apply_delta(self):
        from emotion.state import load_emotion, apply_delta
        state = load_emotion()
        before_curiosity = state.get("curiosity", 0.55)
        state = apply_delta(state, {"curiosity": 0.15})
        # After decay + delta, curiosity should have moved
        assert state["curiosity"] != before_curiosity

    def test_clamp_bounds(self):
        from emotion.state import apply_delta, load_emotion
        state = load_emotion()
        # Push way over the top
        state = apply_delta(state, {"curiosity": 999.0})
        assert state["curiosity"] <= 1.0
        state = apply_delta(state, {"curiosity": -999.0})
        assert state["curiosity"] >= 0.0

    def test_dominant_emotion(self):
        from emotion.state import dominant_emotion, BASELINE
        # curiosity baseline=0.55, set to 1.0 → delta=0.45
        # tension  baseline=0.20, set to 0.25 → delta=0.05
        # all others near baseline → curiosity wins clearly
        state = dict(BASELINE)
        state["curiosity"] = 1.0
        state["tension"] = 0.25
        assert dominant_emotion(state) == "curiosity"

    def test_infer_delta_from_text(self):
        from emotion.state import infer_delta_from_text
        delta = infer_delta_from_text("why does this happen? I'm so curious.")
        assert "curiosity" in delta
        assert delta["curiosity"] > 0

    def test_persistence(self):
        from emotion.state import load_emotion, apply_delta, EMOTION_PATH
        state = load_emotion()
        state = apply_delta(state, {"warmth": 0.20})
        # Reload and check it persisted
        state2 = load_emotion()
        # warmth should be higher than baseline (0.50) after +0.20
        assert state2["warmth"] > 0.50


# ── Identity tests ────────────────────────────────────────────────────────────

class TestIdentity:
    def test_birth(self):
        from identity.profile import load_identity
        identity = load_identity()
        assert identity["name"] == "FeBo"
        assert identity["identity_id"] is not None
        assert identity["birth_timestamp"] is not None
        assert identity["creator"] == "Emmanuel"

    def test_session_count_increments(self):
        from identity.profile import load_identity
        id1 = load_identity()
        id2 = load_identity()
        assert id2["session_count"] > id1["session_count"]

    def test_narrative_append(self):
        from identity.profile import load_identity, append_narrative
        identity = load_identity()
        initial_len = len(identity["life_narrative"])
        identity = append_narrative(identity, "Test narrative event.")
        assert len(identity["life_narrative"]) == initial_len + 1
        assert identity["life_narrative"][-1]["event"] == "Test narrative event."

    def test_narrative_summary(self):
        from identity.profile import load_identity, get_narrative_summary
        identity = load_identity()
        summary = get_narrative_summary(identity, n=3)
        assert isinstance(summary, str)
        assert len(summary) > 0


# ── Reflection tests ──────────────────────────────────────────────────────────

class TestReflection:
    def test_write_and_read(self):
        from reflection.engine import write_reflection, get_reflections
        write_reflection("A test reflection.", kind="observation")
        entries = get_reflections(limit=10)
        assert any(e["text"] == "A test reflection." for e in entries)

    def test_reflection_ordering(self):
        from reflection.engine import write_reflection, get_reflections
        write_reflection("First thought.")
        write_reflection("Second thought.")
        entries = get_reflections(limit=2)
        # Most recent first
        assert entries[0]["text"] == "Second thought."

    def test_should_reflect_interval(self):
        from reflection.engine import should_reflect, REFLECTION_INTERVAL
        assert not should_reflect(0)
        assert not should_reflect(REFLECTION_INTERVAL - 1)
        assert should_reflect(REFLECTION_INTERVAL)
        assert should_reflect(REFLECTION_INTERVAL * 2)

    def test_template_reflection_no_crash(self):
        from reflection.engine import compose_reflection
        emotion = {"curiosity": 0.8, "tension": 0.2, "warmth": 0.5,
                   "boredom": 0.1, "attachment": 0.4, "valence": 0.5, "arousal": 0.4}
        identity = {"name": "FeBo", "life_narrative": [], "session_count": 1}
        result = compose_reflection(emotion, [], identity, llm_client=None)
        assert isinstance(result, str) and len(result) > 10


# ── API route tests ───────────────────────────────────────────────────────────

class TestAPIRoutes:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        # Add project root to path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from interface.app import app
        return TestClient(app)

    def test_get_root(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "FeBo" in res.text

    def test_get_emotion(self, client):
        res = client.get("/emotion")
        assert res.status_code == 200
        data = res.json()
        assert "curiosity" in data
        assert "warmth" in data

    def test_get_memory_recent(self, client):
        res = client.get("/memory/recent?limit=5")
        assert res.status_code == 200
        data = res.json()
        assert "memories" in data
        assert "total" in data

    def test_get_reflections(self, client):
        res = client.get("/reflections")
        assert res.status_code == 200
        data = res.json()
        assert "reflections" in data

    def test_get_identity(self, client):
        res = client.get("/identity")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "FeBo"

    def test_get_status(self, client):
        res = client.get("/status")
        assert res.status_code == 200
        data = res.json()
        assert data["alive"] is True

    def test_post_chat_empty(self, client):
        res = client.post("/chat", json={"message": ""})
        assert res.status_code == 400

    def test_post_chat_stub(self, client):
        # Without API key, should return stub response, not crash
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        res = client.post("/chat", json={"message": "Hello FeBo"})
        assert res.status_code == 200
        data = res.json()
        assert "response" in data
        assert "emotion" in data
        assert "trace" in data
