import streamlit as st

# -------------------------------
# Page Config
# -------------------------------
st.set_page_config(
    page_title="Manoj DevOps Portfolio",
    page_icon="🚀",
    layout="wide"
)

# -------------------------------
# Fake Login Credentials
# -------------------------------
USERNAME = "admin"
PASSWORD = "devops"

# -------------------------------
# Session State
# -------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


# -------------------------------
# Login Page
# -------------------------------
def login():

    st.title("🔐 Login to DevOps Dashboard")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if username == USERNAME and password == PASSWORD:
            st.session_state.logged_in = True
            st.success("Login Successful 🚀")
            st.rerun()

        else:
            st.error("Invalid Credentials")


# -------------------------------
# Dashboard
# -------------------------------
def dashboard():

    st.title("🚀 Manoj DevOps Learning Dashboard")

    st.success("Welcome to the DevOps Portfolio Platform")

    st.markdown("---")

    st.header("🤖 Interesting Facts About AI, DevOps & AWS")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🤖 AI Facts")

        st.write("""
        • AI can automate **40% of DevOps tasks** in the future.
        • AI is widely used in **Anomaly detection in monitoring tools**.
        • Tools like **GitHub Copilot** help developers write code faster.
        • AI helps in **predictive infrastructure scaling**.
        """)

    with col2:
        st.subheader("⚙️ DevOps Facts")

        st.write("""
        • DevOps reduces deployment failures by **60%**.
        • Companies deploying DevOps release **200x more frequently**.
        • Kubernetes is the **most popular container orchestration tool**.
        • CI/CD pipelines automate **build, test, and deployment**.
        """)

    with col3:
        st.subheader("☁️ AWS Facts")

        st.write("""
        • AWS has **200+ cloud services**.
        • AWS powers **Netflix, NASA, Airbnb and more**.
        • EC2 launched in **2006** changed cloud computing forever.
        • AWS Global infrastructure has **100+ availability zones**.
        """)

    st.markdown("---")

    # -------------------------------
    # Sidebar
    # -------------------------------

    st.sidebar.title("📂 Choose Profile")

    option = st.sidebar.selectbox(
        "Select Category",
        ["DevOps Projects", "AWS Projects", "Other Projects"]
    )

    st.header(option)

    if option == "DevOps Projects":

        st.subheader("⚙️ DevOps Project Video")

        st.video("https://youtu.be/oiCDvyxdFHs")

    elif option == "AWS Projects":

        st.subheader("☁️ AWS Project Video")

        st.video("https://youtu.be/oGF0HNcmre4")

    elif option == "Other Projects":

        st.subheader("💡 Other Project Video")

        st.video("https://youtu.be/H6jv8Y_SlAA")

    st.markdown("---")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()


# -------------------------------
# App Flow
# -------------------------------
if st.session_state.logged_in:
    dashboard()
else:
    login()