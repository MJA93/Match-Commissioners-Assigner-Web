import streamlit as st
import pandas as pd
import requests
import re
from io import BytesIO
from functools import lru_cache
from datetime import datetime

st.set_page_config(page_title="Match Commissioners Assigner", page_icon="⚽", layout="wide")

# ---------------- إعدادات الواجهة ---------------- #
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", min_value=0, value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=True)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", min_value=1, value=200)
google_api_key = st.sidebar.text_input("🔑 Google Maps API", type="password")

# ---------------- تحميل الملفات ---------------- #
st.title("📄 تعيين مراقبين للمباريات")
matches_file = st.file_uploader("📥 ملف المباريات", type="xlsx")
observers_file = st.file_uploader("📥 ملف المراقبين", type="xlsx")

# ---------------- دالة التصحيح ---------------- #
def correct_city(city):
    city = str(city).strip()
    return "الهفوف" if city == "الأحساء" else city

# ---------------- التخزين المؤقت للمسافات ---------------- #
@lru_cache(maxsize=10000)
def calculate_distance(city1, city2):
    if not (use_distance and google_api_key):
        return 0
    city1 = correct_city(city1)
    city2 = correct_city(city2)
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
        return meters / 1000
    except:
        return 1e9

# ---------------- قراءة ملف المباريات ---------------- #
def read_matches_file(file):
    try:
        df_raw = pd.read_excel(file, header=None)
        st.write("📋 أول 10 صفوف من الملف (للمراجعة):")
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

# ---------------- التعيين ---------------- #
def assign_observers(matches, observers):
    assignments = []
    usage = {rid: 0 for rid in observers["رقم المراقب"]}
    last_dates = {}

    progress = st.progress(0, text="🔄 جاري تنفيذ التعيين ...")
    total = len(matches)

    for i, row in matches.iterrows():
        match_date = pd.to_datetime(row["التاريخ"], errors="coerce").date()
        city = correct_city(row["المدينة"])
        stadium = str(row["الملعب"]).strip()
        location = stadium if stadium else city

        candidates = observers.copy()

        def is_valid(obs):
            rid = obs["رقم المراقب"]
            prev_date = last_dates.get(rid)

            if prev_date:
                if (match_date - prev_date).days < min_days_between:
                    return False
                if not allow_same_day and prev_date == match_date and obs["مدينة المراقب"] == city:
                    return False

            if use_distance:
                dist = calculate_distance(location, obs["مدينة المراقب"])
                if dist > max_distance:
                    return False
            return True

        candidates = candidates[candidates.apply(is_valid, axis=1)]

        if minimize_repeats:
            candidates["مرات التعيين"] = candidates["رقم المراقب"].map(usage)
            candidates = candidates.sort_values(by="مرات التعيين")
            candidates = candidates.drop(columns=["مرات التعيين"])

        if candidates.empty:
            assignments.append(("غير متوفر", ""))
        else:
            selected = candidates.iloc[0]
            assignments.append((selected["الاسم الكامل"], selected["رقم المراقب"]))
            rid = selected["رقم المراقب"]
            usage[rid] += 1
            last_dates[rid] = match_date

        progress.progress((i + 1) / total, text=f"🔄 تنفيذ التعيين ({i+1}/{total})")

    matches["المراقب"] = [x[0] for x in assignments]
    matches["رقم المراقب"] = [x[1] for x in assignments]
    return matches

# ---------------- قراءة البيانات ---------------- #
matches = None
observers = None

if matches_file:
    matches, match_error = read_matches_file(matches_file)
    if match_error:
        st.warning(match_error)
        matches = None
    else:
        st.success("✅ تم تحميل ملف المباريات بنجاح")

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
        observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()
        st.success("✅ تم تحميل المراقبين بنجاح")
    except Exception as e:
        st.error(f"❌ خطأ في قراءة ملف المراقبين: {e}")
        observers = None

# ---------------- تنفيذ التعيين ---------------- #
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
