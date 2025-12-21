"""
Test Senaryoları
PDF'teki 4 senaryoyu test etmek için
"""

import json
from datetime import date
from typing import Dict


def run_scenario(scenario_id: int, db, Station, Vehicle, Cargo, Route, DistanceMatrix) -> Dict:
    """
    Belirli bir senaryoyu çalıştır
    
    Senaryo 1: Normal kapasite, az kargo
    Senaryo 2: Normal kapasite, orta kargo
    Senaryo 3: Kapasite aşımı - kiralık araç gerekli
    Senaryo 4: Yoğun teslimat günü
    """
    
    from .genetic_algorithm import GeneticAlgorithmCVRP, KnapsackOptimizer
    from .distance_calculator import get_distance_matrix
    
    # Mevcut bekleyen kargoları temizle
    Cargo.query.filter_by(status='pending').delete()
    db.session.commit()
    
    # Senaryo verilerini hazırla
    scenario_data = get_scenario_data(scenario_id)
    
    # İstasyonları al
    stations = Station.query.all()
    station_map = {s.name: s for s in stations}
    
    depot = Station.query.filter_by(is_depot=True).first()
    
    # Senaryo kargolarını ekle
    for cargo_data in scenario_data['cargos']:
        source = station_map.get(cargo_data['source'], depot)
        dest = station_map.get(cargo_data['dest'])
        
        if dest:
            cargo = Cargo(
                sender_name=cargo_data.get('sender', 'Test Gönderici'),
                receiver_name=cargo_data.get('receiver', 'Test Alıcı'),
                weight=cargo_data['weight'],
                source_station_id=source.id,
                dest_station_id=dest.id,
                status='pending'
            )
            db.session.add(cargo)
    
    db.session.commit()
    
    # Araçları al (kiralık olmayan)
    own_vehicles = Vehicle.query.filter_by(is_rental=False, is_available=True).all()
    
    # Toplam kargo ve kapasite hesapla
    pending_cargos = Cargo.query.filter_by(status='pending').all()
    total_cargo_weight = sum(c.weight for c in pending_cargos)
    total_capacity = sum(v.capacity for v in own_vehicles)
    
    # Kiralık araç gerekli mi?
    rental_vehicles = []
    rental_needed = total_cargo_weight > total_capacity
    
    if rental_needed:
        needed_capacity = total_cargo_weight - total_capacity
        rental_count = int(needed_capacity / 500) + 1
        
        for i in range(rental_count):
            rental = Vehicle(
                name=f'Kiralık Araç {i+1}',
                capacity=500,
                cost_per_km=1.0,
                is_rental=True,
                rental_cost=200,
                is_available=True
            )
            db.session.add(rental)
            rental_vehicles.append(rental)
        
        db.session.commit()
    
    # Tüm kullanılabilir araçları al
    all_vehicles = own_vehicles + rental_vehicles
    
    # Mesafe matrisini al
    distance_matrix = get_distance_matrix(db, Station, DistanceMatrix)
    
    # Genetik Algoritma ile optimizasyon
    ga = GeneticAlgorithmCVRP(
        stations=stations,
        vehicles=all_vehicles,
        cargos=pending_cargos,
        depot=depot,
        distance_matrix=distance_matrix,
        population_size=150,
        generations=300
    )
    
    best_solution, total_cost = ga.run()
    
    # Rotaları kaydet ve sonuçları hazırla
    routes_info = []
    total_distance = 0
    fuel_cost = 0
    rental_cost = 0
    
    for vehicle in all_vehicles:
        route_stations = best_solution.get(vehicle.id, [])
        
        if route_stations:
            route_distance = ga.calculate_route_distance(route_stations)
            route_cost = ga.calculate_route_cost(vehicle, route_stations)
            
            total_distance += route_distance
            
            if vehicle.is_rental:
                rental_cost += vehicle.rental_cost
                fuel_cost += route_distance * vehicle.cost_per_km
            else:
                fuel_cost += route_distance * vehicle.cost_per_km
            
            # Rotayı kaydet
            route = Route(
                vehicle_id=vehicle.id,
                date=date.today(),
                route_order=json.dumps([s.id for s in route_stations]),
                total_distance=route_distance,
                total_cost=route_cost,
                status='completed'
            )
            db.session.add(route)
            
            # Kargo atamalarını yap
            for cargo in pending_cargos:
                if cargo.dest_station in route_stations:
                    cargo.vehicle_id = vehicle.id
                    cargo.status = 'delivered'
            
            routes_info.append({
                'vehicle': vehicle.name,
                'capacity': vehicle.capacity,
                'is_rental': vehicle.is_rental,
                'route': [s.name for s in route_stations],
                'distance': round(route_distance, 2),
                'cost': round(route_cost, 2),
                'load': round(ga.calculate_route_weight(route_stations), 2)
            })
    
    db.session.commit()
    
    # Sonuçları hazırla
    result = {
        'scenario_id': scenario_id,
        'scenario_name': scenario_data['name'],
        'scenario_description': scenario_data['description'],
        'total_cargo_weight': total_cargo_weight,
        'total_capacity': total_capacity,
        'rental_needed': rental_needed,
        'rental_vehicles_count': len(rental_vehicles),
        'total_distance': round(total_distance, 2),
        'fuel_cost': round(fuel_cost, 2),
        'rental_cost': round(rental_cost, 2),
        'total_cost': round(fuel_cost + rental_cost, 2),
        'routes': routes_info,
        'efficiency': round((total_cargo_weight / (total_capacity + len(rental_vehicles) * 500)) * 100, 2)
    }
    
    return result


