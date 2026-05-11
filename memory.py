import re
from memory.memory import (
    add_goal,
    add_like,
    add_preference,
    add_task,
    complete_task,
    get_goals,
    get_likes,
    get_preferences,
    get_user_name,
    list_tasks,
    set_user_name,
)
from memory.context import set_context, get_context, set_topic
from memory.knowledge import add_fact

def handle_memory(user_input):
    text = user_input.lower()

    if "what is my name" in text:
        name = get_context("user_name") or get_user_name()    
        return f"Your name is {name}." if name else "I don't know your name yet."

    if "what do i like" in text:
        likes = get_likes()
        return f"You like {_join_items(likes)}." if likes else "I don't know what you like yet."

    if "what are my preferences" in text:
        preferences = get_preferences()
        return f"You prefer {_join_items(preferences)}." if preferences else "I don't know your preferences yet."

    if "what are my goals" in text:
        goals = get_goals()
        return f"Your goals are {_join_items(goals)}." if goals else "I don't know your goals yet."

    if "what are my tasks" in text or "what are my todos" in text:
        tasks = list_tasks()
        task_titles = [task["title"] for task in tasks]
        return f"Your open tasks are {_join_items(task_titles)}." if task_titles else "You don't have open tasks yet."

    complete_match = re.search(r"\b(?:complete|finish|done with) task\s+(.+)$", user_input, re.IGNORECASE)
    if complete_match:
        task = complete_task(complete_match.group(1))
        return f"Marked '{task}' as done." if task else "I couldn't find an open task matching that."

    task_match = re.search(r"\b(?:add task|add todo|todo|remind me to)\s+(.+)$", user_input, re.IGNORECASE)
    if task_match:
        task = task_match.group(1).strip()
        add_task(task)
        add_fact("user", "has_task", task)
        set_topic(task)
        return f"I added '{task}' to your open tasks."

    name_match = re.search(r"\bmy name is\s+(.+)$", user_input, re.IGNORECASE)    
    if name_match:
        name = name_match.group(1).strip()
        set_context("user_name", name)
        set_user_name(name)
        add_fact("user", "has_name", name)
        return f"It's nice to make your acquaintance {name}."

    goal_match = re.search(r"\b(?:my goal is|i want to|i need to)\s+(.+)$", user_input, re.IGNORECASE)
    if goal_match:
        goal = goal_match.group(1).strip()
        add_goal(goal)
        add_fact("user", "has_goal", goal)
        set_topic(goal)
        return f"I'll remember that goal: {goal}."

    preference_match = re.search(r"\bi prefer\s+(.+)$", user_input, re.IGNORECASE)
    if preference_match:
        preference = preference_match.group(1).strip()
        add_preference(preference)
        add_fact("user", "prefers", preference)
        set_topic(preference)
        return "I'll remember that preference."
    
    like_match = re.search(r"\bi like\s+(.+)$|\bi love\s+(.+)$", user_input, re.IGNORECASE)
    if like_match:
        thing = next(group for group in like_match.groups() if group)
        thing = thing.strip()
        add_like(thing)
        add_fact("user", "likes", thing)
        set_context("likes", thing)
        set_topic(thing)
        return f"I'll remember that."
    
    return "I didn't quite get that."

def _join_items(items):
    items = [str(item) for item in items if item]

    if not items:
        return ""

    if len(items) == 1:
        return items[0]

    return ", ".join(items[:-1]) + f", and {items[-1]}"
