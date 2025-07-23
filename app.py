import streamlit as st
import pandas as pd
import bcrypt
from datetime import datetime
from docx import Document
import io
from supabase import create_client, Client

# Supabase setup
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Constants
STATUS_OPTIONS = ["Not started", "Initial Review", "Underwriting", "Second Review", "LOI", "PSA", "No Go"]
PROPERTY_TYPES = ["Residential", "Commercial", "Industrial", "Mixed Use"]

# Session state init
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "deal_saved" not in st.session_state:
    st.session_state.deal_saved = False

# Authentication
def check_password(username, password):
    response = supabase.table("users").select("*").eq("user_name", username).execute()
    users = response.data
    if not users:
        return False
    stored_hash = users[0]["password_hash_text"]
    return bcrypt.checkpw(password.encode(), stored_hash.encode())

def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if check_password(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials.")

if not st.session_state.authenticated:
    login()
    st.stop()

# Navigation
st.sidebar.title("📁 Navigation")
view = st.sidebar.selectbox("Choose a view", [
    "Search Properties",
    "Add New Deal",
    "Preview Deals Table",
    "LOI Creation"
])
def get_deal(pk):
    response = supabase.table("deals").select("*").eq("pk", pk).execute()
    return response.data[0] if response.data else None

def upsert_deal(data):
    supabase.table("deals").upsert(data).execute()

def render_status_cell(status):
    color_map = {
        "Not started": "gray", "Initial Review": "blue", "Underwriting": "orange",
        "Second Review": "purple", "LOI": "green", "PSA": "teal", "No Go": "red"
    }
    color = color_map.get(status, "black")
    return f"<span style='color:{color}; font-weight:bold'>{status}</span>"

def paginate_dataframe(df, page_size=10):
    page = st.session_state.get("page", 0)
    total_pages = (len(df) - 1) // page_size + 1
    start = page * page_size
    end = start + page_size
    st.write(f"Page {page + 1} of {total_pages}")
    col1, col2 = st.columns([1, 1])
    if col1.button("⬅️ Prev") and page > 0:
        st.session_state.page = page - 1
        st.rerun()
    if col2.button("➡️ Next") and page < total_pages - 1:
        st.session_state.page = page + 1
        st.rerun()
    return df.iloc[start:end], page

if view == "Search Properties":
    st.header("🔍 Search Properties")
    activity_filter = st.selectbox("Activity", ["Active", "No Go", "All"])
    status_filter = st.selectbox("Status", ["All"] + STATUS_OPTIONS)

    query = supabase.table("deals").select(
        "pk, status, property_name, location, property_type, size, asking_price, proposed_price, link"
    )
    if activity_filter != "All":
        query = query.eq("activity", activity_filter)
    if status_filter != "All":
        query = query.eq("status", status_filter)

    response = query.execute()
    df = pd.DataFrame(response.data)

    if df.empty:
        st.info("No matching records found.")
    else:
        df["_sort"] = df["status"].map(lambda x: STATUS_OPTIONS.index(x) if x in STATUS_OPTIONS else 99)
        df = df.sort_values(by=["_sort", "property_name"]).drop(columns=["_sort"])
        df_page, page = paginate_dataframe(df)

        headers = ["Status", "Property Name", "Location", "Property Type", "Size", "Asking Price", "Proposed Price", "Link", "Edit"]
        for col, header in zip(st.columns([1.2, 1.5, 1.5, 1.2, 1.2, 1.2, 1.2, 0.8, 0.8]), headers):
            col.markdown(f"**{header}**")

        for _, row in df_page.iterrows():
            deal = get_deal(row["pk"])
            link_url = deal.get("link", "")
            c = st.columns([1.2, 1.5, 1.5, 1.2, 1.2, 1.2, 1.2, 0.8, 0.8])
            c[0].markdown(render_status_cell(row["status"]), unsafe_allow_html=True)
            c[1].markdown(f"<strong>{row['property_name']}</strong>", unsafe_allow_html=True)
            c[2].write(row["location"])
            c[3].write(row["property_type"])
            c[4].write(row["size"])
            c[5].write(row["asking_price"] or "TBD")
            c[6].write(row["proposed_price"] or "TBD")
            c[7].markdown(f'<a href="{link_url}" target="_blank">link</a>' if link_url else "TBD", unsafe_allow_html=True)
            if c[8].button("✏️ Edit", key=f"edit-{row['pk']}"):
                st.session_state.edit_pk = row["pk"]

        if "edit_pk" in st.session_state:
            deal = get_deal(st.session_state.edit_pk)
            if deal:
                st.subheader(f"📝 Edit Deal: {deal['pk']}")
                with st.form("edit_form"):
                    status = st.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(deal["status"]))
                    name = st.text_input("Property Name", value=deal["property_name"])
                    location = st.text_input("Location", value=deal["location"])
                    prop_type = st.text_input("Property Type", value=deal["property_type"])
                    size = st.text_input("Size", value=deal["size"])
                    asking = st.text_input("Asking Price", value=deal["asking_price"])
                    proposed = st.text_input("Proposed Price", value=deal["proposed_price"])
                    link = st.text_input("Link", value=deal["link"])
                    receive_dt = deal["receive_dt"]
                    st.markdown(f"**Receive Date:** `{receive_dt}`")
                    activity = "No Go" if status == "No Go" else "Active"

                    colA, colB = st.columns([1, 1])
                    save = colA.form_submit_button("💾 Save Changes")
                    cancel = colB.form_submit_button("❌ Cancel")

                if save:
                    now = datetime.now().isoformat()
                    updated = {
                        "pk": deal["pk"],
                        "status": status,
                        "property_name": name,
                        "location": location,
                        "property_type": prop_type,
                        "size": size,
                        "asking_price": asking,
                        "proposed_price": proposed,
                        "link": link,
                        "receive_dt": receive_dt,
                        "underwriting_dt": deal["underwriting_dt"] or (now if status == "Underwriting" and deal["status"] != "Underwriting" else None),
                        "initial_review_dt": deal["initial_review_dt"] or (now if status == "Initial Review" and deal["status"] != "Initial Review" else None),
                        "loi_dt": deal["loi_dt"] or (now if status == "LOI" and deal["status"] != "LOI" else None),
                        "second_review_dt": deal["second_review_dt"] or (now if status == "Second Review" and deal["status"] != "Second Review" else None),
                        "psa_dt": deal["psa_dt"] or (now if status == "PSA" and deal["status"] != "PSA" else None),
                        "no_go_dt": deal["no_go_dt"] or (now if status == "No Go" and deal["status"] != "No Go" else None),
                        "activity": activity
                    }
                    upsert_deal(updated)
                    st.success("✅ Changes saved.")
                    del st.session_state.edit_pk
                    st.rerun()
                elif cancel:
                    del st.session_state.edit_pk
                    st.info("🛑 Edit canceled.")
                    st.rerun()
