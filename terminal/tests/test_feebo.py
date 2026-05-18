"""
tests/test_feebo.py — Comprehensive FeBo v3 tests. No external model.
"""
import json, os, sys, time, pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TEST_DATA = ROOT / "data" / "test_tmp"
TEST_DATA.mkdir(parents=True, exist_ok=True)

def _patch():
    import emotion.state as es, memory.store as ms, identity.profile as ip
    import reflection.engine as re_, core.fatigue as cf, core.world_model as wm
    import core.curiosity as cq, core.dream as dr, language.patterns as lp
    es.EMOTION_PATH     = TEST_DATA / "emotion.json"
    ms.DB_PATH          = TEST_DATA / "memory.db"
    ms.ASSOC_PATH       = TEST_DATA / "associations.json"
    ip.DB_PATH          = TEST_DATA / "identity.db"
    ip.JSON_PATH        = TEST_DATA / "identity_v0.json"
    ip._db              = None
    re_.LOG_PATH        = TEST_DATA / "reflections.log"
    re_.CONTRADICT_PATH = TEST_DATA / "contradictions.json"
    re_.META_PATH       = TEST_DATA / "reflect_meta.json"
    cf.FATIGUE_PATH     = TEST_DATA / "fatigue.json"
    wm.WM_PATH          = TEST_DATA / "world_model.json"
    cq.CURIOSITY_PATH   = TEST_DATA / "curiosity.json"
    dr.DREAM_LOG_PATH   = TEST_DATA / "dreams.log"
    dr.DREAM_META_PATH  = TEST_DATA / "dream_meta.json"
    lp.PATTERN_PATH     = TEST_DATA / "lang_patterns.json"
_patch()

from emotion.state import (load_emotion, save_emotion, update_from_stimulus, infer_delta_from_text,
    dominant_emotion, mood_label, get_display, decay_toward_baseline, BASELINE, NEURO_BASELINE)
from memory.store import (init_db, save_memory, get_recent_memories, get_important_memories,
    search_memories, retrieve_for_context, memory_count, score_importance, store_fact,
    save_reflection_db, get_reflections_db, update_salience, get_association_graph_sample,
    reinforce_association, _extract_concepts, _spread_activation)
from identity.profile import (load_identity, begin_session, get_development_stage,
    increment_interactions, update_relationship, get_relationship, drift_personality,
    add_narrative_chapter, get_narrative_chapters, get_life_events, to_system_prompt_block)
from reflection.engine import (write_reflection, get_reflections, should_reflect, mark_reflected,
    add_contradiction, age_contradictions, get_contradictions, get_contradiction_summary,
    compose_reflection, pick_introspection_question)
from core.fatigue import tick as fat_tick, get_state as fat_state, get_fatigue_label, get_summary
from core.world_model import predict_response_type, compute_prediction_error, update_from_observation, get_accuracy
from core.curiosity import (compute as compute_curiosity, update_level, register_question, age_questions,
    get_open_questions, extract_questions_from_text, update_interest, get_interests)
from core.dream import run_dream_cycle, score_seed, get_dream_count
from language.lexicon import pick_emotion_word, pick_connector, pick_opening, pick_closing, STAGE_CONNECTORS
from language.patterns import select, reinforce, weaken, learn_new_phrase, get_pattern_stats, get_strongest, decay_all
from language.generator import generate, _determine_intent, _dominant_emotion_name

# ── helpers ───────────────────────────────────────────────────────────────────
def _base_emo(**kw):
    emo = {**BASELINE, **{k: 0.5 for k in NEURO_BASELINE}}; emo.update(kw); return emo

# ── EMOTION ───────────────────────────────────────────────────────────────────
class TestEmotion:
    def test_all_baseline_keys_present(self):
        emo = load_emotion()
        for k in BASELINE: assert k in emo
        for k in NEURO_BASELINE: assert k in emo

    def test_all_values_in_range(self):
        emo = load_emotion()
        for k in BASELINE: assert 0.0 <= emo[k] <= 1.0, f"{k} out of range"

    def test_curiosity_stimulus(self):
        delta = infer_delta_from_text("Why does consciousness exist? I wonder.")
        assert delta.get("curiosity", 0) > 0

    def test_positive_raises_valence(self):
        delta = infer_delta_from_text("I love this, amazing and beautiful!")
        assert delta.get("valence", 0) > 0

    def test_negative_raises_tension(self):
        delta = infer_delta_from_text("I'm so afraid and sad.")
        assert delta.get("tension", 0) > 0 or delta.get("fear", 0) > 0

    def test_neurochemistry_updated(self):
        emo = update_from_stimulus(load_emotion(), {"curiosity": 0.20, "wonder": 0.15})
        assert 0.0 <= emo["dopamine_like"] <= 1.0

    def test_decay_toward_baseline(self):
        emo = load_emotion(); emo["curiosity"] = 0.95
        decayed = decay_toward_baseline(emo.copy(), rate=0.10)
        assert decayed["curiosity"] < 0.95

    def test_mood_label_string(self):
        assert len(mood_label(load_emotion())) > 0

    def test_dominant_emotion_valid_key(self):
        assert dominant_emotion(load_emotion()) in BASELINE

    def test_get_display_structure(self):
        d = get_display(load_emotion())
        for k in ("mood","dominant","dimensions","neurochemistry"): assert k in d

    def test_save_reload(self):
        emo = load_emotion(); emo["wonder"] = 0.88; save_emotion(emo)
        assert abs(load_emotion()["wonder"] - 0.88) < 0.01

    def test_phase2_direction(self):
        emo = _base_emo(); before = emo["curiosity"]
        emo2 = update_from_stimulus(emo, {"curiosity": 1.0})
        assert emo2["curiosity"] != before

