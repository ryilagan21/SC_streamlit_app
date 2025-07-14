# app.py

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io


# --- Constants ---
STATUS_OPTIONS = ["Not started", "Underwriting", "Initial Review", "LOI", "Second Review", "PSA", "No Go"]
PROPERTY_TYPES = ["BTR", "Commercial", "Industrial", "Mixed-use", "Multi-family", "Single-family", "Town Homes"]

# --- Session State ---
if "deal_saved" not in st.session_state:
    st.session_state.deal_saved = False

# --- Database Setup ---
conn = sqlite3.connect("deals.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS deals (
    pk TEXT PRIMARY KEY,
    status TEXT,
    property_name TEXT,
    location TEXT,
    property_type TEXT,
    size TEXT,
    asking_price TEXT,
    proposed_price TEXT,
    link TEXT,
    receive_dt TEXT,
    underwriting_dt TEXT,
    initial_review_dt TEXT,
    loi_dt TEXT,
    second_review_dt TEXT,
    psa_dt TEXT,
    no_go_dt TEXT,
    activity TEXT DEFAULT 'Active'
)
''')
conn.commit()

# --- Helper Functions ---
def generate_new_pk():
    year = datetime.now().strftime("%Y")
    cursor.execute("SELECT pk FROM deals WHERE pk LIKE ? ORDER BY pk DESC LIMIT 1", (f"{year}-%",))
    last_pk = cursor.fetchone()
    new_num = int(last_pk[0].split("-")[1]) + 1 if last_pk else 1
    return f"{year}-{new_num:04d}"

def upsert_deal(data):
    cursor.execute("SELECT pk FROM deals WHERE pk = ?", (data[0],))
    if cursor.fetchone():
        cursor.execute("""
            UPDATE deals SET
            status=?, property_name=?, location=?, property_type=?, size=?,
            asking_price=?, proposed_price=?, link=?,
            receive_dt=?, underwriting_dt=?, initial_review_dt=?, loi_dt=?,
            second_review_dt=?, psa_dt=?, no_go_dt=?, activity=?
            WHERE pk=?
        """, data[1:] + (data[0],))
    else:
        cursor.execute("INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data)
    conn.commit()

def get_deal(pk):
    cursor.execute("SELECT * FROM deals WHERE pk = ?", (pk,))
    return cursor.fetchone()

def is_duplicate_deal(name, location, prop_type, size):
    cursor.execute("""
        SELECT 1 FROM deals
        WHERE property_name = ? AND location = ? AND property_type = ? AND size = ?
    """, (name, location, prop_type, size))
    return cursor.fetchone() is not None

def paginate_dataframe(df, items_per_page=5, label="Page"):
    total_items = len(df)
    if total_items == 0:
        st.info("No results found.")
        return df.iloc[0:0], 0
    total_pages = (total_items - 1) // items_per_page + 1
    col1, col2 = st.columns([8, 2])
    with col2:
        page = st.number_input(label, min_value=1, max_value=total_pages, value=1, step=1, label_visibility="collapsed")
    start_idx = (page - 1) * items_per_page
    return df.iloc[start_idx:start_idx + items_per_page], page

def sync_activity_column():
    cursor.execute("SELECT pk, status FROM deals")
    for pk, status in cursor.fetchall():
        new_activity = "No Go" if status == "No Go" else "Active"
        cursor.execute("UPDATE deals SET activity = ? WHERE pk = ?", (new_activity, pk))
    conn.commit()

sync_activity_column()

def render_status_cell(status):
    color_map = {
        "Not started": ("#B0B0B0", 100),
        "Underwriting": ("#FFF176", 20),
        "Initial Review": ("#FFD54F", 40),
        "LOI": ("#AED581", 60),
        "Second Review": ("#66BB6A", 80),
        "PSA": ("#66BB6A", 100),
    }

    color, fill = color_map.get(status, ("#FFFFFF", 0))
    gray_fill = 100 - fill

    return f"""
    <div style="
        width: 100%;
        height: 24px;
        border: 1px solid #ccc;
        background: linear-gradient(to right, {color} {fill}%, #E0E0E0 {fill}%);
        text-align: center;
        line-height: 24px;
        font-size: 12px;
        font-weight: 500;
    ">
        <strong>{status}</strong>
    </div>
    """



# --- Streamlit UI ---
st.set_page_config(page_title="Land Acquisition Tracker", layout="wide")
st.sidebar.image("logo.png", width=150)
st.sidebar.markdown("## Scott Communities")

main_menu = st.sidebar.selectbox("Main Menu", ["Land Acquisition", "Land Development"])

if main_menu == "Land Acquisition":
    st.title("📍 Land Acquisition Tracker")
    view = st.sidebar.radio("Select View", ["Search Properties", "Add New Deal", "Preview Deals Table","LOI Creation"])


    if view == "Search Properties":
        st.header("🔍 Search Properties")
        activity_filter = st.selectbox("Activity", ["Active", "No Go", "All"])
        status_filter = st.selectbox("Status", ["All"] + STATUS_OPTIONS)

        query = "SELECT pk, status, property_name, location, property_type, size, asking_price, proposed_price FROM deals WHERE 1=1"
        filters = []
        if activity_filter != "All":
            query += " AND activity = ?"
            filters.append(activity_filter)
        if status_filter != "All":
            query += " AND status = ?"
            filters.append(status_filter)

        results = cursor.execute(query, filters).fetchall()
        df = pd.DataFrame(results, columns=["PK", "Status", "Property Name", "Location", "Property Type", "Size", "Asking Price", "Proposed Price"])
        df["_sort"] = df["Status"].map(lambda x: STATUS_OPTIONS.index(x) if x in STATUS_OPTIONS else 99)
        df = df.sort_values(by=["_sort", "Property Name"]).drop(columns=["_sort"])
        df_page, page = paginate_dataframe(df)

        headers = ["Status", "Property Name", "Location", "Property Type", "Size", "Asking Price", "Proposed Price", "Link", "Edit"]
        st.columns([1.2, 1.5, 1.5, 1.2, 1.2, 1.2, 1.2, 0.8, 0.8])
        for col, header in zip(st.columns([1.2, 1.5, 1.5, 1.2, 1.2, 1.2, 1.2, 0.8, 0.8]), headers):
            col.markdown(f"**{header}**")

        for _, row in df_page.iterrows():
            deal = get_deal(row["PK"])
            link_url = deal[8] if deal else ""
            c = st.columns([1.2, 1.5, 1.5, 1.2, 1.2, 1.2, 1.2, 0.8, 0.8])
            c[0].markdown(render_status_cell(row["Status"]), unsafe_allow_html=True)
            c[1].markdown(f"<strong>{row['Property Name']}</strong>", unsafe_allow_html=True)
            c[2].write(row["Location"])
            c[3].write(row["Property Type"])
            c[4].write(row["Size"])
            c[5].write(row["Asking Price"] or "TBD")
            c[6].write(row["Proposed Price"] or "TBD")
            c[7].markdown(f'<a href="{link_url}" target="_blank">link</a>' if link_url else "TBD", unsafe_allow_html=True)
            if c[8].button("✏️ Edit", key=f"edit-{row['PK']}"):
                st.session_state.edit_pk = row["PK"]

        if "edit_pk" in st.session_state:
            deal = get_deal(st.session_state.edit_pk)
            if deal:
                st.subheader(f"📝 Edit Deal: {deal[0]}")
                with st.form("edit_form"):
                    status = st.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(deal[1]))
                    name = st.text_input("Property Name", value=deal[2])
                    location = st.text_input("Location", value=deal[3])
                    prop_type = st.text_input("Property Type", value=deal[4])
                    size = st.text_input("Size", value=deal[5])
                    asking = st.text_input("Asking Price", value=deal[6])
                    proposed = st.text_input("Proposed Price", value=deal[7])
                    link = st.text_input("Link", value=deal[8])
                    receive_dt = deal[9] or ""
                    st.markdown(f"**Receive Date:** `{receive_dt}`")
                    activity = "No Go" if status == "No Go" else "Active"

                    colA, colB = st.columns([1, 1])
                    save = colA.form_submit_button("💾 Save Changes")
                    cancel = colB.form_submit_button("❌ Cancel")

                if save:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    updated = (
                        deal[0], status, name, location, prop_type, size,
                        asking, proposed, link,
                        receive_dt,
                        deal[10] or (now if status == "Underwriting" and deal[1] != "Underwriting" else None),
                        deal[11] or (now if status == "Initial Review" and deal[1] != "Initial Review" else None),
                        deal[12] or (now if status == "LOI" and deal[1] != "LOI" else None),
                        deal[13] or (now if status == "Second Review" and deal[1] != "Second Review" else None),
                        deal[14] or (now if status == "PSA" and deal[1] != "PSA" else None),
                        deal[15] or (now if status == "No Go" and deal[1] != "No Go" else None),
                        activity
                    )
                    upsert_deal(updated)
                    st.success("✅ Changes saved.")
                    st.session_state.edit_pk = None
                    st.stop()
                elif cancel:
                    st.session_state.edit_pk = None
                    st.info("🛑 Edit canceled.")
                    st.stop()

    elif view == "Add New Deal":
        st.header("➕ Add New Deal")
        if st.session_state.deal_saved:
            st.success("🎉 Deal added successfully.")
            st.session_state.deal_saved = False
            st.stop()

        with st.form("add_deal_form"):
            pk = generate_new_pk()
            st.markdown(f"**New Deal ID:** `{pk}`")
            name = st.text_input("Property Name")
            location = st.text_input("Location")
            prop_type = st.selectbox("Property Type", PROPERTY_TYPES)
            size = st.text_input("Size")
            asking = st.text_input("Asking Price")
            proposed = st.text_input("Proposed Price")
            link = st.text_input("Link to File")
            receive_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.markdown(f"**Receive Date:** `{receive_dt}`")
            status = "Not started"
            activity = "Active"

            submit = st.form_submit_button("✅ Save Deal")
            if submit:
                if not name or not location:
                    st.error("❗ Property Name and Location are required.")
                elif is_duplicate_deal(name, location, prop_type, size):
                    st.warning("⚠️ A deal with the same Property Name, Location, Property Type, and Size already exists.")
                else:
                    data = (
                        pk, status, name, location, prop_type, size,
                        asking, proposed, link,
                        receive_dt, None, None, None, None, None, None,
                        activity
                    )
                    upsert_deal(data)
                    st.session_state.deal_saved = True
                    st.rerun()

    elif view == "Preview Deals Table":
        st.header("📊 Full Deal Inventory")
        full_df = pd.read_sql_query("SELECT * FROM deals", conn)
        st.dataframe(full_df)
    elif view == "LOI Creation":
            st.header("📄 LOI Creation")

    # Connect to database
    conn = sqlite3.connect("deals.db", check_same_thread=False)
    cursor = conn.cursor()

    # Create LOI table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lois (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_pk TEXT,
            created_at TEXT,
            sent_at TEXT,
            received_at TEXT,
            file_path TEXT,
            notes TEXT,
            FOREIGN KEY (deal_pk) REFERENCES deals(pk)
        )
    ''')
    conn.commit()

    # Fetch deals
    cursor.execute("""
    SELECT pk, property_name 
    FROM deals 
    WHERE status IN ('LOI', 'Second Review', 'PSA') 
    ORDER BY pk DESC""")
    
    deals = cursor.fetchall()
    deal_options = {f"{pk} - {name}": pk for pk, name in deals}

    with st.form("loi_form"):
        st.subheader("Fill in LOI Details")

        selected_deal = st.selectbox("Select Deal", list(deal_options.keys()))
        deal_pk = deal_options[selected_deal]

        date_of_letter = st.date_input("Date of Letter", value=datetime.today()).strftime("%B %d, %Y")
        seller_name = st.text_input("Seller Name")
        company_name_of_seller = st.text_input("Company Name of Seller")
        broker_name = st.text_input("Broker Name")
        broker_address1 = st.text_input("Broker Address Line 1")
        broker_address2 = st.text_input("Broker Address Line 2")
        property_full_description = st.text_area("Property Name with Address and Description")
        col1, col2 = st.columns([1, 4])
        with col1:
            purchase_price = st.text_input("Purchase Price")
        with col2:
            st.markdown('<div style="padding-top: 2.2em; color:red;">*must include commas and decimal point</div>', unsafe_allow_html=True)

        col3, col4 = st.columns([1, 4])
        with col3:
            earnest_money_1 = st.text_input("Earnest Money (Initial Deposit)")
        with col4:
            st.markdown('<div style="padding-top: 2.2em; color:red;">*must include commas and decimal point</div>', unsafe_allow_html=True)

        col5, col6 = st.columns([1, 4])
        with col5:
            earnest_money_2 = st.text_input("Earnest Money (Second Deposit)")
        with col6:
            st.markdown('<div style="padding-top: 2.2em; color:red;">*must include commas and decimal point</div>', unsafe_allow_html=True)


        col7, col8 = st.columns([2, 3])
        with col7:
            feasibility_period = st.text_input("Feasibility Period")
        with col8:
            st.markdown('<div style="padding-top: 2.2em; color:red;">Follow this format: one hundred twenty (120) days</div>', unsafe_allow_html=True)

        col9, col10 = st.columns([2, 3])
        with col9:
            close_of_escrow = st.text_input("Close of Escrow Period")
        with col10:
            st.markdown('<div style="padding-top: 2.2em; color:red;">Follow this format: one hundred twenty (120) days</div>', unsafe_allow_html=True)

        signer_name = st.text_input("Signer Name")
        signer_title = st.text_input("Signer Title")
        sent_at = st.date_input("Date Sent (optional)", value=None)
        received_at = st.date_input("Date Received (optional)", value=None)
        notes = st.text_area("Notes (optional)")

        submit = st.form_submit_button("📝 Generate LOI")

    if submit:
        from docx import Document
        import os
        from datetime import datetime

        def replace_placeholder_in_paragraph(paragraph, replacements):
            full_text = ''.join(run.text for run in paragraph.runs)
            for old, new in replacements.items():
                if old in full_text:
                    full_text = full_text.replace(old, new)
            for run in paragraph.runs:
                run.text = ''
            if paragraph.runs:
                paragraph.runs[0].text = full_text
            else:
                paragraph.add_run(full_text)

        def replace_placeholders(doc, replacements):
            for paragraph in doc.paragraphs:
                replace_placeholder_in_paragraph(paragraph, replacements)

            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            replace_placeholder_in_paragraph(paragraph, replacements)

            for section in doc.sections:
                for paragraph in section.header.paragraphs:
                    replace_placeholder_in_paragraph(paragraph, replacements)
                for paragraph in section.footer.paragraphs:
                    replace_placeholder_in_paragraph(paragraph, replacements)

        # Load the template
        template_path = "LOI_Template_Do_Not_Remove.docx"
        doc = Document(template_path)

        # Define replacements
        replacements = {
            "{{DATE_OF_LETTER}}": date_of_letter,
            "{{SELLER_NAME}}": seller_name,
            "{{COMPANY_NAME_OF_SELLER}}": company_name_of_seller,
            "{{BROKER_NAME}}": broker_name,
            "{{BROKER_ADDRESS_LINE_1}}": broker_address1,
            "{{BROKER_ADDRESS_LINE_2}}": broker_address2,
            "{{SELLER_NAME_WITH_PREFIX}}": f"Mr./Ms. {seller_name}",
            "{{PROPERTY NAME_WITH_ADDRESS_AND_DESCRIPTION_(See _attachment)}}": property_full_description,
            "{{PURCHASE_PRICE}}": purchase_price,
            "{{EARNEST_MONEY_1}}": earnest_money_1,
            "{{EARNEST_MONEY_2}}": earnest_money_2,
            "{{FEASIBILITY_PERIOD}}": feasibility_period,
            "{{CLOSE_OF_ESCROW}}": close_of_escrow,
            "{{SIGNER_NAME}}": signer_name,
            "{{SIGNER_TITLE}}": signer_title
        }

        # Replace placeholders
        replace_placeholders(doc, replacements)

import io

        #Fetch property name and type for filename
        cursor.execute("SELECT property_name, property_type FROM deals WHERE pk = ?", (deal_pk,))
        property_name, property_type = cursor.fetchone()

        def sanitize(text):
            return text.strip().replace(" ", "_").replace("/", "-")

        safe_name = sanitize(property_name)
        safe_type = sanitize(property_type)
        filename = f"LOI_{safe_name}_{safe_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

        # Save the document to memory
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)

        # Log in database (file_path can be left blank or set to filename only)
        cursor.execute('''
            INSERT INTO lois (deal_pk, created_at, sent_at, received_at, file_path, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            deal_pk,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            sent_at.strftime("%Y-%m-%d") if sent_at else None,
            received_at.strftime("%Y-%m-%d") if received_at else None,
            filename,  # or use "" if you prefer to leave it blank
            notes
        ))
        conn.commit()

        
        # Show download button
        st.success("✅ LOI generated.")
        st.download_button("📥 Download LOI", doc_io, file_name=filename)















elif main_menu == "Land Development":
    st.title("🏗️ Land Development Tracker")
# You can add Land Development logic here later    

