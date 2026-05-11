"""
main.py — FeBo unified boot + single scheduler.
brain/soul.py is sovereign. core/ is infrastructure.
"""
import sys
import time
from pathlib import Path
from core.logging_config import get_logger
from core.lifecycle import lifecycle
logger = get_logger("main")

def boot() -> bool:
    logger.info("="*55)
    logger.info("FeBo — booting")
    logger.info("="*55)
    try:
        from core.runtime_state import runtime
        runtime.boot_complete = False
        logger.info("  [ok] Runtime state")
    except Exception as e:
        logger.critical(f"Runtime state failed: {e}"); return False
    try:
        from core.identity import identity
        logger.info(f"  [ok] Identity: {identity.get_self_summary()}")
    except Exception as e:
        logger.critical(f"Identity failed: {e}"); return False
    try:
        from brain.emotion import load_state
        state = load_state()
        logger.info(f"  [ok] Emotion: mood={state.get('dominant_mood','?')}")
        from core.runtime_state import runtime
        runtime.update_emotion(state)
    except Exception as e:
        logger.warning(f"Emotion load failed: {e}")
    try:
        from core.drives import drives
        logger.info(f"  [ok] Drives: cur={drives.curiosity:.2f} att={drives.attachment:.2f}")
    except Exception as e:
        logger.warning(f"Drives failed: {e}")
    try:
        from core.reasoning.emergent_nn import reasoner
        logger.info(f"  [ok] Reasoner: vocab={reasoner.vocab.next_idx}")
    except Exception as e:
        logger.warning(f"Reasoner failed: {e}")
    try:
        from core.memory.episodic import episodic
        logger.info("  [ok] Episodic memory")
    except Exception as e:
        logger.warning(f"Episodic memory failed: {e}")
    try:
        from core.consciousness.blackboard import GlobalWorkspace
        from core.consciousness.attention import AttentionMechanism
        from core.consciousness.theory_of_mind import get_theory_of_mind
        get_theory_of_mind(); logger.info("  [ok] Consciousness infrastructure")
    except Exception as e:
        logger.warning(f"Consciousness failed: {e}")
    try:
        from core.ethics.moral_reasoning import get_moral_reasoner
        get_moral_reasoner(); logger.info("  [ok] Moral reasoner")
    except Exception as e:
        logger.warning(f"Ethics failed: {e}")
    _register_background_tasks()
    try:
        from core.runtime_state import runtime
        runtime.boot_complete = True
    except Exception: pass
    logger.info("="*55)
    logger.info("FeBo — boot complete")
    logger.info("="*55)
    return True