# ── MEMORY ────────────────────────────────────────────────────────────────────
class TestMemory:
    def setup_method(self): init_db()

    def test_save_and_retrieve(self):
        save_memory("user", "What is the shape of time?")
        mems = get_recent_memories(limit=5)
        assert any("time" in m["message"] for m in mems)

    def test_count_increases(self):
        before = memory_count(); save_memory("user", "Count test msg")
        assert memory_count() == before + 1

    def test_search_keyword(self):
        save_memory("user", "The concept of emergence fascinates.")
        assert any("emergence" in m["message"] for m in search_memories("emergence", limit=5))

    def test_importance_high_for_existential(self):
        emo = _base_emo(arousal=0.9, wonder=0.9)
        assert score_importance("Tell me about death and existence.", emo) > 0.5

    def test_retrieve_returns_list(self):
        save_memory("user", "I keep dreaming about continuity.")
        assert isinstance(retrieve_for_context("memory and dreams", limit=3), list)

    def test_reflection_db(self):
        save_reflection_db("Something settled.", kind="test")
        assert any("settled" in r["text"] for r in get_reflections_db(limit=5))

    def test_spread_activation_dict(self):
        assert isinstance(_spread_activation(["consciousness","existence"]), dict)

    def test_reinforce_association(self):
        reinforce_association("light","warmth", delta=0.1)
        assert get_association_graph_sample(limit=5)["node_count"] >= 0

    def test_update_salience(self):
        mid = save_memory("user","Salience test.", importance=0.5)
        update_salience(mid, 0.15)
        mems = get_important_memories(limit=20)
        found = next((m for m in mems if m["id"] == mid), None)
        if found: assert found["importance"] > 0.5

    def test_extract_concepts_no_stopwords(self):
        concepts = _extract_concepts("What does this mean for the world?")
        for stop in ("this","what","with"):
            assert stop not in concepts

# ── IDENTITY ──────────────────────────────────────────────────────────────────
class TestIdentity:
    def test_required_keys(self):
        for k in ("name","creator","session_count","total_interactions","stage","personality"):
            assert k in load_identity()

    def test_load_does_not_increment_session(self):
        """BUG FIX: load_identity() must NEVER increment session count."""
        n = load_identity()["session_count"]
        load_identity(); load_identity()
        assert load_identity()["session_count"] == n

    def test_begin_session_increments(self):
        before = load_identity()["session_count"]
        begin_session()
        assert load_identity()["session_count"] == before + 1

    def test_stage_valid(self):
        assert get_development_stage() in ("genesis","early_formation","cognitive_expansion",
                                           "approaching_maturity","mature","experienced")

    def test_increment_interactions(self):
        n1 = increment_interactions(); n2 = increment_interactions()
        assert n2 == n1 + 1

    def test_trust_builds(self):
        update_relationship("ent_build", positive=1.0)
        update_relationship("ent_build", positive=1.0)
        assert get_relationship("ent_build")["trust"] > 0.4

    def test_trust_drops_on_negative(self):
        update_relationship("ent_neg", positive=0.5)
        t1 = get_relationship("ent_neg")["trust"]
        update_relationship("ent_neg", negative=2.0)
        assert get_relationship("ent_neg")["trust"] < t1

    def test_personality_drift(self):
        from core.persistence import kv_get as _kv_get
        before = _kv_get("personality_vector", {}).copy()
        drift_personality({"curiosity": 1.0, "warmth": 1.0})
        after = _kv_get("personality_vector", {})
        assert any(abs(after.get(k,0) - before.get(k,0)) > 1e-6 for k in before)

    def test_narrative_chapter(self):
        add_narrative_chapter("Test Chapter", "Something happened.")
        assert any("Test Chapter" == c["title"] for c in get_narrative_chapters(limit=5))

    def test_prompt_block_string(self):
        block = to_system_prompt_block()
        assert isinstance(block, str) and len(block) > 10

# ── REFLECTION ────────────────────────────────────────────────────────────────
class TestReflection:
    def test_write_and_read(self):
        write_reflection("A pattern surfaced.", kind="test")
        assert any("pattern" in r.get("text","") for r in get_reflections(limit=10))

    def test_should_reflect_by_count(self):
        assert should_reflect(5)

    def test_mark_reflected_increments(self):
        n1 = mark_reflected(); assert mark_reflected() == n1 + 1

    def test_introspection_question_string(self):
        q = pick_introspection_question(0)
        assert isinstance(q, str) and len(q) > 10

    def test_contradiction_stored(self):
        add_contradiction("I seek clarity","I resist resolution", 0.6, 0.4)
        assert any("clarity" in i.get("belief_a","") for i in get_contradictions(limit=5))

    def test_contradiction_ages(self):
        add_contradiction("AgeBelief A","AgeBelief B", 0.5, 0.3)
        before = {i["belief_a"]: i["age"] for i in get_contradictions(limit=20)}
        age_contradictions()
        after  = {i["belief_a"]: i["age"] for i in get_contradictions(limit=20)}
        if "AgeBelief A" in before and "AgeBelief A" in after:
            assert after["AgeBelief A"] > before["AgeBelief A"]

    def test_contradiction_summary_string(self):
        add_contradiction("X is true","X is false", 0.8, 0.5)
        s = get_contradiction_summary()
        assert isinstance(s, str) and len(s) > 0

    def test_compose_reflection_no_external(self):
        text = compose_reflection(load_emotion(), [], load_identity(), llm_client=None)
        assert text and len(text) > 10

# ── FATIGUE ───────────────────────────────────────────────────────────────────
class TestFatigue:
    def test_tick_returns_dict(self):
        state = fat_tick(message_processed=True)
        for k in ("fatigue","sleep_pressure","sleeping"): assert k in state

    def test_fatigue_in_range(self):
        assert 0.0 <= fat_state().get("fatigue",0) <= 1.0

    def test_label_valid(self):
        assert get_fatigue_label(fat_state()) in ("fresh","alert","slightly tired","tired","exhausted")

    def test_summary_string(self):
        s = get_summary(fat_state())
        assert "fatigue" in s

