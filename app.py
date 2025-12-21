"""
Kargo Dağıtım Sistemi - Ana Flask Uygulaması
CVRP (Capacitated Vehicle Routing Problem) çözümü için Genetik Algoritma kullanır
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kargo-sistem-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cargo_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== VERİTABANI MODELLERİ ====================

class Station(db.Model):
    """İstasyon/İlçe modeli"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_depot = db.Column(db.Boolean, default=False)  # Ana depo mu?
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_depot': self.is_depot
        }


class Vehicle(db.Model):
    """Araç modeli"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Float, nullable=False)  # kg cinsinden kapasite
    cost_per_km = db.Column(db.Float, default=1.0)  # km başına maliyet
    is_rental = db.Column(db.Boolean, default=False)  # Kiralık mı?
    rental_cost = db.Column(db.Float, default=0)  # Kiralık ise günlük maliyet
    is_available = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'capacity': self.capacity,
            'cost_per_km': self.cost_per_km,
            'is_rental': self.is_rental,
            'rental_cost': self.rental_cost,
            'is_available': self.is_available
        }


class Cargo(db.Model):
    """Kargo modeli"""
    id = db.Column(db.Integer, primary_key=True)
    sender_name = db.Column(db.String(100), nullable=False)
    receiver_name = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, nullable=False)  # kg cinsinden ağırlık
    source_station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=False)
    dest_station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, in_transit, delivered
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_date = db.Column(db.Date, nullable=True)
    
    source_station = db.relationship('Station', foreign_keys=[source_station_id])
    dest_station = db.relationship('Station', foreign_keys=[dest_station_id])
    vehicle = db.relationship('Vehicle')
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_name': self.sender_name,
            'receiver_name': self.receiver_name,
            'weight': self.weight,
            'source_station': self.source_station.to_dict() if self.source_station else None,
            'dest_station': self.dest_station.to_dict() if self.dest_station else None,
            'status': self.status,
            'vehicle_id': self.vehicle_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None
        }


class Route(db.Model):
    """Rota modeli - Araçların günlük rotaları"""
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    route_order = db.Column(db.Text, nullable=False)  # JSON formatında istasyon sırası
    total_distance = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default='planned')  # planned, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    vehicle = db.relationship('Vehicle')
    
    def to_dict(self):
        import json
        return {
            'id': self.id,
            'vehicle': self.vehicle.to_dict() if self.vehicle else None,
            'date': self.date.isoformat() if self.date else None,
            'route_order': json.loads(self.route_order) if self.route_order else [],
            'total_distance': self.total_distance,
            'total_cost': self.total_cost,
            'status': self.status
        }


class DistanceMatrix(db.Model):
    """İstasyonlar arası mesafe matrisi"""
    id = db.Column(db.Integer, primary_key=True)
    from_station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=False)
    to_station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=False)
    distance = db.Column(db.Float, nullable=False)  # km cinsinden mesafe
    
    from_station = db.relationship('Station', foreign_keys=[from_station_id])
    to_station = db.relationship('Station', foreign_keys=[to_station_id])


class Trip(db.Model):
    """Sefer kayıtları - Tüm seferler anlık olarak kaydedilir"""
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='planned')  # planned, in_progress, completed
    total_distance = db.Column(db.Float, default=0)
    total_cost = db.Column(db.Float, default=0)
    fuel_cost = db.Column(db.Float, default=0)
    rental_cost = db.Column(db.Float, default=0)
    cargo_count = db.Column(db.Integer, default=0)
    total_weight = db.Column(db.Float, default=0)
    route_details = db.Column(db.Text, nullable=True)  # JSON: detaylı rota bilgisi
    path_coordinates = db.Column(db.Text, nullable=True)  # JSON: A* yol koordinatları
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    route = db.relationship('Route')
    vehicle = db.relationship('Vehicle')
    
    def to_dict(self):
        import json
        return {
            'id': self.id,
            'route_id': self.route_id,
            'vehicle': self.vehicle.to_dict() if self.vehicle else None,
            'date': self.date.isoformat() if self.date else None,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status,
            'total_distance': self.total_distance,
            'total_cost': self.total_cost,
            'fuel_cost': self.fuel_cost,
            'rental_cost': self.rental_cost,
            'cargo_count': self.cargo_count,
            'total_weight': self.total_weight,
            'route_details': json.loads(self.route_details) if self.route_details else None,
            'path_coordinates': json.loads(self.path_coordinates) if self.path_coordinates else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ==================== API ROUTES ====================

# Ana sayfa
@app.route('/')
def index():
    return render_template('index.html')


# Kullanıcı paneli
@app.route('/user')
def user_panel():
    return render_template('user_panel.html')


# Yönetici paneli
@app.route('/admin')
def admin_panel():
    return render_template('admin_panel.html')


# ==================== İSTASYON API ====================

@app.route('/api/stations', methods=['GET'])
def get_stations():
    """Tüm istasyonları getir"""
    stations = Station.query.all()
    return jsonify([s.to_dict() for s in stations])


@app.route('/api/stations', methods=['POST'])
def add_station():
    """Yeni istasyon ekle"""
    data = request.json
    station = Station(
        name=data['name'],
        latitude=data['latitude'],
        longitude=data['longitude'],
        is_depot=data.get('is_depot', False)
    )
    db.session.add(station)
    db.session.commit()
    
    # Mesafe matrisini güncelle
    from algorithms.distance_calculator import update_distance_matrix
    update_distance_matrix(db, Station, DistanceMatrix)
    
    return jsonify(station.to_dict()), 201


@app.route('/api/stations/<int:id>', methods=['DELETE'])
def delete_station(id):
    """İstasyon sil"""
    station = Station.query.get_or_404(id)
    db.session.delete(station)
    db.session.commit()
    return jsonify({'message': 'İstasyon silindi'}), 200


# ==================== ARAÇ API ====================

@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    """Tüm araçları getir"""
    vehicles = Vehicle.query.all()
    return jsonify([v.to_dict() for v in vehicles])


@app.route('/api/vehicles', methods=['POST'])
def add_vehicle():
    """Yeni araç ekle"""
    data = request.json
    vehicle = Vehicle(
        name=data['name'],
        capacity=data['capacity'],
        cost_per_km=data.get('cost_per_km', 1.0),
        is_rental=data.get('is_rental', False),
        rental_cost=data.get('rental_cost', 0)
    )
    db.session.add(vehicle)
    db.session.commit()
    return jsonify(vehicle.to_dict()), 201


# ==================== KARGO API ====================

@app.route('/api/cargos', methods=['GET'])
def get_cargos():
    """Tüm kargoları getir"""
    cargos = Cargo.query.all()
    return jsonify([c.to_dict() for c in cargos])


@app.route('/api/cargos/pending', methods=['GET'])
def get_pending_cargos():
    """Bekleyen kargoları getir"""
    cargos = Cargo.query.filter_by(status='pending').all()
    return jsonify([c.to_dict() for c in cargos])


@app.route('/api/cargos', methods=['POST'])
def add_cargo():
    """Yeni kargo ekle"""
    data = request.json
    cargo = Cargo(
        sender_name=data['sender_name'],
        receiver_name=data['receiver_name'],
        weight=data['weight'],
        source_station_id=data['source_station_id'],
        dest_station_id=data['dest_station_id'],
        delivery_date=datetime.strptime(data['delivery_date'], '%Y-%m-%d').date() if data.get('delivery_date') else None
    )
    db.session.add(cargo)
    db.session.commit()
    return jsonify(cargo.to_dict()), 201


@app.route('/api/cargos/<int:id>', methods=['GET'])
def get_cargo(id):
    """Kargo detayı getir"""
    cargo = Cargo.query.get_or_404(id)
    return jsonify(cargo.to_dict())


@app.route('/api/cargos/track/<int:id>', methods=['GET'])
def track_cargo(id):
    """Kargo takibi"""
    cargo = Cargo.query.get_or_404(id)
    result = cargo.to_dict()
    
    # Eğer araç atanmışsa, rota bilgisini de ekle
    if cargo.vehicle_id:
        route = Route.query.filter_by(
            vehicle_id=cargo.vehicle_id,
            status='in_progress'
        ).first()
        if route:
            result['route'] = route.to_dict()
    
    return jsonify(result)


# ==================== ROTA API ====================

@app.route('/api/routes', methods=['GET'])
def get_routes():
    """Tüm rotaları getir"""
    routes = Route.query.all()
    return jsonify([r.to_dict() for r in routes])


@app.route('/api/routes/active', methods=['GET'])
def get_active_routes():
    """Aktif rotaları getir"""
    routes = Route.query.filter(Route.status.in_(['planned', 'in_progress'])).all()
    return jsonify([r.to_dict() for r in routes])


@app.route('/api/routes/optimize', methods=['POST'])
def optimize_routes():
    """Genetik Algoritma ile rota optimizasyonu yap"""
    from algorithms.genetic_algorithm import GeneticAlgorithmCVRP
    from algorithms.distance_calculator import get_distance_matrix, generate_path_between_stations
    import json
    from datetime import date
    
    data = request.json
    target_date = datetime.strptime(data.get('date', date.today().isoformat()), '%Y-%m-%d').date()
    
    # Hedef tarihe göre bekleyen kargoları al (bir sonraki gün için)
    pending_cargos = Cargo.query.filter(
        (Cargo.status == 'pending') &
        ((Cargo.delivery_date == None) | (Cargo.delivery_date <= target_date))
    ).all()
    
    if not pending_cargos:
        return jsonify({'message': 'Bekleyen kargo yok'}), 400
    
    # İstasyon bazlı kargo özeti
    station_summary = {}
    for cargo in pending_cargos:
        dest_id = cargo.dest_station_id
        if dest_id not in station_summary:
            station_summary[dest_id] = {'count': 0, 'weight': 0, 'cargos': []}
        station_summary[dest_id]['count'] += 1
        station_summary[dest_id]['weight'] += cargo.weight
        station_summary[dest_id]['cargos'].append(cargo)
    
    # Mevcut araçları al
    vehicles = Vehicle.query.filter_by(is_available=True, is_rental=False).all()
    own_vehicles = list(vehicles)
    
    # İstasyonları al
    stations = Station.query.all()
    depot = Station.query.filter_by(is_depot=True).first()
    
    if not depot:
        return jsonify({'message': 'Depo istasyonu bulunamadı'}), 400
    
    # Mesafe matrisini al
    distance_matrix = get_distance_matrix(db, Station, DistanceMatrix)
    
    # Toplam kargo ağırlığını hesapla
    total_weight = sum(c.weight for c in pending_cargos)
    total_capacity = sum(v.capacity for v in own_vehicles)
    
    # Kapasite yetersizse kiralık araç ekle
    rental_vehicles = []
    if total_weight > total_capacity:
        needed_capacity = total_weight - total_capacity
        rental_count = int(needed_capacity / 500) + 1  # Her kiralık araç 500kg
        
        for i in range(rental_count):
            rental = Vehicle(
                name=f'Kiralık Araç {i+1}',
                capacity=500,
                cost_per_km=1.0,
                is_rental=True,
                rental_cost=200
            )
            db.session.add(rental)
            rental_vehicles.append(rental)
        
        db.session.commit()
        own_vehicles.extend(rental_vehicles)
    
    # Genetik Algoritma ile optimizasyon
    ga = GeneticAlgorithmCVRP(
        stations=stations,
        vehicles=own_vehicles,
        cargos=pending_cargos,
        depot=depot,
        distance_matrix=distance_matrix
    )
    
    best_solution, best_cost = ga.run()
    
    # Rotaları ve sefer kayıtlarını oluştur
    created_routes = []
    created_trips = []
    
    for vehicle_id, route_stations in best_solution.items():
        vehicle = Vehicle.query.get(vehicle_id)
        if not route_stations:
            continue
        
        route_station_ids = [s.id for s in route_stations]
        route_distance = ga.calculate_route_distance(route_stations)
        route_cost = ga.calculate_route_cost(vehicle, route_stations)
        
        # A* ile yol koordinatlarını hesapla (kuş uçuşu değil)
        path_coords = generate_path_between_stations(depot, route_stations, stations)
        
        # Rotadaki kargolar ve kullanıcılar
        route_cargos = []
        route_total_weight = 0
        for cargo in pending_cargos:
            if cargo.dest_station_id in route_station_ids:
                cargo.vehicle_id = vehicle_id
                cargo.status = 'in_transit'
                route_cargos.append({
                    'id': cargo.id,
                    'sender': cargo.sender_name,
                    'receiver': cargo.receiver_name,
                    'weight': cargo.weight,
                    'destination': cargo.dest_station.name
                })
                route_total_weight += cargo.weight
        
        # Rota detayları
        route_details = {
            'stations': [{'id': s.id, 'name': s.name, 'lat': s.latitude, 'lng': s.longitude} for s in route_stations],
            'cargos': route_cargos,
            'vehicle': vehicle.to_dict()
        }
        
        # Rota kaydı
        route = Route(
            vehicle_id=vehicle_id,
            date=target_date,
            route_order=json.dumps(route_station_ids),
            total_distance=route_distance,
            total_cost=route_cost,
            status='planned'
        )
        db.session.add(route)
        db.session.flush()  # ID almak için
        
        # Sefer kaydı
        fuel_cost = route_distance * vehicle.cost_per_km
        rental_cost_val = vehicle.rental_cost if vehicle.is_rental else 0
        
        trip = Trip(
            route_id=route.id,
            vehicle_id=vehicle_id,
            date=target_date,
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
        
        created_routes.append(route)
        created_trips.append(trip)
    
    db.session.commit()
    
    # Sonuçları hazırla
    total_rental_cost = sum(v.rental_cost for v in rental_vehicles)
    result = {
        'total_cost': best_cost,
        'rental_cost': total_rental_cost,
        'fuel_cost': best_cost - total_rental_cost,
        'routes': [r.to_dict() for r in created_routes],
        'trips': [t.to_dict() for t in created_trips],
        'rented_vehicles': len(rental_vehicles),
        'station_summary': {str(k): {'count': v['count'], 'weight': v['weight']} for k, v in station_summary.items()}
    }
    
    return jsonify(result)


@app.route('/api/routes/<int:id>/start', methods=['POST'])
def start_route(id):
    """Rotayı başlat"""
    route = Route.query.get_or_404(id)
    route.status = 'in_progress'
    db.session.commit()
    return jsonify(route.to_dict())


@app.route('/api/routes/<int:id>/complete', methods=['POST'])
def complete_route(id):
    """Rotayı tamamla"""
    route = Route.query.get_or_404(id)
    route.status = 'completed'
    
    # Araçtaki kargoları teslim edildi olarak işaretle
    cargos = Cargo.query.filter_by(vehicle_id=route.vehicle_id, status='in_transit').all()
    for cargo in cargos:
        cargo.status = 'delivered'
    
    # Sefer kaydını güncelle
    trip = Trip.query.filter_by(route_id=id).first()
    if trip:
        trip.status = 'completed'
        trip.end_time = datetime.utcnow()
    
    db.session.commit()
    return jsonify(route.to_dict())


# ==================== SEFER (TRIP) API ====================

@app.route('/api/trips', methods=['GET'])
def get_trips():
    """Tüm sefer kayıtlarını getir"""
    trips = Trip.query.order_by(Trip.created_at.desc()).all()
    return jsonify([t.to_dict() for t in trips])


@app.route('/api/trips/active', methods=['GET'])
def get_active_trips():
    """Aktif seferleri getir"""
    trips = Trip.query.filter(Trip.status.in_(['planned', 'in_progress'])).all()
    return jsonify([t.to_dict() for t in trips])


@app.route('/api/trips/<int:id>', methods=['GET'])
def get_trip(id):
    """Sefer detayı getir"""
    trip = Trip.query.get_or_404(id)
    return jsonify(trip.to_dict())


@app.route('/api/trips/by-vehicle/<int:vehicle_id>', methods=['GET'])
def get_trips_by_vehicle(vehicle_id):
    """Araç bazlı sefer kayıtları"""
    trips = Trip.query.filter_by(vehicle_id=vehicle_id).order_by(Trip.date.desc()).all()
    return jsonify([t.to_dict() for t in trips])


@app.route('/api/trips/<int:id>/start', methods=['POST'])
def start_trip(id):
    """Seferi başlat"""
    trip = Trip.query.get_or_404(id)
    trip.status = 'in_progress'
    trip.start_time = datetime.utcnow()
    
    # İlgili rotayı da başlat
    route = Route.query.get(trip.route_id)
    if route:
        route.status = 'in_progress'
    
    db.session.commit()
    return jsonify(trip.to_dict())


# ==================== KULLANICI KARGO TAKİP API ====================

@app.route('/api/cargos/my-route/<int:cargo_id>', methods=['GET'])
def get_cargo_route(cargo_id):
    """
    Kullanıcının kargosu için araç rotası - Sadece kendi aracının güzergahı
    DİĞER ARAÇLARIN GÜZERGAH BİLGİLERİNE ERİŞİM ENGELLENMİŞTİR
    """
    cargo = Cargo.query.get_or_404(cargo_id)
    
    if not cargo.vehicle_id:
        return jsonify({
            'message': 'Kargo henüz bir araca atanmamış', 
            'status': 'pending',
            'cargo': cargo.to_dict()
        }), 200
    
    # Bu kargonun aracının sefer bilgisini al
    trip = Trip.query.filter_by(vehicle_id=cargo.vehicle_id).order_by(Trip.created_at.desc()).first()
    
    if not trip:
        # Trip yoksa Route'dan bilgi almayı dene
        route = Route.query.filter_by(vehicle_id=cargo.vehicle_id).order_by(Route.date.desc()).first()
        if not route:
            return jsonify({'message': 'Sefer bilgisi bulunamadı'}), 404
        
        # Route bilgisinden response oluştur
        import json
        route_stations = json.loads(route.route_order) if route.route_order else []
        stops = []
        for station_id in route_stations:
            station = Station.query.get(station_id)
            if station:
                stops.append({
                    'station_id': station.id,
                    'station_name': station.name,
                    'latitude': station.latitude,
                    'longitude': station.longitude
                })
        
        vehicle = Vehicle.query.get(cargo.vehicle_id)
        
        # A* path'i oluştur
        from algorithms.distance_calculator import generate_path_between_stations
        depot = Station.query.filter_by(is_depot=True).first()
        all_stations = {s.id: {'id': s.id, 'name': s.name, 'latitude': s.latitude, 'longitude': s.longitude} 
                       for s in Station.query.all()}
        
        path_coords = []
        if depot and stops:
            path_coords = generate_path_between_stations(
                {'latitude': depot.latitude, 'longitude': depot.longitude},
                stops,
                list(all_stations.values())
            )
        
        return jsonify({
            'cargo': cargo.to_dict(),
            'vehicle': vehicle.to_dict() if vehicle else None,
            'route': {
                'stops': stops,
                'distance': route.total_distance,
                'total_cost': route.total_cost,
                'fuel_cost': route.total_distance * (vehicle.cost_per_km if vehicle else 1),
                'status': route.status
            },
            'path_coordinates': path_coords,
            'trip_status': route.status,
            'trip_date': route.date.isoformat() if route.date else None,
            'message': 'Sadece bu kargonuzun aracının güzergahı gösterilmektedir'
        })
    
    # Trip bilgisinden response oluştur
    import json
    route_details = json.loads(trip.route_details) if trip.route_details else {}
    path_coordinates = json.loads(trip.path_coordinates) if trip.path_coordinates else []
    
    # Durakları route_details'den al
    stops = route_details.get('stops', [])
    
    vehicle = Vehicle.query.get(cargo.vehicle_id)
    
    return jsonify({
        'cargo': cargo.to_dict(),
        'vehicle': {
            'id': vehicle.id,
            'name': vehicle.name,
            'capacity': vehicle.capacity,
            'cost_per_km': vehicle.cost_per_km,
            'daily_rental_cost': vehicle.rental_cost if vehicle.is_rental else 0,
            'is_rental': vehicle.is_rental
        } if vehicle else None,
        'route': {
            'stops': stops,
            'distance': trip.total_distance,
            'total_cost': trip.total_cost,
            'fuel_cost': trip.fuel_cost,
            'rental_cost': trip.rental_cost,
            'cargo_count': trip.cargo_count,
            'total_weight': trip.total_weight
        },
        'path_coordinates': path_coordinates,
        'trip_status': trip.status,
        'trip_date': trip.date.isoformat() if trip.date else None,
        'start_time': trip.start_time.isoformat() if trip.start_time else None,
        'end_time': trip.end_time.isoformat() if trip.end_time else None,
        'message': 'Sadece bu kargonuzun aracının güzergahı gösterilmektedir. Diğer araçların güzergah bilgilerine erişiminiz bulunmamaktadır.'
    })


# ==================== MESAFE MATRİSİ API ====================

@app.route('/api/distance-matrix', methods=['GET'])
def get_distance_matrix_api():
    """Mesafe matrisini getir"""
    from algorithms.distance_calculator import get_distance_matrix
    matrix = get_distance_matrix(db, Station, DistanceMatrix)
    return jsonify(matrix)


# ==================== ANALİZ API ====================

@app.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Genel özet analiz"""
    total_cargos = Cargo.query.count()
    pending_cargos = Cargo.query.filter_by(status='pending').count()
    delivered_cargos = Cargo.query.filter_by(status='delivered').count()
    in_transit = Cargo.query.filter_by(status='in_transit').count()
    
    total_routes = Route.query.count()
    completed_routes = Route.query.filter_by(status='completed').count()
    
    total_cost = db.session.query(db.func.sum(Route.total_cost)).scalar() or 0
    total_distance = db.session.query(db.func.sum(Route.total_distance)).scalar() or 0
    
    return jsonify({
        'total_cargos': total_cargos,
        'pending_cargos': pending_cargos,
        'delivered_cargos': delivered_cargos,
        'in_transit': in_transit,
        'total_routes': total_routes,
        'completed_routes': completed_routes,
        'total_cost': round(total_cost, 2),
        'total_distance': round(total_distance, 2)
    })


