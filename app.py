import streamlit as st
import pandas as pd
import requests
import re
from io import BytesIO
import hashlib

st.set_page_config(page_title="Match Commissioners Assigner", page_icon="⚽", layout="wide")

# ------------------ الإعدادات ------------------ #
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=True)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=300)
google_api_key = st.sidebar.text_input("Google Maps API Key", type="password")

# ------------------ ذاكرة المسافات ------------------ #
distance_cache = {}
def get_distance_cache_key(city1, city2):
    sorted_cities = tuple(sorted([city1.strip().lower(), city2.strip().lower()]))
    return hashlib.md5(str(sorted_cities).encode()).hexdigest()

def calculate_distance_with_cache(city1, city2):
    if not (use_distance and google_api_key):
        return 0
    cache_key = get_distance_cache_key(city1, city2)
    if cache_key in distance_cache:
        return distance_cache[cache_key]
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": city1,
            "destinations": city2,
            "key": google_api_key,
            "units": "metric",
            "language": "ar",
        }
        response = requests.get(url, params=params).json()
        meters = response["rows"][0]["elements"][0]["distance"]["value"]
        km = meters / 1000
        distance_cache[cache_key] = km
        return km
    except:
        distance_cache[cache_key] = 1e9
        return 1e9

# ------------------ قراءة المباريات ------------------ #
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
            return None, "❌ لم يتم العثور على صف يحتوي 'رقم المباراة'."
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

# ------------------ التعيين ------------------ #
def assign_observers(matches, observers):
    assignments = []
    usage = {rid: 0 for rid in observers["رقم المراقب"]}
    last_dates = {}

    progress_bar = st.progress(0)
    total_matches = len(matches)

    for idx, (_, row) in enumerate(matches.iterrows()):
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
                if not allow_same_day and prev_date == match_date:
                    return False
            dist = calculate_distance_with_cache(city, obs["مدينة المراقب"])
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
            full_name = (
                selected["First name"].strip() + " " +
                selected["2nd name"].strip() + " " +
                selected["Family name"].strip()
            )
            assignments.append(f"{full_name} ({selected['رقم المراقب']})")
            rid = selected["رقم المراقب"]
            usage[rid] += 1
            last_dates[rid] = match_date

        progress_bar.progress((idx + 1) / total_matches)

    matches["المراقب"] = assignments
    return matches

# ------------------ الواجهة ------------------ #
st.title("📄 تعيين مراقبين للمباريات")

matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

matches = None
observers = None

if matches_file:
    matches, match_error = read_matches_file(matches_file)
    if match_error:
        st.warning(match_error)
        matches = None
    else:
        st.success("✅ تم تحميل ملف المباريات")
        st.dataframe(matches.head())

if observers_file:
    try:
        obs = pd.read_excel(observers_file)
        obs.columns = obs.columns.str.strip()
        obs["مدينة المراقب"] = obs["المدينة"].astype(str).str.strip()
        obs["الاسم الكامل"] = (
            obs["First name"].fillna("") + " " +
            obs["2nd name"].fillna("") + " " +
            obs["Family name"].fillna("")
        ).str.strip()
        observers = obs[["رقم المراقب", "First name", "2nd name", "Family name", "مدينة المراقب"]].dropna()
        st.success("✅ تم تحميل المراقبين")
        st.dataframe(observers.head())
    except Exception as e:
        st.error(f"❌ خطأ في قراءة ملف المراقبين: {e}")
        observers = None

if matches is not None and observers is not None:
    st.markdown("### ✅ جاهز للتعيين")
    if st.button("🔄 تنفيذ التعيين"):
        try:
            result = assign_observers(matches.copy(), observers)
            st.success("✅ تم تنفيذ التعيين بنجاح")
            st.dataframe(result)
            output = BytesIO()
            result.to_excel(output, index=False, engine="openpyxl")
            st.download_button("📥 تحميل الملف", data=output.getvalue(), file_name="assigned_matches.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.error(f"❌ خطأ أثناء التعيين: {e}")
