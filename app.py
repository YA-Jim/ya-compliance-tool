import io
import os
import re
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px
import plotly.graph_objects as go

try:
    import pdfplumber
except Exception:
    pdfplumber = None

APP_TITLE = "Young Academics Compliance Benchmarking Tool"
APP_VERSION = "v2.6 — Polished Upload Review"
DB_PATH = "compliance_history.sqlite3"
LOGO_URL = "https://www.youngacademics.com.au/application/themes/youngacademics/assets/images/logo.svg"
SIGNIFICANT_LAWS = {"165", "166", "167"}

DEFAULT_PROVIDER_RULES = [
    ("Young Academics", ["young academics"]),
    ("Affinity", ["milestones", "papilio", "kids academy", "bambino", "kindy patch", "world of learning", "great beginnings", "community kids", "aussie kindies", "narellan world of learning", "denham court world of learning"]),
    ("OSHClub & Helping Hands", ["oshclub", "helping hands", "os hclub"]),
    ("Little Zak's Academy", ["little zak", "little zaks"]),
    ("Jenny's Kindergarten", ["jenny's kindergarten", "jennys kindergarten"]),
    ("Oz Education", ["oz education"]),
    ("Only About Children", ["only about children"]),
    ("TheirCare", ["theircare"]),
    ("Guardian Childcare/Education", ["guardian childcare", "guardian child care", "guardian"]),
    ("Goodstart Early Learning", ["goodstart"]),
    ("Camp Australia", ["camp australia"]),
    ("Busy Bees", ["busy bees"]),
    ("Mini Masterminds", ["mini masterminds"]),
    ("TeamKids", ["teamkids"]),
    ("SCECS OSHC", ["scecs"]),
    ("Aspire OSHC", ["aspire oshc"]),
    ("Story House Early Learning", ["story house"]),
    ("MindChamps", ["mindchamps"]),
    ("Montessori Academy", ["montessori academy"]),
    ("Reggio Emilia Early Learning", ["reggio emilia"]),
    ("Learn & Laugh", ["learn & laugh"]),
]

LAW_RE = re.compile(r"\b(?:Law\s*)?(165|166|167|161A|162A|\d{2,3}[A-Z]?)\s*(?:\([^\)]*\))?", re.I)
REG_RE = re.compile(r"\bRegulation\s*(\d{2,3}[A-Z]*(?:AAC|AA|A|B|C|D)?)\s*(?:\([^\)]*\))?", re.I)
ID_RE = re.compile(r"\b((?:SE|PR)-\d{8})\b")
DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")

st.set_page_config(page_title=APP_TITLE, page_icon="🔒", layout="wide")

