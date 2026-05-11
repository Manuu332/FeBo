"""
Registry of all oracles and parallel query execution.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from .oracles import (
    OpenAIOracle,
    GitHubOracle,
    WikipediaOracle,
    BraveSearchOracle,
    NewsCatcherOracle,
    AlphaVantageOracle,
    FinnhubOracle,
    TwelveDataOracle,
    FREDOracle,
    CoinGeckoOracle,
    HuggingFaceOracle,
    OpenRouterOracle,
    SemanticScholarOracle,
    ArxivOracle,
    YFinanceOracle,
)

# All available oracle classes
ALL_ORACLE_CLASSES = [
    OpenAIOracle,
    GitHubOracle,
    WikipediaOracle,
    BraveSearchOracle,
    NewsCatcherOracle,
    AlphaVantageOracle,
    FinnhubOracle,
    TwelveDataOracle,
    FREDOracle,
    CoinGeckoOracle,
    HuggingFaceOracle,
    OpenRouterOracle,
    SemanticScholarOracle,
    ArxivOracle,
    YFinanceOracle,
]

def get_available_oracles():
    """Return list of oracle names that are available (API key present or no key needed)."""
    available = []
    for cls in ALL_ORACLE_CLASSES:
        if cls.is_available():
            available.append(cls.__name__.replace("Oracle", "").lower())
    return available

def query_all_oracles(topic, limit_per_oracle=1, timeout=15):
    """
    Query all available oracles in parallel.
    Returns a list of dicts: {"source": name, "content": result}
    """
    results = []
    with ThreadPoolExecutor(max_workers=len(ALL_ORACLE_CLASSES)) as executor:
        future_to_oracle = {}
        for cls in ALL_ORACLE_CLASSES:
            if cls.is_available():
                future = executor.submit(cls.query, topic, limit_per_oracle)
                future_to_oracle[future] = cls.__name__.replace("Oracle", "").lower()
        for future in as_completed(future_to_oracle, timeout=timeout):
            source = future_to_oracle[future]
            try:
                result = future.result()
                if result:
                    results.append({"source": source, "content": result})
            except Exception as e:
                results.append({"source": source, "error": str(e)})
    return results
