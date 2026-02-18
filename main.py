import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# --- CONFIGURATION ---
GLOBAL_PASSWORD = st.secrets["general"]["password"]
ADMIN_PASSWORD = st.secrets["general"]["admin_password"]

# --- GOOGLE SHEETS CONNECTION ---
def get_data():
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    # Create credentials from the Streamlit Secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Open the sheet
    sheet = client.open("Kingshot_Data").worksheet("Roster")
    return sheet

# --- AUTHENTICATION ---
def check_password():
    def password_entered():
        if st.session_state["password"] == GLOBAL_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Alliance Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Alliance Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

if check_password():
    st.title("⚔️ Kingshot Vikings: Troop Swap")

    # Connect to Sheet
    try:
        sheet = get_data()
        data = sheet.get_all_records()
    except Exception as e:
        st.error(f"Database Error: {e}")
        st.stop()

    # --- INPUT SECTION ---
    st.sidebar.header("Add Your Info")
    user = st.sidebar.text_input("Username (Case Sensitive)")
    status = st.sidebar.radio("Are you Online?", ["Online", "Offline"])
    marches = st.sidebar.slider("How many marches can you send?", 4, 6, 5)
    
    if st.sidebar.button("Submit / Update Entry"):
        if user == "":
             st.error("Please enter a username.")
        else:
            # Check if user exists to update or append
            existing_users = [d['Username'] for d in data]
            if user in existing_users:
                # Update logic is tricky in simple sheets, simpler to delete old and add new or just warn
                st.warning("User exists! (For this simple version, please ask Admin to reset if you made a mistake, or just ignore this)")
            else:
                new_row = [user, status, marches]
                sheet.append_row(new_row)
                st.success(f"Registered {user}!")
                st.rerun()

    # --- DISPLAY ROSTER ---
    st.subheader(f"Current Participants: {len(data)}")
    if len(data) > 0:
        df = pd.DataFrame(data)
        st.dataframe(df)

    # --- THE LOGIC ENGINE ---
    st.markdown("---")
    if st.button("Generate Swap Orders"):
        if len(data) < 2:
            st.warning("Need at least 2 players.")
        else:
            players = data # List of dicts
            for p in players: p['Receiving_Count'] = 0
            
            # Create the pile of marches
            send_queue = []
            for p in players:
                for _ in range(int(p['Marches_Available'])):
                    send_queue.append(p)
            
            random.shuffle(send_queue)
            # Sort: Online sends first
            send_queue.sort(key=lambda x: x['Status'] == 'Online', reverse=True)

            orders = []
            
            def get_valid_target(sender, pool, cap):
                candidates = [t for t in pool if t['Username'] != sender['Username'] and t['Receiving_Count'] < cap]
                if not candidates: return None
                candidates.sort(key=lambda x: x['Receiving_Count'])
                return candidates[0]

            impossible = False
            
            for sender in send_queue:
                target = None
                
                # 1. Online -> Online (Cap 4)
                if sender['Status'] == 'Online':
                    target = get_valid_target(sender, [p for p in players if p['Status']=='Online'], 4)
                
                # 2. Offline -> Offline (Cap 4)
                if sender['Status'] == 'Offline' and target is None:
                    target = get_valid_target(sender, [p for p in players if p['Status']=='Offline'], 4)
                
                # 3. Cross-fill (Cap 4)
                if target is None:
                    target = get_valid_target(sender, players, 4)
                
                # 4. Emergency (Cap 5)
                if target is None:
                     target = get_valid_target(sender, players, 5)
                
                if target:
                    orders.append({"From": sender['Username'], "Status": sender['Status'], "To": target['Username'], "Target Status": target['Status']})
                    target['Receiving_Count'] += 1
                else:
                    orders.append({"From": sender['Username'], "Status": sender['Status'], "To": "NO TARGET", "Target Status": "N/A"})
                    impossible = True

            st.header("📋 Final Orders")
            st.dataframe(pd.DataFrame(orders))

    # --- RESET ---
    st.markdown("---")
    with st.expander("Admin Reset"):
        admin_pass = st.text_input("Admin Password", type="password")
        if st.button("Reset Event Data"):
            if admin_pass == ADMIN_PASSWORD:
                # Clear sheet (keep headers)
                sheet.clear()
                sheet.append_row(["Username", "Status", "Marches_Available"])
                st.success("Data wiped.")
                st.rerun()
            else:
                st.error("Wrong Admin Password")
