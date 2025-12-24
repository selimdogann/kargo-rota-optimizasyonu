"""
Genetik Algoritma ile CVRP (Capacitated Vehicle Routing Problem) Çözümü

SENARYO: Kocaeli ilçelerinden Kocaeli Üniversitesi'ne kargo toplama (TEK YÖNLÜ)
- Araçlar ilçelerden kargoları toplar
- Kocaeli Üniversitesi'ne (depo) getirir
- Tek yönlü rota: İlçe(ler) → Üniversite

OPTİMİZASYON:
- Coğrafi kümeleme ile yakın ilçeler aynı araca atanır
- Uzak ilçeler farklı araçlara dağıtılır (Darıca-Karamürsel gibi)
- Her ilçe için ayrı araç kullanmak daha mantıklı olabilir
"""

import random
import math
from typing import List, Dict, Tuple, Set
import copy


class GeneticAlgorithmCVRP:
    """
    Kapasite Kısıtlı Araç Rotalama Problemi için Genetik Algoritma
    Kargo Toplama Senaryosu: İlçelerden Üniversite'ye
    
    YENİ ÖZELLİKLER:
    - Coğrafi kümeleme (uzak ilçeler farklı araçlara)
    - Mesafe bazlı ceza sistemi
    - Akıllı araç dağıtımı
    """
    
    def __init__(
        self,
        stations: List,
        vehicles: List,
        cargos: List,
        depot,
        distance_matrix: Dict,
        population_size: int = 150,
        generations: int = 300,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.85,
        elite_size: int = 15,
        max_route_distance: float = 60.0  # Maksimum rota mesafesi (km)
    ):
        """
        Args:
            stations: İstasyon listesi (ilçeler)
            vehicles: Araç listesi  
            cargos: Kargo listesi (ilçelerden üniversiteye)
            depot: Depo istasyonu (Kocaeli Üniversitesi)
            distance_matrix: İstasyonlar arası mesafe matrisi
            population_size: Popülasyon büyüklüğü
            generations: Nesil sayısı
            mutation_rate: Mutasyon oranı
            crossover_rate: Çaprazlama oranı
            elite_size: Seçkinlik boyutu
            max_route_distance: Bir rotadaki maksimum toplam mesafe
        """
        self.stations = stations
        self.vehicles = vehicles
        self.cargos = cargos
        self.depot = depot
        self.distance_matrix = distance_matrix
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = elite_size
        self.max_route_distance = max_route_distance
        
        # Kargo KAYNAK istasyonlarını belirle (ilçeler - kargonun toplandığı yerler)
        self.pickup_stations = list(set(c.source_station for c in cargos))
        
        # Her istasyon için toplam kargo ağırlığını hesapla (kaynak istasyona göre)
        self.station_weights = {}
        for station in self.pickup_stations:
            total_weight = sum(c.weight for c in cargos if c.source_station_id == station.id)
            self.station_weights[station.id] = total_weight
        
        # İstasyonların depoya olan mesafelerini önceden hesapla
        self.depot_distances = {}
        for station in self.pickup_stations:
            self.depot_distances[station.id] = self.calculate_distance(station, self.depot)
        
        # İstasyonlar arası mesafeleri önceden hesapla
        self.station_distances = {}
        for s1 in self.pickup_stations:
            for s2 in self.pickup_stations:
                if s1.id != s2.id:
                    key = (s1.id, s2.id)
                    self.station_distances[key] = self.calculate_distance(s1, s2)
    
    def calculate_distance(self, station1, station2) -> float:
        """İki istasyon arası mesafeyi hesapla"""
        key = f"{station1.id}_{station2.id}"
        if key in self.distance_matrix:
            return self.distance_matrix[key]
        
        # Eğer matrise yoksa Haversine formülü ile hesapla
        return self._haversine_distance(
            station1.latitude, station1.longitude,
            station2.latitude, station2.longitude
        )
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine formülü ile iki nokta arası mesafe (km)"""
        R = 6371  # Dünya yarıçapı (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # Yol mesafesi için kuş uçuşu mesafesini 1.3 ile çarp (gerçekçi yol faktörü)
        return R * c * 1.3
    
    def calculate_route_distance(self, route: List) -> float:
        """
        Bir rotanın toplam mesafesini hesapla (TEK YÖNLÜ)
        Rota: İlçe(ler) → Üniversite (depo)
        """
        if not route:
            return 0
        
        total_distance = 0
        
        # İlçeler arası mesafe
        for i in range(len(route) - 1):
            total_distance += self.calculate_distance(route[i], route[i+1])
        
        # Son ilçeden depoya (Üniversite'ye) gidiş
        total_distance += self.calculate_distance(route[-1], self.depot)
        
        return total_distance
    
    def calculate_route_cost(self, vehicle, route: List) -> float:
        """Bir rotanın toplam maliyetini hesapla"""
        if not route:
            return 0
        distance = self.calculate_route_distance(route)
        fuel_cost = distance * vehicle.cost_per_km
        rental_cost = vehicle.rental_cost if vehicle.is_rental else 0
        return fuel_cost + rental_cost
    
    def calculate_route_weight(self, route: List) -> float:
        """Bir rotadaki toplam kargo ağırlığını hesapla"""
        return sum(self.station_weights.get(s.id, 0) for s in route)
    
    def is_route_valid(self, vehicle, route: List) -> bool:
        """Rotanın araç kapasitesine uygun olup olmadığını kontrol et"""
        return self.calculate_route_weight(route) <= vehicle.capacity
    
    def get_geographical_clusters(self) -> List[List]:
        """
        İstasyonları coğrafi konumlarına göre kümele
        Birbirine yakın ilçeler aynı kümeye girer
        """
        if not self.pickup_stations:
            return []
        
        # Her istasyonu depoya olan mesafesine göre sırala
        sorted_stations = sorted(
            self.pickup_stations,
            key=lambda s: self.depot_distances.get(s.id, 0)
        )
        
        clusters = []
        used = set()
        
        for station in sorted_stations:
            if station.id in used:
                continue
            
            # Yeni küme başlat
            cluster = [station]
            used.add(station.id)
            
            # Bu istasyona yakın diğer istasyonları bul
            for other in sorted_stations:
                if other.id in used:
                    continue
                
                # İki istasyon arası mesafe
                dist = self.station_distances.get((station.id, other.id), float('inf'))
                
                # Eğer mesafe 20 km'den az ise aynı kümeye ekle
                if dist < 20:
                    # Kümedeki toplam ağırlık araç kapasitesini aşmamalı
                    cluster_weight = sum(self.station_weights.get(s.id, 0) for s in cluster)
                    station_weight = self.station_weights.get(other.id, 0)
                    
                    max_capacity = max(v.capacity for v in self.vehicles)
                    if cluster_weight + station_weight <= max_capacity:
                        cluster.append(other)
                        used.add(other.id)
            
            clusters.append(cluster)
        
        return clusters
    
    def create_individual_smart(self) -> Dict:
        """
        Akıllı birey oluşturma - coğrafi kümeleme kullanarak
        Uzak ilçeler farklı araçlara atanır
        """
        individual = {v.id: [] for v in self.vehicles}
        
        # Coğrafi kümeleri al
        clusters = self.get_geographical_clusters()
        
        # Her kümeyi bir araca ata
        vehicle_idx = 0
        for cluster in clusters:
            if vehicle_idx >= len(self.vehicles):
                vehicle_idx = 0
            
            vehicle = self.vehicles[vehicle_idx]
            
            # Kümedeki toplam ağırlık
            cluster_weight = sum(self.station_weights.get(s.id, 0) for s in cluster)
            
            # Mevcut araç kapasitesini kontrol et
            current_weight = self.calculate_route_weight(individual[vehicle.id])
            
            if current_weight + cluster_weight <= vehicle.capacity:
                individual[vehicle.id].extend(cluster)
            else:
                # Başka uygun araç bul
                for v in self.vehicles:
                    v_weight = self.calculate_route_weight(individual[v.id])
                    if v_weight + cluster_weight <= v.capacity:
                        individual[v.id].extend(cluster)
                        break
                else:
                    # Uygun araç yoksa en az yüklü araca ekle
                    min_v = min(self.vehicles, key=lambda v: self.calculate_route_weight(individual[v.id]))
                    individual[min_v.id].extend(cluster)
            
            vehicle_idx += 1
        
        return individual
    
    def create_individual_single_station(self) -> Dict:
        """
        Her istasyonu ayrı araca ata
        Bu yaklaşım uzak istasyonlar için daha iyi sonuç verebilir
        """
        individual = {v.id: [] for v in self.vehicles}
        
        # İstasyonları depoya olan mesafeye göre sırala
        sorted_stations = sorted(
            self.pickup_stations,
            key=lambda s: self.depot_distances.get(s.id, 0)
        )
        
        vehicle_idx = 0
        for station in sorted_stations:
            if vehicle_idx >= len(self.vehicles):
                vehicle_idx = 0
            
            vehicle = self.vehicles[vehicle_idx]
            station_weight = self.station_weights.get(station.id, 0)
            current_weight = self.calculate_route_weight(individual[vehicle.id])
            
            if current_weight + station_weight <= vehicle.capacity:
                individual[vehicle.id].append(station)
            else:
                # Başka uygun araç bul
                for v in self.vehicles:
                    v_weight = self.calculate_route_weight(individual[v.id])
                    if v_weight + station_weight <= v.capacity:
                        individual[v.id].append(station)
                        break
            
            vehicle_idx += 1
        
        return individual
    
    def create_individual(self) -> Dict:
        """Karışık strateji ile birey oluştur"""
        r = random.random()
        if r < 0.4:
            return self.create_individual_smart()
        elif r < 0.7:
            return self.create_individual_single_station()
        else:
            return self.create_individual_random()
    
    def create_individual_random(self) -> Dict:
        """Rastgele bir birey (çözüm) oluştur"""
        stations_to_assign = self.pickup_stations.copy()
        random.shuffle(stations_to_assign)
        
        individual = {v.id: [] for v in self.vehicles}
        
        for station in stations_to_assign:
            station_weight = self.station_weights.get(station.id, 0)
            
            available_vehicles = [
                v for v in self.vehicles 
                if self.calculate_route_weight(individual[v.id]) + station_weight <= v.capacity
            ]
            
            if available_vehicles:
                selected_vehicle = random.choice(available_vehicles)
                individual[selected_vehicle.id].append(station)
            else:
                min_weight_vehicle = min(
                    self.vehicles,
                    key=lambda v: self.calculate_route_weight(individual[v.id])
                )
                individual[min_weight_vehicle.id].append(station)
        
        return individual
    
    def calculate_fitness(self, individual: Dict) -> float:
        """
        Bireyin uygunluk değerini hesapla
        
        CEZA SİSTEMİ:
        1. Kapasite aşımı cezası
        2. Uzun rota cezası (ilçeler arası mesafe fazla ise)
        3. Verimsiz rota cezası (tek istasyon için uzun yol)
        """
        total_cost = 0
        penalty = 0
        
        for vehicle in self.vehicles:
            route = individual[vehicle.id]
            if not route:
                continue
            
            # Rota maliyeti
            route_cost = self.calculate_route_cost(vehicle, route)
            total_cost += route_cost
            
            # Kapasite aşımı cezası
            route_weight = self.calculate_route_weight(route)
            if route_weight > vehicle.capacity:
                penalty += (route_weight - vehicle.capacity) * 100
            
            # UZUN ROTA CEZASI
            # Eğer rotada birden fazla istasyon varsa ve aralarındaki mesafe çok fazlaysa ceza ver
            if len(route) > 1:
                for i in range(len(route) - 1):
                    inter_station_dist = self.station_distances.get(
                        (route[i].id, route[i+1].id), 
                        self.calculate_distance(route[i], route[i+1])
                    )
                    # 25 km'den uzak istasyonlar aynı rotada olmamalı
                    if inter_station_dist > 25:
                        penalty += inter_station_dist * 5  # Mesafe bazlı ceza
            
            # VERİMSİZLİK CEZASI
            # Toplam rota mesafesi çok uzunsa ceza ver
            route_distance = self.calculate_route_distance(route)
            if route_distance > self.max_route_distance:
                penalty += (route_distance - self.max_route_distance) * 3
        
        # Uygunluk = 1 / (maliyet + ceza)
        return 1.0 / (total_cost + penalty + 1)
    
    def tournament_selection(self, population: List, fitness_scores: List, tournament_size: int = 5) -> Dict:
        """Turnuva seçimi ile ebeveyn seç"""
        tournament_indices = random.sample(range(len(population)), min(tournament_size, len(population)))
        best_index = max(tournament_indices, key=lambda i: fitness_scores[i])
        return copy.deepcopy(population[best_index])
    
    def crossover(self, parent1: Dict, parent2: Dict) -> Tuple[Dict, Dict]:
        """İki ebeveynden çaprazlama ile çocuklar oluştur"""
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)
        
        child1 = {v.id: [] for v in self.vehicles}
        child2 = {v.id: [] for v in self.vehicles}
        
        all_stations_p1 = []
        all_stations_p2 = []
        
        for v in self.vehicles:
            all_stations_p1.extend(parent1[v.id])
            all_stations_p2.extend(parent2[v.id])
        
        if all_stations_p1 and all_stations_p2:
            crossover_point = random.randint(1, max(1, len(all_stations_p1) - 1))
            
            used_stations = set()
            stations_for_child1 = all_stations_p1[:crossover_point]
            used_stations.update(s.id for s in stations_for_child1)
            
            for s in all_stations_p2:
                if s.id not in used_stations:
                    stations_for_child1.append(s)
                    used_stations.add(s.id)
            
            used_stations = set()
            stations_for_child2 = all_stations_p2[:crossover_point]
            used_stations.update(s.id for s in stations_for_child2)
            
            for s in all_stations_p1:
                if s.id not in used_stations:
                    stations_for_child2.append(s)
                    used_stations.add(s.id)
            
            child1 = self._distribute_stations_smart(stations_for_child1)
            child2 = self._distribute_stations_smart(stations_for_child2)
        
        return child1, child2
    
    def _distribute_stations_smart(self, stations: List) -> Dict:
        """İstasyonları akıllı şekilde araçlara dağıt"""
        result = {v.id: [] for v in self.vehicles}
        
        # İstasyonları depoya olan mesafeye göre sırala
        sorted_stations = sorted(
            stations,
            key=lambda s: self.depot_distances.get(s.id, 0)
        )
        
        for station in sorted_stations:
            station_weight = self.station_weights.get(station.id, 0)
            best_vehicle = None
            best_score = float('inf')
            
            for v in self.vehicles:
                current_weight = self.calculate_route_weight(result[v.id])
                if current_weight + station_weight > v.capacity:
                    continue
                
                # Skor hesapla: Bu istasyonu bu araca eklemenin maliyeti
                if result[v.id]:
                    # Mevcut rotadaki son istasyondan bu istasyona mesafe
                    last_station = result[v.id][-1]
                    extra_dist = self.station_distances.get(
                        (last_station.id, station.id),
                        self.calculate_distance(last_station, station)
                    )
                    score = extra_dist
                else:
                    # Boş araç - sadece depoya mesafe
                    score = self.depot_distances.get(station.id, 0)
                
                if score < best_score:
                    best_score = score
                    best_vehicle = v
            
            if best_vehicle:
                result[best_vehicle.id].append(station)
            else:
                # Kapasiteye uygun araç yoksa en az yüklü araca ekle
                min_v = min(self.vehicles, key=lambda v: self.calculate_route_weight(result[v.id]))
                result[min_v.id].append(station)
        
        return result
    
    def mutate(self, individual: Dict) -> Dict:
        """Mutasyon uygula"""
        if random.random() > self.mutation_rate:
            return individual
        
        mutated = copy.deepcopy(individual)
        mutation_type = random.choice(['swap', 'move', 'reverse', 'split'])
        
        if mutation_type == 'swap':
            vehicles_with_stations = [v for v in self.vehicles if mutated[v.id]]
            if len(vehicles_with_stations) >= 2:
                v1, v2 = random.sample(vehicles_with_stations, 2)
                if mutated[v1.id] and mutated[v2.id]:
                    idx1 = random.randint(0, len(mutated[v1.id]) - 1)
                    idx2 = random.randint(0, len(mutated[v2.id]) - 1)
                    mutated[v1.id][idx1], mutated[v2.id][idx2] = mutated[v2.id][idx2], mutated[v1.id][idx1]
        
        elif mutation_type == 'move':
            vehicles_with_stations = [v for v in self.vehicles if mutated[v.id]]
            if vehicles_with_stations:
                source_vehicle = random.choice(vehicles_with_stations)
                target_vehicle = random.choice(self.vehicles)
                if mutated[source_vehicle.id]:
                    station = mutated[source_vehicle.id].pop(
                        random.randint(0, len(mutated[source_vehicle.id]) - 1)
                    )
                    mutated[target_vehicle.id].append(station)
        
        elif mutation_type == 'reverse':
            vehicles_with_stations = [v for v in self.vehicles if len(mutated[v.id]) > 1]
            if vehicles_with_stations:
                vehicle = random.choice(vehicles_with_stations)
                mutated[vehicle.id].reverse()
        
        elif mutation_type == 'split':
            # Uzun rotayı böl - yeni mutasyon tipi
            vehicles_with_long_routes = [
                v for v in self.vehicles 
                if len(mutated[v.id]) > 1 and self.calculate_route_distance(mutated[v.id]) > self.max_route_distance
            ]
            if vehicles_with_long_routes:
                vehicle = random.choice(vehicles_with_long_routes)
                # Rastgele bir istasyonu başka araca taşı
                if len(mutated[vehicle.id]) > 1:
                    station = mutated[vehicle.id].pop(random.randint(0, len(mutated[vehicle.id]) - 1))
                    # Boş veya az yüklü araç bul
                    empty_vehicles = [v for v in self.vehicles if not mutated[v.id]]
                    if empty_vehicles:
                        mutated[random.choice(empty_vehicles).id].append(station)
                    else:
                        min_v = min(self.vehicles, key=lambda v: self.calculate_route_weight(mutated[v.id]))
                        mutated[min_v.id].append(station)
        
        return mutated
    
    def optimize_route_order(self, route: List) -> List:
        """2-opt algoritması ile rota sırasını optimize et"""
        if len(route) <= 2:
            return route
        
        improved = True
        best_route = route.copy()
        best_distance = self.calculate_route_distance(best_route)
        
        iterations = 0
        max_iterations = 100
        
        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            
            for i in range(len(best_route) - 1):
                for j in range(i + 2, len(best_route)):
                    new_route = best_route[:i+1] + best_route[i+1:j+1][::-1] + best_route[j+1:]
                    new_distance = self.calculate_route_distance(new_route)
                    
                    if new_distance < best_distance:
                        best_route = new_route
                        best_distance = new_distance
                        improved = True
        
        return best_route
    
    def run(self) -> Tuple[Dict, float]:
        """Genetik algoritmayı çalıştır"""
        # Başlangıç popülasyonunu oluştur
        population = [self.create_individual() for _ in range(self.population_size)]
        
        best_solution = None
        best_cost = float('inf')
        no_improvement_count = 0
        
        for generation in range(self.generations):
            fitness_scores = [self.calculate_fitness(ind) for ind in population]
            
            best_idx = max(range(len(population)), key=lambda i: fitness_scores[i])
            current_cost = sum(
                self.calculate_route_cost(v, population[best_idx][v.id])
                for v in self.vehicles
            )
            
            if current_cost < best_cost:
                best_cost = current_cost
                best_solution = copy.deepcopy(population[best_idx])
                no_improvement_count = 0
            else:
                no_improvement_count += 1
            
            # Erken durma - 50 nesil iyileşme yoksa dur
            if no_improvement_count > 50:
                break
            
            new_population = []
            
            elite_indices = sorted(
                range(len(population)),
                key=lambda i: fitness_scores[i],
                reverse=True
            )[:self.elite_size]
            
            for idx in elite_indices:
                new_population.append(copy.deepcopy(population[idx]))
            
            while len(new_population) < self.population_size:
                parent1 = self.tournament_selection(population, fitness_scores)
                parent2 = self.tournament_selection(population, fitness_scores)
                
                child1, child2 = self.crossover(parent1, parent2)
                child1 = self.mutate(child1)
                child2 = self.mutate(child2)
                
                new_population.append(child1)
                if len(new_population) < self.population_size:
                    new_population.append(child2)
            
            population = new_population
        
        # En iyi çözümdeki rotaları optimize et
        if best_solution:
            for vehicle in self.vehicles:
                if best_solution[vehicle.id]:
                    best_solution[vehicle.id] = self.optimize_route_order(best_solution[vehicle.id])
            
            best_cost = sum(
                self.calculate_route_cost(v, best_solution[v.id])
                for v in self.vehicles
            )
        
        return best_solution, best_cost


class KnapsackOptimizer:
    """
    Dinamik Programlama ile Knapsack (Sırt Çantası) Optimizasyonu
    Araç kapasitesi aşıldığında hangi kargoların taşınacağını belirler
    """
    
    def __init__(self, capacity: float, cargos: List):
        self.capacity = int(capacity)
        self.cargos = cargos
    
    def optimize(self) -> Tuple[List, float]:
        n = len(self.cargos)
        W = self.capacity
        
        values = [c.weight for c in self.cargos]
        weights = [int(c.weight) for c in self.cargos]
        
        dp = [[0 for _ in range(W + 1)] for _ in range(n + 1)]
        
        for i in range(1, n + 1):
            for w in range(W + 1):
                if weights[i-1] <= w:
                    dp[i][w] = max(
                        values[i-1] + dp[i-1][w - weights[i-1]],
                        dp[i-1][w]
                    )
                else:
                    dp[i][w] = dp[i-1][w]
        
        selected_cargos = []
        w = W
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i-1][w]:
                selected_cargos.append(self.cargos[i-1])
                w -= weights[i-1]
        
        return selected_cargos, dp[n][W]
