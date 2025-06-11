
import streamlit as st
import pandas as pd
import datetime
import requests

st.set_page_config(page_title="Match Commissioners Assigner", layout="wide")

# Sidebar Settings
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (لنفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google API Key", type="password")

st.title("📄 Match Commissioners Assigner")
st.markdown("**ارفع ملفات المباريات والمراقبين بالصيغ الرسمية (Excel):**")
matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

def calculate_distance(city1, city2, api_key):
    try:
        url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={city1}&destinations={city2}&key={api_key}&language=ar"
        response = requests.get(url).json()
        distance_text = response["rows"][0]["elements"][0]["distance"]["text"]
        distance_km = float(distance_text.replace("كم", "").strip())
        return distance_km
    except:
        return float("inf")

def assign_observers(matches, observers):
    assignments = []
    assigned = {}

    for _, match in matches.iterrows():
        match_number = match.get("رقم المباراة")
        match_date = pd.to_datetime(match.get("التاريخ")).date()
        match_city = str(match.get("مدينة الملعب")).strip()

        if pd.isna(match_number):
            continue

        found = False
        for _, observer in observers.iterrows():
            obs_id = observer["رقم المراقب"]
            obs_name = observer["الاسم الكامل"]
            obs_city = str(observer["مدينة المراقب"]).strip()

            if not obs_name or not obs_city:
                continue

            if obs_id in assigned:
                previous_dates = assigned[obs_id]
                if any(abs((match_date - d).days) < min_days_between for d in previous_dates):
                    continue
                if not allow_same_day and any(d == match_date for d in previous_dates):
                    continue

            if use_distance:
                distance = calculate_distance(match_city, obs_city, google_api_key)
                if distance > max_distance:
                    continue
            elif match_city != obs_city:
                continue

            if minimize_repeats and obs_id in assigned and len(assigned[obs_id]) > 0:
                continue

            assignments.append((match_number, obs_name, obs_id))
            assigned.setdefault(obs_id, []).append(match_date)
            found = True
            break

        if not found:
            assignments.append((match_number, "❌ لم يُعيّن", ""))

    assignment_dict = {row[0]: {"المراقب": row[1], "رقم المراقب": row[2]} for row in assignments}
    matches["المراقب"] = matches["رقم المباراة"].map(lambda x: assignment_dict.get(x, {}).get("المراقب", ""))
    matches["رقم المراقب"] = matches["رقم المباراة"].map(lambda x: assignment_dict.get(x, {}).get("رقم المراقب", ""))
    return matches

if matches_file and observers_file:
    matches = pd.read_excel(matches_file)
    obs_raw = pd.read_excel(observers_file)

    # تجهيز اسم المراقب الكامل + المدينة
# مستوى البلوك الرئيسي (0 مسافات إضافية)
obs_raw["الاسم الكامل"] = (
    # مستوى البلوك داخل القوس (4 مسافات إضافية)
    obs_raw["First name"].fillna("") + " " +
    obs_raw["2nd name"].fillna("") + " " +
    obs_raw["Family name"].fillna("")
).str.strip()

# هذه الأسطر كلها في نفس مستوى البلوك الرئيسي
obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()
observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()



    st.success("✅ تم تحميل الملفات بنجاح")

    if st.button("🔄 تنفيذ التعيين"):
        result_df = assign_observers(matches, observers)
        st.success("✅ تم تنفيذ التعيين")
        st.dataframe(result_df)

        output = result_df.to_excel(index=False)
        st.download_button("📥 تحميل النتائج", data=output, file_name="assigned_matches.xlsx")
else:
    st.warning("يرجى رفع كلا الملفين للاستمرار.")
