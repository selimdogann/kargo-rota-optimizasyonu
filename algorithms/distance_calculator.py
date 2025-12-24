"""
Mesafe Hesaplama ve En Kısa Yol Algoritması
Kocaeli İli Yol Ağı - Gerçek Mesafe Verileri
Dijkstra Algoritması ile En Kısa Yol Hesaplama
"""

import math
import heapq
from typing import Dict, List, Tuple, Optional, Union


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formülü ile iki koordinat arası mesafe (km)"""
    R = 6371
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


# ============================================================================
# KOCAELİ İLÇE KOORDİNATLARI
# ============================================================================

DISTRICT_COORDS = {
    'DEPO': (40.8225, 29.9213),      # Kocaeli Üniversitesi
    'IZMIT': (40.7656, 29.9406),      # İzmit Merkez
    'GEBZE': (40.8027, 29.4307),      # Gebze Merkez
    'DARICA': (40.7694, 29.3753),     # Darıca Merkez
    'CAYIROVA': (40.8267, 29.3728),   # Çayırova Merkez
    'DILOVASI': (40.7847, 29.5369),   # Dilovası Merkez
    'KORFEZ': (40.7539, 29.7636),     # Körfez Merkez
    'DERINCE': (40.7544, 29.8389),    # Derince Merkez
    'GOLCUK': (40.7175, 29.8306),     # Gölcük Merkez
    'KARAMURSEL': (40.6917, 29.6167), # Karamürsel Merkez
    'KANDIRA': (41.0706, 30.1528),    # Kandıra Merkez
    'KARTEPE': (40.7389, 30.0378),    # Kartepe Merkez
    'BASISKELE': (40.7150, 29.9150),  # Başiskele Merkez
}


# ============================================================================
# İSTASYONLAR ARASI GERÇEK MESAFELER (km)
# Google Maps ve yerel bilgiler referans alınarak hazırlanmıştır
# ============================================================================

# Mesafe matrisi - sadece doğrudan bağlantılı yollar
DIRECT_DISTANCES = {
    # DEPO (Kocaeli Üniversitesi) bağlantıları
    ('DEPO', 'IZMIT'): 8,
    ('DEPO', 'KARTEPE'): 12,
    ('DEPO', 'KANDIRA'): 55,
    
    # İZMİT bağlantıları
    ('IZMIT', 'DERINCE'): 9,
    ('IZMIT', 'BASISKELE'): 10,
    ('IZMIT', 'KARTEPE'): 15,
    
    # DERİNCE bağlantıları
    ('DERINCE', 'KORFEZ'): 8,
    ('DERINCE', 'GOLCUK'): 9,
    
    # KÖRFEZ bağlantıları
    ('KORFEZ', 'DILOVASI'): 18,
    ('KORFEZ', 'KARAMURSEL'): 15,
    
    # DİLOVASI bağlantıları
    ('DILOVASI', 'GEBZE'): 12,
    
    # GEBZE bağlantıları
    ('GEBZE', 'DARICA'): 8,
    ('GEBZE', 'CAYIROVA'): 6,
    
    # DARICA - ÇAYIROVA bağlantısı
    ('DARICA', 'CAYIROVA'): 5,
    
    # BAŞİSKELE bağlantıları  
    ('BASISKELE', 'GOLCUK'): 12,
    ('BASISKELE', 'KARTEPE'): 8,
    
    # GÖLCÜK bağlantıları
    ('GOLCUK', 'KARAMURSEL'): 20,
}

# Çift yönlü mesafe matrisi oluştur
DISTANCE_MATRIX = {}
for (a, b), dist in DIRECT_DISTANCES.items():
    DISTANCE_MATRIX[(a, b)] = dist
    DISTANCE_MATRIX[(b, a)] = dist


# ============================================================================
# KOMŞULUK GRAFİ - Hangi ilçeler doğrudan bağlantılı
# ============================================================================

ADJACENCY_GRAPH = {
    'DEPO': ['IZMIT', 'KARTEPE', 'KANDIRA'],
    'IZMIT': ['DEPO', 'DERINCE', 'BASISKELE', 'KARTEPE'],
    'DERINCE': ['IZMIT', 'KORFEZ', 'GOLCUK'],
    'KORFEZ': ['DERINCE', 'DILOVASI', 'KARAMURSEL'],
    'DILOVASI': ['KORFEZ', 'GEBZE'],
    'GEBZE': ['DILOVASI', 'DARICA', 'CAYIROVA'],
    'DARICA': ['GEBZE', 'CAYIROVA'],
    'CAYIROVA': ['GEBZE', 'DARICA'],
    'BASISKELE': ['IZMIT', 'GOLCUK', 'KARTEPE'],
    'GOLCUK': ['BASISKELE', 'DERINCE', 'KARAMURSEL'],
    'KARAMURSEL': ['GOLCUK', 'KORFEZ'],
    'KANDIRA': ['DEPO'],
    'KARTEPE': ['DEPO', 'IZMIT', 'BASISKELE'],
}


# ============================================================================
# YOL SEGMENTLERİ - Harita çizimi için ara koordinatlar
# ============================================================================

ROAD_SEGMENTS = {
    'DEPO_IZMIT': [
        (40.8225, 29.9213),  # Kocaeli Üniversitesi
        (40.8050, 29.9250),  # Yahya Kaptan
        (40.7850, 29.9320),  # Kozluk
        (40.7656, 29.9406),  # İzmit Merkez
    ],
    'DEPO_KARTEPE': [
        (40.8225, 29.9213),  # Kocaeli Üniversitesi
        (40.8000, 29.9500),  # Arslanbey
        (40.7700, 30.0000),  # Uzunçiftlik
        (40.7389, 30.0378),  # Kartepe
    ],
    'DEPO_KANDIRA': [
        (40.8225, 29.9213),  # Kocaeli Üniversitesi
        (40.8700, 29.9400),  # Sarımeşe
        (40.9350, 30.0000),  # Kışladüzü
        (41.0100, 30.1000),  # Kandıra güney
        (41.0706, 30.1528),  # Kandıra Merkez
    ],
    'IZMIT_DERINCE': [
        (40.7656, 29.9406),  # İzmit
        (40.7620, 29.9150),  # Yahya Kaptan
        (40.7580, 29.8700),  # Yavuz Sultan
        (40.7544, 29.8389),  # Derince
    ],
    'IZMIT_BASISKELE': [
        (40.7656, 29.9406),  # İzmit
        (40.7500, 29.9400),  # Serdar
        (40.7350, 29.9200),  # Kullar
        (40.7244, 29.9097),  # Başiskele
    ],
    'IZMIT_KARTEPE': [
        (40.7656, 29.9406),  # İzmit
        (40.7580, 29.9700),  # Arslanbey
        (40.7460, 30.0100),  # Maşukiye
        (40.7389, 30.0378),  # Kartepe
    ],
    'DERINCE_KORFEZ': [
        (40.7544, 29.8389),  # Derince
        (40.7540, 29.8200),  # Çenedağ
        (40.7539, 29.7636),  # Körfez
    ],
    'DERINCE_GOLCUK': [
        (40.7544, 29.8389),  # Derince
        (40.7400, 29.8380),  # Denizevleri
        (40.7175, 29.8306),  # Gölcük
    ],
    'KORFEZ_DILOVASI': [
        (40.7539, 29.7636),  # Körfez
        (40.7580, 29.7150),  # Hereke
        (40.7680, 29.6600),  # Tavşancıl
        (40.7847, 29.5369),  # Dilovası
    ],
    'KORFEZ_KARAMURSEL': [
        (40.7539, 29.7636),  # Körfez
        (40.7350, 29.7150),  # Hereke Sahil
        (40.7050, 29.6400),  # Ereğli
        (40.6917, 29.6167),  # Karamürsel
    ],
    'DILOVASI_GEBZE': [
        (40.7847, 29.5369),  # Dilovası
        (40.7920, 29.4850),  # Sanayi
        (40.8027, 29.4307),  # Gebze
    ],
    'GEBZE_DARICA': [
        (40.8027, 29.4307),  # Gebze
        (40.7850, 29.4000),  # Fevzi Çakmak
        (40.7694, 29.3753),  # Darıca
    ],
    'GEBZE_CAYIROVA': [
        (40.8027, 29.4307),  # Gebze
        (40.8140, 29.4050),  # Mustafapaşa
        (40.8267, 29.3728),  # Çayırova
    ],
    'DARICA_CAYIROVA': [
        (40.7694, 29.3753),  # Darıca
        (40.7950, 29.3770),  # Bayramoğlu
        (40.8267, 29.3728),  # Çayırova
    ],
    'BASISKELE_GOLCUK': [
        (40.7244, 29.9097),  # Başiskele
        (40.7200, 29.8700),  # Yeniköy
        (40.7175, 29.8306),  # Gölcük
    ],
    'BASISKELE_KARTEPE': [
        (40.7244, 29.9097),  # Başiskele
        (40.7300, 29.9700),  # Ara nokta
        (40.7389, 30.0378),  # Kartepe
    ],
    'GOLCUK_KARAMURSEL': [
        (40.7175, 29.8306),  # Gölcük
        (40.7100, 29.7600),  # Halıdere
        (40.7000, 29.6800),  # Yalakdere
        (40.6917, 29.6167),  # Karamürsel
    ],
}


# ============================================================================
# DİJKSTRA ALGORİTMASI İLE EN KISA YOL
# ============================================================================

class KocaeliRoadNetwork:
    """Kocaeli bölgesi yol ağı - Dijkstra algoritması ile rota hesaplama"""
    
    def __init__(self):
        self.districts = DISTRICT_COORDS
        self.adjacency = ADJACENCY_GRAPH
        self.distances = DISTANCE_MATRIX
        self.segments = ROAD_SEGMENTS
        self._path_cache = {}
        self._all_pairs_distances = {}
        self._precompute_all_paths()
    
    def _precompute_all_paths(self):
        """Tüm çiftler için en kısa yolları önceden hesapla"""
        districts = list(self.districts.keys())
        
        for start in districts:
            distances, predecessors = self._dijkstra(start)
            self._all_pairs_distances[start] = distances
            
            # Her hedefe giden yolları kaydet
            for end in districts:
                if start != end:
                    path = self._reconstruct_path(predecessors, start, end)
                    self._path_cache[(start, end)] = (path, distances.get(end, float('inf')))
    
    def _dijkstra(self, start: str) -> Tuple[Dict[str, float], Dict[str, str]]:
        """Dijkstra algoritması - tek kaynaktan tüm hedeflere en kısa yol"""
        distances = {node: float('inf') for node in self.districts}
        distances[start] = 0
        predecessors = {}
        visited = set()
        
        # Min-heap: (mesafe, düğüm)
        heap = [(0, start)]
        
        while heap:
            current_dist, current = heapq.heappop(heap)
            
            if current in visited:
                continue
            visited.add(current)
            
            # Komşuları kontrol et
            for neighbor in self.adjacency.get(current, []):
                if neighbor in visited:
                    continue
                
                # İki düğüm arası mesafe
                edge_dist = self.distances.get((current, neighbor), float('inf'))
                new_dist = current_dist + edge_dist
                
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    predecessors[neighbor] = current
                    heapq.heappush(heap, (new_dist, neighbor))
        
        return distances, predecessors
    
    def _reconstruct_path(self, predecessors: Dict[str, str], start: str, end: str) -> List[str]:
        """Yolu geri oluştur"""
        if end not in predecessors and end != start:
            return [start, end]  # Doğrudan bağlantı yok, fallback
        
        path = []
        current = end
        while current is not None:
            path.append(current)
            current = predecessors.get(current)
        
        path.reverse()
        
        # Başlangıç noktası yoksa ekle
        if path and path[0] != start:
            path.insert(0, start)
        
        return path
    
    def find_path(self, start_id: str, end_id: str) -> Tuple[List[str], float]:
        """İki ilçe arası en kısa yolu bul"""
        if start_id == end_id:
            return [start_id], 0
        
        # Önbellekte var mı?
        cache_key = (start_id, end_id)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        
        # Hesapla
        distances, predecessors = self._dijkstra(start_id)
        path = self._reconstruct_path(predecessors, start_id, end_id)
        distance = distances.get(end_id, float('inf'))
        
        # Eğer yol bulunamadıysa, kuş uçuşu mesafe * 1.3
        if distance == float('inf'):
            c1 = self.districts.get(start_id)
            c2 = self.districts.get(end_id)
            if c1 and c2:
                distance = haversine_distance(c1[0], c1[1], c2[0], c2[1]) * 1.3
            path = [start_id, end_id]
        
        result = (path, distance)
        self._path_cache[cache_key] = result
        return result
    
    def get_distance(self, start_id: str, end_id: str) -> float:
        """İki ilçe arası mesafe (km)"""
        if start_id == end_id:
            return 0
        
        _, distance = self.find_path(start_id, end_id)
        return distance
    
    def get_path_coordinates(self, start_id: str, end_id: str) -> List[Dict]:
        """İki ilçe arası yol koordinatları (harita çizimi için)"""
        path, _ = self.find_path(start_id, end_id)
        
        all_coords = []
        
        for i in range(len(path) - 1):
            from_id = path[i]
            to_id = path[i + 1]
            
            # Segment anahtarını bul
            segment_key = self._get_segment_key(from_id, to_id)
            
            if segment_key and segment_key in self.segments:
                coords = self.segments[segment_key]
                
                # Ters yönde mi?
                if segment_key.startswith(to_id):
                    coords = list(reversed(coords))
                
                # İlk segment değilse, ilk noktayı atla (duplicate önleme)
                start_idx = 1 if (i > 0 and all_coords) else 0
                
                for lat, lon in coords[start_idx:]:
                    all_coords.append({'lat': lat, 'lng': lon})
            else:
                # Segment yoksa, doğrudan koordinatları ekle
                c1 = self.districts.get(from_id)
                c2 = self.districts.get(to_id)
                if c1 and not all_coords:
                    all_coords.append({'lat': c1[0], 'lng': c1[1]})
                if c2:
                    all_coords.append({'lat': c2[0], 'lng': c2[1]})
        
        return all_coords
    
    def _get_segment_key(self, from_id: str, to_id: str) -> Optional[str]:
        """İki ilçe arası segment anahtarını bul"""
        key1 = f"{from_id}_{to_id}"
        key2 = f"{to_id}_{from_id}"
        
        if key1 in self.segments:
            return key1
        if key2 in self.segments:
            return key2
        return None
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Koordinatlardan mesafe hesapla"""
        start_id = self._find_nearest_district(lat1, lon1)
        end_id = self._find_nearest_district(lat2, lon2)
        
        if start_id == end_id:
            return haversine_distance(lat1, lon1, lat2, lon2)
        
        _, distance = self.find_path(start_id, end_id)
        
        # Başlangıç ve bitiş noktalarına olan ekstra mesafeleri ekle
        start_coord = self.districts[start_id]
        end_coord = self.districts[end_id]
        
        extra_start = haversine_distance(lat1, lon1, start_coord[0], start_coord[1])
        extra_end = haversine_distance(lat2, lon2, end_coord[0], end_coord[1])
        
        return distance + extra_start + extra_end
    
    def _find_nearest_district(self, lat: float, lon: float) -> str:
        """En yakın ilçeyi bul"""
        min_dist = float('inf')
        nearest = 'IZMIT'
        
        for district_id, (d_lat, d_lon) in self.districts.items():
            dist = haversine_distance(lat, lon, d_lat, d_lon)
            if dist < min_dist:
                min_dist = dist
                nearest = district_id
        
        return nearest
    
    def get_district_id_by_name(self, name: str) -> Optional[str]:
        """İlçe adından ID bul"""
        name_map = {
            'Kocaeli Üniversitesi': 'DEPO',
            'İzmit': 'IZMIT',
            'Gebze': 'GEBZE',
            'Darıca': 'DARICA',
            'Çayırova': 'CAYIROVA',
            'Dilovası': 'DILOVASI',
            'Körfez': 'KORFEZ',
            'Derince': 'DERINCE',
            'Gölcük': 'GOLCUK',
            'Karamürsel': 'KARAMURSEL',
            'Kandıra': 'KANDIRA',
            'Kartepe': 'KARTEPE',
            'Başiskele': 'BASISKELE',
        }
        return name_map.get(name)
    
    def get_all_distances_from(self, start_id: str) -> Dict[str, float]:
        """Bir ilçeden tüm ilçelere olan mesafeler"""
        if start_id in self._all_pairs_distances:
            return self._all_pairs_distances[start_id].copy()
        
        distances, _ = self._dijkstra(start_id)
        return distances
    
    def print_distance_matrix(self):
        """Mesafe matrisini yazdır (debug için)"""
        districts = list(self.districts.keys())
        
        # Header
        print(f"{'':12}", end='')
        for d in districts:
            print(f"{d:10}", end='')
        print()
        
        # Rows
        for from_d in districts:
            print(f"{from_d:12}", end='')
            for to_d in districts:
                if from_d == to_d:
                    print(f"{'0':10}", end='')
                else:
                    dist = self.get_distance(from_d, to_d)
                    print(f"{dist:10.1f}", end='')
            print()


