#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IKEA Kartal stok testi (mailsiz)
- Playwright yok, direkt CheckStock endpoint'ine istek atar.
- Ürün kodları NOKTASIZ girilir.
"""

import re, json, requests
from datetime import datetime, timezone

CODES = ["20246708", "50338419", "70246386"]  # NOKTASIZ
STORE_CODE = "530"  # IKEA Kartal
URL = "https://www.ikea.com.tr/_ws/general.aspx/CheckStock"

HEADERS = {
    "Accept": "text/plain, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.ikea.com.tr",
    "Referer": "https://www.ikea.com.tr/musteri-hizmetleri/stok-sorgula",
    "User-Agent": "Mozilla/5.0",
}

YOK_PAT = re.compile(r"\b(Stokta yok|Stok yok|Tükendi)\b", re.IGNORECASE)
VAR_PAT = re.compile(r"\b(Stokta|Sınırlı stok|Az stok)\b", re.IGNORECASE)

def parse_status(payload_text: str) -> str:
    # Yanıt JSON içinde HTML taşıyabilir; önce JSON'u dene
    txt = payload_text
    try:
        obj = json.loads(payload_text)
        if isinstance(obj, dict) and "d" in obj and isinstance(obj["d"], str):
            txt = obj["d"]
        else:
            txt = json.dumps(obj, ensure_ascii=False)
    except Exception:
        pass

    # Önce YOK sonra VAR kalıpları
    if YOK_PAT.search(txt):
        return "YOK"
    if VAR_PAT.search(txt):
        return "VAR"
    return "Bilinmiyor"

def check_one(code: str):
    r = requests.post(URL, headers=HEADERS, json={"stockCode": code, "storeCode": STORE_CODE}, timeout=20)
    r.raise_for_status()
    status = parse_status(r.text)
    return status, r.text[:1200]

def main():
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"=== IKEA Kartal stok testi @ {now} ===")
    for code in CODES:
        try:
            status, snippet = check_one(code)
            print(f"{code}: {status}")
            with open(f"resp_{code}.txt", "w", encoding="utf-8") as f:
                f.write(snippet)
        except Exception as e:
            print(f"{code}: HATA -> {e}")

if __name__ == "__main__":
    main()
