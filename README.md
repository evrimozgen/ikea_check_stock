# IKEA Kartal Stok Otomasyonu (GitHub Actions)

Bu depo, IKEA Türkiye stok sorgulama sayfasını Playwright ile ziyaret edip **Kartal mağazasına** göre filtreleyerek
şu ürünlerin stok durumunu kontrol eder ve e-posta gönderir:
- 202.467.08
- 503.384.19
- 702.463.86

## Kurulum
1) Bu dosyaları GitHub'ta yeni bir repoya yükleyin.
2) Repo → **Settings → Secrets and variables → Actions** altında aşağıdaki *Repository secrets*'ları ekleyin:
   - `SMTP_HOST` (örn. smtp.gmail.com)
   - `SMTP_PORT` (örn. 587)
   - `SMTP_USER` (örn. youraddress@gmail.com)
   - `SMTP_PASS` (Gmail Uygulama Şifresi)
   - `TO_EMAIL` (bildirim alacak adres)
   - `FROM_EMAIL` (gönderen adres, genelde SMTP_USER ile aynı)
   - `SUMMARY_EMAIL_ON_EMPTY` (`true` yaparsanız stok olmasa da özet maili gelir; aksi halde sadece stok bulunduğunda mail gelir)

3) Zamanlama GitHub Actions cron ile tanımlı (UTC):
   - İstanbul 08:00 → **05:00 UTC**
   - İstanbul 12:00 → **09:00 UTC**
   - İstanbul 16:00 → **13:00 UTC**

İsterseniz **Run workflow** butonuyla manuel de çalıştırabilirsiniz.

## Dosyalar
- `ikea_stock_checker.py` — Playwright botu + e-posta bildirimi + basit durum önbelleği
- `requirements.txt` — minimum bağımlılık
- `.github/workflows/ikea-stock.yml` — zamanlanmış GitHub Actions iş akışı

## Notlar
- Site işaretçileri değişirse Python dosyasındaki seçicileri güncelleyin.
- Gmail ile gönderim için 2FA + **Uygulama Şifresi** gereklidir.
- E-posta istemiyorsanız Telegram bildirimi ekleyebiliriz (bot token + chat id).
