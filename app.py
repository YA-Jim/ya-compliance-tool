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

APP_TITLE = "Young Academics Compliance Benchmarking Tool v1.2"
DB_PATH = "compliance_history.sqlite3"
SIGNIFICANT_LAWS = {"165", "166", "167"}

# Edit this list in the app using the sidebar CSV download/upload if needed.
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

st.set_page_config(page_title=APP_TITLE, layout="wide")

YA_CSS = """
<style>
:root { --ya-teal:#357b84; --ya-dark:#00504f; --ya-blue:#08245c; }
.block-container { padding-top: 1.5rem; }
h1, h2, h3 { color: var(--ya-teal); }
.stButton > button { background:#357b84; color:white; border-radius:8px; border:0; font-weight:700; }
.stDownloadButton > button { background:#08245c; color:white; border-radius:8px; border:0; font-weight:700; }
.metric-card { background:#eaf6f8; padding:14px; border-radius:12px; border:1px solid #b8dce1; }
.small-note { color:#555; font-size:0.9rem; }
</style>
"""
st.markdown(YA_CSS, unsafe_allow_html=True)


def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            run_id TEXT, quarter TEXT, report_type TEXT, action_id TEXT,
            entity_id TEXT, provider TEXT, service_name TEXT, date_issued TEXT,
            action_type TEXT, raw_text TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS breaches (
            run_id TEXT, quarter TEXT, action_id TEXT, provider TEXT,
            breach_code TEXT, breach_family TEXT, classification TEXT
        )
    """)
    con.commit(); con.close()


def save_to_db(actions: pd.DataFrame, breaches: pd.DataFrame):
    con = sqlite3.connect(DB_PATH)
    if not actions.empty:
        actions.to_sql("actions", con, if_exists="append", index=False)
    if not breaches.empty:
        breaches.to_sql("breaches", con, if_exists="append", index=False)
    con.close()


def load_history() -> Tuple[pd.DataFrame, pd.DataFrame]:
    init_db()
    con = sqlite3.connect(DB_PATH)
    actions = pd.read_sql_query("SELECT * FROM actions", con)
    breaches = pd.read_sql_query("SELECT * FROM breaches", con)
    con.close()
    return actions, breaches


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
    # Fallback: use a cleaned first few words before obvious address/date terms.
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
    # Start after first date; stop before common action-detail phrases.
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
        # Skip obvious action-detail laws where they slip in; keep NSW 223B etc as other.
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
    action_rows = []
    breach_rows = []
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
            })
    return pd.DataFrame(action_rows), pd.DataFrame(breach_rows)


def make_provider_summary(actions: pd.DataFrame, breaches: pd.DataFrame, quarters: List[str] = None) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame()
    a = actions.copy()
    b = breaches.copy()
    if quarters:
        a = a[a["quarter"].isin(quarters)]
        b = b[b["quarter"].isin(quarters)]
    action_counts = a.groupby("provider").size().rename("Enforcement Actions")
    if not b.empty:
        piv = b.pivot_table(index="provider", columns="classification", values="breach_code", aggfunc="count", fill_value=0)
    else:
        piv = pd.DataFrame(index=action_counts.index)
    for col in ["Significant matter: Law 165/166/167", "Other Law/Reg breach"]:
        if col not in piv.columns:
            piv[col] = 0
    out = pd.concat([action_counts, piv], axis=1).fillna(0)
    out = out.rename(columns={
        "Significant matter: Law 165/166/167": "L165/166/167",
        "Other Law/Reg breach": "Other",
    })
    out["Total Breach References"] = out["L165/166/167"] + out["Other"]
    out = out.reset_index().sort_values(["Enforcement Actions", "Total Breach References"], ascending=False)
    out.insert(0, "Rank", range(1, len(out) + 1))
    return out


def make_law_summary(breaches: pd.DataFrame) -> pd.DataFrame:
    if breaches.empty:
        return pd.DataFrame(columns=["breach_code", "Count"])
    return breaches.groupby("breach_code").size().reset_index(name="Count").sort_values("Count", ascending=False)


def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            safe = name[:31].replace("/", "-")
            df.to_excel(writer, sheet_name=safe, index=False)
            ws = writer.sheets[safe]
            for i, col in enumerate(df.columns):
                width = min(max(len(str(col)) + 2, 12), 45)
                ws.set_column(i, i, width)
    return output.getvalue()


def main():
    init_db()
    st.title(APP_TITLE)
    st.caption("Upload the NSW quarterly PDFs. The tool extracts actions, splits Law 165/166/167 from other breaches, saves history, and exports board-ready tables.")

    with st.sidebar:
        st.header("Provider mapping")
        st.write("The PDFs usually list services, not providers. This mapping tells the app how to group brands under providers.")
        default_map = rules_to_df()
        uploaded_map = st.file_uploader("Optional: upload provider_mapping.csv", type=["csv"], key="map")
        if uploaded_map:
            map_df = pd.read_csv(uploaded_map)
        else:
            map_df = default_map
        edited_map = st.data_editor(map_df, num_rows="dynamic", use_container_width=True)
        provider_rules = df_to_rules(edited_map)
        st.download_button("Download mapping CSV", edited_map.to_csv(index=False), "provider_mapping.csv", "text/csv")

    st.subheader("1. Select reporting period")
    quarter = st.text_input("Quarter label", value="Q2 FY25/26 — Oct–Dec 2025")

    st.subheader("2. Upload PDFs")
    col1, col2 = st.columns(2)
    with col1:
        service_enforcement = st.file_uploader("Service Enforcement Action Information PDF", type=["pdf"], key="service")
        provider_cancel = st.file_uploader("Provider Cancellations PDF", type=["pdf"], key="pcancel")
    with col2:
        service_cancel = st.file_uploader("Service Cancellations PDF", type=["pdf"], key="scancel")
        suspension = st.file_uploader("Involuntary Suspensions PDF", type=["pdf"], key="susp")

    st.subheader("3. Process")
    if st.button("Process uploaded reports"):
        uploads = [
            (service_enforcement, "Service Enforcement"),
            (provider_cancel, "Provider Approval Cancellation"),
            (service_cancel, "Service Approval Cancellation"),
            (suspension, "Involuntary Suspension"),
        ]
        all_actions, all_breaches = [], []
        with st.spinner("Reading PDFs and building benchmark tables..."):
            for file, rtype in uploads:
                if file is None:
                    continue
                a, b = parse_pdf(file, quarter, rtype, provider_rules)
                all_actions.append(a); all_breaches.append(b)
        actions = pd.concat(all_actions, ignore_index=True) if all_actions else pd.DataFrame()
        breaches = pd.concat(all_breaches, ignore_index=True) if all_breaches else pd.DataFrame()
        if actions.empty:
            st.error("No rows were extracted. Check that you uploaded the right PDF files.")
        else:
            save_to_db(actions, breaches)
            st.session_state["latest_actions"] = actions
            st.session_state["latest_breaches"] = breaches
            st.success(f"Processed {len(actions)} actions and {len(breaches)} breach references. Saved to history.")

    latest_actions = st.session_state.get("latest_actions", pd.DataFrame())
    latest_breaches = st.session_state.get("latest_breaches", pd.DataFrame())

    hist_actions, hist_breaches = load_history()
    active_actions = latest_actions if not latest_actions.empty else hist_actions
    active_breaches = latest_breaches if not latest_breaches.empty else hist_breaches

    st.subheader("4. Results")
    if active_actions.empty:
        st.info("Upload PDFs and click Process to see results.")
        return

    current_summary = make_provider_summary(latest_actions if not latest_actions.empty else active_actions, latest_breaches if not latest_breaches.empty else active_breaches)
    rolling_summary = make_provider_summary(hist_actions, hist_breaches)
    law_summary = make_law_summary(active_breaches)
    action_type_summary = active_actions.groupby(["quarter", "action_type"]).size().reset_index(name="Count").sort_values(["quarter", "Count"], ascending=[True, False])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Actions shown", f"{len(active_actions):,}")
    c2.metric("Breach references", f"{len(active_breaches):,}")
    sig_count = int((active_breaches["classification"] == "Significant matter: Law 165/166/167").sum()) if not active_breaches.empty else 0
    c3.metric("L165/166/167", f"{sig_count:,}")
    ya_actions = int((active_actions["provider"] == "Young Academics").sum())
    c4.metric("YA actions", f"{ya_actions:,}")

    tabs = st.tabs(["Current quarter", "Rolling history", "Law/Reg breakdown", "Raw extracted rows", "Export"])
    with tabs[0]:
        st.write("Provider ranking for the latest processed quarter/report batch.")
        st.dataframe(current_summary, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.write("All saved processed quarters. Use this as the rolling 4-quarter base once four quarters have been uploaded.")
        st.dataframe(rolling_summary, use_container_width=True, hide_index=True)
        st.dataframe(action_type_summary, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(law_summary, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(active_actions.drop(columns=["raw_text"], errors="ignore"), use_container_width=True, hide_index=True)
        st.dataframe(active_breaches, use_container_width=True, hide_index=True)
    with tabs[4]:
        sheets = {
            "Current Provider Ranking": current_summary,
            "Rolling Provider Ranking": rolling_summary,
            "Law Reg Breakdown": law_summary,
            "Action Type Summary": action_type_summary,
            "Extracted Actions": active_actions.drop(columns=["raw_text"], errors="ignore"),
            "Extracted Breaches": active_breaches,
        }
        xlsx = to_excel_bytes(sheets)
        st.download_button("Download Excel report", xlsx, "YA_Compliance_Benchmark_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("Download raw actions CSV", active_actions.to_csv(index=False), "extracted_actions.csv", "text/csv")
        st.download_button("Download raw breaches CSV", active_breaches.to_csv(index=False), "extracted_breaches.csv", "text/csv")

    st.caption("Important: always review extracted provider mappings before board use. NSW PDFs often list service names rather than provider groups, so the provider mapping table is the control point.")


if __name__ == "__main__":
    main()
