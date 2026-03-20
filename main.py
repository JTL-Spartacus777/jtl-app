st.write("### Data Management")
    if st.button("🧪 Auto-Generate 50 Test Users"):
        if admin_key == ADMIN_PASSWORD:
            with st.spinner("Generating Vikings..."):
                test_users = []
                # Fix: Replaced 10k and 80k with 10000 and 80000
                for i in range(1, 31):
                    test_users.append([f"OnViking_{i}", "Online", "Online", random.randint(4, 6), random.randint(10000, 80000), random.randint(1,1200), random.randint(1,1200), random.randint(100000, 300000), random.randint(300000, 1000000), random.randint(100000, 500000), random.randint(0, 200000)])
                for i in range(1, 21):
                    test_users.append([f"OffViking_{i}", "Offline", "Offline", random.randint(4, 6), random.randint(10000, 80000), random.randint(1,1200), random.randint(1,1200), random.randint(100000, 300000), random.randint(300000, 1000000), random.randint(100000, 500000), random.randint(0, 200000)])
                
                client = get_client()
                sh = client.open("Kingshot_Data").worksheet("Roster")
                sh.clear()
                sh.append_row(["Username", "Status_1", "Status_2", "Marches", "Inf_Cav", "X", "Y", "March_Size", "Inf", "Cav", "Arch"])
                sh.append_rows(test_users)
                st.cache_data.clear(); st.success("Test users created!"); time.sleep(1); st.rerun()
