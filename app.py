"""
Kargo Dağıtım Sistemi - Ana Flask Uygulaması
CVRP (Capacitated Vehicle Routing Problem) çözümü için Genetik Algoritma kullanır
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kargo-sistem-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cargo_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ==================== YARDIMCI FONKSİYONLAR ====================

def hash_password(password):
    """Şifreyi SHA256 ile hashle"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_reset_token():
    """Şifre sıfırlama için token oluştur"""
    return secrets.token_urlsafe(32)


def login_required(f):
    """Admin girişi gerektiren decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def user_login_required(f):
    """Kullanıcı girişi gerektiren decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== VERİTABANI MODELLERİ ====================

class User(db.Model):
    """Kullanıcı modeli - Kargo gönderen kullanıcılar"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), default='user')  # 'user' veya 'admin'
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        self.password_hash = hash_password(password)
    
    def check_password(self, password):
        return self.password_hash == hash_password(password)
    
    def generate_reset_token(self):
        self.reset_token = generate_reset_token()
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Gönderen kullanıcı
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
    
    user = db.relationship('User', backref='cargos')
    source_station = db.relationship('Station', foreign_keys=[source_station_id])
    dest_station = db.relationship('Station', foreign_keys=[dest_station_id])
    vehicle = db.relationship('Vehicle')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
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


# ==================== AUTH ROUTES ====================

# Login sayfası
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        # Önce User tablosunda ara
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                return render_template('login.html', error='Hesabınız devre dışı bırakılmış!')
            
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_name'] = user.full_name
            session['user_role'] = user.role
            
            if remember:
                session.permanent = True
            
            # Role göre yönlendir
            if user.role == 'admin':
                session['admin_id'] = user.id
                session['is_superadmin'] = True
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('user_panel'))
        
        # Eski Admin tablosunda da kontrol et (geriye uyumluluk)
        admin = Admin.query.filter_by(username=email).first()
        if not admin:
            admin = Admin.query.filter_by(email=email).first()
        
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            session['is_superadmin'] = admin.is_superadmin
            session['user_role'] = 'admin'
            admin.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('admin_panel'))
        
        return render_template('login.html', error='E-posta veya şifre hatalı!')
    
    return render_template('login.html')


# Kayıt sayfası
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        # Validasyonlar
        if not all([full_name, email, password, password_confirm]):
            return render_template('register.html', error='Tüm zorunlu alanları doldurun!')
        
        if password != password_confirm:
            return render_template('register.html', error='Şifreler eşleşmiyor!')
        
        if len(password) < 6:
            return render_template('register.html', error='Şifre en az 6 karakter olmalı!')
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Bu e-posta adresi zaten kayıtlı!')
        
        # Yeni kullanıcı oluştur
        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            role='user'
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        return render_template('login.html', success='Kayıt başarılı! Giriş yapabilirsiniz.')
    
    return render_template('register.html')


# Şifremi Unuttum
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Reset token oluştur
            token = user.generate_reset_token()
            db.session.commit()
            
            # Gerçek projede e-posta gönderilir
            # send_reset_email(user.email, token)
            
            return render_template('forgot_password.html', 
                success=f'Şifre sıfırlama kodu: {token[:8]}... (Demo: kodun tamamı konsolda)',
                token=token)
        
        return render_template('forgot_password.html', error='Bu e-posta adresi kayıtlı değil!')
    
    return render_template('forgot_password.html')


# Şifre Sıfırlama
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        return render_template('login.html', error='Geçersiz veya süresi dolmuş token!')
    
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if password != password_confirm:
            return render_template('reset_password.html', token=token, error='Şifreler eşleşmiyor!')
        
        if len(password) < 6:
            return render_template('reset_password.html', token=token, error='Şifre en az 6 karakter olmalı!')
        
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        return render_template('login.html', success='Şifreniz değiştirildi! Giriş yapabilirsiniz.')
    
    return render_template('reset_password.html', token=token)


# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# Kullanıcı paneli
@app.route('/user')
@user_login_required
def user_panel():
    user = User.query.get(session.get('user_id'))
    return render_template('user_panel.html', user=user)


# Yönetici paneli (korumalı)
@app.route('/admin')
@login_required
def admin_panel():
    admin = Admin.query.get(session.get('admin_id'))
    user = User.query.get(session.get('user_id')) if session.get('user_id') else None
    return render_template('admin_panel.html', admin=admin, user=user)


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


# ==================== KULLANICI YÖNETİMİ API ====================

@app.route('/api/users', methods=['GET'])
@login_required
def get_users():
    """Tüm kullanıcıları getir (sadece admin)"""
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """Kullanıcı detayı getir"""
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """Kullanıcı güncelle"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if 'full_name' in data:
        user.full_name = data['full_name']
    if 'phone' in data:
        user.phone = data['phone']
    if 'role' in data:
        user.role = data['role']
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    db.session.commit()
    return jsonify(user.to_dict())


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Kullanıcı sil"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'Kullanıcı silindi'})


