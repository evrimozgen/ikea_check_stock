#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# IKEA Türkiye Stock Checker (Kartal store)
# Uses Playwright to query https://www.ikea.com.tr/musteri-hizmetleri/stok-sorgula
# Article codes fixed as given; filters 'Kartal'; emails if any availability appears.

import os, re, json, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

CHECK_URL = "https://www.ikea.com.tr/musteri-hizmetleri/stok-sorgula"
ARTICLE_CODES = ["20246708", "50338419", "70246386"]
STORE_KEYWORD = "Kartal"
CACHE_FILE = Path("last_status.json")

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(data):
    try:
        CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print("Cache write error:", e)

def send_email(subject, html_body):
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    to_email  = os.getenv("TO_EMAIL", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    if not (smtp_host and smtp_port and smtp_user and smtp_pass and to_email):
        print("Email not configured. Skipping email send.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())
    print("Email sent to", to_email)
    return True

def extract_kartal_rows(page_content: str):
    text = re.sub(r"\s+", " ", page_content)
    results = []
    for m in re.finditer(r"(.{0,200}Kartal.{0,200})", text, flags=re.IGNORECASE):
        block = m.group(1)
        status_match = re.search(r"(Stokta|Stokta yok|Tükendi|Stok yok|Sınırlı stok|Az stok|Stok bilgisi|Stok durumu[: ]?\w+)", block, flags=re.IGNORECASE)
        status = status_match.group(1) if status_match else "Bilinmiyor"
        results.append({"store_block": block, "status": status})
    return results

def run_check_for_code(page, code: str):
    page.goto(CHECK_URL, wait_until="domcontentloaded", timeout=45000)
    # fill product code (various selectors for robustness)
    selector_candidates = [
        'input[placeholder*="Ürün"]',
        'input[placeholder*="ürün"]',
        'input[placeholder*="Kod"]',
        'input[type="text"]',
        'input[name*="stock"]',
        'input[name*="urun"]',
    ]
    filled = False
    for sel in selector_candidates:
        try:
            page.wait_for_selector(sel, timeout=4000)
            page.fill(sel, code)
            filled = True
            break
        except Exception:
            continue
    if not filled:
        try:
            page.focus('input[type="text"]')
            page.keyboard.insert_text(code)
            filled = True
        except Exception:
            pass
    if not filled:
        return {"code": code, "ok": False, "error": "Ürün kodu alanı bulunamadı."}

    # try selecting store Kartal
    selected_store = False
    try:
        page.wait_for_selector("select", timeout=3000)
        for s in page.query_selector_all("select"):
            try:
                s.select_option(label=STORE_KEYWORD)
                selected_store = True
                break
            except Exception:
                continue
    except Exception:
        pass
    if not selected_store:
        try:
            triggers = [
                'text="Mağaza"','text="Mağaza Seç"','text="Mağaza seçin"',
                '[aria-haspopup="listbox"]','[role="combobox"]','button:has-text("Mağaza")'
            ]
            for t in triggers:
                try:
                    page.click(t, timeout=1500)
                    break
                except Exception:
                    continue
            page.click('text=Kartal', timeout=4000)
            selected_store = True
        except Exception:
            pass

    # click query
    clicked = False
    for b in ['button:has-text("Sorgula")','text="Sorgula"','button[type="submit"]']:
        try:
            page.click(b, timeout=3000)
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        try:
            page.keyboard.press("Enter")
            clicked = True
        except Exception:
            pass
    if not clicked:
        return {"code": code, "ok": False, "error": "Sorgula düğmesi bulunamadı."}

    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass

    content = page.content()
    rows = extract_kartal_rows(content)
    available = any(re.search(r"\bStokta\b|Sınırlı stok|Az stok", r["status"], re.IGNORECASE) for r in rows)
    details = "; ".join([r["status"] for r in rows]) if rows else "Kartal için sonuç bulunamadı"
    return {"code": code, "ok": True, "available": available, "details": details, "raw_hits": rows}

def main():
    cache = load_cache()
    all_results, any_available = [], False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="tr-TR")
        page = context.new_page()
        for code in ARTICLE_CODES:
            try:
                r = run_check_for_code(page, code)
            except Exception as e:
                r = {"code": code, "ok": False, "error": str(e)}
            all_results.append(r)
            if r.get("ok") and r.get("available"):
                any_available = True
        browser.close()

    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    summary = [f"<b>Tarih:</b> {now_str}", f"<b>Mağaza:</b> {STORE_KEYWORD}", "<hr>"]
    for r in all_results:
        if not r.get("ok"):
            summary.append(f"<b>{r['code']}</b>: Hata — {r.get('error','bilinmiyor')}")
        else:
            status_word = "VAR" if r.get("available") else "YOK"
            summary.append(f"<b>{r['code']}</b>: Kartal stok {status_word} — {r.get('details','')}")
    html_body = "<br>".join(summary)

    old = cache.get("last", {})
    changes = []
    for r in all_results:
        code = r["code"]
        was = None if old is None else old.get(code, {}).get("available")
        now = r.get("available")
        if r.get("ok") and (was is None or was is False) and now is True:
            changes.append(code)

    summary_on_empty = os.getenv("SUMMARY_EMAIL_ON_EMPTY", "false").lower() == "true"
    should_email = any_available or summary_on_empty

    if should_email:
        subject = "IKEA Kartal Stok Uyarısı" if any_available else "IKEA Kartal Stok Özeti"
        send_email(subject, html_body)

    cache["last"] = {r["code"]: {"available": r.get("available"), "details": r.get("details","")} for r in all_results}
    cache["last_run"] = now_str
    save_cache(cache)

    print("DONE")
    if any_available:
        print("At least one item available; email sent if configured.")
    else:
        print("No availability; email sent only if SUMMARY_EMAIL_ON_EMPTY=true.")

if __name__ == "__main__":
    main()