# ============================================================================
# GLOBAL FONKSİYONLAR
# ============================================================================

_network = None

def get_network() -> KocaeliRoadNetwork:
    """Singleton network instance"""
    global _network
    if _network is None:
        _network = KocaeliRoadNetwork()
    return _network


def road_distance(coord1: Union[Tuple[float, float], float], 
                  coord2_or_lon1: Union[Tuple[float, float], float] = None,
                  lat2: float = None, 
                  lon2: float = None) -> float:
    """
    İki koordinat arası yol mesafesi (km)
    
    Kullanım:
        road_distance((lat1, lon1), (lat2, lon2))
        veya
        road_distance(lat1, lon1, lat2, lon2)
    """
    network = get_network()
    
    if isinstance(coord1, tuple) and isinstance(coord2_or_lon1, tuple):
        return network.calculate_distance(coord1[0], coord1[1], coord2_or_lon1[0], coord2_or_lon1[1])
    elif lat2 is not None and lon2 is not None:
        return network.calculate_distance(coord1, coord2_or_lon1, lat2, lon2)
    else:
        raise ValueError("Geçersiz parametre formatı")


def get_path_coordinates(start_lat: float, start_lon: float, 
                         end_lat: float, end_lon: float) -> List[Dict]:
    """İki koordinat arası yol koordinatları"""
    network = get_network()
    
    start_id = network._find_nearest_district(start_lat, start_lon)
    end_id = network._find_nearest_district(end_lat, end_lon)
    
    coords = network.get_path_coordinates(start_id, end_id)
    
    if coords:
        if abs(coords[0]['lat'] - start_lat) > 0.001 or abs(coords[0]['lng'] - start_lon) > 0.001:
            coords.insert(0, {'lat': start_lat, 'lng': start_lon})
        
        if abs(coords[-1]['lat'] - end_lat) > 0.001 or abs(coords[-1]['lng'] - end_lon) > 0.001:
            coords.append({'lat': end_lat, 'lng': end_lon})
    else:
        coords = [
            {'lat': start_lat, 'lng': start_lon},
            {'lat': end_lat, 'lng': end_lon}
        ]
    
    return coords


