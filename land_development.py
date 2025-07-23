import streamlit as st
import pandas as pd
import sqlite3
import io

# --- Cached DB Connection ---
@st.cache_resource
def get_connection():
    conn = sqlite3.connect("deals.db", check_same_thread=False)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS land_development (
            LD_PK INTEGER PRIMARY KEY AUTOINCREMENT,
            community TEXT,
            location TEXT,
            budget_item TEXT,
            contractor TEXT,
            classification TEXT,
            proposed_budget REAL,
            change_order REAL,
            revised_budget REAL,
            status TEXT,
            date_executed TEXT
        )
    ''')
    conn.commit()
    return conn

conn = get_connection()
cursor = conn.cursor()

# --- Safe Currency Formatter ---
def safe_currency(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# --- Load Data ---
@st.cache_data(ttl=10)
def load_data():
    df = pd.read_sql_query("SELECT * FROM land_development", conn)
    for col in ["proposed_budget", "change_order", "revised_budget"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df

# --- Add Entry View ---
def render_add_entry():
    st.header("➕ Add Land Development Entry")
    classification = st.selectbox("Classification", ["Proposed Budget", "Change Order"])

    with st.form("add_entry_form"):
        community = st.text_input("Community")
        location = st.text_input("Location")
        budget_item = st.text_input("Budget Item")
        contractor = st.text_input("Contractor")

        proposed_budget = st.number_input("Proposed Budget", min_value=0.0, format="%.2f", disabled=(classification != "Proposed Budget"))
        change_order = st.number_input("Change Order", min_value=0.0, format="%.2f", disabled=(classification != "Change Order"))
        revised_budget = proposed_budget + change_order
        status = st.selectbox("Status", ["Proposal Received", "Document Approved", "Sent For signature", "Contract Executed"])
        date_optional = st.checkbox("Specify Date Executed")
        date_executed = st.date_input("Date Executed", disabled=not date_optional)

        submit = st.form_submit_button("✅ Save Entry")

    if submit:
        if not community or not location or not budget_item:
            st.error("Please fill in all required fields.")
            return

        date_value = date_executed.strftime("%Y-%m-%d") if date_optional else None
        try:
            cursor.execute('''
                INSERT INTO land_development (
                    community, location, budget_item, contractor, classification,
                    proposed_budget, change_order, revised_budget, status, date_executed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                community, location, budget_item, contractor, classification,
                proposed_budget, change_order, revised_budget, status, date_value
            ))
            conn.commit()
            st.success("✅ Entry added successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to add entry: {e}")
# --- Inline Edit Form ---
def render_inline_edit_form(row):
    unique_id = row["LD_PK"]
    edit_key = f"edit_mode_{unique_id}"

    if st.session_state.get(edit_key, False):
        with st.form(f"edit_form_{unique_id}"):
            classification = st.selectbox("Classification", ["Proposed Budget", "Change Order"],
                                          index=["Proposed Budget", "Change Order"].index(row["classification"]),
                                          key=f"classification_{unique_id}")

            community = st.text_input("Community", value=row["community"], key=f"community_{unique_id}")
            location = st.text_input("Location", value=row["location"], key=f"location_{unique_id}")
            budget_item = st.text_input("Budget Item", value=row["budget_item"], key=f"budget_item_{unique_id}")
            contractor = st.text_input("Contractor", value=row["contractor"], key=f"contractor_{unique_id}")

            proposed_budget = st.number_input("Proposed Budget", value=safe_currency(row["proposed_budget"]),
                                              format="%.2f", disabled=(classification != "Proposed Budget"),
                                              key=f"proposed_budget_{unique_id}")
            change_order = st.number_input("Change Order", value=safe_currency(row["change_order"]),
                                           format="%.2f", disabled=(classification != "Change Order"),
                                           key=f"change_order_{unique_id}")
            revised_budget = proposed_budget + change_order

            status = st.selectbox("Status", ["Proposal Received", "Document Approved", "Sent For signature", "Contract Executed"],
                                  index=["Proposal Received", "Document Approved", "Sent For signature", "Contract Executed"].index(row["status"]),
                                  key=f"status_{unique_id}")

            date_executed = pd.to_datetime(row["date_executed"]) if row["date_executed"] else None
            date_optional = st.checkbox("Specify Date Executed", value=bool(date_executed), key=f"date_optional_{unique_id}")
            date_input = st.date_input("Date Executed", value=date_executed or pd.to_datetime("today"),
                                       disabled=not date_optional, key=f"date_input_{unique_id}")

            col1, col2 = st.columns(2)
            save = col1.form_submit_button("💾 Save")
            cancel = col2.form_submit_button("❌ Cancel")

        if save:
            if not community or not location or not budget_item:
                st.error("Please fill in all required fields.")
                return

            date_value = date_input.strftime("%Y-%m-%d") if date_optional else None
            try:
                cursor.execute('''
                    UPDATE land_development SET
                        community=?, location=?, budget_item=?, contractor=?, classification=?,
                        proposed_budget=?, change_order=?, revised_budget=?, status=?, date_executed=?
                    WHERE LD_PK=?
                ''', (
                    community, location, budget_item, contractor, classification,
                    proposed_budget, change_order, revised_budget, status, date_value,
                    unique_id
                ))
                conn.commit()
                st.success("✅ Entry updated.")
                st.session_state[edit_key] = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to update entry: {e}")

        elif cancel:
            st.session_state[edit_key] = False
            st.rerun()

    else:
        st.dataframe(pd.DataFrame([row]))
        if st.button("✏️ Edit", key=f"edit_button_{unique_id}"):
            st.session_state[edit_key] = True

