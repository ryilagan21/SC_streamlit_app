# land_development.py (Part 1)

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        revised_budget = st.number_input("Revised Budget", min_value=0.0, format="%.2f")
        status = st.selectbox("Status", ["Proposal Received", "Document Approved", "Sent For signature", "Contract executed"])
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
        except Exception as e:
            st.error(f"❌ Failed to add entry: {e}")
# land_development.py (Part 2)

# --- Safe Currency Formatter ---
def safe_currency(value):
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return "—"

# --- Budget Summary View ---
def render_budget_summary():
    st.header("📊 Budget Summary")
    df = pd.read_sql_query("SELECT * FROM land_development", conn)

    if df.empty:
        st.info("No data available.")
        return

    for col in ["proposed_budget", "change_order", "revised_budget"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    summary = df.groupby(["community", "contractor"]).agg({
        "proposed_budget": "sum",
        "change_order": "sum",
        "revised_budget": "sum"
    }).reset_index()

    summary.columns = ["Community", "Contractor", "Total Proposed", "Total Change Order", "Total Revised"]
    st.dataframe(summary.style.format({
        "Total Proposed": "${:,.2f}",
        "Total Change Order": "${:,.2f}",
        "Total Revised": "${:,.2f}"
    }))

# --- Edit Entry Form ---
def render_edit_form(row):
    st.write("📝 Edit Entry")

    classification = st.selectbox("Classification", ["Proposed Budget", "Change Order"], index=["Proposed Budget", "Change Order"].index(row["classification"]))

    with st.form(f"edit_form_{row['id']}"):
        community = st.text_input("Community", value=row["community"])
        location = st.text_input("Location", value=row["location"])
        budget_item = st.text_input("Budget Item", value=row["budget_item"])
        contractor = st.text_input("Contractor", value=row["contractor"])

        proposed_budget = st.number_input("Proposed Budget", value=row["proposed_budget"], format="%.2f", disabled=(classification != "Proposed Budget"))
        change_order = st.number_input("Change Order", value=row["change_order"], format="%.2f", disabled=(classification != "Change Order"))
        revised_budget = st.number_input("Revised Budget", value=row["revised_budget"], format="%.2f")

        status = st.selectbox("Status", ["Proposal Received", "Document Approved", "Sent For signature", "Contract executed"], index=["Proposal Received", "Document Approved", "Sent For signature", "Contract executed"].index(row["status"]))

        date_executed = pd.to_datetime(row["date_executed"]) if row["date_executed"] else None
        date_optional = st.checkbox("Specify Date Executed", value=bool(date_executed))
        date_input = st.date_input("Date Executed", value=date_executed or pd.to_datetime("today"), disabled=not date_optional)

        save = st.form_submit_button("💾 Save Changes")

    if save:
        date_value = date_input.strftime("%Y-%m-%d") if date_optional else None
        cursor.execute('''
            UPDATE land_development SET
                community=?, location=?, budget_item=?, contractor=?, classification=?,
                proposed_budget=?, change_order=?, revised_budget=?, status=?, date_executed=?
            WHERE id=?
        ''', (
            community, location, budget_item, contractor, classification,
            proposed_budget, change_order, revised_budget, status, date_value,
            row["id"]
        ))
        conn.commit()
        st.success("✅ Entry updated.")

# --- Details View ---
def render_details_view():
    st.header("📋 Development Details")
    df = pd.read_sql_query("SELECT * FROM land_development", conn)

    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        col4, col5, col6 = st.columns(3)

        community_filter = col1.selectbox("Community", ["All"] + sorted(df["community"].dropna().unique().tolist()))
        location_filter = col2.selectbox("Location", ["All"] + sorted(df["location"].dropna().unique().tolist()))
        item_filter = col3.selectbox("Budget Item", ["All"] + sorted(df["budget_item"].dropna().unique().tolist()))
        contractor_filter = col4.selectbox("Contractor", ["All"] + sorted(df["contractor"].dropna().unique().tolist()))
        classification_filter = col5.selectbox("Classification", ["All"] + sorted(df["classification"].dropna().unique().tolist()))
        status_filter = col6.selectbox("Status", ["All", "Proposal Received", "Document Approved", "Sent For signature", "Contract executed"])

    def matches_filters(group):
        if community_filter != "All" and community_filter not in group["community"].values: return False
        if location_filter != "All" and location_filter not in group["location"].values: return False
        if item_filter != "All" and item_filter not in group["budget_item"].values: return False
        if contractor_filter != "All" and contractor_filter not in group["contractor"].values: return False
        if classification_filter != "All" and classification_filter not in group["classification"].values: return False
        if status_filter != "All" and status_filter not in group["status"].values: return False
        return True
    grouped = df.groupby(["community", "location", "budget_item", "contractor"])
    filtered_groups = [group for _, group in grouped if matches_filters(group)]

    if not filtered_groups:
        st.warning("No matching records found.")
        return

    items_per_page = 5
    total_pages = (len(filtered_groups) - 1) // items_per_page + 1
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)

    start = (page - 1) * items_per_page
    end = start + items_per_page
    paginated_groups = filtered_groups[start:end]

    for group in paginated_groups:
        first_row = group.iloc[0]
        with st.container():
            cols = st.columns([1.5, 1.5, 1.5, 1.5, 1, 1, 1, 1])
            cols[0].write(first_row["community"])
            cols[1].write(first_row["location"])
            cols[2].write(first_row["budget_item"])
            cols[3].write(first_row["contractor"])
            cols[4].write(safe_currency(first_row["proposed_budget"]))
            cols[5].write(safe_currency(first_row["change_order"]))
            cols[6].write(safe_currency(first_row["revised_budget"]))
            cols[7].markdown("➕", unsafe_allow_html=True)

            with st.expander("View Versions"):
                for _, row in group.iterrows():
                    st.dataframe(pd.DataFrame([row]))
                    render_edit_form(row)
