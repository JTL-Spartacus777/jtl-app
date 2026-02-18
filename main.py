import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import time

# --- CONFIGURATION ---
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

st.title("⚔️ Kingshot Vikings: Troop Swap")

# Fetch data once per rerun (uses cache)
try:
    roster_data = fetch_data("Roster")
    orders_data = fetch_data("Orders")
except Exception as e:
    st.error("Connection busy. Please wait 10 seconds and refresh.")
    st.stop()

# --- SIDEBAR: PLAYER ACTIONS ---
st.sidebar.header("Member Actions")
with st.sidebar.expander("Add/Update My Entry"):
    user = st.text_input("In-Game Username")
    status = st.radio("Status", ["Online", "Offline"])
    marches = st.slider("Marches to send", 4, 6, 5)
    
    if st.button("Submit Entry"):
        if user:
            with st.spinner("Talking to Google..."):
                client = get_client()
                sheet = client.open("Kingshot_Data").worksheet("Roster")
                
                # FIX: Check locally instead of sheet.find()
                # find index of user in our cached roster_data list
                existing_idx = next((i for i, item in enumerate(roster_data) if item["Username"] == user), None)
                
                if existing_idx is not None:
                    # Row 1 is headers, so index 0 is row 2
                    sheet.delete_rows(existing_idx + 2)
                
                sheet.append_row([user, status, marches])
                st.cache_data.clear()
                st.success(f"Entry for {user} saved!")
                time.sleep(1)
                st.rerun()

with st.sidebar.expander("❌ Remove My Entry"):
    del_user = st.text_input("Confirm Username to Remove")
    if st.button("Delete My Info"):
        with st.spinner("Removing..."):
            client = get_client()
            sheet = client.open("Kingshot_Data").worksheet("Roster")
            
            # FIX: Check locally instead of sheet.find()
            existing_idx = next((i for i, item in enumerate(roster_data) if item["Username"] == del_user), None)
            
            if existing_idx is not None:
                sheet.delete_rows(existing_idx + 2)
                st.cache_data.clear()
                st.success("Entry removed.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Username not found in current roster.")

# --- MAIN AREA ---
tab1, tab2 = st.tabs(["Current Roster", "📜 SWAP ORDERS"])

with tab1:
    st.subheader(f"Registered Players: {len(roster_data)}")
    if roster_data:
        # We sort for the UI display, but the 'delete' logic uses the original order
        df_roster = pd.DataFrame(roster_data).sort_values(by="Username")
        st.table(df_roster)
    else:
        st.info("No players registered yet.")

with tab2:
    if orders_data:
        st.header("📋 Current Orders")
        df_disp = pd.DataFrame(orders_data).sort_values(by="From")
        st.table(df_disp)
    else:
        st.warning("Orders have not been generated yet.")

# --- ADMIN SECTION ---
st.markdown("---")
with st.expander("🛡️ Admin Controls"):
    admin_pw = st.text_input("Admin Password", type="password")
    
    if st.button("Generate & Publish Orders"):
        if admin_pw == ADMIN_PASSWORD:
            with st.spinner("Calculating Swaps..."):
                if len(roster_data) < 2:
                    st.error("Not enough players.")
                else:
                    players = roster_data
                    for p in players: 
                        p['Receiving_Count'] = 0
                        p['History'] = []
                    
                    send_queue = []
                    for p in players:
                        for _ in range(int(p['Marches_Available'])):
                            send_queue.append(p)
                    
                    random.shuffle(send_queue)
                    send_queue.sort(key=lambda x: x['Status'] == 'Online', reverse=True)

                    final_orders = []

                    def get_target(sender, pool, cap):
                        cands = [t for t in pool if t['Username'] != sender['Username'] 
                                 and t['Receiving_Count'] < cap 
                                 and t['Username'] not in sender['History']]
                        if not cands: return None
                        cands.sort(key=lambda x: x['Receiving_Count'])
                        return cands[0]

                    for sender in send_queue:
                        target = (get_target(sender, [p for p in players if p['Status']=='Online'], 4) if sender['Status']=='Online' else None) or \
                                 (get_target(sender, [p for p in players if p['Status']=='Offline'], 4) if sender['Status']=='Offline' else None) or \
                                 get_target(sender, players, 4) or \
                                 get_target(sender, players, 5)
                        
                        if target:
                            final_orders.append([sender['Username'], sender['Status'], target['Username'], target['Status']])
                            target['Receiving_Count'] += 1
                            sender['History'].append(target['Username'])
                        else:
                            final_orders.append([sender['Username'], sender['Status'], "NO UNIQUE TARGET", "N/A"])

                    df_final = pd.DataFrame(final_orders, columns=["From", "Sender_Status", "To", "Target_Status"])
                    df_final = df_final.sort_values(by="From")

                    client = get_client()
                    order_sheet = client.open("Kingshot_Data").worksheet("Orders")
                    order_sheet.clear()
                    order_sheet.append_row(["From", "Sender_Status", "To", "Target_Status"])
                    order_sheet.append_rows(df_final.values.tolist())
                    
                    st.cache_data.clear()
                    st.success("Orders generated!")
                    st.rerun()
        else:
            st.error("Admin Password Required")

    if st.button("Reset All Data"):
        if admin_pw == ADMIN_PASSWORD:
            with st.spinner("Wiping Data..."):
                client = get_client()
                client.open("Kingshot_Data").worksheet("Roster").clear()
                client.open("Kingshot_Data").worksheet("Roster").append_row(["Username", "Status", "Marches_Available"])
                client.open("Kingshot_Data").worksheet("Orders").clear()
                client.open("Kingshot_Data").worksheet("Orders").append_row(["From", "Sender_Status", "To", "Target_Status"])
                st.cache_data.clear()
                st.success("Wiped all data.")
                st.rerun()
