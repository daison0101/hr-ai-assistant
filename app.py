import streamlit as st
import pandas as pd
from datetime import datetime
import pdfplumber
from google.genai import Client
import sqlalchemy as sa
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="HR AI Assistant", page_icon="👩‍💼", layout="wide")

# ================= UI STYLE =================
st.markdown("""
<style>
.main{
background-color:#f5f7fb;
}
.stButton>button{
border-radius:8px;
height:40px;
font-weight:bold;
}
</style>
""", unsafe_allow_html=True)

st.title("👩‍💼 HR AI Assistant - Giáp Thanh Tuyền")
st.caption("Quản lý nhân sự tích hợp AI")

# ================= DATABASE =================

DATABASE_URL = os.getenv("DATABASE_URL")

engine = sa.create_engine(
DATABASE_URL,
pool_size=5,
max_overflow=10,
pool_pre_ping=True
)

metadata = sa.MetaData()

# USERS
users_table = sa.Table(
"users",
metadata,
sa.Column("id", sa.Integer, primary_key=True),
sa.Column("username", sa.String, unique=True),
sa.Column("password", sa.String)
)

# EMPLOYEES
employees_table = sa.Table(
'employees',
metadata,
sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
sa.Column('ho_ten', sa.String),
sa.Column('email', sa.String),
sa.Column('chuc_vu', sa.String),
sa.Column('ngay_vao', sa.String),
sa.Column('luong', sa.Float),
sa.Column('department_id', sa.Integer)
)

# DEPARTMENTS
departments_table = sa.Table(
"departments",
metadata,
sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
sa.Column("ten_phong", sa.String),
sa.Column("mo_ta", sa.String)
)

@st.cache_resource
def init_db():
    metadata.create_all(engine)

init_db()

# ================= GEMINI =================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = Client(api_key=GEMINI_API_KEY)

# ================= CACHE =================

@st.cache_data
def get_employees():
    with engine.connect() as conn:
        result = conn.execute(sa.select(employees_table))
        return pd.DataFrame(result.fetchall(), columns=result.keys())

@st.cache_data
def get_departments():
    with engine.connect() as conn:
        result = conn.execute(sa.select(departments_table))
        return pd.DataFrame(result.fetchall(), columns=result.keys())

# ================= LOGIN SESSION =================

if "login" not in st.session_state:
    st.session_state.login = False

# =====================================================
# LOGIN / REGISTER
# =====================================================

if not st.session_state.login:

    menu = st.sidebar.selectbox("Tài khoản",["Login","Register"])

    if menu == "Login":

        st.subheader("🔐 Đăng nhập")

        username = st.text_input("Username")
        password = st.text_input("Password",type="password")

        if st.button("Login"):

            with engine.connect() as conn:
                query = sa.select(users_table).where(
                    users_table.c.username==username
                )

                result = conn.execute(query).fetchone()

                if result and result.password == password:

                    st.session_state.login = True
                    st.success("Đăng nhập thành công")
                    st.rerun()

                else:
                    st.error("Sai tài khoản hoặc mật khẩu")

    if menu == "Register":

        st.subheader("📝 Tạo tài khoản")

        username = st.text_input("Username")
        password = st.text_input("Password",type="password")

        if st.button("Register"):

            with engine.connect() as conn:

                conn.execute(
                    users_table.insert().values(
                        username=username,
                        password=password
                    )
                )

                conn.commit()

            st.success("Tạo tài khoản thành công")

    st.stop()

# ===== LOGOUT =====

if st.sidebar.button("🚪 Logout"):
    st.session_state.login = False
    st.session_state.messages = []
    st.success("Đã đăng xuất")
    st.rerun()

# =====================================================
# MENU
# =====================================================

menu = st.sidebar.radio(
"Chọn chức năng",
[
"📋 Quản lý nhân viên",
"🏢 Quản lý phòng ban",
"🤖 AI Chatbot HR",
"📄 AI Sàng lọc CV",
"📊 Thống kê"
]
)

