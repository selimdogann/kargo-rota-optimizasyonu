"""
A* Pathfinding Test Scripti
Kuş uçuşu değil, A* ile yol ağı üzerinden rota oluşturma testi
"""
from algorithms.distance_calculator import (
    get_road_network, 
    generate_path_between_stations,
    KocaeliRoadNetwork
)

print('=== A* PATHFINDING TEST ===\n')

# Road network oluştur
rn = get_road_network()
print(f'Toplam Kavşak: {len(rn.intersections)}')
print('Kavşaklar:')
for k, v in rn.intersections.items():
    print(f'  {k}: {v["name"]} ({v["lat"]}, {v["lng"]})')

print(f'\nToplam Yol Bağlantısı: {len(rn.roads)}')

# K0 (Kocaeli Üniversitesi) bağlantılarını kontrol et
k0_connections = []
for road in rn.roads:
    if 'K0' in road:
        k0_connections.append(road)
print(f'\nK0 (Kocaeli Üniversitesi) Bağlantıları:')
for conn in k0_connections:
    print(f'  {conn}')

# Test: Kocaeli Üniversitesi'nden İzmit Merkeze A* path
print('\n--- A* TEST: K0 (Kocaeli Üniv.) -> K1 (İzmit Merkez) ---')
path_ids, distance = rn.a_star_path('K0', 'K1')
print(f'Path IDs: {path_ids}')
print(f'Mesafe: {distance:.2f} km')

# Path koordinatları test
print('\n--- PATH COORDINATES TEST ---')
# Kocaeli Üniversitesi (K0)
start_lat, start_lng = 40.8225, 29.9213
# İzmit Merkez (K1)  
end_lat, end_lng = 40.7654, 29.9408

coords = rn.get_path_coordinates(start_lat, start_lng, end_lat, end_lng)
print(f'Koordinat Sayısı: {len(coords)}')
if coords:
    print(f'İlk 3 koordinat:')
    for i, c in enumerate(coords[:3]):
        print(f'  {i+1}. {c}')
    print(f'Son 3 koordinat:')
    for i, c in enumerate(coords[-3:]):
        print(f'  {len(coords)-2+i}. {c}')

# generate_path_between_stations test
print('\n--- FULL ROUTE TEST: DEPO -> [İstasyon1, İstasyon2] -> DEPO ---')

# Mock depot ve istasyonlar
class MockStation:
    def __init__(self, name, lat, lng):
        self.name = name
        self.latitude = lat
        self.longitude = lng

depot = MockStation('Kocaeli Üniversitesi', 40.8225, 29.9213)
route_stations = [
    MockStation('Gebze', 40.8027, 29.4307),
    MockStation('İzmit', 40.7654, 29.9408),
]
all_stations = [depot] + route_stations

full_path = generate_path_between_stations(depot, route_stations, all_stations)
print(f'Full Path Koordinat Sayısı: {len(full_path)}')
if full_path:
    print(f'Başlangıç: {full_path[0]}')
    print(f'Bitiş: {full_path[-1]}')

print('\n=== TEST TAMAMLANDI ===')
