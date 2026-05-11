import re

from memory.memory import load_memory, save_memory


RELATION_ALIASES = {
    "depends on": "depends_on",
    "depend on": "depends_on",
    "requires": "depends_on",
    "needs": "depends_on",
    "supports": "supports",
    "support": "supports",
    "helps": "supports",
    "enables": "enables",
    "causes": "causes",
    "cause": "causes",
    "leads to": "causes",
    "conflicts with": "conflicts_with",
    "conflict with": "conflicts_with",
    "blocks": "blocks",
    "block": "blocks",
    "is": "is",
    "does not depend on": "not_depends_on",
    "doesn't depend on": "not_depends_on",
    "doesnt depend on": "not_depends_on",
    "does not need": "not_depends_on",
    "doesn't need": "not_depends_on",
    "doesnt need": "not_depends_on",
    "does not require": "not_depends_on",
    "doesn't require": "not_depends_on",
    "doesnt require": "not_depends_on",
    "does not support": "not_supports",
    "doesn't support": "not_supports",
    "doesnt support": "not_supports",
    "does not conflict with": "not_conflicts_with",
    "doesn't conflict with": "not_conflicts_with",
    "doesnt conflict with": "not_conflicts_with",
}

RELATION_DISPLAY = {
    "enables": "enables",
    "is": "is",
    "not_depends_on": "does not depend on",
    "not_supports": "does not support",
    "not_conflicts_with": "does not conflict with",
}

OPPOSITE_RELATIONS = {
    "depends_on": "not_depends_on",
    "not_depends_on": "depends_on",
    "supports": "not_supports",
    "not_supports": "supports",
    "conflicts_with": "not_conflicts_with",
    "not_conflicts_with": "conflicts_with",
}


def add_fact(subject, relation, object_value, source="user", confidence=1.0):
    subject = _clean_term(subject)
    relation = normalize_relation(relation)
    object_value = _clean_term(object_value)

    if not subject or not relation or not object_value:
        return None

    data = load_memory()
    facts = _normalise_facts(data.get("facts"))
    candidate = {
        "subject": subject,
        "relation": relation,
        "object": object_value,
        "source": source,
        "confidence": confidence,
    }

    if not any(_same_fact(fact, candidate) for fact in facts):
        facts.append(candidate)

    data["facts"] = facts
    save_memory(data)
    return candidate


def remove_fact(subject=None, relation=None, object_value=None):
    data = load_memory()
    facts = _normalise_facts(data.get("facts"))
    relation = normalize_relation(relation) if relation else None

    kept = []
    removed = []
    for fact in facts:
        matches = True
        if subject and not _terms_related(subject, fact["subject"]):
            matches = False
        if relation and fact["relation"] != relation:
            matches = False
        if object_value and not _terms_related(object_value, fact["object"]):
            matches = False

        if matches:
            removed.append(fact)
        else:
            kept.append(fact)

    data["facts"] = kept
    save_memory(data)
    return removed


def replace_fact(old_subject, old_relation, old_object, new_subject, new_relation, new_object):
    removed = remove_fact(old_subject, old_relation, old_object)
    added = add_fact(new_subject, new_relation, new_object)
    return removed, added


def list_facts():
    return _normalise_facts(load_memory().get("facts"))


def list_facts_with_ids():
    return list(enumerate(list_facts(), start=1))


def find_facts(subject=None, relation=None, object_value=None):
    subject = _clean_term(subject) if subject else None
    relation = normalize_relation(relation) if relation else None
    object_value = _clean_term(object_value) if object_value else None

    matches = []
    for fact in list_facts():
        if subject and fact["subject"].lower() != subject.lower():
            continue
        if relation and fact["relation"] != relation:
            continue
        if object_value and fact["object"].lower() != object_value.lower():
            continue

        matches.append(fact)

    return matches


def related_facts(term):
    term = _clean_term(term)
    if not term:
        return []

    return [
        fact for fact in list_facts()
        if _terms_related(term, fact["subject"]) or _terms_related(term, fact["object"])
    ]


def facts_about(term):
    return related_facts(term)


