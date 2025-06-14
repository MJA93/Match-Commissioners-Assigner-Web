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
use_distance = st.sidebar.checkbox("استخدام OpenRouteService لحساب المسافة", value=True)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)

# ---------------------- مفتاح ORS ---------------------- #
ORS_API_KEY = "5b3ce3597851110001cf624808a520e10a8e4f9abbc780d99a908202"  # مفتاح مؤقت قابل للتغيير

# ---------------------- رفع الملفات ---------------------- #
st.title("📄 تعيين مراقبين للمباريات")
matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])



# ---------------------- المسافة باستخدام ORS + Cache ---------------------- #
@st.cache_data(show_spinner=False)
def load_city_lookup():
    try:
        df = pd.read_csv("cities_lookup.csv")
        return dict(zip(df["\u0627\u0644\u0627\u0633\u0645_\u0628\u0627\u0644\u0639\u0631\u0628\u064a"], df["\u0627\u0644\u0627\u0633\u0645_\u0627\u0644\u0645\u0648\u062d\u062f"]))
    except:
        return {}

city_lookup = load_city_lookup()

def calculate_distance(city1, city2):
    if city1 == city2:
        return 0

    city1_std = city_lookup.get(city1.strip(), city1.strip())
    city2_std = city_lookup.get(city2.strip(), city2.strip())

    try:
        with open("distance_cache.json", "r", encoding="utf-8") as f:
            cache = json.load(f)
    except:
        cache = {}

    key = f"{city1_std}|{city2_std}"
    if key in cache:
        return cache[key]

    try:
        url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        headers = {
            'Authorization': ORS_API_KEY,
            'Content-Type': 'application/json'
        }
        
        def get_coords(city):
            geo = requests.get(
                f"https://api.openrouteservice.org/geocode/search?api_key={ORS_API_KEY}&text={city}&boundary.country=SA"
            ).json()
            coords = geo['features'][0]['geometry']['coordinates']
            return coords

        locations = [get_coords(city1_std), get_coords(city2_std)]

        body = {
            "locations": locations,
            "metrics": ["distance"],
            "units": "km"
        }

        response = requests.post(url, json=body, headers=headers).json()
        dist = response["distances"][0][1]

        cache[key] = dist
        with open("distance_cache.json", "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        return dist
    except:
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

        # تصحيح ترتيب الاسم: الأول + الثاني + العائلة
        obs_raw["الاسم الكامل"] = (
            obs_raw["First name"].fillna("") + " " +
            obs_raw["2nd name"].fillna("") + " " +
            obs_raw["Family name"].fillna("")
        ).str.strip()

        obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()
        observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()

        st.success("✅ تم تحميل المراقبين بنجاح")
        st.dataframe(observers.head())

    except Exception as e:
        st.error(f"❌ خطأ في قراءة ملف المراقبين: {e}")
        observers = None

# ---------------------- تنفيذ التعيين ---------------------- #
if matches is not None and observers is not None:
    st.markdown("### ✅ جاهز للتعيين")
    if st.button("🔄 تنفيذ التعيين"):
        try:
            result = assign_observers(matches.copy(), observers)
            st.success("✅ تم تنفيذ التعيين بنجاح")
            st.dataframe(result)

            output = BytesIO()
            result.to_excel(output, index=False, engine='openpyxl')
            st.download_button("📥 تحميل الملف النهائي", data=output.getvalue(), file_name="assigned_matches.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.error(f"❌ خطأ أثناء تنفيذ التعيين: {e}")
