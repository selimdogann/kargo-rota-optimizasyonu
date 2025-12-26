"""
Clarke-Wright Savings Algoritması ile VRP (Vehicle Routing Problem) Çözümü

SENARYO: Kocaeli ilçelerinden Kocaeli Üniversitesi'ne kargo toplama (TEK YÖNLÜ)

ALGORITMA:
1. Savings (Tasarruf) hesaplama: s(i,j) = d(depot,i) + d(depot,j) - d(i,j)
2. Savings değerlerini büyükten küçüğe sırala
3. Kısıtları (kapasite, mesafe) ihlal etmeden rotaları birleştir
4. OSRM API ile gerçek yol mesafelerini kullan

ÖZELLİKLER:
- Coğrafi kümeleme (bölge bazlı optimizasyon)
- Kapasite kısıtı (araç kapasitesi)
- Mesafe kısıtı (maksimum rota uzunluğu)
- OSRM API ile gerçek yol geometrisi
"""

import math
import requests
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
import json


@dataclass
class Saving:
    """Savings değeri için veri yapısı"""
    station1_id: int
    station2_id: int
    value: float


class ClarkeWrightSolver:
    """
    Clarke-Wright Savings Algoritması ile VRP Çözücü
    
    Özellikler:
    - Paralel savings yaklaşımı
    - Kapasite ve mesafe kısıtları
    - Coğrafi bölge optimizasyonu
    - OSRM entegrasyonu
    """
    
    OSRM_BASE_URL = "https://router.project-osrm.org"
    
    def __init__(
        self,
        stations: List,
        vehicles: List,
        cargos: List,
        depot,
        distance_matrix: Dict = None,
        max_route_distance: float = 80.0,
        use_osrm: bool = True
    ):
        """
        Args:
            stations: İstasyon listesi (ilçeler)
            vehicles: Araç listesi
            cargos: Kargo listesi
            depot: Depo istasyonu (Kocaeli Üniversitesi)
            distance_matrix: Önceden hesaplanmış mesafe matrisi
            max_route_distance: Maksimum rota mesafesi (km)
            use_osrm: OSRM API kullanılsın mı?
        """
        self.stations = stations
        self.vehicles = vehicles
        self.cargos = cargos
        self.depot = depot
        self.distance_matrix = distance_matrix or {}
        self.max_route_distance = max_route_distance
        self.use_osrm = use_osrm
        
        # Kargo KAYNAK istasyonlarını belirle (ilçeler)
        self.pickup_stations = list(set(c.source_station for c in cargos if c.source_station))
        
        # Her istasyon için toplam kargo ağırlığını hesapla
        self.station_weights = {}
        self.station_cargo_count = {}
        for station in self.pickup_stations:
            station_cargos = [c for c in cargos if c.source_station_id == station.id]
            self.station_weights[station.id] = sum(c.weight for c in station_cargos)
            self.station_cargo_count[station.id] = len(station_cargos)
        
        # Mesafe matrisini hesapla veya OSRM'den al
        self._build_distance_matrix()
        
        # Savings değerlerini hesapla
        self.savings = self._calculate_savings()
    
    def _build_distance_matrix(self):
        """Tüm istasyonlar arası mesafe matrisini oluştur"""
        all_stations = self.pickup_stations + [self.depot]
        
        for s1 in all_stations:
            for s2 in all_stations:
                if s1.id != s2.id:
                    key = f"{s1.id}_{s2.id}"
                    if key not in self.distance_matrix:
                        if self.use_osrm:
                            dist = self._get_osrm_distance(s1, s2)
                        else:
                            dist = self._haversine_distance(
                                s1.latitude, s1.longitude,
                                s2.latitude, s2.longitude
                            ) * 1.3  # Yol faktörü
                        self.distance_matrix[key] = dist
    
    def _get_osrm_distance(self, station1, station2) -> float:
        """OSRM API'den gerçek yol mesafesini al"""
        try:
            # OSRM formatı: lng,lat
            coords = f"{station1.longitude},{station1.latitude};{station2.longitude},{station2.latitude}"
            url = f"{self.OSRM_BASE_URL}/route/v1/driving/{coords}?overview=false"
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['code'] == 'Ok' and data['routes']:
                    # Mesafe metre cinsinden, km'ye çevir
                    return data['routes'][0]['distance'] / 1000
        except Exception as e:
            print(f"OSRM error: {e}")
        
        # Fallback: Haversine mesafe
        return self._haversine_distance(
            station1.latitude, station1.longitude,
            station2.latitude, station2.longitude
        ) * 1.3
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine formülü ile iki nokta arası mesafe (km)"""
        R = 6371  # Dünya yarıçapı (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def get_distance(self, station1, station2) -> float:
        """İki istasyon arası mesafe"""
        key = f"{station1.id}_{station2.id}"
        if key in self.distance_matrix:
            return self.distance_matrix[key]
        
        # Matrise yoksa hesapla
        dist = self._haversine_distance(
            station1.latitude, station1.longitude,
            station2.latitude, station2.longitude
        ) * 1.3
        self.distance_matrix[key] = dist
        return dist
    
    def _calculate_savings(self) -> List[Saving]:
        """
        Clarke-Wright Savings değerlerini hesapla
        
        Savings Formülü: s(i,j) = d(depot,i) + d(depot,j) - d(i,j)
        
        Bu değer, i ve j istasyonlarını aynı rotaya koyarak ne kadar
        mesafe tasarrufu sağlandığını gösterir.
        """
        savings = []
        
        for i, station_i in enumerate(self.pickup_stations):
            for j, station_j in enumerate(self.pickup_stations):
                if i >= j:  # Sadece üst üçgen (i < j)
                    continue
                
                # Depot'tan istasyonlara mesafeler
                d_depot_i = self.get_distance(self.depot, station_i)
                d_depot_j = self.get_distance(self.depot, station_j)
                
                # İki istasyon arası mesafe
                d_i_j = self.get_distance(station_i, station_j)
                
                # Savings değeri
                saving_value = d_depot_i + d_depot_j - d_i_j
                
                if saving_value > 0:
                    savings.append(Saving(
                        station1_id=station_i.id,
                        station2_id=station_j.id,
                        value=saving_value
                    ))
        
        # Savings değerlerini büyükten küçüğe sırala
        savings.sort(key=lambda s: s.value, reverse=True)
        
        return savings
    
    def _get_station_by_id(self, station_id: int):
        """ID'den istasyon nesnesini bul"""
        for station in self.pickup_stations:
            if station.id == station_id:
                return station
        return None
    
    def _calculate_route_distance(self, route: List) -> float:
        """Bir rotanın toplam mesafesini hesapla"""
        if not route:
            return 0
        
        total = 0
        
        # İstasyonlar arası mesafe
        for i in range(len(route) - 1):
            total += self.get_distance(route[i], route[i + 1])
        
        # Son istasyondan depoya
        total += self.get_distance(route[-1], self.depot)
        
        return total
    
    def _calculate_route_weight(self, route: List) -> float:
        """Bir rotadaki toplam kargo ağırlığı"""
        return sum(self.station_weights.get(s.id, 0) for s in route)
    
    def _calculate_route_cargo_count(self, route: List) -> int:
        """Bir rotadaki toplam kargo sayısı"""
        return sum(self.station_cargo_count.get(s.id, 0) for s in route)
    
    def _can_merge_routes(self, route1: List, route2: List, vehicle_capacity: float) -> bool:
        """İki rota birleştirilebilir mi?"""
        if not route1 or not route2:
            return True
        
        merged_weight = self._calculate_route_weight(route1) + self._calculate_route_weight(route2)
        if merged_weight > vehicle_capacity:
            return False
        
        # Birleşik rotanın mesafesini kontrol et
        merged = route1 + route2
        merged_distance = self._calculate_route_distance(merged)
        if merged_distance > self.max_route_distance:
            return False
        
        return True
    
    def solve(self) -> Dict:
        """
        Clarke-Wright Savings algoritması ile VRP'yi çöz
        
        Returns:
            Dict: {vehicle_id: [station_list], ...}
        """
        if not self.pickup_stations:
            return {v.id: [] for v in self.vehicles}
        
        # Başlangıçta her istasyon kendi rotasında
        # route_map: station_id -> route_id
        # routes: route_id -> [station_list]
        route_map = {}
        routes = {}
        
        for i, station in enumerate(self.pickup_stations):
            route_id = i
            routes[route_id] = [station]
            route_map[station.id] = route_id
        
        next_route_id = len(self.pickup_stations)
        
        # Savings listesini işle
        for saving in self.savings:
            s1_id = saving.station1_id
            s2_id = saving.station2_id
            
            route1_id = route_map.get(s1_id)
            route2_id = route_map.get(s2_id)
            
            # Aynı rotada iseler atla
            if route1_id is None or route2_id is None:
                continue
            if route1_id == route2_id:
                continue
            
            route1 = routes.get(route1_id, [])
            route2 = routes.get(route2_id, [])
            
            if not route1 or not route2:
                continue
            
            # Station1 route1'in başında veya sonunda mı?
            # Station2 route2'nin başında veya sonunda mı?
            s1_at_end = route1[-1].id == s1_id
            s1_at_start = route1[0].id == s1_id
            s2_at_end = route2[-1].id == s2_id
            s2_at_start = route2[0].id == s2_id
            
            # Sadece uçlardaki istasyonlar birleştirilebilir
            if not ((s1_at_end or s1_at_start) and (s2_at_end or s2_at_start)):
                continue
            
            # En büyük araç kapasitesini kullan
            max_capacity = max(v.capacity for v in self.vehicles)
            
            # Birleştirme kontrolü
            if not self._can_merge_routes(route1, route2, max_capacity):
                continue
            
            # Rotaları birleştir
            # 4 durum var: start-start, start-end, end-start, end-end
            if s1_at_end and s2_at_start:
                new_route = route1 + route2
            elif s1_at_end and s2_at_end:
                new_route = route1 + list(reversed(route2))
            elif s1_at_start and s2_at_end:
                new_route = route2 + route1
            elif s1_at_start and s2_at_start:
                new_route = list(reversed(route1)) + route2
            else:
                continue
            
            # Yeni rotayı kaydet
            routes[next_route_id] = new_route
            
            # route_map'i güncelle
            for station in new_route:
                route_map[station.id] = next_route_id
            
            # Eski rotaları sil
            if route1_id in routes:
                del routes[route1_id]
            if route2_id in routes:
                del routes[route2_id]
            
            next_route_id += 1
        
        # Rotaları araçlara ata
        return self._assign_routes_to_vehicles(list(routes.values()))
    
    def _assign_routes_to_vehicles(self, route_list: List[List]) -> Dict:
        """
        Oluşan rotaları araçlara ata - KAPASİTE KESİNLİKLE AŞILMAZ
        First-Fit Decreasing (FFD) - Büyük araçlardan başla, minimum araç kullan
        """
        result = {v.id: [] for v in self.vehicles}
        vehicle_loads = {v.id: 0.0 for v in self.vehicles}
        self.vehicle_cargo_assignments = {v.id: [] for v in self.vehicles}
        
        # Araçları kapasiteye göre sırala (BÜYÜKTEN KÜÇÜĞE - önce büyük araçları doldur)
        sorted_vehicles = sorted(self.vehicles, key=lambda v: v.capacity, reverse=True)
        
        # Kargoları ağırlığa göre sırala (büyükten küçüğe)
        sorted_cargos = sorted(self.cargos, key=lambda c: c.weight, reverse=True)
        
        # Her kargoyu ilk sığan araca ata (büyük araçlardan başla)
        for cargo in sorted_cargos:
            weight = cargo.weight
            station = cargo.source_station
            
            # İlk sığan araca ata (büyük araçlar önce)
            assigned = False
            for vehicle in sorted_vehicles:
                remaining = vehicle.capacity - vehicle_loads[vehicle.id]
                if weight <= remaining:
                    # İstasyonu rotaya ekle (tekrar etmeden)
                    if station not in result[vehicle.id]:
                        result[vehicle.id].append(station)
                    vehicle_loads[vehicle.id] += weight
                    self.vehicle_cargo_assignments[vehicle.id].append(cargo)
                    assigned = True
                    break
            
            if not assigned:
                print(f"CRITICAL: Cargo {cargo.id} ({weight}kg) couldn't be assigned!")
        
        # Her rotayı depoya olan mesafeye göre optimize et
        for vehicle_id in result:
            if result[vehicle_id]:
                result[vehicle_id] = self._optimize_route_order(result[vehicle_id])
        
        return result
    
    def _optimize_route_order(self, route: List) -> List:
        """
        Rota içindeki durak sırasını optimize et
        En yakın komşu (Nearest Neighbor) heuristic kullanarak
        """
        if len(route) <= 2:
            return route
        
        optimized = []
        remaining = route.copy()
        
        # Depoya en yakın istasyondan başla (aslında rotanın sonu olacak)
        # Bu yüzden en uzaktan başlayalım ki rota depoya doğru ilerlesin
        current = max(remaining, key=lambda s: self.get_distance(self.depot, s))
        optimized.append(current)
        remaining.remove(current)
        
        while remaining:
            # Mevcut istasyona en yakın istasyonu bul
            nearest = min(remaining, key=lambda s: self.get_distance(current, s))
            optimized.append(nearest)
            remaining.remove(nearest)
            current = nearest
        
        return optimized
    
    def get_osrm_route_geometry(self, route: List) -> Dict:
        """
        OSRM API'den rota geometrisini al
        
        Returns:
            Dict: {'coordinates': [[lng, lat], ...], 'distance': float, 'duration': float, 'geometry': str}
        """
        if not route:
            return {'coordinates': [], 'distance': 0, 'duration': 0, 'geometry': None}
        
        # Rota koordinatlarını oluştur: istasyonlar + depot
        all_points = route + [self.depot]
        
        try:
            # OSRM formatı: lng,lat;lng,lat;...
            coords = ';'.join([f"{s.longitude},{s.latitude}" for s in all_points])
            url = f"{self.OSRM_BASE_URL}/route/v1/driving/{coords}?overview=full&geometries=polyline"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['code'] == 'Ok' and data['routes']:
                    route_data = data['routes'][0]
                    # Encoded polyline'ı decode et
                    geometry_polyline = route_data.get('geometry', '')
                    
                    # Ayrıca geojson olarak da al
                    url_geojson = f"{self.OSRM_BASE_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"
                    response_geojson = requests.get(url_geojson, timeout=10)
                    coordinates = []
                    if response_geojson.status_code == 200:
                        data_geojson = response_geojson.json()
                        if data_geojson['code'] == 'Ok' and data_geojson['routes']:
                            coordinates = data_geojson['routes'][0]['geometry']['coordinates']
                    
                    return {
                        'coordinates': coordinates,
                        'distance': route_data['distance'] / 1000,  # km
                        'duration': route_data['duration'] / 60,  # dakika
                        'geometry': geometry_polyline  # Encoded polyline for frontend
                    }
        except Exception as e:
            print(f"OSRM geometry error: {e}")
        
        # Fallback: basit koordinat listesi
        coords = [[s.longitude, s.latitude] for s in all_points]
        return {
            'coordinates': coords,
            'distance': self._calculate_route_distance(route),
            'duration': self._calculate_route_distance(route) * 2,  # Tahmin
            'geometry': None
        }
    
    def solve_with_details(self) -> Dict:
        """
        Detaylı çözüm döndür (maliyet, mesafe, geometri dahil)
        
        Returns:
            Dict: Detaylı çözüm bilgileri
        """
        solution = self.solve()
        
        result = {
            'routes': [],
            'total_distance': 0,
            'total_cost': 0,
            'total_weight': 0,
            'total_cargos': 0,
            'vehicles_used': 0
        }
        
        for vehicle in self.vehicles:
            route = solution.get(vehicle.id, [])
            if not route:
                continue
            
            route_distance = self._calculate_route_distance(route)
            route_weight = self._calculate_route_weight(route)
            route_cargos = self._calculate_route_cargo_count(route)
            
            # Maliyet hesapla
            fuel_cost = route_distance * vehicle.cost_per_km
            rental_cost = vehicle.rental_cost if vehicle.is_rental else 0
            total_cost = fuel_cost + rental_cost
            
            # OSRM geometrisi al
            geometry = self.get_osrm_route_geometry(route)
            
            route_info = {
                'vehicle': {
                    'id': vehicle.id,
                    'name': vehicle.name,
                    'capacity': vehicle.capacity,
                    'is_rental': vehicle.is_rental,
                    'cost_per_km': vehicle.cost_per_km
                },
                'stops': [{
                    'station_id': s.id,
                    'station_name': s.name,
                    'latitude': s.latitude,
                    'longitude': s.longitude,
                    'weight': self.station_weights.get(s.id, 0),
                    'cargo_count': self.station_cargo_count.get(s.id, 0)
                } for s in route],
                'depot': {
                    'id': self.depot.id,
                    'name': self.depot.name,
                    'latitude': self.depot.latitude,
                    'longitude': self.depot.longitude
                },
                'distance': route_distance,
                'weight': route_weight,
                'cargo_count': route_cargos,
                'fuel_cost': fuel_cost,
                'rental_cost': rental_cost,
                'total_cost': total_cost,
                'utilization': (route_weight / vehicle.capacity * 100) if vehicle.capacity > 0 else 0,
                'geometry': geometry
            }
            
            result['routes'].append(route_info)
            result['total_distance'] += route_distance
            result['total_cost'] += total_cost
            result['total_weight'] += route_weight
            result['total_cargos'] += route_cargos
            result['vehicles_used'] += 1
        
        return result