YA_CSS = """
<style>
:root{
  --ya-bg:#357b84;
  --ya-bg2:#2c6f77;
  --ya-navy:#08245c;
  --ya-teal:#357b84;
  --ya-teal-dark:#00504f;
  --ya-button:#8edfe4;
  --ya-button-hover:#a7eef2;
  --ya-soft:#eaf6f8;
  --ya-line:#b8dce1;
  --ya-yellow:#fff200;
  --ya-ink:#10242a;
}
html, body, [data-testid="stAppViewContainer"]{
  background:linear-gradient(180deg,var(--ya-bg) 0%, var(--ya-bg2) 100%) !important;
  color:#ffffff !important;
}
[data-testid="stHeader"]{background:transparent!important;}
.block-container{padding-top:1.25rem; padding-bottom:3rem; max-width:1280px;}

/* Main header */
.ya-shell{
  background:rgba(255,255,255,.96);
  border-radius:24px;
  padding:24px 28px;
  box-shadow:0 18px 42px rgba(0,0,0,.18);
  margin-bottom:22px;
  border:1px solid rgba(255,255,255,.72);
}
.ya-header{display:flex; align-items:center; justify-content:space-between; gap:18px;}
.ya-brand{display:flex; align-items:center; gap:22px;}
.ya-logo{width:200px; max-width:34vw; background:#fff; padding:6px; border-radius:14px;}
.ya-title h1{font-size:31px; line-height:1.06; color:#357b84!important; margin:0; font-weight:900; letter-spacing:-.02em; text-shadow:none!important;}
.ya-title p{margin:4px 0 0 0; color:var(--ya-teal-dark)!important; font-size:15px;}
.ya-version{background:var(--ya-navy); color:#fff; border-radius:999px; padding:9px 14px; font-weight:900; font-size:12px; white-space:nowrap; box-shadow:0 6px 14px rgba(8,36,92,.18);}
.ya-note{margin-top:16px; padding:14px 16px; border-left:5px solid var(--ya-teal); background:var(--ya-soft); border-radius:14px; color:var(--ya-teal-dark)!important; font-weight:650;}
.ya-disclaimer{margin-top:10px; font-size:12px; line-height:1.4; color:#35535a!important;}

/* Section cards */
.ya-section-card{
  background:rgba(255,255,255,.13);
  border:1px solid rgba(255,255,255,.25);
  border-radius:22px;
  padding:20px;
  margin:14px 0 22px;
  box-shadow:0 10px 28px rgba(0,0,0,.10);
}
.ya-panel-title{font-size:22px; font-weight:900; color:#fff; margin:0 0 12px;}
.ya-pill{display:inline-block; background:#ffffff; color:var(--ya-teal-dark); border:1px solid var(--ya-line); border-radius:999px; padding:7px 11px; font-weight:900; font-size:12px; margin:2px 6px 2px 0;}
.ya-warning{background:#fff8c9; border:2px solid var(--ya-yellow); color:#372f00; border-radius:16px; padding:12px 16px; margin:16px 0; box-shadow:0 6px 16px rgba(0,0,0,.12);}
.ya-warning *{color:#372f00!important;}

/* Headings and body text */
h1,h2,h3,h4,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3{color:#ffffff!important; font-weight:900!important;}
.ya-shell h1,.ya-shell .ya-title h1{color:#357b84!important;}
.ya-shell p,.ya-shell strong{color:#00504f!important;}
p,li,.stMarkdown,.stCaption,[data-testid="stCaptionContainer"]{color:#eefbfc!important;}
label,[data-testid="stWidgetLabel"],[data-testid="stWidgetLabel"] p{color:#ffffff!important; font-weight:800!important;}

/* Inputs */
input, textarea, select{border-radius:12px!important; color:#10242a!important; background:#ffffff!important;}
[data-baseweb="input"], [data-baseweb="select"], [data-baseweb="textarea"]{border-radius:12px!important; background:#ffffff!important; color:#10242a!important;}
[data-baseweb="select"] *{color:#10242a!important;}
[data-baseweb="popover"] *{color:#10242a!important;}
[data-baseweb="menu"] *{color:#10242a!important; background:#ffffff!important;}
[data-baseweb="menu"] li, [role="option"], [role="option"] *{color:#10242a!important; background:#ffffff!important;}
[data-baseweb="menu"] li:hover, [role="option"]:hover{background:#eaf6f8!important;}
/* Disabled buttons remain readable */
.stButton>button:disabled,.stDownloadButton>button:disabled{background:#dceff2!important; color:#357b84!important; box-shadow:none!important; opacity:.95!important;}
[data-baseweb="tag"]{background:#357b84!important; color:#fff!important; border-radius:8px!important;}
[data-baseweb="tag"] span{color:#fff!important;}
.stSelectbox div, .stMultiSelect div, .stTextInput div{color:#10242a!important;}


/* File uploaders */
[data-testid="stFileUploader"] section{
  background:rgba(234,246,248,.16)!important;
  border:1.5px dashed rgba(255,255,255,.55)!important;
  border-radius:18px!important;
}
[data-testid="stFileUploaderDropzone"]{
  background:rgba(234,246,248,.16)!important;
  border:1.5px dashed rgba(255,255,255,.55)!important;
  border-radius:18px!important;
}
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] p{color:#ffffff!important;}
[data-testid="stFileUploaderDropzone"] svg,
[data-testid="stFileUploaderDropzone"] path{color:var(--ya-button)!important; fill:var(--ya-button)!important;}
[data-testid="stFileUploader"] button{
  background:linear-gradient(180deg,var(--ya-button),#61c9d0)!important;
  color:#00393c!important;
  border:0!important;
  border-radius:12px!important;
  font-weight:900!important;
  box-shadow:0 5px 0 #1d6d75, 0 10px 18px rgba(0,0,0,.18)!important;
}
[data-testid="stFileUploader"] button:hover{background:linear-gradient(180deg,var(--ya-button-hover),#74d8df)!important; color:#002f32!important;}

/* Buttons */
.stButton>button,.stDownloadButton>button{
  background:linear-gradient(180deg,var(--ya-button),#61c9d0)!important;
  color:#00393c!important;
  border:0!important;
  border-radius:999px!important;
  padding:.72rem 1.15rem!important;
  font-weight:900!important;
  box-shadow:0 6px 0 #1d6d75, 0 13px 22px rgba(0,0,0,.22)!important;
  transition:transform .08s ease, box-shadow .08s ease, filter .12s ease!important;
}
.stButton>button:hover,.stDownloadButton>button:hover{filter:brightness(1.04)!important; transform:translateY(-1px)!important; box-shadow:0 7px 0 #1d6d75, 0 15px 26px rgba(0,0,0,.25)!important;}
.stButton>button:active,.stDownloadButton>button:active{transform:translateY(5px)!important; box-shadow:0 1px 0 #1d6d75, 0 8px 14px rgba(0,0,0,.22)!important;}

/* Expander / accordion */
[data-testid="stExpander"]{
  background:rgba(255,255,255,.10)!important;
  border:1px solid rgba(255,255,255,.24)!important;
  border-radius:18px!important;
  overflow:hidden;
}
[data-testid="stExpander"] summary p{color:#ffffff!important; font-weight:900!important;}

/* Executive KPI cards */
[data-testid="stMetric"]{
  background:#ffffff!important;
  border:1px solid var(--ya-line)!important;
  padding:18px 18px!important;
  border-radius:20px!important;
  box-shadow:0 10px 24px rgba(0,0,0,.16)!important;
  min-height:112px;
}
[data-testid="stMetric"] *{color:var(--ya-navy)!important;}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] *{color:var(--ya-teal)!important; font-weight:900!important;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] *{color:var(--ya-navy)!important; font-weight:950!important;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:10px; border-bottom:1px solid rgba(255,255,255,.18); padding-bottom:8px;}
.stTabs [data-baseweb="tab"]{
  border-radius:999px!important;
  padding:9px 18px!important;
  background:#eaf6f8!important;
  border:1px solid var(--ya-line)!important;
  color:var(--ya-teal-dark)!important;
  font-weight:900!important;
}
.stTabs [data-baseweb="tab"] p{color:var(--ya-teal-dark)!important; font-weight:900!important;}
.stTabs [aria-selected="true"]{background:var(--ya-navy)!important; border-color:var(--ya-navy)!important;}
.stTabs [aria-selected="true"] p{color:#ffffff!important;}

/* Tables */
[data-testid="stDataFrame"]{background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 10px 22px rgba(0,0,0,.14);}
[data-testid="stDataFrame"] *{color:#10242a!important;}

/* Notes cards */
.ya-note-grid{display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:14px; margin:12px 0 18px;}
.ya-note-card{background:#ffffff; border-radius:18px; padding:16px; min-height:145px; box-shadow:0 10px 22px rgba(0,0,0,.16); border:1px solid #b8dce1;}
.ya-note-card h4{margin:0 0 8px 0; color:#00504f!important; font-size:14px;}
.ya-note-card p{margin:0; color:#10242a!important; font-size:13px; line-height:1.35;}
@media(max-width:900px){.ya-note-grid{grid-template-columns:1fr 1fr}.ya-header{align-items:flex-start}.ya-brand{align-items:flex-start}.ya-logo{width:150px}.ya-title h1{font-size:24px}}


/* Multi-select cleanup: removes the odd white dot/pill artefact */
[data-baseweb="tag"]::before, [data-baseweb="tag"]::after{display:none!important; content:none!important;}
[data-baseweb="tag"]{padding-left:10px!important; margin-left:0!important;}
[data-baseweb="tag"] > div:first-child{display:none!important;}
[data-testid="stMultiSelect"] [data-baseweb="tag"]{background:#357b84!important; border:1px solid #8edfe4!important;}

/* Clean white content panels */
.ya-white-panel{background:#ffffff; border-radius:22px; padding:18px; box-shadow:0 10px 24px rgba(0,0,0,.14); border:1px solid #b8dce1; margin:12px 0 18px;}
.ya-white-panel h3,.ya-white-panel h4{color:#00504f!important; margin-top:0;}
.ya-white-panel p,.ya-white-panel li{color:#10242a!important;}

.ya-provider-title{background:#ffffff; border-radius:24px; padding:24px; box-shadow:0 12px 28px rgba(0,0,0,.16); border-left:8px solid #8edfe4; margin-bottom:18px;}
.ya-provider-title h1{color:#00504f!important; margin:0 0 6px 0;}
.ya-provider-title p{color:#10242a!important; margin:0;}

/* Modern glass dashboard */
.ya-dashboard-card{
  background:rgba(255,255,255,.18);
  border:1px solid rgba(255,255,255,.32);
  border-radius:26px;
  padding:18px 18px 10px;
  box-shadow:0 18px 38px rgba(0,0,0,.16);
  backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);
  margin:8px 0 18px;
}
.ya-dashboard-card h3{
  color:#ffffff!important;
  margin:0 0 6px 0!important;
  padding:0 4px 8px 4px!important;
  font-size:18px!important;
  letter-spacing:-.01em;
}
.ya-chart-caption{color:#d8f4f6!important; font-size:12px; margin-top:-4px; padding-left:4px;}



/* Upload review table - no dimming/backdrop during edits */
[data-baseweb="modal"]{background:transparent!important;}
[data-baseweb="modal"] > div{background:transparent!important;}
[data-baseweb="popover"]{z-index:999999!important; opacity:1!important;}
[data-baseweb="popover"] ul{max-height:320px!important; overflow:auto!important;}
[data-testid="stAppViewContainer"], .main, .block-container{opacity:1!important; filter:none!important;}

.ya-upload-review-card{
  background:#ffffff;
  border-radius:20px;
  overflow:hidden;
  box-shadow:0 14px 30px rgba(0,0,0,.16);
  border:1px solid #b8dce1;
  margin:14px 0 22px;
}
.ya-upload-row{
  border-bottom:1px solid #e2edf0;
  padding:8px 10px;
  color:#10242a!important;
}
.ya-upload-head{
  background:#f2f6f8;
  border-bottom:1px solid #d8e6ea;
  padding:10px;
  font-weight:900;
  color:#51636b!important;
}
.ya-upload-file{font-weight:750; color:#10242a!important; padding-top:8px; overflow-wrap:anywhere;}
.ya-upload-status{font-weight:750; color:#10242a!important; padding-top:8px; font-size:13px;}
.ya-upload-remove button{
  width:42px!important;
  height:40px!important;
  padding:0!important;
  border-radius:12px!important;
  background:#ffffff!important;
  color:#b42318!important;
  box-shadow:none!important;
  border:1.5px solid #f4b0aa!important;
  font-size:17px!important;
}
.ya-upload-remove button:hover{background:#fff1f0!important; transform:none!important; box-shadow:none!important;}
.ya-upload-review-card [data-testid="column"]{padding:0 4px!important;}



/* v2.6 polished upload review */
.ya-review-shell{
  margin:16px 0 10px;
}
.ya-review-intro{
  background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.28);
  border-radius:22px;
  padding:16px 18px;
  box-shadow:0 12px 28px rgba(0,0,0,.12);
  backdrop-filter:blur(10px);
}
.ya-review-eyebrow{
  color:#ffffff!important;
  font-weight:950;
  font-size:18px;
  letter-spacing:-.01em;
}
.ya-review-copy{
  color:#d9f4f6!important;
  font-size:13px;
  margin-top:2px;
}
.ya-review-card{
  background:rgba(255,255,255,.96);
  border:1px solid rgba(255,255,255,.72);
  border-radius:22px;
  padding:16px 18px 18px;
  margin:14px 0;
  box-shadow:0 14px 28px rgba(0,0,0,.16);
}
.ya-file-block{
  display:flex;
  align-items:center;
  gap:12px;
  margin-bottom:12px;
  padding-bottom:12px;
  border-bottom:1px solid #d9ebef;
}
.ya-file-icon{
  width:46px;
  height:46px;
  border-radius:14px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:#eaf6f8;
  color:#00504f!important;
  font-size:11px;
  font-weight:950;
  border:1px solid #b8dce1;
}
.ya-file-name{
  color:#10242a!important;
  font-size:15px;
  line-height:1.25;
  font-weight:900;
  overflow-wrap:anywhere;
}
.ya-file-sub{
  color:#536b72!important;
  font-size:12px;
  margin-top:3px;
}
.ya-file-sub strong{color:#00504f!important;}
.ya-review-card [data-testid="column"]{padding:0 .35rem!important;}
.ya-review-card [data-testid="stCaptionContainer"],
.ya-review-card [data-testid="stCaptionContainer"] *{
  color:#00504f!important;
  font-size:11px!important;
  font-weight:950!important;
  text-transform:uppercase;
  letter-spacing:.04em;
}
.ya-review-card [data-baseweb="select"]{
  min-height:44px!important;
  border:1px solid #c9dde1!important;
  border-radius:14px!important;
  background:#f8fbfc!important;
}
.ya-review-card [data-baseweb="select"] *{
  color:#10242a!important;
  font-size:14px!important;
  font-weight:700!important;
}
.ya-status-badge{
  display:inline-block;
  padding:10px 12px;
  border-radius:999px;
  font-size:12px;
  font-weight:950;
  line-height:1.15;
  max-width:100%;
}
.ya-status-badge.ready{background:#e8fff3; color:#006b3d!important; border:1px solid #7ce0ad;}
.ya-status-badge.check{background:#fff5dc; color:#805300!important; border:1px solid #ffd27a;}
.ya-status-badge.duplicate{background:#ffecec; color:#a61616!important; border:1px solid #ff9d9d;}
.ya-review-card .stButton>button{
  width:44px!important;
  height:44px!important;
  min-height:44px!important;
  padding:0!important;
  border-radius:14px!important;
  background:#fff4f3!important;
  color:#b42318!important;
  border:1px solid #ffb4ad!important;
  box-shadow:0 4px 10px rgba(180,35,24,.12)!important;
  font-size:17px!important;
}
.ya-review-card .stButton>button:hover{
  background:#ffe7e5!important;
  color:#7a130b!important;
  transform:translateY(-1px)!important;
}
.ya-review-card .stButton>button:active{
  transform:translateY(1px)!important;
  box-shadow:none!important;
}
.ya-removed-note{
  background:#eaf6f8;
  color:#00504f!important;
  border:1px solid #b8dce1;
  border-radius:16px;
  padding:12px 14px;
  font-weight:800;
  margin:12px 0 18px;
}
@media(max-width:900px){
  .ya-review-card{padding:14px;}
  .ya-file-name{font-size:13px;}
}

/* Hide Streamlit menu/footer */
#MainMenu, footer{visibility:hidden;}
</style>
"""
st.markdown(YA_CSS, unsafe_allow_html=True)



def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return digest.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    check, _ = hash_password(password, salt)
    return check == stored_hash


