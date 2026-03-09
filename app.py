import streamlit as st
import pandas as pd
from datetime import datetime
import pdfplumber
from google.genai import Client
import sqlalchemy as sa

st.set_page_config(page_title="HR AI Assistant", page_icon="👩‍💼", layout="wide")

# ================= UI =================
st.markdown("""
<style>
.main {
background-color:#f5f7fb;
}
.stButton>button{
border-radius:8px;
height:40px;
font-weight:bold;
}
</style>
""", unsafe_allow_html=True)

st.title("👩‍💼 HR AI Assistant - Đồ án tốt nghiệp")
st.caption("Quản lý nhân sự tích hợp AI | Hải Phòng 2026")

# ================= GEMINI =================

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    client = Client(api_key=GEMINI_API_KEY)
    st.sidebar.success("✅ Gemini API đã kết nối")
except:
    st.error("❌ Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets")
    st.stop()

# ================= DATABASE =================

try:
    DATABASE_URL = st.secrets["connections"]["supabase"]["url"]

    engine = sa.create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )

except Exception as e:
    st.error(f"Lỗi kết nối database: {e}")
    st.stop()

metadata = sa.MetaData()

employees_table = sa.Table(
    'employees',
    metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('ho_ten', sa.String),
    sa.Column('email', sa.String),
    sa.Column('chuc_vu', sa.String),
    sa.Column('ngay_vao', sa.String),
    sa.Column('luong', sa.Float),
)

# ================= LOAD DATA =================

def load_data():
    with engine.connect() as conn:
        query = sa.select(employees_table)
        result = conn.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df

# ================= SESSION =================

if "employees" not in st.session_state:
    try:
        st.session_state.employees = load_data()
    except:
        st.session_state.employees = pd.DataFrame(
            columns=['id','ho_ten','email','chuc_vu','ngay_vao','luong']
        )

# ================= MENU =================

menu = st.sidebar.radio(
"Chọn chức năng",
["📋 Quản lý nhân viên","🤖 AI Chatbot HR","📄 AI Sàng lọc CV","📊 Thống kê"]
)

# =====================================================
# TAB 1 QUẢN LÝ NHÂN VIÊN
# =====================================================

if menu == "📋 Quản lý nhân viên":

    st.subheader("Danh sách nhân viên")

    search = st.text_input("🔎 Tìm kiếm nhân viên")

    df = st.session_state.employees

    if search:
        df = df[df["ho_ten"].str.contains(search,case=False)]

    if not df.empty:
        st.dataframe(df.style.format({"luong":"{:,.0f} ₫"}),use_container_width=True)
    else:
        st.info("Chưa có nhân viên")

    st.divider()

    # ================= ADD =================

    with st.form("add_employee"):

        col1,col2 = st.columns(2)

        with col1:
            ten = st.text_input("Họ và tên")
            email = st.text_input("Email")

        with col2:
            chucvu = st.selectbox(
            "Chức vụ",
            ["Nhân viên","Trưởng nhóm","Quản lý","Giám đốc"]
            )

            luong = st.number_input(
            "Lương",
            min_value=5000000,
            step=100000
            )

        submitted = st.form_submit_button("➕ Thêm nhân viên")

        if submitted and ten and email:

            new_row = {
            'ho_ten':ten,
            'email':email,
            'chuc_vu':chucvu,
            'ngay_vao':datetime.now().strftime("%d/%m/%Y"),
            'luong':luong
            }

            with engine.connect() as conn:
                conn.execute(employees_table.insert().values(**new_row))
                conn.commit()

            st.success("Đã thêm nhân viên")
            st.session_state.employees = load_data()
            st.rerun()

# =====================================================
# TAB 2 AI CHATBOT
# =====================================================

elif menu == "🤖 AI Chatbot HR":

    st.subheader("🤖 Chatbot HR")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Hỏi về HR..."):

        st.session_state.messages.append({"role":"user","content":prompt})

        with st.chat_message("assistant"):

            with st.spinner("Gemini AI đang suy nghĩ..."):

                response = client.models.generate_content(
                    model="models/gemini-3-flash-preview",
                    contents=f"Bạn là chuyên gia HR Việt Nam: {prompt}"
                )

                st.markdown(response.text)

                st.session_state.messages.append(
                    {"role":"assistant","content":response.text}
                )

# =====================================================
# TAB 3 CV AI
# =====================================================

elif menu == "📄 AI Sàng lọc CV":

    st.subheader("📄 AI Sàng lọc CV")

    jd = st.text_area("Job Description")

    uploaded_cv = st.file_uploader("Upload CV PDF",type="pdf")

    if st.button("Phân tích CV") and jd and uploaded_cv:

        text = ""

        with pdfplumber.open(uploaded_cv) as pdf:

            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text

        with st.spinner("AI đang phân tích..."):

            prompt = f"""
JD:
{jd}

CV:
{text[:6000]}

Đánh giá mức độ phù hợp.
"""

            response = client.models.generate_content(
            model="models/gemini-3-flash-preview",
            contents=prompt
            )

            st.markdown(response.text)

# =====================================================
# TAB 4 DASHBOARD
# =====================================================

elif menu == "📊 Thống kê":

    df = st.session_state.employees

    if not df.empty:

        col1,col2,col3 = st.columns(3)

        col1.metric("Nhân viên",len(df))
        col2.metric("Tổng lương",f"{df['luong'].sum():,.0f} ₫")
        col3.metric("Lương TB",f"{df['luong'].mean():,.0f} ₫")

        st.bar_chart(df.groupby('chuc_vu')['luong'].mean())

    else:
        st.info("Chưa có dữ liệu")

st.sidebar.success("Hệ thống hoạt động tốt")