class RegionalClarkeWright(ClarkeWrightSolver):
    """
    Bölge bazlı Clarke-Wright algoritması
    
    Kocaeli'yi coğrafi bölgelere ayırıp her bölge için ayrı optimize eder:
    - Batı Bölgesi: Gebze, Darıca, Çayırova, Dilovası
    - Merkez Bölgesi: İzmit, Derince, Körfez
    - Doğu Bölgesi: Kartepe, Kandıra
    - Güney Bölgesi: Gölcük, Karamürsel, Başiskele
    """
    
    # Coğrafi bölge tanımları (boylam bazlı)
    REGIONS = {
        'BATI': {
            'min_lng': 29.3,
            'max_lng': 29.6,
            'districts': ['Gebze', 'Darıca', 'Çayırova', 'Dilovası']
        },
        'MERKEZ': {
            'min_lng': 29.6,
            'max_lng': 29.9,
            'districts': ['İzmit', 'Derince', 'Körfez']
        },
        'DOGU': {
            'min_lng': 29.9,
            'max_lng': 30.3,
            'districts': ['Kartepe', 'Kandıra']
        },
        'GUNEY': {
            'min_lat': None,  # Enlem bazlı
            'max_lat': 40.72,
            'districts': ['Gölcük', 'Karamürsel', 'Başiskele']
        }
    }
    
    def __init__(self, *args, **kwargs):
        # Önce station_regions'ı tanımla (boş olarak)
        self.station_regions = {}
        super().__init__(*args, **kwargs)
        # Şimdi bölgeleri ata ve savings'i yeniden hesapla
        self.station_regions = self._assign_regions()
        self.savings = self._calculate_savings()
    
    def _assign_regions(self) -> Dict[int, str]:
        """Her istasyonu bir bölgeye ata"""
        regions = {}
        
        for station in self.pickup_stations:
            lng = station.longitude
            lat = station.latitude
            
            # Bölge belirleme
            if lng < 29.6:
                regions[station.id] = 'BATI'
            elif lng < 29.9:
                regions[station.id] = 'MERKEZ'
            elif lat < 40.72 and lng < 29.95:
                regions[station.id] = 'GUNEY'
            else:
                regions[station.id] = 'DOGU'
        
        return regions
    
    def _calculate_savings(self) -> List[Saving]:
        """
        Bölge bazlı savings hesapla
        
        Aynı bölgedeki istasyonlar için daha yüksek savings değeri ver
        """
        savings = []
        
        for i, station_i in enumerate(self.pickup_stations):
            for j, station_j in enumerate(self.pickup_stations):
                if i >= j:
                    continue
                
                d_depot_i = self.get_distance(self.depot, station_i)
                d_depot_j = self.get_distance(self.depot, station_j)
                d_i_j = self.get_distance(station_i, station_j)
                
                saving_value = d_depot_i + d_depot_j - d_i_j
                
                # Aynı bölgedeki istasyonlar için bonus
                if self.station_regions.get(station_i.id) == self.station_regions.get(station_j.id):
                    saving_value *= 1.2  # %20 bonus
                
                if saving_value > 0:
                    savings.append(Saving(
                        station1_id=station_i.id,
                        station2_id=station_j.id,
                        value=saving_value
                    ))
        
        savings.sort(key=lambda s: s.value, reverse=True)
        return savings


