"""Algoritmaların veritabanından bağımsız birim testleri."""
import random

import pytest

from algorithms.distance_calculator import get_network, haversine_distance
from algorithms.scenarios import SCENARIOS, generate_cargos

DEPOT = 'Kocaeli Üniversitesi'


def dist(a, b):
    n = get_network()
    return n.get_distance(n.get_district_id_by_name(a), n.get_district_id_by_name(b))


def test_haversine_known_distance():
    # İzmit merkez ile Umuttepe kampüsü arası kuş uçuşu ~6,5 km
    assert 6 < haversine_distance(40.7656, 29.9406, 40.8225, 29.9213) < 7


def test_road_distance_is_symmetric_and_positive():
    assert dist('Gebze', DEPOT) == pytest.approx(dist(DEPOT, 'Gebze'))
    assert dist('Gebze', 'Gebze') == 0
    assert dist('Gebze', DEPOT) > 0


def test_road_distance_never_shorter_than_straight_line():
    n = get_network()
    coords = {'Gebze': (40.8027, 29.4307), 'Kandıra': (41.0706, 30.1528), DEPOT: (40.8225, 29.9213)}
    for name in ('Gebze', 'Kandıra'):
        straight = haversine_distance(*coords[name], *coords[DEPOT])
        assert dist(name, DEPOT) >= straight


def test_shortest_path_follows_the_coast():
    n = get_network()
    path, km = n.find_path(n.get_district_id_by_name('Gebze'), n.get_district_id_by_name(DEPOT))
    assert path[0] == 'GEBZE' and path[-1] == 'DEPO'
    assert 'IZMIT' in path


def test_triangle_inequality_holds():
    """Dijkstra en kısa yolu bulduysa hiçbir ara durak yolu kısaltamaz."""
    names = ['Gebze', 'Darıca', 'Dilovası', 'Körfez', 'İzmit', DEPOT, 'Kartepe', 'Gölcük']
    for a in names:
        for b in names:
            for c in names:
                assert dist(a, c) <= dist(a, b) + dist(b, c) + 1e-9


def test_clarke_wright_savings_formula_values():
    # s(i,j) = d(0,i) + d(0,j) - d(i,j): komşu ilçeleri birleştirmek pozitif kazanç verir
    s = dist(DEPOT, 'Darıca') + dist(DEPOT, 'Çayırova') - dist('Darıca', 'Çayırova')
    assert s > 100


@pytest.mark.parametrize('sid', sorted(SCENARIOS))
def test_generate_cargos_matches_loads(sid):
    cargos = generate_cargos(sid, random.Random(1))
    loads = SCENARIOS[sid]['loads']
    assert len(cargos) == sum(count for count, _ in loads.values())
    for station, (count, weight) in loads.items():
        mine = [c['weight'] for c in cargos if c['source'] == station]
        assert len(mine) == count
        avg = weight / count
        assert all(max(1, round(avg * 0.9, 1)) <= w <= round(avg * 1.1, 1) + 0.05 for w in mine)


def test_generate_cargos_is_reproducible_with_seed():
    assert generate_cargos(1, random.Random(7)) == generate_cargos(1, random.Random(7))
