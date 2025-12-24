"""
Kocaeli Kargo Dağıtım Sistemi - Veritabanı Başlatma Scripti
Bu script veritabanını oluşturur ve başlangıç verilerini yükler.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Station, Vehicle, Admin, User

def init_database(force_reset=False):
    """Veritabanını başlat ve örnek verileri yükle
    
    Args:
        force_reset: True ise mevcut veritabanını sıfırlar (DİKKAT: tüm veriler silinir)
    """
    
    with app.app_context():
        if force_reset:
            # Tüm tabloları sıfırla (DİKKAT: tüm veriler silinecek!)
            db.drop_all()
            print("⚠ Tüm tablolar silindi (force_reset=True)")
        
        # Tabloları oluştur
        db.create_all()
        print("✓ Veritabanı tabloları oluşturuldu")
        
        # Varsayılan admin oluştur
        if Admin.query.count() == 0:
            admin = Admin(
                username='admin',
                full_name='Sistem Yöneticisi',
                email='admin@kargo.com',
                is_superadmin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✓ Varsayılan admin oluşturuldu (kullanıcı: admin, şifre: admin123)")
        else:
            print("→ Admin zaten mevcut")
        
        # Varsayılan User (admin rolünde) oluştur
        if User.query.count() == 0:
            # Admin kullanıcı
            admin_user = User(
                email='admin@kargo.com',
                full_name='Sistem Yöneticisi',
                phone='0532 000 0000',
                role='admin',
                is_active=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            
            # Örnek normal kullanıcı
            test_user = User(
                email='kullanici@test.com',
                full_name='Test Kullanıcı',
                phone='0533 111 1111',
                role='user',
                is_active=True
            )
            test_user.set_password('123456')
            db.session.add(test_user)
            
            db.session.commit()
            print("✓ Varsayılan kullanıcılar oluşturuldu:")
            print("  - Admin: admin@kargo.com / admin123")
            print("  - Kullanıcı: kullanici@test.com / 123456")
        else:
            print("→ Kullanıcılar zaten mevcut")
        
        # Mevcut istasyonları kontrol et
        if Station.query.count() == 0:
            # Kocaeli Üniversitesi (Ana Depo) ve Kocaeli ilçeleri
            # Kargolar ilçelerden Kocaeli Üniversitesi'ne gelecek
            districts = [
                {'name': 'Kocaeli Üniversitesi', 'latitude': 40.8225, 'longitude': 29.9213, 'is_depot': True},  # Ana Depo - Umuttepe Kampüsü
                {'name': 'İzmit', 'latitude': 40.7656, 'longitude': 29.9406, 'is_depot': False},
                {'name': 'Gebze', 'latitude': 40.8027, 'longitude': 29.4307, 'is_depot': False},
                {'name': 'Darıca', 'latitude': 40.7694, 'longitude': 29.3753, 'is_depot': False},
                {'name': 'Çayırova', 'latitude': 40.8267, 'longitude': 29.3728, 'is_depot': False},
                {'name': 'Dilovası', 'latitude': 40.7847, 'longitude': 29.5369, 'is_depot': False},
                {'name': 'Körfez', 'latitude': 40.7539, 'longitude': 29.7636, 'is_depot': False},
                {'name': 'Derince', 'latitude': 40.7544, 'longitude': 29.8389, 'is_depot': False},
                {'name': 'Gölcük', 'latitude': 40.7175, 'longitude': 29.8306, 'is_depot': False},
                {'name': 'Karamürsel', 'latitude': 40.6917, 'longitude': 29.6167, 'is_depot': False},
                {'name': 'Kandıra', 'latitude': 41.0706, 'longitude': 30.1528, 'is_depot': False},
                {'name': 'Kartepe', 'latitude': 40.7389, 'longitude': 30.0378, 'is_depot': False},
                {'name': 'Başiskele', 'latitude': 40.7244, 'longitude': 29.9097, 'is_depot': False}
            ]
            
            for d in districts:
                station = Station(
                    name=d['name'],
                    latitude=d['latitude'],
                    longitude=d['longitude'],
                    is_depot=d['is_depot']
                )
                db.session.add(station)
            
            db.session.commit()
            print(f"✓ {len(districts)} ilçe (istasyon) eklendi")
        else:
            print("→ İstasyonlar zaten mevcut")
        
        # Mevcut araçları kontrol et
        if Vehicle.query.count() == 0:
            # Başlangıç araç filosu - 3 adet, kiralama maliyeti yok
            # Problem gereksinimleri:
            # - Yol maliyeti: km başına 1 birim
            # - Araç kapasiteleri: 500, 750, 1000 kg
            # - Kiralık araç: 200 birim (500 kg kapasiteli)
            vehicles = [
                {'name': 'Araç 1 (500kg)', 'capacity': 500, 'cost_per_km': 1.0, 'is_rental': False, 'rental_cost': 0},
                {'name': 'Araç 2 (750kg)', 'capacity': 750, 'cost_per_km': 1.0, 'is_rental': False, 'rental_cost': 0},
                {'name': 'Araç 3 (1000kg)', 'capacity': 1000, 'cost_per_km': 1.0, 'is_rental': False, 'rental_cost': 0},
            ]
            
            for v in vehicles:
                vehicle = Vehicle(
                    name=v['name'],
                    capacity=v['capacity'],
                    cost_per_km=v['cost_per_km'],
                    is_rental=v['is_rental'],
                    rental_cost=v['rental_cost']
                )
                db.session.add(vehicle)
            
            db.session.commit()
            print(f"✓ {len(vehicles)} araç eklendi")
        else:
            print("→ Araçlar zaten mevcut")
        
        # Özet bilgileri göster
        print("\n--- Veritabanı Özeti ---")
        print(f"İstasyon sayısı: {Station.query.count()}")
        print(f"Araç sayısı: {Vehicle.query.count()}")
        print(f"Depo: {Station.query.filter_by(is_depot=True).first().name}")
        
        print("\n✓ Veritabanı başlatma tamamlandı!")
        print("Uygulamayı başlatmak için: python app.py")

if __name__ == '__main__':
    import sys
    # Komut satırından --reset parametresi ile çalıştırılırsa veritabanını sıfırla
    force_reset = '--reset' in sys.argv
    if force_reset:
        print("⚠ DİKKAT: Veritabanı sıfırlanacak! Tüm veriler silinecek.")
        confirm = input("Devam etmek istiyor musunuz? (evet/hayır): ")
        if confirm.lower() != 'evet':
            print("İşlem iptal edildi.")
            sys.exit(0)
    init_database(force_reset=force_reset)
