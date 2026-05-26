<div align="center">
  <img src="assets/asset1.jpg" alt="GeForce NOW Rich Presence Banner" width="100%" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);" />
  <br/>
  <h1>🎮 Discord için GeForce NOW Rich Presence</h1>
  <p>
    <strong>GeForce NOW üzerinden oynadığın gerçek oyunları Discord profilinde göster — Windows ve Linux için otomatik ve şık bir şekilde.</strong>
  </p>
  
  [🇺🇸 English](./README.md) • [🇪🇸 Español](./README.es.md) • [🇹🇷 Türkçe](./README.tr.md)
  
  <br/>
  <br/>

  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/github/v/release/Enderjua/GeForce-NOW-Rich-Presence?style=for-the-badge&color=00C853&logo=github&label=En%20Son%20S%C3%BCr%C3%BCm" alt="En Son Sürüm"/>
  </a>
  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases">
    <img src="https://img.shields.io/github/downloads/Enderjua/GeForce-NOW-Rich-Presence/total?style=for-the-badge&color=2962FF&logo=github&label=İndirmeler" alt="Toplam İndirme"/>
  </a>
  
</div>

---

## 🕹️ Bu Nedir?

**Discord için GeForce NOW Rich Presence**, GeForce NOW üzerinde oynadığın **gerçek oyunu** doğrudan Discord profilinde göstermeni sağlar. Artık sıkıcı ve düz "GeForce NOW Oynuyor" durumlarına son!

Bu modern ve geliştirilmiş **fork**, eksiksiz çoklu işletim sistemi desteği (Windows & Linux), Linux üzerinde yerel pencere algılama, gerçek zamanlı Steam entegrasyonu, kişiselleştirilebilir durum alanları ve Discord ödülleri için özel araçlar sunar. 🎮💚

---

## ✨ Özellikler & Büyük Yenilikler

* 🐧 **Linux Desteği (Wayland & X11 Uyumlu)** `[Yeni / Linux Desteği]`
  * Linux sistemleriyle tam entegrasyon. Wayland oturumları için KDE KWin Scripting API ve DBus üzerinden yerel pencere algılama; X11 masaüstü ortamları için ise `xdotool` üzerinden otomatik algılama yapar. Wine veya ağır emülatörlere ihtiyaç duymaz.
* 🌐 **Anlık Steam Entegrasyonu (Scraping)** `[Yeni]`
  * Tarayıcı çerezlerini (Edge/Chrome üzerinden otomatik ya da manuel) kullanarak canlı Steam durumunu çeker. Böylece profilinde detaylı oyun içi bilgileri (*"Dota 2 oynuyor | Dereceli Maçta"*, aktif lobiler vb.) gerçek zamanlı gösterebilirsin.
* 🎁 **Discord Quest Modu (Çoklu Oyun Simülasyonu)** `[Yeni]`
  * Discord ödüllerini ve görevlerini kolayca tamamla! Arka planda geçici ve izole süreçler başlatarak aynı anda birden fazla oyunu (oyun başına 15 dakikalık aktif süre sınırı ile) simüle eder.
* ✏️ **Özelleştirilebilir Profil Detayları** `[Yeni]`
  * Sistem tepsisi (tray) üzerinden birinci satır detaylarını, ikinci satır durumunu ve grup boyutunu (mevcut/maksimum) tamamen kendi isteğine göre düzenleyebilirsin.
* 🎨 **Karanlık Tema Tasarımı (Gaming)** `[Yeni]`
  * Tüm Qt5 sistem tepsisi pencereleri ve arayüz diyalogları için modern karanlık tema uyarlaması.
* ⚡ **Otomatik WebDriver Güncelleyici (Windows)**
  * Steam çerezlerini çekerken sorun yaşamaman için arka planda Edge WebDriver versiyonunu otomatik kontrol eder ve günceller.
* ✅ **Tak & Çalıştır**: Başlatıldığı andan itibaren tamamen arka planda otomatik çalışır.

---

## 📥 Kurulum ve Çalıştırma

### 🪟 Windows

1. [En Son Sürümler](https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest) sayfasından hazır `.exe` kurulum dosyasını indir.
2. Kurulum sihirbazını çalıştırıp adımları tamamla.
3. Uygulamayı aç. Sistem tepsisinde (sağ altta, görev çubuğu köşesinde) çalışmaya başlayacaktır.
4. GeForce NOW'dan bir oyuna gir ve Discord profilinin otomatik güncellenmesini izle!

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch vb.)

GeForce NOW Linux üzerinde tarayıcı veya Electron tabanlı istemciler üzerinden çalıştığı için, uygulamayı kaynak kodundan kolayca çalıştırabilirsin:

