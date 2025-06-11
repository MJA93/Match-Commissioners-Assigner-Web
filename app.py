import streamlit as st
import pandas as pd
import datetime
import requests
import io

st.set_page_config(
    page_title="Match Commissioners Assigner",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Sidebar Settings ---
st.sidebar.title("⚙️ الإعدادات")
allow_same_day = st.sidebar.checkbox("السماح بالتعيين بنفس اليوم (لنفس الملعب فقط)", value=True)
min_days_between = st.sidebar.number_input("عدد الأيام الدنيا بين تعيينين", value=2)
minimize_repeats = st.sidebar.checkbox("تقليل تكرار أسماء المراقبين", value=True)
use_distance = st.sidebar.checkbox("استخدام Google Maps لحساب المسافة", value=False)
max_distance = st.sidebar.number_input("أقصى مسافة بالكيلومترات", value=200)
google_api_key = st.sidebar.text_input("Google API Key", type="password")

# --- Upload Section ---
st.title("📄 Match Commissioners Assigner")
st.markdown("**ارفع ملفات المباريات والمراقبين بالترتيب المطلوب (Excel):**")

matches_file = st.file_uploader("📥 ملف المباريات", type=["xlsx"])
observers_file = st.file_uploader("📥 ملف المراقبين", type=["xlsx"])

if matches_file and observers_file:
    matches = pd.read_excel(matches_file)
    observers = pd.read_excel(observers_file)
    st.success("✅ تم تحميل الملفات بنجاح")
    if st.button("🔄 تنفيذ التعيين"):
        st.info("🚧 التعيين الفعلي سيتم تطويره في المرحلة التالية...")
        st.dataframe(matches.head())
else:
    st.warning("يرجى رفع كلا الملفين للاستمرار.")
