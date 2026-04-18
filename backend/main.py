#!/usr/bin/env python3
from __future__ import annotations

import re
import json
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Fiyat Cekme API", version="2.0.0")

# CORS — frontend'in erişebilmesi için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

PRICE_REGEXES = [
    re.compile(r"(?P<price>\d{1,3}(?:[. ]\d{3})*(?:,\d{1,2})?)[\\s\\u00a0]*(?P<currency>TL|₺)", re.I),
    re.compile(r"(?P<currency>TL|₺)[\\s\\u00a0]*(?P<price>\d{1,3}(?:[. ]\d{3})*(?:,\d{1,2})?)", re.I),
]

JSON_PRICE_REGEX = re.compile(
    r'"price"\s*:\s*"?(?P<price>\d+(?:[.,]\d+)?)"?.{0,80}?"priceCurrency"\s*:\s*"?(?P<currency>[A-Z]{3}|TL|TRY|₺)"?',
    re.I | re.S,
)


class PriceResponse(BaseModel):
    ok: bool
    url: str
    title: Optional[str] = None
    price_text: Optional[str] = None
    price_value: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    brand: Optional[str] = None
    error: Optional[str] = None


def clean_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip() or None


def normalize_currency(currency: Optional[str]) -> Optional[str]:
    if not currency:
        return None
    c = currency.strip().upper()
    if c in {"₺", "TL", "TRY"}:
        return "TRY"
    return c


def normalize_price(price_text: Optional[str]) -> Optional[float]:
    if not price_text:
        return None

    text = price_text.strip()
    text = text.replace("TL", "").replace("₺", "").strip()
    text = text.replace("\u00a0", "").replace(" ", "")

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        if text.count(".") >= 1 and "," not in text:
            parts = text.split(".")
            if all(p.isdigit() for p in parts) and all(len(p) == 3 for p in parts[1:]):
                text = "".join(parts)
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


# ─────────────────────────────────────────────
#  Trendyol için özel çözümleyici
# ─────────────────────────────────────────────
TRENDYOL_ID_RE = re.compile(r"-p-(\d+)(?:[/?#]|$)")


def extract_trendyol_product_id(url: str) -> Optional[str]:
    match = TRENDYOL_ID_RE.search(url)
    return match.group(1) if match else None