# =====================================================
# TAB EMPLOYEES
# =====================================================

if menu == "📋 Quản lý nhân viên":

    st.subheader("Danh sách nhân viên")

    df = get_employees()
    deps = get_departments()

    if not deps.empty:
        df = df.merge(
            deps[["id","ten_phong"]],
            left_on="department_id",
            right_on="id",
            how="left"
        )

        df = df.drop(columns=["department_id","id_y"])
        df = df.rename(columns={"id_x":"id","ten_phong":"phong_ban"})

    search = st.text_input("🔎 Tìm kiếm nhân viên")

    if search:
        df = df[df["ho_ten"].str.contains(search,case=False)]

    if not df.empty:

        df_show = df.rename(columns={
        "id":"ID",
        "ho_ten":"Họ và tên",
        "email":"Email",
        "chuc_vu":"Chức vụ",
        "ngay_vao":"Ngày vào",
        "luong":"Lương",
        "phong_ban":"Phòng ban"
        })

        st.dataframe(
        df_show.style.format({"Lương":"{:,.0f} ₫"}),
        use_container_width=True
        )

    else:
        st.info("Chưa có nhân viên")

    st.divider()

    # ADD EMPLOYEE

    with st.form("add_employee"):

        col1,col2 = st.columns(2)

        with col1:
            ten = st.text_input("Họ và tên *")
            email = st.text_input("Email *")

        with col2:

            chucvu = st.selectbox(
            "Chức vụ",
            ["Nhân viên","Trưởng nhóm","Quản lý","Giám đốc"]
            )

            department = st.selectbox(
            "Phòng ban",
            deps["ten_phong"] if not deps.empty else []
            )

            luong = st.number_input(
            "Lương",
            min_value=5000000,
            step=100000
            )

        submitted = st.form_submit_button("➕ Thêm nhân viên")

        if submitted:

            department_id = None

            if not deps.empty:
                department_id = int(deps[deps["ten_phong"] == department]["id"].values[0])

            with engine.connect() as conn:

                conn.execute(
                employees_table.insert().values(
                ho_ten=ten,
                email=email,
                chuc_vu=chucvu,
                department_id=department_id,
                ngay_vao=datetime.now().strftime("%d/%m/%Y"),
                luong=luong
                ))

                conn.commit()

            get_employees.clear()

            st.success("Đã thêm nhân viên")
            st.rerun()

    # EDIT EMPLOYEE

    if not df.empty:

        st.subheader("✏️ Sửa nhân viên")

        emp_id = st.selectbox("Chọn ID nhân viên", df["id"])

        emp = get_employees()
        emp = emp[emp["id"] == emp_id].iloc[0]

        new_name = st.text_input("Họ tên", value=emp["ho_ten"])
        new_email = st.text_input("Email", value=emp["email"])

        new_position = st.selectbox(
        "Chức vụ",
        ["Nhân viên","Trưởng nhóm","Quản lý","Giám đốc"]
        )

        new_salary = st.number_input("Lương", value=float(emp["luong"]))

        if st.button("💾 Cập nhật"):

            with engine.connect() as conn:

                conn.execute(
                employees_table.update()
                .where(employees_table.c.id == emp_id)
                .values(
                ho_ten=new_name,
                email=new_email,
                chuc_vu=new_position,
                luong=new_salary
                ))

                conn.commit()

            get_employees.clear()

            st.success("Cập nhật thành công")
            st.rerun()

    # DELETE EMPLOYEE

    if not df.empty:

        st.subheader("🗑 Xóa nhân viên")

        emp_delete = st.selectbox("Chọn nhân viên cần xóa", df["id"])

        if st.button("Xóa nhân viên"):

            with engine.connect() as conn:

                conn.execute(
                employees_table.delete()
                .where(employees_table.c.id == emp_delete)
                )

                conn.commit()

            get_employees.clear()

            st.success("Đã xóa")
            st.rerun()

# =====================================================
# TAB DEPARTMENTS
# =====================================================

