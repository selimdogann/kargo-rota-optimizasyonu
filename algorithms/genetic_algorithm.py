"""
Genetik Algoritma ile CVRP (Capacitated Vehicle Routing Problem) Çözümü

SENARYO: Kocaeli ilçelerinden Kocaeli Üniversitesi'ne kargo toplama
- Araçlar Üniversite'den (depo) çıkar
- İlçelere gider ve kargoları toplar
- Üniversite'ye geri döner

İKİ PROBLEM:
1. Sınırsız Araç: Minimum maliyetle tüm kargoları taşı (gerekirse araç kirala)
2. Belirli Araç: Sabit araçlarla maksimum kargo (sayı veya ağırlık)
"""

import random
import math
from typing import List, Dict, Tuple
import copy


class GeneticAlgorithmCVRP:
    """
    Kapasite Kısıtlı Araç Rotalama Problemi için Genetik Algoritma
    Kargo Toplama Senaryosu: İlçelerden Üniversite'ye
    """
    
    def __init__(
        self,
        stations: List,
        vehicles: List,
        cargos: List,
        depot,
        distance_matrix: Dict,
        population_size: int = 100,
        generations: int = 500,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.8,
        elite_size: int = 10
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
        
        # Kargo KAYNAK istasyonlarını belirle (ilçeler - kargonun toplandığı yerler)
        self.pickup_stations = list(set(c.source_station for c in cargos))
        
        # Her istasyon için toplam kargo ağırlığını hesapla (kaynak istasyona göre)
        self.station_weights = {}
        for station in self.pickup_stations:
            total_weight = sum(c.weight for c in cargos if c.source_station_id == station.id)
            self.station_weights[station.id] = total_weight
    
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
        """Bir rotanın toplam mesafesini hesapla"""
        if not route:
            return 0
        
        total_distance = self.calculate_distance(self.depot, route[0])
        
        for i in range(len(route) - 1):
            total_distance += self.calculate_distance(route[i], route[i+1])
        
        total_distance += self.calculate_distance(route[-1], self.depot)
        
        return total_distance
    
    def calculate_route_cost(self, vehicle, route: List) -> float:
        """Bir rotanın toplam maliyetini hesapla"""
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
    
    def create_individual(self) -> Dict:
        """Rastgele bir birey (çözüm) oluştur"""
        # Kargo toplama istasyonlarının kopyasını al ve karıştır
        stations_to_assign = self.pickup_stations.copy()
        random.shuffle(stations_to_assign)
        
        # Her araç için boş rota oluştur
        individual = {v.id: [] for v in self.vehicles}
        
        # İstasyonları araçlara ata (kapasite kısıtına uygun şekilde)
        for station in stations_to_assign:
            station_weight = self.station_weights.get(station.id, 0)
            
            # Uygun kapasiteye sahip rastgele bir araç bul
            available_vehicles = [
                v for v in self.vehicles 
                if self.calculate_route_weight(individual[v.id]) + station_weight <= v.capacity
            ]
            
            if available_vehicles:
                selected_vehicle = random.choice(available_vehicles)
                individual[selected_vehicle.id].append(station)
            else:
                # Kapasiteye uygun araç yoksa, en az yüklü araca ekle
                min_weight_vehicle = min(
                    self.vehicles,
                    key=lambda v: self.calculate_route_weight(individual[v.id])
                )
                individual[min_weight_vehicle.id].append(station)
        
        return individual
    
    def calculate_fitness(self, individual: Dict) -> float:
        """Bireyin uygunluk değerini hesapla (düşük maliyet = yüksek uygunluk)"""
        total_cost = 0
        penalty = 0
        
        for vehicle in self.vehicles:
            route = individual[vehicle.id]
            if route:
                # Rota maliyeti
                total_cost += self.calculate_route_cost(vehicle, route)
                
                # Kapasite aşımı cezası
                route_weight = self.calculate_route_weight(route)
                if route_weight > vehicle.capacity:
                    penalty += (route_weight - vehicle.capacity) * 100
        
        # Uygunluk = 1 / (maliyet + ceza)
        return 1.0 / (total_cost + penalty + 1)
    
    def tournament_selection(self, population: List, fitness_scores: List, tournament_size: int = 5) -> Dict:
        """Turnuva seçimi ile ebeveyn seç"""
        tournament_indices = random.sample(range(len(population)), tournament_size)
        best_index = max(tournament_indices, key=lambda i: fitness_scores[i])
        return copy.deepcopy(population[best_index])
    
    def crossover(self, parent1: Dict, parent2: Dict) -> Tuple[Dict, Dict]:
        """İki ebeveynden çaprazlama ile çocuklar oluştur"""
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)
        
        child1 = {v.id: [] for v in self.vehicles}
        child2 = {v.id: [] for v in self.vehicles}
        
        # Tüm istasyonları topla
        all_stations_p1 = []
        all_stations_p2 = []
        
        for v in self.vehicles:
            all_stations_p1.extend(parent1[v.id])
            all_stations_p2.extend(parent2[v.id])
        
        # Tek nokta çaprazlama
        if all_stations_p1 and all_stations_p2:
            crossover_point = random.randint(1, len(all_stations_p1) - 1) if len(all_stations_p1) > 1 else 1
            
            # Çocuk 1: P1'in ilk yarısı + P2'den geri kalanlar
            used_stations = set()
            stations_for_child1 = all_stations_p1[:crossover_point]
            used_stations.update(s.id for s in stations_for_child1)
            
            for s in all_stations_p2:
                if s.id not in used_stations:
                    stations_for_child1.append(s)
                    used_stations.add(s.id)
            
            # Çocuk 2: P2'nin ilk yarısı + P1'den geri kalanlar
            used_stations = set()
            stations_for_child2 = all_stations_p2[:crossover_point]
            used_stations.update(s.id for s in stations_for_child2)
            
            for s in all_stations_p1:
                if s.id not in used_stations:
                    stations_for_child2.append(s)
                    used_stations.add(s.id)
            
            # İstasyonları araçlara dağıt
            child1 = self._distribute_stations_to_vehicles(stations_for_child1)
            child2 = self._distribute_stations_to_vehicles(stations_for_child2)
        
        return child1, child2
    
    def _distribute_stations_to_vehicles(self, stations: List) -> Dict:
        """İstasyonları araçlara dağıt"""
        result = {v.id: [] for v in self.vehicles}
        
        for station in stations:
            station_weight = self.station_weights.get(station.id, 0)
            
            # Uygun kapasiteye sahip araç bul
            available_vehicles = [
                v for v in self.vehicles
                if self.calculate_route_weight(result[v.id]) + station_weight <= v.capacity
            ]
            
            if available_vehicles:
                # En az yüklü aracı seç
                selected_vehicle = min(
                    available_vehicles,
                    key=lambda v: self.calculate_route_weight(result[v.id])
                )
                result[selected_vehicle.id].append(station)
            else:
                # Kapasiteye uygun araç yoksa en az yüklü araca ekle
                min_weight_vehicle = min(
                    self.vehicles,
                    key=lambda v: self.calculate_route_weight(result[v.id])
                )
                result[min_weight_vehicle.id].append(station)
        
        return result
    
    def mutate(self, individual: Dict) -> Dict:
        """Mutasyon uygula"""
        if random.random() > self.mutation_rate:
            return individual
        
        mutated = copy.deepcopy(individual)
        
        # Mutasyon tipi seç
        mutation_type = random.choice(['swap', 'move', 'reverse'])
        
        if mutation_type == 'swap':
            # İki araç arasında istasyon değiştir
            vehicles_with_stations = [v for v in self.vehicles if mutated[v.id]]
            if len(vehicles_with_stations) >= 2:
                v1, v2 = random.sample(vehicles_with_stations, 2)
                if mutated[v1.id] and mutated[v2.id]:
                    idx1 = random.randint(0, len(mutated[v1.id]) - 1)
                    idx2 = random.randint(0, len(mutated[v2.id]) - 1)
                    mutated[v1.id][idx1], mutated[v2.id][idx2] = mutated[v2.id][idx2], mutated[v1.id][idx1]
        
        elif mutation_type == 'move':
            # Bir istasyonu başka bir araca taşı
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
            # Bir rotayı ters çevir
            vehicles_with_stations = [v for v in self.vehicles if len(mutated[v.id]) > 1]
            if vehicles_with_stations:
                vehicle = random.choice(vehicles_with_stations)
                mutated[vehicle.id].reverse()
        
        return mutated
    
    def optimize_route_order(self, route: List) -> List:
        """2-opt algoritması ile rota sırasını optimize et"""
        if len(route) <= 2:
            return route
        
        improved = True
        best_route = route.copy()
        best_distance = self.calculate_route_distance(best_route)
        
        while improved:
            improved = False
            for i in range(len(best_route) - 1):
                for j in range(i + 2, len(best_route)):
                    # 2-opt swap
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
        
        for generation in range(self.generations):
            # Uygunluk değerlerini hesapla
            fitness_scores = [self.calculate_fitness(ind) for ind in population]
            
            # En iyi çözümü güncelle
            best_idx = max(range(len(population)), key=lambda i: fitness_scores[i])
            current_cost = sum(
                self.calculate_route_cost(v, population[best_idx][v.id])
                for v in self.vehicles
            )
            
            if current_cost < best_cost:
                best_cost = current_cost
                best_solution = copy.deepcopy(population[best_idx])
            
            # Yeni nesil oluştur
            new_population = []
            
            # Seçkinlik: En iyi bireyleri koru
            elite_indices = sorted(
                range(len(population)),
                key=lambda i: fitness_scores[i],
                reverse=True
            )[:self.elite_size]
            
            for idx in elite_indices:
                new_population.append(copy.deepcopy(population[idx]))
            
            # Çaprazlama ve mutasyon ile yeni bireyler oluştur
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
        
        # En iyi çözümdeki rotaları 2-opt ile optimize et
        if best_solution:
            for vehicle in self.vehicles:
                best_solution[vehicle.id] = self.optimize_route_order(best_solution[vehicle.id])
            
            # Final maliyeti hesapla
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
        """
        Args:
            capacity: Araç kapasitesi (kg)
            cargos: Kargo listesi
        """
        self.capacity = int(capacity)
        self.cargos = cargos
    
    def optimize(self) -> Tuple[List, float]:
        """
        Dinamik programlama ile optimal kargo seçimi
        
        Returns:
            (seçilen kargolar, toplam değer)
        """
        n = len(self.cargos)
        W = self.capacity
        
        # Her kargonun değeri = öncelik * ağırlık (basit değerleme)
        values = [c.weight for c in self.cargos]  # Değer olarak ağırlığı kullan
        weights = [int(c.weight) for c in self.cargos]
        
        # DP tablosu
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
        
        # Seçilen kargoları bul
        selected_cargos = []
        w = W
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i-1][w]:
                selected_cargos.append(self.cargos[i-1])
                w -= weights[i-1]
        
        return selected_cargos, dp[n][W]
