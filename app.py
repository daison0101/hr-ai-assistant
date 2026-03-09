import streamlit as st
import pandas as pd
from datetime import datetime
import pdfplumber
import io
from google.genai import Client
import os
from dotenv import load_dotenv
import sqlalchemy as sa

load_dotenv()

st.set_page_config(page_title="HR AI Assistant", page_icon="👩‍💼", layout="wide")

# ================= UI STYLE =================
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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("❌ Chưa có GEMINI_API_KEY")
    st.stop()

try:
    client = Client(api_key=GEMINI_API_KEY)
    st.sidebar.success("✅ Gemini AI đã kết nối")
except Exception as e:
    st.error(f"Lỗi Gemini: {e}")
    st.stop()

# ================= DATABASE =================

try:
    DATABASE_URL = st.secrets["DATABASE_URL"]

    engine = sa.create_engine(
        DATABASE_URL,
        connect_args={"sslmode": "require"}
    )

except KeyError:
    st.error("❌ Chưa cấu hình DATABASE_URL trong Streamlit Secrets")
    st.stop()

engine = sa.create_engine(DATABASE_URL)

metadata = sa.MetaData()

employees_table = sa.Table(
    'employees',
    metadata,
    sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('ho_ten', sa.String),
    sa.Column('email', sa.String),
    sa.Column('chuc_vu', sa.String),
    sa.Column('ngay_vao', sa.String),
    sa.Column('luong', sa.Float),
)

metadata.create_all(engine)

# ================= LOAD DATA =================

def load_data():
    with engine.connect() as conn:
        query = sa.select(employees_table)
        result = conn.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df

# ================= MENU =================

menu = st.sidebar.radio(
"Chọn chức năng",
[
"📋 Quản lý nhân viên",
"🤖 AI Chatbot HR",
"📄 AI Sàng lọc CV",
"📊 Thống kê"
]
)

# =====================================================
# TAB 1 QUẢN LÝ NHÂN VIÊN
# =====================================================

if menu == "📋 Quản lý nhân viên":

    df = load_data()

    st.subheader("Danh sách nhân viên")

    search = st.text_input("🔎 Tìm kiếm nhân viên")

    if search:
        df = df[df["ho_ten"].str.contains(search, case=False)]

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

        submit = st.form_submit_button("➕ Thêm nhân viên")

        if submit and ten and email:

            new_row = {
                "ho_ten":ten,
                "email":email,
                "chuc_vu":chucvu,
                "ngay_vao":datetime.now().strftime("%d/%m/%Y"),
                "luong":luong
            }

            with engine.connect() as conn:
                conn.execute(employees_table.insert().values(**new_row))
                conn.commit()

            st.success("Thêm nhân viên thành công")
            st.rerun()

    st.divider()

    # ================= EDIT =================

    if not df.empty:

        st.subheader("✏️ Sửa nhân viên")

        emp_id = st.selectbox("Chọn nhân viên",df["id"])

        emp = df[df["id"]==emp_id].iloc[0]

        new_name = st.text_input("Họ tên",value=emp["ho_ten"])
        new_email = st.text_input("Email",value=emp["email"])

        new_position = st.selectbox(
            "Chức vụ",
            ["Nhân viên","Trưởng nhóm","Quản lý","Giám đốc"]
        )

        new_salary = st.number_input(
            "Lương",
            value=float(emp["luong"])
        )

        if st.button("💾 Cập nhật"):

            with engine.connect() as conn:
                conn.execute(
                    employees_table.update()
                    .where(employees_table.c.id==emp_id)
                    .values(
                        ho_ten=new_name,
                        email=new_email,
                        chuc_vu=new_position,
                        luong=new_salary
                    )
                )

                conn.commit()

            st.success("Cập nhật thành công")
            st.rerun()

    st.divider()

    # ================= DELETE =================

    if not df.empty:

        st.subheader("🗑 Xóa nhân viên")

        emp_delete = st.selectbox(
            "Chọn nhân viên cần xóa",
            df["id"],
            key="delete"
        )

        if st.button("Xóa nhân viên"):

            with engine.connect() as conn:
                conn.execute(
                    employees_table.delete()
                    .where(employees_table.c.id==emp_delete)
                )

                conn.commit()

            st.success("Đã xóa")
            st.rerun()

# =====================================================
# TAB 2 CHATBOT
# =====================================================

elif menu == "🤖 AI Chatbot HR":

    st.subheader("🤖 Chatbot HR thông minh")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:

        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Hỏi về nhân sự, tuyển dụng..."):

        st.session_state.messages.append({"role":"user","content":prompt})

        with st.chat_message("assistant"):

            with st.spinner("AI đang suy nghĩ..."):

                response = client.models.generate_content(
                    model="models/gemini-3-flash-preview",
                    contents=f"Bạn là chuyên gia HR Việt Nam. Trả lời ngắn gọn: {prompt}"
                )

                st.markdown(response.text)

                st.session_state.messages.append(
                    {"role":"assistant","content":response.text}
                )

# =====================================================
# TAB 3 AI CV
# =====================================================

elif menu == "📄 AI Sàng lọc CV":

    st.subheader("📄 AI Sàng lọc CV")

    jd = st.text_area("Dán Job Description",height=150)

    uploaded_cv = st.file_uploader("Upload CV (PDF)",type="pdf")

    if st.button("🚀 Phân tích CV bằng AI") and jd and uploaded_cv:

        text=""

        with pdfplumber.open(uploaded_cv) as pdf:
            for page in pdf.pages:
                page_text=page.extract_text()
                if page_text:
                    text+=page_text

        prompt=f"""
Phân tích CV so với JD

JD:
{jd}

CV:
{text[:7000]}

Trả lời:

Tên ứng viên
Điểm phù hợp
Kỹ năng phù hợp
Điểm mạnh
Thiếu sót
Khuyến nghị tuyển hay không
"""

        response=client.models.generate_content(
            model="models/gemini-3-flash-preview",
            contents=prompt
        )

        st.markdown("### 📊 Kết quả phân tích AI")
        st.markdown(response.text)

# =====================================================
# TAB 4 DASHBOARD
# =====================================================

elif menu == "📊 Thống kê":

    df = load_data()

    st.subheader("📊 Thống kê nhân sự")

    if not df.empty:

        col1,col2,col3 = st.columns(3)

        col1.metric("Tổng nhân viên",len(df))
        col2.metric("Tổng lương",f"{df['luong'].sum():,.0f} ₫")
        col3.metric("Lương TB",f"{df['luong'].mean():,.0f} ₫")

        st.bar_chart(df.groupby('chuc_vu')['luong'].mean())

        st.divider()

        if st.button("🤖 AI Phân tích nhân sự"):

            prompt=f"""
Phân tích dữ liệu nhân sự sau:

{df.to_string()}

Hãy đưa ra:
- Nhân viên có hiệu suất cao
- Nhân viên nên tăng lương
- Gợi ý quản lý nhân sự
"""

            response=client.models.generate_content(
                model="models/gemini-3-flash-preview",
                contents=prompt
            )

            st.markdown(response.text)

    else:
        st.info("Chưa có dữ liệu")

st.sidebar.success("Hệ thống hoạt động tốt")