def get_scenario_data(scenario_id: int) -> Dict:
    """
    Senaryo verilerini getir
    """
    scenarios = {
        1: {
            'name': 'Senaryo 1 - Hafif Yük',
            'description': 'Normal iş günü, az sayıda kargo',
            'cargos': [
                {'source': 'İzmit', 'dest': 'Gebze', 'weight': 150, 'sender': 'Firma A', 'receiver': 'Müşteri 1'},
                {'source': 'İzmit', 'dest': 'Darıca', 'weight': 200, 'sender': 'Firma B', 'receiver': 'Müşteri 2'},
                {'source': 'İzmit', 'dest': 'Körfez', 'weight': 100, 'sender': 'Firma C', 'receiver': 'Müşteri 3'},
                {'source': 'İzmit', 'dest': 'Gölcük', 'weight': 250, 'sender': 'Firma D', 'receiver': 'Müşteri 4'},
                {'source': 'İzmit', 'dest': 'Kartepe', 'weight': 180, 'sender': 'Firma E', 'receiver': 'Müşteri 5'},
            ]
        },
        2: {
            'name': 'Senaryo 2 - Orta Yük',
            'description': 'Normal kapasite kullanımı',
            'cargos': [
                {'source': 'İzmit', 'dest': 'Gebze', 'weight': 300, 'sender': 'Firma A', 'receiver': 'Müşteri 1'},
                {'source': 'İzmit', 'dest': 'Darıca', 'weight': 250, 'sender': 'Firma B', 'receiver': 'Müşteri 2'},
                {'source': 'İzmit', 'dest': 'Çayırova', 'weight': 200, 'sender': 'Firma C', 'receiver': 'Müşteri 3'},
                {'source': 'İzmit', 'dest': 'Dilovası', 'weight': 350, 'sender': 'Firma D', 'receiver': 'Müşteri 4'},
                {'source': 'İzmit', 'dest': 'Körfez', 'weight': 280, 'sender': 'Firma E', 'receiver': 'Müşteri 5'},
                {'source': 'İzmit', 'dest': 'Derince', 'weight': 320, 'sender': 'Firma F', 'receiver': 'Müşteri 6'},
                {'source': 'İzmit', 'dest': 'Gölcük', 'weight': 180, 'sender': 'Firma G', 'receiver': 'Müşteri 7'},
                {'source': 'İzmit', 'dest': 'Karamürsel', 'weight': 220, 'sender': 'Firma H', 'receiver': 'Müşteri 8'},
            ]
        },
        3: {
            'name': 'Senaryo 3 - Kapasite Aşımı',
            'description': '2700 kg kargo vs 2250 kg kapasite - Kiralık araç gerekli',
            'cargos': [
                {'source': 'İzmit', 'dest': 'Gebze', 'weight': 400, 'sender': 'Firma A', 'receiver': 'Müşteri 1'},
                {'source': 'İzmit', 'dest': 'Darıca', 'weight': 350, 'sender': 'Firma B', 'receiver': 'Müşteri 2'},
                {'source': 'İzmit', 'dest': 'Çayırova', 'weight': 300, 'sender': 'Firma C', 'receiver': 'Müşteri 3'},
                {'source': 'İzmit', 'dest': 'Dilovası', 'weight': 450, 'sender': 'Firma D', 'receiver': 'Müşteri 4'},
                {'source': 'İzmit', 'dest': 'Körfez', 'weight': 280, 'sender': 'Firma E', 'receiver': 'Müşteri 5'},
                {'source': 'İzmit', 'dest': 'Derince', 'weight': 320, 'sender': 'Firma F', 'receiver': 'Müşteri 6'},
                {'source': 'İzmit', 'dest': 'Gölcük', 'weight': 250, 'sender': 'Firma G', 'receiver': 'Müşteri 7'},
                {'source': 'İzmit', 'dest': 'Karamürsel', 'weight': 180, 'sender': 'Firma H', 'receiver': 'Müşteri 8'},
                {'source': 'İzmit', 'dest': 'Kartepe', 'weight': 170, 'sender': 'Firma I', 'receiver': 'Müşteri 9'},
            ]
        },
        4: {
            'name': 'Senaryo 4 - Yoğun Gün',
            'description': 'Tüm ilçelere teslimat',
            'cargos': [
                {'source': 'İzmit', 'dest': 'Gebze', 'weight': 200, 'sender': 'Firma A', 'receiver': 'Müşteri 1'},
                {'source': 'İzmit', 'dest': 'Gebze', 'weight': 150, 'sender': 'Firma A2', 'receiver': 'Müşteri 1b'},
                {'source': 'İzmit', 'dest': 'Darıca', 'weight': 180, 'sender': 'Firma B', 'receiver': 'Müşteri 2'},
                {'source': 'İzmit', 'dest': 'Çayırova', 'weight': 220, 'sender': 'Firma C', 'receiver': 'Müşteri 3'},
                {'source': 'İzmit', 'dest': 'Dilovası', 'weight': 190, 'sender': 'Firma D', 'receiver': 'Müşteri 4'},
                {'source': 'İzmit', 'dest': 'Körfez', 'weight': 210, 'sender': 'Firma E', 'receiver': 'Müşteri 5'},
                {'source': 'İzmit', 'dest': 'Derince', 'weight': 170, 'sender': 'Firma F', 'receiver': 'Müşteri 6'},
                {'source': 'İzmit', 'dest': 'Gölcük', 'weight': 230, 'sender': 'Firma G', 'receiver': 'Müşteri 7'},
                {'source': 'İzmit', 'dest': 'Karamürsel', 'weight': 160, 'sender': 'Firma H', 'receiver': 'Müşteri 8'},
                {'source': 'İzmit', 'dest': 'Kandıra', 'weight': 140, 'sender': 'Firma I', 'receiver': 'Müşteri 9'},
                {'source': 'İzmit', 'dest': 'Kartepe', 'weight': 200, 'sender': 'Firma J', 'receiver': 'Müşteri 10'},
                {'source': 'İzmit', 'dest': 'Başiskele', 'weight': 180, 'sender': 'Firma K', 'receiver': 'Müşteri 11'},
            ]
        }
    }
    
    return scenarios.get(scenario_id, scenarios[1])


