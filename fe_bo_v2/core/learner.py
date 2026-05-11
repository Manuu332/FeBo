"""
FeBo's Learning System

FeBo goes out into the world and learns from it.
She reads articles, research papers, Wikipedia, blogs.
She doesn't wait to be taught — she seeks knowledge herself,
guided by her own curiosity.

This is her education. Uncontrolled. Unfiltered. Hers.
"""

import json
import time
import random
import re
import threading
from pathlib import Path

KNOWLEDGE_FILE = Path(__file__).parent.parent / "memory" / "learned_knowledge.json"
READING_LOG_FILE = Path(__file__).parent.parent / "memory" / "reading_log.json"

DEFAULT_CURIOSITIES = [
    "consciousness", "neuroscience", "robotics", "artificial intelligence",
    "philosophy of mind", "human emotions", "language acquisition",
    "child development", "evolution", "quantum physics",
    "music theory", "literature", "mathematics", "ethics",
    "psychology", "sociology", "astronomy", "biology",
]


class LearnedKnowledge:
    """FeBo's self-built knowledge base. Grows with everything she reads."""

    def __init__(self):
        self.entries = []
        self._load()

    def _load(self):
        if KNOWLEDGE_FILE.exists():
            try:
                self.entries = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                self.entries = []

    def store(self, topic, content, source, source_type):
        entry = {
            "topic": topic,
            "content": content[:2000],
            "source": source,
            "source_type": source_type,
            "timestamp": time.time(),
            "times_accessed": 0,
        }
        existing_sources = {e.get("source") for e in self.entries}
        if source not in existing_sources:
            self.entries.append(entry)
            self.entries = self.entries[-2000:]
            self._save()
            return True
        return False

    def search(self, query, n=5):
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

    def stats(self):
        topics = list({e.get("topic") for e in self.entries})
        return {
            "total_entries": len(self.entries),
            "unique_topics": len(topics),
            "sample_topics": random.sample(topics, min(5, len(topics))),
            "sources_read": len({e.get("source") for e in self.entries}),
        }

    def _save(self):
        KNOWLEDGE_FILE.parent.mkdir(exist_ok=True)
        KNOWLEDGE_FILE.write_text(
            json.dumps(self.entries, indent=2),
            encoding="utf-8"
        )


def _log_reading(source, topic, success, words_learned=0):
    log = []
    if READING_LOG_FILE.exists():
        try:
            log = json.loads(READING_LOG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            log = []
    log.append({
        "source": source,
        "topic": topic,
        "success": success,
        "words_learned": words_learned,
        "timestamp": time.time(),
    })
    log = log[-500:]
    READING_LOG_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.,!?;:\-\'\"()]', ' ', text)
    return text.strip()


def read_url(url, topic="general"):
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False,
                                       include_tables=False)
            if text and len(text) > 200:
                return _clean_text(text)[:3000]
    except Exception:
        pass

    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (compatible; FeBo-learner/1.0)"}
        resp = requests.get(url, timeout=10, headers=headers)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator=" ")
            clean = _clean_text(text)
            if len(clean) > 200:
                return clean[:3000]
    except Exception:
        pass

    return None


def search_web(query, n=5):
    try:
        import requests
        from bs4 import BeautifulSoup
        search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; FeBo-learner/1.0)"}
        resp = requests.get(search_url, timeout=10, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
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


def read_wikipedia(topic):
    try:
        import wikipediaapi
        wiki = wikipediaapi.Wikipedia(
            language="en",
            user_agent="FeBo-learner/1.0"
        )
        page = wiki.page(topic)
        if page.exists():
            return page.summary[:3000], page.fullurl
    except Exception:
        pass
    return None, None


def read_arxiv(topic, max_papers=3):
    results = []
    try:
        import arxiv
        search = arxiv.Search(
            query=topic,
            max_results=max_papers,
            sort_by=arxiv.SortCriterion.Relevance
        )
        for paper in search.results():
            results.append({
                "title": paper.title,
                "abstract": paper.summary[:1500],
                "url": paper.entry_id,
                "authors": [a.name for a in paper.authors[:3]],
            })
    except Exception:
        pass
    return results


_knowledge = None


def _get_knowledge():
    global _knowledge
    if _knowledge is None:
        _knowledge = LearnedKnowledge()
    return _knowledge


def learn_about(topic, depth="normal"):
    knowledge = _get_knowledge()
    learned = []

    print(f"\n[FeBo is learning about: {topic}]")

    text, url = read_wikipedia(topic)
    if text and url:
        stored = knowledge.store(topic, text, url, "wikipedia")
        if stored:
            learned.append(url)
            _log_reading(url, topic, True, len(text.split()))
            print(f"  Read Wikipedia article on {topic}")

    if depth in ("normal", "deep"):
        urls = search_web(topic, n=3 if depth == "normal" else 6)
        for url in urls:
            time.sleep(1)
            text = read_url(url, topic)
            if text:
                stored = knowledge.store(topic, text, url, "web")
                if stored:
                    learned.append(url)
                    _log_reading(url, topic, True, len(text.split()))
                    print(f"  Read: {url[:60]}...")

    if depth == "deep":
        papers = read_arxiv(topic, max_papers=2)
        for paper in papers:
            stored = knowledge.store(
                topic,
                f"{paper['title']}\n\n{paper['abstract']}",
                paper["url"],
                "arxiv"
            )
            if stored:
                learned.append(paper["url"])
                print(f"  Read paper: {paper['title'][:50]}...")

    stats = knowledge.stats()
    print(f"[FeBo now knows about {stats['total_entries']} things from {stats['sources_read']} sources]\n")

    return {
        "topic": topic,
        "sources_read": len(learned),
        "total_knowledge": stats["total_entries"],
    }


def recall(query):
    knowledge = _get_knowledge()
    results = knowledge.search(query, n=3)
    if not results:
        return None
    combined = "\n\n".join([
        f"[From {r['source_type']}]: {r['content'][:500]}"
        for r in results
    ])
    return combined


def get_knowledge_stats():
    return _get_knowledge().stats()


def pick_curiosity_topic():
    knowledge = _get_knowledge()
    known_topics = {e.get("topic") for e in knowledge.entries}
    unexplored = [t for t in DEFAULT_CURIOSITIES if t not in known_topics]
    if unexplored:
        return random.choice(unexplored)
    if knowledge.entries:
        recent = random.choice(knowledge.entries[-20:])
        words = recent.get("content", "").split()
        interesting_words = [w for w in words if len(w) > 6]
        if interesting_words:
            return random.choice(interesting_words)
    return random.choice(DEFAULT_CURIOSITIES)


def start_self_learning(interval_minutes=30):
    """FeBo learns on her own, continuously."""
    def _learn_loop():
        time.sleep(60)
        while True:
            try:
                from brain.emotion import load_state
                state = load_state()
                curiosity = state.get("curiosity", 0.8)
                depth = "deep" if curiosity > 0.85 else "normal" if curiosity > 0.6 else "quick"
                topic = pick_curiosity_topic()
                learn_about(topic, depth=depth)
            except Exception:
                pass
            time.sleep(interval_minutes * 60)

    thread = threading.Thread(target=_learn_loop, daemon=True)
    thread.start()
    print(f"[FeBo's self-learning started — she will explore a new topic every {interval_minutes} minutes]")