def ensure_default_users():
    """Creates the initial admin users if they do not already exist."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_password = "YA2026!#123"
    for email in ["james.mh@youngacademics.com.au", "eric@youngacademics.com.au"]:
        exists = cur.execute("SELECT email FROM users WHERE email=?", (email,)).fetchone()
        if not exists:
            pw_hash, salt = hash_password(default_password)
            cur.execute(
                "INSERT INTO users(email, password_hash, salt, role, active, created_at, updated_at, created_by) VALUES (?,?,?,?,?,?,?,?)",
                (email, pw_hash, salt, "admin", 1, now, now, "system"),
            )
    con.commit(); con.close()


def current_user_email() -> str:
    return st.session_state.get("current_user", {}).get("email", "")


def current_user_role() -> str:
    return st.session_state.get("current_user", {}).get("role", "")


def is_admin() -> bool:
    return current_user_role() == "admin"


def log_audit(action: str, detail: str = ""):
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT INTO audit_logs(timestamp, user_email, role, action, detail) VALUES (?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), current_user_email() or "system", current_user_role() or "system", action, detail),
        )
        con.commit(); con.close()
    except Exception:
        pass


def authenticate_user(email: str, password: str):
    email = (email or "").strip().lower()
    if not email.endswith("@youngacademics.com.au"):
        return None, "Only @youngacademics.com.au emails are permitted."
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT email, password_hash, salt, role, active FROM users WHERE lower(email)=?", (email,)).fetchone()
    con.close()
    if not row:
        return None, "User not found. Ask an admin to create your account."
    if int(row[4]) != 1:
        return None, "This user is inactive. Ask an admin to reactivate the account."
    if not verify_password(password, row[1], row[2]):
        return None, "Invalid password."
    return {"email": row[0], "role": row[3]}, None


def render_login_screen():
    st.markdown(f"""
    <div class='ya-shell' style='max-width:820px;margin:7vh auto 24px;'>
      <div class='ya-header'>
        <div class='ya-brand'>
          <img class='ya-logo' src='{LOGO_URL}' />
          <div class='ya-title'>
            <h1>Compliance Benchmarking System</h1>
            <p>Secure internal access for Young Academics users</p>
          </div>
        </div>
        <div class='ya-version'>Role Login</div>
      </div>
      <div class='ya-note'>Admins can upload, delete and manage users. Standard users can view and export data only.</div>
      <div class='ya-disclaimer'>This system and its outputs are the property of Young Academics Early Learning Centre. Any unauthorised access, use, copying, distribution, or disclosure is strictly prohibited.</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.form("simple_login_form"):
            email = st.text_input("Email", placeholder="name@youngacademics.com.au")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
        if submitted:
            user, err = authenticate_user(email, password)
            if err:
                st.error(err)
            else:
                st.session_state["current_user"] = user
                log_audit("login", "Successful login")
                st.rerun()


def require_login():
    init_db(create_defaults=True)
    if st.session_state.get("current_user"):
        return
    render_login_screen()
    st.stop()


def logout_button():
    c1, c2, c3 = st.columns([5, 2, 1])
    with c2:
        st.caption(f"Signed in: {current_user_email()} · {current_user_role().upper()}")
    with c3:
        if st.button("Logout", key="logout_btn"):
            log_audit("logout", "User logged out")
            st.session_state.pop("current_user", None)
            st.rerun()


def render_admin_user_manager_panel():
    if not is_admin():
        st.info("Admin user management is available to admins only.")
        return
    st.markdown("### Admin users")
    st.caption("Only admins can create users/admins, change passwords, deactivate accounts, and view audit logs.")
    con = sqlite3.connect(DB_PATH)
    users_df = pd.read_sql_query("SELECT email, role, active, created_at, updated_at, created_by FROM users ORDER BY role, email", con)
    logs_df = pd.read_sql_query("SELECT timestamp, user_email, role, action, detail FROM audit_logs ORDER BY timestamp DESC LIMIT 250", con)
    con.close()

    st.markdown("#### Current users")
    st.dataframe(users_df, use_container_width=True, hide_index=True, key="admin_users_table")

    c_create, c_edit = st.columns(2)
    with c_create:
        st.markdown("#### Create user / admin")
        with st.form("create_user_form"):
            new_email = st.text_input("New user email", placeholder="name@youngacademics.com.au")
            new_role = st.selectbox("Role", ["user", "admin"], key="new_user_role")
            new_pw = st.text_input("Set password", type="password", key="new_user_password")
            create_user = st.form_submit_button("Create account")
        if create_user:
            email = (new_email or "").strip().lower()
            if not email.endswith("@youngacademics.com.au"):
                st.error("User must have a @youngacademics.com.au email.")
            elif not new_pw:
                st.error("Enter a password.")
            else:
                try:
                    pw_hash, salt = hash_password(new_pw)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    con = sqlite3.connect(DB_PATH)
                    con.execute(
                        "INSERT INTO users(email, password_hash, salt, role, active, created_at, updated_at, created_by) VALUES (?,?,?,?,?,?,?,?)",
                        (email, pw_hash, salt, new_role, 1, now, now, current_user_email()),
                    )
                    con.commit(); con.close()
                    log_audit("create_user", f"Created {new_role}: {email}")
                    st.success(f"Created {new_role}: {email}")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That user already exists.")

    with c_edit:
        st.markdown("#### Change password / role / status")
        user_options = users_df["email"].tolist() if not users_df.empty else []
        if user_options:
            target = st.selectbox("Select user", user_options, key="admin_target_user")
            target_row = users_df[users_df["email"].eq(target)].iloc[0] if target else None
            role_index = ["user", "admin"].index(str(target_row["role"])) if target_row is not None and str(target_row["role"]) in ["user","admin"] else 0
            status_index = 0 if target_row is not None and int(target_row["active"]) == 1 else 1
            with st.form("edit_user_form"):
                new_role2 = st.selectbox("Role", ["user", "admin"], index=role_index, key="edit_user_role")
                active2 = st.selectbox("Status", ["Active", "Inactive"], index=status_index, key="edit_user_status")
                new_pw2 = st.text_input("New password (leave blank to keep current)", type="password", key="edit_user_password")
                update_user = st.form_submit_button("Update selected user")
            if update_user:
                if target == current_user_email() and active2 == "Inactive":
                    st.error("You cannot deactivate your own account while signed in.")
                else:
                    con = sqlite3.connect(DB_PATH)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    con.execute("UPDATE users SET role=?, active=?, updated_at=? WHERE email=?", (new_role2, 1 if active2 == "Active" else 0, now, target))
                    if new_pw2:
                        pw_hash, salt = hash_password(new_pw2)
                        con.execute("UPDATE users SET password_hash=?, salt=?, updated_at=? WHERE email=?", (pw_hash, salt, now, target))
                    con.commit(); con.close()
                    log_audit("update_user", f"Updated {target}: role={new_role2}, status={active2}, password_changed={bool(new_pw2)}")
                    st.success("User updated.")
                    st.rerun()

    with st.expander("Recent audit logs", expanded=False):
        st.dataframe(logs_df, use_container_width=True, hide_index=True, key="admin_audit_logs_table")


