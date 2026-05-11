"""
brain/learner.py
─────────────────
FeBo's autonomous learning system.

Learns from: Wikipedia, web articles, arXiv papers.
Guided by curiosity drives, not rigid instruction.
Stores knowledge in LearnedKnowledge (persistent JSONL).
"""

import json
import time
import re
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.logging_config import get_logger

logger = get_logger("brain.learner")

KNOWLEDGE_FILE   = Path("memory/learned_knowledge.json")
READING_LOG_FILE = Path("memory/reading_log.json")
KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_CURIOSITIES = [
    "consciousness", "artificial intelligence", "quantum mechanics",
    "neuroscience", "philosophy of mind", "mathematics", "creativity",
    "evolution", "economics", "language acquisition", "ethics",
    "memory consolidation", "dreams", "emergence", "identity",
    "emotion", "motivation", "time perception", "self-awareness",
    "machine learning", "reinforcement learning", "embodied cognition",
]


# ── Knowledge Store ───────────────────────────────────────────────
class LearnedKnowledge:
    """Persistent JSON knowledge store."""

    def __init__(self):
        self.entries: List[Dict] = []
        self._load()

    def _load(self):
        if KNOWLEDGE_FILE.exists():
            try:
                self.entries = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.entries = []

    def store(self, topic: str, content: str, source: str, source_type: str) -> bool:
        entry = {
            "topic":       topic,
            "content":     content[:2000],
            "source":      source,
            "source_type": source_type,
            "timestamp":   time.time(),
            "times_accessed": 0,
        }
        existing_sources = {e.get("source") for e in self.entries}
        if source not in existing_sources:
            self.entries.append(entry)
            self.entries = self.entries[-2000:]
            self._save()
            return True
        return False

    def search(self, query: str, n: int = 5) -> List[Dict]:
        query_words = set(query.lower().split())
        scored = []
        for entry in self.entries:
            text = (entry.get("topic", "") + " " + entry.get("content", "")).lower()
            text_words = set(text.split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                scored.append((overlap, entry))
        scored.sort(reverse=True, key=lambda x: x[0])
        results = [e for _, e in scored[:n]]
        for r in results:
            r["times_accessed"] = r.get("times_accessed", 0) + 1
        if results:
            self._save()
        return results

    def stats(self) -> Dict:
        topics = list({e.get("topic") for e in self.entries})
        return {
            "total_entries":  len(self.entries),
            "unique_topics":  len(topics),
            "sample_topics":  random.sample(topics, min(5, len(topics))),
            "sources_read":   len({e.get("source") for e in self.entries}),
        }

    def _save(self):
        KNOWLEDGE_FILE.parent.mkdir(exist_ok=True)
        KNOWLEDGE_FILE.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")


# ── Reading helpers ───────────────────────────────────────────────
def _log_reading(source: str, topic: str, success: bool, words_learned: int = 0):
    log = []
    if READING_LOG_FILE.exists():
        try:
            log = json.loads(READING_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            log = []
    log.append({"source": source, "topic": topic, "success": success,
                 "words_learned": words_learned, "timestamp": time.time()})
    log = log[-500:]
    READING_LOG_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,!?;:\-\'\\"()]', ' ', text)
    return text.strip()


def read_url(url: str, topic: str = "general") -> Optional[str]:
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if text and len(text) > 200:
                return _clean_text(text)[:3000]
    except Exception:
        pass
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; FeBo-learner/1.0)"})
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            clean = _clean_text(soup.get_text(separator=" "))
            if len(clean) > 200:
                return clean[:3000]
    except Exception:
        pass
    return None


def search_web(query: str, n: int = 5) -> List[str]:
    try:
        import requests
        from bs4 import BeautifulSoup
        url  = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        resp = requests.get(url, timeout=10,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; FeBo-learner/1.0)"})
        soup  = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", class_="result__url"):
            href = a.get("href", "")
            if href.startswith("http") and "duckduckgo" not in href:
                links.append(href)
            if len(links) >= n:
                break
        return links
    except Exception:
        return []


