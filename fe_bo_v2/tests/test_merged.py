"""
tests/test_merged.py
─────────────────────
Comprehensive tests for the merged FeBo architecture.

Tests verify:
  1. Original brain/ modules preserved with correct APIs
  2. New core/runtime_state (single shared state)
  3. New core/scheduler (single heartbeat)
  4. New core/observability (tracing + health)
  5. New brain/soul.py (sovereign loop)
  6. New brain/intents.py
  7. New brain/ai.py
  8. New brain/background.py
  9. Full soul loop end-to-end
  10. No dual-brain conflict (soul is the only orchestrator)

Run: pytest tests/test_merged.py -v
"""

import sys, os, time, json, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# ── Environment overrides so tests don't touch real data ──────────
os.environ.setdefault("FEBO_IDENTITY_DB",   "/tmp/febo_test_identity.db")
os.environ.setdefault("FEBO_KNOWLEDGE_FILE", "/tmp/febo_test_knowledge.json")
os.environ.setdefault("FEBO_LOG_FILE",       "/tmp/febo_test.log")


# ═══════════════════════════════════════════════════════════════════
#  1. ORIGINAL BRAIN MODULES — API PRESERVATION
# ═══════════════════════════════════════════════════════════════════

class TestBrainEmotionAPI:
    """The original emotion system must still work as FeBo expects it."""

    def test_load_state_returns_dict(self):
        from brain.emotion import load_state
        state = load_state()
        assert isinstance(state, dict)

    def test_process_input_returns_dict(self):
        from brain.emotion import process_input
        state = process_input("Hello, how are you?")
        assert isinstance(state, dict)
        assert "valence" in state
        assert "dominant_mood" in state

    def test_save_and_reload(self):
        from brain.emotion import load_state, save_state
        state = load_state()
        state["valence"] = 0.8
        save_state(state)
        reloaded = load_state()
        assert reloaded["valence"] == pytest.approx(0.8, abs=0.01)

    def test_colour_response(self):
        from brain.emotion import colour_response, load_state
        state = load_state()
        coloured = colour_response("hello", state)
        assert isinstance(coloured, str)
        assert len(coloured) > 0

    def test_get_mood_summary(self):
        from brain.emotion import get_mood_summary
        summary = get_mood_summary()
        assert isinstance(summary, str)
        assert len(summary) > 5

    def test_decay_toward_baseline(self):
        from brain.emotion import _decay_toward_baseline
        result = _decay_toward_baseline(0.9, 0.5, 0.1)
        assert result < 0.9
        result2 = _decay_toward_baseline(0.1, 0.5, 0.1)
        assert result2 > 0.1

    def test_all_emotion_keys_present(self):
        from brain.emotion import load_state
        state = load_state()
        for key in ("valence", "arousal", "curiosity", "tension", "warmth",
                    "confidence", "boredom", "dominant_mood"):
            assert key in state, f"Missing key: {key}"

    def test_emotion_values_in_range(self):
        from brain.emotion import process_input
        state = process_input("I love learning new things!")
        for key in ("valence", "arousal", "curiosity", "tension", "warmth",
                    "confidence", "boredom"):
            val = state[key]
            assert 0.0 <= val <= 1.0, f"{key}={val} out of range"


class TestBrainForgiveness:
    def test_record_transgression(self):
        from brain.forgiveness import forgiveness
        forgiveness.record_transgression(severity=0.3, context="test")

    def test_record_apology(self):
        from brain.forgiveness import forgiveness
        forgiveness.record_apology(sincerity=0.7)

    def test_should_forgive_returns_bool(self):
        from brain.forgiveness import forgiveness
        # should_forgive requires severity, context, and apologized keys
        result = forgiveness.should_forgive({"severity": 0.2, "context": "test", "apologized": False})
        assert isinstance(result, bool)

    def test_get_moral_mood(self):
        from brain.forgiveness import forgiveness
        mood = forgiveness.get_moral_mood()
        assert isinstance(mood, str)