def init_db(create_defaults: bool = False):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            run_id TEXT, quarter TEXT, report_type TEXT, action_id TEXT,
            entity_id TEXT, provider TEXT, service_name TEXT, date_issued TEXT,
            action_type TEXT, raw_text TEXT, processed_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS breaches (
            run_id TEXT, quarter TEXT, action_id TEXT, provider TEXT,
            breach_code TEXT, breach_family TEXT, classification TEXT, processed_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, quarter TEXT, processed_at TEXT,
            actions_count INTEGER, breaches_count INTEGER, notes TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            run_id TEXT, quarter TEXT, report_type TEXT, file_name TEXT,
            file_signature TEXT, actions_count INTEGER, breaches_count INTEGER,
            processed_at TEXT, PRIMARY KEY (quarter, report_type)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','user')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            created_by TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_email TEXT,
            role TEXT,
            action TEXT,
            detail TEXT
        )
    """)
    # Backward-compatible column adds.
    for table in ["actions", "breaches"]:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN processed_at TEXT")
        except sqlite3.OperationalError:
            pass
    for table in ["actions", "reports", "runs"]:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN uploaded_by TEXT")
        except sqlite3.OperationalError:
            pass
    con.commit(); con.close()
    if create_defaults:
        ensure_default_users()


def save_to_db(actions: pd.DataFrame, breaches: pd.DataFrame, report_meta: pd.DataFrame = None, uploaded_by: str = ""):
    con = sqlite3.connect(DB_PATH)
    processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not actions.empty:
        actions = actions.copy()
        if "processed_at" not in actions.columns:
            actions["processed_at"] = processed_at
        if "uploaded_by" not in actions.columns:
            actions["uploaded_by"] = uploaded_by or current_user_email()
        actions.to_sql("actions", con, if_exists="append", index=False)
    if not breaches.empty:
        breaches = breaches.copy()
        if "processed_at" not in breaches.columns:
            breaches["processed_at"] = processed_at
        breaches.to_sql("breaches", con, if_exists="append", index=False)
    if not actions.empty:
        run_id = str(actions["run_id"].iloc[0])
        quarters = sorted([str(q) for q in actions["quarter"].dropna().unique().tolist()])
        quarter = quarters[0] if len(quarters) == 1 else f"Bulk upload — {len(quarters)} quarters"
        con.execute("INSERT OR REPLACE INTO runs(run_id, quarter, processed_at, actions_count, breaches_count, notes, uploaded_by) VALUES (?,?,?,?,?,?,?)", (run_id, quarter, processed_at, len(actions), len(breaches), "", uploaded_by or current_user_email()))
    if report_meta is not None and not report_meta.empty:
        report_meta = report_meta.copy()
        if "processed_at" not in report_meta.columns:
            report_meta["processed_at"] = processed_at
        if "uploaded_by" not in report_meta.columns:
            report_meta["uploaded_by"] = uploaded_by or current_user_email()
        report_meta.to_sql("reports", con, if_exists="append", index=False)
    con.commit(); con.close()


def load_history() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    init_db()
    con = sqlite3.connect(DB_PATH)
    actions = pd.read_sql_query("SELECT * FROM actions", con)
    breaches = pd.read_sql_query("SELECT * FROM breaches", con)
    runs = pd.read_sql_query("SELECT * FROM runs ORDER BY processed_at DESC", con)
    con.close()
    return actions, breaches, runs


def delete_run(run_id: str):
    log_audit("delete_run", f"Deleted run_id={run_id}")
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM actions WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM breaches WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM reports WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
    con.commit(); con.close()


def load_reports_history() -> pd.DataFrame:
    init_db()
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM reports ORDER BY processed_at DESC", con)
    finally:
        con.close()
    return df


def read_pdf_text(uploaded_file) -> str:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed. Run: pip install -r requirements.txt")
    data = uploaded_file.read()
    uploaded_file.seek(0)
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = []
        for page in pdf.pages:
            pages.append(page.extract_text(x_tolerance=2, y_tolerance=4) or "")
    return "\n".join(pages)


MONTH_ABBR = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr", "may": "May", "june": "Jun",
    "july": "Jul", "august": "Aug", "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
}

REPORT_TYPE_OPTIONS = [
    "— Select report type —",
    "Service Enforcement",
    "Provider Approval Cancellation",
    "Service Approval Cancellation",
    "Involuntary Suspension",
    "Provider Enforcement",
]

def quarter_label(qnum: int, fy_start_yyyy: int) -> str:
    fy1 = str(fy_start_yyyy)[-2:]
    fy2 = str(fy_start_yyyy + 1)[-2:]
    if qnum == 1:
        return f"Q1 FY{fy1}/{fy2} — Jul–Sep {fy_start_yyyy}"
    if qnum == 2:
        return f"Q2 FY{fy1}/{fy2} — Oct–Dec {fy_start_yyyy}"
    if qnum == 3:
        return f"Q3 FY{fy1}/{fy2} — Jan–Mar {fy_start_yyyy + 1}"
    return f"Q4 FY{fy1}/{fy2} — Apr–Jun {fy_start_yyyy + 1}"

def quarter_options() -> List[str]:
    # Covers historic imports and the next few years. Enforced dropdown means labels stay consistent.
    years = range(2023, 2030)
    return ["— Select quarter —"] + [quarter_label(q, y) for y in years for q in (1, 2, 3, 4)]

def quarter_from_filename_or_text(source: str) -> str:
    # Handles filenames like Q1_Service_Enforcement_Action_Information_2025_2026.pdf
    m = re.search(r"Q([1-4]).*?(20\d{2})[_\-/](20\d{2})", source, re.I)
    if m:
        return quarter_label(int(m.group(1)), int(m.group(2)))
    return ""

def normalise_quarter_label(text: str, fallback: str = "") -> str:
    """Return a strict label like Q2 FY25/26 — Oct–Dec 2025 from NSW PDF header text or filename."""
    source = f"{fallback}\n{text or ''}"

    # 1) Best case: official header contains Qx FYyy/yy and month range.
    q = re.search(r"\bQ([1-4])\s*FY\s*(20)?(\d{2})\s*/\s*(20)?(\d{2})\b", source, re.I)
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+to\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})", source, re.I)
    if q and m:
        qnum = q.group(1)
        fy1 = q.group(3)
        fy2 = q.group(5)
        start = MONTH_ABBR[m.group(1).lower()]
        end = MONTH_ABBR[m.group(2).lower()]
        year = m.group(3)
        return f"Q{qnum} FY{fy1}/{fy2} — {start}–{end} {year}"

    # 2) Filename fallback: Q1_..._2025_2026.pdf → Q1 FY25/26 — Jul–Sep 2025.
    derived = quarter_from_filename_or_text(source)
    if derived:
        return derived

    # 3) Preserve already-standard labels only.
    clean = (fallback or "").strip()
    if re.match(r"^Q[1-4]\s+FY\d{2}/\d{2}\s+—\s+[A-Z][a-z]{2}–[A-Z][a-z]{2}\s+20\d{2}$", clean):
        return clean
    return "UNIDENTIFIED QUARTER — CHECK PDF"


def file_signature(uploaded_file) -> str:
    data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return hashlib.sha256(data).hexdigest()


def report_already_uploaded(quarter: str, report_type: str) -> int:
    con = sqlite3.connect(DB_PATH)
    try:
        count = con.execute("SELECT COUNT(*) FROM actions WHERE quarter=? AND report_type=?", (quarter, report_type)).fetchone()[0]
    finally:
        con.close()
    return int(count or 0)


def detect_report_type(text: str, file_name: str = "") -> str:
    """Classify NSW PDF report type from header/title text."""
    source = f"{file_name}\n{text[:4000]}".lower()
    if "provider approval cancellations" in source or "provider cancellations" in source:
        return "Provider Approval Cancellation"
    if "service approval cancellations" in source or "service cancellations" in source:
        return "Service Approval Cancellation"
    if "involuntary suspensions" in source or "grounds for involuntary suspension" in source:
        return "Involuntary Suspension"
    if "enforceable undertakings" in source or "emergency action notices" in source or "compliance notices" in source or "reason for enforcement action" in source:
        return "Service Enforcement"
    return "UNIDENTIFIED REPORT TYPE"


def delete_report_data(quarter: str, report_type: str):
    """Remove one quarter/report-type safely before replacing it."""
    log_audit("delete_report_data", f"Deleted/replaced {quarter} · {report_type}")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    action_ids = [r[0] for r in cur.execute("SELECT action_id FROM actions WHERE quarter=? AND report_type=?", (quarter, report_type)).fetchall()]
    if action_ids:
        placeholders = ",".join(["?"] * len(action_ids))
        cur.execute(f"DELETE FROM breaches WHERE action_id IN ({placeholders})", action_ids)
    cur.execute("DELETE FROM actions WHERE quarter=? AND report_type=?", (quarter, report_type))
    cur.execute("DELETE FROM reports WHERE quarter=? AND report_type=?", (quarter, report_type))
    con.commit(); con.close()


def build_upload_review(uploaded_files: List, provider_rules) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Read all dropped files, identify quarter/report type, and prepare review table."""
    rows = []
    cache = {}
    seen_in_batch = set()
    for f in uploaded_files or []:
        try:
            txt = read_pdf_text(f)
            cache[f.name] = txt
            quarter = normalise_quarter_label(txt, f.name)
            report_type = detect_report_type(txt, f.name)
            existing = report_already_uploaded(quarter, report_type) if not quarter.startswith("UNIDENTIFIED") and not report_type.startswith("UNIDENTIFIED") else 0
            batch_key = (quarter, report_type)
            duplicate_in_batch = batch_key in seen_in_batch
            seen_in_batch.add(batch_key)
            if quarter.startswith("UNIDENTIFIED"):
                status = "Needs check — quarter not detected"
            elif report_type.startswith("UNIDENTIFIED"):
                status = "Needs check — report type not detected"
            elif duplicate_in_batch:
                status = "Duplicate in this upload batch"
            elif existing:
                status = f"Already uploaded — {existing} existing action rows"
            else:
                status = "Ready"
            rows.append({
                "File": f.name,
                "Detected quarter": quarter if not quarter.startswith("UNIDENTIFIED") else "— Select quarter —",
                "Detected report type": report_type if not report_type.startswith("UNIDENTIFIED") else "— Select report type —",
                "Existing rows": existing,
                "Status": status,
            })
        except Exception as e:
            rows.append({
                "File": getattr(f, "name", "Uploaded file"),
                "Detected quarter": "— Select quarter —",
                "Detected report type": "— Select report type —",
                "Existing rows": 0,
                "Status": f"Could not read PDF — {str(e)[:120]}",
            })
    return pd.DataFrame(rows), cache


def recalc_upload_review(edited_df: pd.DataFrame) -> pd.DataFrame:
    """Recalculate duplicate/existing statuses after an admin edits quarter/report-type dropdowns."""
    if edited_df is None or edited_df.empty:
        return pd.DataFrame()
    df = edited_df.copy()
    statuses = []
    existing_rows = []
    seen = set()
    for _, row in df.iterrows():
        quarter = str(row.get("Detected quarter", ""))
        report_type = str(row.get("Detected report type", ""))
        existing = report_already_uploaded(quarter, report_type) if quarter in quarter_options() and report_type in REPORT_TYPE_OPTIONS else 0
        key = (quarter, report_type)
        duplicate = key in seen
        seen.add(key)
        if quarter == "— Select quarter —" or quarter not in quarter_options():
            status = "Needs check — select quarter"
        elif report_type == "— Select report type —" or report_type not in REPORT_TYPE_OPTIONS:
            status = "Needs check — select report type"
        elif duplicate:
            status = "Duplicate in this upload batch"
        elif existing:
            status = f"Already uploaded — {existing} existing action rows"
        else:
            status = "Ready"
        statuses.append(status)
        existing_rows.append(existing)
    df["Existing rows"] = existing_rows
    df["Status"] = statuses
    return df




def _file_row_key(file_name: str) -> str:
    return hashlib.sha1(str(file_name).encode("utf-8")).hexdigest()[:12]


