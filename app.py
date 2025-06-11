import streamlit as st
import pandas as pd
import datetime
import requests

st.set_page_config(
    page_title="Match Commissioners Assigner",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- الإعدادات الجانبية ---
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google API Key", type="password")

# --- رفع الملفات ---
st.title("📄 Match Commissioners Assigner")
st.markdown("**ارفع ملفات المباريات والمراقبين بالترتيب المطلوب (Excel):**")
matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

def calculate_distance(city1, city2, api_key):
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": city1, "destinations": city2, "key": api_key, "language": "ar"}
    response = requests.get(url, params=params)
    data = response.json()
    try:
        distance = data["rows"][0]["elements"][0]["distance"]["value"] / 1000  # بالكيلومتر
        return distance
    except:
        return float("inf")

def assign_observers(matches, observers):
    assignments = []
    assigned_days = {}
    observer_usage = {row["رقم المراقب"]: 0 for _, row in observers.iterrows()}
    last_assignment = {row["رقم المراقب"]: datetime.date(2000,1,1) for _, row in observers.iterrows()}

    for _, match in matches.iterrows():
        match_number = match.get("رقم المباراة")
        if pd.isna(match_number):
            assignments.append("❌ غير مخصص")
            continue

        # معالجة التاريخ مع اليوم
        try:
            match_date_str = str(match.get("التاريخ")).split("-")[-3:]
            match_date = pd.to_datetime("-".join(match_date_str), dayfirst=True).date()
        except:
            assignments.append("⚠️ تاريخ غير صالح")
            continue

        stadium = match.get("الملعب")
        city = match.get("المدينة")

        candidates = observers.copy()
        candidates["usage"] = candidates["رقم المراقب"].map(observer_usage)

        # استبعاد من عُيّن قبل أقل من X أيام
        if min_days_between > 0:
            candidates = candidates[candidates["رقم المراقب"].apply(lambda x: (match_date - last_assignment[x]).days >= min_days_between)]

        # منع التعيين المكرر في نفس اليوم باستثناء نفس الملعب
        if not allow_same_day:
            candidates = candidates[candidates["رقم المراقب"].apply(lambda x: assigned_days.get(x) != match_date or stadium == "")]

        # مسافة Google
        if use_distance and google_api_key:
            candidates["distance"] = candidates["مدينة المراقب"].apply(lambda c: calculate_distance(c, city, google_api_key))
            candidates = candidates[candidates["distance"] <= max_distance]

        # اختيار أقل استخدام
        if minimize_repeats:
            candidates = candidates.sort_values(by="usage")

        if not candidates.empty:
            chosen = candidates.iloc[0]
            observer_id = chosen["رقم المراقب"]
            assignments.append(f'{observer_id} - {chosen["الاسم الكامل"]}')
            observer_usage[observer_id] += 1
            last_assignment[observer_id] = match_date
            assigned_days[observer_id] = match_date
        else:
            assignments.append("❌ لا يوجد متاح")

    matches["المراقب"] = assignments
    return matches

# --- المعالجة ---
if matches_file and observers_file:
    matches = pd.read_excel(matches_file)
    obs_raw = pd.read_excel(observers_file)

    # معالجة ملف المراقبين
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

        output = result_df.to_excel(index=False)
        st.download_button("📥 تحميل الملف", data=output, file_name="assigned_matches.xlsx")
else:
    st.warning("⚠️ يرجى رفع كلا الملفين للمتابعة.")
