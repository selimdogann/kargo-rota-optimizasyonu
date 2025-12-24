"""
Kargo Dağıtım Sistemi - Ana Flask Uygulaması
CVRP (Capacitated Vehicle Routing Problem) çözümü için Genetik Algoritma kullanır
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import hashlib
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kargo-sistem-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cargo_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ==================== YARDIMCI FONKSİYONLAR ====================

def hash_password(password):
    """Şifreyi SHA256 ile hashle"""
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    """Admin girişi gerektiren decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== VERİTABANI MODELLERİ ====================

class Admin(db.Model):
    """Yönetici modeli"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    is_superadmin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        self.password_hash = hash_password(password)
    
    def check_password(self, password):
        return self.password_hash == hash_password(password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name,
            'email': self.email,
            'is_superadmin': self.is_superadmin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


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
    """
    Kargo modeli
    NOT: Tüm kargolar ilçelerden Kocaeli Üniversitesi'ne gönderilir.
    source_station_id = Kargonun gönderildiği ilçe
    dest_station_id = Her zaman Kocaeli Üniversitesi (depo)
    """
    id = db.Column(db.Integer, primary_key=True)
    sender_name = db.Column(db.String(100), nullable=False)  # Gönderen adı
    receiver_name = db.Column(db.String(100), nullable=False)  # Alıcı adı (Üniversitedeki)
    weight = db.Column(db.Float, nullable=False)  # kg cinsinden ağırlık
    source_station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=False)  # Kaynak ilçe
    dest_station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=False)  # Hedef (Kocaeli Üni)
    status = db.Column(db.String(50), default='pending')  # pending, accepted, rejected, in_transit, delivered
    is_accepted = db.Column(db.Boolean, default=True)  # Kargo kabul edildi mi?
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
            'is_accepted': self.is_accepted,
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


# Login sayfası
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            session['is_superadmin'] = admin.is_superadmin
            admin.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('admin_panel'))
        
        return render_template('login.html', error='Kullanıcı adı veya şifre hatalı!')
    
    return render_template('login.html')


# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# Kullanıcı paneli
@app.route('/user')
def user_panel():
    return render_template('user_panel.html')


# Yönetici paneli (korumalı)
@app.route('/admin')
@login_required
def admin_panel():
    admin = Admin.query.get(session.get('admin_id'))
    return render_template('admin_panel.html', admin=admin)


# ==================== ADMİN YÖNETİMİ API ====================

@app.route('/api/admins', methods=['GET'])
@login_required
def get_admins():
    """Tüm adminleri getir (sadece superadmin)"""
    if not session.get('is_superadmin'):
        return jsonify({'error': 'Yetkiniz yok'}), 403
    admins = Admin.query.all()
    return jsonify([a.to_dict() for a in admins])


@app.route('/api/admins', methods=['POST'])
@login_required
def add_admin():
    """Yeni admin ekle (sadece superadmin)"""
    if not session.get('is_superadmin'):
        return jsonify({'error': 'Yetkiniz yok'}), 403
    
    data = request.get_json()
    
    if Admin.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Bu kullanıcı adı zaten kullanılıyor'}), 400
    
    admin = Admin(
        username=data['username'],
        full_name=data.get('full_name', ''),
        email=data.get('email', ''),
        is_superadmin=data.get('is_superadmin', False)
    )
    admin.set_password(data['password'])
    
    db.session.add(admin)
    db.session.commit()
    
    return jsonify(admin.to_dict()), 201


@app.route('/api/admins/<int:admin_id>', methods=['DELETE'])
@login_required
def delete_admin(admin_id):
    """Admin sil (sadece superadmin)"""
    if not session.get('is_superadmin'):
        return jsonify({'error': 'Yetkiniz yok'}), 403
    
    if admin_id == session.get('admin_id'):
        return jsonify({'error': 'Kendinizi silemezsiniz'}), 400
    
    admin = Admin.query.get_or_404(admin_id)
    db.session.delete(admin)
    db.session.commit()
    
    return jsonify({'message': 'Admin silindi'})


@app.route('/api/admins/change-password', methods=['POST'])
@login_required
def change_password():
    """Şifre değiştir"""
    data = request.get_json()
    admin = Admin.query.get(session.get('admin_id'))
    
    if not admin.check_password(data['current_password']):
        return jsonify({'error': 'Mevcut şifre hatalı'}), 400
    
    admin.set_password(data['new_password'])
    db.session.commit()
    
    return jsonify({'message': 'Şifre değiştirildi'})


@app.route('/api/current-admin', methods=['GET'])
@login_required
def get_current_admin():
    """Giriş yapmış admin bilgisi"""
    admin = Admin.query.get(session.get('admin_id'))
    return jsonify(admin.to_dict())


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


@app.route('/api/vehicles/<int:id>', methods=['PUT'])
def update_vehicle(id):
    """Araç güncelle"""
    vehicle = Vehicle.query.get_or_404(id)
    data = request.json
    
    if 'name' in data:
        vehicle.name = data['name']
    if 'capacity' in data:
        vehicle.capacity = float(data['capacity'])
    if 'cost_per_km' in data:
        vehicle.cost_per_km = float(data['cost_per_km'])
    if 'is_available' in data:
        vehicle.is_available = data['is_available']
    
    db.session.commit()
    return jsonify(vehicle.to_dict())


@app.route('/api/vehicles/<int:id>', methods=['DELETE'])
def delete_vehicle(id):
    """Araç sil"""
    vehicle = Vehicle.query.get_or_404(id)
    
    # Aktif kargolara atanmış araçlar silinemez
    active_cargos = Cargo.query.filter_by(vehicle_id=id).filter(
        Cargo.status.in_(['pending', 'in_transit'])
    ).count()
    
    if active_cargos > 0:
        return jsonify({'error': f'Bu araçta {active_cargos} aktif kargo var, silinemez'}), 400
    
    db.session.delete(vehicle)
    db.session.commit()
    return jsonify({'message': 'Araç silindi'}), 200


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
    """
    Yeni kargo ekle
    
    SENARYO: Kocaeli ilçelerinden Kocaeli Üniversitesi'ne kargo gönderimi
    - Kaynak (source): İlçe seçilir
    - Hedef (dest): Her zaman Kocaeli Üniversitesi (otomatik)
    """
    data = request.json
    
    # Validasyon: Gönderici ve alıcı adı zorunlu
    if not data.get('sender_name') or not data.get('sender_name').strip():
        return jsonify({'error': 'Gönderici adı zorunludur'}), 400
    if not data.get('receiver_name') or not data.get('receiver_name').strip():
        return jsonify({'error': 'Alıcı adı (Üniversitedeki) zorunludur'}), 400
    
    # Validasyon: Ağırlık pozitif olmalı
    weight = data.get('weight')
    if not weight or float(weight) <= 0:
        return jsonify({'error': 'Kargo ağırlığı pozitif bir sayı olmalıdır'}), 400
    if float(weight) > 1000:
        return jsonify({'error': 'Maksimum kargo ağırlığı 1000 kg olabilir'}), 400
    
    # Validasyon: Kaynak istasyon (ilçe) tanımlı olmalı
    source_station_id = data.get('source_station_id')
    if not source_station_id:
        return jsonify({'error': 'Kargonun gönderileceği ilçe seçilmelidir'}), 400
    source_station = Station.query.get(source_station_id)
    if not source_station:
        return jsonify({'error': 'Geçersiz ilçe. Tanımlı bir ilçe seçiniz.'}), 400
    if source_station.is_depot:
        return jsonify({'error': 'Kaynak olarak Kocaeli Üniversitesi seçilemez. Bir ilçe seçiniz.'}), 400
    
    # Hedef her zaman Kocaeli Üniversitesi (depo)
    depot = Station.query.filter_by(is_depot=True).first()
    if not depot:
        return jsonify({'error': 'Sistem hatası: Kocaeli Üniversitesi tanımlı değil'}), 500
    
    dest_station_id = depot.id
    
    # Validasyon: Teslimat tarihi geçmiş olamaz
    delivery_date = None
    if data.get('delivery_date'):
        try:
            delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d').date()
            from datetime import date
            if delivery_date < date.today():
                return jsonify({'error': 'Teslimat tarihi bugünden önce olamaz'}), 400
        except ValueError:
            return jsonify({'error': 'Geçersiz tarih formatı. YYYY-MM-DD formatında giriniz.'}), 400
    
    cargo = Cargo(
        sender_name=data['sender_name'].strip(),
        receiver_name=data['receiver_name'].strip(),
        weight=float(weight),
        source_station_id=source_station_id,
        dest_station_id=dest_station_id,  # Her zaman Kocaeli Üniversitesi
        is_accepted=True,
        delivery_date=delivery_date
    )
    db.session.add(cargo)
    db.session.commit()
    return jsonify(cargo.to_dict()), 201


@app.route('/api/cargos/<int:id>', methods=['GET'])
def get_cargo(id):
    """Kargo detayı getir"""
    cargo = Cargo.query.get_or_404(id)
    return jsonify(cargo.to_dict())


@app.route('/api/cargos/<int:id>', methods=['DELETE'])
def delete_cargo(id):
    """Tek bir kargoyu sil"""
    cargo = Cargo.query.get_or_404(id)
    
    db.session.delete(cargo)
    db.session.commit()
    return jsonify({'message': 'Kargo başarıyla silindi', 'id': id})


@app.route('/api/cargos/bulk-delete', methods=['POST'])
def bulk_delete_cargos():
    """Toplu kargo silme"""
    data = request.json
    cargo_ids = data.get('ids', [])
    
    if not cargo_ids:
        return jsonify({'error': 'Silinecek kargo seçilmedi'}), 400
    
    deleted_count = 0
    errors = []
    
    for cargo_id in cargo_ids:
        cargo = Cargo.query.get(cargo_id)
        if cargo:
            db.session.delete(cargo)
            deleted_count += 1
        else:
            errors.append(f'Kargo #{cargo_id} bulunamadı')
    
    db.session.commit()
    
    return jsonify({
        'message': f'{deleted_count} kargo silindi',
        'deleted_count': deleted_count,
        'errors': errors
    })


@app.route('/api/cargos/delete-all', methods=['DELETE'])
def delete_all_cargos():
    """Tüm kargoları ve ilgili sefer kayıtlarını sil"""
    cargo_count = Cargo.query.count()
    trip_count = Trip.query.count()
    route_count = Route.query.count()
    
    # Önce Trip kayıtlarını sil
    Trip.query.delete()
    
    # Sonra Route kayıtlarını sil
    Route.query.delete()
    
    # Kiralık araçları sil
    Vehicle.query.filter_by(is_rental=True).delete()
    
    # En son kargoları sil
    Cargo.query.delete()
    
    db.session.commit()
    
    return jsonify({
        'message': f'Tüm veriler silindi',
        'deleted': {
            'cargos': cargo_count,
            'trips': trip_count,
            'routes': route_count
        }
    })


@app.route('/api/cargos/track/<int:id>', methods=['GET'])
def track_cargo(id):
    """Kargo takibi"""
    cargo = Cargo.query.get_or_404(id)
    result = cargo.to_dict()
    
    # Eğer araç atanmışsa, rota bilgisini de ekle (planned veya in_progress)
    if cargo.vehicle_id:
        route = Route.query.filter_by(
            vehicle_id=cargo.vehicle_id
        ).filter(Route.status.in_(['planned', 'in_progress'])).order_by(Route.date.desc()).first()
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
    """
    Genetik Algoritma ile rota optimizasyonu
    
    SENARYO: Kocaeli ilçelerinden Kocaeli Üniversitesi'ne kargo toplama
    
    İKİ PROBLEM:
    1. SINIRSIZ ARAÇ PROBLEMİ (unlimited_vehicles):
       - Minimum maliyetle kaç araç ile taşıma tamamlanabilir?
       - Tüm kargolar kabul edilir
       - Kapasite aşılırsa araç kiralanır (200 birim/500kg)
       - Hedef: Toplam taşıma maliyetini minimize et
       
    2. BELİRLİ SAYIDA ARAÇ PROBLEMİ (fixed_vehicles):
       - Minimum maliyet, maksimum kargo güzergahı
       - Kapasite aşılırsa bazı kargolar reddedilir
       - max_count: Maksimum kargo SAYISI (önce hafif kargolar)
       - max_weight: Maksimum kargo AĞIRLIĞI (önce ağır kargolar)
    """
    from algorithms.genetic_algorithm import GeneticAlgorithmCVRP
    from algorithms.distance_calculator import road_distance, calculate_route_with_coordinates, get_network
    import json
    from datetime import date
    
    data = request.json
    target_date = datetime.strptime(data.get('date', date.today().isoformat()), '%Y-%m-%d').date()
    optimization_mode = data.get('mode', 'unlimited_vehicles')
    max_criteria = data.get('accept_criteria', 'max_weight')
    
    # Bekleyen kargoları al
    pending_cargos = Cargo.query.filter(
        (Cargo.status == 'pending') &
        ((Cargo.delivery_date == None) | (Cargo.delivery_date <= target_date))
    ).all()
    
    if not pending_cargos:
        return jsonify({'message': 'Bekleyen kargo yok'}), 400
    
    # İstasyon bazlı kargo özeti (KAYNAK istasyona göre - ilçeler)
    station_summary = {}
    for cargo in pending_cargos:
        source_id = cargo.source_station_id
        if source_id not in station_summary:
            station_summary[source_id] = {'count': 0, 'weight': 0, 'cargos': []}
        station_summary[source_id]['count'] += 1
        station_summary[source_id]['weight'] += cargo.weight
        station_summary[source_id]['cargos'].append(cargo)
    
    # Mevcut araçları al (kiralık olmayanlar)
    own_vehicles = Vehicle.query.filter_by(is_available=True, is_rental=False).all()
    vehicles_to_use = list(own_vehicles)
    
    # İstasyonları al
    stations = Station.query.all()
    depot = Station.query.filter_by(is_depot=True).first()
    
    if not depot:
        return jsonify({'message': 'Depo (Kocaeli Üniversitesi) bulunamadı'}), 400
    
    # Mesafe matrisini yol ağı üzerinden dinamik hesapla
    distance_matrix = {}
    for s1 in stations:
        distance_matrix[s1.id] = {}
        for s2 in stations:
            if s1.id == s2.id:
                distance_matrix[s1.id][s2.id] = 0
            else:
                distance_matrix[s1.id][s2.id] = road_distance(
                    (s1.latitude, s1.longitude),
                    (s2.latitude, s2.longitude)
                )
    
    # Toplam bilgiler
    total_weight = sum(c.weight for c in pending_cargos)
    total_count = len(pending_cargos)
    total_capacity = sum(v.capacity for v in own_vehicles)
    
    rental_vehicles = []
    accepted_cargos = list(pending_cargos)
    rejected_cargos = []
    
    # ==================== SENARYO 1: SINIRSIZ ARAÇ PROBLEMİ ====================
    # Minimum maliyetle kaç araç ile taşıma tamamlanabilir?
    if optimization_mode == 'unlimited_vehicles':
        # Kapasite yetersizse kiralık araç ekle
        if total_weight > total_capacity:
            needed_capacity = total_weight - total_capacity
            rental_count = int(needed_capacity / 500) + 1  # Her kiralık araç 500kg
            
            for i in range(rental_count):
                rental = Vehicle(
                    name=f'Kiralık Araç {i+1} (500kg)',
                    capacity=500,
                    cost_per_km=1.0,  # Yol maliyeti: 1 birim/km
                    is_rental=True,
                    rental_cost=200  # Kiralama maliyeti: 200 birim
                )
                db.session.add(rental)
                rental_vehicles.append(rental)
            
            db.session.flush()
            vehicles_to_use.extend(rental_vehicles)
        
        # Tüm kargolar kabul edilir
        accepted_cargos = list(pending_cargos)
        for cargo in accepted_cargos:
            cargo.is_accepted = True
    
    # ==================== SENARYO 2: BELİRLİ SAYIDA ARAÇ PROBLEMİ ====================
    # Minimum maliyet, maksimum kargo güzergahı - hangi kargolar kabul edilsin?
    elif optimization_mode == 'fixed_vehicles':
        if total_weight <= total_capacity:
            # Kapasite yeterli - tüm kargolar kabul
            accepted_cargos = list(pending_cargos)
            for cargo in accepted_cargos:
                cargo.is_accepted = True
        else:
            # Kapasite yetersiz - kargo seçimi yap
            if max_criteria == 'max_count':
                # Maksimum kargo SAYISI - Önce en hafif kargoları al (daha fazla kargo sığar)
                sorted_cargos = sorted(pending_cargos, key=lambda c: c.weight)
            else:  # max_weight
                # Maksimum kargo AĞIRLIĞI - Önce en ağır kargoları al
                sorted_cargos = sorted(pending_cargos, key=lambda c: c.weight, reverse=True)
            
            # Kapasiteye sığacak kadar kargo seç
            current_weight = 0
            accepted_cargos = []
            
            for cargo in sorted_cargos:
                if current_weight + cargo.weight <= total_capacity:
                    accepted_cargos.append(cargo)
                    cargo.is_accepted = True
                    current_weight += cargo.weight
                else:
                    rejected_cargos.append(cargo)
                    cargo.is_accepted = False
                    cargo.status = 'rejected'
    
    if not accepted_cargos:
        return jsonify({'message': 'Kabul edilebilecek kargo yok'}), 400
    
    # Genetik Algoritma ile optimizasyon
    ga = GeneticAlgorithmCVRP(
        stations=stations,
        vehicles=vehicles_to_use,
        cargos=accepted_cargos,
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
        
        # A* ile yol koordinatlarını hesapla
        route_coords = [(depot.latitude, depot.longitude)] + [(s.latitude, s.longitude) for s in route_stations]
        route_result = calculate_route_with_coordinates(
            route_coords[0],
            route_coords[1:]
        )
        path_coords = route_result.get('coordinates', [])
        
        # Rotadaki kargolar (KAYNAK istasyona göre)
        route_cargos = []
        route_total_weight = 0
        for cargo in accepted_cargos:
            if cargo.source_station_id in route_station_ids:
                cargo.vehicle_id = vehicle_id
                cargo.status = 'in_transit'
                cargo.is_accepted = True
                route_cargos.append({
                    'id': cargo.id,
                    'sender': cargo.sender_name,
                    'receiver': cargo.receiver_name,
                    'weight': cargo.weight,
                    'source': cargo.source_station.name  # Kaynak ilçe
                })
                route_total_weight += cargo.weight
        
        # Rota detayları
        route_details = {
            'stations': [{'id': s.id, 'name': s.name, 'lat': s.latitude, 'lng': s.longitude} for s in route_stations],
            'stops': [{'station_id': s.id, 'station_name': s.name, 'latitude': s.latitude, 'longitude': s.longitude} for s in route_stations],
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
        db.session.flush()
        
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
    total_fuel_cost = sum(t.fuel_cost for t in created_trips)
    total_distance = sum(t.total_distance for t in created_trips)
    accepted_weight = sum(c.weight for c in accepted_cargos)
    rejected_weight = sum(c.weight for c in rejected_cargos)
    
    # Kapasite kullanım oranı
    used_capacity = sum(v.capacity for v in vehicles_to_use)
    capacity_utilization = (accepted_weight / used_capacity * 100) if used_capacity > 0 else 0
    
    # Araç bazlı detaylar
    vehicle_details = []
    for trip in created_trips:
        vehicle = Vehicle.query.get(trip.vehicle_id)
        if vehicle:
            vehicle_details.append({
                'vehicle_name': vehicle.name,
                'capacity': vehicle.capacity,
                'load': trip.total_weight,
                'utilization': round((trip.total_weight / vehicle.capacity * 100), 1) if vehicle.capacity > 0 else 0,
                'distance': round(trip.total_distance, 2),
                'fuel_cost': round(trip.fuel_cost, 2),
                'rental_cost': round(trip.rental_cost, 2),
                'total_cost': round(trip.total_cost, 2),
                'cargo_count': trip.cargo_count,
                'is_rental': vehicle.is_rental
            })
    
    result = {
        'mode': optimization_mode,
        'mode_description': 'Sınırsız Araç - Tüm kargolar taşınır' if optimization_mode == 'unlimited_vehicles' else 'Belirli Araç - Sabit filolar',
        
        # Maliyet bilgileri
        'total_cost': round(best_cost, 2),
        'fuel_cost': round(total_fuel_cost, 2),
        'rental_cost': round(total_rental_cost, 2),
        
        # Mesafe bilgileri
        'total_distance': round(total_distance, 2),
        
        # Araç bilgileri
        'own_vehicles_count': len(own_vehicles),
        'rented_vehicles': len(rental_vehicles),
        'total_vehicles_used': len([t for t in created_trips if t.total_weight > 0]),
        'total_capacity': used_capacity,
        'capacity_utilization': round(capacity_utilization, 1),
        
        # Kargo bilgileri
        'total_cargo_count': total_count,
        'total_cargo_weight': total_weight,
        'accepted_count': len(accepted_cargos),
        'accepted_weight': accepted_weight,
        'rejected_count': len(rejected_cargos),
        'rejected_weight': rejected_weight,
        
        # Detaylı veriler
        'vehicle_details': vehicle_details,
        'routes': [r.to_dict() for r in created_routes],
        'trips': [t.to_dict() for t in created_trips],
        'rejected_cargo_list': [{'id': c.id, 'weight': c.weight, 'sender': c.sender_name, 'source': c.source_station.name if c.source_station else ''} for c in rejected_cargos],
        'station_summary': {str(k): {'count': v['count'], 'weight': v['weight']} for k, v in station_summary.items()}
    }
    
    return jsonify(result)


@app.route('/api/routes/<int:id>/start', methods=['POST'])
def start_route(id):
    """Rotayı başlat"""
    route = Route.query.get_or_404(id)
    route.status = 'in_progress'
    
    # Sefer kaydını da başlat
    trip = Trip.query.filter_by(route_id=id).first()
    if trip:
        trip.status = 'in_progress'
        trip.start_time = datetime.utcnow()
    
    # Bu araçtaki kargoları "taşımada" olarak işaretle
    cargos = Cargo.query.filter_by(vehicle_id=route.vehicle_id, status='pending').all()
    for cargo in cargos:
        cargo.status = 'in_transit'
    
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


@app.route('/api/trips/delete-all', methods=['DELETE'])
def delete_all_trips():
    """Tüm sefer ve rota kayıtlarını sil"""
    trip_count = Trip.query.count()
    route_count = Route.query.count()
    
    # Kargolardaki araç atamalarını temizle
    Cargo.query.update({Cargo.vehicle_id: None, Cargo.status: 'pending'})
    
    # Sefer ve rotaları sil
    Trip.query.delete()
    Route.query.delete()
    
    # Kiralık araçları sil
    rental_count = Vehicle.query.filter_by(is_rental=True).count()
    Vehicle.query.filter_by(is_rental=True).delete()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Tüm seferler ve rotalar silindi',
        'deleted': {
            'trips': trip_count,
            'routes': route_count,
            'rental_vehicles': rental_count
        }
    })


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
    
    # Bu araçtaki kargoları "taşımada" olarak işaretle
    cargos = Cargo.query.filter_by(vehicle_id=trip.vehicle_id, status='pending').all()
    for cargo in cargos:
        cargo.status = 'in_transit'
    
    db.session.commit()
    return jsonify(trip.to_dict())


@app.route('/api/trips/<int:id>/complete', methods=['POST'])
def complete_trip(id):
    """Seferi tamamla"""
    trip = Trip.query.get_or_404(id)
    trip.status = 'completed'
    trip.end_time = datetime.utcnow()
    
    # İlgili rotayı da tamamla
    route = Route.query.get(trip.route_id)
    if route:
        route.status = 'completed'
    
    # Bu araçtaki taşımada olan kargoları "teslim edildi" olarak işaretle
    cargos = Cargo.query.filter_by(vehicle_id=trip.vehicle_id, status='in_transit').all()
    for cargo in cargos:
        cargo.status = 'delivered'
    
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
        from algorithms.distance_calculator import calculate_route_with_coordinates
        depot = Station.query.filter_by(is_depot=True).first()
        
        path_coords = []
        if depot and stops:
            route_result = calculate_route_with_coordinates(
                (depot.latitude, depot.longitude),
                [(s['latitude'], s['longitude']) for s in stops]
            )
            path_coords = route_result.get('coordinates', [])
        
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
    """Mesafe matrisini getir - yol ağı üzerinden hesaplanır"""
    from algorithms.distance_calculator import road_distance
    stations = Station.query.all()
    matrix = {}
    for s1 in stations:
        matrix[s1.id] = {}
        for s2 in stations:
            if s1.id == s2.id:
                matrix[s1.id][s2.id] = 0
            else:
                matrix[s1.id][s2.id] = road_distance(
                    (s1.latitude, s1.longitude),
                    (s2.latitude, s2.longitude)
                )
    return jsonify(matrix)


# ==================== ANALİZ API ====================

@app.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Genel özet analiz"""
    total_cargos = Cargo.query.count()
    pending_cargos = Cargo.query.filter_by(status='pending').count()
    delivered_cargos = Cargo.query.filter_by(status='delivered').count()
    in_transit = Cargo.query.filter_by(status='in_transit').count()
    rejected_cargos = Cargo.query.filter_by(status='rejected').count()
    
    total_routes = Route.query.count()
    completed_routes = Route.query.filter_by(status='completed').count()
    active_routes = Route.query.filter(Route.status.in_(['planned', 'in_progress'])).count()
    
    # Aktif araç sayısı (mevcut filo + kiralık)
    total_vehicles = Vehicle.query.filter_by(is_available=True).count()
    own_vehicles = Vehicle.query.filter_by(is_available=True, is_rental=False).count()
    rental_vehicles = Vehicle.query.filter_by(is_available=True, is_rental=True).count()
    
    # Aktif seferlerdeki araçlar
    active_vehicle_ids = db.session.query(Trip.vehicle_id).filter(
        Trip.status.in_(['planned', 'in_progress'])
    ).distinct().count()
    
    total_cost = db.session.query(db.func.sum(Route.total_cost)).scalar() or 0
    total_distance = db.session.query(db.func.sum(Route.total_distance)).scalar() or 0
    
    return jsonify({
        'total_cargos': total_cargos,
        'pending_cargos': pending_cargos,
        'delivered_cargos': delivered_cargos,
        'in_transit': in_transit,
        'rejected_cargos': rejected_cargos,
        'total_routes': total_routes,
        'completed_routes': completed_routes,
        'active_routes': active_routes,
        'total_vehicles': total_vehicles,
        'own_vehicles': own_vehicles,
        'rental_vehicles': rental_vehicles,
        'active_vehicles': active_vehicle_ids,
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
    total_distance = 0
    
    for trip in trips:
        fuel_cost += trip.fuel_cost or 0
        rental_cost += trip.rental_cost or 0
        total_distance += trip.total_distance or 0
    
    return jsonify({
        'fuel_cost': round(fuel_cost, 2),
        'rental_cost': round(rental_cost, 2),
        'total_cost': round(fuel_cost + rental_cost, 2),
        'total_distance': round(total_distance, 2)
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
    """
    İstasyon bazlı kargo özeti
    Kargolar ilçelerden (source) Üniversite'ye gönderiliyor
    """
    stations = Station.query.filter_by(is_depot=False).all()  # Sadece ilçeler
    result = []
    
    for station in stations:
        # Kaynak istasyona göre bekleyen kargolar
        pending_cargos = Cargo.query.filter(
            (Cargo.source_station_id == station.id) &
            (Cargo.status == 'pending')
        ).all()
        
        result.append({
            'station': station.to_dict(),
            'station_name': station.name,  # Frontend için eklendi
            'station_id': station.id,
            'cargo_count': len(pending_cargos),
            'total_weight': sum(c.weight for c in pending_cargos),
            'cargos': [c.to_dict() for c in pending_cargos]
        })
    
    return jsonify(result)


# ==================== PARAMETRE API ====================

@app.route('/api/parameters', methods=['GET'])
def get_parameters():
    """
    Sistem parametrelerini getir
    Problem gereksinimleri:
    - Yol maliyeti: km başına 1 birim
    - Araç kapasiteleri: 500, 750, 1000 kg
    - Kiralık araç: 200 birim (500 kg kapasiteli)
    """
    vehicles = Vehicle.query.filter_by(is_rental=False).all()
    
    return jsonify({
        'cost_per_km': 1.0,  # Km başına maliyet (birim)
        'rental_cost': 200,  # Kiralık araç maliyeti (birim)
        'rental_capacity': 500,  # Kiralık araç kapasitesi (kg)
        'own_vehicles': [v.to_dict() for v in vehicles],
        'total_own_capacity': sum(v.capacity for v in vehicles)
    })


@app.route('/api/parameters', methods=['PUT'])
def update_parameters():
    """
    Sistem parametrelerini güncelle
    Parametreler değiştirilebilir olmalı
    """
    data = request.json
    
    # Araç parametrelerini güncelle
    if 'vehicles' in data:
        for v_data in data['vehicles']:
            vehicle = Vehicle.query.get(v_data.get('id'))
            if vehicle:
                if 'capacity' in v_data:
                    vehicle.capacity = float(v_data['capacity'])
                if 'cost_per_km' in v_data:
                    vehicle.cost_per_km = float(v_data['cost_per_km'])
    
    db.session.commit()
    return jsonify({'message': 'Parametreler güncellendi'})


@app.route('/api/vehicles/rent', methods=['POST'])
def rent_vehicle():
    """
    Yeni kiralık araç ekle
    Kiralık araç: 200 birim, 500 kg kapasiteli
    """
    data = request.json
    count = data.get('count', 1)
    
    rented = []
    for i in range(count):
        vehicle = Vehicle(
            name=f'Kiralık Araç (500kg)',
            capacity=500,
            cost_per_km=1.0,
            is_rental=True,
            rental_cost=200,
            is_available=True
        )
        db.session.add(vehicle)
        rented.append(vehicle)
    
    db.session.commit()
    return jsonify({
        'message': f'{count} adet araç kiralandı',
        'vehicles': [v.to_dict() for v in rented],
        'total_rental_cost': count * 200
    })


@app.route('/api/vehicles/rental', methods=['DELETE'])
def remove_rental_vehicles():
    """Tüm kiralık araçları sil"""
    Vehicle.query.filter_by(is_rental=True).delete()
    db.session.commit()
    return jsonify({'message': 'Kiralık araçlar silindi'})


# ==================== SENARYO YÜKLEYİCİ API ====================

# PDF'deki 4 örnek senaryo verisi
SCENARIO_DATA = {
    1: {
        'name': 'Senaryo 1 - Orta Yük (1445 kg, 113 kargo)',
        'description': 'Mevcut kapasite (2250 kg) yeterli, kiralama gerekmez. Rota optimizasyonu önemli.',
        'total_weight': 1445,
        'total_count': 113,
        'cargos': [
            {'source': 'Başiskele', 'count': 10, 'weight': 120},
            {'source': 'Çayırova', 'count': 8, 'weight': 80},
            {'source': 'Darıca', 'count': 15, 'weight': 200},
            {'source': 'Derince', 'count': 10, 'weight': 150},
            {'source': 'Dilovası', 'count': 12, 'weight': 180},
            {'source': 'Gebze', 'count': 5, 'weight': 70},
            {'source': 'Gölcük', 'count': 7, 'weight': 90},
            {'source': 'Kandıra', 'count': 6, 'weight': 60},
            {'source': 'Karamürsel', 'count': 9, 'weight': 110},
            {'source': 'Kartepe', 'count': 11, 'weight': 130},
            {'source': 'Körfez', 'count': 6, 'weight': 75},
            {'source': 'İzmit', 'count': 14, 'weight': 160}
        ]
    },
    2: {
        'name': 'Senaryo 2 - Dengesiz Dağılım (905 kg, 118 kargo)',
        'description': 'Kapasite yeterli ama kargo yoğunluğu dengesiz. Rota optimizasyonu kritik.',
        'total_weight': 905,
        'total_count': 118,
        'cargos': [
            {'source': 'Başiskele', 'count': 40, 'weight': 200},
            {'source': 'Çayırova', 'count': 35, 'weight': 175},
            {'source': 'Darıca', 'count': 10, 'weight': 150},
            {'source': 'Derince', 'count': 5, 'weight': 100},
            {'source': 'Dilovası', 'count': 0, 'weight': 0},
            {'source': 'Gebze', 'count': 8, 'weight': 120},
            {'source': 'Gölcük', 'count': 0, 'weight': 0},
            {'source': 'Kandıra', 'count': 0, 'weight': 0},
            {'source': 'Karamürsel', 'count': 0, 'weight': 0},
            {'source': 'Kartepe', 'count': 0, 'weight': 0},
            {'source': 'Körfez', 'count': 0, 'weight': 0},
            {'source': 'İzmit', 'count': 20, 'weight': 160}
        ]
    },
    3: {
        'name': 'Senaryo 3 - Kapasite Aşımı (2700 kg, 17 kargo)',
        'description': 'Kapasite (2250 kg) aşılıyor, en az 1 araç kiralanmalı. Ağır kargolar birkaç ilçede yoğunlaşmış.',
        'total_weight': 2700,
        'total_count': 17,
        'cargos': [
            {'source': 'Başiskele', 'count': 0, 'weight': 0},
            {'source': 'Çayırova', 'count': 3, 'weight': 700},
            {'source': 'Darıca', 'count': 0, 'weight': 0},
            {'source': 'Derince', 'count': 0, 'weight': 0},
            {'source': 'Dilovası', 'count': 4, 'weight': 800},
            {'source': 'Gebze', 'count': 5, 'weight': 900},
            {'source': 'Gölcük', 'count': 0, 'weight': 0},
            {'source': 'Kandıra', 'count': 0, 'weight': 0},
            {'source': 'Karamürsel', 'count': 0, 'weight': 0},
            {'source': 'Kartepe', 'count': 0, 'weight': 0},
            {'source': 'Körfez', 'count': 0, 'weight': 0},
            {'source': 'İzmit', 'count': 5, 'weight': 300}
        ]
    },
    4: {
        'name': 'Senaryo 4 - Yoğun Hafif Yük (1150 kg, 88 kargo)',
        'description': 'Kapasite yeterli. 3 araç ile sefer düzenlenebilir, minimum maliyet hedefi.',
        'total_weight': 1150,
        'total_count': 88,
        'cargos': [
            {'source': 'Başiskele', 'count': 30, 'weight': 300},
            {'source': 'Çayırova', 'count': 0, 'weight': 0},
            {'source': 'Darıca', 'count': 0, 'weight': 0},
            {'source': 'Derince', 'count': 0, 'weight': 0},
            {'source': 'Dilovası', 'count': 0, 'weight': 0},
            {'source': 'Gebze', 'count': 0, 'weight': 0},
            {'source': 'Gölcük', 'count': 15, 'weight': 220},
            {'source': 'Kandıra', 'count': 5, 'weight': 250},
            {'source': 'Karamürsel', 'count': 20, 'weight': 180},
            {'source': 'Kartepe', 'count': 10, 'weight': 200},
            {'source': 'Körfez', 'count': 8, 'weight': 400},
            {'source': 'İzmit', 'count': 0, 'weight': 0}
        ]
    }
}


@app.route('/api/scenarios/load/<int:scenario_id>', methods=['POST'])
def load_scenario(scenario_id):
    """
    Belirli bir senaryonun kargolarını veritabanına yükle
    Mevcut bekleyen kargolar silinir, yeni senaryo kargoları eklenir
    """
    if scenario_id not in SCENARIO_DATA:
        return jsonify({'error': f'Senaryo {scenario_id} bulunamadı'}), 404
    
    scenario = SCENARIO_DATA[scenario_id]
    
    # Mevcut bekleyen kargoları sil
    Cargo.query.filter_by(status='pending').delete()
    
    # Kiralık araçları sil
    Vehicle.query.filter_by(is_rental=True).delete()
    
    # Eski rotaları ve seferleri sil
    Trip.query.delete()
    Route.query.delete()
    
    # İstasyon haritası
    stations = Station.query.all()
    station_map = {s.name: s for s in stations}
    depot = Station.query.filter_by(is_depot=True).first()
    
    # Senaryo kargolarını ekle
    cargo_count = 0
    total_weight = 0
    
    for cargo_data in scenario['cargos']:
        source_name = cargo_data['source']
        source = station_map.get(source_name)
        
        if not source or cargo_data['count'] == 0:
            continue
        
        # Her ilçe için kargo ağırlığını kargo sayısına böl
        weight_per_cargo = cargo_data['weight'] / cargo_data['count'] if cargo_data['count'] > 0 else 0
        
        for i in range(cargo_data['count']):
            cargo = Cargo(
                sender_name=f'Gönderici {source_name} #{i+1}',
                receiver_name=f'Üniversite Alıcı #{cargo_count+1}',
                weight=round(weight_per_cargo, 1),
                source_station_id=source.id,
                dest_station_id=depot.id,
                status='pending',
                is_accepted=True
            )
            db.session.add(cargo)
            cargo_count += 1
            total_weight += weight_per_cargo
    
    db.session.commit()
    
    return jsonify({
        'message': f'{scenario["name"]} yüklendi',
        'scenario_id': scenario_id,
        'scenario_name': scenario['name'],
        'description': scenario['description'],
        'cargo_count': cargo_count,
        'total_weight': round(total_weight, 1),
        'expected_weight': scenario['total_weight'],
        'expected_count': scenario['total_count']
    })


@app.route('/api/scenarios/list', methods=['GET'])
def list_scenarios():
    """Mevcut senaryoları listele"""
    scenarios = []
    total_capacity = sum(v.capacity for v in Vehicle.query.filter_by(is_rental=False).all())
    
    for id, data in SCENARIO_DATA.items():
        scenarios.append({
            'id': id,
            'name': data['name'],
            'description': data['description'],
            'total_weight': data['total_weight'],
            'total_count': data['total_count'],
            'rental_needed': data['total_weight'] > total_capacity,
            'capacity_status': 'Yeterli' if data['total_weight'] <= total_capacity else 'Aşım'
        })
    
    return jsonify({
        'scenarios': scenarios,
        'total_capacity': total_capacity,
        'vehicle_count': Vehicle.query.filter_by(is_rental=False).count()
    })


@app.route('/api/analytics/scenario-summary', methods=['GET'])
def get_scenario_summary():
    """Tüm senaryolar için özet tablo"""
    total_capacity = sum(v.capacity for v in Vehicle.query.filter_by(is_rental=False).all())
    
    scenarios = []
    for id, data in SCENARIO_DATA.items():
        scenarios.append({
            'id': id,
            'name': data['name'],
            'description': data['description'],
            'cargo_count': data['total_count'],
            'estimated_weight': data['total_weight'],
            'rental_expected': data['total_weight'] > total_capacity,
            'difficulty': 'Kolay' if data['total_weight'] < total_capacity * 0.7 else ('Orta' if data['total_weight'] <= total_capacity else 'Zor')
        })
    
    return jsonify(scenarios)


# ==================== VERİTABANI BAŞLATMA ====================

def init_db():
    """Veritabanını başlat ve örnek verileri ekle"""
    with app.app_context():
        db.create_all()
        
        # Varsayılan Admin oluştur
        if Admin.query.count() == 0:
            admin = Admin(
                username='admin',
                full_name='Sistem Yöneticisi',
                email='admin@kocaeli.edu.tr',
                is_superadmin=True
            )
            admin.set_password('admin123')  # Varsayılan şifre
            db.session.add(admin)
            db.session.commit()
            print("Varsayılan admin oluşturuldu: admin / admin123")
        
        # Eğer istasyon yoksa, Kocaeli Üniversitesi (ana depo) ve ilçeleri ekle
        # Kargolar ilçelerden Kocaeli Üniversitesi'ne gelecek
        if Station.query.count() == 0:
            kocaeli_districts = [
                {'name': 'Kocaeli Üniversitesi', 'lat': 40.8225, 'lng': 29.9213, 'is_depot': True},  # Ana Depo - Umuttepe Kampüsü
                {'name': 'İzmit', 'lat': 40.7654, 'lng': 29.9408, 'is_depot': False},
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
                {'name': 'Başiskele', 'lat': 40.7381, 'lng': 30.0001, 'is_depot': False},
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
        
        # Eğer araç yoksa, varsayılan araçları ekle
        # Problem gereksinimleri: km başına 1 birim maliyet
        if Vehicle.query.count() == 0:
            vehicles = [
                {'name': 'Araç 1 (500kg)', 'capacity': 500, 'cost_per_km': 1.0},
                {'name': 'Araç 2 (750kg)', 'capacity': 750, 'cost_per_km': 1.0},
                {'name': 'Araç 3 (1000kg)', 'capacity': 1000, 'cost_per_km': 1.0},
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
    app.run(debug=False, port=5000)