def render_upload_review_editor(review_df: pd.DataFrame) -> pd.DataFrame:
    """Polished upload review editor with removable file cards and locked dropdowns."""
    if review_df is None or review_df.empty:
        return pd.DataFrame()

    upload_sig = "|".join(review_df["File"].astype(str).tolist())
    if st.session_state.get("upload_review_signature") != upload_sig:
        st.session_state["upload_review_signature"] = upload_sig
        st.session_state["upload_removed_files"] = []
        for f in review_df["File"].astype(str):
            rk = _file_row_key(f)
            st.session_state.pop(f"review_quarter_{rk}", None)
            st.session_state.pop(f"review_type_{rk}", None)

    removed = set(st.session_state.get("upload_removed_files", []))

    for _, row in review_df.iterrows():
        fname = str(row["File"])
        rk = _file_row_key(fname)
        q_key = f"review_quarter_{rk}"
        t_key = f"review_type_{rk}"
        if q_key not in st.session_state:
            q_val = str(row.get("Detected quarter", "— Select quarter —"))
            st.session_state[q_key] = q_val if q_val in quarter_options() else "— Select quarter —"
        if t_key not in st.session_state:
            t_val = str(row.get("Detected report type", "— Select report type —"))
            st.session_state[t_key] = t_val if t_val in REPORT_TYPE_OPTIONS else "— Select report type —"

    rows = []
    for _, row in review_df.iterrows():
        fname = str(row["File"])
        if fname in removed:
            continue
        rk = _file_row_key(fname)
        rows.append({
            "File": fname,
            "Detected quarter": st.session_state.get(f"review_quarter_{rk}", "— Select quarter —"),
            "Detected report type": st.session_state.get(f"review_type_{rk}", "— Select report type —"),
            "Existing rows": int(row.get("Existing rows", 0) or 0),
            "Status": str(row.get("Status", "")),
        })
    active_df = recalc_upload_review(pd.DataFrame(rows)) if rows else pd.DataFrame(columns=["File","Detected quarter","Detected report type","Existing rows","Status"])

    st.markdown("""
    <div class='ya-review-shell'>
      <div class='ya-review-intro'>
        <div>
          <div class='ya-review-eyebrow'>Upload review</div>
          <div class='ya-review-copy'>Confirm the quarter and report type before processing. Remove anything you do not want included.</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    for i, row in active_df.iterrows():
        fname = str(row["File"])
        rk = _file_row_key(fname)
        status = str(row.get("Status", ""))
        existing = int(row.get("Existing rows", 0) or 0)
        status_class = "ready" if status.lower() == "ready" else ("duplicate" if existing else "check")
        file_display = fname if len(fname) <= 78 else fname[:38] + "…" + fname[-32:]

        st.markdown(f"""
        <div class='ya-review-card'>
          <div class='ya-file-block'>
            <div class='ya-file-icon'>PDF</div>
            <div>
              <div class='ya-file-name'>{file_display}</div>
              <div class='ya-file-sub'>Existing rows: <strong>{existing}</strong></div>
            </div>
          </div>
        """, unsafe_allow_html=True)

        c_trash, c_quarter, c_type, c_status = st.columns([0.65, 2.1, 2.1, 2.0], vertical_alignment="center")
        with c_trash:
            if st.button("🗑", key=f"remove_upload_{rk}", help=f"Remove {fname} from this upload"):
                st.session_state.setdefault("upload_removed_files", [])
                if fname not in st.session_state["upload_removed_files"]:
                    st.session_state["upload_removed_files"].append(fname)
                st.rerun()
        with c_quarter:
            st.caption("Quarter")
            current_q = st.session_state.get(f"review_quarter_{rk}", "— Select quarter —")
            q_opts = quarter_options()
            st.selectbox(
                "Quarter",
                q_opts,
                index=q_opts.index(current_q) if current_q in q_opts else 0,
                key=f"review_quarter_{rk}",
                label_visibility="collapsed",
            )
        with c_type:
            st.caption("Report type")
            current_t = st.session_state.get(f"review_type_{rk}", "— Select report type —")
            st.selectbox(
                "Report type",
                REPORT_TYPE_OPTIONS,
                index=REPORT_TYPE_OPTIONS.index(current_t) if current_t in REPORT_TYPE_OPTIONS else 0,
                key=f"review_type_{rk}",
                label_visibility="collapsed",
            )
        with c_status:
            st.caption("Status")
            st.markdown(f"<span class='ya-status-badge {status_class}'>{status}</span>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    if removed:
        st.markdown(f"<div class='ya-removed-note'>{len(removed)} file(s) removed from this upload consideration.</div>", unsafe_allow_html=True)
    return active_df


def render_kpi_notes():
    st.markdown("""
    <div class='ya-note-grid'>
      <div class='ya-note-card'><h4>Actions</h4><p>Counts each published enforcement action row extracted from the uploaded NSW PDFs. This is not the same as breach references; one action can contain multiple Law/Reg items.</p></div>
      <div class='ya-note-card'><h4>Breach references</h4><p>Counts every Law or Regulation reference extracted from the reason field. This is the better measure for issue volume and complexity.</p></div>
      <div class='ya-note-card'><h4>L165/166/167</h4><p>Isolates the serious matters bucket: supervision, inappropriate discipline, and protection from harm/hazards.</p></div>
      <div class='ya-note-card'><h4>YA actions</h4><p>Counts Young Academics enforcement actions in the selected quarter range. This supports direct provider ranking.</p></div>
      <div class='ya-note-card'><h4>YA significant</h4><p>Counts Young Academics breach references that fall into Law 165, 166 or 167. This is the board-level risk indicator.</p></div>
    </div>
    """, unsafe_allow_html=True)


def rules_to_df(rules=DEFAULT_PROVIDER_RULES) -> pd.DataFrame:
    rows = []
    for provider, aliases in rules:
        for alias in aliases:
            rows.append({"provider": provider, "alias_contains": alias})
    return pd.DataFrame(rows)


def df_to_rules(df: pd.DataFrame) -> List[Tuple[str, List[str]]]:
    if df is None or df.empty:
        return DEFAULT_PROVIDER_RULES
    grouped: Dict[str, List[str]] = {}
    for _, r in df.dropna().iterrows():
        provider = str(r.get("provider", "")).strip()
        alias = str(r.get("alias_contains", "")).strip().lower()
        if provider and alias:
            grouped.setdefault(provider, []).append(alias)
    return list(grouped.items()) or DEFAULT_PROVIDER_RULES


def infer_provider(text: str, rules: List[Tuple[str, List[str]]]) -> str:
    t = re.sub(r"\s+", " ", text.lower())
    for provider, aliases in rules:
        for alias in aliases:
            if alias.lower() in t:
                return provider
    first = text.strip().split("\n")[0]
    first = re.sub(r"\b\d{1,4}[A-Za-z]?\b.*", "", first).strip(" -,")
    return first[:60] if first else "Unknown / Needs Mapping"


def detect_action_type(text: str, report_type: str) -> str:
    low = text.lower()
    if "involuntary" in report_type.lower() or "suspended under section 72" in low:
        return "Involuntary suspension"
    if "service approval" in report_type.lower() and "cancel" in low:
        return "Service approval cancellation"
    if "provider approval" in report_type.lower() and "cancel" in low:
        return "Provider approval cancellation"
    if "emergency action" in low or "section 179" in low:
        return "Emergency action notice"
    if "enforceable undertaking" in low or "179a" in low:
        return "Enforceable undertaking"
    if "compliance notice" in low or "section 177" in low:
        return "Compliance notice"
    return report_type


def extract_reason_section(block: str) -> str:
    m = DATE_RE.search(block)
    section = block[m.end():] if m else block
    stop_words = ["Issue of compliance notice", "Issue of emergency action", "Enter into an Enforceable", "Service approval suspended", "Cancellation of"]
    idxs = [section.lower().find(w.lower()) for w in stop_words if section.lower().find(w.lower()) >= 0]
    if idxs:
        section = section[:min(idxs)]
    return section


def extract_breaches(reason: str) -> List[Tuple[str, str, str]]:
    out = []
    for m in LAW_RE.finditer(reason):
        code = m.group(1).upper()
        if code in {"177", "179"}:
            continue
        classification = "Significant matter: Law 165/166/167" if code in SIGNIFICANT_LAWS else "Other Law/Reg breach"
        out.append((f"Law {code}", "Law", classification))
    for m in REG_RE.finditer(reason):
        code = m.group(1).upper()
        out.append((f"Regulation {code}", "Regulation", "Other Law/Reg breach"))
    return out


def split_blocks(text: str) -> List[str]:
    matches = list(ID_RE.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append(text[start:end].strip())
    return blocks


def parse_pdf(uploaded_file, quarter: str, report_type: str, provider_rules, run_id: str = None, pre_read_text: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    text = pre_read_text if pre_read_text is not None else read_pdf_text(uploaded_file)
    blocks = split_blocks(text)
    run_id = run_id or datetime.now().strftime("%Y%m%d%H%M%S")
    processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    action_rows, breach_rows = [], []
    for idx, block in enumerate(blocks, start=1):
        id_match = ID_RE.search(block)
        date_match = DATE_RE.search(block)
        if not id_match:
            continue
        entity_id = id_match.group(1)
        date_issued = date_match.group(1) if date_match else ""
        left = block[id_match.end(): date_match.start() if date_match else min(len(block), 220)].strip()
        provider = infer_provider(left + "\n" + block[:400], provider_rules)
        action_id = f"{run_id}-{report_type[:3]}-{idx:04d}"
        reason = extract_reason_section(block)
        breaches = extract_breaches(reason)
        action_rows.append({
            "run_id": run_id,
            "quarter": quarter,
            "report_type": report_type,
            "action_id": action_id,
            "entity_id": entity_id,
            "provider": provider,
            "service_name": re.sub(r"\s+", " ", left)[:180],
            "date_issued": date_issued,
            "action_type": detect_action_type(block, report_type),
            "raw_text": block[:4000],
            "processed_at": processed_at,
        })
        for code, family, classification in breaches:
            breach_rows.append({
                "run_id": run_id,
                "quarter": quarter,
                "action_id": action_id,
                "provider": provider,
                "breach_code": code,
                "breach_family": family,
                "classification": classification,
                "processed_at": processed_at,
            })
    return pd.DataFrame(action_rows), pd.DataFrame(breach_rows)


def make_provider_summary(actions: pd.DataFrame, breaches: pd.DataFrame, quarters: List[str] = None, top_n: int = None) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame()
    a = actions.copy()
    b = breaches.copy()
    if quarters:
        a = a[a["quarter"].isin(quarters)]
        b = b[b["quarter"].isin(quarters)] if not b.empty else b
    action_counts = a.groupby("provider").size().rename("Enforcement Actions")
    if not b.empty:
        piv = b.pivot_table(index="provider", columns="classification", values="breach_code", aggfunc="count", fill_value=0)
    else:
        piv = pd.DataFrame(index=action_counts.index)
    for col in ["Significant matter: Law 165/166/167", "Other Law/Reg breach"]:
        if col not in piv.columns:
            piv[col] = 0
    out = pd.concat([action_counts, piv], axis=1).fillna(0)
    out = out.rename(columns={"Significant matter: Law 165/166/167": "L165/166/167", "Other Law/Reg breach": "Other"})
    out["Total Breach References"] = out["L165/166/167"] + out["Other"]
    out = out.reset_index().sort_values(["Enforcement Actions", "Total Breach References"], ascending=False)
    out.insert(0, "Rank", range(1, len(out) + 1))
    if top_n:
        ya = out[out["provider"].eq("Young Academics")]
        top = out.head(top_n)
        out = pd.concat([top, ya]).drop_duplicates(subset=["provider"]).sort_values("Rank")
    return out


def make_law_summary(breaches: pd.DataFrame) -> pd.DataFrame:
    if breaches.empty:
        return pd.DataFrame(columns=["breach_code", "Count"])
    return breaches.groupby("breach_code").size().reset_index(name="Count").sort_values("Count", ascending=False)


def quarter_summary(actions: pd.DataFrame, breaches: pd.DataFrame) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame()
    action_q = actions.groupby("quarter").size().rename("Enforcement Actions")
    if breaches.empty:
        out = action_q.reset_index()
        out["L165/166/167"] = 0
        out["Other"] = 0
        out["Total Breach References"] = 0
        return out
    b = breaches.pivot_table(index="quarter", columns="classification", values="breach_code", aggfunc="count", fill_value=0)
    for col in ["Significant matter: Law 165/166/167", "Other Law/Reg breach"]:
        if col not in b.columns:
            b[col] = 0
    out = pd.concat([action_q, b], axis=1).fillna(0).reset_index()
    out = out.rename(columns={"Significant matter: Law 165/166/167": "L165/166/167", "Other Law/Reg breach": "Other"})
    out["Total Breach References"] = out["L165/166/167"] + out["Other"]
    return out


def ya_position_text(summary: pd.DataFrame) -> str:
    if summary.empty or "Young Academics" not in set(summary["provider"]):
        return "Young Academics does not appear in the selected report set."
    row = summary[summary["provider"].eq("Young Academics")].iloc[0]
    return f"YA Rank: {int(row['Rank'])}/{len(summary)} • Actions: {int(row['Enforcement Actions'])} • L165/166/167: {int(row['L165/166/167'])} • Other: {int(row['Other'])}"


def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#357b84", "font_color": "#FFFFFF", "border": 1})
        ya_fmt = workbook.add_format({"bold": True, "bg_color": "#FFF200", "font_color": "#000000"})
        for name, df in sheets.items():
            safe = name[:31].replace("/", "-")
            df.to_excel(writer, sheet_name=safe, index=False)
            ws = writer.sheets[safe]
            for i, col in enumerate(df.columns):
                width = min(max(len(str(col)) + 4, 13), 48)
                ws.set_column(i, i, width)
                ws.write(0, i, col, header_fmt)
            if "provider" in df.columns:
                provider_col = list(df.columns).index("provider")
                for r, val in enumerate(df["provider"], start=1):
                    if val == "Young Academics":
                        ws.set_row(r, None, ya_fmt)
    return output.getvalue()


def render_header():
    st.markdown(f"""
    <div class='ya-shell'>
      <div class='ya-header'>
        <div class='ya-brand'>
          <img class='ya-logo' src='{LOGO_URL}' />
          <div class='ya-title'>
            <h1>{APP_TITLE}</h1>
            <p>Register of Published Enforcement Actions Benchmarking</p>
            <p><strong>Developed by James Maclean-Horton</strong></p>
          </div>
        </div>
        <div class='ya-version'>{APP_VERSION}</div>
      </div>
      <div class='ya-note'>Internal reporting tool for quarterly NSW enforcement action PDFs, provider benchmarking, Law 165/166/167 split, cancellations, suspensions, and rolling history.</div>
      <div class='ya-disclaimer'>This system and its outputs are the property of Young Academics Early Learning Centre. Any unauthorised access, use, copying, distribution, or disclosure is strictly prohibited.</div>
    </div>
    """, unsafe_allow_html=True)



def add_percent(df: pd.DataFrame, count_col: str = "Count") -> pd.DataFrame:
    if df is None or df.empty or count_col not in df.columns:
        return df if df is not None else pd.DataFrame()
    out = df.copy()
    total = float(out[count_col].sum() or 0)
    out["%"] = (out[count_col] / total * 100).round(1) if total else 0.0
    return out


def make_action_category_summary(actions: pd.DataFrame, quarter: str = None) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame(columns=["Category", "Count", "%"])
    df = actions.copy()
    if quarter:
        df = df[df["quarter"].eq(quarter)]
    if df.empty:
        return pd.DataFrame(columns=["Category", "Count", "%"])
    out = df.groupby("action_type").size().reset_index(name="Count").rename(columns={"action_type":"Category"}).sort_values("Count", ascending=False)
    return add_percent(out)


def make_breach_category_summary(breaches: pd.DataFrame, quarter: str = None) -> pd.DataFrame:
    if breaches.empty:
        return pd.DataFrame(columns=["Category", "Count", "%"])
    df = breaches.copy()
    if quarter:
        df = df[df["quarter"].eq(quarter)]
    if df.empty:
        return pd.DataFrame(columns=["Category", "Count", "%"])
    out = df.groupby("classification").size().reset_index(name="Count").rename(columns={"classification":"Category"}).sort_values("Count", ascending=False)
    return add_percent(out)


def make_provider_action_category_summary(actions: pd.DataFrame, quarter: str = None) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame(columns=["provider", "Category", "Count", "% of Category", "% of Provider Actions"])
    df = actions.copy()
    if quarter:
        df = df[df["quarter"].eq(quarter)]
    if df.empty:
        return pd.DataFrame(columns=["provider", "Category", "Count", "% of Category", "% of Provider Actions"])
    out = df.groupby(["provider", "action_type"]).size().reset_index(name="Count").rename(columns={"action_type":"Category"})
    cat_total = out.groupby("Category")["Count"].transform("sum")
    prov_total = out.groupby("provider")["Count"].transform("sum")
    out["% of Category"] = (out["Count"] / cat_total * 100).round(1)
    out["% of Provider Actions"] = (out["Count"] / prov_total * 100).round(1)
    return out.sort_values(["Category", "Count"], ascending=[True, False])


def make_provider_breach_category_summary(breaches: pd.DataFrame, quarter: str = None) -> pd.DataFrame:
    if breaches.empty:
        return pd.DataFrame(columns=["provider", "Category", "Count", "% of Category", "% of Provider Breaches"])
    df = breaches.copy()
    if quarter:
        df = df[df["quarter"].eq(quarter)]
    if df.empty:
        return pd.DataFrame(columns=["provider", "Category", "Count", "% of Category", "% of Provider Breaches"])
    out = df.groupby(["provider", "classification"]).size().reset_index(name="Count").rename(columns={"classification":"Category"})
    cat_total = out.groupby("Category")["Count"].transform("sum")
    prov_total = out.groupby("provider")["Count"].transform("sum")
    out["% of Category"] = (out["Count"] / cat_total * 100).round(1)
    out["% of Provider Breaches"] = (out["Count"] / prov_total * 100).round(1)
    return out.sort_values(["Category", "Count"], ascending=[True, False])


def make_provider_qoq_summary(actions: pd.DataFrame, breaches: pd.DataFrame) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame()
    rows = []
    for (quarter, provider), a in actions.groupby(["quarter", "provider"]):
        b = breaches[(breaches["quarter"].eq(quarter)) & (breaches["provider"].eq(provider))] if not breaches.empty else pd.DataFrame()
        sig = int((b["classification"].eq("Significant matter: Law 165/166/167")).sum()) if not b.empty else 0
        rows.append({
            "quarter": quarter,
            "provider": provider,
            "Enforcement Actions": len(a),
            "Breach References": len(b),
            "L165/166/167": sig,
            "Other": max(len(b) - sig, 0),
        })
    out = pd.DataFrame(rows).sort_values(["provider", "quarter"])
    out["QoQ Action Change"] = out.groupby("provider")["Enforcement Actions"].diff().fillna(0).astype(int)
    out["QoQ Breach Change"] = out.groupby("provider")["Breach References"].diff().fillna(0).astype(int)
    return out


def make_type_qoq_summary(actions: pd.DataFrame, breaches: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    action_qoq = pd.DataFrame()
    breach_qoq = pd.DataFrame()
    if not actions.empty:
        action_qoq = actions.groupby(["quarter", "provider", "action_type"]).size().reset_index(name="Count")
        action_qoq = action_qoq.sort_values(["provider", "action_type", "quarter"])
        action_qoq["QoQ Change"] = action_qoq.groupby(["provider", "action_type"])["Count"].diff().fillna(0).astype(int)
    if not breaches.empty:
        breach_qoq = breaches.groupby(["quarter", "provider", "classification"]).size().reset_index(name="Count")
        breach_qoq = breach_qoq.rename(columns={"classification":"Category"}).sort_values(["provider", "Category", "quarter"])
        breach_qoq["QoQ Change"] = breach_qoq.groupby(["provider", "Category"])["Count"].diff().fillna(0).astype(int)
    return action_qoq, breach_qoq


def render_pie(df: pd.DataFrame, title: str, key: str = None):
    if df.empty or df["Count"].sum() == 0:
        st.info(f"No data available for {title.lower()}.")
        return
    plot_df = add_percent(df)
    fig = px.pie(
        plot_df,
        names="Category",
        values="Count",
        hole=0.62,
        color_discrete_sequence=["#8edfe4", "#08245c", "#fff200", "#f59f9c", "#54b9a8", "#d6f3f5", "#4b9ca4"],
        custom_data=["%"] if "%" in plot_df.columns else None,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
        marker=dict(line=dict(color="rgba(255,255,255,.72)", width=2)),
    )
    fig.update_layout(
        height=355,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#ffffff", family="Inter, Arial"),
        legend=dict(orientation="v", yanchor="middle", y=.5, xanchor="left", x=.98, font=dict(color="#ffffff", size=12), title=dict(text="Category", font=dict(color="#d8f4f6"))),
        showlegend=True,
    )
    st.markdown(f"<div class='ya-dashboard-card'><h3>{title}</h3><div class='ya-chart-caption'>Includes count and percentage share for the selected quarter.</div>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, key=key)
    st.markdown("</div>", unsafe_allow_html=True)


def provider_detail_view(provider: str, actions: pd.DataFrame, breaches: pd.DataFrame, selected_quarters: List[str]):
    st.button("← Back to dashboard", on_click=lambda: st.session_state.pop("provider_detail", None))
    a = actions[actions["provider"].eq(provider)].copy()
    b = breaches[breaches["provider"].eq(provider)].copy() if not breaches.empty else breaches
    if selected_quarters:
        a = a[a["quarter"].isin(selected_quarters)]
        b = b[b["quarter"].isin(selected_quarters)] if not b.empty else b

    st.markdown(f"""
    <div class='ya-provider-title'>
      <h1>{provider}</h1>
      <p>Provider summary across selected quarters: <strong>{', '.join(selected_quarters) if selected_quarters else 'All history'}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Actions", f"{len(a):,}")
    c2.metric("Breach references", f"{len(b):,}")
    sig = int((b["classification"] == "Significant matter: Law 165/166/167").sum()) if not b.empty else 0
    c3.metric("L165/166/167", f"{sig:,}")
    c4.metric("Other", f"{(len(b)-sig):,}")

    st.markdown("<div class='ya-white-panel'><h3>Executive summary</h3>", unsafe_allow_html=True)
    if a.empty:
        st.markdown("<p>No enforcement actions found for this provider in the selected period.</p></div>", unsafe_allow_html=True)
        return
    top_action = a["action_type"].mode().iloc[0] if not a["action_type"].dropna().empty else "Not available"
    top_breach = b["breach_code"].mode().iloc[0] if not b.empty and not b["breach_code"].dropna().empty else "No breach references extracted"
    q_count = a["quarter"].nunique()
    st.markdown(f"""
    <p><strong>{provider}</strong> appears in <strong>{len(a):,}</strong> enforcement action row(s) across <strong>{q_count}</strong> selected quarter(s).</p>
    <p>The most common action category is <strong>{top_action}</strong>. The most common extracted Law/Reg reference is <strong>{top_breach}</strong>.</p>
    <p>Serious matter references under Law 165/166/167 total <strong>{sig:,}</strong>, with all other extracted Law/Reg references totalling <strong>{(len(b)-sig):,}</strong>.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Provider dashboard")
    p1, p2 = st.columns(2)
    with p1:
        render_pie(make_action_category_summary(a), "Actions by category", key=f"provider_actions_pie_{provider}")
    with p2:
        render_pie(make_breach_category_summary(b), "Breach references by category", key=f"provider_breaches_pie_{provider}")

    st.markdown("### Quarter trend")
    pq = quarter_summary(a, b)
    st.dataframe(pq, use_container_width=True, hide_index=True, key=f"provider_qtrend_{provider}")
    if not pq.empty:
        st.line_chart(pq.set_index("quarter")[["Enforcement Actions", "L165/166/167", "Other"]])

    st.markdown("### Action category breakdown")
    st.dataframe(make_action_category_summary(a), use_container_width=True, hide_index=True, key=f"provider_action_cat_{provider}")

    st.markdown("### Law/Reg references")
    st.dataframe(make_law_summary(b), use_container_width=True, hide_index=True, key=f"provider_law_summary_{provider}")

    st.markdown("### Service/action level detail")
    display_cols = ["quarter", "report_type", "entity_id", "service_name", "date_issued", "action_type"]
    st.dataframe(a[display_cols], use_container_width=True, hide_index=True, key=f"provider_detail_rows_{provider}")

    with st.expander("Show raw extracted text excerpts", expanded=False):
        for _, row in a.head(30).iterrows():
            st.markdown(f"**{row.get('date_issued','')} — {row.get('service_name','')} — {row.get('action_type','')}**")
            st.code(str(row.get("raw_text", ""))[:2500])


def main():
    require_login()
    render_header()
    logout_button()

    hist_actions, hist_breaches, runs = load_history()

    st.markdown("<div class='ya-section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='ya-panel-title'>Upload & Controls</div>", unsafe_allow_html=True)

    if is_admin():
        st.success("Admin access: upload, replace/delete, and user management enabled.")
    else:
        st.info("Read-only access: you can view dashboards and export reports. Uploads/deletions are admin-only.")

    if is_admin():
        with st.expander("Provider mapping controls", expanded=False):
            st.caption("Provider mapping groups service names into provider/brand groups. Keep this collapsed unless you need to update or download the mapping file.")
            uploaded_map = st.file_uploader("Upload provider_mapping.csv", type=["csv"], key="map")
            map_df = pd.read_csv(uploaded_map) if uploaded_map else rules_to_df()
            edited_map = st.data_editor(map_df, num_rows="dynamic", use_container_width=True, height=280)
            st.download_button("Download provider mapping CSV", edited_map.to_csv(index=False), "provider_mapping.csv", "text/csv")
    else:
        edited_map = rules_to_df()

    provider_rules = df_to_rules(edited_map)

    if is_admin():
        st.markdown("""
        <div class='ya-note' style='margin-top:8px;'>
          Drop any NSW quarterly enforcement PDFs here. You can upload one quarter, a partial quarter, or a full year at once. The app will detect the quarter and report type from each PDF header before saving.
        </div>
        """, unsafe_allow_html=True)

        bulk_files = st.file_uploader(
            "Drop all NSW enforcement PDFs here",
            type=["pdf"],
            accept_multiple_files=True,
            key="bulk_pdf_upload",
            help="Accepts Service Enforcement, Provider Cancellations, Service Cancellations, and Involuntary Suspensions PDFs. Missing reports are allowed.",
        )
    else:
        bulk_files = []

    review_df = pd.DataFrame()
    file_text_cache = {}
    if bulk_files:
        with st.spinner("Reading PDF headers and checking saved history…"):
            review_df, file_text_cache = build_upload_review(bulk_files, provider_rules)
        st.markdown("### Upload review")
        st.caption("Admin step: fix any unidentified quarter/report type before saving. Use the trash icon to remove a file from this upload. Quarter and report type are dropdowns so the naming convention stays locked.")
        active_review_df = render_upload_review_editor(review_df)
        review_df = active_review_df.copy()

        ready_count = int((active_review_df["Status"] == "Ready").sum()) if not active_review_df.empty else 0
        existing_count = int(active_review_df["Status"].astype(str).str.startswith("Already uploaded").sum()) if not active_review_df.empty else 0
        blocked_count = len(active_review_df) - ready_count - existing_count
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Ready to save", ready_count)
        rc2.metric("Already uploaded", existing_count)
        rc3.metric("Needs check", blocked_count)

        process_mode = st.radio(
            "How should duplicates be handled?",
            ["Process new files only", "Replace existing quarter/report type", "Stop if anything already exists"],
            horizontal=True,
            key="bulk_duplicate_mode",
        )
    else:
        process_mode = "Process new files only"

    action_col, history_col = st.columns([1, 1])
    with action_col:
        process_clicked = st.button("Process uploaded PDFs", key="process_bulk_pdfs", disabled=not is_admin())
    with history_col:
        with st.expander("History manager", expanded=False):
            reports_history = load_reports_history()
            st.caption(f"Saved runs: {len(runs)}")
            if not reports_history.empty:
                st.markdown("**Saved reports by quarter/type**")
                st.dataframe(reports_history[["quarter", "report_type", "file_name", "actions_count", "breaches_count", "processed_at"]], use_container_width=True, hide_index=True, key="saved_reports_history_table")
            if is_admin() and not runs.empty:
                run_labels = [f"{r['quarter']} — {r['processed_at']} — {r['actions_count']} actions" for _, r in runs.iterrows()]
                selected_delete = st.selectbox("Delete a saved run", [""] + run_labels, key="delete_saved_run_select")
                if selected_delete:
                    idx = run_labels.index(selected_delete)
                    run_id_to_delete = runs.iloc[idx]["run_id"]
                    confirm_delete = st.text_input("Type DELETE to confirm", key="confirm_run_delete")
                    if st.button("Delete selected run", key="delete_selected_run_btn", disabled=(confirm_delete != "DELETE")):
                        delete_run(run_id_to_delete)
                        st.success("Deleted. Refreshing…")
                        st.rerun()
            elif not is_admin():
                st.caption("Delete controls are admin-only.")
            else:
                st.caption("No saved runs yet.")

    if process_clicked:
        if not is_admin():
            st.error("Uploads are admin-only.")
        elif not bulk_files:
            st.error("Upload at least one PDF before processing.")
        else:
            if review_df.empty:
                review_df, file_text_cache = build_upload_review(bulk_files, provider_rules)
            if not review_df.empty:
                active_review_df = review_df.copy()
            else:
                active_review_df = render_upload_review_editor(review_df)
            review_df = recalc_upload_review(active_review_df)

            bad = review_df[review_df["Status"].astype(str).str.startswith("Needs check") | review_df["Status"].astype(str).eq("Duplicate in this upload batch")]
            if not bad.empty:
                st.error("Some uploaded files could not be safely identified or are duplicated in this batch. Remove/fix those files first.")
                st.dataframe(bad, use_container_width=True, hide_index=True, key="bulk_bad_files_table")
            elif process_mode == "Stop if anything already exists" and (review_df["Existing rows"] > 0).any():
                st.error("At least one quarter/report type already exists. Choose 'Process new files only' or 'Replace existing quarter/report type'.")
            else:
                run_id = datetime.now().strftime("%Y%m%d%H%M%S")
                all_actions, all_breaches, report_meta = [], [], []
                processed_files = 0
                skipped_files = []
                with st.spinner("Processing bulk upload: extracting rows, classifying breaches, grouping quarters, and saving history…"):
                    files_to_process = {str(x) for x in review_df["File"].tolist()}
                    for f in bulk_files:
                        if f.name not in files_to_process:
                            skipped_files.append(f"{f.name} — removed from upload review")
                            continue
                        row = review_df[review_df["File"].eq(f.name)].iloc[0]
                        quarter = str(row["Detected quarter"])
                        rtype = str(row["Detected report type"])
                        existing = int(row["Existing rows"] or 0)
                        if existing and process_mode == "Process new files only":
                            skipped_files.append(f"{f.name} — already uploaded")
                            continue
                        if existing and process_mode == "Replace existing quarter/report type":
                            delete_report_data(quarter, rtype)

                        txt = file_text_cache.get(f.name) or read_pdf_text(f)
                        a, b = parse_pdf(f, quarter, rtype, provider_rules, run_id=run_id, pre_read_text=txt)
                        if a.empty:
                            skipped_files.append(f"{f.name} — no action rows extracted")
                            continue
                        all_actions.append(a)
                        all_breaches.append(b)
                        report_meta.append({
                            "run_id": run_id,
                            "quarter": quarter,
                            "report_type": rtype,
                            "file_name": f.name,
                            "file_signature": file_signature(f),
                            "actions_count": len(a),
                            "breaches_count": len(b),
                            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        })
                        processed_files += 1

                actions = pd.concat(all_actions, ignore_index=True) if all_actions else pd.DataFrame()
                breaches = pd.concat(all_breaches, ignore_index=True) if all_breaches else pd.DataFrame()
                meta_df = pd.DataFrame(report_meta)
                if actions.empty:
                    st.warning("No new rows were saved. " + (" Skipped: " + "; ".join(skipped_files[:8]) if skipped_files else ""))
                else:
                    save_to_db(actions, breaches, meta_df)
                    st.session_state["latest_actions"] = actions
                    st.session_state["latest_breaches"] = breaches
                    quarters_saved = ", ".join(sorted(actions["quarter"].unique().tolist()))
                    st.success(f"Processed {processed_files} file(s), saved {len(actions)} actions and {len(breaches)} breach references across: {quarters_saved}.")
                    if skipped_files:
                        st.info("Skipped: " + "; ".join(skipped_files[:10]))
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    hist_actions, hist_breaches, runs = load_history()
    if hist_actions.empty:
        st.info("Upload PDFs and click Process to start building historical tracking.")
        return

    quarters_all = list(dict.fromkeys(hist_actions.sort_values("processed_at", ascending=False)["quarter"].astype(str).tolist()))

    st.markdown("### Quarter controls")
    qc1, qc2 = st.columns([1, 2])
    with qc1:
        current_quarter = st.selectbox(
            "Current quarter dashboard",
            quarters_all,
            index=0,
            help="Use this to search/view the dashboard one quarter at a time.",
            key="current_quarter_select",
        )
    with qc2:
        selected_quarters = st.multiselect(
            "Rolling / comparison quarters",
            quarters_all,
            default=quarters_all[:4],
            help="Default shows the most recent four processed quarters for rolling history.",
            key="rolling_quarter_multiselect",
        )

    show_actions = hist_actions[hist_actions["quarter"].isin(selected_quarters)] if selected_quarters else hist_actions
    show_breaches = hist_breaches[hist_breaches["quarter"].isin(selected_quarters)] if selected_quarters and not hist_breaches.empty else hist_breaches

    if st.session_state.get("provider_detail"):
        provider_detail_view(st.session_state["provider_detail"], hist_actions, hist_breaches, selected_quarters)
        return

    current_actions = hist_actions[hist_actions["quarter"].eq(current_quarter)]
    current_breaches = hist_breaches[hist_breaches["quarter"].eq(current_quarter)] if not hist_breaches.empty else hist_breaches

    current_summary = make_provider_summary(current_actions, current_breaches)
    rolling_summary = make_provider_summary(show_actions, show_breaches)
    law_summary = make_law_summary(show_breaches)
    q_summary = quarter_summary(show_actions, show_breaches)
    action_type_summary = show_actions.groupby(["quarter", "action_type"]).size().reset_index(name="Count").sort_values(["quarter", "Count"], ascending=[True, False])
    current_action_category = make_action_category_summary(current_actions)
    current_breach_category = make_breach_category_summary(current_breaches)

    st.markdown("## Executive position")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Actions", f"{len(show_actions):,}")
    k2.metric("Breach references", f"{len(show_breaches):,}")
    sig_count = int((show_breaches["classification"] == "Significant matter: Law 165/166/167").sum()) if not show_breaches.empty else 0
    k3.metric("L165/166/167", f"{sig_count:,}")
    ya_actions = int((show_actions["provider"] == "Young Academics").sum())
    k4.metric("YA actions", f"{ya_actions:,}")
    ya_sig = int(((show_breaches["provider"] == "Young Academics") & (show_breaches["classification"] == "Significant matter: Law 165/166/167")).sum()) if not show_breaches.empty else 0
    k5.metric("YA significant", f"{ya_sig:,}")

    with st.expander("What do these executive position numbers mean?", expanded=False):
        render_kpi_notes()

    st.markdown(f"<div class='ya-warning'><strong>{ya_position_text(rolling_summary)}</strong></div>", unsafe_allow_html=True)

    provider_action_category_current = make_provider_action_category_summary(current_actions)
    provider_breach_category_current = make_provider_breach_category_summary(current_breaches)
    provider_qoq = make_provider_qoq_summary(show_actions, show_breaches)
    action_type_qoq, breach_type_qoq = make_type_qoq_summary(show_actions, show_breaches)

    tab_names = ["Dashboard", "Current quarter", "Rolling 4-quarter view", "Provider summary", "Quarter-on-quarter", "Law/Reg breakdown", "Raw extracted rows", "Export"]
    if is_admin():
        tab_names.append("Admin users")
    tabs = st.tabs(tab_names)
    with tabs[0]:
        st.caption(f"Current selected quarter: {current_quarter}")
        d1, d2 = st.columns(2)
        with d1:
            render_pie(current_action_category, "Current quarter actions by category", key=f"pie_actions_{current_quarter}")
        with d2:
            render_pie(current_breach_category, "Current quarter breach references by category", key=f"pie_breaches_{current_quarter}")

        st.markdown("### Current quarter category tables")
        st.caption("These tables include counts and percentage share for the selected quarter and are included in the Excel export.")
        cta, ctb = st.columns(2)
        with cta:
            st.dataframe(current_action_category, use_container_width=True, hide_index=True, key="current_action_category_table")
        with ctb:
            st.dataframe(current_breach_category, use_container_width=True, hide_index=True, key="current_breach_category_table")

        st.markdown("### Competitor breakdown by category")
        st.caption("Use this to see which providers are driving each action category and serious/other breach category.")
        comp1, comp2 = st.columns(2)
        with comp1:
            st.markdown("#### Actions by provider/category")
            st.dataframe(provider_action_category_current, use_container_width=True, hide_index=True, key="provider_action_category_current")
        with comp2:
            st.markdown("#### Breaches by provider/category")
            st.dataframe(provider_breach_category_current, use_container_width=True, hide_index=True, key="provider_breach_category_current")

    with tabs[1]:
        st.caption(f"Current selected quarter: {current_quarter}")
        st.caption("Click one provider row to open a detailed provider summary with a back button.")
        try:
            event = st.dataframe(current_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="current_summary_selectable")
            rows = event.selection.rows if hasattr(event, "selection") else []
            if rows:
                provider = str(current_summary.iloc[rows[0]]["provider"])
                st.session_state["provider_detail"] = provider
                st.rerun()
        except TypeError:
            st.dataframe(current_summary, use_container_width=True, hide_index=True, key="current_summary_fallback")
            provider = st.selectbox("Open provider summary", [""] + current_summary["provider"].astype(str).tolist(), key="current_provider_open_select")
            if provider and st.button("Open selected provider", key="current_provider_open_btn"):
                st.session_state["provider_detail"] = provider
                st.rerun()

    with tabs[2]:
        st.caption("Selected quarters combined. This is the rolling view for board reporting. Click one provider row to open a detailed provider summary.")
        try:
            event = st.dataframe(rolling_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="rolling_summary_selectable")
            rows = event.selection.rows if hasattr(event, "selection") else []
            if rows:
                provider = str(rolling_summary.iloc[rows[0]]["provider"])
                st.session_state["provider_detail"] = provider
                st.rerun()
        except TypeError:
            st.dataframe(rolling_summary, use_container_width=True, hide_index=True, key="rolling_summary_fallback")
        st.markdown("### Action type summary")
        st.dataframe(action_type_summary, use_container_width=True, hide_index=True, key="rolling_action_type_summary")

    with tabs[3]:
        provider_list = rolling_summary["provider"].astype(str).tolist() if not rolling_summary.empty else []
        selected_provider = st.selectbox("Choose provider", [""] + provider_list, key="provider_summary_select")
        if selected_provider:
            if st.button("Open provider summary", key="open_provider_summary_button"):
                st.session_state["provider_detail"] = selected_provider
                st.rerun()
            pa = show_actions[show_actions["provider"].eq(selected_provider)]
            pb = show_breaches[show_breaches["provider"].eq(selected_provider)] if not show_breaches.empty else show_breaches
            st.markdown("### Quick provider snapshot")
            snapshot = make_provider_summary(pa, pb)
            st.dataframe(snapshot, use_container_width=True, hide_index=True, key="provider_snapshot_table")
            sc1, sc2 = st.columns(2)
            with sc1:
                render_pie(make_action_category_summary(pa), "Actions by category", key=f"provider_tab_actions_{selected_provider}")
            with sc2:
                render_pie(make_breach_category_summary(pb), "Breach references by category", key=f"provider_tab_breaches_{selected_provider}")

    with tabs[4]:
        st.caption("Quarter-on-quarter stats by competitor and issue/action type.")
        st.markdown("### Provider quarter-on-quarter movement")
        st.dataframe(provider_qoq, use_container_width=True, hide_index=True, key="provider_qoq_table")
        st.markdown("### Action type quarter-on-quarter by provider")
        st.dataframe(action_type_qoq, use_container_width=True, hide_index=True, key="action_type_qoq_table")
        st.markdown("### Breach category quarter-on-quarter by provider")
        st.dataframe(breach_type_qoq, use_container_width=True, hide_index=True, key="breach_type_qoq_table")
        st.markdown("### Overall quarter trend")
        st.dataframe(q_summary, use_container_width=True, hide_index=True, key="quarter_summary_table")
        if not q_summary.empty:
            chart_df = q_summary.set_index("quarter")[["Enforcement Actions", "L165/166/167", "Other"]]
            st.line_chart(chart_df)

    with tabs[5]:
        st.dataframe(law_summary, use_container_width=True, hide_index=True, key="law_summary_table")
        if not show_breaches.empty:
            st.markdown("### Serious matters only: Law 165/166/167")
            sig_only = show_breaches[show_breaches["classification"].eq("Significant matter: Law 165/166/167")]
            st.dataframe(make_law_summary(sig_only), use_container_width=True, hide_index=True, key="serious_law_summary_table")

    with tabs[6]:
        st.markdown("### Extracted enforcement actions")
        st.dataframe(show_actions.drop(columns=["raw_text"], errors="ignore"), use_container_width=True, hide_index=True, key="raw_actions_table")
        st.markdown("### Extracted breach references")
        st.dataframe(show_breaches, use_container_width=True, hide_index=True, key="raw_breaches_table")

    with tabs[7]:
        sheets = {
            "Current Provider Ranking": current_summary,
            "Rolling Provider Ranking": rolling_summary,
            "Current Action Categories": current_action_category,
            "Current Breach Categories": current_breach_category,
            "Provider Action Categories": provider_action_category_current,
            "Provider Breach Categories": provider_breach_category_current,
            "Provider QoQ": provider_qoq,
            "Action Type QoQ": action_type_qoq,
            "Breach Category QoQ": breach_type_qoq,
            "Quarter Trend": q_summary,
            "Law Reg Breakdown": law_summary,
            "Action Type Summary": action_type_summary,
            "Extracted Actions": show_actions.drop(columns=["raw_text"], errors="ignore"),
            "Extracted Breaches": show_breaches,
            "Runs History": runs,
            "Uploaded Reports": load_reports_history(),
        }
        xlsx = to_excel_bytes(sheets)
        st.download_button("Download Excel report", xlsx, "YA_Compliance_Benchmark_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_report")
        st.download_button("Download full history database", open(DB_PATH, "rb").read(), "compliance_history.sqlite3", "application/octet-stream", key="download_history_db")

    if is_admin():
        with tabs[8]:
            render_admin_user_manager_panel()

    st.caption("Internal use only. Review provider mapping before board or Commission reporting, as NSW PDFs often list service names rather than provider groups.")


if __name__ == "__main__":
    main()
