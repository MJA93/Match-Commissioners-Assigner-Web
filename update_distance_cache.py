
import pandas as pd
import requests
import json
import time
from itertools import product

ORS_API_KEY = "b3b1566c3b10xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# تحميل الملفات
cities_df = pd.read_csv("cities_lookup.csv")
cities = cities_df["الاسم_بالعربي"].dropna().unique().tolist()
city_lookup = dict(zip(cities_df["الاسم_بالعربي"], cities_df["الاسم_الموحد"]))

# تحميل الكاش الموجود
try:
    with open("distance_cache.json", "r", encoding="utf-8") as f:
        distance_cache = json.load(f)
except:
    distance_cache = {}

# دالة إحداثيات
def get_coords(city):
    city_std = city_lookup.get(city, city)
    url = f"https://api.openrouteservice.org/geocode/search"
    params = {
        "api_key": ORS_API_KEY,
        "text": city_std,
        "boundary.country": "SA"
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    geo = r.json()
    return geo['features'][0]['geometry']['coordinates']

# البحث عن أزواج المدن الجديدة فقط
new_pairs = []
for c1, c2 in product(cities, cities):
    if c1 == c2:
        continue
    key1 = f"{c1}|{c2}"
    key2 = f"{c2}|{c1}"
    if key1 not in distance_cache and key2 not in distance_cache:
        new_pairs.append((c1, c2))

print(f"🔍 عدد الأزواج الجديدة التي سيتم حسابها: {len(new_pairs)}")

# حساب المسافات الجديدة فقط
for idx, (city1, city2) in enumerate(new_pairs):
    try:
        coords1 = get_coords(city1)
        coords2 = get_coords(city2)

        matrix_url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        headers = {
            "Authorization": ORS_API_KEY,
            "Content-Type": "application/json"
        }
        body = {
            "locations": [coords1, coords2],
            "metrics": ["distance"],
            "units": "km"
        }
        r = requests.post(matrix_url, json=body, headers=headers)
        r.raise_for_status()
        dist = r.json()["distances"][0][1]

        distance_cache[f"{city1}|{city2}"] = dist
        print(f"[{idx+1}/{len(new_pairs)}] {city1} <-> {city2} = {dist:.1f} km")

        # حفظ دوري مؤقت
        if (idx + 1) % 100 == 0:
            with open("distance_cache.json", "w", encoding="utf-8") as f:
                json.dump(distance_cache, f, ensure_ascii=False, indent=2)

        time.sleep(1.2)

    except Exception as e:
        print(f"خطأ في {city1}|{city2}: {e}")
        continue

# حفظ نهائي
with open("distance_cache.json", "w", encoding="utf-8") as f:
    json.dump(distance_cache, f, ensure_ascii=False, indent=2)

print("✅ تم تحديث الكاش بالمسافات الجديدة فقط.")
