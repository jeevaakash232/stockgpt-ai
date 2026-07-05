import time
import logging
import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

class NSEDownloader:
    """
    Session-aware HTTP Downloader for official NSE endpoints.
    Automatically fetches home page first to capture valid session cookies.
    """
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        self.session.headers.update(self.headers)
        
        # Configure retry policies
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[401, 403, 500, 502, 503, 504],
            raise_on_status=False
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        
        self.cookies_warmed = False

    def warm_cookies(self):
        """Fetch NSE homepage to acquire cookies."""
        try:
            logger.info("Warming up NSE cookies...")
            # Fetch root url first
            resp = self.session.get("https://www.nseindia.com", timeout=15)
            if resp.ok:
                self.cookies_warmed = True
                logger.info("NSE session cookies warmed up successfully.")
                time.sleep(1)
            else:
                logger.warning("NSE cookies warmup returned status %d", resp.status_code)
        except Exception as e:
            logger.error("Failed to warm up NSE cookies: %s", e)

    def fetch_api(self, url: str, params: dict = None) -> dict:
        """Fetch json from official API after checking cookies."""
        if not self.cookies_warmed:
            self.warm_cookies()

        headers = {
            "Referer": "https://www.nseindia.com/option-chain",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 401:
                # Session expired, re-warm
                logger.info("Received 401 from NSE. Rewarming cookies...")
                self.cookies_warmed = False
                self.warm_cookies()
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("fetch_api failed for %s: %s", url, e)
            raise e

    def download_file(self, url: str, save_path: str) -> bool:
        """Download binary file (e.g. zip Bhavcopy)."""
        try:
            logger.info("Downloading file from %s...", url)
            resp = self.session.get(url, headers={"Referer": "https://www.nseindia.com/all-reports"}, timeout=20, stream=True)
            resp.raise_for_status()
            
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info("File successfully downloaded and saved to %s", save_path)
            return True
        except Exception as e:
            logger.error("download_file failed for %s: %s", url, e)
            return False

# Global instance for shared session reuse
downloader = NSEDownloader()
