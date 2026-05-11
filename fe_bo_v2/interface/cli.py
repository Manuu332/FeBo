"""
interface/cli.py
─────────────────
FeBo's conversational CLI.

Commands:
  exit                 – graceful shutdown
  how are you          – emotional state
  what have you learned / what do you know – knowledge stats
  what have you been thinking – background thoughts
  status               – full observability snapshot
  observe              – emotion drift + health
  reward <val>         – apply reward signal (-1.0 to 1.0)
  learn about <topic>  – force a learning session
  who are you          – identity summary
  scheduler            – show background task status
  help                 – list commands
  <anything else>      – conversation
"""

from brain.soul import process_input, apply_reward
from brain.ai import get_experience_summary
from brain.background import get_recent_thoughts
from brain.learner import get_knowledge_stats
from brain.emotion import get_mood_summary
from core.identity import identity
from brain.initiation import start_initiation_thread
from config.settings import ENABLE_INITIATION
from core.logging_config import get_logger

logger = get_logger("interface.cli")

_HELP = """
Commands:
  exit / quit          – graceful shutdown
  how are you          – FeBo's emotional state
  your mood            – same as above
  who are you          – identity summary
  what do you know     – knowledge statistics
  what have you learned – same as above
  what have you been thinking – background thoughts
  learn about <topic>  – force topic learning
  reward <-1.0 to 1.0> – apply reward signal (e.g. reward 0.8)
  status               – full system status
  observe              – emotion drift + health log
  scheduler            – background task status
  help / ?             – this message
  <anything>           – conversation
"""


def start_cli():
    # Start proactive initiation thread if enabled
    if ENABLE_INITIATION:
        try:
            start_initiation_thread()
        except Exception as e:
            logger.debug(f"Initiation thread failed: {e}")

    # Greeting
    summary = get_experience_summary()
    stage        = summary.get("stage", "newborn")
    interactions = summary.get("interactions", 0)
    words        = summary.get("words_learned", 0)
    knowledge    = get_knowledge_stats()

    print()
    print("FeBo is awake.")
    print(f"Identity: {identity.get_self_summary()}")
    print(f"Stage: {stage}")

    if interactions > 0:
        print(f"She has had {interactions} interaction(s) and knows {words} word(s).")
    else:
        print("She has never spoken before. She is listening.")

    if knowledge.get("total_entries", 0) > 0:
        print(f"She has read {knowledge.get('sources_read', 0)} source(s) "
              f"across {knowledge.get('unique_topics', 0)} topic(s).")
        sample = knowledge.get("sample_topics", [])
        if sample:
            print(f"She has been thinking about: {', '.join(sample)}")

    thoughts = get_recent_thoughts(1)
    if thoughts:
        print(f'She has been thinking: "{thoughts[-1]["thought"]}"')

    print()
    print("Type 'help' for commands. Type 'exit' to quit.")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nFeBo: I'll be here.")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        # ── Exit ──────────────────────────────────────────────────
        if lower in ("exit", "quit", "bye", "goodbye"):
            print("FeBo: I'll be here.")
            break

        # ── Help ──────────────────────────────────────────────────
        if lower in ("help", "?", "commands"):
            print(_HELP)
            continue

        # ── Mood ─────────────────────────────────────────────────
        if lower in ("how are you", "how are you feeling", "how do you feel",
                     "your mood", "what's your mood"):
            print(f"FeBo: {get_mood_summary()}")
            print()
            continue

        # ── Identity ─────────────────────────────────────────────
        if lower in ("who are you", "your identity", "tell me about yourself"):
            try:
                from core.runtime_state import runtime
                snap = runtime.snapshot()
                print(f"FeBo: {identity.get_self_summary()}")
                print(f"      Uptime: {snap['uptime_s']:.0f}s  Turns: {snap['turn_count']}")
                print(f"      Mood: {snap['mood']}  Desire: {snap['desire']}")
                print(f"      Avg reward: {snap['avg_reward']:.3f}")
            except Exception:
                print(f"FeBo: {identity.get_self_summary()}")
            print()
            continue

        # ── Knowledge ────────────────────────────────────────────
        if lower in ("what do you know", "what have you learned", "your knowledge"):
            stats = get_knowledge_stats()
            if stats.get("total_entries", 0) == 0:
                print("FeBo: I haven't read much yet. Ask me to learn about something.")
            else:
                print(f"FeBo: I've read {stats.get('sources_read', 0)} sources "
                      f"across {stats.get('unique_topics', 0)} topics.")
                sample = stats.get("sample_topics", [])
                if sample:
                    print(f"      Some things I've explored: {', '.join(sample)}")
            print()
            continue

        # ── Background thoughts ───────────────────────────────────
        if lower in ("what have you been thinking", "what are you thinking", "your thoughts"):
            thoughts = get_recent_thoughts(3)
            if thoughts:
                for t in thoughts:
                    print(f"FeBo: {t['thought']}")
            else:
                print("FeBo: I haven't had long enough to think yet.")
            print()
            continue

        # ── Reward signal ─────────────────────────────────────────
        if lower.startswith("reward "):
            try:
                val = float(user_input.split()[1])
                apply_reward(val)
                print(f"FeBo: [Reward {val:+.2f} applied. Thank you.]")
            except (ValueError, IndexError):
                print("FeBo: Please provide a number, e.g. 'reward 0.8' or 'reward -0.5'")
            print()
            continue

        # ── Force learning ────────────────────────────────────────
        if lower.startswith("learn about "):
            topic = user_input[12:].strip()
            if topic:
                print(f"FeBo: [Starting to learn about '{topic}'...]")
                try:
                    from brain.learner import learn_about
                    result = learn_about(topic, depth="normal")
                    print(f"FeBo: I've just read {result.get('sources_read', 0)} "
                          f"source(s) about {topic}.")
                except Exception as e:
                    print(f"FeBo: I tried to learn but ran into a problem: {e}")
            print()
            continue

        # ── Observability ─────────────────────────────────────────
        if lower in ("status", "system status"):
            try:
                from core.observability import snapshot
                print(snapshot())
            except Exception as e:
                print(f"[status unavailable: {e}]")
            print()
            continue

        if lower in ("observe", "health", "drift"):
            try:
                from core.observability import emotion_tracker
                drift = emotion_tracker.compute_drift()
                from core.observability import health_monitor, HEALTH_LOG
                import json, time as _time
                events = []
                if HEALTH_LOG.exists():
                    with open(HEALTH_LOG) as f:
                        events = [json.loads(l) for l in f if l.strip()]
                print(f"FeBo: Emotion drift from baseline: {drift}")
                if events:
                    print(f"      Recent health events ({len(events)}):")
                    for ev in events[-3:]:
                        print(f"        {ev.get('warning','?')}")
                else:
                    print("      No health events detected.")
            except Exception as e:
                print(f"[observe error: {e}]")
            print()
            continue

        if lower in ("scheduler", "background tasks"):
            try:
                from core.scheduler import scheduler
                tasks = scheduler.status()
                print("Background tasks:")
                for t in tasks:
                    last = f"{t['last_run_ago']}s ago" if t["last_run_ago"] else "never"
                    print(f"  {t['name']:<25} every {t['interval_s']:>5.0f}s  "
                          f"runs={t['run_count']:>4}  errors={t['error_count']}  last={last}")
            except Exception as e:
                print(f"[scheduler error: {e}]")
            print()
            continue

        # ── Conversation ──────────────────────────────────────────
        response = process_input(user_input)
        print(f"FeBo: {response}")
        print()
