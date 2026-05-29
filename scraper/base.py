"""スクレイパー基底クラス・共通ユーティリティ"""
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from typing import Optional

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def fetch(url: str, wait: float = 1.5) -> Optional[BeautifulSoup]:
    """URLを取得してBeautifulSoupを返す。失敗時はNone"""
    time.sleep(wait + random.uniform(0, 1))  # サーバー負荷軽減
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logger.error(f"Fetch failed: {url} -> {e}")
        return None


def safe_text(element) -> str:
    """要素からテキストを安全に取得"""
    if element is None:
        return ""
    return element.get_text(strip=True)


def safe_float(text: str) -> Optional[float]:
    """文字列をfloatに変換。失敗時はNone"""
    try:
        return float(text.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def safe_int(text: str) -> Optional[int]:
    """文字列をintに変換。失敗時はNone"""
    try:
        return int(text.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None
