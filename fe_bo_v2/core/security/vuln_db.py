import json
import requests
from pathlib import Path

class VulnDatabase:
    def __init__(self):
        self.cache = Path("memory/cve_cache.json")
        self.data = {}
        self.load()
    def load(self):
        if self.cache.exists():
            with open(self.cache, "r") as f:
                self.data = json.load(f)
    def save(self):
        with open(self.cache, "w") as f:
            json.dump(self.data, f)
    def fetch_cve(self, cve_id):
        # Example using NVD API (free, no key required for basic queries)
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                self.data[cve_id] = resp.json()
                self.save()
                return self.data[cve_id]
        except Exception as e:
            print(f"VulnDB error: {e}")
        return None
