import streamlit as st
import pandas as pd
import requests
import re
import json
from io import BytesIO

st.set_page_config(page_title="Match Commissioners Assigner by Harashi", page_icon="⚽", layout="wide", initial_sidebar_state="expanded")

# ---------------------- الإعدادات ---------------------- #
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=True)
google_api_key = st.sidebar.text_input("Google Maps API Key", type="password")
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)

# ---------------------- تحميل الكاش للمسافات ---------------------- #
try:
    with open("distance_cache.json", "r", encoding="utf-8") as f:
        distance_cache = json.load(f)
except:
    distance_cache = {}

# ---------------------- Google Maps Distance ---------------------- #
def google_maps_distance(city1, city2):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": city1,
        "destinations": city2,
        "key": google_api_key,
        "units": "metric",
        "language": "ar"
    }
    response = requests.get(url, params=params)
    data = response.json()
    if data.get("status") != "OK":
        raise ValueError(f"API error: {data.get('status')}")
    element = data["rows"][0]["elements"][0]
    if element["status"] != "OK":
        raise ValueError(f"Element error: {element['status']}")
    return element["distance"]["value"] / 1000

@st.cache_data(show_spinner=False)
def calculate_distance(city1, city2):
    if city1 == city2:
        return 0
    key1 = f"{city1}|{city2}"
    key2 = f"{city2}|{city1}"

    if key1 in distance_cache:
        return distance_cache[key1]
    if key2 in distance_cache:
        return distance_cache[key2]

    try:
        dist = google_maps_distance(city1, city2)
        distance_cache[key1] = dist
        with open("distance_cache.json", "w", encoding="utf-8") as f:
            json.dump(distance_cache, f, ensure_ascii=False, indent=2)
        return dist
    except:
        distance_cache[key1] = 1e9
        with open("distance_cache.json", "w", encoding="utf-8") as f:
            json.dump(distance_cache, f, ensure_ascii=False, indent=2)
        return 1e9

# ---------------------- قراءة ملف المباريات ---------------------- #
def read_matches_file(file):
    try:
        df_raw = pd.read_excel(file, header=None)
        st.write("📋 أول 10 صفوف من الملف:")
        st.dataframe(df_raw.head(10))
        header_row = None
        for i in range(len(df_raw)):
            if df_raw.iloc[i].astype(str).str.contains("رقم المباراة").any():
                header_row = i
                break
        if header_row is None:
            return None, "❌ لم يتم العثور على صف يحتوي على 'رقم المباراة'."
        df = pd.read_excel(file, header=header_row)
        df.columns = df.columns.str.strip()
        if "التاريخ" in df.columns:
            def clean_date(value):
                if isinstance(value, str):
                    value = re.sub(r"^\D+\s*[-–]?\s*", "", value.strip())
                    return pd.to_datetime(value, errors="coerce")
                return pd.to_datetime(value, errors="coerce")
            df["التاريخ"] = df["التاريخ"].apply(clean_date)
        required_cols = ["رقم المباراة", "التاريخ", "الملعب", "المدينة"]
        if not all(col in df.columns for col in required_cols):
            return None, f"⚠️ الأعمدة الناقصة: {set(required_cols) - set(df.columns)}"
        df = df.dropna(subset=required_cols)
        if df.empty:
            return None, "⚠️ لا توجد مباريات بعد التنظيف."
        return df, None
    except Exception as e:
        return None, f"❌ خطأ في قراءة ملف المباريات: {e}"

# ---------------------- التعيين ---------------------- #
def assign_observers(matches, observers):
    assignments = []
    usage = {rid: 0 for rid in observers["رقم المراقب"]}
    last_dates = {}
    progress = st.progress(0, text="🔄 جاري تعيين المراقبين...")
    for idx, row in matches.iterrows():
        match_date = pd.to_datetime(row["التاريخ"], errors="coerce").date()
        city = str(row["المدينة"]).strip()
        stadium = str(row["الملعب"]).strip()
        candidates = observers.copy()
        def is_valid(obs):
            rid = obs["رقم المراقب"]
            if rid in last_dates:
                prev_date = last_dates[rid]
                if (match_date - prev_date).days < min_days_between:
                    return False
                if not allow_same_day and prev_date == match_date and obs["مدينة المراقب"] == city:
                    return False
            if use_distance:
                dist = calculate_distance(city, obs["مدينة المراقب"])
                if dist > max_distance:
                    return False
            return True
        candidates = candidates[candidates.apply(is_valid, axis=1)]
        if minimize_repeats:
            candidates["مرات التعيين"] = candidates["رقم المراقب"].map(usage)
            candidates = candidates.sort_values(by="مرات التعيين")
            candidates = candidates.drop(columns=["مرات التعيين"])
        if candidates.empty:
            assignments.append("غير متوفر")
        else:
            selected = candidates.iloc[0]
            assignments.append(f"{selected['الاسم الكامل']}\n[{selected['رقم المراقب']}]")
            rid = selected["رقم المراقب"]
            usage[rid] += 1
            last_dates[rid] = match_date
        progress.progress((idx + 1) / len(matches), text=f"🕐 جاري التعيين... ({idx+1}/{len(matches)})")
    matches["المراقب"] = assignments
    return matches

# ---------------------- المعالجة ---------------------- #
matches = None
observers = None

if matches_file:
    matches, match_error = read_matches_file(matches_file)
    if match_error:
        st.warning(match_error)
        matches = None
    else:
        st.success("✅ تم تحميل ملف المباريات بنجاح")
        st.dataframe(matches.head())

if observers_file:
    try:
        obs_raw = pd.read_excel(observers_file)
        obs_raw.columns = obs_raw.columns.str.strip()
        obs_raw["الاسم الكامل"] = (
            obs_raw["First name"].fillna("") + " " +
            obs_raw["2nd name"].fillna("") + " " +
            obs_raw["Family name"].fillna("")
        ).str.strip()
        obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()
        observers = obs_raw[["\u0631\u0642\u0645 \u0627\u0644\u0645\u0631\u0627\u0642\u0628", "\u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u0643\u0627\u0645\u0644", "\u0645\u062f\u064a\u0646\u0629 \u0627\u0644\u0645\u0631\u0627\u0642\u0628"]].dropna()
        st.success("✅ تم تحميل المراقبين بنجاح")
        st.dataframe(observers.head())
    except Exception as e:
        st.error(f"❌ خطأ في قراءة ملف المراقبين: {e}")
        observers = None

if matches is not None and observers is not None:
    st.markdown("### ✅ جاهز للتعيين")
    if st.button("🔄 تنفيذ التعيين"):
        try:
            result = assign_observers(matches.copy(), observers)
            st.success("✅ تم تنفيذ
