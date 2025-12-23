"""
Veritabanı test scripti
"""
from app import db, app, Trip, Route, Cargo, Station, Vehicle
import json

with app.app_context():
    print('=== VERITABANI KONTROL ===')
    
    # İstasyonlar
    stations = Station.query.all()
    depot = Station.query.filter_by(is_depot=True).first()
    print(f'Toplam İstasyon: {len(stations)}')
    print(f'Depo: {depot.name if depot else "YOK"} ({depot.latitude}, {depot.longitude})' if depot else '')
    
    # Kargolar
    cargos = Cargo.query.all()
    print(f'\nToplam Kargo: {len(cargos)}')
    for c in cargos:
        print(f'  - Kargo {c.id}: {c.sender_name} -> {c.receiver_name}, Agirlik: {c.weight}kg, Durum: {c.status}, Arac: {c.vehicle_id}')
    
    # Tripler
    trips = Trip.query.all()
    print(f'\nToplam Trip: {len(trips)}')
    for t in trips:
        print(f'  - Trip {t.id}:')
        print(f'    Arac ID: {t.vehicle_id}')
        print(f'    Mesafe: {t.total_distance}')
        print(f'    Toplam Maliyet: {t.total_cost}')
        print(f'    Yakit Maliyeti: {t.fuel_cost}')
        print(f'    Durum: {t.status}')
        
        if t.path_coordinates:
            coords = json.loads(t.path_coordinates)
            print(f'    Path Koordinat Sayisi: {len(coords)}')
            if coords:
                print(f'    Ilk koordinat: {coords[0]}')
                print(f'    Son koordinat: {coords[-1]}')
        else:
            print('    Path Koordinat: YOK')
    
    # Rotalar
    routes = Route.query.all()
    print(f'\nToplam Route: {len(routes)}')
    for r in routes:
        print(f'  - Route {r.id}: Arac {r.vehicle_id}, Mesafe: {r.total_distance}, Maliyet: {r.total_cost}')

print('\n=== TEST TAMAMLANDI ===')