# --- Details View ---
def render_details_view():
    st.header("📋 Development Details")
    df = load_data()

    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        col4, col5, col6 = st.columns(3)

        community_filter = col1.selectbox("Community", ["All"] + sorted(df["community"].dropna().unique().tolist()))
        location_filter = col2.selectbox("Location", ["All"] + sorted(df["location"].dropna().unique().tolist()))
        item_filter = col3.selectbox("Budget Item", ["All"] + sorted(df["budget_item"].dropna().unique().tolist()))
        contractor_filter = col4.selectbox("Contractor", ["All"] + sorted(df["contractor"].dropna().unique().tolist()))
        classification_filter = col5.selectbox("Classification", ["All"] + sorted(df["classification"].dropna().unique().tolist()))
        status_filter = col6.selectbox("Status", ["All", "Proposal Received", "Document Approved", "Sent For signature", "Contract Executed"])

    # Apply filters
    if community_filter != "All":
        df = df[df["community"] == community_filter]
    if location_filter != "All":
        df = df[df["location"] == location_filter]
    if item_filter != "All":
        df = df[df["budget_item"] == item_filter]
    if contractor_filter != "All":
        df = df[df["contractor"] == contractor_filter]
    if classification_filter != "All":
        df = df[df["classification"] == classification_filter]
    if status_filter != "All":
        df = df[df["status"] == status_filter]

    if df.empty:
        st.warning("No matching records found.")
        return

    grouped = df.groupby(["community", "location", "budget_item", "contractor"])
    for group_key, group in grouped:
        first_row = group.iloc[0]
        total_proposed = group["proposed_budget"].sum()
        total_change_order = group["change_order"].sum()
        total_revised = total_proposed + total_change_order

        with st.expander(f"📂 {first_row['community']} | {first_row['location']} | {first_row['budget_item']} | {first_row['contractor']}"):
            st.write(f"**Total Proposed:** ${total_proposed:,.2f}")
            st.write(f"**Total Change Order:** ${total_change_order:,.2f}")
            st.write(f"**Total Revised:** ${total_revised:,.2f}")

            for _, row in group.iterrows():
                render_inline_edit_form(row)
# --- Budget Summary View ---
def render_budget_summary():
    st.header("📊 Budget Summary")
    df = load_data()

    if df.empty:
        st.info("No data available.")
        return

    grouped = df.groupby(["community", "contractor"])
    summary_rows = []

    for (community, contractor), group in grouped:
        total_proposed = group["proposed_budget"].sum()
        total_change = group["change_order"].sum()
        total_revised = group["revised_budget"].sum()

        summary_rows.append({
            "Community": community,
            "Contractor": contractor,
            "Total Proposed": total_proposed,
            "Total Change Order": total_change,
            "Total Revised": total_revised,
            "Group": group
        })

    for i, row in enumerate(summary_rows):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
        col1.write(f"**{row['Community']}**")
        col2.write(f"**{row['Contractor']}**")

        if col3.button(f"${row['Total Proposed']:,.2f}", key=f"prop_{i}"):
            st.info("**Proposed Budget Details**")
            st.dataframe(row["Group"][["budget_item", "proposed_budget"]])

        if col4.button(f"${row['Total Change Order']:,.2f}", key=f"chg_{i}"):
            st.info("**Change Order Details**")
            st.dataframe(row["Group"][["budget_item", "change_order"]])

        if col5.button(f"${row['Total Revised']:,.2f}", key=f"rev_{i}"):
            st.info("**Revised Budget Details**")
            st.dataframe(row["Group"][["budget_item", "revised_budget"]])

