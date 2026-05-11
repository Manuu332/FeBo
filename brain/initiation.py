"""
FeBo initiates conversation when you've been absent.
Runs in background thread.
"""

import threading
import time
from pathlib import Path
from config.settings import ENABLE_INITIATION, INITIATION_INTERVAL_SECONDS

LAST_USER_TIME_FILE = Path(__file__).parent.parent / "memory" / "last_user_time.json"

def _get_last_user_time():
    try:
        with open(LAST_USER_TIME_FILE, "r") as f:
            import json
            return json.load(f).get("last_interaction", time.time())
    except Exception:
        return time.time()

def _set_last_user_time(t):
    with open(LAST_USER_TIME_FILE, "w") as f:
        import json
        json.dump({"last_interaction": t}, f)

def update_activity():
    """Call this whenever user speaks."""
    _set_last_user_time(time.time())

def _initiation_loop():
    if not ENABLE_INITIATION:
        return
    while True:
        time.sleep(60)  # check every minute
        try:
            last = _get_last_user_time()
            now = time.time()
            if now - last > INITIATION_INTERVAL_SECONDS:
                # It's been too long. Ask to speak.
                from brain.soul import enqueue_proactive_message
                enqueue_proactive_message(
                    "I've been thinking while you were away… I'd like to talk when you're ready."
                )
                # reset timer to avoid spamming
                _set_last_user_time(now - INITIATION_INTERVAL_SECONDS + 300)
        except Exception:
            pass

def start_initiation_thread():
    thread = threading.Thread(target=_initiation_loop, daemon=True)
    thread.start()
