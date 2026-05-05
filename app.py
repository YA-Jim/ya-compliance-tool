import streamlit as st

# ---- PASSWORD PROTECTION ----
def check_password():
    def password_entered():
        if st.session_state["password"] == "YA2026!":
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        st.error("Incorrect password")
        return False
    else:
        return True

if not check_password():
    st.stop()


import base64
import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pdfplumber
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

APP_VERSION = "v2.1 — Auth Build"
YA_LOGO_URL = "https://www.youngacademics.com.au/application/themes/youngacademics/assets/images/logo.svg"
ADMIN_EMAILS = {"james.mh@youngacademics.com.au", "eric@youngacademics.com.au"}
ALLOWED_DOMAIN = "@youngacademics.com.au"

QUARTERS = [
    "Q1 FY24/25 — Jul–Sep 2024", "Q2 FY24/25 — Oct–Dec 2024", "Q3 FY24/25 — Jan–Mar 2025", "Q4 FY24/25 — Apr–Jun 2025",
    "Q1 FY25/26 — Jul–Sep 2025", "Q2 FY25/26 — Oct–Dec 2025", "Q3 FY25/26 — Jan–Mar 2026", "Q4 FY25/26 — Apr–Jun 2026",
    "Q1 FY26/27 — Jul–Sep 2026", "Q2 FY26/27 — Oct–Dec 2026", "Q3 FY26/27 — Jan–Mar 2027", "Q4 FY26/27 — Apr–Jun 2027",
]
REPORT_TYPES = ["Service Enforcement", "Provider Approval Cancellation", "Service Approval Cancellation", "Involuntary Suspension"]
SIGNIFICANT = {"165", "166", "167"}

st.set_page_config(page_title="YA Compliance Benchmarking", page_icon="📊", layout="wide")