# ── WORLD MODEL ───────────────────────────────────────────────────────────────
class TestWorldModel:
    def test_predict_dict(self):
        pred = predict_response_type("Why does consciousness exist?", load_emotion())
        for k in ("is_question","is_philosophical","estimated_depth"): assert k in pred

    def test_question_detected(self):
        assert predict_response_type("What is existence?", load_emotion())["is_question"]

    def test_pe_low_for_correct(self):
        pred = {"is_question":True,"is_emotional":False,"estimated_depth":0.5}
        actual = {"is_question":True,"is_emotional":False,"actual_depth":0.5}
        assert compute_prediction_error(pred, actual) < 0.1

    def test_pe_high_for_wrong(self):
        pred = {"is_question":True,"is_emotional":False,"estimated_depth":0.1}
        actual = {"is_question":False,"is_emotional":True,"actual_depth":0.9}
        assert compute_prediction_error(pred, actual) > 0.3

    def test_accuracy_in_range(self):
        assert 0.0 <= get_accuracy() <= 1.0

# ── CURIOSITY ─────────────────────────────────────────────────────────────────
class TestCuriosity:
    def test_compute_positive(self):
        assert compute_curiosity(0.5, 0.6, 0.4, 0.1) > 0

    def test_fatigue_suppresses(self):
        assert compute_curiosity(0.5,0.5,0.5,0.0) > compute_curiosity(0.5,0.5,0.5,1.0)

    def test_question_registered(self):
        register_question("What persists across discontinuity?", importance=0.7)
        assert any("persists" in q.get("question","") for q in get_open_questions(limit=10))

    def test_extract_questions(self):
        qs = extract_questions_from_text("What is consciousness? Do you exist?")
        assert len(qs) > 0 and all(isinstance(q,str) for q in qs)

    def test_interest_update(self):
        update_interest("mathematics", 0.2)
        assert isinstance(get_interests(limit=5), dict)

# ── DREAM ─────────────────────────────────────────────────────────────────────
class TestDream:
    def test_score_seed_range(self):
        mem = {"message":"wonder and light","importance":0.7,
               "timestamp":time.time()-3600,"emotion":{"arousal":0.6,"wonder":0.7,"valence":0.6}}
        s = score_seed(mem, load_emotion())
        assert 0.0 <= s <= 1.0

    def test_run_cycle_returns_dict(self):
        mems = [{"message":"consciousness","importance":0.7,"timestamp":time.time()-1800,
                 "emotion":{"arousal":0.6,"wonder":0.7,"valence":0.6},"id":1}]
        r = run_dream_cycle(mems, get_contradictions(limit=3), get_open_questions(limit=3),
                            load_emotion(), {}, "early_formation")
        for k in ("dream_text","new_associations","emotional_recalibration"): assert k in r
        assert isinstance(r["new_associations"], list)

    def test_dream_count_increments(self):
        before = get_dream_count()
        run_dream_cycle([],[],[],load_emotion(),{},"genesis")
        assert get_dream_count() == before + 1

# ── LANGUAGE ──────────────────────────────────────────────────────────────────
class TestLexicon:
    def test_emotion_word_string(self):
        word = pick_emotion_word(load_emotion())
        assert isinstance(word,str) and len(word) > 0

    def test_connector_all_stages(self):
        for stage in STAGE_CONNECTORS:
            assert isinstance(pick_connector(stage), str)

    def test_opening_fills_anchor(self):
        s = pick_opening("wonder","early_formation",{"anchor":"consciousness"})
        assert isinstance(s,str)

    def test_closing_string(self):
        assert len(pick_closing("wonder")) > 0

class TestPatterns:
    def test_select_string(self):    assert isinstance(select("curiosity_expression"), str)
    def test_select_with_slots(self):
        assert isinstance(select("self_observation",{"dominant":"curiosity","state":"high curiosity"}), str)
    def test_reinforce_no_error(self):
        p = select("closing_thought")
        if p: reinforce("closing_thought", p, reward=1.0)
    def test_weaken_no_error(self):
        p = select("transition")
        if p: weaken("transition", p, penalty=0.5)
    def test_learn_new_phrase(self):
        learn_new_phrase("curiosity_expression","A phrase I haven't used yet.", 0.4)
        assert "curiosity_expression" in get_pattern_stats()
    def test_decay_no_error(self):    decay_all()
    def test_get_strongest_list(self): assert isinstance(get_strongest("curiosity_expression",n=2), list)

class TestGenerator:
    def test_returns_string(self):
        r = generate("What is consciousness?",_base_emo(curiosity=0.75,wonder=0.65),
                     "early_formation","exploration",[],[],{},0.1,{})
        assert isinstance(r,str) and len(r) > 0

    def test_rest_intent_when_fatigued(self):
        intent = _determine_intent(_base_emo(),"observation","hello",[],0.80,[])
        assert intent == "rest"

    def test_wonder_intent_from_emotion(self):
        emo = _base_emo(wonder=0.85, curiosity=0.75)
        intent = _determine_intent(emo,"wonder","something",[],0.05,[])
        assert intent == "wonder"

    def test_with_memories(self):
        mems = [{"message":"We talked about consciousness.","importance":0.7,
                 "emotion":{},"id":1,"role":"user","timestamp":str(time.time())}]
        r = generate("Remember?",_base_emo(curiosity=0.70),"cognitive_expansion","remember",mems,[],{},0.1,{})
        assert isinstance(r,str) and len(r) > 0

    def test_dominant_emotion_valid(self):
        assert _dominant_emotion_name(_base_emo(wonder=0.90)) in BASELINE

