import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time

# 1. INITIAL CONFIG
st.set_page_config(page_title="Kingshot Vikings Tool", page_icon="⚔️", layout="wide")

# 2. GHOST MODE & MOBILE CSS
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    .stAppViewFooter {display: none !important;}
    [data-baseweb="tab-list"] { gap: 8px; }
    [data-baseweb="tab"] {
        border: 1px solid #4B5563 !important;
        border-radius: 8px !important;
        padding: 10px 15px !important;
        background-color: #1F2937 !important;
        color: #F3F4F6 !important;
        font-weight: 600 !important;
    }
    [data-baseweb="tab"][aria-selected="true"] {
        background-color: #3B82F6 !important;
        border-color: #60A5FA !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. API HELPERS
def get_client():
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=10)
def fetch_all_data():
    client = get_client()
    sh = client.open("Kingshot_Data")
    return sh.worksheet("Roster").get_all_records(), sh.worksheet("Orders").get_all_records()

# 4. AUTH
GLOBAL_PASSWORD = st.secrets["general"]["password"]
ADMIN_PASSWORD = st.secrets["general"]["admin_password"]

if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    st.title("⚔️ Alliance Login")
    pw = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if pw == GLOBAL_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("Wrong password.")
    st.stop()

# 5. DATA LOADING
try:
    roster_data, orders_data = fetch_all_data()
except Exception:
    st.error("Connection busy. Wait 15s.")
    st.stop()

# 6. UI TABS
st.title("⚔️ Vikings Strict Swap")
tab_reg, tab_roster, tab_orders = st.tabs(["📝 REGISTER", "👥 ROSTER", "📜 SWAP ORDERS"])

with tab_reg:
    st.subheader("Register Troops")
    user = st.text_input("Username")
    status = st.radio("Status", ["Online", "Offline"], horizontal=True)
    marches = st.slider("Marches to send", 4, 6, 5)
    inf_cav = st.number_input("Infantry + Cavalry", min_value=0, value=0)
    
    if st.button("Submit Entry", use_container_width=True):
        if user:
            with st.spinner("Saving..."):
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Roster")
                idx = next((i for i, item in enumerate(roster_data) if item["Username"] == user), None)
                if idx is not None: sheet.delete_rows(idx + 2)
                sheet.append_row([user, status, marches, inf_cav])
                st.cache_data.clear()
                st.success(f"Saved {user}!")
                time.sleep(1); st.rerun()

with tab_roster:
    c1, c2 = st.columns([3, 1])
    c1.subheader(f"Total: {len(roster_data)}")
    if c2.button("🔄 Refresh", key="r_rost"):
        st.cache_data.clear(); st.rerun()
    st.dataframe(pd.DataFrame(roster_data), use_container_width=True)

with tab_orders:
    c3, c4 = st.columns([3, 1])
    c3.subheader("Strict Swap Orders (Max 4)")
    if c4.button("🔄 Refresh", key="r_ord"):
        st.cache_data.clear(); st.rerun()
    if orders_data:
        search = st.text_input("🔍 Search your name")
        df_ord = pd.DataFrame(orders_data)
        if search: df_ord = df_ord[df_ord['From'].str.contains(search, case=False)]
        st.dataframe(df_ord, use_container_width=True)
    else: st.info("Orders not generated.")

# 7. ADMIN CONTROLS
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_pw = st.text_input("Admin Key", type="password")
    
    # --- NEW AUTOFILL TEST FUNCTION ---
    if st.button("🔨 Autofill 50 Test Entries"):
        if admin_pw == ADMIN_PASSWORD:
            with st.spinner("Generating Odin's Army..."):
                test_users = []
                for i in range(1, 51):
                    test_users.append([
                        f"Viking_{i}",
                        random.choice(["Online", "Offline"]),
                        random.randint(4, 6),
                        random.randint(5000, 100000)
                    ])
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Roster")
                sheet.append_rows(test_users)
                st.cache_data.clear()
                st.success("Added 50 test users!")
                time.sleep(1); st.rerun()

    # --- UPDATED STRICT LOGIC ---
    if st.button("Generate & Publish Orders", use_container_width=True):
        if admin_pw == ADMIN_PASSWORD:
            with st.spinner("Calculating Strict Bubbles..."):
                players = []
                for p in roster_data:
                    players.append({
                        "Username": p["Username"], "Status": p["Status"],
                        "Sends": int(p["Marches_Available"]), "Rec_Count": 0, "History": []
                    })
                
                # Split players into isolated pools
                pools = {
                    "Online": [p for p in players if p["Status"] == "Online"],
                    "Offline": [p for p in players if p["Status"] == "Offline"]
                }
                
                final_rows = []

                for status_type, pool in pools.items():
                    # Create march-by-march queue for THIS pool
                    send_queue = []
                    for p in pool:
                        for _ in range(p["Sends"]): send_queue.append(p)
                    
                    # Randomize the send order for fairness
                    random.shuffle(send_queue)

                    for s in send_queue:
                        # Find target ONLY in same pool with max 4 received
                        eligible = [t for t in pool if t['Username'] != s['Username'] 
                                    and t['Rec_Count'] < 4 and t['Username'] not in s['History']]
                        
                        if eligible:
                            target = random.choice(eligible) # Random distribution
                            final_rows.append([s['Username'], s['Status'], target['Username'], target['Status']])
                            target['Rec_Count'] += 1
                            s['History'].append(target['Username'])
                        else:
                            final_rows.append([s['Username'], s['Status'], "NO UNIQUE TARGET", "N/A"])

                df_final = pd.DataFrame(final_rows, columns=["From", "Status", "Send To", "Target Status"]).sort_values(by="From")
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Orders")
                sheet.clear()
                sheet.append_row(["From", "Status", "Send To", "Target Status"])
                sheet.append_rows(df_final.values.tolist())
                st.cache_data.clear(); st.success("Strict Orders Published!"); st.rerun()

    if st.button("Reset All Data"):
        if admin_pw == ADMIN_PASSWORD:
            client = get_client()
            sh = client.open("Kingshot_Data")
            sh.worksheet("Roster").clear()
            sh.worksheet("Roster").append_row(["Username", "Status", "Marches_Available", "Inf_Cav"])
            sh.worksheet("Orders").clear()
            sh.worksheet("Orders").append_row(["From", "Status", "Send To", "Target Status"])
            st.cache_data.clear(); st.success("Wiped."); st.rerun()