# --- Pending Contracts View ---
def render_pending_contracts():
    st.header("📌 Pending Contracts")
    df = load_data()
    df = df[df["status"] != "Contract Executed"]

    status_order = {
        "Proposal Received": 0,
        "Document Approved": 1,
        "Sent For signature": 2
    }

    df["status_rank"] = df["status"].map(status_order)
    df = df.sort_values(by="status_rank")

    def get_status_color(status):
        if status == "Proposal Received":
            return "background-color: lightgray; font-weight: bold"
        elif status == "Document Approved":
            return "background: linear-gradient(90deg, yellow 50%, lightgray 50%); font-weight: bold"
        elif status == "Sent For signature":
            return "background-color: yellow; font-weight: bold"
        return ""

    if df.empty:
        st.info("No pending contracts.")
    else:
        display_df = df[["status", "community", "contractor", "budget_item", "proposed_budget", "change_order", "revised_budget"]]
        styled_df = display_df.style.applymap(get_status_color, subset=["status"]).format({
            "proposed_budget": "${:,.2f}",
            "change_order": "${:,.2f}",
            "revised_budget": "${:,.2f}"
        })
        st.dataframe(styled_df)

# --- Preview All View ---
def render_preview_all():
    st.header("📁 Preview All Entries")
    df = load_data()

    if df.empty:
        st.info("No entries found.")
    else:
        st.dataframe(df.style.format({
            "proposed_budget": "${:,.2f}",
            "change_order": "${:,.2f}",
            "revised_budget": "${:,.2f}"
        }))
# --- Batch Entry View ---
def render_batch_entry():
    st.header("📥 Batch Entry")
    st.markdown("Download the Excel template, fill it in, and upload it below:")

    template_df = pd.DataFrame(columns=[
        "community", "location", "budget_item", "contractor", "classification",
        "proposed_budget", "change_order", "status", "date_executed"
    ])

    buffer = io.BytesIO()
    template_df.to_excel(buffer, index=False)
    buffer.seek(0)

    st.download_button(
        label="📄 Download Template",
        data=buffer,
        file_name="land_development_batch_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    uploaded_file = st.file_uploader("Upload filled Excel file", type=["xlsx"])

    def clean_float(value):
        if pd.isnull(value):
            return 0.0
        try:
            return float(str(value).strip().replace("-", "").replace("—", "").replace("N/A", ""))
        except ValueError:
            return 0.0

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)

            required_columns = template_df.columns.tolist()
            if not all(col in df.columns for col in required_columns):
                st.error("❌ Uploaded file is missing required columns.")
                return

            for col in ["proposed_budget", "change_order"]:
                df[col] = df[col].apply(clean_float)
            df["revised_budget"] = df["proposed_budget"] + df["change_order"]

            st.subheader("📋 Preview Uploaded Data")
            st.dataframe(df.style.format({
                "proposed_budget": "${:,.2f}",
                "change_order": "${:,.2f}",
                "revised_budget": "${:,.2f}"
            }))

            confirm, cancel = st.columns([1, 1])
            if confirm.button("✅ Confirm Upload"):
                for _, row in df.iterrows():
                    try:
                        date_value = pd.to_datetime(row["date_executed"]).strftime("%Y-%m-%d") if pd.notnull(row["date_executed"]) else None
                        cursor.execute('''
                            INSERT INTO land_development (
                                community, location, budget_item, contractor, classification,
                                proposed_budget, change_order, revised_budget, status, date_executed
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row["community"], row["location"], row["budget_item"], row["contractor"],
                            row["classification"], row["proposed_budget"], row["change_order"],
                            row["revised_budget"], row["status"], date_value
                        ))
                    except Exception as row_error:
                        st.warning(f"Skipped row due to error: {row_error}")
                conn.commit()
                st.success("✅ Batch records uploaded successfully.")
                st.rerun()

            elif cancel.button("❌ Cancel"):
                st.info("Upload canceled. No data was saved.")

        except Exception as e:
            st.error(f"❌ Error processing file: {e}")

# --- Route Views ---
def render_land_development_ui():
    st.title("🏗️ Land Development")
    view = st.sidebar.radio("Select View", [
        "Budget Summary", "Details", "Pending Contracts", "Preview All", "Add Entry", "Batch Entry"
    ])

    if view == "Budget Summary":
        render_budget_summary()
    elif view == "Details":
        render_details_view()
    elif view == "Pending Contracts":
        render_pending_contracts()
    elif view == "Preview All":
        render_preview_all()
    elif view == "Add Entry":
        render_add_entry()
    elif view == "Batch Entry":
        render_batch_entry()

# --- Run App ---
if __name__ == "__main__":
    render_land_development_ui()