# land_development.py (Part 3)

# --- Preview All View ---
def render_preview_all():
    st.header("📁 Preview All Entries")
    df = pd.read_sql_query("SELECT * FROM land_development", conn)
    if df.empty:
        st.info("No entries found.")
    else:
        st.dataframe(df)

# --- Batch Entry View ---
def render_batch_entry():
    st.header("📥 Batch Entry")
    st.markdown("Download the Excel template, fill it in, and upload it below:")

    template_df = pd.DataFrame(columns=[
        "community", "location", "budget_item", "contractor", "classification",
        "proposed_budget", "change_order", "revised_budget", "status", "date_executed"
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

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)

            required_columns = template_df.columns.tolist()
            if not all(col in df.columns for col in required_columns):
                st.error("❌ Uploaded file is missing required columns.")
                return

            for _, row in df.iterrows():
                try:
                    proposed_budget = float(row["proposed_budget"]) if pd.notnull(row["proposed_budget"]) else 0.0
                    change_order = float(row["change_order"]) if pd.notnull(row["change_order"]) else 0.0
                    revised_budget = float(row["revised_budget"]) if pd.notnull(row["revised_budget"]) else 0.0
                    date_value = pd.to_datetime(row["date_executed"]).strftime("%Y-%m-%d") if pd.notnull(row["date_executed"]) else None

                    cursor.execute('''
                        INSERT INTO land_development (
                            community, location, budget_item, contractor, classification,
                            proposed_budget, change_order, revised_budget, status, date_executed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row["community"], row["location"], row["budget_item"], row["contractor"],
                        row["classification"], proposed_budget, change_order,
                        revised_budget, row["status"], date_value
                    ))
                except Exception as row_error:
                    st.warning(f"Skipped row due to error: {row_error}")

            conn.commit()
            st.success("✅ Batch records uploaded successfully.")
        except Exception as e:
            st.error(f"❌ Error processing file: {e}")

# --- Route Views ---
def render_land_development_ui():
    st.title("🏗️ Land Development")
    view = st.sidebar.radio("Select View", [
        "Budget Summary", "Details", "Preview All", "Add Entry", "Batch Entry"
    ])

    if view == "Budget Summary":
        render_budget_summary()
    elif view == "Details":
        render_details_view()
    elif view == "Preview All":
        render_preview_all()
    elif view == "Add Entry":
        render_add_entry()
    elif view == "Batch Entry":
        render_batch_entry()