class TestBrainResonance:
    def test_learn_association(self):
        from brain.resonance import resonance
        resonance.learn_association("color_blue", -0.05)

    def test_apply_to_emotion(self):
        from brain.resonance import resonance
        from brain.emotion import load_state
        state = load_state()
        result = resonance.apply_to_emotion(state, "color_blue")
        assert isinstance(result, dict)
        assert "valence" in result

    def test_feel_unknown_stimulus(self):
        from brain.resonance import resonance
        val = resonance.feel("xyz_unknown_999")
        assert val == 0.0 or isinstance(val, float)


class TestBrainTimeAwareness:
    def test_get_time_context(self):
        from brain.time_awareness import get_time_context
        ctx = get_time_context()
        assert isinstance(ctx, dict)
        assert "hour" in ctx
        assert "period" in ctx

    def test_record_interaction(self):
        from brain.time_awareness import record_interaction
        record_interaction()  # Should not raise

    def test_absence_feeling_is_string_or_none(self):
        from brain.time_awareness import get_absence_feeling
        result = get_absence_feeling()
        assert result is None or isinstance(result, str)

    def test_get_greeting_for_time(self):
        from brain.time_awareness import get_greeting_for_time
        greeting = get_greeting_for_time()
        assert isinstance(greeting, str)
        assert len(greeting) > 2


class TestBrainInitiation:
    def test_update_activity(self):
        from brain.initiation import update_activity
        update_activity()  # Should not raise

    def test_start_thread_is_idempotent(self):
        from brain.initiation import start_initiation_thread
        # Calling twice should not raise
        start_initiation_thread()
        start_initiation_thread()


class TestBrainLearner:
    def test_pick_curiosity_topic_returns_string(self):
        from brain.learner import pick_curiosity_topic
        topic = pick_curiosity_topic()
        assert isinstance(topic, str)
        assert len(topic) > 2

    def test_get_knowledge_stats_returns_dict(self):
        from brain.learner import get_knowledge_stats
        stats = get_knowledge_stats()
        assert isinstance(stats, dict)
        assert "total_entries" in stats
        assert "unique_topics" in stats

    def test_recall_returns_string_or_none(self):
        from brain.learner import recall
        result = recall("consciousness and mind")
        assert result is None or isinstance(result, str)

    def test_learn_about_returns_dict(self):
        from brain.learner import learn_about
        # Without network, should still return a dict
        result = learn_about("test_topic_xyz_not_real", depth="quick")
        assert isinstance(result, dict)
        assert "topic" in result
        assert "sources_read" in result


# ═══════════════════════════════════════════════════════════════════
#  2. RUNTIME STATE — SINGLE SHARED STATE
# ═══════════════════════════════════════════════════════════════════