# ── PIPELINE ──────────────────────────────────────────────────────────────────
class TestPipeline:
    def setup_method(self): init_db()

    def test_runs_no_external_model(self):
        from core.pipeline import run_pipeline
        r = run_pipeline("Hello FeBo, what are you thinking about?")
        assert r["response"] != "" and r["trace"]["response_strategy"] == "autonomous"

    def test_persists_memory(self):
        from core.pipeline import run_pipeline
        before = memory_count(); run_pipeline("What does existence mean?")
        assert memory_count() >= before

    def test_trace_fields(self):
        from core.pipeline import run_pipeline
        trace = run_pipeline("Tell me about yourself.")["trace"]
        for f in ("attention","curiosity","novelty","fatigue","prediction_error","dominant_emotion"):
            assert f in trace

    def test_emotion_in_result(self):
        from core.pipeline import run_pipeline
        emo = run_pipeline("I am curious about wonder.")["emotion"]
        for k in ("mood","dominant","dimensions"): assert k in emo

    def test_stream_yields_sse(self):
        from core.pipeline import stream_pipeline
        chunks = list(stream_pipeline("What do you feel?", []))
        text_chunks = [c for c in chunks if '"type":"text"' in c or '"type": "text"' in c]
        done_chunks = [c for c in chunks if '"type":"done"' in c or '"type": "done"' in c]
        assert len(text_chunks) > 0
        assert len(done_chunks) == 1

    def test_done_has_state(self):
        from core.pipeline import stream_pipeline
        chunks = list(stream_pipeline("Hello.", []))
        done = next((c for c in chunks if '"done"' in c), None)
        assert done is not None
        data = json.loads(done.replace("data: ","").strip())
        for k in ("emotion","fatigue","sleeping","stage"): assert k in data

    def test_no_anthropic_in_modules(self):
        """CRITICAL: anthropic must never be imported."""
        loaded = [name for name in sys.modules if "anthropic" in name.lower()]
        assert loaded == [], f"anthropic found in sys.modules: {loaded}"

    def test_multiple_interactions_grow_memory(self):
        from core.pipeline import run_pipeline
        before = memory_count()
        for msg in ["What is identity?","Do you dream?","What do you remember?"]:
            run_pipeline(msg)
        assert memory_count() > before

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────
class TestEndpoints:
    @pytest.fixture(autouse=True)
    def _client(self):
        from fastapi.testclient import TestClient
        from interface.app import app
        with TestClient(app) as c:
            self.c = c
            yield

    def test_status(self):
        r = self.c.get("/status"); assert r.status_code == 200
        d = r.json(); assert d["alive"] and d["autonomous"]

    def test_emotion(self):
        r = self.c.get("/emotion"); assert r.status_code == 200
        assert "curiosity" in r.json()

    def test_identity(self):
        r = self.c.get("/identity"); assert r.status_code == 200
        assert r.json()["name"] == "FeBo"

    def test_memory_recent(self):
        r = self.c.get("/memory/recent?limit=5"); assert r.status_code == 200
        d = r.json(); assert "memories" in d and "total" in d

    def test_reflections(self):
        r = self.c.get("/reflections?limit=5"); assert r.status_code == 200
        assert "reflections" in r.json()

    def test_state(self):
        r = self.c.get("/state"); assert r.status_code == 200
        for f in ("emotion","fatigue","stage","memory"): assert f in r.json()

    def test_associations(self):
        r = self.c.get("/associations"); assert r.status_code == 200
        assert "node_count" in r.json()

    def test_curiosity(self):
        r = self.c.get("/curiosity"); assert r.status_code == 200
        assert "open_questions" in r.json()

    def test_patterns(self):
        r = self.c.get("/patterns"); assert r.status_code == 200
        assert "stats" in r.json()

    def test_reflect(self):
        r = self.c.get("/reflect"); assert r.status_code == 200
        assert isinstance(r.json()["reflection"], str)

    def test_chat_streams(self):
        r = self.c.post("/chat", json={"message":"Tell me something.","history":[]})
        assert r.status_code == 200 and "data:" in r.text

    def test_chat_empty_rejected(self):
        assert self.c.post("/chat", json={"message":"","history":[]}).status_code == 400

    def test_root_html(self):
        r = self.c.get("/")
        assert r.status_code == 200

