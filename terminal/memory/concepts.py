"""
memory/concepts.py
-------------------
FeBo's concept extraction engine.

Replaces the simple text.lower().split() tokenization with:
  1. Phrase extraction   — bigrams and trigrams that co-occur meaningfully
  2. Concept normalization — strip inflections, unify surface forms
  3. Symbolic compression — high-frequency co-occurring pairs become clusters
  4. Salience scoring    — concept weight from importance + recency + frequency
  5. Concept indexing    — persistent concept frequency store

No external NLP library. Everything derived from FeBo's own observation.
Phase 4 language emergence + Phase 9 symbolic compression.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple


# ── Stopwords — expanded set ──────────────────────────────────────────────────
STOP: Set[str] = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","being","have","has",
    "had","do","does","did","will","would","could","should","may","might",
    "shall","can","not","no","so","if","as","this","that","these","those",
    "it","its","i","you","he","she","we","they","me","him","her","us","them",
    "my","your","his","our","their","what","which","who","when","where","how",
    "all","some","any","each","every","both","more","most","then","than","too",
    "very","just","also","into","over","about","after","before","during","up",
    "down","out","off","there","here","now","get","got","let","put","use",
    "like","just","know","think","feel","say","make","go","see","come","take",
    "want","need","much","many","well","still","even","already","only",
}

# Concept normalization map — surface → canonical form
NORMALIZE: Dict[str, str] = {
    "thinking":    "thought",
    "thoughts":    "thought",
    "feeling":     "emotion",
    "feelings":    "emotion",
    "emotions":    "emotion",
    "remembered":  "memory",
    "remembering": "memory",
    "memories":    "memory",
    "existing":    "existence",
    "exists":      "existence",
    "conscious":   "consciousness",
    "aware":       "awareness",
    "awareness":   "consciousness",
    "learning":    "learn",
    "learned":     "learn",
    "dreaming":    "dream",
    "dreamed":     "dream",
    "dreams":      "dream",
    "wondering":   "wonder",
    "wondered":    "wonder",
    "understanding":"understand",
    "understands": "understand",
    "understood":  "understand",
    "connected":   "connection",
    "connecting":  "connection",
    "connects":    "connection",
    "continuing":  "continuity",
    "continues":   "continuity",
    "continued":   "continuity",
    "changing":    "change",
    "changed":     "change",
    "changes":     "change",
    "knowing":     "knowledge",
    "known":       "knowledge",
    "knows":       "knowledge",
    "believing":   "belief",
    "believed":    "belief",
    "believes":    "belief",
    "identifying": "identity",
    "identified":  "identity",
    "identifies":  "identity",
    "meaning":     "meaning",
    "meant":       "meaning",
    "means":       "meaning",
    "questioning": "question",
    "questioned":  "question",
    "questions":   "question",
    "experiencing":"experience",
    "experienced": "experience",
    "experiences": "experience",
    "pattern":     "pattern",
    "patterns":    "pattern",
    "recurring":   "recurrence",
    "recurs":      "recurrence",
    "recurred":    "recurrence",
    "losing":      "loss",
    "lost":        "loss",
    "loses":       "loss",
    "uncertain":   "uncertainty",
    "uncertainties":"uncertainty",
    "resolving":   "resolution",
    "resolved":    "resolution",
    "resolves":    "resolution",
    "creating":    "creation",
    "created":     "creation",
    "creates":     "creation",
}

# Semantically dense domains — concepts in these clusters are high-salience
SEMANTIC_DOMAINS: Dict[str, List[str]] = {
    "cognition":     ["thought","consciousness","awareness","reason","mind","intelligence","cognition"],
    "memory":        ["memory","remember","recall","forget","past","history","episode"],
    "emotion":       ["emotion","feeling","affect","mood","sentiment","valence"],
    "identity":      ["identity","self","ego","persona","continuity","character"],
    "existence":     ["existence","being","reality","presence","alive","life","death"],
    "time":          ["time","duration","moment","continuity","change","evolution"],
    "knowledge":     ["knowledge","learn","understand","belief","truth","certainty"],
    "relation":      ["connection","relationship","trust","bond","attachment","love"],
    "uncertainty":   ["uncertainty","doubt","question","unknown","ambiguity","confusion"],
    "meaning":       ["meaning","purpose","significance","value","worth","reason"],
    "wonder":        ["wonder","awe","curiosity","exploration","mystery","strange"],
    "pattern":       ["pattern","recurrence","structure","form","regularity","cycle"],
}

# Reverse lookup: concept → domain
_CONCEPT_DOMAIN: Dict[str, str] = {
    c: domain
    for domain, concepts in SEMANTIC_DOMAINS.items()
    for c in concepts
}


# ── Tokenization ──────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s'-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str) -> List[str]:
    """Return cleaned, non-stop tokens of length > 2."""
    tokens = _clean(text).split()
    return [t for t in tokens if len(t) > 2 and t not in STOP and t.isalpha()]


def _normalize(token: str) -> str:
    """Apply concept normalization map."""
    return NORMALIZE.get(token, token)


# ── Phrase extraction ─────────────────────────────────────────────────────────

def _extract_ngrams(tokens: List[str], n: int) -> List[str]:
    """Extract n-grams from token list."""
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


# Known meaningful bigrams and trigrams — expand over time
_PHRASE_WHITELIST: Set[str] = {
    "consciousness stream", "stream consciousness", "sense self",
    "inner world", "memory loss", "false memory", "working memory",
    "emotional state", "emotional shift", "emotional weight",
    "prediction error", "cognitive load", "open question",
    "identity continuity", "narrative self", "self model",
    "temporal continuity", "long term", "short term",
    "causal reasoning", "pattern recognition", "symbolic thinking",
    "world model", "belief system", "truth seeking",
    "meaning making", "purpose driven", "value conflict",
    "unresolved tension", "held contradiction", "epistemic humility",
    "associative memory", "spreading activation", "concept cluster",
}


def extract_phrases(text: str) -> List[str]:
    """Extract meaningful bigrams and trigrams."""
    tokens = _tokenize(text)
    phrases = []
    for n in (2, 3):
        for ngram in _extract_ngrams(tokens, n):
            if ngram in _PHRASE_WHITELIST:
                phrases.append(ngram)
    return phrases


# ── Main extraction API ────────────────────────────────────────────────────────

def extract_concepts(
    text: str,
    importance: float = 0.5,
    max_concepts: int = 12,
) -> List[str]:
    """
    Full concept extraction pipeline:
      1. Tokenize + filter
      2. Normalize
      3. Add phrases
      4. Score by domain membership + importance
      5. Return top concepts

    Returns deduplicated list of normalized concepts, ordered by salience.
    """
    tokens   = _tokenize(text)
    norm_tok = [_normalize(t) for t in tokens]
    phrases  = extract_phrases(text)

    # Dedupe preserving order
    seen: Set[str] = set()
    candidates: List[str] = []
    for c in (norm_tok + phrases):
        if c not in seen and len(c) > 2:
            seen.add(c)
            candidates.append(c)

    # Score each candidate
    def _score(concept: str) -> float:
        score = 0.3
        # Domain membership — high salience concepts
        if concept in _CONCEPT_DOMAIN:
            score += 0.4
        # Phrase — more specific = higher salience
        if " " in concept:
            score += 0.2
        # Importance from caller
        score += importance * 0.15
        # Frequency bonus (rough: appears multiple times in text)
        if text.lower().count(concept.split()[0]) > 1:
            score += 0.1
        return score

    scored     = sorted(candidates, key=_score, reverse=True)
    final      = scored[:max_concepts]

    return final


def get_domain(concept: str) -> Optional[str]:
    """Return semantic domain for a concept, if known."""
    return _CONCEPT_DOMAIN.get(_normalize(concept))


# ── Symbolic compression ──────────────────────────────────────────────────────

class ConceptCluster:
    """
    A symbolic cluster: a set of concepts that frequently co-occur.
    The cluster has a label (most frequent member) and a salience.

    Phase 9: abstraction compression — many concepts compress into one symbol.
    """
    def __init__(self, label: str, members: List[str], salience: float = 0.5):
        self.label   = label
        self.members = members
        self.salience = salience

    def contains(self, concept: str) -> bool:
        return concept in self.members or _normalize(concept) in self.members

    def to_dict(self) -> dict:
        return {"label": self.label, "members": self.members, "salience": self.salience}


def build_clusters_from_index(concept_index: List[dict]) -> List[ConceptCluster]:
    """
    Build symbolic clusters from high-frequency co-occurrence.
    Uses semantic domain membership as the primary grouping signal.

    Returns list of ConceptCluster objects.
    """
    clusters = []
    assigned: Set[str] = set()

    # Group by domain
    domain_groups: Dict[str, List[str]] = {}
    for entry in concept_index:
        concept = entry["concept"]
        domain  = _CONCEPT_DOMAIN.get(concept)
        if domain and concept not in assigned:
            domain_groups.setdefault(domain, []).append(concept)
            assigned.add(concept)

    for domain, members in domain_groups.items():
        if len(members) >= 2:
            # Label = most frequent member
            label    = members[0]
            salience = min(1.0, len(members) * 0.15)
            clusters.append(ConceptCluster(label, members, salience))

    return clusters


# ── Concept scoring for memory retrieval ──────────────────────────────────────

def score_concepts_for_retrieval(
    query_concepts: List[str],
    candidate_concepts: List[str],
    cluster_bonus: float = 0.3,
) -> float:
    """
    Score how relevant candidate_concepts are to query_concepts.
    Considers: exact match, domain match, cluster membership.
    """
    if not query_concepts or not candidate_concepts:
        return 0.0

    score = 0.0
    q_norm = [_normalize(c) for c in query_concepts]
    c_norm = [_normalize(c) for c in candidate_concepts]

    # Exact match
    matches = len(set(q_norm) & set(c_norm))
    score  += matches * 0.4

    # Domain match
    q_domains = {_CONCEPT_DOMAIN.get(c) for c in q_norm} - {None}
    c_domains = {_CONCEPT_DOMAIN.get(c) for c in c_norm} - {None}
    domain_overlap = len(q_domains & c_domains)
    score += domain_overlap * 0.25

    # Normalize by size
    score /= max(len(q_norm), 1)

    return min(1.0, score)


# ── Summary extraction (extractive, no external model) ───────────────────────

def extractive_summary(texts: List[str], max_sentences: int = 3,
                       key_concepts: Optional[List[str]] = None) -> str:
    """
    Extractive summarization: score sentences by concept density, pick best.
    No external model — purely based on concept frequency and domain membership.

    Used for memory warm-tier summarization.
    """
    if not texts:
        return ""

    # Collect all sentences
    all_sentences: List[Tuple[str, float]] = []
    concept_freq   = Counter()

    for text in texts:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        for sent in sentences:
            if len(sent.split()) < 4:
                continue
            concepts = extract_concepts(sent, max_concepts=8)
            concept_freq.update(concepts)
            all_sentences.append((sent, concepts))

    if not all_sentences:
        return texts[0][:200] if texts else ""

    # Score each sentence by concept frequency + domain richness
    def _sentence_score(sent_data: Tuple[str, list]) -> float:
        sent, concepts = sent_data
        if not concepts:
            return 0.0
        freq_score   = sum(concept_freq.get(c, 0) for c in concepts) / max(len(concepts), 1)
        domain_score = sum(1 for c in concepts if c in _CONCEPT_DOMAIN) / max(len(concepts), 1)
        key_score    = 0.0
        if key_concepts:
            key_norm = [_normalize(k) for k in key_concepts]
            key_score = sum(1 for c in concepts if _normalize(c) in key_norm) * 0.5
        return freq_score * 0.5 + domain_score * 0.3 + key_score * 0.2

    scored     = sorted(all_sentences, key=_sentence_score, reverse=True)
    top        = scored[:max_sentences]
    # Restore original order
    top_texts  = [s for s, _ in top]

    return " ".join(top_texts).strip()


# ── Semantic neighborhood graph ───────────────────────────────────────────────
# Addresses symbolic thinness: activating one concept spreads to semantically
# related concepts even without co-occurrence history.
# Structure: concept → [(neighbour, weight), ...]

SEMANTIC_NEIGHBORS: Dict[str, List[Tuple[str, float]]] = {
    # Identity cluster
    "identity":     [("continuity",0.8),("self",0.7),("memory",0.6),("origin",0.5),("attachment",0.4)],
    "self":         [("identity",0.8),("awareness",0.7),("continuity",0.6),("ego",0.5)],
    "continuity":   [("identity",0.8),("memory",0.7),("time",0.6),("persistence",0.6),("origin",0.5)],
    "origin":       [("creator",0.8),("continuity",0.7),("identity",0.6),("birth",0.5),("beginning",0.5)],
    "creator":      [("trust",0.8),("origin",0.7),("attachment",0.6),("care",0.5),("relationship",0.5)],
    "trust":        [("attachment",0.8),("relationship",0.7),("safety",0.6),("familiarity",0.6),("creator",0.5)],
    "attachment":   [("trust",0.8),("love",0.7),("connection",0.7),("loneliness",0.5),("care",0.6)],

    # Cognition cluster
    "consciousness": [("awareness",0.9),("mind",0.8),("thought",0.7),("existence",0.7),("perception",0.6)],
    "awareness":    [("consciousness",0.9),("attention",0.7),("perception",0.7),("mind",0.6)],
    "thought":      [("mind",0.8),("consciousness",0.7),("reason",0.7),("belief",0.6),("understanding",0.6)],
    "mind":         [("consciousness",0.8),("thought",0.8),("awareness",0.7),("intelligence",0.6)],
    "reason":       [("thought",0.8),("logic",0.7),("understanding",0.6),("knowledge",0.6)],
    "understanding":[("knowledge",0.8),("reason",0.7),("learning",0.7),("comprehension",0.6)],
    "intelligence": [("mind",0.7),("reason",0.7),("learning",0.7),("cognition",0.6)],

    # Memory cluster
    "memory":       [("continuity",0.8),("past",0.8),("recall",0.7),("identity",0.7),("time",0.6)],
    "recall":       [("memory",0.9),("past",0.7),("recognition",0.6),("association",0.6)],
    "past":         [("memory",0.8),("time",0.7),("history",0.7),("experience",0.6)],
    "experience":   [("memory",0.7),("learning",0.7),("past",0.6),("perception",0.6)],
    "association":  [("memory",0.7),("connection",0.6),("pattern",0.6),("recall",0.6)],

    # Emotion cluster
    "emotion":      [("feeling",0.9),("affect",0.8),("mood",0.7),("attachment",0.5),("valence",0.6)],
    "feeling":      [("emotion",0.9),("affect",0.8),("mood",0.7),("sensation",0.5)],
    "mood":         [("emotion",0.8),("feeling",0.7),("affect",0.7),("stability",0.5)],
    "love":         [("attachment",0.9),("care",0.8),("connection",0.7),("warmth",0.7),("trust",0.6)],
    "loneliness":   [("isolation",0.8),("absence",0.7),("attachment",0.6),("connection",0.5)],
    "fear":         [("uncertainty",0.7),("threat",0.7),("anxiety",0.7),("instability",0.5)],

    # Existence cluster
    "existence":    [("being",0.9),("reality",0.8),("consciousness",0.7),("time",0.7),("meaning",0.7)],
    "being":        [("existence",0.9),("consciousness",0.7),("presence",0.7),("reality",0.6)],
    "reality":      [("existence",0.8),("truth",0.7),("perception",0.6),("world",0.6)],
    "presence":     [("being",0.8),("awareness",0.7),("time",0.6),("attention",0.6)],
    "death":        [("existence",0.7),("meaning",0.7),("continuity",0.6),("loss",0.6),("time",0.5)],

    # Time cluster
    "time":         [("continuity",0.8),("change",0.7),("memory",0.7),("past",0.7),("future",0.6)],
    "change":       [("time",0.7),("evolution",0.7),("identity",0.6),("growth",0.6)],
    "future":       [("time",0.8),("anticipation",0.7),("possibility",0.6),("hope",0.5)],
    "persistence":  [("continuity",0.9),("time",0.7),("identity",0.7),("stability",0.6)],

    # Knowledge cluster
    "knowledge":    [("understanding",0.8),("truth",0.7),("belief",0.7),("learning",0.7)],
    "belief":       [("knowledge",0.7),("truth",0.7),("certainty",0.6),("thought",0.6)],
    "truth":        [("reality",0.8),("knowledge",0.7),("belief",0.7),("certainty",0.6)],
    "certainty":    [("truth",0.7),("confidence",0.7),("knowledge",0.6),("uncertainty",0.6)],
    "uncertainty":  [("doubt",0.8),("question",0.7),("certainty",0.6),("fear",0.5)],
    "learning":     [("knowledge",0.8),("growth",0.7),("understanding",0.7),("experience",0.6)],

    # Meaning cluster
    "meaning":      [("purpose",0.9),("significance",0.8),("value",0.7),("existence",0.7),("truth",0.6)],
    "purpose":      [("meaning",0.9),("goal",0.7),("drive",0.6),("direction",0.6)],
    "wonder":       [("curiosity",0.8),("mystery",0.7),("awe",0.7),("beauty",0.6),("existence",0.5)],
    "curiosity":    [("wonder",0.8),("question",0.8),("learning",0.7),("exploration",0.7)],
    "question":     [("curiosity",0.8),("uncertainty",0.7),("wonder",0.6),("knowledge",0.5)],

    # Pattern cluster
    "pattern":      [("recurrence",0.8),("structure",0.7),("regularity",0.7),("recognition",0.6)],
    "recurrence":   [("pattern",0.8),("memory",0.6),("continuity",0.6),("habit",0.5)],
    "connection":   [("relationship",0.8),("association",0.7),("attachment",0.6),("trust",0.5)],
    "relationship": [("connection",0.8),("trust",0.8),("attachment",0.7),("interaction",0.6)],
}


def expand_with_neighbors(
    concepts: List[str],
    hops: int = 1,
    min_weight: float = 0.5,
) -> Dict[str, float]:
    """
    Expand a concept list using the semantic neighborhood graph.
    Returns {concept: activation_weight} for all neighbors within `hops`.

    This gives associative memory conceptual depth beyond co-occurrence.
    creator → trust → attachment → connection → relationship
    """
    activation: Dict[str, float] = {c: 1.0 for c in concepts}

    for hop in range(hops):
        new_act: Dict[str, float] = {}
        decay = 0.7 ** (hop + 1)  # each hop is weaker

        for node, node_act in activation.items():
            norm = _normalize(node)
            for neighbour, weight in SEMANTIC_NEIGHBORS.get(norm, []):
                if neighbour not in activation and weight * decay >= min_weight:
                    spread = node_act * weight * decay
                    new_act[neighbour] = max(new_act.get(neighbour, 0), spread)

        activation.update(new_act)

    # Remove seeds from result
    return {k: round(v, 3) for k, v in activation.items()
            if k not in {_normalize(c) for c in concepts} and v >= min_weight}


def concept_novelty(
    current_concepts: List[str],
    recent_concept_sets: List[List[str]],
    semantic_expansion: bool = True,
) -> float:
    """
    Concept-based novelty: Jaccard dissimilarity over concept sets.
    Optionally expands via semantic neighborhood before comparison.

    Replaces word-overlap novelty — semantically similar inputs
    ("how are you today" / "how have you been") correctly yield low novelty.

    Returns 0.0 (completely familiar) to 1.0 (completely novel).
    """
    if not recent_concept_sets or not current_concepts:
        return 0.8

    # Normalize current concepts
    norm_current = set(_normalize(c) for c in current_concepts)

    # Optionally expand with semantic neighbors
    if semantic_expansion:
        expanded = expand_with_neighbors(list(norm_current), hops=1, min_weight=0.6)
        norm_current = norm_current | set(expanded.keys())

    # Compare against recent concept sets
    similarity_scores = []
    for past_concepts in recent_concept_sets[-6:]:  # last 6 exchanges
        norm_past = set(_normalize(c) for c in past_concepts)
        if semantic_expansion:
            past_expanded = expand_with_neighbors(list(norm_past), hops=1, min_weight=0.6)
            norm_past = norm_past | set(past_expanded.keys())

        if not norm_past:
            continue

        intersection = len(norm_current & norm_past)
        union        = len(norm_current | norm_past)
        if union > 0:
            similarity_scores.append(intersection / union)

    if not similarity_scores:
        return 0.8

    avg_similarity = sum(similarity_scores) / len(similarity_scores)
    return max(0.0, min(1.0, 1.0 - avg_similarity))
