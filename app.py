import streamlit as st
import pandas as pd
import pdfplumber
import re

st.set_page_config(layout="wide")

# =========================
# STYLING
# =========================
st.markdown("""
<style>
section.main {
    background: linear-gradient(180deg, #357b84 0%, #2f6f77 100%);
}
h1, h2, h3, h4, h5, h6, p, label {
    color: white !important;
}
.stDataFrame {
    background-color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("Young Academics Compliance Tool")

# =========================
# PDF EXTRACTION
# =========================
def extract_service_data_from_pdf(file):
    rows = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                headers = [str(h).strip().lower() if h else "" for h in table[0]]

                if "service name" in headers and "service id" in headers:
                    idx_name = headers.index("service name")
                    idx_id = headers.index("service id")

                    for row in table[1:]:
                        try:
                            service_name = row[idx_name]
                            service_id = row[idx_id]

                            if service_id:
                                rows.append({
                                    "service_id": str(service_id).strip(),
                                    "service_name": str(service_name).strip() if service_name else None
                                })
                        except:
                            continue

    return pd.DataFrame(rows)


# =========================
# LAW CLASSIFICATION
# =========================
def classify_law(text):
    if pd.isna(text):
        return "Other"
    if re.search(r"165|166|167", str(text)):
        return "Significant"
    return "Other"


# =========================
# COMPLIANCE TABLE
# =========================
def build_compliance_position(df):
    df["law_category"] = df["law"].apply(classify_law)

    summary = df.groupby("provider").agg(
        significant=("law_category", lambda x: (x == "Significant").sum()),
        total=("provider", "count")
    ).reset_index()

    summary["other"] = summary["total"] - summary["significant"]

    return summary[["provider", "significant", "other", "total"]].sort_values("total", ascending=False)


# =========================
# FILE UPLOAD
# =========================
st.header("Upload Files")

pdf_files = st.file_uploader(
    "Upload enforcement PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

lookup_file = st.file_uploader(
    "Upload Provider Lookup (CSV)",
    type=["csv"]
)

# =========================
# PROCESS
# =========================
if pdf_files and lookup_file:

    lookup_df = pd.read_csv(lookup_file)

    all_rows = []

    with st.spinner("Extracting data..."):
        for file in pdf_files:
            service_df = extract_service_data_from_pdf(file)

            if service_df.empty:
                continue

            # Fake placeholder law column (you'll improve this later)
            service_df["law"] = "Unknown"

            all_rows.append(service_df)

    if not all_rows:
        st.error("No valid data extracted")
        st.stop()

    df = pd.concat(all_rows, ignore_index=True)

    # =========================
    # MERGE PROVIDER DATA
    # =========================
    df = df.merge(lookup_df, on="service_id", how="left")

    df["provider"] = df["provider"].fillna("UNMAPPED")

    # =========================
    # SPLIT CLEAN VS UNMAPPED
    # =========================
    clean_df = df[df["provider"] != "UNMAPPED"]
    unmapped_df = df[df["provider"] == "UNMAPPED"]

    # =========================
    # DASHBOARD
    # =========================
    st.header("Compliance Position")

    compliance_table = build_compliance_position(clean_df)

    st.dataframe(compliance_table, use_container_width=True, hide_index=True)

    # =========================
    # UNMAPPED SECTION
    # =========================
    st.header("Unmapped Services")

    if not unmapped_df.empty:
        unmapped_grouped = (
            unmapped_df
            .groupby(["service_id", "service_name"])
            .size()
            .reset_index(name="Total")
            .sort_values("Total", ascending=False)
        )

        st.metric("Total Unmapped Records", int(unmapped_grouped["Total"].sum()))

        st.dataframe(unmapped_grouped, use_container_width=True, hide_index=True)
    else:
        st.success("No unmapped services")

    # =========================
    # RAW DATA (optional)
    # =========================
    with st.expander("View Raw Data"):
        st.dataframe(df, use_container_width=True)

else:
    st.info("Upload PDFs and a provider lookup file to begin")
