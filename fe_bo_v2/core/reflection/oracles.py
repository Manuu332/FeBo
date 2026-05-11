"""
All external APIs FeBo can use for reflection and study.
Each oracle class has two static methods:
- is_available() -> bool
- query(topic, limit=1) -> str or dict (any serialisable result)
"""

import os
import json
import base64
import requests
from typing import Optional, Union

# ----------------------------------------------------------------------
# Helper to load API keys from environment
def _get_key(name: str) -> Optional[str]:
    return os.getenv(name)

# ----------------------------------------------------------------------
# 1. OpenAI
class OpenAIOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("OPENAI_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[str]:
        import openai
        openai.api_key = _get_key("OPENAI_API_KEY")
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for an AI named FeBo."},
                    {"role": "user", "content": topic}
                ],
                max_tokens=200,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[OpenAI error: {e}]"

# ----------------------------------------------------------------------
# 2. GitHub (search repos)
class GitHubOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("GITHUB_TOKEN"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Union[list, str]:
        token = _get_key("GITHUB_TOKEN")
        headers = {"Authorization": f"token {token}"}
        url = f"https://api.github.com/search/repositories?q={topic}+language:python&sort=stars&per_page={limit}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                results = []
                for item in items[:limit]:
                    results.append({
                        "name": item["full_name"],
                        "url": item["html_url"],
                        "stars": item["stargazers_count"],
                        "description": item.get("description", "")
                    })
                return results
            else:
                return f"[GitHub error: {resp.status_code}]"
        except Exception as e:
            return f"[GitHub error: {e}]"

# ----------------------------------------------------------------------
# 3. Wikipedia (no key required)
import wikipedia
class WikipediaOracle:
    @staticmethod
    def is_available() -> bool:
        return True
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[str]:
        try:
            summary = wikipedia.summary(topic, sentences=3)
            return summary
        except Exception:
            return None

# ----------------------------------------------------------------------
# 4. Brave Search API
class BraveSearchOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("BRAVE_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Union[list, str]:
        key = _get_key("BRAVE_API_KEY")
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": key}
        params = {"q": topic, "count": limit}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for web in data.get("web", {}).get("results", [])[:limit]:
                    results.append({"title": web.get("title"), "url": web.get("url"), "description": web.get("description")})
                return results
            else:
                return f"[Brave error: {resp.status_code}]"
        except Exception as e:
            return f"[Brave error: {e}]"

# ----------------------------------------------------------------------
# 5. NewsCatcher API
class NewsCatcherOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("NEWSCATCHER_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Union[list, str]:
        key = _get_key("NEWSCATCHER_API_KEY")
        url = "https://api.newscatcherapi.com/v2/search"
        headers = {"x-api-key": key}
        params = {"q": topic, "page_size": limit}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                results = []
                for art in articles[:limit]:
                    results.append({"title": art.get("title"), "link": art.get("link"), "summary": art.get("excerpt")})
                return results
            else:
                return f"[NewsCatcher error: {resp.status_code}]"
        except Exception as e:
            return f"[NewsCatcher error: {e}]"

# ----------------------------------------------------------------------
# 6. Alpha Vantage (stocks)
class AlphaVantageOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("ALPHA_VANTAGE_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[dict]:
        key = _get_key("ALPHA_VANTAGE_API_KEY")
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={topic}&apikey={key}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return data.get("Global Quote")
        except Exception:
            return None

# ----------------------------------------------------------------------
# 7. Finnhub
class FinnhubOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("FINNHUB_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[dict]:
        key = _get_key("FINNHUB_API_KEY")
        url = f"https://finnhub.io/api/v1/quote?symbol={topic}&token={key}"
        try:
            resp = requests.get(url, timeout=10)
            return resp.json()
        except Exception:
            return None

# ----------------------------------------------------------------------
# 8. Twelve Data
class TwelveDataOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("TWELVE_DATA_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[dict]:
        key = _get_key("TWELVE_DATA_API_KEY")
        url = f"https://api.twelvedata.com/quote?symbol={topic}&apikey={key}"
        try:
            resp = requests.get(url, timeout=10)
            return resp.json()
        except Exception:
            return None

# ----------------------------------------------------------------------
# 9. FRED (economic data)
class FREDOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("FRED_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[list]:
        # topic is series ID like "GDP"
        key = _get_key("FRED_API_KEY")
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={topic}&api_key={key}&file_type=json"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            return data.get("observations", [])[:limit]
        except Exception:
            return None

# ----------------------------------------------------------------------
# 10. CoinGecko (crypto)
class CoinGeckoOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("COINGECKO_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[dict]:
        key = _get_key("COINGECKO_API_KEY")
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={topic}&vs_currencies=usd&x_cg_demo_api_key={key}"
        try:
            resp = requests.get(url, timeout=10)
            return resp.json()
        except Exception:
            return None

# ----------------------------------------------------------------------
# 11. Hugging Face Inference API
class HuggingFaceOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("HUGGINGFACE_TOKEN"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[str]:
        token = _get_key("HUGGINGFACE_TOKEN")
        # Use a simple text generation model (e.g., gpt2)
        headers = {"Authorization": f"Bearer {token}"}
        url = "https://api-inference.huggingface.co/models/gpt2"
        payload = {"inputs": topic, "parameters": {"max_length": 100}}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                return resp.json()[0].get("generated_text")
            else:
                return f"[HuggingFace error: {resp.status_code}]"
        except Exception as e:
            return f"[HuggingFace error: {e}]"

# ----------------------------------------------------------------------
# 12. OpenRouter (unified LLM)
class OpenRouterOracle:
    @staticmethod
    def is_available() -> bool:
        return bool(_get_key("OPENROUTER_API_KEY"))
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[str]:
        key = _get_key("OPENROUTER_API_KEY")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": topic}]
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            else:
                return f"[OpenRouter error: {resp.status_code}]"
        except Exception as e:
            return f"[OpenRouter error: {e}]"

# ----------------------------------------------------------------------
# 13. Semantic Scholar
class SemanticScholarOracle:
    @staticmethod
    def is_available() -> bool:
        return True  # No key required for basic queries
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[list]:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={topic}&limit={limit}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                papers = resp.json().get("data", [])
                results = []
                for p in papers[:limit]:
                    results.append({
                        "title": p.get("title"),
                        "abstract": p.get("abstract"),
                        "year": p.get("year"),
                        "url": f"https://www.semanticscholar.org/paper/{p.get('paperId')}"
                    })
                return results
            else:
                return None
        except Exception:
            return None

# ----------------------------------------------------------------------
# 14. arXiv API
class ArxivOracle:
    @staticmethod
    def is_available() -> bool:
        return True
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[list]:
        import feedparser
        query = f"all:{topic}"
        url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={limit}"
        try:
            feed = feedparser.parse(url)
            entries = []
            for entry in feed.entries[:limit]:
                entries.append({
                    "title": entry.title,
                    "summary": entry.summary[:300],
                    "link": entry.link
                })
            return entries
        except Exception:
            return None

# ----------------------------------------------------------------------
# 15. yFinance (no key, but we'll wrap as an oracle)
class YFinanceOracle:
    @staticmethod
    def is_available() -> bool:
        try:
            import yfinance
            return True
        except ImportError:
            return False
    @staticmethod
    def query(topic: str, limit: int = 1) -> Optional[dict]:
        import yfinance as yf
        try:
            ticker = yf.Ticker(topic)
            info = ticker.info
            return {"name": info.get("longName"), "current_price": info.get("currentPrice"), "market_cap": info.get("marketCap")}
        except Exception:
            return None