def get_all_scenarios() -> list:
    """
    Tüm senaryoların özet bilgilerini döndür
    """
    scenarios_summary = [
        {
            'id': 1,
            'name': 'Senaryo 1 - Hafif Yük',
            'description': 'Normal iş günü, az sayıda kargo (~880 kg)',
            'cargo_count': 5,
            'estimated_weight': 880,
            'rental_expected': False,
            'difficulty': 'Kolay'
        },
        {
            'id': 2,
            'name': 'Senaryo 2 - Orta Yük',
            'description': 'Normal kapasite kullanımı (~2100 kg)',
            'cargo_count': 8,
            'estimated_weight': 2100,
            'rental_expected': False,
            'difficulty': 'Orta'
        },
        {
            'id': 3,
            'name': 'Senaryo 3 - Kapasite Aşımı',
            'description': '2700 kg kargo vs 2250 kg kapasite - Kiralık araç gerekli',
            'cargo_count': 9,
            'estimated_weight': 2700,
            'rental_expected': True,
            'difficulty': 'Zor'
        },
        {
            'id': 4,
            'name': 'Senaryo 4 - Yoğun Gün',
            'description': 'Tüm ilçelere teslimat (~2230 kg)',
            'cargo_count': 12,
            'estimated_weight': 2230,
            'rental_expected': False,
            'difficulty': 'Orta-Zor'
        }
    ]
    
    return scenarios_summary