1. **Depoyu bilgisayarına kopyala:**
   ```bash
   git clone https://github.com/Enderjua/GeForce-NOW-Rich-Presence.git
   cd GeForce-NOW-Rich-Presence
   ```
2. **Sanal ortam (venv) oluştur ve aktif et:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Gerekli kütüphaneleri yükle:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Not: Klasik X11 pencere yöneticisi kullanıyorsan sisteminde `xdotool` paketinin yüklü olduğundan emin ol).*
4. **Uygulamayı başlat:**
   ```bash
   PYTHONPATH=. python3 src/GeForceNOWRichPresence.py
   ```
   *(Saf Wayland oturumlarında uygulama doğrudan KWin/Wayland API'lerine bağlanacaktır).*

---

## ⚙️ Sistem Tepsisi (Tray) Seçenekleri

Sistem tepsisindeki uygulama simgesine sağ tıklayarak tüm ayarları yönetebilirsin:

| Komut | Açıklama |
| :--- | :--- |
| 🎮 **Oyunu Zorla...** | Otomatik algılamayı devre dışı bırakıp profilinde görünmesini istediğin oyunu manuel seç. |
| 🎁 **Discord Görev Modu** | Discord görevlerini hızlıca tamamlamak için çoklu oyun simülasyonu başlat. |
| ✅ **Steam Çerezini Al** | Tarayıcı çerezini çekerek Steam profil verilerini entegre et. |
| 👥 **Grup Boyutunu Belirle...**| Durum alanında gösterilecek maksimum grup sınırını ayarla. |
| 🚀 **GeForce NOW'ı Aç** | NVIDIA GeForce NOW uygulamasını hızlıca çalıştır. |
| 📊 **Oyun Veritabanını Güncelle** | Discord detectable uygulamalar önbelleğini yenile. |
| 📝 **Logları Aç** | Hata tespiti için arka plan çalışma günlüklerini görüntüle. |
| ❌ **Çıkış** | Uygulamayı tamamen kapat. |

---

## 🧠 Nasıl Çalışır?

Uygulama arka planda hafif bir servis gibi çalışır:
1. **İzler**: Aktif pencereleri takip eder (Wayland'de KWin DBus API, Windows'ta Win32 API'leri kullanarak).
2. **Düzenler**: GeForce NOW pencere başlığındaki gereksiz ifadeleri temizleyip sadece oyun adını çıkarır.
3. **Eşleştirir**: Temizlenen oyun adını Discord'un resmi uygulama kataloğuyla eşleştirir.
4. **Başlatır**: Geçici bir dizinde minimal bir sanal yürütücü dosya çalıştırarak durumu doğrudan yerel Discord istemcine iletir.

---

## 🧩 SSS (Sıkça Sorulan Sorular)

**S: Windows kullanıcısıyım, Python veya harici bir bağımlılık kurmam gerekiyor mu?**  
C: Hayır. Windows için sunulan `.exe` sürümü tamamen kendi kendine çalışacak şekilde paketlenmiştir.

**S: Steam çerezini almak güvenli mi?**  
C: Evet. Çerez verileri tamamen yerel makinenizde saklanır ve hiçbir uzak sunucuya aktarılmaz. Şifrenizi istemez ya da kaydetmez.

---

## 💬 Geliştiriciler, Destek & İletişim

Bu proje, aşağıdaki geliştiricilerin ortak çalışmasıdır:

* 🧑‍💻 **KarmaDevz** - Windows paketinin ve uygulamanın çekirdek mimarisinin kurucusu ve geliştiricisi.
  * [GitHub Profili](https://github.com/KarmaDevz) • [PayPal Destek](https://paypal.me/KarmaDevz)
* 🛠️ **Enderjua** - Linux entegrasyonu, Quest Modu geliştirmesi, hata çözümleri ve özellik eklemeleriyle fork yöneticisi.
  * **GitHub Fork:** [Enderjua/GeForce-NOW-Rich-Presence](https://github.com/Enderjua/GeForce-NOW-Rich-Presence)
  * **Discord Sunucusu:** [Destek Sunucumuza Katıl](https://discord.gg/A9ESFRTzqR)
  * **E-posta:** enderjua@gmail.com
  * **Instagram:** [@marijuabakunin](https://instagram.com/marijuabakunin)

---

<div align="center">
  <a href="https://github.com/Enderjua/GeForce-NOW-Rich-Presence/releases/latest">
    <img src="https://img.shields.io/badge/Hemen%20İndir%20➡️-1B5E20?style=for-the-badge&logo=nvidia&logoColor=white" alt="Hemen İndir"/>
  </a>
</div>
