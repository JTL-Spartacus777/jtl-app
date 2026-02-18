import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time

# MUST BE THE FIRST ST COMMAND
st.set_page_config(
    page_title="Kingshot Vikings Tool",
    page_icon="⚔️",
    layout="wide"
)

# --- ENHANCED MOBILE DARK MODE CSS ---
hide_elements = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    [data-testid="stDecoration"] {display: none;}
    .stAppViewFooter {display: none !important;}

    /* --- MOBILE TAB STYLING --- */
    /* Container for the tabs */
    [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent !important;
    }

    /* Individual Tab Buttons */
    [data-baseweb="tab"] {
        border: 1px solid #4B5563 !important; /* Dark grey border */
        border-radius: 8px !important;
        padding: 10px 15px !important;
        background-color: #1F2937 !important; /* Deep grey background */
        color: #F3F4F6 !important; /* Off-white text */
        font-weight: 600 !important;
        min-width: 100px;
    }

    /* Active (Selected) Tab */
    [data-baseweb="tab"][aria-selected="true"] {
        background-color: #3B82F6 !important; /* Bright Blue to show it's active */
        border-color: #60A5FA !important;
        color: white !important;
    }

    /* Remove the annoying underline Streamlit adds */
    [data-baseweb="tab-highlight"] {
        display: none !important;
    }
    
    /* Make table text readable in dark mode */
    .stTable, .stDataFrame {
        border: 1px solid #4B5563;
    }
    </style>
    """
st.markdown(hide_elements, unsafe_allow_html=True)

# --- CONFIG & CONNECTION (Keep your existing secrets/creds logic) ---
GLOBAL_PASSWORD = st.secrets["general"]["password"]
ADMIN_PASSWORD = st.secrets["general"]["admin_password"]

def get_client():
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=5)
def fetch_data(sheet_name):
    client = get_client()
    sheet = client.open("Kingshot_Data").worksheet(sheet_name)
    return sheet.get_all_records()

# --- AUTHENTICATION ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    pw = st.text_input("Enter Alliance Password", type="password")
    if st.button("Login"):
        if pw == GLOBAL_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.stop()

# --- MAIN APP ---
st.title("⚔️ Kingshot Vikings Tool")

try:
    roster_data = fetch_data("Roster")
    orders_data = fetch_data("Orders")
except:
    st.error("Connection busy. Refreshing...")
    st.stop()

# --- NEW TAB STRUCTURE FOR MOBILE ---
# We use 3 tabs so everything is on the main screen
tab_reg, tab_roster, tab_orders = st.tabs(["📝 REGISTER", "👥 ROSTER", "📜 SWAP ORDERS"])

with tab_reg:
    st.subheader("Add or Update Your Info")
    user = st.text_input("In-Game Username")
    status = st.radio("Status", ["Online", "Offline"], horizontal=True)
    marches = st.slider("Marches you are sending", 4, 6, 5)
    inf_cav = st.number_input("Infantry + Cavalry Count", min_value=0, value=0)
    
    if st.button("Submit My Entry", use_container_width=True): # Makes button wide on mobile
        if user:
            with st.spinner("Saving..."):
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Roster")
                existing_idx = next((i for i, item in enumerate(roster_data) if item["Username"] == user), None)
                if existing_idx is not None:
                    sheet.delete_rows(existing_idx + 2)
                sheet.append_row([user, status, marches, inf_cav])
                st.cache_data.clear()
                st.success(f"Saved {user}!")
                time.sleep(1)
                st.rerun()
    
    st.markdown("---")
    with st.expander("❌ Need to remove your entry?"):
        del_user = st.text_input("Confirm Username to Delete")
        if st.button("Delete My Info", use_container_width=True):
            client = get_client()
            sheet = client.open("Kingshot_Data").worksheet("Roster")
            existing_idx = next((i for i, item in enumerate(roster_data) if item["Username"] == del_user), None)
            if existing_idx is not None:
                sheet.delete_rows(existing_idx + 2)
                st.cache_data.clear()
                st.success("Deleted.")
                time.sleep(1)
                st.rerun()

with tab_roster:
    col_a, col_b = st.columns([3, 1])
    col_a.subheader(f"Total Players: {len(roster_data)}")
    if col_b.button("🔄 Refresh", key="refresh_roster"):
        st.cache_data.clear()
        st.rerun()
        
    if roster_data:
        st.dataframe(pd.DataFrame(roster_data).sort_values(by="Inf_Cav", ascending=False), use_container_width=True)
    else:
        st.info("No one has signed up yet.")

with tab_orders:
    col_c, col_d = st.columns([3, 1])
    col_c.subheader("Current Swap Orders")
    if col_d.button("🔄 Refresh", key="refresh_orders"):
        st.cache_data.clear()
        st.rerun()

    if orders_data:
        my_name = st.text_input("🔍 Filter by your name (optional)")
        df_orders = pd.DataFrame(orders_data).sort_values(by="From")
        
        if my_name:
            df_orders = df_orders[df_orders['From'].str.contains(my_name, case=False)]
        
        st.dataframe(df_orders, use_container_width=True)
    else:
        st.warning("Orders not yet generated.")

# --- ADMIN SECTION ---
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_pw = st.text_input("Admin Password", type="password")
    
    if st.button("Generate & Publish Orders"):
        if admin_pw == ADMIN_PASSWORD:
            with st.spinner("Calculating Optimized Swaps..."):
                if len(roster_data) < 2:
                    st.error("Need more players!")
                else:
                    players = []
                    for p in roster_data:
                        players.append({
                            "Username": p["Username"],
                            "Status": p["Status"],
                            "Sends": int(p["Marches_Available"]),
                            "Inf_Cav": int(p.get("Inf_Cav", 0)),
                            "Receiving_Count": 0,
                            "History": []
                        })
                    
                    marches_to_assign = []
                    for p in players:
                        for _ in range(p["Sends"]):
                            marches_to_assign.append(p)
                    
                    random.shuffle(marches_to_assign)
                    marches_to_assign.sort(key=lambda x: x['Status'] == 'Online', reverse=True)

                    final_orders = []

                    def find_best_target(sender, target_pool, max_cap, prioritize_strength=False):
                        eligible = [
                            t for t in target_pool 
                            if t['Username'] != sender['Username'] 
                            and t['Receiving_Count'] < max_cap 
                            and t['Username'] not in sender['History']
                        ]
                        if not eligible: return None
                        
                        if prioritize_strength:
                            # Sort by Infantry+Cavalry (High to Low) then by current count (Low to High)
                            eligible.sort(key=lambda x: (-x['Inf_Cav'], x['Receiving_Count']))
                        else:
                            # Standard sort: just balance the load evenly
                            eligible.sort(key=lambda x: x['Receiving_Count'])
                        
                        return eligible[0]

                    # DISTRIBUTION WATERFALL
                    for sender in marches_to_assign:
                        target = None
                        
                        # STEP 1: Same Status (Cap 4) - Standard Load Balancing
                        target = find_best_target(sender, [p for p in players if p['Status'] == sender['Status']], 4)
                        
                        # STEP 2: Cross Status (Cap 4) - Standard Load Balancing
                        if not target:
                            target = find_best_target(sender, players, 4)
                        
                        # STEP 3: The "Step Up" (Cap 5+) - PRIORITIZE HIGH INF_CAV
                        if not target:
                            target = find_best_target(sender, players, 10, prioritize_strength=True)

                        if target:
                            final_orders.append([sender['Username'], sender['Status'], target['Username'], target['Status']])
                            target['Receiving_Count'] += 1
                            sender['History'].append(target['Username'])
                        else:
                            final_orders.append([sender['Username'], sender['Status'], "LIMIT REACHED", "N/A"])

                    df_final = pd.DataFrame(final_orders, columns=["From", "Status", "Send To", "Target Status"])
                    df_final = df_final.sort_values(by="From")

                    client = get_client()
                    order_sheet = client.open("Kingshot_Data").worksheet("Orders")
                    order_sheet.clear()
                    order_sheet.append_row(["From", "Status", "Send To", "Target Status"])
                    order_sheet.append_rows(df_final.values.tolist())
                    
                    st.cache_data.clear()
                    st.success("Orders published! High Inf+Cav players prioritized for extra marches.")
                    st.rerun()
        else:
            st.error("Wrong Admin Password")

    if st.button("Reset All Data"):
        if admin_pw == ADMIN_PASSWORD:
            client = get_client()
            client.open("Kingshot_Data").worksheet("Roster").clear()
            client.open("Kingshot_Data").worksheet("Roster").append_row(["Username", "Status", "Marches_Available", "Inf_Cav"])
            client.open("Kingshot_Data").worksheet("Orders").clear()
            client.open("Kingshot_Data").worksheet("Orders").append_row(["From", "Status", "Send To", "Target Status"])
            st.cache_data.clear()
            st.success("Wiped everything.")
            st.rerun()