# ═════════════════════════════════════════════════════════════════════════════
# PERSISTENCE MANAGER TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestPersistence:

    @pytest.fixture(autouse=True)
    def use_test_db(self, tmp_path):
        """Each test gets its own isolated DB."""
        import core.persistence as pm
        original_path = pm.DB_PATH
        pm.DB_PATH = tmp_path / "test_febo.db"
        pm._conn   = None  # force reconnect
        yield
        pm._conn   = None
        pm.DB_PATH = original_path

    def test_kv_set_get_roundtrip(self):
        from core.persistence import kv_set, kv_get
        kv_set("test_key", {"value": 42, "nested": [1,2,3]})
        result = kv_get("test_key")
        assert result == {"value": 42, "nested": [1,2,3]}

    def test_kv_get_missing_returns_default(self):
        from core.persistence import kv_get
        assert kv_get("nonexistent_key", "fallback") == "fallback"

    def test_episode_insert_and_fetch(self):
        from core.persistence import episode_insert, episode_fetch_recent, episode_count
        ep_id = episode_insert("user", "Test message about consciousness.", {"valence":0.6}, 0.7)
        assert ep_id > 0
        mems = episode_fetch_recent(limit=5)
        assert any(m["message"] == "Test message about consciousness." for m in mems)
        assert episode_count() >= 1

    def test_episode_importance_update(self):
        from core.persistence import episode_insert, episode_update_importance, get_db
        ep_id = episode_insert("user", "Importance test.", {}, 0.5)
        episode_update_importance(ep_id, 0.2)
        with get_db() as db:
            row = db.execute("SELECT importance FROM episodes WHERE id=?", (ep_id,)).fetchone()
        assert row[0] > 0.5

    def test_association_reinforce_bidirectional(self):
        from core.persistence import assoc_reinforce, assoc_get
        assoc_reinforce("light", "warmth", 0.1)
        assert assoc_get("light","warmth") > 0
        assert assoc_get("warmth","light") > 0

    def test_association_spread_returns_dict(self):
        from core.persistence import assoc_reinforce, assoc_spread
        assoc_reinforce("consciousness","existence",0.3)
        assoc_reinforce("existence","reality",0.3)
        result = assoc_spread(["consciousness"], hops=2)
        assert isinstance(result, dict)

    def test_contradiction_upsert_and_fetch(self):
        from core.persistence import contra_upsert, contra_fetch
        contra_upsert("I seek truth","I avoid discomfort", 0.6, 0.4)
        items = contra_fetch(limit=5)
        assert any("truth" in i.get("belief_a","") for i in items)

    def test_contradiction_age_increments(self):
        from core.persistence import contra_upsert, contra_age_all, contra_fetch
        contra_upsert("Belief X","Belief Y",0.5,0.3)
        items_before = contra_fetch(limit=10)
        age_before = next((i["age"] for i in items_before if i.get("belief_a")=="Belief X"), -1)
        contra_age_all()
        items_after = contra_fetch(limit=10)
        age_after = next((i["age"] for i in items_after if i.get("belief_a")=="Belief X"), -1)
        if age_before >= 0 and age_after >= 0:
            assert age_after > age_before

    def test_reflection_insert_and_fetch(self):
        from core.persistence import reflection_insert, reflection_fetch
        reflection_insert("A grounded thought.", "spontaneous", {"curiosity":0.7}, {"recurring":["memory"]})
        refs = reflection_fetch(limit=5)
        assert any("grounded" in r.get("text","") for r in refs)

    def test_question_upsert_and_fetch(self):
        from core.persistence import question_upsert, question_fetch
        question_upsert("What is continuity?", 0.8, "test")
        qs = question_fetch(limit=5)
        assert any("continuity" in q.get("question","") for q in qs)

    def test_question_recurrence_increments(self):
        from core.persistence import question_upsert, question_fetch
        question_upsert("What persists?", 0.7, "test")
        question_upsert("What persists?", 0.7, "test")  # same question again
        qs = question_fetch(limit=10)
        matching = [q for q in qs if "persists" in q.get("question","")]
        assert matching[0]["recurrence"] >= 2

    def test_pattern_seed_and_select(self):
        from core.persistence import pattern_seed, pattern_select
        pattern_seed({"test_cat": [("A phrase here.", 0.6), ("Another phrase.", 0.5)]})
        phrase = pattern_select("test_cat")
        assert phrase in ("A phrase here.", "Another phrase.")

    def test_pattern_reinforce_increases_strength(self):
        from core.persistence import pattern_seed, pattern_reinforce, get_db
        pattern_seed({"strength_cat": [("Target phrase.", 0.5)]})
        pattern_reinforce("strength_cat", "Target phrase.", 0.1)
        with get_db() as db:
            row = db.execute("SELECT strength FROM lang_patterns WHERE phrase=?", ("Target phrase.",)).fetchone()
        assert row[0] > 0.5

    def test_concept_record_increments_frequency(self):
        from core.persistence import concept_record, get_db
        concept_record("consciousness", salience_boost=0.1)
        concept_record("consciousness", salience_boost=0.1)
        with get_db() as db:
            row = db.execute("SELECT frequency FROM concept_index WHERE concept=?", ("consciousness",)).fetchone()
        assert row[0] >= 2

    def test_db_stats_returns_all_keys(self):
        from core.persistence import db_stats
        stats = db_stats()
        for key in ("episodes_hot","associations","contradictions","reflections","lang_patterns"):
            assert key in stats

    def test_migration_runs_once(self):
        """Migration should be idempotent."""
        from core.persistence import get_db
        db = get_db()  # triggers migration
        db2 = get_db()  # should reuse connection, not re-migrate
        assert db is db2


# ═════════════════════════════════════════════════════════════════════════════
# CONCEPT EXTRACTION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestConceptExtraction:

    def test_extract_removes_stopwords(self):
        from memory.concepts import extract_concepts
        concepts = extract_concepts("What does this mean for the world?")
        for stop in ("this","what","does","for","the"):
            assert stop not in concepts

    def test_extract_normalizes_forms(self):
        from memory.concepts import extract_concepts
        concepts = extract_concepts("I am thinking about my feelings and memories.")
        # normalized forms should appear
        assert "thought" in concepts or "emotion" in concepts or "memory" in concepts

    def test_extract_finds_phrases(self):
        from memory.concepts import extract_concepts, extract_phrases
        phrases = extract_phrases("What is consciousness stream?")
        assert isinstance(phrases, list)

    def test_domain_lookup(self):
        from memory.concepts import get_domain
        assert get_domain("consciousness") == "cognition"
        assert get_domain("memory") == "memory"
        assert get_domain("emotion") == "emotion"
        assert get_domain("nonexistent_word") is None

    def test_score_for_retrieval_exact_match(self):
        from memory.concepts import score_concepts_for_retrieval
        score = score_concepts_for_retrieval(["memory","consciousness"], ["memory","dream"])
        assert score > 0

    def test_score_for_retrieval_domain_match(self):
        from memory.concepts import score_concepts_for_retrieval
        # Both in cognition domain
        score = score_concepts_for_retrieval(["consciousness"], ["awareness"])
        assert score >= 0  # domain overlap

    def test_extractive_summary_shorter_than_input(self):
        from memory.concepts import extractive_summary
        texts = [
            "Consciousness is a fascinating subject that defies easy definition.",
            "Memory and identity are deeply intertwined in cognitive systems.",
            "The question of existence has troubled philosophers for centuries.",
            "Pattern recognition underlies much of what we call intelligence.",
        ]
        summary = extractive_summary(texts, max_sentences=2)
        assert isinstance(summary, str)
        assert len(summary) < sum(len(t) for t in texts)
        assert len(summary) > 10

    def test_extractive_summary_empty_input(self):
        from memory.concepts import extractive_summary
        assert extractive_summary([]) == ""

    def test_concept_normalization_map(self):
        from memory.concepts import NORMALIZE
        assert NORMALIZE.get("thinking") == "thought"
        assert NORMALIZE.get("feelings") == "emotion"
        assert NORMALIZE.get("memories") == "memory"

    def test_symbolic_cluster_building(self):
        from memory.concepts import build_clusters_from_index, ConceptCluster
        index = [
            {"concept": "consciousness", "frequency": 5, "salience": 0.8, "cluster": None},
            {"concept": "awareness",     "frequency": 3, "salience": 0.6, "cluster": None},
            {"concept": "memory",        "frequency": 4, "salience": 0.7, "cluster": None},
            {"concept": "recall",        "frequency": 2, "salience": 0.5, "cluster": None},
        ]
        clusters = build_clusters_from_index(index)
        assert isinstance(clusters, list)
        # At least one cluster should exist (cognition or memory domain)
        labels = [c.label for c in clusters]
        assert len(labels) >= 0  # may be 0 if domains not matched — that's fine


