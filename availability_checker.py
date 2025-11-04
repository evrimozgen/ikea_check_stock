#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IKEA Kartal stok kontrolü (EMAIL'LI)
- Playwright yok; doğrudan CheckStock endpoint'ini çağırır.
- Ürün kodları NOKTASIZ girilir.
- Varsayılan: SADECE stok VAR ise e-posta gönderir.
- İsterseniz SUMMARY_EMAIL_ON_EMPTY=true yaparak stok yokken de özet e-postası gönderebilirsiniz.
"""

import os, re, json, requests, smtplib, ssl
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---- AYARLAR ----
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

# E-POSTA (ENV ile)
SMTP_HOST = os.getenv("SMTP_HOST","")
SMTP_PORT = int(os.getenv("SMTP_PORT","587"))
SMTP_USER = os.getenv("SMTP_USER","")
SMTP_PASS = os.getenv("SMTP_PASS","")
TO_EMAIL  = os.getenv("TO_EMAIL","")
FROM_EMAIL= os.getenv("FROM_EMAIL", SMTP_USER)
SUMMARY_EMAIL_ON_EMPTY = os.getenv("SUMMARY_EMAIL_ON_EMPTY","false").lower()=="true"

YOK_PAT = re.compile(r"\b(Stokta yok|Stok yok|Tükendi)\b", re.IGNORECASE)
VAR_PAT = re.compile(r"\b(Stokta|Sınırlı stok|Az stok)\b", re.IGNORECASE)

def parse_status(payload_text: str) -> str:
    """
    Yanıt JSON içinde HTML taşıyabilir; önce JSON'u dene, sonra HTML/metinden stok durumunu çıkar.
    """
    txt = payload_text
    try:
        obj = json.loads(payload_text)
        if isinstance(obj, dict) and "d" in obj and isinstance(obj["d"], str):
            txt = obj["d"]
        else:
            txt = json.dumps(obj, ensure_ascii=False)
    except Exception:
        pass

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

def send_email(subject: str, html: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and TO_EMAIL):
        print("Email not configured. Skipping email send.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls(context=ctx)
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(FROM_EMAIL, [TO_EMAIL], msg.as_string())
    print("Email sent to", TO_EMAIL)
    return True

def main():
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    results = []
    any_var = False

    for code in CODES:
        try:
            status, snippet = check_one(code)
        except Exception as e:
            status, snippet = f"HATA: {e}", ""
        any_var |= (status == "VAR")
        results.append({"code": code, "status": status})

    # Konsol özeti
    print(f"=== IKEA Kartal stok özeti @ {now} ===")
    for r in results:
        print(f"{r['code']}: {r['status']}")

    # E-posta içeriği
    lis = [f"<li><b>{r['code']}</b>: {r['status']}</li>" for r in results]
# E-posta içeriği (renkli, büyük yazı)
    lis = []
    for r in results:
        color = (
            "#2ecc71" if r["status"] == "VAR"
            else "#e74c3c" if r["status"] == "YOK"
            else "#7f8c8d"
        )
        lis.append(
            f"<li style='font-size:22px; line-height:1.6;'>"
            f"<b>{r['code']}</b>: "
            f"<span style='color:{color}; font-weight:bold;'>{r['status']}</span>"
            f"</li>"
        )
    
    # E-posta içeriği (tablo biçiminde, renkli)
rows = []
for r in results:
    color_bg = (
        "#d4edda" if r["status"] == "VAR"
        else "#f8d7da" if r["status"] == "YOK"
        else "#e2e3e5"
    )
    color_text = (
        "#155724" if r["status"] == "VAR"
        else "#721c24" if r["status"] == "YOK"
        else "#383d41"
    )
    rows.append(
        f"<tr style='background:{color_bg};color:{color_text};font-size:20px;'>"
        f"<td style='padding:10px 25px;'><b>{r['code']}</b></td>"
        f"<td style='padding:10px 25px;font-weight:bold;text-align:center;'>{r['status']}</td>"
        f"</tr>"
    )

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; font-size: 17px; color: #222;">
        <h2 style="color:#0058a3;">🛒 IKEA Kartal Stok Bildirimi</h2>
        <p style="font-size:16px;"><b>Tarih:</b> {now}<br><b>Mağaza:</b> IKEA Kartal</p>
    
        <table style="border-collapse:collapse; width:80%; max-width:600px; border:1px solid #ccc;">
          <thead>
            <tr style="background:#f1f1f1;">
              <th style="text-align:left;padding:10px 25px;">Ürün Kodu</th>
              <th style="text-align:center;padding:10px 25px;">Durum</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
    
        <p style="font-size:13px; color:#777; margin-top:30px;">
          Bu e-posta otomatik olarak gönderilmiştir.<br>
          IKEA Kartal stok kontrol sistemi (CheckStock API).
        </p>
      </body>
    </html>
    """




    # Politika: sadece VAR varsa gönder; özet için ENV ile açılabilir
    if any_var or SUMMARY_EMAIL_ON_EMPTY:
        subj = "IKEA Kartal Stok Uyarısı" if any_var else "IKEA Kartal Stok Özeti"
        send_email(subj, html)

if __name__ == "__main__":
    main()
