"""
Test: Kargo ekle ve optimizasyon yap
"""
from app import db, app, Trip, Route, Cargo, Station, Vehicle
import json
from datetime import date

with app.app_context():
    # Bekleyen kargo var mı kontrol et
    pending = Cargo.query.filter_by(status='pending').count()
    print(f'Bekleyen kargo sayısı: {pending}')
    
    if pending == 0:
        print('Test kargolar ekleniyor...')
        
        # Depoyu bul
        depot = Station.query.filter_by(is_depot=True).first()
        print(f'Depo: {depot.name}')
        
        # Hedef istasyonları bul (depo olmayan)
        stations = Station.query.filter_by(is_depot=False).all()
        print(f'Hedef istasyon sayısı: {len(stations)}')
        
        # Test kargolar ekle
        test_cargos = [
            {'sender': 'Ali Yılmaz', 'receiver': 'Mehmet Demir', 'weight': 50, 'dest': 'Gebze'},
            {'sender': 'Ayşe Kaya', 'receiver': 'Fatma Öz', 'weight': 30, 'dest': 'İzmit'},
            {'sender': 'Veli Çelik', 'receiver': 'Hasan Ak', 'weight': 80, 'dest': 'Körfez'},
        ]
        
        for tc in test_cargos:
            dest_station = Station.query.filter_by(name=tc['dest']).first()
            if dest_station:
                cargo = Cargo(
                    sender_name=tc['sender'],
                    receiver_name=tc['receiver'],
                    weight=tc['weight'],
                    source_station_id=depot.id,  # Tüm kargolar depodan
                    dest_station_id=dest_station.id,
                    status='pending',
                    delivery_date=date.today()
                )
                db.session.add(cargo)
                print(f'  + Kargo eklendi: {tc["sender"]} -> {tc["receiver"]} ({tc["weight"]}kg) -> {tc["dest"]}')
        
        db.session.commit()
        print('Test kargolar eklendi!')
    
    # Şimdi optimizasyon yap
    print('\n=== OPTİMİZASYON BAŞLIYOR ===')
    
    from algorithms.distance_calculator import get_distance_matrix, generate_path_between_stations
    from algorithms.genetic_algorithm import GeneticAlgorithmCVRP
    
    pending_cargos = Cargo.query.filter_by(status='pending').all()
    stations = Station.query.all()
    vehicles = Vehicle.query.filter_by(is_available=True).all()
    depot = Station.query.filter_by(is_depot=True).first()
    
    print(f'Bekleyen kargo: {len(pending_cargos)}')
    print(f'Mevcut araç: {len(vehicles)}')
    print(f'Depo: {depot.name}')
    
    if not pending_cargos:
        print('Bekleyen kargo yok!')
        exit()
    
    if not vehicles:
        print('Mevcut araç yok!')
        exit()
    
    # Mesafe matrisi
    distance_matrix = get_distance_matrix(db, Station, __import__('app').DistanceMatrix)
    
    # GA çalıştır
    ga = GeneticAlgorithmCVRP(
        stations=stations,
        vehicles=vehicles,
        cargos=pending_cargos,
        depot=depot,
        distance_matrix=distance_matrix
    )
    
    best_solution, best_cost = ga.run()
    print(f'\nEn iyi maliyet: {best_cost:.2f} TL')
    
    # Her araç için rota oluştur
    for vehicle_id, route_stations in best_solution.items():
        vehicle = Vehicle.query.get(vehicle_id)
        if not route_stations:
            continue
        
        print(f'\nAraç {vehicle_id} ({vehicle.name}):')
        print(f'  Durak sayısı: {len(route_stations)}')
        
        route_station_ids = [s.id for s in route_stations]
        route_distance = ga.calculate_route_distance(route_stations)
        route_cost = ga.calculate_route_cost(vehicle, route_stations)
        
        print(f'  Mesafe: {route_distance:.2f} km')
        print(f'  Maliyet: {route_cost:.2f} TL')
        
        # A* path
        path_coords = generate_path_between_stations(depot, route_stations, stations)
        print(f'  Path koordinat sayısı: {len(path_coords)}')
        
        # Rotadaki kargolar
        route_cargos = []
        route_total_weight = 0
        for cargo in pending_cargos:
            if cargo.dest_station_id in route_station_ids:
                cargo.vehicle_id = vehicle_id
                cargo.status = 'in_transit'
                route_cargos.append({'id': cargo.id, 'weight': cargo.weight})
                route_total_weight += cargo.weight
        
        print(f'  Kargo sayısı: {len(route_cargos)}')
        print(f'  Toplam ağırlık: {route_total_weight} kg')
        
        # Rota detayları
        route_details = {
            'stations': [{'id': s.id, 'name': s.name, 'lat': s.latitude, 'lng': s.longitude} for s in route_stations],
            'stops': [{'station_id': s.id, 'station_name': s.name, 'latitude': s.latitude, 'longitude': s.longitude} for s in route_stations],
            'cargos': route_cargos,
            'vehicle': vehicle.to_dict()
        }
        
        # Route kaydet
        route = Route(
            vehicle_id=vehicle_id,
            date=date.today(),
            route_order=json.dumps(route_station_ids),
            total_distance=route_distance,
            total_cost=route_cost,
            status='planned'
        )
        db.session.add(route)
        db.session.flush()
        
        # Trip kaydet
        fuel_cost = route_distance * vehicle.cost_per_km
        rental_cost_val = vehicle.rental_cost if vehicle.is_rental else 0
        
        trip = Trip(
            route_id=route.id,
            vehicle_id=vehicle_id,
            date=date.today(),
            status='planned',
            total_distance=route_distance,
            total_cost=route_cost,
            fuel_cost=fuel_cost,
            rental_cost=rental_cost_val,
            cargo_count=len(route_cargos),
            total_weight=route_total_weight,
            route_details=json.dumps(route_details),
            path_coordinates=json.dumps(path_coords)
        )
        db.session.add(trip)
        
        print(f'  Route ID: {route.id}')
        print(f'  Trip oluşturuldu!')
    
    db.session.commit()
    print('\n=== OPTİMİZASYON TAMAMLANDI ===')
    
    # Sonuçları kontrol et
    print('\n=== SONUÇ KONTROL ===')
    trips = Trip.query.all()
    for t in trips:
        print(f'\nTrip {t.id}:')
        print(f'  Araç: {t.vehicle_id}')
        print(f'  Mesafe: {t.total_distance}')
        print(f'  Maliyet: {t.total_cost}')
        print(f'  Yakıt: {t.fuel_cost}')
        
        if t.path_coordinates:
            coords = json.loads(t.path_coordinates)
            print(f'  Path koordinat sayısı: {len(coords)}')
            if len(coords) > 2:
                print('  ✓ Düzgün A* path oluşturulmuş (kuş uçuşu değil)')
            else:
                print('  ✗ Sadece 2 koordinat var, kuş uçuşu olabilir!')