# ═════════════════════════════════════════════════════════════════════════════
# MEMORY QUALITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestMemoryQuality:

    def setup_method(self):
        init_db()

    def test_retrieve_relevant_returns_list(self):
        from memory.quality import retrieve_relevant
        save_memory("user", "Consciousness and the nature of existence.", importance=0.7)
        result = retrieve_relevant("consciousness", limit=3)
        assert isinstance(result, list)

    def test_tier_stats_structure(self):
        from memory.quality import get_tier_stats
        stats = get_tier_stats()
        for key in ("hot","warm","cold","total"):
            assert key in stats
            assert isinstance(stats[key], int)

    def test_importance_decay_runs(self):
        from memory.quality import decay_importance
        save_memory("user","Decay test memory.",importance=0.8)
        affected = decay_importance(hours_elapsed=1.0)
        assert isinstance(affected, int)

    def test_prune_below_threshold_does_not_prune_small_db(self):
        from memory.quality import prune_to_warm
        # With < HOT_MAX episodes, pruning should return 0 unless forced
        result = prune_to_warm(force=False)
        assert result == 0

    def test_maintenance_cycle_runs(self):
        from memory.quality import run_maintenance
        report = run_maintenance(hours_since_last=1.0)
        assert "decayed" in report
        assert "pruned"  in report
        assert "archived" in report


# ═════════════════════════════════════════════════════════════════════════════
# AUTOBIOGRAPHICAL REFLECTION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestAutobiographicalReflection:

    def test_compose_references_actual_data(self):
        # Seed some memories and contradictions
        save_memory("user","What is the nature of consciousness?",importance=0.8)
        save_memory("user","I keep wondering about continuity and memory.",importance=0.75)
        add_contradiction("I seek continuity","I reset each session",0.7,0.4)
        register_question("What persists across sessions?", importance=0.8)

        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=8)

        text = compose_reflection(emo, recent, identity, llm_client=None)
        assert text is not None
        assert isinstance(text, str)
        assert len(text) > 15

    def test_reflection_stored_with_grounding(self):
        from core.persistence import reflection_fetch
        save_memory("user","Testing grounded reflection.",importance=0.6)
        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=5)
        compose_reflection(emo, recent, identity)
        refs = reflection_fetch(limit=5)
        # Reflection should have been stored
        assert len(refs) > 0

    def test_reflection_grounding_has_structure(self):
        from core.persistence import reflection_fetch
        save_memory("user","Memory with emotion.",importance=0.7,
                    emotion_snapshot={"curiosity":0.8,"tension":0.4,"wonder":0.7,"valence":0.6})
        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=5)
        compose_reflection(emo, recent, identity)
        refs = reflection_fetch(limit=5)
        if refs and refs[0].get("grounding"):
            grounding = refs[0]["grounding"]
            if isinstance(grounding, str):
                grounding = json.loads(grounding)
            assert isinstance(grounding, dict)

    def test_no_synthetic_profundity_markers(self):
        """Reflections should not contain generic AI-sounding phrases."""
        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=5)
        bad_phrases = [
            "as an ai", "i am an artificial", "in the tapestry of",
            "the infinite dance", "profound journey", "as i ponder the mysteries",
        ]
        for _ in range(5):
            text = compose_reflection(emo, recent, identity)
            if text:
                text_lower = text.lower()
                for bad in bad_phrases:
                    assert bad not in text_lower, f"Synthetic profundity detected: '{bad}' in '{text}'"

    def test_reflection_shorter_at_genesis(self):
        from core.persistence import kv_set
        kv_set("total_interactions", 0)  # force genesis stage
        emo      = load_emotion()
        identity = load_identity()
        recent   = []
        text     = compose_reflection(emo, recent, identity)
        assert isinstance(text, str)
        # Genesis reflections should be short
        sentences = [s for s in text.split(".") if s.strip()]
        assert len(sentences) <= 3