def contradiction_pairs(term=None):
    facts = related_facts(term) if term else list_facts()
    contradictions = []

    for index, fact in enumerate(facts):
        opposite = OPPOSITE_RELATIONS.get(fact["relation"])
        if not opposite:
            continue

        for other in facts[index + 1:]:
            if (
                other["relation"] == opposite
                and _terms_related(fact["subject"], other["subject"])
                and _terms_related(fact["object"], other["object"])
            ):
                contradictions.append((fact, other))

    return contradictions


def dependencies_for(subject):
    return [fact["object"] for fact in related_facts(subject) if fact["relation"] == "depends_on" and _terms_related(subject, fact["subject"])]


def dependents_of(object_value):
    return [fact["subject"] for fact in related_facts(object_value) if fact["relation"] == "depends_on" and _terms_related(object_value, fact["object"])]


def conflicts_for(term):
    facts = related_facts(term)
    conflicts = []

    for fact in facts:
        if fact["relation"] in {"conflicts_with", "blocks"}:
            conflicts.append(fact)

    return conflicts


def supports_for(term):
    facts = related_facts(term)
    return [fact for fact in facts if fact["relation"] in {"supports", "enables"}]


def normalize_relation(relation):
    relation = _clean_relation(relation)
    return RELATION_ALIASES.get(relation, relation.replace(" ", "_"))


def format_fact(fact):
    if fact["relation"] == "depends_on":
        relation = _verb_for_subject(fact["subject"], "depends on", "depend on")
        return f"{fact['subject']} {relation} {fact['object']}"

    if fact["relation"] == "supports":
        relation = _verb_for_subject(fact["subject"], "supports", "support")
        return f"{fact['subject']} {relation} {fact['object']}"

    if fact["relation"] == "causes":
        relation = _verb_for_subject(fact["subject"], "causes", "cause")
        return f"{fact['subject']} {relation} {fact['object']}"

    if fact["relation"] == "conflicts_with":
        relation = _verb_for_subject(fact["subject"], "conflicts with", "conflict with")
        return f"{fact['subject']} {relation} {fact['object']}"

    if fact["relation"] == "blocks":
        relation = _verb_for_subject(fact["subject"], "blocks", "block")
        return f"{fact['subject']} {relation} {fact['object']}"

    relation = RELATION_DISPLAY.get(fact["relation"], fact["relation"].replace("_", " "))
    return f"{fact['subject']} {relation} {fact['object']}"


def summarize_subject(term):
    facts = related_facts(term)
    if not facts:
        return f"I don't know any facts about {term} yet."

    formatted = "; ".join(format_fact(fact) for fact in facts)
    return f"What I know about {term}: {formatted}."


def _normalise_facts(facts):
    normalised = []

    if not isinstance(facts, list):
        return normalised

    for fact in facts:
        if not isinstance(fact, dict):
            continue

        subject = _clean_term(fact.get("subject", ""))
        relation = normalize_relation(fact.get("relation", ""))
        object_value = _clean_term(fact.get("object", ""))

        if subject and relation and object_value:
            normalised.append({
                "subject": subject,
                "relation": relation,
                "object": object_value,
                "source": fact.get("source", "user"),
                "confidence": fact.get("confidence", 1.0),
            })

    return normalised


def _same_fact(left, right):
    return (
        left["subject"].lower() == right["subject"].lower()
        and left["relation"] == right["relation"]
        and left["object"].lower() == right["object"].lower()
    )


def _terms_related(left, right):
    left = _clean_term(left)
    right = _clean_term(right)

    if not left or not right:
        return False

    if left.lower() in right.lower() or right.lower() in left.lower():
        return True

    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    return bool(left_tokens & right_tokens)


def _tokens(text):
    tokens = set()

    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if len(token) > 3 and token.endswith("s"):
            token = token[:-1]
        if token not in {"the", "and", "for", "with", "that", "this", "about"}:
            tokens.add(token)

    return tokens


def _clean_term(value):
    value = str(value).strip()
    value = re.sub(r"[?.!]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _clean_relation(value):
    value = str(value).strip().lower()
    value = value.replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    return value


def _verb_for_subject(subject, singular, plural):
    subject = subject.lower().strip()
    if subject.endswith("s") and not subject.endswith("ss"):
        return plural

    return singular
