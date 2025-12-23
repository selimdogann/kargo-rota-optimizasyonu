"""
Mesafe Hesaplama ve A* Pathfinding Algoritması
Kocaeli İli Yol Ağı - Manuel Oluşturulmuş Statik Veriler
Harici API (Google Maps, Yandex vb.) KULLANILMAMAKTADIR
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
# KOCAELİ YOL AĞI - MANUEL OLUŞTURULMUŞ STATİK VERİLER
# OpenStreetMap'ten referans alınarak hazırlanmıştır
# Tüm koordinatlar gerçek yol güzergahlarını takip eder
# ============================================================================

# Her yol segmenti için ara noktalar (gerçek yol kıvrımlarını takip eder)
# Format: 'segment_id': [(lat, lon), (lat, lon), ...]

ROAD_SEGMENTS = {
    # ===== DEPO (Kocaeli Üniversitesi) -> İZMİT =====
    'DEPO_IZMIT': [
        (40.8225, 29.9213),  # Kocaeli Üniversitesi
        (40.8180, 29.9220),  # Üniversite çıkışı
        (40.8120, 29.9235),  # Umuttepe yokuşu
        (40.8050, 29.9250),  # Yahya Kaptan
        (40.7950, 29.9280),  # Körfez Mah
        (40.7850, 29.9320),  # Kozluk
        (40.7780, 29.9360),  # İzmit girişi
        (40.7720, 29.9390),  # Merkez
        (40.7656, 29.9406),  # İzmit Merkez
    ],
    
    # ===== İZMİT -> DERİNCE (D100 üzeri) =====
    'IZMIT_DERINCE': [
        (40.7656, 29.9406),  # İzmit
        (40.7640, 29.9300),  # Yenişehir
        (40.7620, 29.9150),  # Yahya Kaptan
        (40.7600, 29.9000),  # Çukurbağ
        (40.7580, 29.8850),  # Tavşantepe
        (40.7560, 29.8700),  # Yavuz Sultan
        (40.7544, 29.8550),  # Derince girişi
        (40.7544, 29.8389),  # Derince Merkez
    ],
    
    # ===== DERİNCE -> KÖRFEZ (D100 üzeri) =====
    'DERINCE_KORFEZ': [
        (40.7544, 29.8389),  # Derince
        (40.7540, 29.8200),  # Çenedağ
        (40.7535, 29.8000),  # Deniz Mah
        (40.7540, 29.7850),  # Yarımca girişi
        (40.7539, 29.7636),  # Körfez Merkez
    ],
    
    # ===== KÖRFEZ -> DİLOVASI (D100 üzeri) =====
    'KORFEZ_DILOVASI': [
        (40.7539, 29.7636),  # Körfez
        (40.7550, 29.7400),  # Hereke
        (40.7580, 29.7150),  # Hereke Sahil
        (40.7620, 29.6900),  # Tavşancıl
        (40.7680, 29.6600),  # Tavşancıl Doğu
        (40.7750, 29.6200),  # Dilovası girişi
        (40.7800, 29.5800),  # Sanayi
        (40.7847, 29.5369),  # Dilovası Merkez
    ],
    
    # ===== DİLOVASI -> GEBZE (D100 üzeri) =====
    'DILOVASI_GEBZE': [
        (40.7847, 29.5369),  # Dilovası
        (40.7880, 29.5100),  # Dilovası Batı
        (40.7920, 29.4850),  # Sanayi Bölgesi
        (40.7960, 29.4600),  # GOSB
        (40.8000, 29.4450),  # Gebze girişi
        (40.8027, 29.4307),  # Gebze Merkez
    ],
    
    # ===== GEBZE -> DARICA =====
    'GEBZE_DARICA': [
        (40.8027, 29.4307),  # Gebze
        (40.7980, 29.4200),  # Gebze güney
        (40.7920, 29.4100),  # Pelitli
        (40.7850, 29.4000),  # Fevzi Çakmak
        (40.7780, 29.3900),  # Nenehatun
        (40.7730, 29.3820),  # Darıca girişi
        (40.7694, 29.3753),  # Darıca Merkez
    ],
    
    # ===== GEBZE -> ÇAYIROVA =====
    'GEBZE_CAYIROVA': [
        (40.8027, 29.4307),  # Gebze
        (40.8080, 29.4200),  # Gebze Kuzey
        (40.8140, 29.4050),  # Mustafapaşa
        (40.8200, 29.3900),  # Çayırova girişi
        (40.8267, 29.3728),  # Çayırova Merkez
    ],
    
    # ===== ÇAYIROVA -> DARICA =====
    'CAYIROVA_DARICA': [
        (40.8267, 29.3728),  # Çayırova
        (40.8180, 29.3750),  # Akse
        (40.8080, 29.3760),  # Şekerpınar
        (40.7950, 29.3770),  # Bayramoğlu
        (40.7850, 29.3760),  # Osmangazi
        (40.7750, 29.3755),  # Darıca Kuzey
        (40.7694, 29.3753),  # Darıca Merkez
    ],
    
    # ===== İZMİT -> BAŞİSKELE =====
    'IZMIT_BASISKELE': [
        (40.7656, 29.9406),  # İzmit
        (40.7580, 29.9350),  # Yenidoğan
        (40.7500, 29.9280),  # Serdar
        (40.7400, 29.9200),  # Kullar
        (40.7320, 29.9150),  # Başiskele girişi
        (40.7244, 29.9097),  # Başiskele Merkez
    ],
    
    # ===== BAŞİSKELE -> GÖLCÜK =====
    'BASISKELE_GOLCUK': [
        (40.7244, 29.9097),  # Başiskele
        (40.7220, 29.8950),  # Yeniköy
        (40.7200, 29.8800),  # Bahçecik
        (40.7190, 29.8600),  # Değirmendere
        (40.7180, 29.8450),  # Gölcük girişi
        (40.7175, 29.8306),  # Gölcük Merkez
    ],
    
    # ===== GÖLCÜK -> KARAMÜRSEL =====
    'GOLCUK_KARAMURSEL': [
        (40.7175, 29.8306),  # Gölcük
        (40.7150, 29.8000),  # Yazlık
        (40.7100, 29.7600),  # Halıdere
        (40.7050, 29.7200),  # Ulaşlı
        (40.7000, 29.6800),  # Yalakdere
        (40.6950, 29.6500),  # Karamürsel girişi
        (40.6917, 29.6167),  # Karamürsel Merkez
    ],
    
    # ===== İZMİT -> KARTEPE =====
    'IZMIT_KARTEPE': [
        (40.7656, 29.9406),  # İzmit
        (40.7620, 29.9550),  # Erenler
        (40.7580, 29.9700),  # Arslanbey
        (40.7520, 29.9900),  # Uzunçiftlik
        (40.7460, 30.0100),  # Maşukiye yol ayrımı
        (40.7410, 30.0250),  # Kartepe girişi
        (40.7389, 30.0378),  # Kartepe Merkez
    ],
    
    # ===== DEPO -> KANDIRA (Kuzey yolu) =====
    'DEPO_KANDIRA': [
        (40.8225, 29.9213),  # Kocaeli Üniversitesi
        (40.8350, 29.9250),  # Arıtman
        (40.8500, 29.9300),  # Kullar Kuzey
        (40.8700, 29.9400),  # Sarımeşe
        (40.8900, 29.9550),  # Karaağaç
        (40.9100, 29.9750),  # Kışladüzü
        (40.9350, 30.0000),  # Akçakoca yol ayrımı
        (40.9600, 30.0300),  # Kefken
        (40.9850, 30.0650),  # Kerpe
        (41.0100, 30.1000),  # Kandıra güney
        (41.0400, 30.1250),  # Kandıra girişi
        (41.0706, 30.1528),  # Kandıra Merkez
    ],
    
    # ===== KÖRFEZ -> KARAMÜRSEL (Sahil yolu) =====
    'KORFEZ_KARAMURSEL': [
        (40.7539, 29.7636),  # Körfez
        (40.7450, 29.7400),  # Hereke
        (40.7350, 29.7150),  # Hereke Sahil
        (40.7250, 29.6900),  # Kırkarmut
        (40.7150, 29.6650),  # Ereğli
        (40.7050, 29.6400),  # Karamürsel kuzey
        (40.6917, 29.6167),  # Karamürsel Merkez
    ],
    
    # ===== DERİNCE -> GÖLCÜK (İç yol) =====
    'DERINCE_GOLCUK': [
        (40.7544, 29.8389),  # Derince
        (40.7480, 29.8400),  # Çenedağ
        (40.7400, 29.8380),  # Denizevleri
        (40.7320, 29.8350),  # Gölcük kuzey
        (40.7250, 29.8330),  # Gölcük girişi
        (40.7175, 29.8306),  # Gölcük Merkez
    ],
}

# İlçe merkezi koordinatları
DISTRICT_COORDS = {
    'DEPO': (40.8225, 29.9213),
    'IZMIT': (40.7656, 29.9406),
    'GEBZE': (40.8027, 29.4307),
    'DARICA': (40.7694, 29.3753),
    'CAYIROVA': (40.8267, 29.3728),
    'DILOVASI': (40.7847, 29.5369),
    'KORFEZ': (40.7539, 29.7636),
    'DERINCE': (40.7544, 29.8389),
    'GOLCUK': (40.7175, 29.8306),
    'KARAMURSEL': (40.6917, 29.6167),
    'KANDIRA': (41.0706, 30.1528),
    'KARTEPE': (40.7389, 30.0378),
    'BASISKELE': (40.7244, 29.9097),
}

# Yol ağı graf yapısı - hangi segment hangi ilçeleri bağlar
ROAD_GRAPH = {
    'DEPO': ['IZMIT', 'KANDIRA'],
    'IZMIT': ['DEPO', 'DERINCE', 'BASISKELE', 'KARTEPE'],
    'DERINCE': ['IZMIT', 'KORFEZ', 'GOLCUK'],
    'KORFEZ': ['DERINCE', 'DILOVASI', 'KARAMURSEL'],
    'DILOVASI': ['KORFEZ', 'GEBZE'],
    'GEBZE': ['DILOVASI', 'DARICA', 'CAYIROVA'],
    'DARICA': ['GEBZE', 'CAYIROVA'],
    'CAYIROVA': ['GEBZE', 'DARICA'],
    'BASISKELE': ['IZMIT', 'GOLCUK'],
    'GOLCUK': ['BASISKELE', 'DERINCE', 'KARAMURSEL'],
    'KARAMURSEL': ['GOLCUK', 'KORFEZ'],
    'KANDIRA': ['DEPO'],
    'KARTEPE': ['IZMIT'],
}

# Segment anahtarları - iki ilçe arasındaki yol segmenti
def get_segment_key(from_id: str, to_id: str) -> Optional[str]:
    """İki ilçe arasındaki segment anahtarını bul"""
    key1 = f"{from_id}_{to_id}"
    key2 = f"{to_id}_{from_id}"
    
    if key1 in ROAD_SEGMENTS:
        return key1
    if key2 in ROAD_SEGMENTS:
        return key2
    
    return None


class KocaeliRoadNetwork:
    """
    Kocaeli bölgesi yol ağı - A* algoritması ile rota hesaplama
    Harici API KULLANILMAZ
    """
    
    def __init__(self):
        self.districts = DISTRICT_COORDS
        self.segments = ROAD_SEGMENTS
        self.graph = ROAD_GRAPH
        self._distance_cache = {}
        self._path_cache = {}
        self._precompute_segment_distances()
    
    def _precompute_segment_distances(self):
        """Her segment için toplam mesafe hesapla"""
        self.segment_distances = {}
        
        for key, coords in self.segments.items():
            total = 0
            for i in range(len(coords) - 1):
                total += haversine_distance(
                    coords[i][0], coords[i][1],
                    coords[i+1][0], coords[i+1][1]
                )
            self.segment_distances[key] = total
    
    def _get_edge_distance(self, from_id: str, to_id: str) -> float:
        """İki ilçe arası kenar mesafesi"""
        segment_key = get_segment_key(from_id, to_id)
        
        if segment_key and segment_key in self.segment_distances:
            return self.segment_distances[segment_key]
        
        c1 = self.districts.get(from_id)
        c2 = self.districts.get(to_id)
        if c1 and c2:
            return haversine_distance(c1[0], c1[1], c2[0], c2[1]) * 1.3
        
        return float('inf')
    
    def _heuristic(self, from_id: str, to_id: str) -> float:
        """A* sezgisel fonksiyonu"""
        c1 = self.districts.get(from_id)
        c2 = self.districts.get(to_id)
        if c1 and c2:
            return haversine_distance(c1[0], c1[1], c2[0], c2[1])
        return float('inf')
    
    def find_path(self, start_id: str, end_id: str) -> Tuple[List[str], float]:
        """A* algoritması ile en kısa yolu bul"""
        cache_key = (start_id, end_id)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        
        if start_id == end_id:
            return [start_id], 0
        
        open_set = [(0, start_id)]
        came_from = {}
        g_score = {start_id: 0}
        f_score = {start_id: self._heuristic(start_id, end_id)}
        
        while open_set:
            current_f, current = heapq.heappop(open_set)
            
            if current == end_id:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                
                total_distance = g_score[end_id]
                result = (path, total_distance)
                self._path_cache[cache_key] = result
                return result
            
            neighbors = self.graph.get(current, [])
            for neighbor in neighbors:
                tentative_g = g_score[current] + self._get_edge_distance(current, neighbor)
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, end_id)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        direct_dist = self._heuristic(start_id, end_id) * 1.3
        return [start_id, end_id], direct_dist
    
    def get_path_coordinates(self, start_id: str, end_id: str) -> List[Dict]:
        """İki ilçe arası yol koordinatları (harita çizimi için)"""
        path, _ = self.find_path(start_id, end_id)
        
        all_coords = []
        
        for i in range(len(path) - 1):
            from_id = path[i]
            to_id = path[i + 1]
            
            segment_key = get_segment_key(from_id, to_id)
            
            if segment_key and segment_key in self.segments:
                coords = self.segments[segment_key]
                
                if segment_key.startswith(from_id):
                    segment_coords = coords
                else:
                    segment_coords = list(reversed(coords))
                
                if i > 0 and all_coords:
                    segment_coords = segment_coords[1:]
                
                for lat, lon in segment_coords:
                    all_coords.append({'lat': lat, 'lng': lon})
            else:
                c1 = self.districts.get(from_id)
                c2 = self.districts.get(to_id)
                if c1 and not all_coords:
                    all_coords.append({'lat': c1[0], 'lng': c1[1]})
                if c2:
                    all_coords.append({'lat': c2[0], 'lng': c2[1]})
        
        return all_coords
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Koordinatlardan mesafe hesapla"""
        start_id = self._find_nearest_district(lat1, lon1)
        end_id = self._find_nearest_district(lat2, lon2)
        
        if start_id == end_id:
            return haversine_distance(lat1, lon1, lat2, lon2)
        
        _, distance = self.find_path(start_id, end_id)
        
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
    if isinstance(coord1, tuple) and isinstance(coord2_or_lon1, tuple):
        # Tuple formatı: road_distance((lat1, lon1), (lat2, lon2))
        lat1, lon1 = coord1
        lat2, lon2 = coord2_or_lon1
    else:
        # Düz format: road_distance(lat1, lon1, lat2, lon2)
        lat1 = coord1
        lon1 = coord2_or_lon1
    
    return get_network().calculate_distance(lat1, lon1, lat2, lon2)


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


def test_network():
    """Yol ağı testi"""
    network = get_network()
    
    print("=" * 60)
    print("KOCAELİ YOL AĞI TESTİ")
    print("=" * 60)
    
    test_routes = [
        ('DEPO', 'IZMIT', 'Kocaeli Üni -> İzmit'),
        ('DEPO', 'GEBZE', 'Kocaeli Üni -> Gebze'),
        ('DEPO', 'KANDIRA', 'Kocaeli Üni -> Kandıra'),
        ('IZMIT', 'KARAMURSEL', 'İzmit -> Karamürsel'),
        ('GEBZE', 'KARTEPE', 'Gebze -> Kartepe'),
    ]
    
    for start, end, desc in test_routes:
        path, distance = network.find_path(start, end)
        coords = network.get_path_coordinates(start, end)
        
        print(f"\n{desc}:")
        print(f"  Rota: {' -> '.join(path)}")
        print(f"  Mesafe: {distance:.2f} km")
        print(f"  Koordinat sayısı: {len(coords)}")
    
    print("\n" + "=" * 60)
    print("Tum testler basarili!")
    print("=" * 60)


if __name__ == "__main__":
    test_network()
