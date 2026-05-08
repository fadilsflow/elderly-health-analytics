"""
HTTP Client dengan retry, User-Agent, dan timeout.

Menggunakan requests.Session agar koneksi TCP dapat di-reuse
untuk multiple request ke host yang sama.  Cocok untuk
Google Colab maupun eksekusi lokal.
"""

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HttpClient:
    """
    HTTP Client wrapper dengan retry logic dan timeout default.

    Penggunaan:
        client = HttpClient()
        response = client.get("https://api.example.com/data")
    """

    # Default timeout agar tidak hang di Colab / jaringan lambat
    DEFAULT_TIMEOUT: int = 30
    DEFAULT_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; BigDataElderlyHealth/1.0; "
        "Academic research project; +https://github.com/example)"
    )

    def __init__(self, timeout: int = None, user_agent: str = None):
        """
        Inisialisasi HttpClient dengan session persistent.

        Args:
            timeout: Timeout request dalam detik (default 30)
            user_agent: User-Agent header string
        """
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": user_agent or self.DEFAULT_USER_AGENT,
            "Accept": "application/json",
        })

        # Retry strategy: max 2 kali retry pada kondisi network error
        retry_strategy = Retry(
            total=2,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Melakukan HTTP GET request dengan timeout default.

        Args:
            url: Target URL
            **kwargs: Parameter tambahan untuk requests (params, headers, dll)

        Returns:
            requests.Response object

        Raises:
            requests.RequestException: Jika request gagal setelah retry
        """
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response

    def close(self):
        """Tutup session untuk membersihkan resource."""
        self.session.close()
