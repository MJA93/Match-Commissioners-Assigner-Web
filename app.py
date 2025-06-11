import streamlit as st
import pandas as pd
import datetime
import requests

# إعدادات الصفحة
st.set_page_config(page_title="Match Commissioners Assigner", layout="wide")

# الشريط الجانبي: الإعدادات
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار تعيين المراقب", value=True)
use_distance = st.sidebar.checkbox("استخدام المسافة بين المدن (Google Maps)", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة (كم)", value=200)
google_api_key = st.sidebar.text_input("Google Maps API Key:")

# واجهة التحميل
st.title("📄 تعيين مراقبين للمباريات")
matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

# دالة لحساب المسافة باستخدام Google Maps
def calculate_distance(origin, destination):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destination,
        "key": google_api_key,
        "language": "ar",
        "units": "metric"
    }
    response = requests.get(url, params=params)
    data = response.json()
    try:
        distance = data["rows"][0]["elements"][0]["distance"]["value"] / 1000  # كم
        return distance
    except:
        return float("inf")

# دالة التعيين
def assign_observers(matches, observers):
    assignments = []
    observer_usage = {obs["رقم المراقب"]: 0 for _, obs in observers.iterrows()}
    assigned_days = {}

    for _, match in matches.iterrows():
        match_number = match.get("رقم المباراة")
        match_date_raw = str(match.get("التاريخ")).strip()
        if pd.isna(match_number) or not match_date_raw:
            assignments.append("—")
            continue

        try:
            match_date_str = match_date_raw.split(" - ")[-1]
            match_date = pd.to_datetime(match_date_str).date()
        except:
            assignments.append("—")
            continue

        match_city = str(match.get("المدينة")).strip()
        match_stadium = str(match.get("الملعب")).strip()

        candidates = observers.copy()
        candidates["المرات"] = candidates["رقم المراقب"].map(observer_usage)
        candidates = candidates.sort_values(by="المرات")

        def is_eligible(obs):
            obs_id = obs["رقم المراقب"]
            obs_city = obs["مدينة المراقب"].strip()

            if minimize_repeats and assignments.count(obs_id) > 0:
                return False
            if obs_id in assigned_days:
                for day, stadium in assigned_days[obs_id]:
                    delta = abs((match_date - day).days)
                    if delta < min_days_between:
                        return False
                    if not allow_same_day and (match_date == day and match_stadium != stadium):
                        return False
            if use_distance:
                distance = calculate_distance(obs_city, match_city)
                if distance > max_distance:
                    return False
            return True

        chosen = None
        for _, obs in candidates.iterrows():
            if is_eligible(obs):
                chosen = obs
                break

        if chosen is not None:
            obs_id = chosen["رقم المراقب"]
            assignments.append(obs_id)
            observer_usage[obs_id] += 1
            assigned_days.setdefault(obs_id, []).append((match_date, match_stadium))
        else:
            assignments.append("—")

    matches["المراقب"] = assignments
    return matches

# تنفيذ التعيين
if matches_file and observers_file:
    try:
        matches = pd.read_excel(matches_file)
        obs_raw = pd.read_excel(observers_file)

        # تجهيز عمود الاسم الكامل
        obs_raw["الاسم الكامل"] = (
            obs_raw["First name"].fillna("") + " " +
            obs_raw["2nd name"].fillna("") + " " +
            obs_raw["Family name"].fillna("")
        ).str.strip()

        # تجهيز المدينة
        obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()

        # تجهيز المراقبين النهائي
        observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()

        st.success("✅ تم تحميل الملفات بنجاح")

        if st.button("🔄 تنفيذ التعيين"):
            result_df = assign_observers(matches, observers)
            st.success("✅ تم التعيين بنجاح")
            st.dataframe(result_df)
            st.download_button("⬇️ تحميل الملف", data=result_df.to_excel(index=False), file_name="assigned_matches.xlsx")

    except Exception as e:
        st.error(f"حدث خطأ أثناء المعالجة: {e}")
else:
    st.warning("📂 يرجى رفع ملفي المباريات والمراقبين.")