def extract_json_obj_from_script(txt: str, marker: str) -> Optional[str]:
    """
    Verilen marker'ı bulup arkasından gelen ilk JSON objesini
    balanced-brace tekniğiyle döndürür.
    """
    idx = txt.find(marker)
    if idx < 0:
        return None
    start = txt.find("{", idx)
    if start < 0:
        return None
    depth = 0
    for j, ch in enumerate(txt[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return txt[start: j + 1]
    return None


def get_price_from_envoy_props(product: dict) -> Tuple[Optional[float], Optional[str]]:
    """
    __envoy_product-detail__PROPS içindeki product dict'inden fiyat çıkar.
    """
    variants = product.get("variants", [])
    for var in variants:
        if not isinstance(var, dict):
            continue
        price_obj = var.get("price", {})
        if isinstance(price_obj, dict):
            val = price_obj.get("value") or price_obj.get("discountedPrice", {}).get("value")
            txt = price_obj.get("text") or price_obj.get("discountedPrice", {}).get("text")
            if val and val > 0:
                return float(val), txt

    merchant_listing = product.get("merchantListing", {})
    if isinstance(merchant_listing, dict):
        for key in ["otherMerchants", "merchants"]:
            for merchant in merchant_listing.get(key, []):
                for var in merchant.get("variants", []):
                    price_obj = var.get("price", {})
                    if not isinstance(price_obj, dict):
                        continue
                    for sub in ["discountedPrice", "sellingPrice", "originalPrice"]:
                        sub_obj = price_obj.get(sub, {})
                        if isinstance(sub_obj, dict):
                            val = sub_obj.get("value")
                            txt = sub_obj.get("text")
                            if val and val > 0:
                                return float(val), txt

    return deep_find_price_envoy(product), None


def deep_find_price_envoy(obj, max_depth: int = 10) -> Optional[float]:
    if max_depth <= 0 or not obj:
        return None
    if isinstance(obj, dict):
        for key in ["discountedPrice", "sellingPrice", "salePrice"]:
            val = obj.get(key)
            if isinstance(val, dict):
                v = val.get("value")
                if isinstance(v, (int, float)) and v > 0:
                    return float(v)
            elif isinstance(val, (int, float)) and val > 0:
                return float(val)
        for v in obj.values():
            result = deep_find_price_envoy(v, max_depth - 1)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = deep_find_price_envoy(item, max_depth - 1)
            if result is not None:
                return result
    return None


def scrape_trendyol(url: str) -> Optional[PriceResponse]:
    """Trendyol ürün sayfasından fiyat çeker."""
    product_id = extract_trendyol_product_id(url)
    if not product_id:
        return None
    return scrape_trendyol_from_html(url, product_id)


def scrape_trendyol_from_html(url: str, product_id: str) -> Optional[PriceResponse]:
    """
    Trendyol sayfasını HTML olarak indirir.
    Sırasıyla şu kaynakları dener:
      1) __PRODUCT_DETAIL_APP_INITIAL_STATE__  (yeni yapı — 2024+)
         product.price.discountedPrice.value
      2) window["__envoy_product-detail__PROPS"] (eski yapı)
      3) __NEXT_DATA__
      4) DOM .prc-dsc / .prc-org CSS class fallback
      5) Genel JSON regex son çare
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code not in (200, 301, 302):
            return None
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # ── 1) YENİ: __PRODUCT_DETAIL_APP_INITIAL_STATE__ ─────────────────
        if "__PRODUCT_DETAIL_APP_INITIAL_STATE__" in html:
            raw_json = extract_json_obj_from_script(html, "__PRODUCT_DETAIL_APP_INITIAL_STATE__")
            if raw_json:
                try:
                    data = json.loads(raw_json)
                    product = (
                        data.get("product")
                        or data.get("productDetail", {}).get("product")
                        or {}
                    )
                    if product:
                        pv: Optional[float] = None
                        pt: Optional[str] = None

                        # product.price → {discountedPrice: {value, text}, sellingPrice: ...}
                        price_obj = product.get("price", {})
                        if isinstance(price_obj, dict):
                            for key in ("discountedPrice", "sellingPrice", "originalPrice"):
                                sub = price_obj.get(key, {})
                                if isinstance(sub, dict):
                                    val = sub.get("value")
                                    if val and float(val) > 0:
                                        pv = float(val)
                                        pt = sub.get("text") or sub.get("formattedPrice")
                                        break
                                elif isinstance(sub, (int, float)) and sub > 0:
                                    pv = float(sub)
                                    break

                        # Eski şema: priceInfo.discountedPrice
                        if pv is None:
                            for container_key in ("priceInfo", "price"):
                                container = product.get(container_key, {})
                                if isinstance(container, dict):
                                    for sub_key in ("discountedPrice", "sellingPrice", "price"):
                                        val = container.get(sub_key)
                                        if isinstance(val, (int, float)) and val > 0:
                                            pv = float(val)
                                            break
                                        if isinstance(val, dict):
                                            v2 = val.get("value")
                                            if isinstance(v2, (int, float)) and v2 > 0:
                                                pv = float(v2)
                                                pt = val.get("text")
                                                break
                                if pv:
                                    break

                        if pv and pv > 0:
                            if pt:
                                price_text_final = pt.replace(" TL", "").strip()
                            else:
                                price_text_final = (
                                    f"{pv:,.2f}"
                                    .replace(",", "X").replace(".", ",").replace("X", ".")
                                )

                            title = clean_text(product.get("name") or product.get("title"))
                            brand_raw = product.get("brand")
                            brand = None
                            if isinstance(brand_raw, dict):
                                brand = clean_text(brand_raw.get("name"))
                            elif brand_raw:
                                brand = clean_text(str(brand_raw))

                            images = product.get("images", [])
                            image_url = None
                            if images:
                                img = images[0] if isinstance(images[0], str) else ""
                                if img and not img.startswith("http"):
                                    img = "https://cdn.dsmcdn.com" + img
                                image_url = img or None

                            return PriceResponse(
                                ok=True,
                                url=url,
                                title=title,
                                price_text=price_text_final,
                                price_value=pv,
                                currency="TRY",
                                image_url=image_url,
                                brand=brand,
                            )
                except (ValueError, json.JSONDecodeError, KeyError, TypeError):
                    pass

        # ── 2) ESKİ: window["__envoy_product-detail__PROPS"] ──────────────
        for script in soup.find_all("script"):
            txt = script.string or ""
            if "__envoy_product-detail__PROPS" not in txt:
                continue
            raw_json = extract_json_obj_from_script(txt, "__envoy_product-detail__PROPS")
            if not raw_json:
                continue
            try:
                data = json.loads(raw_json)
            except (ValueError, json.JSONDecodeError):
                continue
            product = data.get("product", {})
            if not product:
                continue
            price_value, price_text_raw = get_price_from_envoy_props(product)
            if price_value is None or price_value <= 0:
                continue
            if price_text_raw:
                pt = price_text_raw.replace(" TL", "").strip()
            else:
                pt = (
                    f"{price_value:,.2f}"
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                )
            title = clean_text(product.get("name") or product.get("title"))
            brand_raw = product.get("brand")
            brand = (
                clean_text(brand_raw.get("name")) if isinstance(brand_raw, dict)
                else clean_text(str(brand_raw) if brand_raw else None)
            )
            images = product.get("images", [])
            image_url = None
            if images:
                img = images[0] if isinstance(images[0], str) else ""
                if img and not img.startswith("http"):
                    img = "https://cdn.dsmcdn.com" + img
                image_url = img or None
            return PriceResponse(
                ok=True, url=url, title=title, price_text=pt,
                price_value=price_value, currency="TRY",
                image_url=image_url, brand=brand,
            )

        # ── 3) __NEXT_DATA__ ──────────────────────────────────────────────
        next_data_tag = soup.find("script", id="__NEXT_DATA__")
        if next_data_tag:
            try:
                data = json.loads(next_data_tag.string or "")
                price_val = deep_find(data, ["discountedPrice", "salePrice", "price"])
                title_val = deep_find(data, ["name", "title", "productName"])
                if price_val is not None:
                    pv = float(price_val)
                    pt = (
                        f"{pv:,.2f}"
                        .replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    return PriceResponse(
                        ok=True, url=url,
                        title=clean_text(str(title_val)) if title_val else None,
                        price_text=pt, price_value=pv, currency="TRY",
                    )
            except (ValueError, json.JSONDecodeError):
                pass

        # ── 4) DOM FALLBACK: .prc-dsc / .prc-org ─────────────────────────
        for css_class in ("prc-dsc", "prc-org", "product-price-container"):
            node = soup.find(class_=css_class)
            if not node:
                node = soup.find(
                    lambda tag: tag.get("class")
                    and any(css_class in c for c in tag.get("class", []))
                )
            if node:
                raw = clean_text(node.get_text(" ", strip=True))
                if raw:
                    pv = normalize_price(raw)
                    if pv and pv > 0:
                        return PriceResponse(
                            ok=True, url=url,
                            price_text=raw.replace(" TL", "").replace("TL", "").strip(),
                            price_value=pv, currency="TRY",
                        )

        # ── 5) Genel JSON regex son çare ──────────────────────────────────
        for rx in [
            re.compile(r'"discountedPrice"\s*:\s*\{\s*"value"\s*:\s*(\d+(?:\.\d+)?)'),
            re.compile(r'"sellingPrice"\s*:\s*\{\s*"value"\s*:\s*(\d+(?:\.\d+)?)'),
            re.compile(r'"salePrice"\s*:\s*(\d+(?:\.\d+)?)'),
        ]:
            m2 = rx.search(html)
            if m2:
                pv = float(m2.group(1))
                if pv > 0:
                    pt = (
                        f"{pv:,.2f}"
                        .replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    return PriceResponse(
                        ok=True, url=url,
                        price_text=pt, price_value=pv, currency="TRY",
                    )

        return None

    except Exception:
        return None


def deep_find(obj, keys: list, max_depth: int = 12):
    """JSON ağacında verilen anahtarlardan birini özyinelemeli olarak arar."""
    if max_depth <= 0:
        return None
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] is not None:
                return obj[key]
        for v in obj.values():
            result = deep_find(v, keys, max_depth - 1)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = deep_find(item, keys, max_depth - 1)
            if result is not None:
                return result
    return None


# ─────────────────────────────────────────────
#  Genel scraper (Trendyol dışı siteler)
# ─────────────────────────────────────────────
def fetch_html(url: str, timeout: int = 25) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_title(soup: BeautifulSoup) -> Optional[str]:
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


def extract_price_from_meta_or_schema(soup: BeautifulSoup, html: str) -> Tuple[Optional[str], Optional[str]]:
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
            currency_node = (
                soup.select_one("meta[itemprop='priceCurrency']")
                or soup.select_one("meta[property='product:price:currency']")
                or soup.select_one("meta[property='og:price:currency']")
            )
            currency_text = None
            if currency_node:
                currency_text = currency_node.get("content") or currency_node.get_text(" ", strip=True)
            return raw, clean_text(currency_text) or "TRY"

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


def extract_price_from_dom(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    selectors = [
        ".price", ".product-price", ".sale-price",
        "[class*='price']", "[id*='price']", "[data-price]",
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


def extract_price_from_text(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    text = soup.get_text("\n", strip=True)
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    for line in lines[:140]:
        for rx in PRICE_REGEXES:
            match = rx.search(line)
            if match:
                return match.group("price"), match.group("currency")
    return None, None


def scrape_product(url: str) -> PriceResponse:
    # ── Trendyol özel işleyici ──
    if "trendyol.com" in url:
        result = scrape_trendyol(url)
        if result:
            return result
        return PriceResponse(
            ok=False,
            url=url,
            error="Trendyol ürünü alınamadı. Ürün kaldırılmış veya link geçersiz olabilir.",
        )

    # ── Genel scraper ──
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
        currency = normalize_currency(currency)

        if not price_text:
            return PriceResponse(
                ok=False,
                url=url,
                title=title,
                error="Fiyat bulunamadı. Sayfa yapısı değişmiş olabilir.",
            )

        return PriceResponse(
            ok=True,
            url=url,
            title=title,
            price_text=price_text,
            price_value=price_value,
            currency=currency,
        )

    except requests.HTTPError as exc:
        return PriceResponse(ok=False, url=url, error=f"HTTP hatası: {exc}")
    except requests.RequestException as exc:
        return PriceResponse(ok=False, url=url, error=f"Ağ hatası: {exc}")
    except Exception as exc:
        return PriceResponse(ok=False, url=url, error=f"Beklenmeyen hata: {exc}")


# ─────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "ok": True,
        "message": "Fiyat Cekme API v2 calisiyor",
        "endpoint": "/price?url=https://www.trendyol.com/...",
    }


@app.get("/price", response_model=PriceResponse)
def get_price(url: str = Query(..., description="Ürün sayfası URL")):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Geçerli bir URL gir")
    return scrape_product(url)
