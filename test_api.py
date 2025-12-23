"""
API Response Test
"""
import urllib.request
import json

with urllib.request.urlopen('http://127.0.0.1:5000/api/cargos/my-route/1') as response:
    data = json.loads(response.read().decode())

print('=== API RESPONSE ===')
print(f'HTTP Status: {r.status_code}')
print()

if 'route' in data:
    route = data['route']
    print('Route Info:')
    print(f'  distance: {route.get("distance")}')
    print(f'  total_cost: {route.get("total_cost")}')
    print(f'  fuel_cost: {route.get("fuel_cost")}')
    print(f'  stops count: {len(route.get("stops", []))}')

if 'path_coordinates' in data:
    coords = data['path_coordinates']
    print(f'\nPath Coordinates: {len(coords)} adet')
    if coords:
        print(f'  First: {coords[0]}')
        print(f'  Last: {coords[-1]}')