def get_route_coordinates(start_name: str, end_name: str) -> List[Dict]:
    """İki ilçe arası rota koordinatları (harita çizimi için)"""
    network = get_network()
    
    start_id = network.get_district_id_by_name(start_name)
    end_id = network.get_district_id_by_name(end_name)
    
    if not start_id or not end_id:
        return []
    
    return network.get_path_coordinates(start_id, end_id)


def get_district_distance(from_name: str, to_name: str) -> float:
    """İki ilçe arası mesafe (km)"""
    network = get_network()
    
    from_id = network.get_district_id_by_name(from_name)
    to_id = network.get_district_id_by_name(to_name)
    
    if not from_id or not to_id:
        return float('inf')
    
    return network.get_distance(from_id, to_id)


def calculate_route_distance(station_names: List[str]) -> Tuple[float, List[str]]:
    """
    Bir rota için toplam mesafe hesapla
    
    Args:
        station_names: İstasyon adları listesi (sıralı)
    
    Returns:
        (toplam_mesafe, geçilen_ilçeler)
    """
    if len(station_names) < 2:
        return 0, station_names
    
    network = get_network()
    total_distance = 0
    full_path = []
    
    for i in range(len(station_names) - 1):
        from_id = network.get_district_id_by_name(station_names[i])
        to_id = network.get_district_id_by_name(station_names[i + 1])
        
        if from_id and to_id:
            path, distance = network.find_path(from_id, to_id)
            total_distance += distance
            
            # Yolu ekle (ilk segment için tüm yol, sonrakiler için ilk eleman hariç)
            if not full_path:
                full_path.extend(path)
            else:
                full_path.extend(path[1:])
    
    return total_distance, full_path


