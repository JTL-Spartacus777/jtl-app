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

def safe_int(val, default=0):
    try:
        if val == "" or val is None: return default
        return int(float(val))
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
    st.error("Sync Error: Ensure 'Roster' has 11 columns and 'Meta' exists.")
    st.stop()

# 6. HEADER INFO
c1, c2 = st.columns(2)
with c1: st.metric("Event 1 (UTC)", event_1_time)
with c2: st.metric("Event 2 (UTC)", event_2_time)

# --- REFRESH BUTTON ---
if st.button("🔄 Refresh Data (Sync Latest Coords)", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 7. UI TABS
tab_reg, tab_roster, tab_orders = st.tabs(["📝 REGISTER", "👥 ROSTER", "📜 SWAP"])

with tab_reg:
    st.subheader("Viking Availability")
    user_input = st.text_input("Username").strip()
    existing_user = next((item for item in roster_data if item["Username"] == user_input), None)
    
    if existing_user:
        st.info(f"Updating data for **{user_input}**")
        s1_def, s2_def = existing_user.get("Status_1", "Online"), existing_user.get("Status_2", "Online")
        m_def, ic_def = safe_int(existing_user.get("Marches", 5)), safe_int(existing_user.get("Inf_Cav", 0))
        x_def, y_def = safe_int(existing_user.get("X", 0)), safe_int(existing_user.get("Y", 0))
        ms_def = safe_int(existing_user.get("March_Size", 0))
        inf_def, cav_def, arch_def = safe_int(existing_user.get("Inf", 0)), safe_int(existing_user.get("Cav", 0)), safe_int(existing_user.get("Arch", 0))
    else:
        s1_def, s2_def, m_def, ic_def = "Online", "Online", 5, 0
        x_def, y_def, ms_def, inf_def, cav_def, arch_def = 0, 0, 0, 0, 0, 0

    col_a, col_b = st.columns(2)
    with col_a: status_1 = st.selectbox("Event 1 Status", ["Online", "Offline"], index=0 if s1_def == "Online" else 1)
    with col_b: status_2 = st.selectbox("Event 2 Status", ["Online", "Offline"], index=0 if s2_def == "Online" else 1)
    
    marches = st.slider("Marches to send", 4, 6, m_def)
    inf_cav = st.number_input("Approximate Infantry + Cavalry count", min_value=0, value=ic_def)
    
    with st.expander("⚙️ Advanced (Optional; Can update after assignment)"):
        cx, cy = st.columns(2)
        with cx: x_coord = st.number_input("X Coordinate", value=x_def)
        with cy: y_coord = st.number_input("Y Coordinate", value=y_def)
        march_sz = st.number_input("Exact March Capacity", min_value=0, value=ms_def)
        t_inf = st.number_input("Total Infantry", min_value=0, value=inf_def)
        t_cav = st.number_input("Total Cavalry", min_value=0, value=cav_def)
        t_arch = st.number_input("Total Archers", min_value=0, value=arch_def)

    if st.button("Submit Registration", use_container_width=True, type="primary"):
        if user_input:
            client = get_client()
            sheet = client.open("Kingshot_Data").worksheet("Roster")
            if existing_user:
                all_vals = sheet.get_all_values()
                for i, row in enumerate(all_vals):
                    if row[0] == user_input: sheet.delete_rows(i + 1); break
            sheet.append_row([user_input, status_1, status_2, marches, inf_cav, x_coord, y_coord, march_sz, t_inf, t_cav, t_arch])
            st.cache_data.clear(); st.success("Saved!"); time.sleep(1); st.rerun()

with tab_roster:
    st.dataframe(pd.DataFrame(roster_data), use_container_width=True, hide_index=True)

with tab_orders:
    search = st.text_input("🔍 Search Name")
    if orders_data:
        r_dict = {r['Username']: r for r in roster_data}
        disp = []
        for o in orders_data:
            s_name, t_name = o['From'], o['Send To']
            s_d, t_d = r_dict.get(s_name, {}), r_dict.get(t_name, {})
            
            # Troop Math
            n_m, m_sz = safe_int(s_d.get('Marches', 0)), safe_int(s_d.get('March_Size', 0))
            m_str = "Not Set"
            if n_m > 0 and m_sz > 0:
                p_i, p_c, p_a = safe_int(s_d.get('Inf',0))//n_m, safe_int(s_d.get('Cav',0))//n_m, safe_int(s_d.get('Arch',0))//n_m
                m_i = min(p_i, m_sz)
                rem = m_sz - m_i
                m_c = min(p_c, rem)
                m_a = min(p_a, rem - m_c)
                m_str = f"⚔️{m_i} | 🐎{m_c} | 🏹{m_a}"
            
            coords = f"X:{t_d.get('X','?')} Y:{t_d.get('Y','?')}"
            disp.append({"From": s_name, "Per March": m_str, "Send To": t_name, "Target Coords": coords})
        
        df_d = pd.DataFrame(disp)
        if search: df_d = df_d[df_d['From'].str.contains(search, case=False)]
        st.dataframe(df_d, use_container_width=True, hide_index=True)

# 8. ADMIN
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_key = st.text_input("Admin Key", type="password")
    
    if st.button("Update UTC Times"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client()
            ms = client.open("Kingshot_Data").worksheet("Meta")
            ms.clear(); ms.append_row(["Key", "Value"])
            ms.append_rows([["event_1_time", t1], ["event_2_time", t2]])
            st.cache_data.clear(); st.success("Updated!"); st.rerun()

    event_gen = st.selectbox("Orders For:", ["Event 1", "Event 2"])
    if st.button("🚀 Generate & Publish", use_container_width=True):
        if admin_key == ADMIN_PASSWORD:
            status_col = "Status_1" if event_gen == "Event 1" else "Status_2"
            players = [{"Username": p["Username"], "Status": p[status_col], "Sends": safe_int(p["Marches"]), "Inf_Cav": safe_int(p["Inf_Cav"]), "Rec_Count": 0, "History": []} for p in roster_data]
            on_p, off_p = [p for p in players if p["Status"] == "Online"], [p for p in players if p["Status"] == "Offline"]
            
            def find_t(s, pool, mx):
                elig = [t for t in pool if t['Username'] != s['Username'] and t['Rec_Count'] < mx and t['Username'] not in s['History']]
                if not elig: return None
                random.shuffle(elig); return elig[0]

            final = []
            for rd in range(1, 7):
                senders = [p for p in players if p["Sends"] >= rd]
                random.shuffle(senders)
                for s in senders:
                    target = find_t(s, on_p if s["Status"] == "Online" else off_p, 4) or find_t(s, off_p if s["Status"] == "Online" else on_p, 4) or find_t(s, on_p + off_p, 6)
                    if target:
                        final.append([s['Username'], s['Status'], target['Username'], target['Status']])
                        target['Rec_Count'] += 1; s['History'].append(target['Username'])
                    else: final.append([s['Username'], s['Status'], "NO TARGET", "N/A"])

            client = get_client(); os = client.open("Kingshot_Data").worksheet("Orders")
            os.clear(); os.append_row(["From", "Status", "Send To", "Target Status"])
            os.append_rows(pd.DataFrame(final).sort_values(0).values.tolist())
            st.cache_data.clear(); st.success("Orders Live!"); st.rerun()

    if st.button("🧪 Auto-Generate 50 Test Users"):
        if admin_key == ADMIN_PASSWORD:
            tests = []
            for i in range(1, 51):
                stat = "Online" if i <= 30 else "Offline"
                tests.append([f"Viking_{i}", stat, stat, random.randint(4,6), random.randint(10000,80000), random.randint(1,1200), random.randint(1,1200), 200000, 600000, 300000, 100000])
            client = get_client(); rs = client.open("Kingshot_Data").worksheet("Roster")
            rs.clear(); rs.append_row(["Username", "Status_1", "Status_2", "Marches", "Inf_Cav", "X", "Y", "March_Size", "Inf", "Cav", "Arch"])
            rs.append_rows(tests); st.cache_data.clear(); st.rerun()

    if st.button("Reset Roster", type="secondary"):
        if admin_key == ADMIN_PASSWORD:
            client = get_client(); rs = client.open("Kingshot_Data").worksheet("Roster")
            rs.clear(); rs.append_row(["Username", "Status_1", "Status_2", "Marches", "Inf_Cav", "X", "Y", "March_Size", "Inf", "Cav", "Arch"])
            st.cache_data.clear(); st.rerun()