@app.route('/api/analytics/cost-breakdown', methods=['GET'])
def get_cost_breakdown():
    """Maliyet dağılımı"""
    routes = Route.query.all()
    trips = Trip.query.all()
    
    fuel_cost = 0
    rental_cost = 0
    
    for trip in trips:
        fuel_cost += trip.fuel_cost or 0
        rental_cost += trip.rental_cost or 0
    
    return jsonify({
        'fuel_cost': round(fuel_cost, 2),
        'rental_cost': round(rental_cost, 2),
        'total_cost': round(fuel_cost + rental_cost, 2)
    })


@app.route('/api/analytics/vehicle-breakdown', methods=['GET'])
def get_vehicle_breakdown():
    """Araç bazlı maliyet ve performans dağılımı"""
    vehicles = Vehicle.query.all()
    result = []
    
    for vehicle in vehicles:
        trips = Trip.query.filter_by(vehicle_id=vehicle.id).all()
        total_distance = sum(t.total_distance or 0 for t in trips)
        total_cost = sum(t.total_cost or 0 for t in trips)
        total_cargos = sum(t.cargo_count or 0 for t in trips)
        total_weight = sum(t.total_weight or 0 for t in trips)
        
        result.append({
            'vehicle': vehicle.to_dict(),
            'total_trips': len(trips),
            'total_distance': round(total_distance, 2),
            'total_cost': round(total_cost, 2),
            'total_cargos': total_cargos,
            'total_weight': round(total_weight, 2),
            'efficiency': round((total_weight / vehicle.capacity * 100) if trips else 0, 1)
        })
    
    return jsonify(result)


