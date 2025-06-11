import streamlit as st
import pandas as pd
import datetime
import requests

# ---------------------------
# Page Configuration
# ---------------------------
st.set_page_config(
    page_title="Match Commissioners Assigner",
    page_icon="⚽",
    layout="wide"
)

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
    if not google_api_key:
        return float('inf')
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": city1,
        "destinations": city2,
        "key": google_api_key,
        "units": "metric",
        "language": "ar"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        distance = data["rows"][0]["elements"][0]["distance"]["value"] / 1000
        return distance
    except:
        return float('inf')

# ---------------------------
# Core Assigner Function
# ---------------------------
def assign_observers(matches, observers):
    assignments = []
    observer_usage = {row['رقم المراقب']: 0 for _, row in observers.iterrows()}
    assigned_days = {}

    for _, match in matches.iterrows():
        match_id = match.get("رقم المباراة")
        match_date_str = str(match.get("التاريخ"))
        match_date_clean = match_date_str.split("-")[-1].strip().split()[0]
        match_date = pd.to_datetime(match_date_clean).date()
        match_city = str(match.get("المدينة")).strip()
        match_venue = str(match.get("الملعب")).strip()

        if pd.isna(match_id):
            assignments.append("—")
            continue

        candidates = observers.copy()

        if not allow_same_day:
            candidates = candidates[~candidates['رقم المراقب'].isin([
                rid for rid, day in assigned_days.items()
                if day == match_date and match_venue == match.get("الملعب")
            ])]

        if minimize_repeats:
            candidates = candidates.sort_values(by=candidates['رقم المراقب'].map(observer_usage))

        if use_distance:
            candidates["distance"] = candidates["مدينة المراقب"].apply(
                lambda x: calculate_distance(x, match_city)
            )
            candidates = candidates[candidates["distance"] <= max_distance]
            candidates = candidates.sort_values(by="distance")

        if not candidates.empty:
            chosen = candidates.iloc[0]
            observer_id = chosen["رقم المراقب"]
            observer_name = chosen["الاسم الكامل"]
            assignments.append(observer_name)
            observer_usage[observer_id] += 1
            assigned_days[observer_id] = match_date
        else:
            assignments.append("غير متوفر")

    matches["المراقب"] = assignments
    return matches

# ---------------------------
# Process Uploaded Files
# ---------------------------
if matches_file and observers_file:
    matches = pd.read_excel(matches_file)
    obs_raw = pd.read_excel(observers_file)

    # تجهيز اسم المراقب الكامل ومدينة المراقب
    obs_raw["الاسم الكامل"] = (
        obs_raw["First name"].fillna("") + " " +
        obs_raw["2nd name"].fillna("") + " " +
        obs_raw["Family name"].fillna("")
    ).str.strip()

    obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()
    observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()

    st.success("✅ تم تحميل الملفات بنجاح")

    if st.button("🔄 تنفيذ التعيين"):
        result_df = assign_observers(matches, observers)
        st.success("✅ تم تنفيذ التعيين")
        st.dataframe(result_df)
        st.download_button("📥 تنزيل الملف النهائي", data=result_df.to_excel(index=False), file_name="assigned_matches.xlsx")
else:
    st.warning("📌 يرجى رفع كلا الملفين للاستمرار.")
