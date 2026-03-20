import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time
from datetime import datetime

# 1. INITIAL CONFIG
st.set_page_config(page_title="JTL Vikings Tool", page_icon="⚔️", layout="wide")

# 2. MOBILE-OPTIMIZED CSS
st.markdown("""
    <style>
    /* Hide headers/footers */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* Mobile-friendly tabs */
    [data-baseweb="tab-list"] { 
        gap: 4px;
        display: flex;
        justify-content: space-between;
    }
    [data-baseweb="tab"] {
        padding: 8px 10px !important;
        font-size: 14px !important;
        flex-grow: 1;
        text-align: center;
    }
    
    /* Cards for readability on small screens */
    div.stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
    }
    .stMetric {
        background-color: #1F2937;
        padding: 10px;
        border-radius: 10px;
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
    # Fetch Roster, Orders, and Event Times
    roster = sh.worksheet("Roster").get_all_records()
    orders = sh.worksheet("Orders").get_all_records()
    meta = {row['Key']: row['Value'] for row in sh.worksheet("Meta").get_all_records()}
    return roster, orders, meta

# 4. AUTHENTICATION
GLOBAL_PASSWORD = st.secrets["general"]["password"]
ADMIN_PASSWORD = st.secrets["general"]["admin_password"]

if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    st.title("🛡️ JTL Login")
    pw = st.text_input("Alliance Password", type="password")
    if st.button("Access Tool"):
        if pw == GLOBAL_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("Wrong Password")
    st.stop()

# 5. DATA LOADING
try:
    roster_data, orders_data, meta_data = fetch_all_data()
    event_1_time = meta_data.get("event_1_time", "Not Set")
    event_2_time = meta_data.get("event_2_time", "Not Set")
except Exception as e:
    st.error(f"Sync Error: {e}")
    st.stop()

# 6. HEADER INFO (Mobile Friendly)
c1, c2 = st.columns(2)
with c1: st.metric("Event 1 (UTC)", event_1_time)
with c2: st.metric("Event 2 (UTC)", event_2_time)

# 7. UI TABS
tab_reg, tab_roster, tab_orders = st.tabs(["📝 REGISTER", "👥 ROSTER", "📜 SWAP"])

with tab_reg:
    st.subheader("Viking Availability")
    user_input = st.text_input("Username (Case Sensitive)").strip()
    existing_user = next((item for item in roster_data if item["Username"] == user_input), None)
    
    if existing_user:
        st.info(f"Updating data for **{user_input}**")
        s1_def = existing_user.get("Status_1", "Online")
        s2_def = existing_user.get("Status_2", "Online")
        m_def = int(existing_user.get("Marches", 5))
        i_def = int(existing_user.get("Inf_Cav", 0))
    else:
        s1_def, s2_def, m_def, i_def = "Online", "Online", 5, 0

    col_a, col_b = st.columns(2)
    with col_a: 
        status_1 = st.selectbox("Event 1 Status", ["Online", "Offline"], index=0 if s1_def == "Online" else 1)
    with col_b: 
        status_2 = st.selectbox("Event 2 Status", ["Online", "Offline"], index=0 if s2_def == "Online" else 1)
    
    marches = st.slider("Marches to send", 4, 6, m_def)
    inf_cav = st.number_input("Infantry + Cavalry Count", min_value=0, value=i_def)
    
    if st.button("Submit Registration", use_container_width=True):
        if user_input:
            client = get_client()
            sheet = client.open("Kingshot_Data").worksheet("Roster")
            if existing_user:
                all_vals = sheet.get_all_values()
                for i, row in enumerate(all_vals):
                    if row[0] == user_input: sheet.delete_rows(i + 1); break
            
            sheet.append_row([user_input, status_1, status_2, marches, inf_cav])
            st.cache_data.clear(); st.success("Viking Data Saved!"); time.sleep(1); st.rerun()

with tab_roster:
    st.dataframe(pd.DataFrame(roster_data), use_container_width=True, hide_index=True)

with tab_orders:
    search = st.text_input("🔍 Search My Name")
    if orders_data:
        df_ord = pd.DataFrame(orders_data)
        if search: df_ord = df_ord[df_ord['From'].str.contains(search, case=False)]
        st.dataframe(df_ord, use_container_width=True, hide_index=True)
    else: st.info("No orders live yet.")

# 8. ADMIN & LOGIC
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_key = st.text_input("Admin Key", type="password")
    
    # Update Times
    t1 = st.text_input("Event 1 UTC Time", value=event_1_time)
    t2 = st.text_input("Event 2 UTC Time", value=event_2_time)
    if st.button("Update UTC Times"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client()
            ms = client.open("Kingshot_Data").worksheet("Meta")
            ms.clear(); ms.append_row(["Key", "Value"])
            ms.append_rows([["event_1_time", t1], ["event_2_time", t2]])
            st.cache_data.clear(); st.success("Times Updated!"); st.rerun()

    event_to_gen = st.selectbox("Generate Orders For:", ["Event 1", "Event 2"])
    
    if st.button("Generate & Publish Orders", use_container_width=True):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Logic Engine Running..."):
                status_key = "Status_1" if event_to_gen == "Event 1" else "Status_2"
                players = []
                for p in roster_data:
                    players.append({
                        "Username": p["Username"], "Status": p[status_key],
                        "Sends": int(p["Marches"]), "Inf_Cav": int(p["Inf_Cav"]),
                        "Rec_Count": 0, "History": []
                    })
                
                on_p = [p for p in players if p["Status"] == "Online"]
                off_p = [p for p in players if p["Status"] == "Offline"]
                
                def find_target(s, pool, max_rec, prio_strength=False):
                    elig = [t for t in pool if t['Username'] != s['Username'] 
                            and t['Rec_Count'] < max_rec and t['Username'] not in s['History']]
                    if not elig: return None
                    if prio_strength:
                        elig.sort(key=lambda x: (x['Inf_Cav'], x['Rec_Count']))
                        return elig[0]
                    return random.choice(elig)

                final_rows = []
                for rd in range(1, 7):
                    senders = [p for p in players if p["Sends"] >= rd]
                    random.shuffle(senders)
                    for s in senders:
                        my_pool = on_p if s["Status"] == "Online" else off_p
                        other_pool = off_p if s["Status"] == "Online" else on_p
                        
                        target = find_target(s, my_pool, 4) or \
                                 find_target(s, my_pool, 5, True) or \
                                 find_target(s, other_pool, 4) or \
                                 find_target(s, other_pool, 5, True)

                        if target:
                            final_rows.append([s['Username'], s['Status'], target['Username'], target['Status']])
                            target['Rec_Count'] += 1; s['History'].append(target['Username'])
                        else:
                            final_rows.append([s['Username'], s['Status'], "NO TARGET FOUND", "N/A"])

                sheet = client.open("Kingshot_Data").worksheet("Orders")
                sheet.clear(); sheet.append_row(["From", "Status", "Send To", "Target Status"])
                sheet.append_rows(pd.DataFrame(final_rows).sort_values(0).values.tolist())
                st.cache_data.clear(); st.success("Done!"); time.sleep(1); st.rerun()

    if st.button("Reset Roster"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client(); sh = client.open("Kingshot_Data").worksheet("Roster")
            sh.clear(); sh.append_row(["Username", "Status_1", "Status_2", "Marches", "Inf_Cav"])
            st.cache_data.clear(); st.rerun()