@app.route('/api/analytics/station-summary', methods=['GET'])
def get_station_summary():
    """İstasyon bazlı kargo özeti - Bir sonraki gün için planlama"""
    from datetime import date, timedelta
    tomorrow = date.today() + timedelta(days=1)
    
    stations = Station.query.all()
    result = []
    
    for station in stations:
        pending_cargos = Cargo.query.filter(
            (Cargo.dest_station_id == station.id) &
            (Cargo.status == 'pending')
        ).all()
        
        result.append({
            'station': station.to_dict(),
            'cargo_count': len(pending_cargos),
            'total_weight': sum(c.weight for c in pending_cargos),
            'cargos': [c.to_dict() for c in pending_cargos]
        })
    
    return jsonify(result)


@app.route('/api/analytics/scenario-summary', methods=['GET'])
def get_scenario_summary():
    """Tüm senaryolar için özet tablo"""
    from algorithms.scenarios import get_all_scenarios
    scenarios = get_all_scenarios()
    return jsonify(scenarios)


# ==================== SENARYO TEST API ====================

@app.route('/api/scenarios/test/<int:scenario_id>', methods=['POST'])
def test_scenario(scenario_id):
    """Belirli bir senaryoyu test et"""
    from algorithms.scenarios import run_scenario
    result = run_scenario(scenario_id, db, Station, Vehicle, Cargo, Route, DistanceMatrix)
    return jsonify(result)


