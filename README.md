# Kocaeli Üniversitesi Kargo Dağıtım Sistemi

**Kocaeli'nin ilçelerinden Kocaeli Üniversitesi'ne** gelen kargo araçları için yük ve rota planlaması yapan Flask tabanlı, Genetik Algoritma kullanan kargo dağıtım optimizasyon sistemi.

## 🎯 Proje Amacı

Bu sistem, Kocaeli'nin 12 ilçesinden **Kocaeli Üniversitesi (Umuttepe Kampüsü)**'ne kargo taşımacılığı için:
- Optimal rota planlaması
- Araç kapasite-maliyet optimizasyonu
- Yakıt tüketimi ve kiralama maliyeti hesaplaması
- Dinamik sefer yönetimi

işlemlerini gerçekleştirir.

## 🚀 Özellikler

- **Genetik Algoritma (GA)** ile CVRP (Capacitated Vehicle Routing Problem) çözümü
- **A\* Algoritması** ile yol bulucu (kuş uçuşu değil, gerçek yol ağı)
- **Knapsack Optimizasyonu** ile araç yükleme
- **Leaflet.js** ile interaktif harita (OpenStreetMap - harici API kullanılmaz)
- Kullanıcı ve Yönetici panelleri
- 4 farklı test senaryosu
- Kiralık araç desteği (kapasite aşımı durumunda)
- Sefer kayıtlarının anlık tutulması
- Kullanıcıya sadece kendi kargosunun aracının güzergahının gösterilmesi

## 📍 İstasyonlar (Kocaeli İlçeleri)

| İstasyon | Tip | Koordinat |
|----------|-----|-----------|
| **Kocaeli Üniversitesi** | Ana Depo | 40.8225, 29.9213 |
| Başiskele | İlçe | 40.7244, 29.9097 |
| Çayırova | İlçe | 40.8267, 29.3728 |
| Darıca | İlçe | 40.7694, 29.3753 |
| Derince | İlçe | 40.7544, 29.8389 |
| Dilovası | İlçe | 40.7847, 29.5369 |
| Gebze | İlçe | 40.8027, 29.4307 |
| Gölcük | İlçe | 40.7175, 29.8306 |
| İzmit | İlçe | 40.7656, 29.9406 |
| Kandıra | İlçe | 41.0706, 30.1528 |
| Karamürsel | İlçe | 40.6917, 29.6167 |
| Kartepe | İlçe | 40.7389, 30.0378 |
| Körfez | İlçe | 40.7539, 29.7636 |

## 📋 Gereksinimler

- Python 3.8+
- Flask
- SQLAlchemy
- NumPy
- SciPy

## 🔧 Kurulum

1. **Proje dizinine gidin:**
```bash
cd cargosystem
```

2. **Sanal ortam oluşturun (önerilir):**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# veya
source venv/bin/activate  # Linux/Mac
```

3. **Gereksinimleri yükleyin:**
```bash
pip install -r requirements.txt
```

4. **Veritabanını başlatın:**
```bash
python init_db.py
```

5. **Uygulamayı çalıştırın:**
```bash
python app.py
```

6. **Tarayıcıda açın:**
- Ana Sayfa: http://localhost:5000
- Kullanıcı Paneli: http://localhost:5000/user
- Yönetici Paneli: http://localhost:5000/admin

## 📁 Proje Yapısı

```
cargosystem/
├── app.py                  # Ana Flask uygulaması
├── init_db.py              # Veritabanı başlatma
├── requirements.txt        # Python bağımlılıkları
├── algorithms/
│   ├── __init__.py
│   ├── genetic_algorithm.py  # GA ve Knapsack
│   ├── distance_calculator.py # A* ve mesafe hesaplama
│   └── scenarios.py          # Test senaryoları
├── templates/
│   ├── index.html          # Ana sayfa
│   ├── user_panel.html     # Kullanıcı paneli
│   └── admin_panel.html    # Yönetici paneli
└── static/
    ├── css/
    │   └── styles.css
    └── js/
        └── main.js
```

## 🗺️ Kocaeli İlçeleri

Sistem 12 Kocaeli ilçesini destekler:
- İzmit (Ana Depo)
- Gebze, Darıca, Çayırova, Dilovası
- Körfez, Derince, Gölcük, Karamürsel
- Kandıra, Kartepe, Başiskele

## 🚛 Araç Filosu

| Araç | Kapasite | Maliyet |
|------|----------|---------|
| Araç 1 | 500 kg | 1.0 ₺/km |
| Araç 2 | 750 kg | 1.2 ₺/km |
| Araç 3 | 1000 kg | 1.5 ₺/km |
| Kiralık | 500 kg | 200 ₺/gün + 1.0 ₺/km |

## 📊 Test Senaryoları

1. **Senaryo 1 - Hafif Yük:** ~880 kg (tek araç yeterli)
2. **Senaryo 2 - Orta Yük:** ~2100 kg (tüm araçlar)
3. **Senaryo 3 - Kapasite Aşımı:** 2700 kg (kiralık araç gerekli)
4. **Senaryo 4 - Yoğun Gün:** ~2230 kg (tüm ilçeler)

## 🔬 Algoritmalar

### Genetik Algoritma (CVRP)
- Popülasyon: 100
- Nesil: 500
- Mutasyon oranı: 0.1
- Çaprazlama oranı: 0.8
- Seçkinler: 10
- 2-opt yerel optimizasyon

### A* Pathfinding
- Haversine sezgisel
- Yol faktörü: 1.35x

### Knapsack Optimizasyonu
- Dinamik programlama
- Öncelikli kargo seçimi

## 📝 API Endpoints

### İstasyonlar
- `GET /api/stations` - Tüm istasyonları listele
- `POST /api/stations` - Yeni istasyon ekle
- `DELETE /api/stations/<id>` - İstasyon sil

### Kargolar
- `GET /api/cargos` - Tüm kargoları listele
- `POST /api/cargos` - Yeni kargo ekle
- `GET /api/cargos/track/<no>` - Kargo takip

### Araçlar
- `GET /api/vehicles` - Araçları listele
- `POST /api/vehicles` - Araç ekle

### Rotalar
- `POST /api/routes/optimize` - Rota optimizasyonu
- `GET /api/routes/active` - Aktif rotalar

### Senaryolar
- `POST /api/scenarios/test/<id>` - Senaryo çalıştır

### Analizler
- `GET /api/analytics/summary` - Özet istatistikler
- `GET /api/analytics/cost-breakdown` - Maliyet dağılımı

## 📄 Lisans

Bu proje eğitim amaçlıdır.

## 👤 Geliştirici

Kocaeli Üniversitesi - Yazılım Laboratuvarı Projesi
