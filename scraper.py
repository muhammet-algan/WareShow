#!/usr/bin/env python3
"""Basit fiyat cekme boti.

Kullanim:
    python incehesap_fiyat_bot.py "https://..."
    python incehesap_fiyat_bot.py urls.txt --json

Notlar:
- requests + BeautifulSoup kullanir.
- Incehesap dahil olmak uzere yaygin e-ticaret sayfalarinda calisacak sekilde
  genel seciciler ve metin tabanli fallback'ler icerir.
- Ciktida urun basligi, fiyat, para birimi ve URL doner.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

PRICE_REGEXES = [
    re.compile(r"(?P<price>\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?)\s*(?P<currency>TL|₺)", re.I),
    re.compile(r"(?P<currency>TL|₺)\s*(?P<price>\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?)", re.I),
]

JSON_PRICE_REGEX = re.compile(
    r'"price"\s*:\s*"?(?P<price>\d+(?:[.,]\d+)?)"?.{0,80}?"priceCurrency"\s*:\s*"?(?P<currency>[A-Z]{3}|TL|TRY|₺)"?',
    re.I | re.S,
)


@dataclass
class ProductPrice:
    title: str | None
    price_text: str | None
    price_value: float | None
    currency: str | None
    url: str
    ok: bool
    error: str | None = None


def normalize_price(price_text: str | None) -> float | None:
    if not price_text:
        return None
    text = price_text.strip()
    text = text.replace("TL", "").replace("₺", "").strip()

    # Turkce format: 1.849,90 -> 1849.90
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        # 1.849 -> 1849 ; 1849,90 -> 1849.90
        if text.count(".") >= 1 and "," not in text:
            parts = text.split(".")
            if all(p.isdigit() for p in parts) and all(len(p) == 3 for p in parts[1:]):
                text = "".join(parts)
        text = text.replace(",", ".")
        text = text.replace(" ", "")

    try:
        return float(text)
    except ValueError:
        return None


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip() or None


def fetch_html(url: str, timeout: int = 25) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_title(soup: BeautifulSoup) -> str | None:
    selectors = [
        "meta[property='og:title']",
        "meta[name='twitter:title']",
        "h1",
        "title",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        title = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
        title = clean_text(title)
        if title:
            return title.replace(" - incehesap.com", "").strip()
    return None


def extract_price_from_meta_or_schema(soup: BeautifulSoup, html: str) -> tuple[str | None, str | None]:
    meta_candidates = [
        "meta[itemprop='price']",
        "[itemprop='price']",
        "meta[property='product:price:amount']",
        "meta[property='og:price:amount']",
    ]
    for selector in meta_candidates:
        node = soup.select_one(selector)
        if not node:
            continue
        raw = node.get("content") or node.get_text(" ", strip=True)
        raw = clean_text(raw)
        if raw:
            currency = (
                soup.select_one("meta[itemprop='priceCurrency']")
                or soup.select_one("meta[property='product:price:currency']")
                or soup.select_one("meta[property='og:price:currency']")
            )
            currency_text = None
            if currency:
                currency_text = currency.get("content") or currency.get_text(" ", strip=True)
            currency_text = clean_text(currency_text) or "TRY"
            return raw, currency_text

    match = JSON_PRICE_REGEX.search(html)
    if match:
        return match.group("price"), match.group("currency")

    for script in soup.select("script"):
        text = script.string or script.get_text(" ", strip=True)
        if not text:
            continue
        match = JSON_PRICE_REGEX.search(text)
        if match:
            return match.group("price"), match.group("currency")

    return None, None


def extract_price_from_dom(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    selectors = [
        ".price",
        ".product-price",
        ".sale-price",
        "[class*='price']",
        "[id*='price']",
        "[data-price]",
    ]
    for selector in selectors:
        for node in soup.select(selector):
            text = clean_text(node.get("data-price") or node.get_text(" ", strip=True))
            if not text:
                continue
            for rx in PRICE_REGEXES:
                match = rx.search(text)
                if match:
                    return match.group("price"), match.group("currency")
    return None, None


def extract_price_from_text(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    text = soup.get_text("\n", strip=True)
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    # Ust kisimda bulunan fiyat daha isabetli olsun diye ilk 140 satiri tara.
    for line in lines[:140]:
        for rx in PRICE_REGEXES:
            match = rx.search(line)
            if match:
                return match.group("price"), match.group("currency")
    return None, None


def scrape_product(url: str) -> ProductPrice:
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        title = extract_title(soup)

        price_text, currency = extract_price_from_meta_or_schema(soup, html)
        if not price_text:
            price_text, currency = extract_price_from_dom(soup)
        if not price_text:
            price_text, currency = extract_price_from_text(soup)

        price_value = normalize_price(price_text)
        if not price_text:
            return ProductPrice(
                title=title,
                price_text=None,
                price_value=None,
                currency=None,
                url=url,
                ok=False,
                error="Fiyat bulunamadi. Sayfa yapisi degismis olabilir.",
            )

        return ProductPrice(
            title=title,
            price_text=price_text,
            price_value=price_value,
            currency=currency,
            url=url,
            ok=True,
        )
    except requests.HTTPError as exc:
        return ProductPrice(None, None, None, None, url, False, f"HTTP hatasi: {exc}")
    except requests.RequestException as exc:
        return ProductPrice(None, None, None, None, url, False, f"Ag hatasi: {exc}")
    except Exception as exc:  # noqa: BLE001
        return ProductPrice(None, None, None, None, url, False, f"Beklenmeyen hata: {exc}")


def iter_urls(target: str) -> Iterable[str]:
    if target.startswith("http://") or target.startswith("https://"):
        yield target
        return

    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                yield line


def main() -> int:
    parser = argparse.ArgumentParser(description="Urun fiyat cekme boti")
    parser.add_argument("target", help="Tek URL veya URL listesi iceren txt dosyasi")
    parser.add_argument("--json", action="store_true", help="JSON cikti ver")
    args = parser.parse_args()

    results = [asdict(scrape_product(url)) for url in iter_urls(args.target)]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for item in results:
        print("=" * 60)
        print(f"URL      : {item['url']}")
        print(f"Baslik   : {item['title']}")
        print(f"Fiyat    : {item['price_text']}")
        print(f"Para Bir.: {item['currency']}")
        print(f"Deger    : {item['price_value']}")
        print(f"Durum    : {'OK' if item['ok'] else 'HATA'}")
        if item["error"]:
            print(f"Hata     : {item['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