def calculate_route_with_coordinates(start_coord: Tuple[float, float], 
                                      stop_coords: List[Tuple[float, float]]) -> Dict:
    """
    Birden fazla durak için rota hesapla
    
    Args:
        start_coord: Başlangıç noktası (lat, lon)
        stop_coords: Durak koordinatları listesi [(lat, lon), ...]
    
    Returns:
        Dict: {'distance': float, 'coordinates': List[Dict]}
    """
    if not stop_coords:
        return {'distance': 0, 'coordinates': []}
    
    network = get_network()
    total_distance = 0
    all_coords = []
    
    # Tüm noktaları birleştir: start + stops
    all_points = [start_coord] + stop_coords
    
    for i in range(len(all_points) - 1):
        lat1, lon1 = all_points[i]
        lat2, lon2 = all_points[i + 1]
        
        dist = network.calculate_distance(lat1, lon1, lat2, lon2)
        total_distance += dist
        
        coords = get_path_coordinates(lat1, lon1, lat2, lon2)
        
        if i == 0:
            all_coords.extend(coords)
        else:
            # İlk koordinatı atla (önceki segmentin son koordinatı)
            all_coords.extend(coords[1:] if coords else [])
    
    return {
        'distance': total_distance,
        'coordinates': all_coords
    }


