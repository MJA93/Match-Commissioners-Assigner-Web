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

# --- Sidebar Settings ---
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (لنفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين التعيينات", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("لحساب المسافة Google Maps استخدام", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google API Key", type="password")

# --- Upload Section ---
st.title("📄 Match Commissioners Assigner")
st.markdown("**ارفع ملفات المباريات والمراقبين بالترتيب المطلوϽ(Excel):**")

matches_file = st.file_uploader("📅 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("🔹 ملف المراقبين", type=["xlsx"])

def assign_observers(matches_file, observers_file):
    # --- قراءة المباريات ---
    matches_raw = pd.read_excel(matches_file, skiprows=1)
    cols = matches_raw.columns
    match_no_col = next(col for col in cols if "رقم" in str(col))
    date_col = next(col for col in cols if "اريخ" in str(col))
    stadium_col = next(col for col in cols if "ملعب" in str(col))
    city_col = next(col for col in cols if "مدين" in str(col))

    matches = matches_raw.rename(columns={
        match_no_col: "رقم المباراة",
        date_col: "التاريخ",
        stadium_col: "الملعب",
        city_col: "المدينة"
    })
    matches = matches.dropna(subset=["رقم المباراة"])
    matches["التاريخ"] = matches["التاريخ"].astype(str).apply(lambda x: x.split("-")[-1].strip())

    # --- قراءة المراقبين ---
    obs_raw = pd.read_excel(observers_file)
    obs_raw["الاسم الكامل"] = (
        obs_raw["First name"].fillna("") + " " +
        obs_raw["2nd name"].fillna("") + " " +
        obs_raw["Family name"].fillna("")
    ).str.strip()
    obs_raw["مدينة المراقب"] = obs_raw["المدينة"].astype(str).str.strip()
    observers = obs_raw[["رقم المراقب", "الاسم الكامل", "مدينة المراقب"]].dropna()

    # مخرجات تجريبية
    matches["المراقب"] = "---"
    return matches

if matches_file and observers_file:
    st.success("✅ تم تحميل الملفات بنجاح")

    if st.button("🔄 تنفيذ التعيين"):
        result_df = assign_observers(matches_file, observers_file)
        st.success("✅ تم تنفيذ التعيين")
        st.dataframe(result_df)

        output = result_df.to_excel(index=False)
        st.download_button("📂 تنزيل النتيجة", data=output, file_name="assigned_matches.xlsx")
else:
    st.warning("يرجى رفع كلا الملفين للاستمرار.")
