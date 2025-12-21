"""
Kocaeli Kargo Dağıtım Sistemi - Veritabanı Başlatma Scripti
Bu script veritabanını oluşturur ve başlangıç verilerini yükler.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Station, Vehicle

def init_database():
    """Veritabanını başlat ve örnek verileri yükle"""
    
    with app.app_context():
        # Tabloları oluştur
        db.create_all()
        print("✓ Veritabanı tabloları oluşturuldu")
        
        # Mevcut istasyonları kontrol et
        if Station.query.count() == 0:
            # Kocaeli ilçeleri
            districts = [
                {'name': 'İzmit', 'latitude': 40.7656, 'longitude': 29.9406, 'is_depot': True},
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
            # Araç filosu
            vehicles = [
                {'name': 'Araç 1', 'capacity': 500, 'cost_per_km': 1.0, 'is_rental': False, 'rental_cost': 0},
                {'name': 'Araç 2', 'capacity': 750, 'cost_per_km': 1.2, 'is_rental': False, 'rental_cost': 0},
                {'name': 'Araç 3', 'capacity': 1000, 'cost_per_km': 1.5, 'is_rental': False, 'rental_cost': 0},
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
    init_database()