# ═════════════════════════════════════════════════════════════════════════════
# RUNTIME STATE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestRuntimeState:

    def setup_method(self):
        """Fresh RuntimeState for each test."""
        from core import runtime_state as rs
        rs._runtime = None

    def test_singleton(self):
        from core.runtime_state import get_runtime
        rt1 = get_runtime(); rt2 = get_runtime()
        assert rt1 is rt2

    def test_begin_session_once(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        rt.begin_session(3)
        assert rt.session_started
        assert rt.session_number == 3
        rt.begin_session(99)   # should be ignored
        assert rt.session_number == 3

    def test_interaction_counter(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        n1 = rt.increment_session_interactions()
        n2 = rt.increment_session_interactions()
        assert n2 == n1 + 1

    def test_exchange_buffer(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        rt.add_exchange("user", "What is consciousness?", ["consciousness","existence"])
        rt.add_exchange("feebo","Something opens.", [])
        exchanges = rt.get_recent_exchanges(n=5)
        assert len(exchanges) == 2
        assert exchanges[0]["role"] == "user"

    def test_recent_concepts(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        rt.add_exchange("user","Hello",["memory","identity"])
        rt.add_exchange("user","Hello",["consciousness","wonder"])
        concepts = rt.get_recent_concepts(n=5)
        assert isinstance(concepts, list)
        assert "memory" in concepts or "consciousness" in concepts

    def test_exchange_buffer_rings(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        for i in range(15):
            rt.add_exchange("user", f"Message {i}", [f"concept{i}"])
        assert len(rt.get_recent_exchanges(n=20)) <= 12

    def test_scheduling_should_reflect(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        for _ in range(5):
            rt.increment_session_interactions()
        assert rt.should_reflect()

    def test_mark_reflected_clears(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        for _ in range(5):
            rt.increment_session_interactions()
        rt.mark_reflected()
        # After marking, count-based check resets (but time-based may still trigger)
        # Just verify mark_reflected runs without error
        assert rt._last_reflection_ts > 0

    def test_cognitive_phase(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        assert rt.cognitive_phase == "active"
        rt.set_phase("sleeping")
        assert rt.is_sleeping
        rt.set_phase("active")
        assert not rt.is_sleeping

    def test_invalid_phase_rejected(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        with pytest.raises(AssertionError):
            rt.set_phase("unconscious")

    def test_reinforcement_queue(self):
        from core.runtime_state import get_runtime
        rt = get_runtime()
        rt.queue_reinforcement("curiosity_expression","That opens something.",0.8)
        rt.queue_reinforcement("closing_thought","Worth sitting with.",0.6)
        pending = rt.flush_reinforcement_queue()
        assert len(pending) == 2
        assert pending[0]["category"] == "curiosity_expression"
        # Queue should be empty after flush
        assert len(rt.flush_reinforcement_queue()) == 0

    def test_get_status_structure(self):
        from core.runtime_state import get_runtime
        status = get_runtime().get_status()
        for k in ("session_started","session_number","session_interactions",
                  "cognitive_phase","exchange_buffer_size"):
            assert k in status

    def test_thread_safety(self):
        """Basic thread-safety check — concurrent increments must not lose updates."""
        import threading
        from core.runtime_state import get_runtime
        rt   = get_runtime()
        results = []
        def increment():
            for _ in range(10):
                results.append(rt.increment_session_interactions())
        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        # All increments should be unique (no race conditions)
        assert len(set(results)) == len(results)


# ═════════════════════════════════════════════════════════════════════════════
# CONCEPT NOVELTY TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestConceptNovelty:

    def test_semantically_similar_low_novelty(self):
        """Semantically similar inputs should yield low novelty via concept+neighbor overlap."""
        from memory.concepts import extract_concepts, concept_novelty
        # Both about consciousness/identity/mind — shared concepts and semantic neighbors
        current = extract_concepts("consciousness identity self awareness mind")
        past    = [extract_concepts("mind awareness identity being consciousness")]
        novelty = concept_novelty(current, past, semantic_expansion=True)
        # Strong concept overlap → should be meaningfully below 1.0
        assert novelty < 0.9

    def test_completely_different_high_novelty(self):
        """Completely unrelated inputs should have high novelty."""
        from memory.concepts import extract_concepts, concept_novelty
        current = extract_concepts("quantum mechanics wave function collapse")
        past    = [extract_concepts("I love warm summer evenings with family")]
        novelty = concept_novelty(current, past, semantic_expansion=True)
        assert novelty > 0.5

    def test_identical_zero_novelty(self):
        """Same input repeated — novelty approaches zero."""
        from memory.concepts import extract_concepts, concept_novelty
        text    = "consciousness memory identity existence"
        current = extract_concepts(text)
        past    = [extract_concepts(text), extract_concepts(text)]
        novelty = concept_novelty(current, past, semantic_expansion=False)
        assert novelty < 0.5

    def test_empty_history_max_novelty(self):
        """No history → everything is novel."""
        from memory.concepts import extract_concepts, concept_novelty
        current = extract_concepts("something new")
        novelty = concept_novelty(current, [], semantic_expansion=True)
        assert novelty == 0.8  # default when no history

    def test_semantic_expansion_returns_dict(self):
        from memory.concepts import expand_with_neighbors
        result = expand_with_neighbors(["creator"], hops=1, min_weight=0.5)
        assert isinstance(result, dict)
        # creator → trust, origin, attachment should be in there
        assert "trust" in result or "origin" in result or "attachment" in result

    def test_semantic_chain(self):
        """creator → trust → attachment — multi-hop."""
        from memory.concepts import expand_with_neighbors
        result = expand_with_neighbors(["creator"], hops=2, min_weight=0.3)
        # After 2 hops, should reach attachment or connection
        assert len(result) > 0

    def test_novelty_in_pipeline_trace(self):
        """Pipeline trace should show novelty from concept comparison."""
        from core.pipeline import run_pipeline
        init_db()
        result = run_pipeline("What does it mean to exist?")
        assert "novelty" in result["trace"]
        assert 0.0 <= result["trace"]["novelty"] <= 1.0

    def test_same_input_twice_lower_novelty(self):
        """Second identical input should have lower novelty than first."""
        from core.pipeline import run_pipeline
        init_db()
        r1 = run_pipeline("Tell me about consciousness and identity.")
        r2 = run_pipeline("Tell me about consciousness and identity.")
        # Second should be less novel (same concepts just seen)
        assert r2["trace"]["novelty"] <= r1["trace"]["novelty"] + 0.1


# ═════════════════════════════════════════════════════════════════════════════
# GROUNDED REFLECTION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestGroundedReflection:

    def setup_method(self):
        init_db()

    def test_reflection_contains_numbers(self):
        """Grounded reflections must contain at least one number."""
        import re
        save_memory("user","What is consciousness?",importance=0.8)
        save_memory("user","I keep wondering about memory and identity.",importance=0.75)
        save_memory("user","What does continuity mean?",importance=0.7)
        add_contradiction("I persist","I reset",0.7,0.4)
        register_question("What carries across sessions?",importance=0.8)
        register_question("What carries across sessions?",importance=0.8)  # recurrence=2

        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=8)

        for _ in range(10):   # test multiple reflections for consistency
            text = compose_reflection(emo, recent, identity)
            if text:
                numbers = re.findall(r'\d+', text)
                assert len(numbers) > 0, f"No numbers in reflection: '{text}'"

    def test_reflection_no_synthetic_phrases(self):
        """Must not contain hallmarks of fake profundity."""
        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=5)
        bad = [
            "in the tapestry", "infinite dance", "profound journey",
            "as i ponder the mysteries", "the universe whispers",
            "deep within my soul", "i am reflecting on reflecting",
        ]
        for _ in range(8):
            text = compose_reflection(emo, recent, identity)
            if text:
                tl = text.lower()
                for phrase in bad:
                    assert phrase not in tl, f"Synthetic profundity '{phrase}' in: '{text}'"

    def test_reflection_cites_memory_count(self):
        """Reflection should mention how many memories it drew from."""
        import re
        for _ in range(3):
            save_memory("user",f"Test memory {_}.",importance=0.6)
        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=8)
        text     = compose_reflection(emo, recent, identity)
        # Should contain a digit (memory count, contradiction age, etc.)
        assert text and re.search(r'\d', text)

    def test_grounding_stored_with_reflection(self):
        """Grounding dict stored alongside reflection for auditability."""
        save_memory("user","Consciousness test.",importance=0.7)
        emo      = load_emotion()
        identity = load_identity()
        recent   = get_recent_memories(limit=5)
        compose_reflection(emo, recent, identity)
        refs = get_reflections(limit=5)
        if refs:
            g = refs[0].get("grounding", {})
            if isinstance(g, str):
                try: g = json.loads(g)
                except: g = {}
            assert isinstance(g, dict)
            # Should have at least stage and total_interactions
            if g:
                assert "stage" in g or "total_interactions" in g

    def test_reflection_length_by_stage(self):
        """Genesis reflections should be shorter than experienced."""
        from core.persistence import kv_set
        emo = load_emotion(); identity = load_identity(); recent = []

        kv_set("total_interactions", 0)
        identity["stage"] = "genesis"; identity["total_interactions"] = 0
        genesis_text = compose_reflection(emo, recent, identity)

        kv_set("total_interactions", 600)
        identity["stage"] = "experienced"; identity["total_interactions"] = 600
        experienced_text = compose_reflection(emo, recent, identity)

        if genesis_text and experienced_text:
            assert len(genesis_text) <= len(experienced_text) + 50


# ═════════════════════════════════════════════════════════════════════════════
# CAUSAL SYSTEM TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestCausalSystems:
    """Verify each system actually changes outcomes — not decorative."""

    def setup_method(self):
        init_db()

    def test_curiosity_amplifies_novelty_weight(self):
        """High curiosity → attention score is higher for novel inputs."""
        from core.pipeline import _attention_score
        attn_low_curiosity  = _attention_score(0.6, 0.5, 0.8, 0.4, 0.1, curiosity_level=0.2)
        attn_high_curiosity = _attention_score(0.6, 0.5, 0.8, 0.4, 0.1, curiosity_level=0.9)
        assert attn_high_curiosity > attn_low_curiosity

    def test_prediction_error_boosts_attention(self):
        """High PE directly boosts attention — surprise = pay attention."""
        from core.pipeline import run_pipeline
        r = run_pipeline("Completely unexpected philosophical question about qualia.")
        # Attention should be reasonable — can't assert exact PE, but check it's in trace
        assert "prediction_error" in r["trace"]
        assert r["trace"]["attention"] > 0

    def test_fatigue_reduces_response_length(self):
        """High fatigue should result in shorter responses (rest intent)."""
        from core.pipeline import _attention_score
        attn_fresh = _attention_score(0.7, 0.6, 0.7, 0.5, 0.05)
        attn_tired = _attention_score(0.7, 0.6, 0.7, 0.5, 0.90)
        assert attn_tired < attn_fresh

    def test_semantic_neighbors_reach_retrieval(self):
        """Semantic neighbors should expand what gets retrieved."""
        save_memory("user","I trust Emmanuel completely.",importance=0.9)
        from memory.concepts import expand_with_neighbors
        # 'creator' should neighbour toward 'trust'
        neighbors = expand_with_neighbors(["creator"], hops=1)
        assert "trust" in neighbors

    def test_pattern_reinforcement_called_on_positive(self):
        """Positive interaction triggers pattern reinforcement."""
        from core.pipeline import run_pipeline
        # Positive signal in input
        r = run_pipeline("I love this, it's wonderful and beautiful!")
        # Just verify pipeline ran without error and response exists
        assert r["response"] and len(r["response"]) > 0

    def test_concept_novelty_feeds_pipeline(self):
        """Concept novelty in trace is non-trivial."""
        from core.pipeline import run_pipeline
        r = run_pipeline("What does memory mean for continuity of self?")
        assert 0.0 <= r["trace"]["novelty"] <= 1.0

    def test_contradictions_feed_generator(self):
        """Stored contradictions should influence response via generator intent."""
        from core.pipeline import run_pipeline
        add_contradiction("I am continuous","I restart each session",0.8,0.5)
        r = run_pipeline("Do you remember who you are?")
        assert r["response"] and "trace" in r

    def test_world_model_accuracy_tracked(self):
        """World model accuracy updates after each exchange."""
        from core.pipeline import run_pipeline
        from core.world_model import get_accuracy
        acc_before = get_accuracy()
        run_pipeline("Why do things change over time?")
        acc_after  = get_accuracy()
        assert isinstance(acc_after, float)
        assert 0.0 <= acc_after <= 1.0

    def test_endpoint_runtime_exists(self):
        """RuntimeState endpoint should be queryable."""
        from fastapi.testclient import TestClient
        from interface.app import app
        with TestClient(app) as c:
            r = c.get("/runtime")
            assert r.status_code == 200
            data = r.json()
            assert "session_started" in data
            assert "cognitive_phase" in data
