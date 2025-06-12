import streamlit as st
import pandas as pd
import requests
import re
from io import BytesIO

st.set_page_config(page_title="Match Commissioners Assigner", layout="wide", initial_sidebar_state="expanded")

# ---------------------------
# Sidebar Settings
# ---------------------------
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("حساب المسافة بين المدن باستخدام Google Maps", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google Maps API Key", type="password")

# ---------------------------
# Google Maps API
# ---------------------------
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

# ---------------------------
# Core Logic
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

        match_date = pd.to_datetime(row["التاريخ"], errors="coerce").date()
        city = str(row["المدينة"]).strip()
        stadium = str(row["الملعب"]).strip()

        candidates = observers.copy()

        def is_valid(obs):
            rid = obs["رقم المراقب"]
            if rid in last_dates:
                if (match_date - last_dates[rid]).days < min_days_between:
                    return False
                if not allow_same_day and match_date == last_dates[rid] and obs["مدينة المراقب"] == city:
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
            usage[selected["رقم المراقب"]] += 1
            last_dates[selected["رقم المراقب"]] = match_date

    matches["المراقب"] = assignments
    return matches

# ---------------------------
# Match Reader
# ---------------------------
def read_matches_file(file):
    df_raw = pd.read_excel(file, header=None)
    header_index = None
    for i in range(len(df_raw)):
        if df_raw.iloc[i].astype(str).str.contains("رقم المباراة").any():
            header_index = i
            break
    if header_index is None:
        return None, "⚠️ لم يتم العثور على صف يحتوي على 'رقم المباراة' لتحديد بداية الجدول"
    df_matches = pd.read_excel(file, header=header_index)
    df_matches.columns = df_matches.columns.str.strip()
    df_matches = df_matches.dropna(subset=["رقم المباراة", "التاريخ", "الملعب", "المدينة"])

    # تنظيف التاريخ
    def clean_date(val):
        if isinstance(val, str):
            match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", val)
            if match:
                return pd.to_datetime(match.group(1), dayfirst=True)
            return pd.NaT
        return pd.to_datetime(val, errors="coerce")

    df_matches["التاريخ"] = df_matches["التاريخ"].apply(clean_date)
    df_matches = df_matches.dropna(subset=["التاريخ"])
    return df_matches, None

# ---------------------------
# واجهة المستخدم
# ---------------------------
st.title("📄 تعيين مراقبين للمباريات")
st.markdown("**🔼 رفع ملفات المباريات والمراقبين بالترتيب المطلوب (Excel):**")
matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

if matches_file and observers_file:
    try:
        matches_raw, error = read_matches_file(matches_file)
        if error:
            st.error(error)
            st.stop()

        obs_raw = pd.read_excel(observers_file)
        obs_raw.columns = obs_raw.columns.str.strip()
        obs_raw["الاسم الكامل"] = (
            obs_raw["First name"].fillna("") + " " +
            obs_raw["2nd name"].fillna("") + " " +
            obs_raw["Family name"].fillna("")
        ).str.strip()
        obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()
        observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()

        st.success("✅ تم تحميل الملفات بنجاح")
        st.dataframe(matches_raw.head())
        st.dataframe(observers.head())

        if st.button("🔄 تنفيذ التعيين"):
            result = assign_observers(matches_raw.copy(), observers)
            st.success("✅ تم تنفيذ التعيين بنجاح")
            st.dataframe(result)

            output = BytesIO()
            result.to_excel(output, index=False, engine='openpyxl')
            st.download_button("📥 تحميل الملف النهائي", data=output.getvalue(), file_name="assigned_matches.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"❌ حدث خطأ: {e}")
else:
    st.info("📌 الرجاء رفع ملفي المباريات والمراقبين للمتابعة.")
