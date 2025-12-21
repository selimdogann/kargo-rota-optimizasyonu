"""
Mesafe Hesaplama ve A* Pathfinding Algoritmaları
Kuş uçuşu değil, gerçek yol ağı simülasyonu ile güzergah hesaplama
Harici API (Google Maps, Yandex vb.) KULLANILMAMAKTADIR
"""

import math
import heapq
from typing import Dict, List, Tuple, Optional
import random


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Haversine formülü ile iki koordinat arası mesafe (km)
    """
    R = 6371  # Dünya yarıçapı (km)
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def road_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Gerçekçi yol mesafesi hesapla (kuş uçuşu * faktör)
    Yol ağı için yaklaşık 1.3-1.5 kat daha uzun
    """
    crow_distance = haversine_distance(lat1, lon1, lat2, lon2)
    # Kocaeli bölgesi için ortalama yol faktörü
    road_factor = 1.35
    return crow_distance * road_factor


# ==================== KOCAELİ YOL AĞI ====================
# Gerçek yol ağını simüle eden sabit veriler
# Bu veriler Google/Yandex API kullanılmadan manuel oluşturulmuştur

KOCAELI_ROAD_NETWORK = {
    # Ana yol kavşak noktaları (lat, lng) - Kocaeli bölgesi
    'intersections': [
        {'id': 'K1', 'lat': 40.7654, 'lng': 29.9408, 'name': 'İzmit Merkez'},
        {'id': 'K2', 'lat': 40.7700, 'lng': 29.8800, 'name': 'İzmit Batı'},
        {'id': 'K3', 'lat': 40.7600, 'lng': 29.8200, 'name': 'Derince Kavşak'},
        {'id': 'K4', 'lat': 40.7550, 'lng': 29.7600, 'name': 'Körfez Kavşak'},
        {'id': 'K5', 'lat': 40.7200, 'lng': 29.8400, 'name': 'Gölcük Kavşak'},
        {'id': 'K6', 'lat': 40.7000, 'lng': 29.6500, 'name': 'Karamürsel Kavşak'},
        {'id': 'K7', 'lat': 40.7800, 'lng': 29.5500, 'name': 'Dilovası Kavşak'},
        {'id': 'K8', 'lat': 40.8000, 'lng': 29.4500, 'name': 'Gebze Batı'},
        {'id': 'K9', 'lat': 40.8027, 'lng': 29.4307, 'name': 'Gebze Merkez'},
        {'id': 'K10', 'lat': 40.7700, 'lng': 29.3800, 'name': 'Darıca Kavşak'},
        {'id': 'K11', 'lat': 40.8200, 'lng': 29.3700, 'name': 'Çayırova Kavşak'},
        {'id': 'K12', 'lat': 40.7400, 'lng': 29.9800, 'name': 'Kartepe Kavşak'},
        {'id': 'K13', 'lat': 40.7200, 'lng': 29.9400, 'name': 'Başiskele Kavşak'},
        {'id': 'K14', 'lat': 41.0000, 'lng': 30.0000, 'name': 'Kandıra Yol'},
        {'id': 'K15', 'lat': 40.9000, 'lng': 29.9800, 'name': 'Kandıra Güney'},
        {'id': 'K16', 'lat': 40.8500, 'lng': 29.9500, 'name': 'İzmit Kuzey'},
    ],
    # Yol bağlantıları (from_id, to_id) - çift yönlü
    'roads': [
        ('K1', 'K2'), ('K2', 'K3'), ('K3', 'K4'), ('K4', 'K7'),
        ('K7', 'K8'), ('K8', 'K9'), ('K9', 'K10'), ('K10', 'K11'),
        ('K1', 'K12'), ('K12', 'K13'), ('K13', 'K5'),
        ('K3', 'K5'), ('K5', 'K6'), ('K4', 'K6'),
        ('K1', 'K16'), ('K16', 'K15'), ('K15', 'K14'),
        ('K2', 'K5'), ('K6', 'K7'), ('K11', 'K9'),
        ('K1', 'K13'), ('K16', 'K12'),
    ]
}