@app.route('/api/current-user', methods=['GET'])
@user_login_required
def get_current_user():
    """Giriş yapmış kullanıcı bilgisi"""
    user = User.query.get(session.get('user_id'))
    if user:
        return jsonify(user.to_dict())
    return jsonify({'error': 'Kullanıcı bulunamadı'}), 404


@app.route('/api/user/change-password', methods=['POST'])
@user_login_required
def user_change_password():
    """Kullanıcı şifre değiştir"""
    data = request.get_json()
    user = User.query.get(session.get('user_id'))
    
    if not user.check_password(data['current_password']):
        return jsonify({'error': 'Mevcut şifre hatalı'}), 400
    
    if len(data['new_password']) < 6:
        return jsonify({'error': 'Şifre en az 6 karakter olmalı'}), 400
    
    user.set_password(data['new_password'])
    db.session.commit()
    
    return jsonify({'message': 'Şifre değiştirildi'})


# ==================== İSTASYON API ====================

@app.route('/api/stations', methods=['GET'])
def get_stations():
    """Tüm istasyonları getir"""
    stations = Station.query.all()
    return jsonify([s.to_dict() for s in stations])


@app.route('/api/stations', methods=['POST'])
@login_required
def add_station():
    """Yeni istasyon ekle (Sadece admin)"""
    data = request.json
    
    # Validasyon
    if not data.get('name') or not data.get('name').strip():
        return jsonify({'error': 'İstasyon adı zorunludur'}), 400
    if not data.get('latitude') or not data.get('longitude'):
        return jsonify({'error': 'Koordinatlar zorunludur'}), 400
    
    # İsim kontrolü
    existing = Station.query.filter_by(name=data['name'].strip()).first()
    if existing:
        return jsonify({'error': 'Bu isimde bir istasyon zaten mevcut'}), 400
    
    station = Station(
        name=data['name'].strip(),
        latitude=float(data['latitude']),
        longitude=float(data['longitude']),
        is_depot=data.get('is_depot', False)
    )
    db.session.add(station)
    db.session.commit()
    
    return jsonify(station.to_dict()), 201


@app.route('/api/stations/<int:id>', methods=['PUT'])
@login_required
def update_station(id):
    """İstasyon güncelle (Sadece admin)"""
    station = Station.query.get_or_404(id)
    data = request.json
    
    if 'name' in data:
        # İsim değişikliğinde duplicate kontrolü
        existing = Station.query.filter(Station.name == data['name'].strip(), Station.id != id).first()
        if existing:
            return jsonify({'error': 'Bu isimde başka bir istasyon mevcut'}), 400
        station.name = data['name'].strip()
    
    if 'latitude' in data:
        station.latitude = float(data['latitude'])
    if 'longitude' in data:
        station.longitude = float(data['longitude'])
    if 'is_depot' in data:
        station.is_depot = data['is_depot']
    
    db.session.commit()
    return jsonify(station.to_dict())


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
    """Tüm kargoları getir (admin için) veya kullanıcının kargolarını getir"""
    if session.get('user_role') == 'admin' or session.get('admin_id'):
        # Admin tüm kargoları görebilir
        cargos = Cargo.query.all()
    elif session.get('user_id'):
        # Normal kullanıcı sadece kendi kargolarını görebilir
        cargos = Cargo.query.filter_by(user_id=session.get('user_id')).all()
    else:
        cargos = Cargo.query.all()
    return jsonify([c.to_dict() for c in cargos])


@app.route('/api/cargos/my', methods=['GET'])
@user_login_required
def get_my_cargos():
    """Giriş yapmış kullanıcının kargolarını getir"""
    cargos = Cargo.query.filter_by(user_id=session.get('user_id')).all()
    return jsonify([c.to_dict() for c in cargos])


