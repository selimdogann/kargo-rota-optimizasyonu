"""
Senaryolar ve rota optimizasyonu (Clarke-Wright) uçtan uca:
yükle -> optimize et -> sonucu iş kurallarına göre doğrula.
"""
import pytest

from algorithms.scenarios import SCENARIOS, scenario_summary

EXPECTED = {  # senaryo: (toplam kg, kargo sayısı, ilçe sayısı, kiralık gerekir mi)
    1: (1425, 113, 12, False),
    2: (805, 118, 5, False),
    3: (2700, 17, 4, True),
    4: (1550, 88, 6, False),
}


@pytest.mark.parametrize('sid', sorted(EXPECTED))
def test_scenario_summary_matches_definition(sid):
    s = scenario_summary(sid)
    assert (s['total_weight'], s['total_cargos'], s['stations_count'], s['rental_needed']) == EXPECTED[sid]


def test_scenario_list_endpoint(admin):
    data = admin.get('/api/scenarios').get_json()
    assert [s['id'] for s in data] == [1, 2, 3, 4]
    assert [s['total_weight'] for s in data] == [EXPECTED[i][0] for i in (1, 2, 3, 4)]


@pytest.mark.parametrize('sid', sorted(EXPECTED))
def test_load_and_optimize(admin, sid):
    loaded = admin.post(f'/api/scenarios/load/{sid}').get_json()
    kg, count, n_stations, rental = EXPECTED[sid]
    assert loaded['total_cargos'] == count
    assert loaded['stations_loaded'] == n_stations
    assert abs(loaded['total_weight'] - kg) <= kg * 0.1  # her kargo ortalamanın ±%10'u

    r = admin.post('/api/routes/optimize', json={})
    assert r.status_code == 200
    o = r.get_json()

    assert o['accepted_count'] == count and o['rejected_count'] == 0
    assert (o['rented_vehicles'] > 0) == rental
    for v in o['vehicle_details']:
        assert v['load'] <= v['capacity'] + 1e-6, f"{v['vehicle_name']} kapasiteyi aşıyor"
    # her kargo tam olarak bir araca yüklenir
    assert sum(v['cargo_count'] for v in o['vehicle_details']) == count
    assert o['total_distance'] > 0


def test_fixed_fleet_rejects_overflow_instead_of_renting(admin):
    admin.post('/api/scenarios/load/3')
    o = admin.post('/api/routes/optimize', json={'mode': 'fixed_vehicles', 'accept_criteria': 'max_weight'}).get_json()
    assert o['rented_vehicles'] == 0
    assert o['rejected_count'] > 0
    assert o['accepted_weight'] <= 2250 + 1e-6


def test_invalid_scenario_returns_400(admin):
    assert admin.post('/api/scenarios/load/9').status_code == 400


def test_compare_all_uses_same_scenarios_as_ui(admin):
    """GA karşılaştırması, arayüzde yüklenen senaryolarla aynı veriyi kullanmalı."""
    d = admin.post('/api/scenarios/compare-all', json={}).get_json()
    results = {s['scenario_id']: s for s in d['scenarios']}
    assert sorted(results) == [1, 2, 3, 4]
    for sid, (kg, count, _, _) in EXPECTED.items():
        assert results[sid]['total_cargo_count'] == count
        assert abs(results[sid]['total_cargo_weight'] - kg) <= kg * 0.1
        assert results[sid]['scenario_name'] == SCENARIOS[sid]['name']
    # GA artık birden fazla ilçeden toplama yapıyor (eski veride tek durak vardı)
    stops = {name for v in results[1]['vehicle_routes'] for name in v['route']}
    assert len(stops) >= 10
