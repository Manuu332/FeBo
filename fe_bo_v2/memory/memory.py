import json
import re
from pathlib import Path

MEMORY_FILE = Path(__file__).with_name("data.json")
MAX_EPISODES = 50

def load_memory():
    if not MEMORY_FILE.exists():
        return {}
    
    with MEMORY_FILE.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_memory(data):
    MEMORY_FILE.parent.mkdir(exist_ok=True)

    with MEMORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def set_memory(key, value):
    data = load_memory()
    data[key] = value
    save_memory(data)

def get_memory(key, default=None):
    data = load_memory()
    return data.get(key, default)

def _as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [item for item in value if item]

    return [value]

def _clean_text(value):
    return str(value).strip()

def add_unique_memory(key, value):
    value = _clean_text(value)
    if not value:
        return list_memory(key)

    data = load_memory()
    items = _as_list(data.get(key))
    known = {str(item).lower() for item in items}

    if value.lower() not in known:
        items.append(value)

    data[key] = items
    save_memory(data)
    return items

def list_memory(key):
    return _as_list(load_memory().get(key))

def set_user_name(name):
    set_memory("user_name", _clean_text(name))

def get_user_name():
    return get_memory("user_name") or get_memory("name")

def add_like(value):
    return add_unique_memory("likes", value)

def get_likes():
    return list_memory("likes")

def add_preference(value):
    return add_unique_memory("preferences", value)

def get_preferences():
    return list_memory("preferences")

def add_goal(value):
    return add_unique_memory("goals", value)

def get_goals():
    return list_memory("goals")

def _normalise_tasks(tasks):
    normalised = []

    for task in _as_list(tasks):
        if isinstance(task, dict):
            title = _clean_text(task.get("title", ""))
            status = task.get("status", "open")
        else:
            title = _clean_text(task)
            status = "open"

        if title:
            normalised.append({"title": title, "status": status})

    return normalised

def add_task(title):
    title = _clean_text(title)
    if not title:
        return list_tasks()

    data = load_memory()
    tasks = _normalise_tasks(data.get("tasks"))
    known = {task["title"].lower() for task in tasks}

    if title.lower() not in known:
        tasks.append({"title": title, "status": "open"})

    data["tasks"] = tasks
    save_memory(data)
    return tasks

def list_tasks(open_only=True):
    tasks = _normalise_tasks(load_memory().get("tasks"))

    if open_only:
        return [task for task in tasks if task["status"] == "open"]

    return tasks

def complete_task(query):
    query = _clean_text(query).lower()
    if not query:
        return None

    data = load_memory()
    tasks = _normalise_tasks(data.get("tasks"))

    for task in tasks:
        if query in task["title"].lower() and task["status"] == "open":
            task["status"] = "done"
            data["tasks"] = tasks
            save_memory(data)
            return task["title"]

    return None

def add_episode(user_input, intent, response, topic=None):
    data = load_memory()
    episodes = _normalise_episodes(data.get("episodes"))
    episodes.append({
        "user": _clean_text(user_input),
        "intent": _clean_text(intent),
        "response": _clean_text(response),
        "topic": _clean_text(topic) if topic else None,
    })

    data["episodes"] = episodes[-MAX_EPISODES:]
    save_memory(data)


def list_episodes(limit=10):
    episodes = _normalise_episodes(load_memory().get("episodes"))
    return episodes[-limit:]


def search_episodes(query, limit=5):
    query = _clean_text(query)
    if not query:
        return []

    query_tokens = _tokens(query)
    scored = []

    for episode in _normalise_episodes(load_memory().get("episodes")):
        haystack = " ".join(str(value or "") for value in episode.values())
        haystack_tokens = _tokens(haystack)
        score = len(query_tokens & haystack_tokens)

        if query.lower() in haystack.lower():
            score += 3

        if score > 0:
            scored.append((score, episode))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [episode for _, episode in scored[:limit]]


def _normalise_episodes(episodes):
    normalised = []

    if not isinstance(episodes, list):
        return normalised

    for episode in episodes:
        if not isinstance(episode, dict):
            continue

        user = _clean_text(episode.get("user", ""))
        response = _clean_text(episode.get("response", ""))
        intent = _clean_text(episode.get("intent", "unknown"))
        topic = episode.get("topic")

        if user or response:
            normalised.append({
                "user": user,
                "intent": intent,
                "response": response,
                "topic": _clean_text(topic) if topic else None,
            })

    return normalised


def _tokens(text):
    return {
        token[:-1] if len(token) > 3 and token.endswith("s") else token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in {"the", "and", "for", "with", "that", "this", "about", "what"}
    }
