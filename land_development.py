import streamlit as st
import sqlite3
import pandas as pd

# --- Database Connection ---
conn = sqlite3.connect("deals.db", check_same_thread=False)
cursor = conn.cursor()

# --- Ensure Table Exists ---
cursor.execute('''
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

# --- Add Entry View ---
def render_add_entry():
    st.header("➕ Add Land Development Entry")

    with st.form("add_entry_form"):
        community = st.text_input("Community")
        location = st.text_input("Location")
        budget_item = st.text_input("Budget Item")
        contractor = st.text_input("Contractor")

        classification = st.selectbox("Classification", ["Proposed Budget", "Change Order"])

        # Conditional input fields
        if classification == "Proposed Budget":
            proposed_budget = st.number_input("Proposed Budget", min_value=0.0, format="%.2f")
            change_order = 0.0
            st.number_input("Change Order", value=0.0, disabled=True, format="%.2f")
        else:
            proposed_budget = 0.0
            st.number_input("Proposed Budget", value=0.0, disabled=True, format="%.2f")
            change_order = st.number_input("Change Order", min_value=0.0, format="%.2f")

        revised_budget = st.number_input("Revised Budget", min_value=0.0, format="%.2f")
        status = st.selectbox("Status", ["Proposal Received", "Document Approved", "Sent For signature", "Contract executed"])
        date_optional = st.checkbox("Specify Date Executed")
        date_executed = st.date_input("Date Executed", disabled=not date_optional)

        submit = st.form_submit_button("✅ Save Entry")

    if submit:
        date_value = date_executed.strftime("%Y-%m-%d") if date_optional else None

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

# --- Budget Summary View ---
def render_budget_summary():
    st.header("📊 Budget Summary")

    df = pd.read_sql_query("SELECT * FROM land_development", conn)

    if df.empty:
        st.info("No data available.")
        return
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
    with st.form(f"edit_form_{row['id']}"):
        st.write("📝 Edit Entry")
        community = st.text_input("Community", value=row["community"])
        location = st.text_input("Location", value=row["location"])
        budget_item = st.text_input("Budget Item", value=row["budget_item"])
        contractor = st.text_input("Contractor", value=row["contractor"])

        classification = st.selectbox("Classification", ["Proposed Budget", "Change Order"],
                                      index=["Proposed Budget", "Change Order"].index(row["classification"]))

        if classification == "Proposed Budget":
            proposed_budget = st.number_input("Proposed Budget", value=row["proposed_budget"], format="%.2f")
            change_order = 0.0
            st.number_input("Change Order", value=0.0, disabled=True, format="%.2f")
        else:
            proposed_budget = 0.0
            st.number_input("Proposed Budget", value=0.0, disabled=True, format="%.2f")
            change_order = st.number_input("Change Order", value=row["change_order"], format="%.2f")

        revised_budget = st.number_input("Revised Budget", value=row["revised_budget"], format="%.2f")
        status = st.selectbox("Status", ["Proposal Received", "Document Approved", "Sent For signature", "Contract executed"],
                              index=["Proposal Received", "Document Approved", "Sent For signature", "Contract executed"].index(row["status"]))

        date_executed = st.date_input("Date Executed", value=pd.to_datetime(row["date_executed"]) if row["date_executed"] else pd.to_datetime("today"))

        save = st.form_submit_button("💾 Save Changes")

    if save:
        cursor.execute('''
            UPDATE land_development SET
                community=?, location=?, budget_item=?, contractor=?, classification=?,
                proposed_budget=?, change_order=?, revised_budget=?, status=?, date_executed=?
            WHERE id=?
        ''', (
            community, location, budget_item, contractor, classification,
            proposed_budget, change_order, revised_budget, status, date_executed.strftime("%Y-%m-%d"),
            row["id"]
        ))
        conn.commit()
        st.success("✅ Entry updated.")

# --- Details View ---
def render_details_view():
    st.header("📋 Development Details")

    df = pd.read_sql_query("SELECT * FROM land_development", conn)

    # --- Filters ---
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
            cols[4].write(f"${first_row['proposed_budget']:,.2f}")
            cols[5].write(f"${first_row['change_order']:,.2f}")
            cols[6].write(f"${first_row['revised_budget']:,.2f}")
            cols[7].markdown("➕", unsafe_allow_html=True)

            with st.expander("View Versions"):
                st.write("### Versions")
                for _, row in group.iterrows():
                    st.dataframe(pd.DataFrame([row]))
                    render_edit_form(row)

# --- Preview All View ---
def render_preview_all():
    st.header("📁 Preview All Entries")

    df = pd.read_sql_query("SELECT * FROM land_development", conn)

    if df.empty:
        st.info("No entries found.")
    else:
        st.dataframe(df)

# --- Route Views ---
def render_land_development_ui():
    st.title("🏗️ Land Development")
    view = st.sidebar.radio("Select View", ["Budget Summary", "Details", "Preview All", "Add Entry"])

    if view == "Budget Summary":
        render_budget_summary()
    elif view == "Details":
        render_details_view()
    elif view == "Preview All":
        render_preview_all()
    elif view == "Add Entry":
        render_add_entry()
