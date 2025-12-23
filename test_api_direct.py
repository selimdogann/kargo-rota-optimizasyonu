"""
Doğrudan DB Test
"""
import sys
sys.path.insert(0, 'C:\\Users\\PC\\Desktop\\cargosystem')

from app import db, app, Trip, Cargo
import json

with app.app_context():
    cargo = Cargo.query.get(1)
    trip = Trip.query.filter_by(vehicle_id=cargo.vehicle_id).order_by(Trip.created_at.desc()).first()
    
    print('=== TRIP VERİSİ ===')
    print(f'Trip ID: {trip.id}')
    print(f'Mesafe: {trip.total_distance}')
    print(f'Maliyet: {trip.total_cost}')
    print(f'Yakıt: {trip.fuel_cost}')
    
    route_details = json.loads(trip.route_details) if trip.route_details else {}
    stops = route_details.get('stops', [])
    print(f'Durak sayısı: {len(stops)}')
    if stops:
        print('Duraklar:')
        for s in stops:
            print(f'  - {s.get("station_name")} ({s.get("latitude")}, {s.get("longitude")})')
    
    coords = json.loads(trip.path_coordinates) if trip.path_coordinates else []
    print(f'\nPath koordinat sayısı: {len(coords)}')
    if coords:
        print(f'İlk: {coords[0]}')
        print(f'Son: {coords[-1]}')
        
        # Format kontrol
        first = coords[0]
        if 'lat' in first and 'lng' in first:
            print('Format: dict with lat/lng ✓')
    
    print('\n=== JSON RESPONSE SİMÜLASYONU ===')
    
    # API'nin döndüreceği veriyi simüle et
    response_data = {
        'route': {
            'stops': stops,
            'distance': trip.total_distance,
            'total_cost': trip.total_cost,
            'fuel_cost': trip.fuel_cost,
        },
        'path_coordinates': coords
    }
    
    print('route.distance:', response_data['route']['distance'])
    print('route.total_cost:', response_data['route']['total_cost'])
    print('route.fuel_cost:', response_data['route']['fuel_cost'])
    print('route.stops length:', len(response_data['route']['stops']))
    print('path_coordinates length:', len(response_data['path_coordinates']))
