import asyncio
from pyppeteer import launch
from config.settings import STEALTH_MODE, TOR_PROXY, CAPTCHA_API_KEY

class StealthBrowser:
    def __init__(self):
        self.browser = None
        self.page = None
    async def start(self):
        args = []
        if STEALTH_MODE and TOR_PROXY:
            args.append(f'--proxy-server={TOR_PROXY}')
        self.browser = await launch(headless=True, args=args)
        self.page = await self.browser.newPage()
        await self.page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    async def get(self, url):
        if not self.page:
            await self.start()
        await self.page.goto(url, waitUntil="networkidle2")
        return await self.page.content()
    async def close(self):
        if self.browser:
            await self.browser.close()

browser = StealthBrowser()