# --- Add New Deal ---
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
        receive_dt = datetime.now().isoformat()
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
                data = {
                    "pk": pk,
                    "status": status,
                    "property_name": name,
                    "location": location,
                    "property_type": prop_type,
                    "size": size,
                    "asking_price": asking,
                    "proposed_price": proposed,
                    "link": link,
                    "receive_dt": receive_dt,
                    "underwriting_dt": None,
                    "initial_review_dt": None,
                    "loi_dt": None,
                    "second_review_dt": None,
                    "psa_dt": None,
                    "no_go_dt": None,
                    "activity": activity
                }
                upsert_deal(data)
                st.session_state.deal_saved = True
                st.rerun()

# --- Preview Deals Table ---
elif view == "Preview Deals Table":
    st.header("📊 Full Deal Inventory")
    response = supabase.table("deals").select("*").execute()
    full_df = pd.DataFrame(response.data)
    st.dataframe(full_df)

# --- LOI Creation ---
elif view == "LOI Creation":
    st.header("📄 LOI Creation")
    response = supabase.table("deals").select("pk, property_name").in_("status", ["LOI", "Second Review", "PSA"]).order("pk", desc=True).execute()
    deals = response.data
    deal_options = {f"{d['pk']} - {d['property_name']}": d["pk"] for d in deals}

    if not deal_options:
        st.info("No eligible deals found for LOI creation.")
    else:
        with st.form("loi_form"):
            st.subheader("Fill in LOI Details")
            selected_deal = st.selectbox("Select Deal", list(deal_options.keys()))
            deal_pk = deal_options.get(selected_deal)

            date_of_letter = st.date_input("Date of Letter", value=datetime.today()).strftime("%B %d, %Y")
            seller_name = st.text_input("Seller Name")
            company_name_of_seller = st.text_input("Company Name of Seller")
            broker_name = st.text_input("Broker Name")
            broker_address1 = st.text_input("Broker Address Line 1")
            broker_address2 = st.text_input("Broker Address Line 2")
            property_full_description = st.text_area("Property Name with Address and Description")
            purchase_price = st.text_input("Purchase Price")
            earnest_money_1 = st.text_input("Earnest Money (Initial Deposit)")
            earnest_money_2 = st.text_input("Earnest Money (Second Deposit)")
            feasibility_period = st.text_input("Feasibility Period")
            close_of_escrow = st.text_input("Close of Escrow Period")
            signer_name = st.text_input("Signer Name")
            signer_title = st.text_input("Signer Title")
            sent_at = st.date_input("Date Sent (optional)", value=None)
            received_at = st.date_input("Date Received (optional)", value=None)
            notes = st.text_area("Notes (optional)")

            submit = st.form_submit_button("📝 Generate LOI")
