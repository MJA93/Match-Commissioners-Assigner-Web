import streamlit as st
import pandas as pd
import requests
import re
from io import BytesIO

st.set_page_config(page_title="Match Commissioners Assigner", page_icon="⚽", layout="wide")

# واجهة التحكم
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google Maps API Key", type="password")

st.title("📄 تعيين مراقبين للمباريات")
matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

# دالة المسافة
def calculate_distance(city1, city2):
    if not (use_distance and google_api_key): return 0
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": city1, "destinations": city2,
            "key": google_api_key, "units": "metric", "language": "ar"
        }
        response = requests.get(url, params=params).json()
        return response["rows"][0]["elements"][0]["distance"]["value"] / 1000
    except:
        return 1e9

# عرض الصفوف الأولى للمعاينة
if matches_file:
    st.info("📌 أول 10 صفوف من ملف المباريات (للمراجعة):")
    df_preview = pd.read_excel(matches_file, header=None, nrows=10)
    st.dataframe(df_preview)

# دالة استخراج البيانات من ملف المباريات بذكاء
def read_matches_file(file):
    df_raw = pd.read_excel(file, header=None)
    header_row = None
    for i, row in df_raw.iterrows():
        if row.astype(str).str.contains("رقم المباراة").any():
            header_row = i
            break
    if header_row is None:
        return None, "⚠️ لم يتم العثور على صف يحتوي على 'رقم المباراة'"

    df_matches = pd.read_excel(file, header=header_row)
    df_matches.columns = df_matches.columns.str.strip()

    # محاولة كشف الأعمدة الأساسية
    col_match = next((c for c in df_matches.columns if "رقم" in c and "مباراة" in c), None)
    col_date = next((c for c in df_matches.columns if "تاريخ" in c), None)
    col_stadium = next((c for c in df_matches.columns if "ملعب" in c), None)
    col_city = next((c for c in df_matches.columns if "مدينة" in c), None)

    if not all([col_match, col_date, col_stadium, col_city]):
        return None, "⚠️ الأعمدة الأساسية غير مكتملة"

    # تنظيف التاريخ
def clean_date(value):
    if isinstance(value, str):
        # يحذف أي كلمة قبل التاريخ مثل "الجمعة -"
        value = re.sub(r"^\D+\s*[-–]\s*", "", value.strip())
        try:
            return pd.to_datetime(value, errors='coerce')
        except:
            return pd.NaT
    return pd.to_datetime(value, errors='coerce')

    df_matches[col_date] = df_matches[col_date].apply(clean_date)
    df_matches = df_matches.dropna(subset=[col_match, col_date, col_city, col_stadium])
    return df_matches[[col_match, col_date, col_stadium, col_city]], None

# تعيين المراقبين
def assign_observers(matches, observers):
    assignments = []
    usage = {rid: 0 for rid in observers["رقم المراقب"]}
    last_dates = {}

    for _, row in matches.iterrows():
        match_date = pd.to_datetime(row["التاريخ"], errors='coerce').date()
        city = str(row["المدينة"]).strip()
        stadium = str(row["الملعب"]).strip()

        candidates = observers.copy()

        def is_valid(obs):
            rid = obs["رقم المراقب"]
            if rid in last_dates:
                d = last_dates[rid]
                if (match_date - d).days < min_days_between:
                    return False
                if not allow_same_day and d == match_date and obs["مدينة المراقب"] == city:
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

# معالجة وتحميل البيانات
if matches_file and observers_file:
    matches, match_error = read_matches_file(matches_file)
    if match_error:
        st.warning(match_error)
    else:
        st.success("✅ تم تحميل مباريات بنجاح")
        st.dataframe(matches)

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
        st.dataframe(observers)

        if st.button("🔄 تنفيذ التعيين"):
            result = assign_observers(matches.copy(), observers)
            st.success("✅ تم تنفيذ التعيين")
            st.dataframe(result)

            output = BytesIO()
            result.to_excel(output, index=False, engine='openpyxl')
            st.download_button("📥 تحميل الملف النهائي", data=output.getvalue(), file_name="assigned_matches.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("📌 يرجى رفع كلا الملفين للمتابعة.")
