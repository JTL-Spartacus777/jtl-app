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
tab_reg, tab_roster, tab_orders = st.tabs(["📝 REGISTER / EDIT", "👥 ROSTER", "📜 SWAP ORDERS"])

with tab_reg:
    st.subheader("Manage Your Troop Status")
    
    # Identify if user already exists to allow "Editing"
    user_input = st.text_input("Username (Case Sensitive)").strip()
    existing_user = next((item for item in roster_data if item["Username"] == user_input), None)
    
    if existing_user:
        st.info(f"✨ **{user_input}** is already registered. Updating below will overwrite your old data.")
        default_status = existing_user["Status"]
        default_marches = int(existing_user["Marches_Available"])
        default_inf_cav = int(existing_user["Inf_Cav"])
        btn_label = "Update My Entry"
    else:
        default_status = "Online"
        default_marches = 5
        default_inf_cav = 0
        btn_label = "Register Me"

    status = st.radio("Status", ["Online", "Offline"], index=0 if default_status == "Online" else 1, horizontal=True)
    marches = st.slider("Marches you are sending", 4, 6, default_marches)
    inf_cav = st.number_input("Infantry + Cavalry Count", min_value=0, value=default_inf_cav)
    
    if st.button(btn_label, use_container_width=True):
        if user_input:
            with st.spinner("Talking to the gods..."):
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Roster")
                
                # If editing, find and delete the old row first
                if existing_user:
                    all_rows = sheet.get_all_values()
                    for idx, row in enumerate(all_rows):
                        if row[0] == user_input:
                            sheet.delete_rows(idx + 1)
                            break
                
                sheet.append_row([user_input, status, marches, inf_cav])
                st.cache_data.clear()
                st.success(f"Success! {user_input} has been { 'updated' if existing_user else 'registered' }.")
                time.sleep(1); st.rerun()
        else:
            st.warning("Please enter your username.")

    st.markdown("---")
    with st.expander("🗑️ Delete My Entry"):
        st.write("Type your username exactly to remove yourself from the roster.")
        del_user = st.text_input("Confirm Username to Delete").strip()
        if st.button("Permanently Remove Me", type="primary"):
            target = next((item for item in roster_data if item["Username"] == del_user), None)
            if target:
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Roster")
                all_rows = sheet.get_all_values()
                for idx, row in enumerate(all_rows):
                    if row[0] == del_user:
                        sheet.delete_rows(idx + 1)
                        st.cache_data.clear()
                        st.success(f"{del_user} removed from roster.")
                        time.sleep(1); st.rerun()
            else:
                st.error("Username not found in current roster.")

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
        df_ord_display = pd.DataFrame(orders_data)
        if search:
            df_ord_display = df_ord_display[df_ord_display['From'].str.contains(search, case=False)]
        st.dataframe(df_ord_display, use_container_width=True)
    else:
        st.info("Orders not yet generated.")

# 7. ADMIN & LOGIC
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_key = st.text_input("Admin Key", type="password")
    
    if st.button("🔨 Autofill 30 Online / 20 Offline"):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Generating Vikings..."):
                test_users = []
                for i in range(1, 31):
                    test_users.append([f"OnViking_{i}", "Online", random.randint(4, 6), random.randint(5000, 80000)])
                for i in range(1, 21):
                    test_users.append([f"OffViking_{i}", "Offline", random.randint(4, 6), random.randint(5000, 80000)])
                random.shuffle(test_users)
                client = get_client()
                client.open("Kingshot_Data").worksheet("Roster").append_rows(test_users)
                st.cache_data.clear(); st.success("50 Test Vikings added!"); time.sleep(1); st.rerun()

    if st.button("Generate & Publish Orders", use_container_width=True):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Running Randomized Round-Robin..."):
                players = []
                for p in roster_data:
                    players.append({
                        "Username": p["Username"], "Status": p["Status"],
                        "Sends": int(p["Marches_Available"]), "Inf_Cav": int(p.get("Inf_Cav", 0)),
                        "Rec_Count": 0, "History": []
                    })
                
                online_pool = [p for p in players if p["Status"] == "Online"]
                offline_pool = [p for p in players if p["Status"] == "Offline"]
                
                def find_target(sender, pool, max_rec, prioritize_strength=False):
                    eligible = [t for t in pool if t['Username'] != sender['Username'] 
                                and t['Rec_Count'] < max_rec and t['Username'] not in sender['History']]
                    if not eligible: return None
                    if prioritize_strength:
                        eligible.sort(key=lambda x: (x['Inf_Cav'], x['Rec_Count']))
                        return eligible[0]
                    return random.choice(eligible)

                final_rows = []
                success_count = 0
                fail_count = 0

                for round_num in range(1, 7):
                    current_round_senders = [p for p in players if p["Sends"] >= round_num]
                    random.shuffle(current_round_senders)

                    for s in current_round_senders:
                        target = None
                        my_status = s["Status"]
                        same_pool = online_pool if my_status == "Online" else offline_pool
                        other_pool = offline_pool if my_status == "Online" else online_pool

                        # Waterfall Logic
                        target = find_target(s, same_pool, 4)
                        if not target:
                            target = find_target(s, same_pool, 5, prioritize_strength=True)
                        if not target:
                            target = find_target(s, other_pool, 4)
                        if not target:
                            target = find_target(s, other_pool, 5, prioritize_strength=True)

                        if target:
                            final_rows.append([s['Username'], s['Status'], target['Username'], target['Status']])
                            target['Rec_Count'] += 1
                            s['History'].append(target['Username'])
                            success_count += 1
                        else:
                            final_rows.append([s['Username'], s['Status'], "NO TARGET FOUND", "N/A"])
                            fail_count += 1

                df_final = pd.DataFrame(final_rows, columns=["From", "Status", "Send To", "Target Status"]).sort_values(by="From")
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Orders")
                sheet.clear()
                sheet.append_row(["From", "Status", "Send To", "Target Status"])
                sheet.append_rows(df_final.values.tolist())
                st.cache_data.clear()
                st.success(f"Orders Published! ✅ {success_count} Connected | ⚠️ {fail_count} Failed.")
                time.sleep(2); st.rerun()

    if st.button("Reset All Data"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client()
            sh = client.open("Kingshot_Data")
            sh.worksheet("Roster").clear()
            sh.worksheet("Roster").append_row(["Username", "Status", "Marches_Available", "Inf_Cav"])
            sh.worksheet("Orders").clear()
            sh.worksheet("Orders").append_row(["From", "Status", "Send To", "Target Status"])
            st.cache_data.clear(); st.success("Wiped."); st.rerun()