# ============================================================================
# TEST FONKSİYONU
# ============================================================================

def test_network():
    """Yol ağı testi"""
    network = get_network()
    
    print("=" * 70)
    print("KOCAELİ YOL AĞI - DİJKSTRA ALGORİTMASI TESTİ")
    print("=" * 70)
    
    test_routes = [
        ('DEPO', 'IZMIT', 'Kocaeli Üni -> İzmit'),
        ('DEPO', 'GEBZE', 'Kocaeli Üni -> Gebze'),
        ('DEPO', 'DARICA', 'Kocaeli Üni -> Darıca'),
        ('DEPO', 'KANDIRA', 'Kocaeli Üni -> Kandıra'),
        ('GEBZE', 'KARTEPE', 'Gebze -> Kartepe'),
        ('DARICA', 'GOLCUK', 'Darıca -> Gölcük'),
        ('KARAMURSEL', 'CAYIROVA', 'Karamürsel -> Çayırova'),
    ]
    
    for start, end, desc in test_routes:
        path, distance = network.find_path(start, end)
        
        print(f"\n{desc}:")
        print(f"  Güzergah: {' -> '.join(path)}")
        print(f"  Mesafe: {distance:.1f} km")
    
    print("\n" + "=" * 70)
    print("MESAFE MATRİSİ (Tüm ilçeler arası en kısa yollar)")
    print("=" * 70)
    network.print_distance_matrix()


if __name__ == "__main__":
    test_network()