# ==================== VERİTABANI BAŞLATMA ====================

def init_db():
    """Veritabanını başlat ve örnek verileri ekle"""
    with app.app_context():
        db.create_all()
        
        # Eğer istasyon yoksa, Kocaeli ilçelerini ekle
        if Station.query.count() == 0:
            kocaeli_districts = [
                {'name': 'İzmit', 'lat': 40.7654, 'lng': 29.9408, 'is_depot': True},
                {'name': 'Gebze', 'lat': 40.8027, 'lng': 29.4307, 'is_depot': False},
                {'name': 'Darıca', 'lat': 40.7692, 'lng': 29.3753, 'is_depot': False},
                {'name': 'Çayırova', 'lat': 40.8261, 'lng': 29.3689, 'is_depot': False},
                {'name': 'Dilovası', 'lat': 40.7847, 'lng': 29.5372, 'is_depot': False},
                {'name': 'Körfez', 'lat': 40.7539, 'lng': 29.7628, 'is_depot': False},
                {'name': 'Derince', 'lat': 40.7531, 'lng': 29.8142, 'is_depot': False},
                {'name': 'Gölcük', 'lat': 40.7167, 'lng': 29.8333, 'is_depot': False},
                {'name': 'Karamürsel', 'lat': 40.6917, 'lng': 29.6167, 'is_depot': False},
                {'name': 'Kandıra', 'lat': 41.0711, 'lng': 30.1528, 'is_depot': False},
                {'name': 'Kartepe', 'lat': 40.7333, 'lng': 30.0333, 'is_depot': False},
                {'name': 'Başiskele', 'lat': 40.7208, 'lng': 29.9361, 'is_depot': False},
            ]
            
            for district in kocaeli_districts:
                station = Station(
                    name=district['name'],
                    latitude=district['lat'],
                    longitude=district['lng'],
                    is_depot=district['is_depot']
                )
                db.session.add(station)
            
            db.session.commit()
            
            # Mesafe matrisini oluştur
            from algorithms.distance_calculator import update_distance_matrix
            update_distance_matrix(db, Station, DistanceMatrix)
        
        # Eğer araç yoksa, varsayılan araçları ekle
        if Vehicle.query.count() == 0:
            vehicles = [
                {'name': 'Araç 1 (500kg)', 'capacity': 500, 'cost_per_km': 1.0},
                {'name': 'Araç 2 (750kg)', 'capacity': 750, 'cost_per_km': 1.2},
                {'name': 'Araç 3 (1000kg)', 'capacity': 1000, 'cost_per_km': 1.5},
            ]
            
            for v in vehicles:
                vehicle = Vehicle(
                    name=v['name'],
                    capacity=v['capacity'],
                    cost_per_km=v['cost_per_km']
                )
                db.session.add(vehicle)
            
            db.session.commit()


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