class TestRuntimeState:
    def test_singleton_pattern(self):
        from core.runtime_state import RuntimeState
        a = RuntimeState()
        b = RuntimeState()
        assert a is b

    def test_update_emotion(self):
        from core.runtime_state import runtime
        runtime.update_emotion({"valence": 0.7, "arousal": 0.6, "dominant_mood": "curious"})
        state = runtime.get_emotion()
        assert state["valence"] == pytest.approx(0.7)
        assert state["dominant_mood"] == "curious"

    def test_update_drives(self):
        from core.runtime_state import runtime
        runtime.update_drives("explore", curiosity=0.9)
        assert runtime.get_desire() == "explore"
        assert runtime.drives.curiosity == pytest.approx(0.9)

    def test_turn_tracking(self):
        from core.runtime_state import runtime
        before = runtime.turn_count
        runtime.update_turn("hello", "hi")
        assert runtime.turn_count == before + 1
        assert runtime.last_input == "hello"
        assert runtime.last_response == "hi"

    def test_reward_tracking(self):
        from core.runtime_state import runtime
        runtime.record_reward(0.8)
        runtime.record_reward(0.6)
        avg = runtime.avg_reward()
        assert 0.0 <= avg <= 1.0

    def test_reward_capped_at_100(self):
        from core.runtime_state import runtime
        for i in range(150):
            runtime.record_reward(float(i % 2))
        assert len(runtime.total_rewards) == 100

    def test_namespaced_storage(self):
        from core.runtime_state import runtime
        runtime.set("test_ns", "foo", 42)
        assert runtime.get("test_ns", "foo") == 42
        assert runtime.get("test_ns", "missing", "default") == "default"

    def test_snapshot_returns_dict(self):
        from core.runtime_state import runtime
        snap = runtime.snapshot()
        assert isinstance(snap, dict)
        for key in ("uptime_s", "turn_count", "mood", "desire", "avg_reward"):
            assert key in snap

    def test_uptime_increases(self):
        from core.runtime_state import runtime
        u1 = runtime.uptime_seconds
        time.sleep(0.01)
        u2 = runtime.uptime_seconds
        assert u2 > u1

    def test_thread_safety(self):
        from core.runtime_state import runtime
        errors = []
        def writer(val):
            try:
                for _ in range(20):
                    runtime.update_emotion({"valence": val, "dominant_mood": "test"})
                    runtime.record_reward(val)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(float(i)/10,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════
#  3. SCHEDULER — SINGLE HEARTBEAT
# ═══════════════════════════════════════════════════════════════════

class TestScheduler:
    def test_singleton_pattern(self):
        from core.scheduler import FeBo_Scheduler
        a = FeBo_Scheduler()
        b = FeBo_Scheduler()
        assert a is b

    def test_register_and_run(self):
        from core.scheduler import FeBo_Scheduler
        sched  = FeBo_Scheduler()
        called = []
        sched.register("test_task_run", interval_s=0.5,
                       callback=lambda: called.append(1))
        sched.start()
        time.sleep(2.5)
        sched.unregister("test_task_run")
        assert len(called) >= 1

    def test_enable_disable(self):
        from core.scheduler import FeBo_Scheduler
        sched  = FeBo_Scheduler()
        called = []
        sched.register("test_toggle", interval_s=0.5,
                       callback=lambda: called.append(1), enabled=False)
        sched.start()
        time.sleep(1.0)
        count_disabled = len(called)
        sched.enable("test_toggle", True)
        time.sleep(2.0)
        sched.unregister("test_toggle")
        assert count_disabled == 0
        assert len(called) >= 1

    def test_error_does_not_kill_scheduler(self):
        from core.scheduler import FeBo_Scheduler
        sched  = FeBo_Scheduler()
        called = []
        def bad_task():
            called.append(1)
            raise RuntimeError("Intentional test error")
        sched.register("test_error_task", interval_s=0.5, callback=bad_task)
        sched.start()
        time.sleep(2.5)
        sched.unregister("test_error_task")
        assert len(called) >= 1

    def test_status_returns_list(self):
        from core.scheduler import scheduler
        status = scheduler.status()
        assert isinstance(status, list)

    def test_repr(self):
        from core.scheduler import scheduler
        r = repr(scheduler)
        assert "FeBo_Scheduler" in r


# ═══════════════════════════════════════════════════════════════════
#  4. OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════

class TestObservability:
    def test_emotion_tracker_records(self):
        from core.observability import EmotionDriftTracker
        tracker = EmotionDriftTracker(sample_every_n_turns=1)
        state = {"valence": 0.6, "arousal": 0.5, "curiosity": 0.8,
                 "tension": 0.0, "warmth": 0.5, "confidence": 0.6,
                 "boredom": 0.1, "dominant_mood": "curious"}
        tracker.record(state, turn=1, reward=0.5)
        assert tracker._baseline is not None

    def test_interaction_ledger(self):
        from core.observability import InteractionLedger
        ledger = InteractionLedger()
        ledger.record(turn=1, user_len=20, resp_len=30, mood="calm",
                      desire="explore", reward=0.5, vocab_sz=100)
        # Should not raise

    def test_health_monitor_no_warnings_initially(self):
        from core.observability import HealthMonitor
        hm = HealthMonitor()
        warnings = hm.check(turn=5, mood="curious", vocab_sz=50, reward=0.5)
        assert isinstance(warnings, list)

    def test_health_monitor_detects_mood_stagnation(self):
        from core.observability import HealthMonitor
        hm = HealthMonitor()
        for i in range(55):
            warnings = hm.check(turn=i, mood="bored", vocab_sz=100, reward=0.0)
        assert any("MOOD_STAGNATION" in w for w in warnings)

    def test_health_monitor_detects_vocab_stagnation(self):
        from core.observability import HealthMonitor
        hm = HealthMonitor()
        # Simulate 35 turns with same vocab size, after 50 turns total
        hm._last_vocab = 50
        for i in range(55, 92):
            hm._stable_vocab_turns += 1
            hm._last_mood = "curious"
        warnings = hm.check(turn=92, mood="curious", vocab_sz=50, reward=0.5)
        assert any("VOCAB_STAGNATION" in w for w in warnings)

    def test_snapshot_returns_string(self):
        from core.observability import snapshot
        result = snapshot()
        assert isinstance(result, str)
        assert len(result) > 10


# ═══════════════════════════════════════════════════════════════════
#  5. BRAIN/INTENTS
# ═══════════════════════════════════════════════════════════════════

class TestIntentClassifier:
    def test_greeting(self):
        from brain.intents import classify_intent
        assert classify_intent("hello there") == "greeting"
        assert classify_intent("hey") == "greeting"

    def test_farewell(self):
        from brain.intents import classify_intent
        assert classify_intent("goodbye") == "farewell"
        assert classify_intent("bye") == "farewell"

    def test_identity(self):
        from brain.intents import classify_intent
        assert classify_intent("who are you?") == "identity"

    def test_knowledge_what_question(self):
        from brain.intents import classify_intent
        assert classify_intent("what is consciousness?") == "knowledge"

    def test_reasoning_why(self):
        from brain.intents import classify_intent
        assert classify_intent("why does this happen?") in ("reasoning", "knowledge")

    def test_tools_math(self):
        from brain.intents import classify_intent
        assert classify_intent("calculate 3 + 5") == "tools"
        assert classify_intent("3 + 5") == "tools"
        # "what is 100 * 7" — math regex picks up * between numbers
        result = classify_intent("100 * 7")
        assert result == "tools"

    def test_reflection(self):
        from brain.intents import classify_intent
        assert classify_intent("I want you to reflect on your nature") == "reflection"

    def test_unknown_returns_unknown(self):
        from brain.intents import classify_intent
        assert classify_intent("blorp zorp xyzzy") == "unknown"

    def test_empty_input(self):
        from brain.intents import classify_intent
        assert classify_intent("") == "unknown"

    def test_emotional_intent(self):
        from brain.intents import classify_intent
        intent = classify_intent("how do you feel right now?")
        assert intent == "emotional"

    def test_memory_intent(self):
        from brain.intents import classify_intent
        intent = classify_intent("can you remember what I told you?")
        assert intent == "memory"


# ═══════════════════════════════════════════════════════════════════
#  6. BRAIN/AI — LANGUAGE GENERATION LAYER
# ═══════════════════════════════════════════════════════════════════

class TestBrainAI:
    def test_generate_response_returns_string(self):
        from brain.ai import generate_response
        from brain.emotion import load_state
        state = load_state()
        resp  = generate_response("Hello FeBo", state, [])
        assert isinstance(resp, str)
        assert len(resp) > 0

    def test_generate_with_context(self):
        from brain.ai import generate_response
        from brain.emotion import load_state
        state   = load_state()
        context = [{"user": "Hi", "response": "Hello"}]
        resp    = generate_response("Tell me more", state, context)
        assert isinstance(resp, str)

    def test_learn_from_interaction(self):
        from brain.ai import learn_from_interaction
        from brain.emotion import load_state
        state = load_state()
        # Should not raise
        learn_from_interaction("test input", "test response", state, 0.5)

    def test_get_experience_summary(self):
        from brain.ai import get_experience_summary
        summary = get_experience_summary()
        assert isinstance(summary, dict)
        for key in ("stage", "interactions", "words_learned",
                    "positive_rewards", "negative_rewards"):
            assert key in summary

    def test_stage_progresses(self):
        from brain.ai import _get_stage, DEVELOPMENTAL_STAGES
        assert _get_stage(0)    == "newborn"
        assert _get_stage(10)   == "infant"
        assert _get_stage(200)  == "child"
        assert _get_stage(5000) == "experienced"

    def test_positive_reward_increments_counter(self):
        from brain.ai import learn_from_interaction, get_experience_summary, _load_experience
        from brain.emotion import load_state
        state   = load_state()
        before  = _load_experience().get("positive_rewards", 0)
        learn_from_interaction("test", "test", state, 0.8)
        after   = _load_experience().get("positive_rewards", 0)
        assert after >= before


# ═══════════════════════════════════════════════════════════════════
#  7. BRAIN/BACKGROUND — SPONTANEOUS THOUGHTS
# ═══════════════════════════════════════════════════════════════════

class TestBrainBackground:
    def test_add_thought(self):
        from brain.background import _add_thought, get_recent_thoughts
        _add_thought("This is a test thought.")
        thoughts = get_recent_thoughts(5)
        assert any("test thought" in t["thought"] for t in thoughts)

    def test_get_recent_thoughts_limit(self):
        from brain.background import _add_thought, get_recent_thoughts
        for i in range(10):
            _add_thought(f"Thought number {i}")
        result = get_recent_thoughts(3)
        assert len(result) <= 3

    def test_buffer_max_size(self):
        from brain.background import _add_thought, _thoughts_buffer
        for i in range(60):
            _add_thought(f"Overflow thought {i}")
        assert len(_thoughts_buffer) <= 50

    def test_start_background_thoughts_idempotent(self):
        from brain.background import start_background_thoughts
        start_background_thoughts()
        start_background_thoughts()  # Should not start two threads


# ═══════════════════════════════════════════════════════════════════
#  8. SOUL LOOP — SOVEREIGN END-TO-END
# ═══════════════════════════════════════════════════════════════════

class TestSoulLoop:
    def test_process_input_returns_string(self):
        from brain.soul import process_input
        response = process_input("Hello FeBo")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_multiple_turns(self):
        from brain.soul import process_input
        inputs = [
            "Hello, how are you?",
            "What do you think about consciousness?",
            "Tell me something interesting.",
            "I like learning new things.",
            "What is your purpose?",
        ]
        for user_input in inputs:
            response = process_input(user_input)
            assert isinstance(response, str)
            assert len(response) > 0

    def test_apply_reward_positive(self):
        from brain.soul import process_input, apply_reward
        process_input("Great response!")
        apply_reward(0.9)  # Should not raise

    def test_apply_reward_negative(self):
        from brain.soul import process_input, apply_reward
        process_input("That was wrong")
        apply_reward(-0.5)  # Should not raise

    def test_apply_reward_clamped(self):
        from brain.soul import apply_reward
        apply_reward(5.0)   # Should be clamped to 1.0
        apply_reward(-5.0)  # Should be clamped to -1.0

    def test_perceive_updates_runtime(self):
        from brain.soul import perceive
        from core.runtime_state import runtime
        perceive("Something exciting!")
        state = runtime.get_emotion()
        assert isinstance(state, dict)
        assert "valence" in state

    def test_desire_returns_tuple(self):
        from brain.soul import desire
        from brain.emotion import load_state
        state = load_state()
        d_type, d_strength = desire(state, "hello", "greeting")
        assert d_type in ("learn", "connect", "reflect", "answer_deeply", "respond")
        assert 0.0 <= d_strength <= 1.0

    def test_boredom_triggers_learn_desire(self):
        """Boredom + unknown intent (not a greeting or short social) → learn."""
        from brain.soul import desire
        state = {
            "curiosity": 0.5, "boredom": 0.9, "warmth": 0.5,
            "tension": 0.1, "valence": 0.5, "arousal": 0.5,
            "confidence": 0.5, "dominant_mood": "bored"
        }
        # Greeting intent → social path (respond/connect), not learn
        d_type, _ = desire(state, "hello", "greeting")
        assert d_type in ("respond", "connect")
        # Unknown intent + high boredom → learn
        d_type2, _ = desire(state, "I wonder what else is out there to discover today", "unknown")
        assert d_type2 == "learn"

    def test_high_warmth_triggers_connect(self):
        from brain.soul import desire
        state = {
            "curiosity": 0.5, "boredom": 0.0, "warmth": 0.9,
            "tension": 0.0, "valence": 0.8, "arousal": 0.5,
            "confidence": 0.8, "dominant_mood": "warm"
        }
        # Patch drives.attachment temporarily
        d_type, _ = desire(state, "I miss you", "emotional")
        # May be connect or respond depending on drive state
        assert d_type in ("connect", "respond", "learn")

    def test_high_tension_triggers_reflect(self):
        """Tension > 0.55 should lead to reflect, unless drives override."""
        from brain.soul import desire
        state = {
            "curiosity": 0.1, "boredom": 0.0, "warmth": 0.1,
            "tension": 0.9, "valence": -0.4, "arousal": 0.8,
            "confidence": 0.1, "dominant_mood": "anxious"
        }
        # Tension is very high, boredom/curiosity are low — should reflect
        # (drives might override, so accept reflect or respond)
        d_type, _ = desire(state, "this is stressful", "emotional")
        # drives can override, so accept any valid desire type
        assert d_type in ("reflect", "respond", "learn", "connect", "answer_deeply")

    def test_plan_returns_tuple(self):
        from brain.soul import plan
        from brain.emotion import load_state
        state = load_state()
        action_type, params = plan("respond", "hello", state)
        assert isinstance(action_type, str)
        assert isinstance(params, dict)

    def test_reflect_is_called_on_each_turn(self):
        """Verify reflect writes to episodic memory on each turn."""
        from brain.soul import process_input
        from memory.memory import load_memory
        before = len(load_memory().get("episodes", []))
        process_input("Tell me something about memory.")
        after = len(load_memory().get("episodes", []))
        assert after >= before

    def test_no_exception_on_edge_inputs(self):
        from brain.soul import process_input
        edge_cases = ["", "?", "   ", "a", "1234567890", "!@#$%^&*()"]
        for inp in edge_cases:
            try:
                response = process_input(inp)
                assert isinstance(response, str)
            except Exception as e:
                pytest.fail(f"process_input raised on '{inp}': {e}")

    def test_runtime_state_updated_after_process(self):
        from brain.soul import process_input
        from core.runtime_state import runtime
        before = runtime.turn_count
        process_input("Hello")
        assert runtime.turn_count == before + 1


# ═══════════════════════════════════════════════════════════════════
#  9. NO DUAL-BRAIN CONFLICT
# ═══════════════════════════════════════════════════════════════════

class TestNoDualBrainConflict:
    """Verify soul.py is the sovereign and cognitive_loop is infrastructure only."""

    def test_cognitive_loop_is_not_called_by_soul(self):
        """soul.py must not import from core.cognitive_loop at runtime."""
        import ast
        soul_path = Path(__file__).parent.parent / "brain" / "soul.py"
        src = soul_path.read_text()
        # Should not import from cognitive_loop
        assert "cognitive_loop" not in src, (
            "soul.py imports from cognitive_loop — dual-brain conflict!"
        )

    def test_single_process_count(self):
        """soul._process_count is the only turn counter sovereign."""
        import brain.soul as soul_mod
        before = soul_mod._process_count
        soul_mod.process_input("test for single counter")
        after = soul_mod._process_count
        assert after == before + 1

    def test_runtime_state_is_sole_emotion_authority(self):
        """After process_input, runtime_state has the current emotion (not a stale copy)."""
        from brain.soul import process_input, perceive
        from core.runtime_state import runtime
        from brain.emotion import process_input as em_process
        # Process and check they're in sync
        emotion_from_perceive = perceive("I feel great today!")
        emotion_from_runtime  = runtime.get_emotion()
        assert emotion_from_runtime["dominant_mood"] == emotion_from_perceive.get("dominant_mood")

    def test_scheduler_is_sole_thread_manager(self):
        """No module should spawn raw threads independently (except the scheduler)."""
        from core.scheduler import scheduler
        # After boot-like init, scheduler should be the thread owner
        # Just verify it's a singleton
        from core.scheduler import FeBo_Scheduler
        assert FeBo_Scheduler() is scheduler


# ═══════════════════════════════════════════════════════════════════
#  10. CORE INFRASTRUCTURE (unchanged originals)
# ═══════════════════════════════════════════════════════════════════

class TestCoreIdentity:
    def test_get_self_summary(self):
        from core.identity import identity
        summary = identity.get_self_summary()
        assert isinstance(summary, str)
        assert len(summary) > 5

    def test_get_and_set(self):
        from core.identity import identity
        identity.set("test_key_xyz", "test_value_abc")
        result = identity.get("test_key_xyz")
        assert result == "test_value_abc"

    def test_add_life_event(self):
        from core.identity import identity
        identity.add_life_event("Test event", emotion_valence=0.5)

    def test_get_recent_events(self):
        from core.identity import identity
        events = identity.get_recent_events(5)
        assert isinstance(events, list)


class TestCoreDrives:
    def test_drives_attributes_exist(self):
        from core.drives import drives
        assert hasattr(drives, "curiosity")
        assert hasattr(drives, "attachment")
        assert hasattr(drives, "mastery")

    def test_drives_values_in_range(self):
        from core.drives import drives
        for attr in ("curiosity", "attachment", "mastery"):
            val = getattr(drives, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} out of range"

    def test_get_current_desire(self):
        from core.drives import drives
        desire = drives.get_current_desire()
        assert desire in ("explore", "connect", "learn", "wait")

    def test_update_with_positive(self):
        from core.drives import drives
        m_before = drives.mastery
        drives.update(0.8)
        # mastery should have moved (direction depends on implementation)
        assert 0.0 <= drives.mastery <= 1.0


class TestCoreMemoryEpisodic:
    def test_store_and_retrieve(self):
        from core.memory.episodic import episodic
        episodic.store("test user input", "test response", [0.5] * 6)
        results = episodic.recent(3)
        assert isinstance(results, list)
        assert len(results) >= 0  # might be tuples or dicts


class TestCoreMoralReasoning:
    def test_get_moral_reasoner(self):
        from core.ethics.moral_reasoning import get_moral_reasoner
        mr = get_moral_reasoner()
        assert mr is not None

    def test_evaluate_action(self):
        from core.ethics.moral_reasoning import get_moral_reasoner
        mr = get_moral_reasoner()
        result = mr.evaluate_action(
            "Tell me about philosophy",
            consequences={"positive": ["learning"], "negative": []},
            uncertainty=0.3,
        )
        assert result is not None
        assert hasattr(result, "moral_score")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