class KocaeliRoadNetwork:
    """
    Kocaeli bölgesi için özel yol ağı
    A* algoritması ile gerçekçi güzergah hesaplama
    NOT: Harici API kullanılmamaktadır
    """
    
    def __init__(self):
        self.intersections = {i['id']: i for i in KOCAELI_ROAD_NETWORK['intersections']}
        self.roads = KOCAELI_ROAD_NETWORK['roads']
        self._build_graph()
    
    def _build_graph(self):
        """Yol ağı grafını oluştur"""
        self.graph = {i_id: [] for i_id in self.intersections}
        
        for road in self.roads:
            from_id, to_id = road
            from_node = self.intersections[from_id]
            to_node = self.intersections[to_id]
            
            # Mesafe hesapla
            distance = haversine_distance(
                from_node['lat'], from_node['lng'],
                to_node['lat'], to_node['lng']
            )
            
            # Çift yönlü bağlantı
            self.graph[from_id].append((to_id, distance))
            self.graph[to_id].append((from_id, distance))
    
    def find_nearest_intersection(self, lat: float, lng: float) -> str:
        """Verilen koordinata en yakın kavşağı bul"""
        min_dist = float('inf')
        nearest = None
        
        for i_id, intersection in self.intersections.items():
            dist = haversine_distance(lat, lng, intersection['lat'], intersection['lng'])
            if dist < min_dist:
                min_dist = dist
                nearest = i_id
        
        return nearest
    
    def a_star_path(self, start_id: str, goal_id: str) -> Tuple[List[str], float]:
        """
        A* algoritması ile en kısa yolu bul
        
        Args:
            start_id: Başlangıç kavşak ID
            goal_id: Hedef kavşak ID
            
        Returns:
            (kavşak ID listesi, toplam mesafe)
        """
        if start_id == goal_id:
            return [start_id], 0
        
        # Priority queue: (f_score, node_id)
        open_set = [(0, start_id)]
        came_from = {}
        
        g_score = {i_id: float('inf') for i_id in self.intersections}
        g_score[start_id] = 0
        
        f_score = {i_id: float('inf') for i_id in self.intersections}
        f_score[start_id] = self._heuristic(start_id, goal_id)
        
        open_set_hash = {start_id}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            open_set_hash.discard(current)
            
            if current == goal_id:
                # Yolu yeniden oluştur
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path, g_score[goal_id]
            
            for neighbor, weight in self.graph.get(current, []):
                tentative_g_score = g_score[current] + weight
                
                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self._heuristic(neighbor, goal_id)
                    
                    if neighbor not in open_set_hash:
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
                        open_set_hash.add(neighbor)
        
        # Yol bulunamadı - doğrudan bağlantı
        return [start_id, goal_id], haversine_distance(
            self.intersections[start_id]['lat'], self.intersections[start_id]['lng'],
            self.intersections[goal_id]['lat'], self.intersections[goal_id]['lng']
        )
    
    def _heuristic(self, node1_id: str, node2_id: str) -> float:
        """A* sezgisel fonksiyonu - Haversine mesafesi"""
        n1 = self.intersections[node1_id]
        n2 = self.intersections[node2_id]
        return haversine_distance(n1['lat'], n1['lng'], n2['lat'], n2['lng'])
    
    def get_path_coordinates(self, start_lat: float, start_lng: float, 
                            end_lat: float, end_lng: float) -> List[Dict]:
        """
        İki koordinat arası A* ile hesaplanmış yol koordinatlarını döndür
        
        Args:
            start_lat, start_lng: Başlangıç koordinatları
            end_lat, end_lng: Bitiş koordinatları
            
        Returns:
            Koordinat listesi [{'lat': ..., 'lng': ...}, ...]
        """
        # En yakın kavşakları bul
        start_intersection = self.find_nearest_intersection(start_lat, start_lng)
        end_intersection = self.find_nearest_intersection(end_lat, end_lng)
        
        # A* ile yol bul
        path_ids, total_distance = self.a_star_path(start_intersection, end_intersection)
        
        # Koordinat listesi oluştur
        coordinates = []
        
        # Başlangıç noktası
        coordinates.append({'lat': start_lat, 'lng': start_lng})
        
        # Ara kavşaklar (detaylı yol ile)
        for i, node_id in enumerate(path_ids):
            node = self.intersections[node_id]
            
            # Önceki noktadan bu noktaya ara noktalar ekle
            if i > 0 or (coordinates and 
                        haversine_distance(coordinates[-1]['lat'], coordinates[-1]['lng'],
                                          node['lat'], node['lng']) > 0.5):
                prev = coordinates[-1]
                # Ara noktalar ekle (yolun eğriliğini simüle et)
                num_intermediate = 3
                for j in range(1, num_intermediate + 1):
                    t = j / (num_intermediate + 1)
                    intermediate_lat = prev['lat'] + t * (node['lat'] - prev['lat'])
                    intermediate_lng = prev['lng'] + t * (node['lng'] - prev['lng'])
                    
                    # Hafif sapma ekle (yol karakteristiği)
                    offset = 0.002 * math.sin(j * math.pi / 2)
                    coordinates.append({
                        'lat': intermediate_lat + offset * (0.5 - random.random()),
                        'lng': intermediate_lng + offset * (0.5 - random.random())
                    })
            
            coordinates.append({'lat': node['lat'], 'lng': node['lng']})
        
        # Bitiş noktasına bağlan
        if coordinates:
            last = coordinates[-1]
            if haversine_distance(last['lat'], last['lng'], end_lat, end_lng) > 0.1:
                # Ara noktalar
                num_intermediate = 2
                for j in range(1, num_intermediate + 1):
                    t = j / (num_intermediate + 1)
                    coordinates.append({
                        'lat': last['lat'] + t * (end_lat - last['lat']),
                        'lng': last['lng'] + t * (end_lng - last['lng'])
                    })
        
        coordinates.append({'lat': end_lat, 'lng': end_lng})
        
        return coordinates


