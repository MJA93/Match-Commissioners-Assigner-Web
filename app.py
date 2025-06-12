import streamlit as st
import pandas as pd
import requests
import datetime
import re
# ---------------------------
# Page Configuration
# ---------------------------
st.set_page_config(page_title="Match Commissioners Assigner", page_icon="⚽", layout="wide",initial_sidebar_state="expanded")

# ---------------------------
# Sidebar Settings
# ---------------------------
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google Maps API Key", type="password")

# ---------------------------
# File Uploads
# ---------------------------
st.title("📄 تعيين مراقبين للمباريات")
st.markdown("**🔼 رفع ملفات المباريات والمراقبين بالترتيب المطلوب (Excel):**")

matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

# ---------------------------
# Helper: Google Maps API
# ---------------------------
def calculate_distance(city1, city2):
    if not (use_distance and google_api_key):
        return 0
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": city1,
        "destinations": city2,
        "key": google_api_key,
        "units": "metric",
        "language": "ar",
    }
    try:
        resp = requests.get(url, params=params).json()
        meters = resp["rows"][0]["elements"][0]["distance"]["value"]
        return meters / 1000
    except Exception:
        return 1e9

# ---------------------------
# Core Assigner
# ---------------------------
def assign_observers(matches, observers):
    assignments = []
    usage = {rid: 0 for rid in observers["رقم المراقب"]}
    last_dates = {}

    for _, row in matches.iterrows():
        match_no = row["رقم المباراة"]
        if pd.isna(match_no):
            assignments.append("—")
            continue

        raw_date = str(row["التاريخ"]).split()[0]  # إزالة اليوم من بداية التاريخ
        match_date = pd.to_datetime(raw_date, errors="coerce").date()
        city = str(row["المدينة"]).strip()
        stadium = str(row["الملعب"]).strip()

        # المرشحين
        cand = observers.copy()

        def valid(o):
            rid = o["رقم المراقب"]
            if rid in last_dates:
                d = last_dates[rid]
                if (match_date - d).days < min_days_between:
                    return False
                if not allow_same_day and d == match_date and o["مدينة المراقب"] == city:
                    return False
            if use_distance:
                dist = calculate_distance(city, o["مدينة المراقب"])
                if dist > max_distance:
                    return False
            return True

        cand = cand[cand.apply(valid, axis=1)]
        if minimize_repeats:
            cand = cand.sort_values(by=cand["رقم المراقب"].map(usage))

        if cand.empty:
            assignments.append("غير متوفر")
            continue

        chosen = cand.iloc[0]
        rid = chosen["رقم المراقب"]
        assignments.append(chosen["الاسم الكامل"])
        usage[rid] += 1
        last_dates[rid] = match_date

    matches["المراقب"] = assignments
    return matches

# ---------------------------
# File Handling
# ---------------------------
if matches_file and observers_file:
    try:
        matches_raw = pd.read_excel(matches_file, header=1)
        matches_raw.columns = matches_raw.columns.str.strip()
        cols = matches_raw.columns

        col_match_number = next((c for c in cols if "رقم" in c and "مباراة" in c), None)
        col_match_date = next((c for c in cols if "تاريخ" in c), None)
        col_stadium = next((c for c in cols if "ملعب" in c), None)
        col_city = next((c for c in cols if "مدينة" in c), None)

        if not all([col_match_number, col_match_date, col_stadium, col_city]):
            st.error(f"⚠️ الأعمدة المطلوبة غير موجودة أو غير واضحة.
الأعمدة الحالية: {list(cols)}")
        else:
            matches = matches_raw[[col_match_number, col_match_date, col_stadium, col_city]].dropna()

            # تنظيف التاريخ
            def clean_date(value):
                if isinstance(value, str):
                    match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", value)
                    if match:
                        return pd.to_datetime(match.group(1), dayfirst=True)
                    return pd.NaT
                return pd.to_datetime(value, errors="coerce")

            matches[col_match_date] = matches[col_match_date].apply(clean_date)
            matches = matches.dropna(subset=[col_match_date])

            obs_raw = pd.read_excel(observers_file)
            obs_raw.columns = obs_raw.columns.str.strip()

            col_id = next((c for c in obs_raw.columns if "رقم" in c), None)
            col_first = next((c for c in obs_raw.columns if "first" in c.lower()), None)
            col_second = next((c for c in obs_raw.columns if "2nd" in c.lower()), None)
            col_family = next((c for c in obs_raw.columns if "family" in c.lower()), None)
            col_city_obs = next((c for c in obs_raw.columns if "مدينة" in c), None)

            if not all([col_id, col_first, col_family, col_city_obs]):
                st.error(f"⚠️ الأعمدة الأساسية للمراقبين غير موجودة.
الأعمدة الحالية: {list(obs_raw.columns)}")
            else:
                obs_raw["الاسم الكامل"] = (
                    obs_raw[col_first].fillna("") + " " +
                    obs_raw.get(col_second, "").fillna("") + " " +
                    obs_raw[col_family].fillna("")
                ).str.strip()
                obs_raw["مدينة المراقب"] = obs_raw[col_city_obs].astype(str).str.strip()
                observers = obs_raw[[col_id, "الاسم الكامل", "مدينة المراقب"]].dropna()

                st.success("✅ تم تحميل الملفات بنجاح")
                st.dataframe(matches.head())
                st.dataframe(observers.head())

    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء معالجة الملفات: {e}")
else:
    st.warning("يرجى رفع كلا الملفين للاستمرار.")

