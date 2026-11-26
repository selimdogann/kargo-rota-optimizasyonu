"""
Test senaryoları: tek kaynak.

Senaryo yükleme (/api/scenarios/load/<id>), senaryo listesi (/api/scenarios) ve
genetik algoritma karşılaştırması (/api/scenarios/compare-all) aynı veriyi buradan okur.
Böylece arayüzde "Senaryo 1" neyse karşılaştırmada da odur.

Her senaryo: {ilçe adı: (kargo sayısı, toplam ağırlık kg)}.
Tüm kargolar ilçelerden Kocaeli Üniversitesi'ne (depo) gider.
"""

import random
from typing import Dict, List

SCENARIOS: Dict[int, Dict] = {
    # Her senaryo farklı bir durumu dener:
    # 1) tüm ilçelerden dengeli toplama, 2) depoya uzak batıda çok sayıda hafif paket,
    # 3) filo kapasitesini aşan ağır yük, 4) depoya yakın doğuda ağır ama sığan yük.
    1: {
        'name': 'Senaryo 1',
        'description': 'Dengeli gün: 12 ilçenin hepsinden toplama, kiralık araç gerekmez',
        'loads': {
            'Başiskele': (10, 120), 'Çayırova': (8, 80), 'Darıca': (15, 200),
            'Derince': (10, 150), 'Dilovası': (12, 180), 'Gebze': (5, 70),
            'Gölcük': (7, 90), 'Kandıra': (6, 60), 'Karamürsel': (9, 110),
            'Kartepe': (11, 130), 'Körfez': (6, 75), 'İzmit': (14, 160),
        },
    },
    2: {
        'name': 'Senaryo 2',
        'description': 'Batı ilçelerinde çok sayıda hafif paket, depoya uzak; kiralık araç gerekmez',
        'loads': {
            'Çayırova': (35, 175), 'Darıca': (30, 210), 'Gebze': (25, 200),
            'Dilovası': (15, 120), 'Körfez': (13, 100),
        },
    },
    3: {
        'name': 'Senaryo 3',
        'description': 'Ağır kargolar filo kapasitesini (2.250 kg) aşar, kiralık araç gerekir',
        'loads': {
            'Çayırova': (3, 700), 'Dilovası': (4, 800), 'Gebze': (5, 900), 'İzmit': (5, 300),
        },
    },
    4: {
        'name': 'Senaryo 4',
        'description': 'Doğu ilçelerinde ağır yük, kapasiteye sığar; kiralık araç gerekmez',
        'loads': {
            'İzmit': (20, 330), 'Başiskele': (30, 300), 'Kartepe': (10, 200),
            'Kandıra': (5, 250), 'Gölcük': (15, 220), 'Derince': (8, 250),
        },
    },
}

# Sabit filonun toplam kapasitesi (Araç 1 + 2 + 3)
FLEET_CAPACITY_KG = 2250

SENDER_NAMES = ['Ahmet', 'Mehmet', 'Ayşe', 'Fatma', 'Ali', 'Veli', 'Zeynep', 'Mustafa']
RECEIVER_NAMES = ['Prof. Yılmaz', 'Doç. Kaya', 'Öğr. Gör. Demir', 'Arş. Gör. Çelik']


def scenario_summary(scenario_id: int) -> Dict:
    """Bir senaryonun özeti: toplam kargo, toplam ağırlık, ilçe sayısı, kiralık gerekir mi."""
    s = SCENARIOS[scenario_id]
    total_cargos = sum(count for count, _ in s['loads'].values())
    total_weight = sum(weight for _, weight in s['loads'].values())
    return {
        'id': scenario_id,
        'name': s['name'],
        'description': s['description'],
        'total_cargos': total_cargos,
        'total_weight': total_weight,
        'stations_count': len(s['loads']),
        'rental_needed': total_weight > FLEET_CAPACITY_KG,
    }


def all_scenario_summaries() -> List[Dict]:
    return [scenario_summary(sid) for sid in sorted(SCENARIOS)]


def generate_cargos(scenario_id: int, rng: random.Random = None) -> List[Dict]:
    """
    Senaryonun kargolarını üret.

    Her ilçenin toplam ağırlığı kargolara bölünür; her kargo ortalamanın %90-110'u
    arasında rastgele bir ağırlık alır (en az 1 kg). Sabit bir `rng` verilirse
    (ör. random.Random(42)) aynı kargolar üretilir: testler bunu kullanır.
    """
    rng = rng or random
    cargos = []
    for station_name, (count, weight) in SCENARIOS[scenario_id]['loads'].items():
        if count <= 0:
            continue
        avg = weight / count
        for _ in range(count):
            cargos.append({
                'source': station_name,
                'weight': max(1, round(avg * rng.uniform(0.9, 1.1), 1)),
                'sender': f"{rng.choice(SENDER_NAMES)} - {station_name}",
                'receiver': rng.choice(RECEIVER_NAMES),
            })
    return cargos
