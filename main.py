import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time

# 1. INITIAL CONFIG
st.set_page_config(page_title="JTL Vikings Tool", page_icon="⚔️", layout="wide")

# 2. MOBILE-OPTIMIZED & LIGHT-THEME CSS
st.markdown("""
    <style>
    /* Hide headers/footers */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* LIGHT METRIC BOXES */
    [data-testid="stMetric"] {
        background-color: #F0F2F6 !important; 
        border: 1px solid #D1D5DB !important;
        border-radius: 10px;
        padding: 10px;
    }
    [data-testid="stMetric"] label, [data-testid="stMetric"] div {
        color: #1F2937 !important;
    }

    /* LIGHT INPUT BOXES */
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div,
    div[data-baseweb="number-input"] > div {
        background-color: #F0F2F6 !important; 
        color: #1F2937 !important; 
        border-radius: 8px !important;
    }
    input { color: #1F2937 !important; }

    /* Mobile-friendly tabs */
    [data-baseweb="tab-list"] { 
        gap: 4px; display: flex; justify-content: space-between;
    }
    [data-baseweb="tab"] {
        padding: 8px 10px !important; font-size: 14px !important; flex-grow: 1; text-align: center;
    }

    div.stButton > button {
        width: 100%; border-radius: 10px; height: 3em; font-weight: 700;
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
    roster = sh.worksheet("Roster").get_all_records()
    orders = sh.worksheet("Orders").get_all_records()
    meta = {row['Key']: row['Value'] for row in sh.worksheet("Meta").get_all_records()}
    return roster, orders, meta

# Helper to handle empty string conversions from Google Sheets
def safe_int(val, default=0):
    try: return int(val) if val != "" else default
    except: return default

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
    st.error(f"Sync Error: Make sure your Roster sheet has the 11 updated columns exactly.")
    st.stop()

# 6. HEADER INFO
c1, c2 = st.columns(2)
with c1: st.metric("Event 1 (UTC)", event_1_time)
with c2: st.metric("Event 2 (UTC)", event_2_time)

# 7. UI TABS
tab_reg, tab_roster, tab_orders = st.tabs(["📝 REGISTER", "👥 ROSTER", "📜 SWAP"])

with tab_reg:
    st.subheader("Viking Availability")
    user_input = st.text_input("Username").strip()
    existing_user = next((item for item in roster_data if item["Username"] == user_input), None)
    
    if existing_user:
        st.info(f"Updating data for **{user_input}**")
        s1_def = existing_user.get("Status_1", "Online")
        s2_def = existing_user.get("Status_2", "Online")
        m_def = safe_int(existing_user.get("Marches", 5))
        ic_def = safe_int(existing_user.get("Inf_Cav", 0))
        # Advanced Defaults
        x_def = safe_int(existing_user.get("X", 0))
        y_def = safe_int(existing_user.get("Y", 0))
        ms_def = safe_int(existing_user.get("March_Size", 0))
        inf_def = safe_int(existing_user.get("Inf", 0))
        cav_def = safe_int(existing_user.get("Cav", 0))
        arch_def = safe_int(existing_user.get("Arch", 0))
    else:
        s1_def, s2_def, m_def, ic_def = "Online", "Online", 5, 0
        x_def, y_def, ms_def, inf_def, cav_def, arch_def = 0, 0, 0, 0, 0, 0

    col_a, col_b = st.columns(2)
    with col_a: status_1 = st.selectbox("Event 1 Status", ["Online", "Offline"], index=0 if s1_def == "Online" else 1)
    with col_b: status_2 = st.selectbox("Event 2 Status", ["Online", "Offline"], index=0 if s2_def == "Online" else 1)
    
    marches = st.slider("Marches to send", 4, 6, m_def)
    inf_cav = st.number_input("General Inf/Cav Power (For Matchmaking)", min_value=0, value=ic_def)
    
    with st.expander("⚙️ Advanced Setup (Optional / Update Later)"):
        st.caption("Coordinates and exact troop layouts for your marches. You can return here to update these even after swap orders are published.")
        c_x, c_y = st.columns(2)
        with c_x: x_coord = st.number_input("X Coordinate", value=x_def, step=1)
        with c_y: y_coord = st.number_input("Y Coordinate", value=y_def, step=1)
        
        march_size = st.number_input("Exact March Size (Capacity)", min_value=0, value=ms_def, step=1000)
        st.write("Total Available Troops")
        t_inf = st.number_input("Total Infantry", min_value=0, value=inf_def, step=1000)
        t_cav = st.number_input("Total Cavalry", min_value=0, value=cav_def, step=1000)
        t_arch = st.number_input("Total Archers", min_value=0, value=arch_def, step=1000)

    if st.button("Submit Registration", use_container_width=True):
        if user_input:
            client = get_client()
            sheet = client.open("Kingshot_Data").worksheet("Roster")
            if existing_user:
                all_vals = sheet.get_all_values()
                for i, row in enumerate(all_vals):
                    if row[0] == user_input: sheet.delete_rows(i + 1); break
            
            # Save all 11 columns
            sheet.append_row([user_input, status_1, status_2, marches, inf_cav, x_coord, y_coord, march_size, t_inf, t_cav, t_arch])
            st.cache_data.clear(); st.success("Data Saved!"); time.sleep(1); st.rerun()

with tab_roster:
    st.dataframe(pd.DataFrame(roster_data), use_container_width=True, hide_index=True)

with tab_orders:
    search = st.text_input("🔍 Search My Name")
    if orders_data and roster_data:
        df_ord = pd.DataFrame(orders_data)
        
        # Build dictionary for fast lookup of dynamic live roster data
        roster_dict = {r['Username']: r for r in roster_data}
        
        display_list = []
        for _, order in df_ord.iterrows():
            sender = order['From']
            target = order['Send To']
            
            s_data = roster_dict.get(sender, {})
            t_data = roster_dict.get(target, {})
            
            # ---- Sender Calculation ----
            num_m = safe_int(s_data.get('Marches', 0))
            m_size = safe_int(s_data.get('March_Size', 0))
            total_inf = safe_int(s_data.get('Inf', 0))
            total_cav = safe_int(s_data.get('Cav', 0))
            total_arch = safe_int(s_data.get('Arch', 0))
            
            march_str = "Not Set"
            if num_m > 0 and m_size > 0:
                # Divide available troops by marches
                p_inf = total_inf // num_m
                p_cav = total_cav // num_m
                p_arch = total_arch // num_m
                
                # Fill up to march capacity, prioritizing Inf -> Cav -> Arch
                m_inf = min(p_inf, m_size)
                rem = m_size - m_inf
                
                m_cav = min(p_cav, rem)
                rem -= m_cav
                
                m_arch = min(p_arch, rem)
                
                march_str = f"⚔️ {m_inf} I | 🐎 {m_cav} C | 🏹 {m_arch} A"
            
            # ---- Target Calculation ----
            t_x = t_data.get('X', '')
            t_y = t_data.get('Y', '')
            target_coords = f"X:{t_x} Y:{t_y}" if (t_x and t_y) else "No Coords"
            
            display_list.append({
                "From": sender,
                "Send Per March": march_str,
                "Send To": target,
                "Target Coords": target_coords,
                "Tgt Status": order.get('Target Status', '')
            })

        df_display = pd.DataFrame(display_list)
        if search: df_display = df_display[df_display['From'].str.contains(search, case=False)]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else: 
        st.info("No orders live yet.")

# 8. ADMIN & LOGIC
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_key = st.text_input("Admin Key", type="password")
    
    st.write("### Set Event Times")
    t1 = st.text_input("Event 1 UTC Time", value=event_1_time)
    t2 = st.text_input("Event 2 UTC Time", value=event_2_time)
    
    if st.button("Update UTC Times"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client()
            ms = client.open("Kingshot_Data").worksheet("Meta")
            ms.clear()
            ms.append_row(["Key", "Value"])
            ms.append_rows([["event_1_time", t1], ["event_2_time", t2]])
            st.cache_data.clear()
            st.success("Times Updated!")
            st.rerun()

    st.write("### Logic Engine")
    event_to_gen = st.selectbox("Generate Orders For:", ["Event 1", "Event 2"])
    
    if st.button("Generate & Publish Orders", use_container_width=True):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Logic Engine Running..."):
                status_key = "Status_1" if event_to_gen == "Event 1" else "Status_2"
                players = []
                for p in roster_data:
                    players.append({
                        "Username": p["Username"], 
                        "Status": p[status_key],
                        "Sends": safe_int(p["Marches"]), 
                        "Inf_Cav": safe_int(p["Inf_Cav"]),
                        "Rec_Count": 0, 
                        "History": []
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
                            target['Rec_Count'] += 1
                            s['History'].append(target['Username'])
                        else:
                            final_rows.append([s['Username'], s['Status'], "NO TARGET FOUND", "N/A"])

                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Orders")
                sheet.clear()
                sheet.append_row(["From", "Status", "Send To", "Target Status"])
                sheet.append_rows(pd.DataFrame(final_rows).sort_values(0).values.tolist())
                st.cache_data.clear()
                st.success("Done!")
                time.sleep(1)
                st.rerun()

    st.write("### Data Management")
    if st.button("🧪 Auto-Generate 50 Test Users"):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Generating Vikings..."):
                test_users = []
                # 30 Online test users
                for i in range(1, 31):
                    test_users.append([
                        f"OnViking_{i}", "Online", "Online", random.randint(4, 6), 
                        random.randint(10000, 80000), random.randint(1,1200), 
                        random.randint(1,1200), random.randint(100000, 300000), 
                        random.randint(300000, 1000000), random.randint(100000, 500000), 
                        random.randint(0, 200000)
                    ])
                # 20 Offline test users
                for i in range(1, 21):
                    test_users.append([
                        f"OffViking_{i}", "Offline", "Offline", random.randint(4, 6), 
                        random.randint(10000, 80000), random.randint(1,1200), 
                        random.randint(1,1200), random.randint(100000, 300000), 
                        random.randint(300000, 1000000), random.randint(100000, 500000), 
                        random.randint(0, 200000)
                    ])
                
                client = get_client()
                sh = client.open("Kingshot_Data").worksheet("Roster")
                sh.clear()
                sh.append_row(["Username", "Status_1", "Status_2", "Marches", "Inf_Cav", "X", "Y", "March_Size", "Inf", "Cav", "Arch"])
                sh.append_rows(test_users)
                st.cache_data.clear()
                st.success("Test users created!")
                time.sleep(1)
                st.rerun()

    if st.button("Reset / Wipe Roster", type="secondary"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client()
            sh = client.open("Kingshot_Data").worksheet("Roster")
            sh.clear()
            sh.append_row(["Username", "Status_1", "Status_2", "Marches", "Inf_Cav", "X", "Y", "March_Size", "Inf", "Cav", "Arch"])
            st.cache_data.clear()
            st.rerun()