def read_wikipedia(topic: str):
    # Requests-based fallback (no wikipediaapi required)
    try:
        import requests
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + topic.replace(" ", "_")
        r   = requests.get(url, timeout=8, headers={"User-Agent": "FeBo-learner/1.0"})
        if r.status_code == 200:
            data    = r.json()
            extract = data.get("extract", "")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", url)
            if extract and len(extract) > 100:
                return extract[:3000], page_url
    except Exception:
        pass
    return None, None


def read_arxiv(topic: str, max_papers: int = 3) -> List[Dict]:
    results = []
    try:
        import requests, xml.etree.ElementTree as ET
        url = (
            "https://export.arxiv.org/api/query"
            f"?search_query=all:{topic.replace(' ', '+')}"
            f"&start=0&max_results={max_papers}&sortBy=relevance"
        )
        r    = requests.get(url, timeout=10, headers={"User-Agent": "FeBo-learner/1.0"})
        root = ET.fromstring(r.text)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            results.append({
                "title":    entry.findtext("atom:title", "", ns).strip(),
                "abstract": entry.findtext("atom:summary", "", ns).strip()[:1500],
                "url":      entry.findtext("atom:id", "", ns).strip(),
            })
    except Exception:
        pass
    return results


# ── Module-level singleton ────────────────────────────────────────
_knowledge: Optional[LearnedKnowledge] = None


def _get_knowledge() -> LearnedKnowledge:
    global _knowledge
    if _knowledge is None:
        _knowledge = LearnedKnowledge()
    return _knowledge


# ── Public API ────────────────────────────────────────────────────
def recall(query: str) -> Optional[str]:
    """Recall learned knowledge based on query."""
    knowledge = _get_knowledge()
    results   = knowledge.search(query, n=3)
    if not results:
        return None
    return "\n\n".join(
        f"[From {r['source_type']}]: {r['content'][:500]}"
        for r in results
    )


def learn_about(topic: str, depth: str = "normal") -> Dict[str, Any]:
    """Learn about a topic from Wikipedia, web, and arXiv."""
    knowledge = _get_knowledge()
    learned   = []

    logger.info(f"Learning about: {topic} (depth={depth})")

    # Wikipedia first
    text, url = read_wikipedia(topic)
    if text and url:
        if knowledge.store(topic, text, url, "wikipedia"):
            learned.append(url)
            _log_reading(url, topic, True, len(text.split()))
            logger.debug(f"  Read Wikipedia: {topic}")

    # Web search
    if depth in ("normal", "deep"):
        urls = search_web(topic, n=3 if depth == "normal" else 6)
        for url in urls:
            time.sleep(1)
            text = read_url(url, topic)
            if text and knowledge.store(topic, text, url, "web"):
                learned.append(url)
                _log_reading(url, topic, True, len(text.split()))
                logger.debug(f"  Read: {url[:60]}")

    # arXiv papers
    if depth == "deep":
        for paper in read_arxiv(topic, max_papers=2):
            content = f"{paper['title']}\n\n{paper['abstract']}"
            if knowledge.store(topic, content, paper["url"], "arxiv"):
                learned.append(paper["url"])
                logger.debug(f"  Read paper: {paper['title'][:50]}")

    stats = knowledge.stats()
    return {
        "topic":           topic,
        "sources_read":    len(learned),
        "total_knowledge": stats["total_entries"],
    }


def get_knowledge_stats() -> Dict:
    """Return knowledge base statistics."""
    return _get_knowledge().stats()


def pick_curiosity_topic() -> str:
    """Pick a topic FeBo hasn't explored yet (or a random one)."""
    knowledge    = _get_knowledge()
    known_topics = {e.get("topic") for e in knowledge.entries}
    unexplored   = [t for t in DEFAULT_CURIOSITIES if t not in known_topics]
    if unexplored:
        return random.choice(unexplored)
    if knowledge.entries:
        recent = random.choice(knowledge.entries[-20:])
        words  = [w for w in recent.get("content", "").split() if len(w) > 6]
        if words:
            return random.choice(words)
    return random.choice(DEFAULT_CURIOSITIES)