def _register_background_tasks():
    from core.scheduler import scheduler
    try:
        from config.settings import ENABLE_DREAMS, ENABLE_DEFENDER_AGENT, DREAM_INTERVAL_SECONDS
    except Exception:
        ENABLE_DREAMS = True; ENABLE_DEFENDER_AGENT = True; DREAM_INTERVAL_SECONDS = 300

    def _drives_decay():
        try:
            from core.drives import drives
            import random
            drives.curiosity  = min(1.0, drives.curiosity + random.uniform(-0.01, 0.02))
            drives.attachment = max(0.0, drives.attachment - 0.005)
            drives.mastery    = min(1.0, drives.mastery + random.uniform(-0.005, 0.01))
            drives._save()
        except Exception: pass
    scheduler.register("drives_decay", 60, _drives_decay)

    def _emotion_decay():
        try:
            from brain.emotion import load_state, save_state, _decay_toward_baseline
            state = load_state()
            state["arousal"] = _decay_toward_baseline(state["arousal"], 0.5, 0.03)
            state["tension"] = _decay_toward_baseline(state["tension"], 0.0, 0.05)
            state["boredom"] = min(1.0, state.get("boredom", 0.0) + 0.01)
            save_state(state)
            from core.runtime_state import runtime
            runtime.update_emotion(state)
        except Exception: pass
    scheduler.register("emotion_decay", 120, _emotion_decay)

    if ENABLE_DREAMS:
        def _dream_tick():
            try:
                from core.consciousness.blackboard import GlobalWorkspace
                from core.reflection.dreamer import get_dream_system
                ds = get_dream_system(GlobalWorkspace())
                fn = getattr(ds, "_generate_dream", None) or getattr(ds, "tick", None)
                if fn: fn()
            except Exception: pass
        scheduler.register("dream_cycle", DREAM_INTERVAL_SECONDS, _dream_tick, max_duration_s=25)

    if ENABLE_DEFENDER_AGENT:
        def _defender():
            try:
                log_path = Path("logs/audit.log")
                if log_path.exists():
                    lines = log_path.read_text().splitlines()[-10:]
                    for line in lines:
                        if "critical" in line.lower():
                            logger.warning(f"[defender] {line[:100]}")
            except Exception: pass
        scheduler.register("defender", 30, _defender)

    def _self_learning():
        try:
            from brain.emotion import load_state
            state = load_state()
            if state.get("curiosity", 0.8) > 0.75:
                from brain.learner import learn_about, pick_curiosity_topic
                topic = pick_curiosity_topic()
                learn_about(topic, "deep" if state.get("curiosity",0.8) > 0.9 else "normal")
        except Exception: pass
    scheduler.register("self_learning", 1800, _self_learning, max_duration_s=60)

    def _background_thought():
        try:
            from brain.background import _add_thought, _SPONTANEOUS_THOUGHTS
            import random
            from brain.emotion import load_state
            state = load_state()
            if state.get("boredom", 0.0) > 0.4 or random.random() < 0.3:
                _add_thought(random.choice(_SPONTANEOUS_THOUGHTS))
        except Exception: pass
    scheduler.register("background_thought", 300, _background_thought)

    def _identity_save():
        try:
            from core.identity import identity
            identity.get("name")
        except Exception: pass
    scheduler.register("identity_save", 300, _identity_save)

    def _obs_health():
        try:
            from core.observability import health_monitor
            from brain.emotion import load_state
            from core.runtime_state import runtime
            state = load_state()
            vocab_sz = 0
            try:
                from core.reasoning.emergent_nn import reasoner as _r
                vocab_sz = getattr(getattr(_r, "vocab", None), "next_idx", 0)
            except Exception: pass
            health_monitor.check(runtime.turn_count, state.get("dominant_mood","?"), vocab_sz, runtime.last_reward)
        except Exception: pass
    scheduler.register("obs_health", 60, _obs_health)

    scheduler.start()
    logger.info(f"  [ok] Scheduler: {len(scheduler._tasks)} tasks")

def shutdown():
    logger.info("FeBo — shutting down")
    try:
        from core.scheduler import scheduler; scheduler.stop()
    except Exception: pass
    try:
        from brain.emotion import load_state, save_state; save_state(load_state())
    except Exception: pass
    try:
        from core.reasoning.emergent_nn import reasoner; reasoner._save()
    except Exception: pass
    try:
        from core.emotion_rlhf import emotion_rlhf; emotion_rlhf.save()
    except Exception: pass
    try:
        from core.identity import identity; identity.close()
    except Exception: pass
    logger.info("FeBo — shutdown complete")

def main():
    import atexit
    atexit.register(shutdown)
    lifecycle.register_shutdown(shutdown)
    ok = boot()
    if not ok:
        print("FeBo failed to boot. Check logs/febo.log."); sys.exit(1)
    try:
        from brain.background import start_background_thoughts
        start_background_thoughts()
    except Exception: pass
    try:
        from interface.cli import start_cli
        start_cli()
    except KeyboardInterrupt:
        print("\nFeBo: I'll be here.")
    except Exception as e:
        logger.error(f"CLI error: {e}", exc_info=True)
    finally:
        shutdown()

if __name__ == "__main__":
    main()
