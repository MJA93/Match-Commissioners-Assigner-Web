import streamlit as st
import pandas as pd
import datetime
import requests

st.set_page_config(page_title="Match Commissioners Assigner", page_icon="⚽", layout="wide")

# --- الإعدادات الجانبية ---
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (لنفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين تعيينين", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google API Key", type="password")

# --- دالة حساب المسافة ---
def calculate_distance(city1, city2, api_key):
    if city1 == city2:
        return 0
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={city1}&destinations={city2}&key={api_key}&language=ar"
    response = requests.get(url)
    if response.status_code == 200:
        try:
            meters = response.json()["rows"][0]["elements"][0]["distance"]["value"]
            return meters / 1000
        except:
            return None
    return None

# --- دالة التعيين ---
def assign_observers(matches_df, observers_df):
    assignments = []
    observer_last_dates = {}
    observer_usage = {name: 0 for name in observers_df["اسم المراقب"]}

    for index, match in matches_df.iterrows():
        match_number = match.get("رقم المباراة")
        if pd.isna(match_number):
            assignments.append("غير متوفر")
            continue

        try:
            match_date = pd.to_datetime(str(match.get("التاريخ"))).date()
        except:
            assignments.append("غير متوفر")
            continue

        match_city = match.get("المدينة")
        match_stadium = match.get("الملعب")

        available = []
        for _, obs in observers_df.iterrows():
            name = obs["اسم المراقب"]
            city = obs["مدينة المراقب"]

            last_date = observer_last_dates.get(name)
            if last_date:
                if (match_date - last_date).days < min_days_between:
                    continue

            if not allow_same_day:
                if name in assignments:
                    continue

            if use_distance:
                distance = calculate_distance(match_city, city, google_api_key)
                if distance is None or distance > max_distance:
                    continue

            available.append((name, observer_usage[name]))

        if not available:
            assignments.append("غير متوفر")
            continue

        available.sort(key=lambda x: x[1])
        chosen = available[0][0]
        assignments.append(chosen)
        observer_last_dates[chosen] = match_date
        observer_usage[chosen] += 1

    matches_df["المراقب"] = assignments
    return matches_df

# --- واجهة التطبيق ---
st.title("📄 Match Commissioners Assigner")
st.markdown("**ارفع ملفات المباريات والمراقبين (Excel):**")

matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

if matches_file and observers_file:
    matches_df = pd.read_excel(matches_file)
    observers_df = pd.read_excel(observers_file)

    st.success("✅ تم تحميل الملفات بنجاح")

    if st.button("🔄 تنفيذ التعيين"):
        with st.spinner("🚀 جاري تنفيذ التعيين..."):
            assigned = assign_observers(matches_df, observers_df)
            st.success("✅ تم تنفيذ التعيين")
            st.dataframe(assigned)

            output = assigned.to_excel(index=False, engine="openpyxl")
            st.download_button("📥 تحميل الملف المعين", output, file_name="assigned_matches.xlsx")
else:
    st.warning("يرجى رفع كلا الملفين للاستمرار.")
