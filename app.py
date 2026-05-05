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
import io
import os
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    import pdfplumber
except Exception:
    pdfplumber = None

APP_TITLE = "Young Academics Compliance Benchmarking Tool"
APP_VERSION = "v1.6 — Internal Build"
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
.ya-title h1{font-size:31px; line-height:1.06; color:var(--ya-teal)!important; margin:0; font-weight:900; letter-spacing:-.02em;}
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
p,li,.stMarkdown,.stCaption,[data-testid="stCaptionContainer"]{color:#eefbfc!important;}
label,[data-testid="stWidgetLabel"],[data-testid="stWidgetLabel"] p{color:#ffffff!important; font-weight:800!important;}

/* Inputs */
input, textarea, select{border-radius:12px!important;}
[data-baseweb="input"]{border-radius:12px!important;}

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

/* Hide Streamlit menu/footer */
#MainMenu, footer{visibility:hidden;}
</style>
"""
st.markdown(YA_CSS, unsafe_allow_html=True)


def app_password() -> str:
    try:
        pw = st.secrets.get("APP_PASSWORD", None)
        if pw:
            return str(pw)
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD", "")


def check_password():
    required = app_password()
    if not required:
        return True
    if st.session_state.get("password_correct"):
        return True
    st.markdown(f"""
    <div class='ya-shell'>
      <div class='ya-header'>
        <div class='ya-brand'>
          <img class='ya-logo' src='{LOGO_URL}' />
          <div class='ya-title'>
            <h1>{APP_TITLE}</h1>
            <p>Internal access only</p>
          </div>
        </div>
        <div class='ya-version'>Secure Login</div>
      </div>
      <div class='ya-note'>Enter the internal password to continue.</div>
    </div>
    """, unsafe_allow_html=True)
    pw = st.text_input("Password", type="password", label_visibility="collapsed")
    if st.button("Unlock app"):
        if pw == required:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()


def init_db():
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
    # Backward-compatible column adds.
    for table in ["actions", "breaches"]:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN processed_at TEXT")
        except sqlite3.OperationalError:
            pass
    con.commit(); con.close()


def save_to_db(actions: pd.DataFrame, breaches: pd.DataFrame):
    con = sqlite3.connect(DB_PATH)
    processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not actions.empty:
        actions = actions.copy()
        if "processed_at" not in actions.columns:
            actions["processed_at"] = processed_at
        actions.to_sql("actions", con, if_exists="append", index=False)
    if not breaches.empty:
        breaches = breaches.copy()
        if "processed_at" not in breaches.columns:
            breaches["processed_at"] = processed_at
        breaches.to_sql("breaches", con, if_exists="append", index=False)
    if not actions.empty:
        run_id = str(actions["run_id"].iloc[0])
        quarter = str(actions["quarter"].iloc[0])
        con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?)", (run_id, quarter, processed_at, len(actions), len(breaches), ""))
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
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM actions WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM breaches WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
    con.commit(); con.close()


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


def parse_pdf(uploaded_file, quarter: str, report_type: str, provider_rules) -> Tuple[pd.DataFrame, pd.DataFrame]:
    text = read_pdf_text(uploaded_file)
    blocks = split_blocks(text)
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
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


def main():
    check_password()
    init_db()
    render_header()

    hist_actions, hist_breaches, runs = load_history()

    st.markdown("<div class='ya-section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='ya-panel-title'>Upload & Controls</div>", unsafe_allow_html=True)

    with st.expander("Provider mapping controls", expanded=False):
        st.caption("Provider mapping groups service names into provider/brand groups. Keep this collapsed unless you need to update or download the mapping file.")
        uploaded_map = st.file_uploader("Upload provider_mapping.csv", type=["csv"], key="map")
        map_df = pd.read_csv(uploaded_map) if uploaded_map else rules_to_df()
        edited_map = st.data_editor(map_df, num_rows="dynamic", use_container_width=True, height=280)
        st.download_button("Download provider mapping CSV", edited_map.to_csv(index=False), "provider_mapping.csv", "text/csv")

    provider_rules = df_to_rules(edited_map)

    colq1, colq2 = st.columns([1, 1])
    with colq1:
        quarter = st.text_input("Quarter label", value="Q2 FY25/26 — Oct–Dec 2025")
    with colq2:
        st.markdown("<span class='ya-pill'>Manual upload</span><span class='ya-pill'>Saved history</span><span class='ya-pill'>Excel export</span>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        service_enforcement = st.file_uploader("Service Enforcement Action Information PDF", type=["pdf"], key="service")
        provider_cancel = st.file_uploader("Provider Cancellations PDF", type=["pdf"], key="pcancel")
    with c2:
        service_cancel = st.file_uploader("Service Cancellations PDF", type=["pdf"], key="scancel")
        suspension = st.file_uploader("Involuntary Suspensions PDF", type=["pdf"], key="susp")

    action_col, history_col = st.columns([1, 1])
    with action_col:
        process_clicked = st.button("Process uploaded reports")
    with history_col:
        with st.expander("History manager", expanded=False):
            st.caption(f"Saved runs: {len(runs)}")
            if not runs.empty:
                run_labels = [f"{r['quarter']} — {r['processed_at']} — {r['actions_count']} actions" for _, r in runs.iterrows()]
                selected_delete = st.selectbox("Delete a saved run", [""] + run_labels)
                if selected_delete:
                    idx = run_labels.index(selected_delete)
                    run_id_to_delete = runs.iloc[idx]["run_id"]
                    if st.button("Delete selected run"):
                        delete_run(run_id_to_delete)
                        st.success("Deleted. Refreshing…")
                        st.rerun()
            else:
                st.caption("No saved runs yet.")

    if process_clicked:
        uploads = [
            (service_enforcement, "Service Enforcement"),
            (provider_cancel, "Provider Approval Cancellation"),
            (service_cancel, "Service Approval Cancellation"),
            (suspension, "Involuntary Suspension"),
        ]
        all_actions, all_breaches = [], []
        with st.spinner("Reading PDFs, extracting actions, classifying breaches, and saving history…"):
            for file, rtype in uploads:
                if file is None:
                    continue
                a, b = parse_pdf(file, quarter, rtype, provider_rules)
                all_actions.append(a)
                all_breaches.append(b)
        actions = pd.concat(all_actions, ignore_index=True) if all_actions else pd.DataFrame()
        breaches = pd.concat(all_breaches, ignore_index=True) if all_breaches else pd.DataFrame()
        if actions.empty:
            st.error("No rows were extracted. Check that you uploaded the correct NSW PDFs.")
        else:
            save_to_db(actions, breaches)
            st.session_state["latest_actions"] = actions
            st.session_state["latest_breaches"] = breaches
            st.success(f"Processed and saved: {len(actions)} actions and {len(breaches)} breach references.")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    hist_actions, hist_breaches, runs = load_history()
    if hist_actions.empty:
        st.info("Upload PDFs and click Process to start building historical tracking.")
        return

    quarters_all = list(dict.fromkeys(hist_actions.sort_values("processed_at", ascending=False)["quarter"].astype(str).tolist()))
    selected_quarters = st.multiselect("Select quarters to show", quarters_all, default=quarters_all[:4], help="Default shows the most recent four processed quarters for rolling history.")
    show_actions = hist_actions[hist_actions["quarter"].isin(selected_quarters)] if selected_quarters else hist_actions
    show_breaches = hist_breaches[hist_breaches["quarter"].isin(selected_quarters)] if selected_quarters and not hist_breaches.empty else hist_breaches

    current_quarter = selected_quarters[0] if selected_quarters else quarters_all[0]
    current_actions = hist_actions[hist_actions["quarter"].eq(current_quarter)]
    current_breaches = hist_breaches[hist_breaches["quarter"].eq(current_quarter)] if not hist_breaches.empty else hist_breaches

    current_summary = make_provider_summary(current_actions, current_breaches)
    rolling_summary = make_provider_summary(show_actions, show_breaches)
    law_summary = make_law_summary(show_breaches)
    q_summary = quarter_summary(show_actions, show_breaches)
    action_type_summary = show_actions.groupby(["quarter", "action_type"]).size().reset_index(name="Count").sort_values(["quarter", "Count"], ascending=[True, False])

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

    st.markdown(f"<div class='ya-warning'><strong>{ya_position_text(rolling_summary)}</strong></div>", unsafe_allow_html=True)

    tabs = st.tabs(["Current quarter", "Rolling 4-quarter view", "Trend", "Law/Reg breakdown", "Raw extracted rows", "Export"])
    with tabs[0]:
        st.caption(f"Current selected quarter: {current_quarter}")
        st.dataframe(current_summary, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.caption("Selected quarters combined. This is the rolling view for board reporting.")
        st.dataframe(rolling_summary, use_container_width=True, hide_index=True)
        st.dataframe(action_type_summary, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.caption("Quarter-by-quarter historical tracking.")
        st.dataframe(q_summary, use_container_width=True, hide_index=True)
        if not q_summary.empty:
            chart_df = q_summary.set_index("quarter")[["Enforcement Actions", "L165/166/167", "Other"]]
            st.line_chart(chart_df)
    with tabs[3]:
        st.dataframe(law_summary, use_container_width=True, hide_index=True)
    with tabs[4]:
        st.dataframe(show_actions.drop(columns=["raw_text"], errors="ignore"), use_container_width=True, hide_index=True)
        st.dataframe(show_breaches, use_container_width=True, hide_index=True)
    with tabs[5]:
        sheets = {
            "Current Provider Ranking": current_summary,
            "Rolling Provider Ranking": rolling_summary,
            "Quarter Trend": q_summary,
            "Law Reg Breakdown": law_summary,
            "Action Type Summary": action_type_summary,
            "Extracted Actions": show_actions.drop(columns=["raw_text"], errors="ignore"),
            "Extracted Breaches": show_breaches,
            "Runs History": runs,
        }
        xlsx = to_excel_bytes(sheets)
        st.download_button("Download Excel report", xlsx, "YA_Compliance_Benchmark_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("Download full history database", open(DB_PATH, "rb").read(), "compliance_history.sqlite3", "application/octet-stream")

    st.caption("Internal use only. Review provider mapping before board or Commission reporting, as NSW PDFs often list service names rather than provider groups.")


if __name__ == "__main__":
    main()
