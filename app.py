import streamlit as st
import pandas as pd
import requests

# ---------------------------
# Page Configuration
# ---------------------------
st.set_page_config(page_title="Match Commissioners Assigner", page_icon="⚽", layout="wide")

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
        return meters / 1000  # كم
    except Exception:
        return 1e9  # قيمة كبيرة تعني مسافة غير مقبولة

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

        # تاريخ (مع تنظيف اليوم)
        raw_date = str(row["التاريخ"]).split("-")[-1].strip().split()[0]
        match_date = pd.to_datetime(raw_date, errors="coerce").date()
        city = str(row["المدينة"]).strip()
        stadium = str(row["الملعب"]).strip()

        # مرشحين أوليين
        cand = observers.copy()

        # استبعاد حسب نفس اليوم / الملعب
        def valid(o):
            rid = o["رقم المراقب"]
            if rid in last_dates:
                d = last_dates[rid]
                if (match_date - d).days < min_days_between:
                    return False
                if not allow_same_day and d == match_date:
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
# Processing
# ---------------------------
if matches_file and observers_file:
    # 1) Read matches with dynamic columns
    matches_raw = pd.read_excel(matches_file)
    matches_raw.columns = matches_raw.columns.str.strip()
    # محاولة العثور على الأعمدة الأساسية حتى لو كانت Unnamed
    def find_col(cols, keyword):
        return next(col for col in cols if keyword in str(col))

    cols = matches_raw.columns
    matches = matches_raw.rename(columns={
        find_col(cols, "رقم"): "رقم المباراة",
        find_col(cols, "اريخ"): "التاريخ",
        find_col(cols, "ملعب"): "الملعب",
        find_col(cols, "مدين"): "المدينة",
    })

    # 2) Read observers and clean columns
    obs_raw = pd.read_excel(observers_file)
    obs_raw.columns = obs_raw.columns.str.strip()

    obs_raw["الاسم الكامل"] = (
        obs_raw["الأسم الأول"].fillna("") + " " +
        obs_raw["الأسم الثاني"].fillna("") + " " +
        obs_raw["أسم العائلة"].fillna("")
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