# ============================================================================
# OSRM YARDIMCI FONKSİYONLARI
# ============================================================================

def get_osrm_route(coordinates: List[Tuple[float, float]]) -> Dict:
    """
    OSRM API'den rota bilgisi al
    
    Args:
        coordinates: [(lat, lng), ...] formatında koordinat listesi
    
    Returns:
        Dict: {'coordinates': [[lng, lat], ...], 'distance': km, 'duration': dakika}
    """
    if len(coordinates) < 2:
        return {'coordinates': [], 'distance': 0, 'duration': 0}
    
    try:
        # OSRM formatı: lng,lat;lng,lat;...
        coord_str = ';'.join([f"{lng},{lat}" for lat, lng in coordinates])
        url = f"https://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok' and data['routes']:
                route = data['routes'][0]
                return {
                    'coordinates': route['geometry']['coordinates'],
                    'distance': route['distance'] / 1000,
                    'duration': route['duration'] / 60
                }
    except Exception as e:
        print(f"OSRM error: {e}")
    
    return {'coordinates': [], 'distance': 0, 'duration': 0}


def get_osrm_distance_matrix(coordinates: List[Tuple[float, float]]) -> List[List[float]]:
    """
    OSRM Table API'den mesafe matrisi al
    
    Args:
        coordinates: [(lat, lng), ...] formatında koordinat listesi
    
    Returns:
        List[List[float]]: Mesafe matrisi (km cinsinden)
    """
    if len(coordinates) < 2:
        return []
    
    try:
        coord_str = ';'.join([f"{lng},{lat}" for lat, lng in coordinates])
        url = f"https://router.project-osrm.org/table/v1/driving/{coord_str}"
        
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok':
                # Saniye -> dakika, metre -> km dönüşümü
                durations = data.get('durations', [])
                # Mesafe için ayrı bir istek gerekiyor veya süre bazlı tahmin
                return [[d / 1000 if d else 0 for d in row] for row in durations]
    except Exception as e:
        print(f"OSRM matrix error: {e}")
    
    return []


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("Clarke-Wright Savings Algorithm Module")
    print("Bu modül app.py tarafından import edilir")