@app.route('/api/cargos/pending', methods=['GET'])
def get_pending_cargos():
    """Bekleyen kargoları getir"""
    if session.get('user_role') == 'admin' or session.get('admin_id'):
        cargos = Cargo.query.filter_by(status='pending').all()
    elif session.get('user_id'):
        cargos = Cargo.query.filter_by(status='pending', user_id=session.get('user_id')).all()
    else:
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
    
    # Kullanıcı ID'sini al
    user_id = session.get('user_id')
    
    cargo = Cargo(
        user_id=user_id,
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


@app.route('/api/cargos/bulk-add', methods=['POST'])
def bulk_add_cargos():
    """
    Toplu kargo ekleme - Tek seferde birden fazla ilçeden kargo ekle
    
    Format:
    {
        "cargos": [
            {"station_name": "İzmit", "count": 15, "avg_weight": 10},
            {"station_name": "Darıca", "count": 20, "avg_weight": 12},
            ...
        ]
    }
    """
    import random
    
    data = request.json
    cargo_list = data.get('cargos', [])
    
    if not cargo_list:
        return jsonify({'error': 'Kargo listesi boş'}), 400
    
    # Hedef: Kocaeli Üniversitesi
    depot = Station.query.filter_by(is_depot=True).first()
    if not depot:
        return jsonify({'error': 'Kocaeli Üniversitesi tanımlı değil'}), 500
    
    total_added = 0
    errors = []
    
    # Örnek isimler
    sender_names = ['Ahmet', 'Mehmet', 'Ayşe', 'Fatma', 'Ali', 'Veli', 'Zeynep', 'Mustafa', 'Hasan', 'Hüseyin']
    receiver_names = ['Prof. Yılmaz', 'Doç. Kaya', 'Öğr. Gör. Demir', 'Arş. Gör. Çelik', 'Dr. Öztürk', 'Prof. Aydın', 'Doç. Şahin', 'Öğr. Gör. Arslan']
    
    for item in cargo_list:
        station_name = item.get('station_name')
        count = int(item.get('count', 0))
        avg_weight = float(item.get('avg_weight', 10))
        
        if count <= 0:
            continue
        
        # İstasyonu bul
        station = Station.query.filter_by(name=station_name).first()
        if not station:
            errors.append(f"'{station_name}' istasyonu bulunamadı")
            continue
        
        if station.is_depot:
            errors.append(f"'{station_name}' bir depo, kaynak olarak kullanılamaz")
            continue
        
        # Belirtilen sayıda kargo ekle
        for i in range(count):
            # Rastgele ağırlık (avg_weight'in %70 - %130 arası)
            weight = round(avg_weight * random.uniform(0.7, 1.3), 1)
            weight = max(0.5, min(weight, 100))  # 0.5 - 100 kg arası
            
            cargo = Cargo(
                sender_name=f"{random.choice(sender_names)} - {station_name}",
                receiver_name=random.choice(receiver_names),
                weight=weight,
                source_station_id=station.id,
                dest_station_id=depot.id,
                is_accepted=True
            )
            db.session.add(cargo)
            total_added += 1
    
    db.session.commit()
    
    return jsonify({
        'message': f'{total_added} kargo başarıyla eklendi',
        'total_added': total_added,
        'errors': errors
    })


# ==================== SENARYO API ====================

@app.route('/api/scenarios/load/<int:scenario_id>', methods=['POST'])
def load_scenario(scenario_id):
    """
    Örnek senaryoları veritabanına yükle
    
    Senaryo 1: 1445 kg, 113 kargo (kiralık gereksiz)
    Senaryo 2: 1105 kg (kiralık gereksiz)
    Senaryo 3: 2700 kg (kiralık gerekli)
    Senaryo 4: 1550 kg (kiralık gereksiz)
    """
    import random
    
    # Senaryolar: {ilce_adi: (kargo_sayisi, toplam_agirlik)}
    scenarios = {
        1: {
            'Başiskele': (10, 120),
            'Çayırova': (8, 80),
            'Darıca': (15, 200),
            'Derince': (10, 150),
            'Dilovası': (12, 180),
            'Gebze': (5, 70),
            'Gölcük': (7, 90),
            'Kandıra': (6, 60),
            'Karamürsel': (9, 110),
            'Kartepe': (11, 130),
            'Körfez': (6, 75),
            'İzmit': (14, 160)
        },
        2: {
            'Başiskele': (40, 200),
            'Çayırova': (35, 175),
            'Darıca': (10, 150),
            'Derince': (5, 100),
            'Gebze': (8, 120),
            'İzmit': (20, 160)
        },
        3: {
            'Çayırova': (3, 700),
            'Dilovası': (4, 800),
            'Gebze': (5, 900),
            'İzmit': (5, 300)
        },
        4: {
            'Başiskele': (30, 300),
            'Gölcük': (15, 220),
            'Kandıra': (5, 250),
            'Karamürsel': (20, 180),
            'Kartepe': (10, 200),
            'Körfez': (8, 400)
        }
    }
    
    if scenario_id not in scenarios:
        return jsonify({'error': f'Geçersiz senaryo: {scenario_id}. Geçerli: 1, 2, 3, 4'}), 400
    
    scenario = scenarios[scenario_id]
    
    # Önce mevcut kargoları, seferleri ve kiralık araçları temizle
    Trip.query.filter_by(status='planned').delete()
    Route.query.filter_by(status='planned').delete()
    Vehicle.query.filter_by(is_rental=True).delete()
    Cargo.query.delete()
    db.session.commit()
    
    # Hedef: Kocaeli Üniversitesi
    depot = Station.query.filter_by(is_depot=True).first()
    if not depot:
        return jsonify({'error': 'Kocaeli Üniversitesi tanımlı değil'}), 500
    
    sender_names = ['Ahmet', 'Mehmet', 'Ayşe', 'Fatma', 'Ali', 'Veli', 'Zeynep', 'Mustafa']
    receiver_names = ['Prof. Yılmaz', 'Doç. Kaya', 'Öğr. Gör. Demir', 'Arş. Gör. Çelik']
    
    total_cargos = 0
    total_weight = 0
    errors = []
    details = []
    
    for station_name, (count, weight) in scenario.items():
        if count <= 0:
            continue
            
        station = Station.query.filter_by(name=station_name).first()
        if not station:
            errors.append(f"'{station_name}' istasyonu bulunamadı")
            continue
        
        # Her kargo için ortalama ağırlık hesapla
        avg_weight = weight / count
        station_total_weight = 0
        
        for i in range(count):
            # Ağırlık: ortalama etrafında %20 varyasyon
            cargo_weight = round(avg_weight * random.uniform(0.9, 1.1), 1)
            cargo_weight = max(1, cargo_weight)  # Minimum 1 kg
            
            cargo = Cargo(
                sender_name=f"{random.choice(sender_names)} - {station_name}",
                receiver_name=random.choice(receiver_names),
                weight=cargo_weight,
                source_station_id=station.id,
                dest_station_id=depot.id,
                status='pending'
            )
            db.session.add(cargo)
            total_cargos += 1
            total_weight += cargo_weight
            station_total_weight += cargo_weight
        
        details.append({
            'station': station_name,
            'count': count,
            'weight': station_total_weight
        })
    
    db.session.commit()
    
    # Senaryo bilgileri
    scenario_info = {
        1: {'name': 'Senaryo 1', 'expected_weight': 1445, 'expected_rental': False},
        2: {'name': 'Senaryo 2', 'expected_weight': 1105, 'expected_rental': False},
        3: {'name': 'Senaryo 3', 'expected_weight': 2700, 'expected_rental': True},
        4: {'name': 'Senaryo 4', 'expected_weight': 1550, 'expected_rental': False}
    }
    
    info = scenario_info[scenario_id]
    
    return jsonify({
        'message': f"{info['name']} başarıyla yüklendi",
        'scenario_name': info['name'],
        'scenario_id': scenario_id,
        'total_cargos': total_cargos,
        'total_weight': round(total_weight, 1),
        'expected_weight': info['expected_weight'],
        'rental_needed': info['expected_rental'],
        'vehicle_capacity': 2250,
        'stations_loaded': len(details),
        'details': details,
        'errors': errors
    })


@app.route('/api/scenarios', methods=['GET'])
def get_scenarios():
    """Tüm senaryoların listesini döndür"""
    scenarios = [
        {
            'id': 1,
            'name': 'Senaryo 1',
            'total_weight': 1445,
            'total_cargos': 113,
            'rental_needed': False,
            'description': 'Tüm ilçelerden dengeli dağılım - Kiralık araç gereksiz'
        },
        {
            'id': 2,
            'name': 'Senaryo 2',
            'total_weight': 1105,
            'total_cargos': 118,
            'rental_needed': False,
            'description': 'Batı ilçeleri ağırlıklı - Kiralık araç gereksiz'
        },
        {
            'id': 3,
            'name': 'Senaryo 3',
            'total_weight': 2700,
            'total_cargos': 17,
            'rental_needed': True,
            'description': 'Ağır kargolar - KİRALIK ARAÇ GEREKLİ'
        },
        {
            'id': 4,
            'name': 'Senaryo 4',
            'total_weight': 1550,
            'total_cargos': 88,
            'rental_needed': False,
            'description': 'Doğu ilçeleri ağırlıklı - Kiralık araç gereksiz'
        }
    ]
    
    # İstasyon sayısı ekle
    for s in scenarios:
        s['stations_count'] = {1: 12, 2: 6, 3: 4, 4: 6}.get(s['id'], 0)
    
    return jsonify(scenarios)


@app.route('/api/scenarios/create-custom', methods=['POST'])
def create_custom_scenario():
    """
    Kullanıcının oluşturduğu özel senaryoyu yükle
    
    Beklenen JSON:
    {
        "cargos": [
            {"station_id": 1, "station_name": "İzmit", "count": 5, "total_weight": 100},
            ...
        ]
    }
    """
    import random
    
    data = request.get_json()
    if not data or 'cargos' not in data:
        return jsonify({'error': 'Kargo verisi gerekli'}), 400
    
    cargos_data = data['cargos']
    if not cargos_data:
        return jsonify({'error': 'En az bir istasyona kargo ekleyin'}), 400
    
    # Önce mevcut kargoları, seferleri ve kiralık araçları temizle
    Trip.query.filter_by(status='planned').delete()
    Route.query.filter_by(status='planned').delete()
    Vehicle.query.filter_by(is_rental=True).delete()
    Cargo.query.delete()
    db.session.commit()
    
    # Hedef: Kocaeli Üniversitesi
    depot = Station.query.filter_by(is_depot=True).first()
    if not depot:
        return jsonify({'error': 'Kocaeli Üniversitesi tanımlı değil'}), 500
    
    sender_names = ['Ahmet', 'Mehmet', 'Ayşe', 'Fatma', 'Ali', 'Veli', 'Zeynep', 'Mustafa']
    receiver_names = ['Prof. Yılmaz', 'Doç. Kaya', 'Öğr. Gör. Demir', 'Arş. Gör. Çelik']
    
    total_cargos = 0
    total_weight = 0
    details = []
    
    for cargo_info in cargos_data:
        station_id = cargo_info.get('station_id')
        station_name = cargo_info.get('station_name')
        count = cargo_info.get('count', 0)
        weight = cargo_info.get('total_weight', 0)
        
        if count <= 0 or weight <= 0:
            continue
        
        station = Station.query.get(station_id)
        if not station:
            continue
        
        # Her kargo için ortalama ağırlık
        avg_weight = weight / count
        station_total_weight = 0
        
        for i in range(count):
            # Ağırlık: ortalama etrafında %10 varyasyon
            cargo_weight = round(avg_weight * random.uniform(0.95, 1.05), 1)
            cargo_weight = max(0.5, cargo_weight)
            
            cargo = Cargo(
                sender_name=f"{random.choice(sender_names)} - {station_name}",
                receiver_name=random.choice(receiver_names),
                weight=cargo_weight,
                source_station_id=station.id,
                dest_station_id=depot.id,
                status='pending'
            )
            db.session.add(cargo)
            total_cargos += 1
            total_weight += cargo_weight
            station_total_weight += cargo_weight
        
        details.append({
            'station': station_name,
            'count': count,
            'weight': station_total_weight
        })
    
    db.session.commit()
    
    rental_needed = total_weight > 2250
    
    return jsonify({
        'message': 'Özel senaryo yüklendi',
        'scenario_name': 'Özel Senaryo',
        'total_cargos': total_cargos,
        'total_weight': round(total_weight, 1),
        'rental_needed': rental_needed,
        'vehicle_capacity': 2250,
        'stations_loaded': len(details),
        'details': details
    })


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
    Clarke-Wright Savings Algoritması ile rota optimizasyonu
    
    SENARYO: Kocaeli ilçelerinden Kocaeli Üniversitesi'ne kargo toplama
    
    ALGORİTMA: Clarke-Wright Savings (VRP)
    - Savings hesaplama: s(i,j) = d(depot,i) + d(depot,j) - d(i,j)
    - Kapasite ve bölge kısıtları ile rota birleştirme
    - OSRM API ile gerçek yol geometrisi
    
    İKİ PROBLEM:
    1. SINIRSIZ ARAÇ PROBLEMİ (unlimited_vehicles):
       - Minimum maliyetle kaç araç ile taşıma tamamlanabilir?
       - Tüm kargolar kabul edilir
       - Kapasite aşılırsa araç kiralanır (200 birim/500kg)
       
    2. BELİRLİ SAYIDA ARAÇ PROBLEMİ (fixed_vehicles):
       - Minimum maliyet, maksimum kargo güzergahı
       - Kapasite aşılırsa bazı kargolar reddedilir
    """
    from algorithms.clarke_wright import ClarkeWrightSolver, RegionalClarkeWright
    from algorithms.distance_calculator import road_distance, calculate_route_with_coordinates, get_network
    import json
    from datetime import date
    
    data = request.json
    target_date = datetime.strptime(data.get('date', date.today().isoformat()), '%Y-%m-%d').date()
    optimization_mode = data.get('mode', 'unlimited_vehicles')
    max_criteria = data.get('accept_criteria', 'max_weight')
    use_regional = data.get('use_regional', True)  # Bölge bazlı optimizasyon
    
    # ==================== ESKİ SEFERLERİ TEMİZLE ====================
    # Her optimizasyon öncesi eski planned seferleri sil
    Trip.query.filter_by(status='planned').delete()
    Route.query.filter_by(status='planned').delete()
    Vehicle.query.filter_by(is_rental=True).delete()
    
    # Kargoları sıfırla (pending durumuna getir)
    Cargo.query.filter(Cargo.status == 'in_transit').update({'status': 'pending', 'vehicle_id': None})
    db.session.commit()
    
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
    
    # Toplam bilgiler
    total_weight = sum(c.weight for c in pending_cargos)
    total_count = len(pending_cargos)
    total_capacity = sum(v.capacity for v in own_vehicles)
    
    rental_vehicles = []
    accepted_cargos = list(pending_cargos)
    rejected_cargos = []
    
    # ==================== SENARYO 1: SINIRSIZ ARAÇ PROBLEMİ ====================
    if optimization_mode == 'unlimited_vehicles':
        # Kapasite yetersizse TEK BİR kiralık araç ekle
        if total_weight > total_capacity:
            needed_capacity = total_weight - total_capacity
            
            # Tek bir kiralık araç - ihtiyaca göre uygun kapasiteyi seç
            # Bin-packing için biraz fazla kapasite al
            if needed_capacity <= 400:
                capacity = 500
                cost = 1.0
                rental_cost_val = 200
            elif needed_capacity <= 600:
                capacity = 750
                cost = 1.2
                rental_cost_val = 250
            else:
                capacity = 1000
                cost = 1.5
                rental_cost_val = 300
            
            rental = Vehicle(
                name=f'Kiralık Araç ({capacity}kg)',
                capacity=capacity,
                cost_per_km=cost,
                is_rental=True,
                rental_cost=rental_cost_val
            )
            db.session.add(rental)
            rental_vehicles.append(rental)
            db.session.flush()
            vehicles_to_use.extend(rental_vehicles)
        
        accepted_cargos = list(pending_cargos)
        for cargo in accepted_cargos:
            cargo.is_accepted = True
    
    # ==================== SENARYO 2: BELİRLİ SAYIDA ARAÇ PROBLEMİ ====================
    elif optimization_mode == 'fixed_vehicles':
        if total_weight <= total_capacity:
            accepted_cargos = list(pending_cargos)
            for cargo in accepted_cargos:
                cargo.is_accepted = True
        else:
            if max_criteria == 'max_count':
                sorted_cargos = sorted(pending_cargos, key=lambda c: c.weight)
            else:
                sorted_cargos = sorted(pending_cargos, key=lambda c: c.weight, reverse=True)
            
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
    
    # Mesafe matrisini oluştur
    distance_matrix = {}
    for s1 in stations:
        for s2 in stations:
            if s1.id != s2.id:
                key = f"{s1.id}_{s2.id}"
                distance_matrix[key] = road_distance(
                    (s1.latitude, s1.longitude),
                    (s2.latitude, s2.longitude)
                )
    
    # ==================== CLARKE-WRIGHT SAVINGS ALGORİTMASI ====================
    # Bölge bazlı veya standart algoritma seç
    SolverClass = RegionalClarkeWright if use_regional else ClarkeWrightSolver
    
    solver = SolverClass(
        stations=stations,
        vehicles=vehicles_to_use,
        cargos=accepted_cargos,
        depot=depot,
        distance_matrix=distance_matrix,
        max_route_distance=80.0,
        use_osrm=True  # OSRM API ile gerçek mesafeler
    )
    
    # Çözümü al
    best_solution = solver.solve()
    
    # Rotaları ve sefer kayıtlarını oluştur
    created_routes = []
    created_trips = []
    
    for vehicle_id, route_stations in best_solution.items():
        vehicle = Vehicle.query.get(vehicle_id)
        if not route_stations:
            continue
        
        route_station_ids = [s.id for s in route_stations]
        route_distance = solver._calculate_route_distance(route_stations)
        
        # Maliyet hesapla
        fuel_cost = route_distance * vehicle.cost_per_km
        rental_cost_val = vehicle.rental_cost if vehicle.is_rental else 0
        route_cost = fuel_cost + rental_cost_val
        
        # OSRM ile yol koordinatlarını al
        osrm_geometry = solver.get_osrm_route_geometry(route_stations)
        path_coords = [{'lat': c[1], 'lng': c[0]} for c in osrm_geometry.get('coordinates', [])]
        
        # Rotadaki kargolar - SOLVER'DAN ATANAN KARGOLARI AL
        route_cargos = []
        route_total_weight = 0
        
        # Solver'dan bu araca atanan kargoları al
        assigned_cargos = []
        if hasattr(solver, 'vehicle_cargo_assignments'):
            assigned_cargos = solver.vehicle_cargo_assignments.get(vehicle_id, [])
        
        for cargo in assigned_cargos:
            cargo.vehicle_id = vehicle_id
            cargo.status = 'in_transit'
            cargo.is_accepted = True
            route_cargos.append({
                'id': cargo.id,
                'sender': cargo.sender_name,
                'receiver': cargo.receiver_name,
                'weight': cargo.weight,
                'source': cargo.source_station.name
            })
            route_total_weight += cargo.weight
        
        # Rota detayları
        route_details = {
            'stations': [{'id': s.id, 'name': s.name, 'lat': s.latitude, 'lng': s.longitude} for s in route_stations],
            'stops': [{'station_id': s.id, 'station_name': s.name, 'latitude': s.latitude, 'longitude': s.longitude} for s in route_stations],
            'cargos': route_cargos,
            'vehicle': vehicle.to_dict(),
            'osrm_distance': osrm_geometry.get('distance', route_distance),
            'osrm_duration': osrm_geometry.get('duration', 0),
            'geometry': osrm_geometry.get('geometry', None)  # Encoded polyline for simulation
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
        'algorithm': 'Clarke-Wright Savings',
        'algorithm_description': 'Bölge bazlı VRP optimizasyonu + OSRM gerçek yol geometrisi',
        'mode': optimization_mode,
        'mode_description': 'Sınırsız Araç - Tüm kargolar taşınır' if optimization_mode == 'unlimited_vehicles' else 'Belirli Araç - Sabit filolar',
        
        # Maliyet bilgileri
        'total_cost': round(total_fuel_cost + total_rental_cost, 2),
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

# (Senaryo API'si yukarıda tanımlandı - /api/scenarios ve /api/scenarios/load)


@app.route('/api/scenarios/compare-all', methods=['POST'])
@login_required
def compare_all_scenarios():
    """
    Tüm senaryoları çalıştır ve karşılaştırmalı sonuç döndür.
    Her senaryo için optimizasyon yapılır ve sonuçlar toplanır.
    """
    from algorithms.scenarios import get_scenario_data, get_all_scenarios
    from algorithms.genetic_algorithm import GeneticAlgorithmCVRP
    from algorithms.distance_calculator import road_distance
    import json
    
    results = []
    scenarios_info = get_all_scenarios()
    
    for scenario_info in scenarios_info:
        scenario_id = scenario_info['id']
        
        # Mevcut verileri temizle
        Cargo.query.delete()
        Trip.query.delete()
        Route.query.delete()
        Vehicle.query.filter_by(is_rental=True).delete()
        db.session.commit()
        
        # Senaryo verilerini yükle
        scenario = get_scenario_data(scenario_id)
        depot = Station.query.filter_by(is_depot=True).first()
        
        total_weight = 0
        cargo_count = 0
        
        for cargo_data in scenario['cargos']:
            source_station = Station.query.filter_by(name=cargo_data['source']).first()
            dest_station = Station.query.filter_by(name=cargo_data['dest']).first()
            
            if source_station and dest_station:
                cargo = Cargo(
                    sender_name=cargo_data.get('sender', f'Gönderici'),
                    receiver_name=cargo_data.get('receiver', f'Alıcı'),
                    weight=cargo_data['weight'],
                    source_station_id=source_station.id,
                    dest_station_id=dest_station.id,
                    status='pending'
                )
                db.session.add(cargo)
                total_weight += cargo_data['weight']
                cargo_count += 1
        
        db.session.commit()
        
        # Araçları al
        own_vehicles = Vehicle.query.filter_by(is_available=True, is_rental=False).all()
        total_capacity = sum(v.capacity for v in own_vehicles)
        
        # Kiralık araç gerekli mi?
        rental_needed = total_weight > total_capacity
        rental_count = 0
        
        if rental_needed:
            needed_capacity = total_weight - total_capacity
            rental_count = int(needed_capacity / 500) + 1
            
            for i in range(rental_count):
                rental = Vehicle(
                    name=f'Kiralık Araç {i+1}',
                    capacity=500,
                    cost_per_km=1.0,
                    is_rental=True,
                    rental_cost=200
                )
                db.session.add(rental)
            db.session.flush()
        
        all_vehicles = Vehicle.query.filter_by(is_available=True).all()
        stations = Station.query.all()
        pending_cargos = Cargo.query.filter_by(status='pending').all()
        
        # Mesafe matrisi
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
        
        # GA ile optimizasyon
        ga = GeneticAlgorithmCVRP(
            stations=stations,
            vehicles=all_vehicles,
            cargos=pending_cargos,
            depot=depot,
            distance_matrix=distance_matrix
        )
        
        best_solution, best_cost = ga.run()
        
        # Sonuçları hesapla
        total_distance = 0
        fuel_cost = 0
        rental_cost = rental_count * 200
        vehicle_routes = []
        
        for vehicle in all_vehicles:
            route_stations = best_solution.get(vehicle.id, [])
            if route_stations:
                route_distance = ga.calculate_route_distance(route_stations)
                route_cost = ga.calculate_route_cost(vehicle, route_stations)
                route_weight = ga.calculate_route_weight(route_stations)
                
                total_distance += route_distance
                fuel_cost += route_distance * vehicle.cost_per_km
                
                # Bu araçtaki kargolar
                route_cargos = []
                for cargo in pending_cargos:
                    if cargo.source_station in route_stations:
                        route_cargos.append({
                            'id': cargo.id,
                            'sender': cargo.sender_name,
                            'receiver': cargo.receiver_name,
                            'weight': cargo.weight
                        })
                
                vehicle_routes.append({
                    'vehicle_name': vehicle.name,
                    'vehicle_capacity': vehicle.capacity,
                    'is_rental': vehicle.is_rental,
                    'route': [s.name for s in route_stations],
                    'distance': round(route_distance, 2),
                    'cost': round(route_cost, 2),
                    'load': round(route_weight, 2),
                    'utilization': round((route_weight / vehicle.capacity) * 100, 1),
                    'cargo_count': len(route_cargos),
                    'cargos': route_cargos
                })
        
        results.append({
            'scenario_id': scenario_id,
            'scenario_name': scenario['name'],
            'description': scenario['description'],
            'total_cargo_count': cargo_count,
            'total_cargo_weight': round(total_weight, 2),
            'own_vehicles_used': len([v for v in vehicle_routes if not v['is_rental']]),
            'rental_vehicles_used': rental_count,
            'total_distance': round(total_distance, 2),
            'fuel_cost': round(fuel_cost, 2),
            'rental_cost': round(rental_cost, 2),
            'total_cost': round(fuel_cost + rental_cost, 2),
            'capacity_utilization': round((total_weight / (total_capacity + rental_count * 500)) * 100, 1),
            'vehicle_routes': vehicle_routes
        })
        
        # Kiralık araçları temizle
        Vehicle.query.filter_by(is_rental=True).delete()
        db.session.commit()
    
    # Final temizlik
    Cargo.query.delete()
    Trip.query.delete()
    Route.query.delete()
    db.session.commit()
    
    return jsonify({
        'scenarios': results,
        'summary': {
            'total_scenarios': len(results),
            'min_cost_scenario': min(results, key=lambda x: x['total_cost'])['scenario_name'] if results else None,
            'max_cost_scenario': max(results, key=lambda x: x['total_cost'])['scenario_name'] if results else None,
            'avg_cost': round(sum(r['total_cost'] for r in results) / len(results), 2) if results else 0,
            'avg_distance': round(sum(r['total_distance'] for r in results) / len(results), 2) if results else 0
        }
    })


@app.route('/api/analytics/vehicle-routes', methods=['GET'])
@login_required
def get_vehicle_routes_detail():
    """
    Her araç için detaylı rota bilgisi:
    - Rota maliyetleri
    - Rotalar
    - Araçtaki kargolar ve sahipleri
    - Simülasyon için rota geometrisi
    """
    trips = Trip.query.order_by(Trip.created_at.desc()).all()
    result = []
    
    for trip in trips:
        vehicle = Vehicle.query.get(trip.vehicle_id)
        if not vehicle:
            continue
        
        import json
        route_details = json.loads(trip.route_details) if trip.route_details else {}
        
        # Bu araçtaki kargolar
        cargos = Cargo.query.filter_by(vehicle_id=trip.vehicle_id).all()
        cargo_list = []
        station_names = []
        
        for cargo in cargos:
            cargo_list.append({
                'id': cargo.id,
                'sender_name': cargo.sender_name,
                'receiver_name': cargo.receiver_name,
                'weight': cargo.weight,
                'source': cargo.source_station.name if cargo.source_station else '-',
                'status': cargo.status
            })
            if cargo.source_station and cargo.source_station.name not in station_names:
                station_names.append(cargo.source_station.name)
        
        result.append({
            'trip_id': trip.id,
            'vehicle_id': vehicle.id,
            'vehicle_plate': vehicle.name,
            'vehicle': {
                'id': vehicle.id,
                'name': vehicle.name,
                'capacity': vehicle.capacity,
                'is_rental': vehicle.is_rental
            },
            'date': trip.date.isoformat() if trip.date else None,
            'status': trip.status,
            'route_stops': route_details.get('stops', []),
            'route_geometry': route_details.get('geometry', None),  # OSRM geometry for simulation
            'stations': station_names,  # İstasyon adları
            'total_distance': round(trip.total_distance or 0, 2),
            'fuel_cost': round(trip.fuel_cost or 0, 2),
            'rental_cost': round(trip.rental_cost or 0, 2),
            'total_cost': round(trip.total_cost or 0, 2),
            'cargo_count': trip.cargo_count or 0,
            'total_weight': round(trip.total_weight or 0, 2),
            'capacity_utilization': round((trip.total_weight / vehicle.capacity) * 100, 1) if vehicle.capacity else 0,
            'cargos': cargo_list
        })
    
    return jsonify(result)
    
    return jsonify(result)


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
                {'name': 'Başiskele', 'lat': 40.7244, 'lng': 29.9097, 'is_depot': False},
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