CSS = """
<style>
:root{--ya:#357b84;--ya-dark:#0b4f59;--ya-light:#71d5cc;--navy:#092a5e;--glass:rgba(255,255,255,.17);--glass2:rgba(255,255,255,.88);--ink:#0b2530;}
html,body,[data-testid="stAppViewContainer"]{background:linear-gradient(135deg,#357b84 0%,#2d747d 45%,#225e68 100%) !important;color:white;}
[data-testid="stHeader"]{background:transparent!important;}
[data-testid="stSidebar"]{background:#286b74!important;color:white!important;}
h1,h2,h3,h4,label,p,span,div{font-family:Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}
h1{color:white!important;font-weight:900!important;letter-spacing:-.04em!important;}
h2,h3{color:white!important;font-weight:850!important;}
label, .stMarkdown p{color:white!important;}
.hero{background:rgba(255,255,255,.94);border-radius:26px;padding:32px 34px;margin:28px 0 26px 0;box-shadow:0 22px 55px rgba(0,0,0,.18);border:1px solid rgba(255,255,255,.45);}
.hero-grid{display:grid;grid-template-columns:210px 1fr auto;gap:22px;align-items:center;}
.logo-box{background:white;border-radius:18px;padding:14px;box-shadow:0 10px 25px rgba(0,0,0,.08);}
.hero h1{color:#0b4f59!important;margin:0;font-size:32px!important;}
.hero p{color:#0b4f59!important;margin:6px 0;font-weight:650;}
.badge{background:#092a5e;color:white;border-radius:999px;padding:10px 18px;font-weight:800;box-shadow:0 8px 20px rgba(0,0,0,.2);white-space:nowrap;}
.notice{margin-top:18px;background:#eaf6f8;border-left:6px solid #357b84;border-radius:16px;padding:16px 18px;color:#07444c;font-weight:750;}
.disclaimer{color:#193f48!important;font-size:12px!important;margin-top:12px!important;}
.glass-card{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);box-shadow:0 18px 45px rgba(0,0,0,.16);backdrop-filter:blur(18px);border-radius:24px;padding:24px;margin:16px 0;}
.metric-card{background:linear-gradient(180deg,rgba(255,255,255,.94),rgba(255,255,255,.83));color:#0b4f59;border-radius:22px;padding:22px;box-shadow:0 18px 35px rgba(0,0,0,.15);border:1px solid rgba(255,255,255,.5);min-height:130px;}
.metric-card .label{color:#26636c;font-size:13px;font-weight:850;text-transform:uppercase;letter-spacing:.04em;}
.metric-card .value{font-size:36px;line-height:1;font-weight:950;margin-top:14px;color:#092a5e;}
.metric-card .note{font-size:12px;margin-top:10px;color:#4d6c72;}
.stButton>button, div[data-testid="stDownloadButton"] button{background:#71d5cc!important;color:#063d43!important;border:0!important;border-radius:999px!important;font-weight:900!important;box-shadow:0 8px 18px rgba(0,0,0,.22)!important;transition:all .12s ease!important;padding:.65rem 1.05rem!important;}
.stButton>button:hover, div[data-testid="stDownloadButton"] button:hover{transform:translateY(-1px);background:#92eee7!important;box-shadow:0 12px 22px rgba(0,0,0,.25)!important;}
.stButton>button:active{transform:translateY(1px);box-shadow:none!important;}
[data-testid="stFileUploader"] section{border:1.5px dashed rgba(255,255,255,.55)!important;background:rgba(255,255,255,.14)!important;border-radius:18px!important;}
[data-testid="stFileUploader"] button{background:#71d5cc!important;color:#063d43!important;border-radius:999px!important;font-weight:900!important;}
[data-testid="stDataFrame"], .stDataFrame{border-radius:18px!important;overflow:hidden!important;box-shadow:0 15px 32px rgba(0,0,0,.14)!important;}
input, textarea, select{border-radius:14px!important;}
[data-baseweb="input"], [data-baseweb="select"], [data-baseweb="textarea"]{border-radius:14px!important;background:white!important;}
.small-muted{color:rgba(255,255,255,.78);font-size:13px;}
.auth-card{max-width:520px;margin:58px auto;background:rgba(255,255,255,.94);border-radius:28px;padding:34px;box-shadow:0 24px 70px rgba(0,0,0,.25);}
.auth-card h1,.auth-card h2,.auth-card h3,.auth-card p,.auth-card label{color:#0b4f59!important;}
.plot-card{background:rgba(255,255,255,.86);border-radius:24px;padding:18px 18px 8px 18px;box-shadow:0 20px 45px rgba(0,0,0,.16);border:1px solid rgba(255,255,255,.6);}
.plot-title{color:#0b4f59;font-weight:900;font-size:18px;margin:4px 0 12px 8px;}
hr{border-color:rgba(255,255,255,.18)!important;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------- Supabase low-level client ----------
def get_secrets() -> Tuple[str, str]:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_ANON_KEY", "")
    return url.rstrip("/"), key

def sb_headers(token: Optional[str] = None) -> Dict[str, str]:
    url, key = get_secrets()
    h = {"apikey": key, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    else:
        h["Authorization"] = f"Bearer {key}"
    return h

def supabase_ready() -> bool:
    url, key = get_secrets()
    return bool(url and key)

def auth_request(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url, _ = get_secrets()
    r = requests.post(f"{url}/auth/v1/{endpoint}", headers=sb_headers(), json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"message": r.text}
    if r.status_code >= 400:
        raise RuntimeError(data.get("msg") or data.get("message") or str(data))
    return data

def db_select(table: str, token: Optional[str], params: Dict[str, str] = None) -> List[Dict[str, Any]]:
    url, _ = get_secrets()
    r = requests.get(f"{url}/rest/v1/{table}", headers=sb_headers(token), params=params or {}, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

def db_insert(table: str, rows: List[Dict[str, Any]], token: Optional[str]) -> List[Dict[str, Any]]:
    url, _ = get_secrets()
    h = sb_headers(token); h["Prefer"] = "return=representation"
    r = requests.post(f"{url}/rest/v1/{table}", headers=h, json=rows, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json() if r.text else []

def db_update(table: str, values: Dict[str, Any], token: Optional[str], params: Dict[str, str]) -> List[Dict[str, Any]]:
    url, _ = get_secrets()
    h = sb_headers(token); h["Prefer"] = "return=representation"
    r = requests.patch(f"{url}/rest/v1/{table}", headers=h, params=params, json=values, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json() if r.text else []

def db_delete(table: str, token: Optional[str], params: Dict[str, str]) -> None:
    url, _ = get_secrets()
    r = requests.delete(f"{url}/rest/v1/{table}", headers=sb_headers(token), params=params, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(r.text)

# ---------- Auth ----------
def is_ya_email(email: str) -> bool:
    return (email or "").strip().lower().endswith(ALLOWED_DOMAIN)

def create_or_sync_profile(user: Dict[str, Any], token: str) -> Dict[str, Any]:
    email = user.get("email", "").lower()
    uid = user.get("id")
    existing = db_select("profiles", token, {"id": f"eq.{uid}", "select": "*"})
    if existing:
        return existing[0]
    role = "admin" if email in ADMIN_EMAILS else "user"
    approved = email in ADMIN_EMAILS
    row = {"id": uid, "email": email, "role": role, "approved": approved, "created_at": datetime.now(timezone.utc).isoformat()}
    return db_insert("profiles", [row], token)[0]

def log_action(action: str, details: Dict[str, Any] = None):
    if not supabase_ready() or "user" not in st.session_state:
        return
    u = st.session_state.user
    token = st.session_state.access_token
    row = {"user_id": u.get("id"), "email": u.get("email"), "action": action, "details": details or {}, "created_at": datetime.now(timezone.utc).isoformat()}
    try:
        db_insert("audit_logs", [row], token)
    except Exception:
        pass

def login_screen():
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.image(YA_LOGO_URL, width=210)
    st.markdown("<h2>Compliance Benchmarking System</h2><p>Secure internal access for Young Academics users.</p>", unsafe_allow_html=True)
    if not supabase_ready():
        st.error("Supabase is not configured yet. Add SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit Secrets.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    tab_login, tab_signup, tab_reset = st.tabs(["Login", "Request access", "Reset password"])
    with tab_login:
        email = st.text_input("Email", key="login_email").strip().lower()
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", key="login_btn"):
            if not is_ya_email(email):
                st.error("Use your @youngacademics.com.au email address.")
            else:
                try:
                    data = auth_request("token?grant_type=password", {"email": email, "password": password})
                    st.session_state.access_token = data["access_token"]
                    st.session_state.refresh_token = data.get("refresh_token")
                    st.session_state.user = data["user"]
                    profile = create_or_sync_profile(data["user"], data["access_token"])
                    st.session_state.profile = profile
                    log_action("login", {"method": "password"})
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
    with tab_signup:
        st.caption("Accounts are created as pending. James or Eric must approve access.")
        email = st.text_input("Young Academics email", key="signup_email").strip().lower()
        password = st.text_input("Create password", type="password", key="signup_password")
        password2 = st.text_input("Confirm password", type="password", key="signup_password2")
        if st.button("Request access", key="signup_btn"):
            if not is_ya_email(email):
                st.error("Only @youngacademics.com.au emails can request access.")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters.")
            elif password != password2:
                st.error("Passwords do not match.")
            else:
                try:
                    data = auth_request("signup", {"email": email, "password": password})
                    token = data.get("access_token")
                    if token and data.get("user"):
                        st.session_state.access_token = token
                        st.session_state.user = data["user"]
                        profile = create_or_sync_profile(data["user"], token)
                        st.session_state.profile = profile
                        log_action("request_access", {"email": email})
                    st.success("Access request created. An admin now needs to approve you.")
                except Exception as e:
                    st.error(f"Could not create account: {e}")
    with tab_reset:
        email = st.text_input("Email for password reset", key="reset_email").strip().lower()
        if st.button("Send reset email", key="reset_btn"):
            if not is_ya_email(email):
                st.error("Use your @youngacademics.com.au email address.")
            else:
                try:
                    auth_request("recover", {"email": email})
                    st.success("Password reset email sent if the account exists.")
                except Exception as e:
                    st.error(f"Could not send reset: {e}")
    st.markdown("<p class='disclaimer'>This system is the property of Young Academics Early Learning Centre. Any unauthorised access, use, copying, distribution, or disclosure is strictly prohibited.</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def require_auth() -> bool:
    if "user" not in st.session_state or "profile" not in st.session_state:
        login_screen()
        return False
    prof = st.session_state.profile
    if not prof.get("approved"):
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        st.image(YA_LOGO_URL, width=200)
        st.warning("Your account is pending approval. James or Eric must approve access before you can use the tool.")
        if st.button("Logout"):
            st.session_state.clear(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    return True

# ---------- Parsing ----------
def read_pdf_text(file) -> str:
    data = file.getvalue()
    text_parts = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for p in pdf.pages:
            text_parts.append(p.extract_text() or "")
    return "\n".join(text_parts)

def file_hash(file) -> str:
    return hashlib.sha256(file.getvalue()).hexdigest()

def detect_report_type(filename: str, text: str) -> str:
    hay = f"{filename}\n{text[:5000]}".lower()
    if "involuntary suspension" in hay or "involuntary_suspension" in hay:
        return "Involuntary Suspension"
    if "provider approval cancellations" in hay or "cancellations_providers" in hay or "provider approval cancellation" in hay:
        return "Provider Approval Cancellation"
    if "service approval cancellations" in hay or "cancellations_services" in hay or "service approval cancellation" in hay:
        return "Service Approval Cancellation"
    if "enforceable undertakings" in hay or "service_enforcement_action" in hay or "compliance notices" in hay:
        return "Service Enforcement"
    return "UNIDENTIFIED REPORT TYPE"

def q_from_month_year(months: List[str], year: int) -> Optional[str]:
    mset = {m.lower()[:3] for m in months}
    if {"jul", "aug", "sep"} & mset:
        return f"Q1 FY{str(year)[-2:]}/{str(year+1)[-2:]} — Jul–Sep {year}"
    if {"oct", "nov", "dec"} & mset:
        return f"Q2 FY{str(year)[-2:]}/{str(year+1)[-2:]} — Oct–Dec {year}"
    if {"jan", "feb", "mar"} & mset:
        return f"Q3 FY{str(year-1)[-2:]}/{str(year)[-2:]} — Jan–Mar {year}"
    if {"apr", "may", "jun"} & mset:
        return f"Q4 FY{str(year-1)[-2:]}/{str(year)[-2:]} — Apr–Jun {year}"
    return None

def detect_quarter(filename: str, text: str) -> str:
    hay = f"{filename}\n{text[:4000]}"
    m = re.search(r"(July|Jul)\s*(?:to|–|-)\s*(September|Sep)\s*(\d{4})", hay, re.I)
    if m: return q_from_month_year(["Jul","Sep"], int(m.group(3))) or "UNIDENTIFIED QUARTER — CHECK PDF"
    m = re.search(r"(October|Oct)\s*(?:to|–|-)\s*(December|Dec)\s*(\d{4})", hay, re.I)
    if m: return q_from_month_year(["Oct","Dec"], int(m.group(3))) or "UNIDENTIFIED QUARTER — CHECK PDF"
    m = re.search(r"(January|Jan)\s*(?:to|–|-)\s*(March|Mar)\s*(\d{4})", hay, re.I)
    if m: return q_from_month_year(["Jan","Mar"], int(m.group(3))) or "UNIDENTIFIED QUARTER — CHECK PDF"
    m = re.search(r"(April|Apr)\s*(?:to|–|-)\s*(June|Jun)\s*(\d{4})", hay, re.I)
    if m: return q_from_month_year(["Apr","Jun"], int(m.group(3))) or "UNIDENTIFIED QUARTER — CHECK PDF"
    # filename fallback Q1_..._2025_2026
    m = re.search(r"Q([1-4]).*?(20\d{2})[_-](20\d{2})", filename, re.I)
    if m:
        q, y1, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return {1:f"Q1 FY{str(y1)[-2:]}/{str(y2)[-2:]} — Jul–Sep {y1}",2:f"Q2 FY{str(y1)[-2:]}/{str(y2)[-2:]} — Oct–Dec {y1}",3:f"Q3 FY{str(y1)[-2:]}/{str(y2)[-2:]} — Jan–Mar {y2}",4:f"Q4 FY{str(y1)[-2:]}/{str(y2)[-2:]} — Apr–Jun {y2}"}[q]
    return "UNIDENTIFIED QUARTER — CHECK PDF"

def load_mapping() -> pd.DataFrame:
    p = Path("provider_mapping.csv")
    if p.exists(): return pd.read_csv(p)
    return pd.DataFrame({"pattern": ["Young Academics"], "provider": ["Young Academics"]})

def infer_provider(service_name: str, mapping: pd.DataFrame) -> str:
    name = service_name or "Unknown"
    for _, row in mapping.iterrows():
        if str(row["pattern"]).lower() in name.lower():
            return str(row["provider"])
    # fallback before dash or first three words
    cleaned = re.split(r"\s+-\s+|\s+at\s+|\s+@\s+", name)[0].strip()
    return " ".join(cleaned.split()[:3]) if cleaned else "Unknown"

def extract_law_refs(reason: str) -> List[str]:
    if not reason: return []
    refs = []
    for m in re.finditer(r"\b(?:Law|Section|s\.?|S\.?)\s*([0-9]{1,3}[A-Z]?)(?:\s*\([^)]*\))*|\bRegulation\s*([0-9]{1,3}[A-Z]*)(?:\s*\([^)]*\))*", reason, re.I):
        law, reg = m.group(1), m.group(2)
        if law:
            refs.append(f"Law {law.upper()}")
        elif reg:
            refs.append(f"Regulation {reg.upper()}")
    # rows sometimes start '165(1)' without Law
    for m in re.finditer(r"(?m)^\s*(165|166|167)\s*\([^)]*\)?", reason):
        refs.append(f"Law {m.group(1)}")
    return refs

def classify_breach(ref: str) -> str:
    m = re.search(r"Law\s*(\d+)", ref, re.I)
    if m and m.group(1) in SIGNIFICANT:
        return f"Significant matter: Law {m.group(1)}"
    return "Other Law/Reg breach"

def action_category(report_type: str, details: str) -> str:
    d = (details or "").lower()
    if report_type == "Provider Approval Cancellation": return "Provider approval cancellation"
    if report_type == "Service Approval Cancellation": return "Service approval cancellation"
    if report_type == "Involuntary Suspension": return "Involuntary suspension"
    if "emergency action" in d or "section 179" in d: return "Emergency action notice"
    if "enforceable undertaking" in d or "179a" in d: return "Enforceable undertaking"
    return "Compliance notice"

def split_rows_from_text(text: str, report_type: str, quarter: str, filename: str, mapping: pd.DataFrame) -> pd.DataFrame:
    # Split at Service/Provider IDs while keeping ID
    pattern = r"(?=(?:SE|PR)-\d{5,8})"
    chunks = [c.strip() for c in re.split(pattern, text) if re.match(r"^(?:SE|PR)-\d", c.strip())]
    rows = []
    for chunk in chunks:
        first_line = chunk.splitlines()[0] if chunk.splitlines() else chunk[:80]
        idm = re.match(r"((?:SE|PR)-\d{5,8})\s+(.*)", first_line)
        if not idm: continue
        entity_id = idm.group(1)
        after = idm.group(2).strip()
        date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", chunk)
        date_issued = date_match.group(1) if date_match else ""
        # crude service/provider name = text between id and first date, stripped of addressy tail where possible
        before_date = chunk[:date_match.start()] if date_match else first_line
        before_date = re.sub(rf"^{re.escape(entity_id)}\s*", "", before_date).strip()
        entity_name = " ".join(before_date.split()[:8]).strip()
        reason = chunk[date_match.end():] if date_match else chunk
        details = ""
        dm = re.search(r"(Issue of|Enter into|Cancellation of|Service approval suspended)", reason, re.I)
        if dm:
            details = reason[dm.start():]
            reason = reason[:dm.start()]
        provider = infer_provider(entity_name, mapping) if entity_id.startswith("SE") else entity_name
        refs = extract_law_refs(reason)
        rows.append({
            "quarter": quarter, "report_type": report_type, "source_file": filename, "entity_id": entity_id,
            "service_or_provider": entity_name, "provider": provider, "date_issued": date_issued,
            "reason_excerpt": reason[:1200], "details_excerpt": details[:600],
            "action_category": action_category(report_type, details), "law_refs": refs,
            "significant_count": sum(1 for r in refs if classify_breach(r).startswith("Significant")),
            "other_count": sum(1 for r in refs if classify_breach(r) == "Other Law/Reg breach"),
            "total_breach_references": len(refs),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows)

def parse_file(file, quarter: str, report_type: str) -> pd.DataFrame:
    text = read_pdf_text(file)
    mapping = load_mapping()
    df = split_rows_from_text(text, report_type, quarter, file.name, mapping)
    return df

# ---------- Data operations ----------
def get_records() -> pd.DataFrame:
    rows = db_select("compliance_records", st.session_state.access_token, {"select": "*", "order": "uploaded_at.desc"})
    return pd.DataFrame(rows)

def get_uploaded_reports() -> pd.DataFrame:
    rows = db_select("uploaded_reports", st.session_state.access_token, {"select": "*", "order": "uploaded_at.desc"})
    return pd.DataFrame(rows)

def existing_count(quarter: str, report_type: str) -> int:
    rows = db_select("uploaded_reports", st.session_state.access_token, {"quarter": f"eq.{quarter}", "report_type": f"eq.{report_type}", "select": "id"})
    return len(rows)

def save_parsed_file(file, quarter: str, report_type: str, replace: bool = False) -> Tuple[int, int]:
    token = st.session_state.access_token
    user = st.session_state.user
    h = file_hash(file)
    if replace:
        db_delete("compliance_records", token, {"quarter": f"eq.{quarter}", "report_type": f"eq.{report_type}"})
        db_delete("uploaded_reports", token, {"quarter": f"eq.{quarter}", "report_type": f"eq.{report_type}"})
        log_action("replace_existing_report", {"quarter": quarter, "report_type": report_type, "file": file.name})
    df = parse_file(file, quarter, report_type)
    report_row = {
        "quarter": quarter, "report_type": report_type, "file_name": file.name, "file_sha256": h,
        "uploaded_by": user.get("email"), "uploaded_by_user_id": user.get("id"), "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(df)),
    }
    db_insert("uploaded_reports", [report_row], token)
    if not df.empty:
        df["uploaded_by"] = user.get("email")
        df["uploaded_by_user_id"] = user.get("id")
        # law_refs as JSON list is accepted by jsonb column
        db_insert("compliance_records", df.where(pd.notna(df), None).to_dict("records"), token)
    log_action("upload_report", {"quarter": quarter, "report_type": report_type, "file": file.name, "rows": int(len(df))})
    return 1, len(df)

# ---------- UI helpers ----------
def header():
    st.markdown(f"""
    <div class='hero'>
      <div class='hero-grid'>
        <div class='logo-box'><img src='{YA_LOGO_URL}' width='190'></div>
        <div>
          <h1>Young Academics Compliance Benchmarking Tool</h1>
          <p>Register of Published Enforcement Actions Benchmarking</p>
          <p>Developed by James Maclean-Horton</p>
        </div>
        <div class='badge'>{APP_VERSION}</div>
      </div>
      <div class='notice'>Internal reporting tool for quarterly NSW enforcement action PDFs, provider benchmarking, Law 165/166/167 split, cancellations, suspensions, and rolling history.</div>
      <p class='disclaimer'>This system and its outputs are the property of Young Academics Early Learning Centre. Any unauthorised access, use, copying, distribution, or disclosure is strictly prohibited.</p>
    </div>
    """, unsafe_allow_html=True)

def metric(label: str, value: Any, note: str = ""):
    st.markdown(f"<div class='metric-card'><div class='label'>{label}</div><div class='value'>{value}</div><div class='note'>{note}</div></div>", unsafe_allow_html=True)

def styled_plot(fig, title):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=15,r=15,t=20,b=15), font=dict(color="#0b4f59"), legend=dict(orientation="v"))
    st.markdown(f"<div class='plot-card'><div class='plot-title'>{title}</div>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def excel_bytes(dfs: Dict[str, pd.DataFrame]) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, df in dfs.items():
            sheet = re.sub(r"[^A-Za-z0-9 _-]", "", name)[:31] or "Sheet"
            df.to_excel(writer, sheet_name=sheet, index=False)
    return out.getvalue()

# ---------- Admin ----------
def admin_panel():
    prof = st.session_state.profile
    if prof.get("role") != "admin":
        st.info("Admin tools are restricted.")
        return
    st.markdown("## Admin")
    tab_users, tab_logs, tab_delete = st.tabs(["User approvals", "Audit logs", "Delete data"])
    with tab_users:
        profiles = pd.DataFrame(db_select("profiles", st.session_state.access_token, {"select":"*", "order":"created_at.desc"}))
        if profiles.empty:
            st.info("No profiles found.")
        else:
            st.dataframe(profiles[["email","role","approved","created_at"]], use_container_width=True, hide_index=True)
            emails = profiles["email"].tolist()
            selected = st.selectbox("Select user", emails, key="admin_user_select")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Approve", key="approve_user"):
                    uid = profiles.loc[profiles.email==selected, "id"].iloc[0]
                    db_update("profiles", {"approved": True}, st.session_state.access_token, {"id": f"eq.{uid}"})
                    log_action("approve_user", {"email": selected})
                    st.rerun()
            with col2:
                new_role = st.selectbox("Role", ["user","admin"], key="role_select")
                if st.button("Update role", key="role_update"):
                    uid = profiles.loc[profiles.email==selected, "id"].iloc[0]
                    db_update("profiles", {"role": new_role}, st.session_state.access_token, {"id": f"eq.{uid}"})
                    log_action("update_user_role", {"email": selected, "role": new_role})
                    st.rerun()
            with col3:
                if st.button("Suspend", key="suspend_user"):
                    uid = profiles.loc[profiles.email==selected, "id"].iloc[0]
                    db_update("profiles", {"approved": False}, st.session_state.access_token, {"id": f"eq.{uid}"})
                    log_action("suspend_user", {"email": selected})
                    st.rerun()
    with tab_logs:
        logs = pd.DataFrame(db_select("audit_logs", st.session_state.access_token, {"select":"*", "order":"created_at.desc", "limit":"500"}))
        if logs.empty: st.info("No logs yet.")
        else: st.dataframe(logs[["created_at","email","action","details"]], use_container_width=True, hide_index=True)
    with tab_delete:
        reports = get_uploaded_reports()
        if reports.empty:
            st.info("No saved reports.")
        else:
            reports["label"] = reports["quarter"] + " — " + reports["report_type"] + " — " + reports["file_name"]
            choice = st.selectbox("Saved report to delete", reports["label"].tolist(), key="delete_choice")
            st.warning("Deletion is permanent. Admin password is required again.")
            pw = st.text_input("Re-enter your password", type="password", key="admin_delete_pw")
            if st.button("Delete selected report", key="delete_selected_report"):
                email = st.session_state.user.get("email")
                try:
                    auth_request("token?grant_type=password", {"email": email, "password": pw})
                    row = reports.loc[reports.label==choice].iloc[0]
                    db_delete("compliance_records", st.session_state.access_token, {"quarter": f"eq.{row['quarter']}", "report_type": f"eq.{row['report_type']}"})
                    db_delete("uploaded_reports", st.session_state.access_token, {"id": f"eq.{row['id']}"})
                    log_action("delete_report", {"quarter": row["quarter"], "report_type": row["report_type"], "file": row["file_name"]})
                    st.success("Deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Deletion blocked: {e}")

# ---------- Main App ----------
def upload_workflow():
    st.markdown("## Bulk upload")
    st.caption("Drop any number of quarterly PDFs. The app detects quarter and report type, but you can correct them before saving.")
    files = st.file_uploader("Drop all NSW enforcement PDFs here", type=["pdf"], accept_multiple_files=True, key="bulk_pdf_upload")
    if not files:
        return
    rows = []
    text_cache = {}
    with st.spinner("Reading PDF headers..."):
        for f in files:
            try:
                text = read_pdf_text(f)
                text_cache[f.name] = text
                q = detect_quarter(f.name, text)
                rt = detect_report_type(f.name, text)
                exists = 0 if q.startswith("UNIDENTIFIED") or rt.startswith("UNIDENTIFIED") else existing_count(q, rt)
                status = "Ready" if not q.startswith("UNIDENTIFIED") and not rt.startswith("UNIDENTIFIED") and exists == 0 else ("Already uploaded" if exists else "Needs check")
                rows.append({"File": f.name, "Detected quarter": q, "Detected report type": rt, "Existing rows": exists, "Status": status})
            except Exception as e:
                rows.append({"File": f.name, "Detected quarter": "UNIDENTIFIED QUARTER — CHECK PDF", "Detected report type": "UNIDENTIFIED REPORT TYPE", "Existing rows": 0, "Status": f"Error: {e}"})
    review = pd.DataFrame(rows)
    st.markdown("### Upload review")
    edited = st.data_editor(
        review,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Detected quarter": st.column_config.SelectboxColumn("Quarter", options=QUARTERS + ["UNIDENTIFIED QUARTER — CHECK PDF"], required=True),
            "Detected report type": st.column_config.SelectboxColumn("Report type", options=REPORT_TYPES + ["UNIDENTIFIED REPORT TYPE"], required=True),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Existing rows": st.column_config.NumberColumn("Existing rows", disabled=True),
            "File": st.column_config.TextColumn("File", disabled=True),
        },
        key="upload_review_editor"
    )
    # recompute readiness after edits
    edited["Existing rows"] = edited.apply(lambda r: 0 if str(r["Detected quarter"]).startswith("UNIDENTIFIED") or str(r["Detected report type"]).startswith("UNIDENTIFIED") else existing_count(r["Detected quarter"], r["Detected report type"]), axis=1)
    edited["Status"] = edited.apply(lambda r: "Needs check" if str(r["Detected quarter"]).startswith("UNIDENTIFIED") or str(r["Detected report type"]).startswith("UNIDENTIFIED") else ("Already uploaded" if r["Existing rows"] else "Ready"), axis=1)
    st.markdown("#### Final status")
    st.dataframe(edited, use_container_width=True, hide_index=True, key="upload_final_status")
    mode = st.radio("Duplicate handling", ["Process new files only", "Replace existing quarter/report type", "Stop if anything already exists"], horizontal=True)
    ready = not any(edited["Status"].str.contains("Needs check", na=False))
    if not ready:
        st.warning("Fix all unidentified quarters/report types before saving. Use the dropdowns above.")
        return
    if st.button("Save reviewed uploads", key="save_reviewed_uploads"):
        if mode == "Stop if anything already exists" and any(edited["Existing rows"] > 0):
            st.error("Blocked because one or more quarter/report combinations already exist.")
            return
        total_files, total_rows = 0, 0
        for _, row in edited.iterrows():
            if row["Existing rows"] > 0 and mode == "Process new files only":
                continue
            f = next(x for x in files if x.name == row["File"])
            replace = bool(row["Existing rows"] > 0 and mode == "Replace existing quarter/report type")
            _, nrows = save_parsed_file(f, row["Detected quarter"], row["Detected report type"], replace=replace)
            total_files += 1; total_rows += nrows
        st.success(f"Saved {total_files} file(s), {total_rows} extracted row(s).")
        st.rerun()

def dashboard():
    records = get_records()
    if records.empty:
        st.info("No saved data yet. Upload PDFs first.")
        return
    quarters = [q for q in QUARTERS if q in records["quarter"].unique().tolist()]
    if not quarters:
        quarters = sorted(records["quarter"].dropna().unique().tolist())
    selected_quarter = st.selectbox("Select quarter", quarters, index=len(quarters)-1 if quarters else 0, key="dash_quarter_select")
    qdf = records[records["quarter"] == selected_quarter].copy()
    st.markdown(f"<p class='small-muted'>Current selected quarter: {selected_quarter}</p>", unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1: metric("Actions", len(qdf), "Rows/actions extracted")
    with c2: metric("Breach references", int(qdf["total_breach_references"].fillna(0).sum()), "Law/Reg mentions")
    with c3: metric("L165/166/167", int(qdf["significant_count"].fillna(0).sum()), "Significant matters")
    with c4: metric("YA actions", len(qdf[qdf["provider"].str.contains("Young Academics", case=False, na=False)]), "Young Academics rows")
    with c5: metric("YA significant", int(qdf.loc[qdf["provider"].str.contains("Young Academics", case=False, na=False), "significant_count"].fillna(0).sum()), "Significant matters")

    tabs = st.tabs(["Dashboard", "Provider benchmarking", "Quarter-on-quarter", "Provider deep dive", "Raw data", "Export"])
    with tabs[0]:
        colA, colB = st.columns(2)
        action_counts = qdf.groupby("action_category", dropna=False).size().reset_index(name="Count")
        action_counts["Percent"] = (action_counts["Count"] / action_counts["Count"].sum() * 100).round(1) if not action_counts.empty else 0
        breach_counts = pd.DataFrame({"Category": ["Significant matter: Law 165/166/167", "Other Law/Reg breach"], "Count": [int(qdf["significant_count"].fillna(0).sum()), int(qdf["other_count"].fillna(0).sum())]})
        breach_counts = breach_counts[breach_counts["Count"] > 0]
        breach_counts["Percent"] = (breach_counts["Count"] / breach_counts["Count"].sum() * 100).round(1) if not breach_counts.empty else 0
        with colA:
            fig = px.pie(action_counts, names="action_category", values="Count", hole=.52, hover_data=["Percent"], color_discrete_sequence=px.colors.qualitative.Set3)
            styled_plot(fig, "Current quarter actions by category")
            st.dataframe(action_counts, use_container_width=True, hide_index=True, key="action_counts_table")
        with colB:
            fig = px.pie(breach_counts, names="Category", values="Count", hole=.52, hover_data=["Percent"], color_discrete_sequence=px.colors.qualitative.Pastel)
            styled_plot(fig, "Current quarter breach references by category")
            st.dataframe(breach_counts, use_container_width=True, hide_index=True, key="breach_counts_table")
        st.markdown("### Competitors by category")
        competitor_cat = qdf.groupby(["provider", "action_category"], dropna=False).size().reset_index(name="Actions")
        total_by_provider = competitor_cat.groupby("provider")["Actions"].transform("sum")
        competitor_cat["Percent of provider actions"] = (competitor_cat["Actions"] / total_by_provider * 100).round(1)
        st.dataframe(competitor_cat.sort_values(["Actions"], ascending=False), use_container_width=True, hide_index=True, key="competitor_cat_table")
    with tabs[1]:
        summary = qdf.groupby("provider", dropna=False).agg(
            **{"Enforcement Actions": ("provider", "size"), "Other": ("other_count", "sum"), "L165/166/167": ("significant_count", "sum"), "Total Breach References": ("total_breach_references", "sum")}
        ).reset_index().sort_values(["Enforcement Actions","Total Breach References"], ascending=False)
        summary.insert(0, "Rank", range(1, len(summary)+1))
        st.dataframe(summary, use_container_width=True, hide_index=True, key="provider_benchmark_table")
    with tabs[2]:
        qo = records.groupby(["quarter","provider","action_category"], dropna=False).agg(Actions=("provider","size"), Significant=("significant_count","sum"), Other=("other_count","sum"), Breaches=("total_breach_references","sum")).reset_index()
        st.dataframe(qo, use_container_width=True, hide_index=True, key="qoq_table")
        top_providers = qo.groupby("provider")["Actions"].sum().sort_values(ascending=False).head(12).index.tolist()
        chart_df = qo[qo["provider"].isin(top_providers)].groupby(["quarter","provider"])["Actions"].sum().reset_index()
        fig = px.line(chart_df, x="quarter", y="Actions", color="provider", markers=True)
        styled_plot(fig, "Quarter-on-quarter actions by competitor")
    with tabs[3]:
        providers = sorted(records["provider"].dropna().unique().tolist())
        provider = st.selectbox("Select provider", providers, key="provider_deep_select")
        pdf = records[records["provider"] == provider].copy()
        st.markdown(f"## {provider}")
        c1,c2,c3,c4 = st.columns(4)
        with c1: metric("Total actions", len(pdf))
        with c2: metric("Significant", int(pdf["significant_count"].fillna(0).sum()))
        with c3: metric("Other", int(pdf["other_count"].fillna(0).sum()))
        with c4: metric("Breach refs", int(pdf["total_breach_references"].fillna(0).sum()))
        st.dataframe(pdf[["quarter","report_type","service_or_provider","date_issued","action_category","significant_count","other_count","total_breach_references","reason_excerpt"]], use_container_width=True, hide_index=True, key="provider_detail_table")
    with tabs[4]:
        st.dataframe(records, use_container_width=True, hide_index=True, key="raw_records_table")
    with tabs[5]:
        exports = {
            "records": records,
            "current_quarter_records": qdf,
            "current_quarter_action_categories": action_counts,
            "current_quarter_breach_categories": breach_counts,
            "qoq_by_provider_category": records.groupby(["quarter","provider","action_category"], dropna=False).size().reset_index(name="Actions"),
        }
        st.download_button("Download Excel workbook", excel_bytes(exports), file_name=f"YA_Compliance_Benchmarking_{datetime.now().date()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def main():
    if not require_auth():
        return
    header()
    top_col1, top_col2 = st.columns([1, .25])
    with top_col1:
        st.markdown(f"<p class='small-muted'>Signed in as <strong>{st.session_state.user.get('email')}</strong> · role: <strong>{st.session_state.profile.get('role')}</strong></p>", unsafe_allow_html=True)
    with top_col2:
        if st.button("Logout", key="logout_btn"):
            st.session_state.clear(); st.rerun()
    nav = st.tabs(["Upload", "Results", "Admin"])
    with nav[0]: upload_workflow()
    with nav[1]: dashboard()
    with nav[2]: admin_panel()

if __name__ == "__main__":
    main()
