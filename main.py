import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time

# 1. INITIAL CONFIG
st.set_page_config(page_title="JTL Vikings Tool", page_icon="⚔️", layout="wide")

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

# 4. AUTHENTICATION
GLOBAL_PASSWORD = st.secrets["general"]["password"]
ADMIN_PASSWORD = st.secrets["general"]["admin_password"]

if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    st.title("🛡️ JTL Vikings Login")
    pw = st.text_input("Alliance Password", type="password")
    if st.button("Access Tool", use_container_width=True):
        if pw == GLOBAL_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect Password")
    st.stop()

# 5. DATA LOADING
try:
    roster_data, orders_data = fetch_all_data()
except Exception:
    st.error("Sheet Connection Busy. Please wait 15 seconds.")
    st.stop()

# 6. UI TABS
st.title("⚔️ JTL Vikings Swap Tool")
tab_reg, tab_roster, tab_orders = st.tabs(["📝 REGISTER", "👥 ROSTER", "📜 SWAP ORDERS"])

with tab_reg:
    st.subheader("Register Your Status")
    user = st.text_input("Username")
    status = st.radio("Status", ["Online", "Offline"], horizontal=True)
    marches = st.slider("Marches you are sending", 4, 6, 5)
    inf_cav = st.number_input("Infantry + Cavalry Approximate Count", min_value=0, value=0)
    
    if st.button("Submit My Entry", use_container_width=True):
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
    c1.subheader(f"Total Players: {len(roster_data)}")
    if c2.button("🔄 Refresh", key="r_rost"):
        st.cache_data.clear(); st.rerun()
    if roster_data:
        st.dataframe(pd.DataFrame(roster_data), use_container_width=True)
    else:
        st.info("No entries yet.")

with tab_orders:
    c3, c4 = st.columns([3, 1])
    c3.subheader("Live Swap Orders")
    if c4.button("🔄 Refresh", key="r_ord"):
        st.cache_data.clear(); st.rerun()
    if orders_data:
        search = st.text_input("🔍 Search for your name")
        df_ord = pd.DataFrame(orders_data)
        if search: df_ord = df_ord[df_ord['From'].str.contains(search, case=False)]
        st.dataframe(df_ord, use_container_width=True)
    else: st.info("Orders not yet generated.")

# 7. ADMIN & LOGIC
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_key = st.text_input("Admin Key", type="password")
    
    # UPDATED AUTOFILL: 30 Online, 20 Offline
    if st.button("🔨 Autofill 50 Test Entries"):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Generating 30 Online & 20 Offline Vikings..."):
                test_users = []
                # Generate 30 Online
                for i in range(1, 31):
                    test_users.append([f"Online_Viking_{i}", "Online", random.randint(4, 6), random.randint(5000, 80000)])
                # Generate 20 Offline
                for i in range(1, 21):
                    test_users.append([f"Offline_Viking_{i}", "Offline", random.randint(4, 6), random.randint(5000, 80000)])
                
                random.shuffle(test_users) # Mix them up
                
                client = get_client()
                client.open("Kingshot_Data").worksheet("Roster").append_rows(test_users)
                st.cache_data.clear(); st.success("The Army has arrived!"); time.sleep(1); st.rerun()

    if st.button("Generate & Publish Orders", use_container_width=True):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Calculating Spillovers..."):
                players = []
                for p in roster_data:
                    players.append({
                        "Username": p["Username"], "Status": p["Status"],
                        "Sends": int(p["Marches_Available"]), "Inf_Cav": int(p.get("Inf_Cav", 0)),
                        "Rec_Count": 0, "History": []
                    })
                
                online_pool = [p for p in players if p["Status"] == "Online"]
                offline_pool = [p for p in players if p["Status"] == "Offline"]
                
                # Expand into a march-by-march queue
                march_queue = []
                for p in players:
                    for _ in range(p["Sends"]):
                        march_queue.append(p)
                random.shuffle(march_queue)

                def find_target(sender, pool, max_rec, prioritize_strength=False):
                    eligible = [t for t in pool if t['Username'] != sender['Username'] 
                                and t['Rec_Count'] < max_rec and t['Username'] not in sender['History']]
                    if not eligible: return None
                    if prioritize_strength:
                        # Sort by Inf_Cav (Lowest first) then Rec_Count
                        eligible.sort(key=lambda x: (x['Inf_Cav'], x['Rec_Count']))
                        return eligible[0]
                    return random.choice(eligible)

                final_rows = []
                for s in march_queue:
                    target = None
                    my_status = s["Status"]
                    same_pool = online_pool if my_status == "Online" else offline_pool
                    other_pool = offline_pool if my_status == "Online" else online_pool

                    # 1. Same Status (Cap 4)
                    target = find_target(s, same_pool, 4)
                    
                    # 2. Same Status (Cap 5, Weakest Priority)
                    if not target:
                        target = find_target(s, same_pool, 5, prioritize_strength=True)

                    # 3. SPILLOVER: Other Status (Cap 4)
                    if not target:
                        target = find_target(s, other_pool, 4)

                    # 4. SPILLOVER: Other Status (Cap 5, Weakest Priority)
                    if not target:
                        target = find_target(s, other_pool, 5, prioritize_strength=True)

                    if target:
                        final_rows.append([s['Username'], s['Status'], target['Username'], target['Status']])
                        target['Rec_Count'] += 1
                        s['History'].append(target['Username'])
                    else:
                        final_rows.append([s['Username'], s['Status'], "NO TARGET FOUND", "N/A"])

                df_final = pd.DataFrame(final_rows, columns=["From", "Status", "Send To", "Target Status"]).sort_values(by="From")
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Orders")
                sheet.clear()
                sheet.append_row(["From", "Status", "Send To", "Target Status"])
                sheet.append_rows(df_final.values.tolist())
                st.cache_data.clear(); st.success("Orders Published!"); time.sleep(1); st.rerun()

    if st.button("Reset All Data"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client()
            sh = client.open("Kingshot_Data")
            sh.worksheet("Roster").clear()
            sh.worksheet("Roster").append_row(["Username", "Status", "Marches_Available", "Inf_Cav"])
            sh.worksheet("Orders").clear()
            sh.worksheet("Orders").append_row(["From", "Status", "Send To", "Target Status"])
            st.cache_data.clear(); st.success("Wiped."); st.rerun()
