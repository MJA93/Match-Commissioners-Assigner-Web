import streamlit as st
import pandas as pd
import requests
import re
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Match Commissioners Assigner by Harashi", page_icon="⚽", layout="wide", initial_sidebar_state="expanded")

# ---------------------- Sidebar ----------------------
st.sidebar.title("⚙️ الإعدادااااات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google Maps API Key", type="password")

# ---------------------- UI ----------------------
st.title("📄 تعيين مراقبين للمباريات")
st.markdown("**🔼 رفع ملفات المباريات والمراقبين بالترتيب المطلوب (Excel):**")

matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

# ---------------------- Google Distance ----------------------
def calculate_distance(city1, city2):
    if not (use_distance and google_api_key):
        return 0
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

# ---------------------- Read Matches File ----------------------
def read_matches_file(file):
    try:
        df_raw = pd.read_excel(file, header=None)
        match_header_index = None
        for i in range(len(df_raw)):
            if df_raw.iloc[i].astype(str).str.contains("رقم المباراة").any():
                match_header_index = i
                break
        if match_header_index is None:
            return None, "⚠️ لم يتم العثور على صف يحتوي على 'رقم المباراة'."
        
        df = pd.read_excel(file, header=match_header_index)
        df.columns = df.columns.str.strip()
        if "التاريخ" in df.columns:
            def clean_date(val):
                if isinstance(val, str):
                    m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", val)
                    if m:
                        return pd.to_datetime(m.group(1), dayfirst=True)
                    return pd.NaT
                return pd.to_datetime(val, errors="coerce")
            df["التاريخ"] = df["التاريخ"].apply(clean_date)
            df = df.dropna(subset=["التاريخ"])
        return df, None
    except Exception as e:
        return None, f"❌ خطأ أثناء قراءة ملف المباريات: {e}"

# ---------------------- Assignment Logic ----------------------
def assign_observers(matches, observers):
    assignments = []
    usage = {rid: 0 for rid in observers["رقم المراقب"]}
    last_dates = {}

    for _, row in matches.iterrows():
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
            candidates = candidates.sort_values(by=candidates["رقم المراقب"].map(usage))

        if candidates.empty:
            assignments.append("غير متوفر")
        else:
            selected = candidates.iloc[0]
            assignments.append(selected["الاسم الكامل"])
            rid = selected["رقم المراقب"]
            usage[rid] += 1
            last_dates[rid] = match_date

    matches["المراقب"] = assignments
    return matches

# ---------------------- Load Matches ----------------------
matches = None
if matches_file:
    matches, error = read_matches_file(matches_file)
    if error:
        st.error(error)
    elif matches is not None and len(matches) > 0:
        st.success("✅ تم تحميل مباريات")
        st.dataframe(matches.head())
    else:
        st.warning("⚠️ لم يتم العثور على أي مباريات داخل الملف.")

# ---------------------- Load Observers ----------------------
observers = None
if observers_file:
    try:
        obs_raw = pd.read_excel(observers_file)
        obs_raw.columns = obs_raw.columns.str.strip()
        obs_raw["الاسم الكامل"] = (
            obs_raw.get("First name", "") + " " +
            obs_raw.get("2nd name", "") + " " +
            obs_raw.get("Family name", "")
        ).str.strip()
        obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()
        observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()
        st.success("✅ تم تحميل المراقبين")
        st.dataframe(observers.head())
    except Exception as e:
        st.error(f"❌ خطأ في ملف المراقبين: {e}")

# ---------------------- Run Assignment ----------------------
if matches is not None and observers is not None:
    if st.button("🔄 تنفيذ التعيين"):
        result = assign_observers(matches.copy(), observers)
        st.success("✅ تم تنفيذ التعيين")
        st.dataframe(result)
        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        st.download_button("📥 تحميل الملف النهائي", data=output.getvalue(), file_name="assigned_matches.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