# Global yol ağı instance
_road_network = None

def get_road_network() -> KocaeliRoadNetwork:
    """Singleton yol ağı instance'ı döndür"""
    global _road_network
    if _road_network is None:
        _road_network = KocaeliRoadNetwork()
    return _road_network


def update_distance_matrix(db, Station, DistanceMatrix):
    """
    Tüm istasyonlar arası mesafe matrisini güncelle
    """
    stations = Station.query.all()
    
    # Mevcut matrisi temizle
    DistanceMatrix.query.delete()
    
    for i, station1 in enumerate(stations):
        for j, station2 in enumerate(stations):
            if i != j:
                distance = road_distance(
                    station1.latitude, station1.longitude,
                    station2.latitude, station2.longitude
                )
                
                dm = DistanceMatrix(
                    from_station_id=station1.id,
                    to_station_id=station2.id,
                    distance=round(distance, 2)
                )
                db.session.add(dm)
    
    db.session.commit()


def get_distance_matrix(db, Station, DistanceMatrix) -> Dict:
    """
    Mesafe matrisini dictionary olarak getir
    """
    matrix = {}
    distances = DistanceMatrix.query.all()
    
    for d in distances:
        key = f"{d.from_station_id}_{d.to_station_id}"
        matrix[key] = d.distance
    
    return matrix


class AStarPathfinder:
    """
    A* Algoritması ile İki Nokta Arası En Kısa Yol
    """
    
    def __init__(self, nodes: List[Dict], edges: List[Dict]):
        """
        Args:
            nodes: Düğüm listesi [{'id': 1, 'lat': 40.5, 'lng': 29.5}, ...]
            edges: Kenar listesi [{'from': 1, 'to': 2, 'weight': 10.5}, ...]
        """
        self.nodes = {n['id']: n for n in nodes}
        self.graph = {}
        
        # Graf yapısını oluştur
        for node in nodes:
            self.graph[node['id']] = []
        
        for edge in edges:
            self.graph[edge['from']].append((edge['to'], edge['weight']))
            # Çift yönlü
            self.graph[edge['to']].append((edge['from'], edge['weight']))
    
    def heuristic(self, node1_id: int, node2_id: int) -> float:
        """
        A* için sezgisel fonksiyon (Haversine mesafesi)
        """
        node1 = self.nodes[node1_id]
        node2 = self.nodes[node2_id]
        return haversine_distance(
            node1['lat'], node1['lng'],
            node2['lat'], node2['lng']
        )
    
    def find_path(self, start_id: int, goal_id: int) -> Tuple[List[int], float]:
        """
        A* ile en kısa yolu bul
        
        Returns:
            (yol listesi, toplam mesafe)
        """
        # Priority queue: (f_score, node_id)
        open_set = [(0, start_id)]
        came_from = {}
        
        g_score = {node_id: float('inf') for node_id in self.nodes}
        g_score[start_id] = 0
        
        f_score = {node_id: float('inf') for node_id in self.nodes}
        f_score[start_id] = self.heuristic(start_id, goal_id)
        
        open_set_hash = {start_id}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            open_set_hash.discard(current)
            
            if current == goal_id:
                # Yolu yeniden oluştur
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path, g_score[goal_id]
            
            for neighbor, weight in self.graph.get(current, []):
                tentative_g_score = g_score[current] + weight
                
                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self.heuristic(neighbor, goal_id)
                    
                    if neighbor not in open_set_hash:
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
                        open_set_hash.add(neighbor)
        
        return [], float('inf')  # Yol bulunamadı


