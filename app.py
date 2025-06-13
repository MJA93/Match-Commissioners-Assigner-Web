import streamlit as st
import pandas as pd
import requests
import datetime
import re
from io import BytesIO

st.set_page_config(page_title="Match Commissioners Assigner by Harashi", page_icon="⚽", layout="wide")

# الإعدادات الجانبية
st.sidebar.title("⚙️ الإعدادااات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (نفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google Maps API Key", type="password")

# واجهة تحميل الملفات
st.title("📄 تعيين مراقبين للمباريات")
st.markdown("**🔼 رفع ملفات المباريات والمراقبين بالترتيب المطلوب (Excel):**")

matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

# دالة حساب المسافة بين مدينتين
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

# دالة تنظيف التاريخ
def clean_date(value):
    if isinstance(value, str):
        match = re.search(r"(\d{4}-\d{2}-\d{2})|(\d{1,2}/\d{1,2}/\d{4})", value)
        if match:
            return pd.to_datetime(match.group(0), errors="coerce")
        return pd.NaT
    return pd.to_datetime(value, errors="coerce")

# دالة قراءة ملف المباريات تلقائيًا
def read_matches_file(file):
    df_raw = pd.read_excel(file, header=None)
    header_row = None

    for i in range(len(df_raw)):
        if df_raw.iloc[i].astype(str).str.contains("رقم المباراة").any():
            header_row = i
            break

    if header_row is None:
        return None, "⚠️ لم يتم العثور على صف يحتوي على 'رقم المباراة' لتحديد بداية الجدول"

    df_matches = pd.read_excel(file, header=header_row)
    df_matches.columns = df_matches.columns.str.strip()

    expected_cols = ["رقم المباراة", "التاريخ", "الملعب", "المدينة"]
    missing = [col for col in expected_cols if col not in df_matches.columns]

    if missing:
        return None, f"⚠️ لم يتم العثور على الأعمدة التالية في الملف: {missing}"

    df_matches = df_matches.dropna(subset=["الملعب", "المدينة", "التاريخ"])
    if "رقم المباراة" in df_matches.columns:
        df_matches = df_matches[df_matches["رقم المباراة"].notna()]

    df_matches["التاريخ"] = df_matches["التاريخ"].apply(clean_date)
    df_matches = df_matches.dropna(subset=["التاريخ"])

    return df_matches, None


# دالة تعيين المراقبين
def assign_observers(matches, observers):
    assignments = []
    usage = {rid: 0 for rid in observers["رقم المراقب"]}
    last_dates = {}

    for _, row in matches.iterrows():
        match_no = row.get("رقم المباراة", None)
        match_date = pd.to_datetime(row["التاريخ"], errors="coerce").date()
        city = str(row["المدينة"]).strip()
        stadium = str(row["الملعب"]).strip()

        candidates = observers.copy()

        def is_valid(o):
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

        candidates = candidates[candidates.apply(is_valid, axis=1)]

        if minimize_repeats and "رقم المراقب" in candidates.columns:
            candidates["__usage__"] = candidates["رقم المراقب"].map(usage)
            candidates = candidates.sort_values(by="__usage__")

        if candidates.empty:
            assignments.append("غير متوفر")
            continue

        chosen = candidates.iloc[0]
        rid = chosen["رقم المراقب"]
        assignments.append(chosen["الاسم الكامل"])
        usage[rid] += 1
        last_dates[rid] = match_date

    matches["المراقب"] = assignments
    return matches

# تنفيذ المعالجة عند تحميل الملفات
if matches_file:
    matches, match_error = read_matches_file(matches_file)
    if match_error:
        st.warning(match_error)
        matches = None
    else:
        st.success("✅ تم تحميل مباريات بنجاح")
        st.markdown("### أول 10 صفوف من ملف المباريات (للمراجعة):")
        st.dataframe(matches.head(10))

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
        st.dataframe(observers.head())
    except Exception as e:
        st.error(f"خطأ في ملف المراقبين: {e}")
        observers = None
else:
    observers = None

# تنفيذ التعيين
if matches_file and observers_file and matches is not None and observers is not None:
    if st.button("🔄 تنفيذ التعيين"):
        result = assign_observers(matches.copy(), observers)
        st.success("✅ تم تنفيذ التعيين بنجاح")
        st.dataframe(result)

        output = BytesIO()
        result.to_excel(output, index=False, engine="openpyxl")
        st.download_button("📥 تحميل الملف النهائي", data=output.getvalue(), file_name="assigned_matches.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