elif menu == "🏢 Quản lý phòng ban":

    st.subheader("🏢 Quản lý phòng ban")

    df = get_departments()

    if not df.empty:

        df_show = df.rename(columns={
        "id":"ID",
        "ten_phong":"Tên phòng ban",
        "mo_ta":"Mô tả"
        })

        st.dataframe(df_show,use_container_width=True)

    else:
        st.info("Chưa có phòng ban")

    st.divider()

    with st.form("add_department"):

        ten = st.text_input("Tên phòng ban")
        mota = st.text_area("Mô tả")

        submit = st.form_submit_button("➕ Thêm phòng ban")

        if submit:

            with engine.connect() as conn:

                conn.execute(
                departments_table.insert().values(
                ten_phong=ten,
                mo_ta=mota
                ))

                conn.commit()

            get_departments.clear()

            st.success("Đã thêm phòng ban")
            st.rerun()

    if not df.empty:

        dep_id = st.selectbox("Chọn phòng ban cần xóa", df["id"])

        if st.button("🗑 Xóa phòng ban"):

            with engine.connect() as conn:

                conn.execute(
                departments_table.delete()
                .where(departments_table.c.id == dep_id)
                )

                conn.commit()

            get_departments.clear()

            st.success("Đã xóa")
            st.rerun()

# =====================================================
# TAB AI CHAT
# =====================================================

elif menu == "🤖 AI Chatbot HR":

    st.subheader("🤖 Chatbot HR")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Hiển thị lịch sử chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Nhập câu hỏi
    prompt = st.chat_input("Hỏi về nhân sự...")

    if prompt:

        # Lưu message user
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        # Hiển thị message user ngay lập tức
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI trả lời
        with st.chat_message("assistant"):
            with st.spinner("AI đang suy nghĩ..."):

                response = client.models.generate_content(
                    model="models/gemini-3-flash-preview",
                    contents=f"Bạn là chuyên gia HR Việt Nam có 15 năm kinh ngiệm. Trả lời ngắn gọn: {prompt}"
                )

                answer = response.text
                st.markdown(answer)

        # Lưu câu trả lời AI
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

# =====================================================
# TAB AI CV
# =====================================================

elif menu == "📄 AI Sàng lọc CV":

    st.subheader("AI Sàng lọc CV")

    jd = st.text_area("Job Description")

    uploaded_cv = st.file_uploader("Upload CV",type="pdf")

    if st.button("Phân tích") and jd and uploaded_cv:

        text = ""

        with pdfplumber.open(uploaded_cv) as pdf:

            for page in pdf.pages:

                t = page.extract_text()

                if t:
                    text += t

        with st.spinner("AI đang phân tích CV..."):

            prompt = f"""
Phân tích CV so với JD

JD:
{jd}

CV:
{text[:6000]}

Đánh giá điểm phù hợp 0-100 và khuyến nghị tuyển.
"""

            response = client.models.generate_content(
            model="models/gemini-3-flash-preview",
            contents=prompt
            )

            st.markdown(response.text)

# =====================================================
# TAB DASHBOARD
# =====================================================

elif menu == "📊 Thống kê":

    df = get_employees()

    if not df.empty:

        col1,col2,col3 = st.columns(3)

        col1.metric("Tổng nhân viên",len(df))
        col2.metric("Tổng lương",f"{df['luong'].sum():,.0f} ₫")
        col3.metric("Lương TB",f"{df['luong'].mean():,.0f} ₫")

        st.bar_chart(df.groupby('chuc_vu')['luong'].mean())

        if st.button("🤖 AI phân tích nhân sự"):

            with st.spinner("AI đang phân tích..."):

                prompt = f"""
Phân tích dữ liệu nhân sự sau:

{df.to_string()}

Đưa ra gợi ý quản lý nhân sự.
"""

                response = client.models.generate_content(
                model="models/gemini-3-flash-preview",
                contents=prompt
                )

                st.markdown(response.text)

    else:
        st.info("Chưa có dữ liệu")

st.sidebar.success("Hệ thống hoạt động tốt")