class RoadNetworkBuilder:
    """
    İstasyonlar arası yol ağı oluşturucu
    """
    
    def __init__(self, stations: List):
        """
        Args:
            stations: İstasyon listesi
        """
        self.stations = stations
    
    def build_complete_network(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Tam bağlı graf oluştur (her istasyon diğer tüm istasyonlara bağlı)
        
        Returns:
            (nodes, edges)
        """
        nodes = [
            {'id': s.id, 'lat': s.latitude, 'lng': s.longitude, 'name': s.name}
            for s in self.stations
        ]
        
        edges = []
        for i, s1 in enumerate(self.stations):
            for j, s2 in enumerate(self.stations):
                if i < j:
                    distance = road_distance(
                        s1.latitude, s1.longitude,
                        s2.latitude, s2.longitude
                    )
                    edges.append({
                        'from': s1.id,
                        'to': s2.id,
                        'weight': round(distance, 2)
                    })
        
        return nodes, edges
    
    def build_mst_network(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Minimum Spanning Tree (Prim algoritması) ile yol ağı oluştur
        
        Returns:
            (nodes, edges)
        """
        nodes = [
            {'id': s.id, 'lat': s.latitude, 'lng': s.longitude, 'name': s.name}
            for s in self.stations
        ]
        
        if len(self.stations) < 2:
            return nodes, []
        
        # Prim algoritması
        in_mst = {self.stations[0].id}
        edges = []
        
        while len(in_mst) < len(self.stations):
            min_edge = None
            min_weight = float('inf')
            
            for s1 in self.stations:
                if s1.id not in in_mst:
                    continue
                
                for s2 in self.stations:
                    if s2.id in in_mst:
                        continue
                    
                    distance = road_distance(
                        s1.latitude, s1.longitude,
                        s2.latitude, s2.longitude
                    )
                    
                    if distance < min_weight:
                        min_weight = distance
                        min_edge = (s1.id, s2.id, distance)
            
            if min_edge:
                edges.append({
                    'from': min_edge[0],
                    'to': min_edge[1],
                    'weight': round(min_edge[2], 2)
                })
                in_mst.add(min_edge[1])
        
        return nodes, edges


def calculate_route_path(stations: List, distance_matrix: Dict) -> List[Dict]:
    """
    Verilen istasyon sırası için detaylı yol bilgisi oluştur
    
    Args:
        stations: Sıralı istasyon listesi
        distance_matrix: Mesafe matrisi
    
    Returns:
        Yol segmentleri listesi
    """
    path_segments = []
    
    for i in range(len(stations) - 1):
        s1 = stations[i]
        s2 = stations[i + 1]
        
        key = f"{s1.id}_{s2.id}"
        distance = distance_matrix.get(key, 0)
        
        # Ara noktalar oluştur (düz çizgi için 2 nokta yeterli)
        segment = {
            'from': {
                'id': s1.id,
                'name': s1.name,
                'lat': s1.latitude,
                'lng': s1.longitude
            },
            'to': {
                'id': s2.id,
                'name': s2.name,
                'lat': s2.latitude,
                'lng': s2.longitude
            },
            'distance': distance,
            'waypoints': generate_waypoints(s1, s2)
        }
        
        path_segments.append(segment)
    
    return path_segments


def generate_waypoints(station1, station2, num_points: int = 5) -> List[Dict]:
    """
    İki istasyon arasında ara noktalar oluştur (düzgün eğri için)
    
    Args:
        station1: Başlangıç istasyonu
        station2: Bitiş istasyonu
        num_points: Ara nokta sayısı
    
    Returns:
        Waypoint listesi
    """
    waypoints = []
    
    lat_diff = station2.latitude - station1.latitude
    lng_diff = station2.longitude - station1.longitude
    
    for i in range(num_points + 1):
        t = i / num_points
        
        # Basit lineer interpolasyon (gerekirse Bezier eğrisi eklenebilir)
        lat = station1.latitude + t * lat_diff
        lng = station1.longitude + t * lng_diff
        
        waypoints.append({'lat': lat, 'lng': lng})
    
    return waypoints


def generate_realistic_road_path(station1, station2, all_stations: List, num_intermediate: int = 8) -> List[Dict]:
    """
    A* algoritması ile gerçekçi yol çizimi
    KUŞ UÇUŞU DEĞİL - Yol ağı üzerinden A* ile hesaplanır
    HARİCİ API KULLANILMAMAKTADIR
    
    Args:
        station1: Başlangıç istasyonu (object veya dict)
        station2: Bitiş istasyonu (object veya dict)
        all_stations: Tüm istasyonlar
        num_intermediate: Kullanılmıyor (A* otomatik hesaplar)
    
    Returns:
        Koordinat listesi [{'lat': ..., 'lng': ...}, ...]
    """
    # Station obje veya dict olabilir
    lat1 = station1.latitude if hasattr(station1, 'latitude') else station1.get('latitude', station1.get('lat'))
    lng1 = station1.longitude if hasattr(station1, 'longitude') else station1.get('longitude', station1.get('lng'))
    lat2 = station2.latitude if hasattr(station2, 'latitude') else station2.get('latitude', station2.get('lat'))
    lng2 = station2.longitude if hasattr(station2, 'longitude') else station2.get('longitude', station2.get('lng'))
    
    # A* yol ağını kullan
    road_network = get_road_network()
    path_coords = road_network.get_path_coordinates(lat1, lng1, lat2, lng2)
    
    return path_coords


def generate_path_between_stations(depot, route_stations: List, all_stations: List) -> List[Dict]:
    """
    Tüm rota için A* algoritması ile yol koordinatları oluştur
    
    KUŞ UÇUŞU ÇİZİM YAPILMAMAKTADIR!
    HARİCİ API (Google Maps, Yandex) KULLANILMAMAKTADIR!
    
    Kendi A* implementasyonumuz ile Kocaeli yol ağı üzerinde
    gerçekçi güzergah hesaplanır.
    
    Args:
        depot: Depo istasyonu (başlangıç ve bitiş)
        route_stations: Rota sırası (istasyon listesi)
        all_stations: Tüm istasyonlar
    
    Returns:
        Tam rota için koordinat listesi
    """
    full_path = []
    road_network = get_road_network()
    
    # Depo koordinatları
    depot_lat = depot.latitude if hasattr(depot, 'latitude') else depot.get('latitude', depot.get('lat'))
    depot_lng = depot.longitude if hasattr(depot, 'longitude') else depot.get('longitude', depot.get('lng'))
    
    if not route_stations:
        return full_path
    
    # Depo -> İlk istasyon (A* ile)
    first_station = route_stations[0]
    first_lat = first_station.latitude if hasattr(first_station, 'latitude') else first_station.get('latitude', first_station.get('lat'))
    first_lng = first_station.longitude if hasattr(first_station, 'longitude') else first_station.get('longitude', first_station.get('lng'))
    
    segment = road_network.get_path_coordinates(depot_lat, depot_lng, first_lat, first_lng)
    full_path.extend(segment)
    
    # İstasyonlar arası (A* ile)
    for i in range(len(route_stations) - 1):
        s1 = route_stations[i]
        s2 = route_stations[i+1]
        
        lat1 = s1.latitude if hasattr(s1, 'latitude') else s1.get('latitude', s1.get('lat'))
        lng1 = s1.longitude if hasattr(s1, 'longitude') else s1.get('longitude', s1.get('lng'))
        lat2 = s2.latitude if hasattr(s2, 'latitude') else s2.get('latitude', s2.get('lat'))
        lng2 = s2.longitude if hasattr(s2, 'longitude') else s2.get('longitude', s2.get('lng'))
        
        segment = road_network.get_path_coordinates(lat1, lng1, lat2, lng2)
        # İlk koordinatı atla (önceki segmentin son koordinatı ile aynı)
        if segment and full_path:
            full_path.extend(segment[1:])
        else:
            full_path.extend(segment)
    
    # Son istasyon -> Depo (A* ile)
    last_station = route_stations[-1]
    last_lat = last_station.latitude if hasattr(last_station, 'latitude') else last_station.get('latitude', last_station.get('lat'))
    last_lng = last_station.longitude if hasattr(last_station, 'longitude') else last_station.get('longitude', last_station.get('lng'))
    
    segment = road_network.get_path_coordinates(last_lat, last_lng, depot_lat, depot_lng)
    if segment and full_path:
        full_path.extend(segment[1:])
    else:
        full_path.extend(segment)
    
    return full_path


def calculate_total_path_distance(path_coords: List[Dict]) -> float:
    """
    Koordinat listesi üzerinden toplam mesafe hesapla
    """
    total = 0
    for i in range(len(path_coords) - 1):
        total += haversine_distance(
            path_coords[i]['lat'], path_coords[i]['lng'],
            path_coords[i+1]['lat'], path_coords[i+1]['lng']
        )
    return total
