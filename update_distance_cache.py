# update_distance_cache.py

import os
import json
import time
import pandas as pd
import requests
from itertools import product

# ---------------------- إعدادات ---------------------- #
GOOGLE_API_KEY = "ضع_مفتاحك_هنا"  # 🔑 تأكد من تغييره بمفتاحك الصحيح
CACHE_FILE = "distance_cache.json"
CITY_LOOKUP_FILE = "cities_lookup.csv"
UPLOAD_DIR = "uploaded_files"

# ---------------------- تحميل ملفات ---------------------- #
def load_city_lookup():
    df = pd.read_csv(CITY_LOOKUP_FILE)
    return dict(zip(df["الاسم_بالعربي"], df["الاسم_الموحد"]))

def load_uploaded_cities():
    cities = set()
    for file in os.listdir(UPLOAD_DIR):
        if file.endswith(".xlsx"):
            df = pd.read_excel(os.path.join(UPLOAD_DIR, file))
            if "المدينة" in df.columns:
                cities.update(df["المدينة"].dropna().astype(str).str.strip())
    return sorted(cities)

def load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ---------------------- دالة حساب المسافة ---------------------- #
def google_maps_distance(city1, city2):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": city1,
        "destinations": city2,
        "key": GOOGLE_API_KEY,
        "units": "metric",
        "language": "ar"
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data.get("status") != "OK":
        raise ValueError(f"API status error: {data.get('status')}")

    element = data["rows"][0]["elements"][0]
    if element["status"] != "OK":
        raise ValueError(f"Element status: {element['status']}")

    return element["distance"]["value"] / 1000  # بالكم

# ---------------------- العملية الرئيسية ---------------------- #
if __name__ == "__main__":
    print("🚀 جاري تحميل الملفات...")
    lookup = load_city_lookup()
    all_cities = load_uploaded_cities()
    cache = load_cache()

    translated = [c for c in all_cities if c in lookup]
    untranslated = [c for c in all_cities if c not in lookup]

    if untranslated:
        print("⚠️ مدن لم تُترجم، أضفها يدويًا إلى cities_lookup.csv:")
        for u in untranslated:
            print("-", u)

    new_pairs = []
    for c1, c2 in product(translated, translated):
        if c1 == c2:
            continue
        k1 = f"{c1}|{c2}"
        k2 = f"{c2}|{c1}"
        if k1 not in cache and k2 not in cache:
            new_pairs.append((c1, c2))

    print(f"🔍 عدد الأزواج الجديدة: {len(new_pairs)}")

    for idx, (city1, city2) in enumerate(new_pairs):
        try:
            c1_std = lookup.get(city1, city1)
            c2_std = lookup.get(city2, city2)

            dist = google_maps_distance(c1_std, c2_std)
            cache[f"{city1}|{city2}"] = dist
            print(f"[{idx+1}/{len(new_pairs)}] {city1} ↔ {city2} = {dist:.1f} km")

            if (idx + 1) % 50 == 0:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)

            time.sleep(1)

        except Exception as e:
            print(f"❌ خطأ في {city1}|{city2}: {e}")
            continue

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print("\n✅ تم تحديث كاش Google Maps للمسافات.")
