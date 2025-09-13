import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json, time, os, re, firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, time as dtime
from seat_visualizer import visualize_seating

# --- Page Config ---
st.set_page_config(page_title="Exam System Portal", layout="wide")

# --- Firebase Initialization ---
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://exam-hall-seating-arrang-38bc9-default-rtdb.firebaseio.com/'
    })

# --- Constants ---
DATA_FILE = "classrooms.json"
ADMIN_USER, ADMIN_PASS = "admin", "password123"
STAFF_USER, STAFF_PASS = "staff", "staff123"

# --- Ensure Storage ---
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

# --- Session Defaults ---
if "role" not in st.session_state:
    st.session_state.role = None
if "df" not in st.session_state:
    st.session_state.df = None
if "exam_time" not in st.session_state:
    st.session_state.exam_time = dtime(9, 0)
if "selected_subject" not in st.session_state:
    st.session_state.selected_subject = None

# --- Logout ---
def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- Login ---
if st.session_state.role is None:
    st.title("🔐 Login")
    with st.form("login_form"):
        role = st.selectbox("Login as", ["Student", "Staff", "Admin"], key="login_role")
        uid = st.text_input("User ID")
        pwd = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

    if submit:
        if role == "Admin" and uid == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state.role = "admin"
            st.rerun()
        elif role == "Staff" and uid == STAFF_USER and pwd == STAFF_PASS:
            st.session_state.role = "staff"
            st.rerun()
        elif role == "Student":
            try:
                real = db.reference(f"{uid}/B").get()
            except Exception:
                real = None
            if real and pwd == str(real):
                st.session_state.role = "student"
                st.session_state.student_id = uid
                st.rerun()
            else:
                st.error("Invalid student credentials")
        else:
            st.error("Invalid credentials")
    st.stop()

# --- Main Tabs (Always visible) ---
tab_labels = ["Home", "Search & Lookup"]

# For students, rename the second tab
if st.session_state.role == "student":
    tab_labels[1] = "Hall Ticket 📄"

tabs = st.tabs(tab_labels)

# --- Sidebar Session Label ---
role_display = {
    "admin": "Admin Session",
    "staff": "Staff Session",
    "student": "Student Session"
}.get(st.session_state.role, "Session")

st.sidebar.markdown(f"## 🔓 {role_display}")
if st.sidebar.button("Logout"):
    logout()

# --- Utility ---

def detect_subject_columns(columns):
    pattern = re.compile(r"\b\d{2}[a-z]{3,5}\d{4}", re.IGNORECASE)
    return [col for col in columns if pattern.search(col.strip())]

def distribute_students(df, subject, classrooms, exam_date, exam_time):
    subject_col = subject.lower().strip()
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()

    if subject_col not in df.columns or "registration number" not in df.columns:
        st.error("Required columns missing.")
        return pd.DataFrame()

    col_data = df[subject_col].fillna("").astype(str).str.strip().str.upper()
    mask = (col_data != "") & (col_data != "NA")

    sel = df.loc[mask, ["registration number"]].dropna()
    sel["registration number"] = sel["registration number"].astype(str).str.strip().str.upper()
    sel = sel.sort_values("registration number").reset_index(drop=True)

    seating, idx, total = [], 0, len(sel)
    for room_name, cfg in classrooms.items():
        if idx >= total:
            break
        rows, cols = int(cfg.get("rows", 1)), int(cfg.get("cols", 1))
        capacity = rows * cols
        batch = sel.iloc[idx: idx + capacity]
        students = batch["registration number"].tolist()
        assigned = 0

        for c in range(cols):
            if assigned >= len(students): break
            row_iter = range(rows) if c % 2 == 0 else range(rows - 1, -1, -1)
            for r in row_iter:
                if assigned >= len(students): break
                seating.append({
                    "Subject": subject.upper(),
                    "Registration Number": students[assigned],
                    "Classroom": f"Room - {str(room_name)}", 
                    "Row": r + 1,
                    "Column": c + 1,
                    "Date": exam_date.strftime("%Y-%m-%d") if exam_date else "",
                    "Time": exam_time.strftime("%H:%M") if exam_time else ""
                })
                assigned += 1
        idx += assigned
    return pd.DataFrame(seating)

# --- ADMIN ---
if st.session_state.role == "admin":
    tabs = st.tabs(["Home", "Search & Lookup"])

    with tabs[0]:
        st.header("🏫 Classroom Management")
        with open(DATA_FILE, 'r') as f:
            classrooms = json.load(f)

        updated = False  

        st.subheader("📋 Existing Classrooms")
        for name, cfg in classrooms.items():
            cols = st.columns([3, 2, 2, 1, 1])
            cols[0].markdown(f"Classroom No.{name}")
            rows_input = cols[1].number_input(f"Rows: {name}", min_value=1, value=cfg['rows'], key=f"rows: {name}")
            cols_input = cols[2].number_input(f"Cols: {name}", min_value=1, value=cfg['cols'], key=f"cols: {name}")

            if cols[3].button("Update", key=f"update_{name}"):
                classrooms[name] = {'rows': int(rows_input), 'cols': int(cols_input)}
                updated = True
                st.success(f"✅ Updated '{name}' to {rows_input} rows × {cols_input} columns")

            if cols[4].button("Delete", key=f"delete_{name}"):
                del classrooms[name]
                with open(DATA_FILE, 'w') as f:
                    json.dump(classrooms, f)
                st.rerun()

        if updated:
            with open(DATA_FILE, 'w') as f:
                json.dump(classrooms, f)
            st.success("Classroom updated")
            time.sleep(2)
            st.rerun()

        st.markdown("---")
        st.subheader("➕ Add New Classroom with Seat Designer")

        new_name = st.text_input("Classroom Number:", value=st.session_state.get("new_name", ""))
        new_r = st.number_input("Rows:", min_value=1, value=st.session_state.get("new_r", 3), key="new_r_input")
        new_c = st.number_input("Columns:", min_value=1, value=st.session_state.get("new_c", 5), key="new_c_input")

        # Initialize layout in session_state if not exists or size changed
        if "seat_layout" not in st.session_state or len(st.session_state.seat_layout) != new_r or len(st.session_state.seat_layout[0]) != new_c:
            st.session_state.seat_layout = [[1 for _ in range(new_c)] for _ in range(new_r)]

        fig, ax = plt.subplots(figsize=(new_c * 0.25, new_r  * 0.25),dpi = 200)
        ax.set_facecolor('black')  # Background

        gap_x = 0.3
        gap_y = 0.2
        # Teacher's board with border
        desk_total_width = new_c * (1 + gap_x)
        ax.add_patch(plt.Rectangle(
            (-0.5, new_r + 0.3),       
            desk_total_width + 0.5,    
            1.2,                       
            facecolor='white',
            edgecolor='black',
            lw=1
        ))

        desk_width = 1 
        total_width = new_c * (1 + gap_x)  
        x_offset = (new_c * (1 + gap_x)) / -2 + 0.5 

        # Draw desks with rounded tops (semi-circle + base rectangle)
        for r in range(new_r):
            for c in range(new_c):
                desk_color = '#00CFFF' if st.session_state.seat_layout[r][c] == 1 else '#2E2E2E'
                # 
                x_pos = c * (1 + gap_x)
                y_pos = new_r - r - 1  


                # Desk base
                ax.add_patch(plt.Rectangle(
                (x_pos + 0.1, y_pos),   
                0.8, 0.4,
                facecolor=desk_color,
                edgecolor='black',
                lw=0.6
                ))

                semi = plt.Circle(
                (x_pos + 0.5, y_pos + 0.5),  
                0.4,
                facecolor=desk_color,
                edgecolor='black',
                lw=0.4
                )
                ax.add_patch(semi)
        ax.add_patch(plt.Rectangle(
            (-0.9, new_r + -0.9),  
            0.6, 0.9,
            facecolor='brown',
            edgecolor='black',
            lw=0.8
        ))  

        ax.set_xlim(-1.2, new_c + 2.7) 
        ax.set_ylim(-0.8, new_r + 1.6)
        ax.set_aspect('equal')
        ax.axis('off')
        plt.tight_layout(pad=0)
        st.pyplot(fig, clear_figure=True, use_container_width=True)

        if st.button("Save Classroom"):
            if new_name and new_name not in classrooms:
                classrooms[new_name] = {
                    "rows": int(new_r),
                    "cols": int(new_c),
                    "layout": st.session_state.seat_layout
                }
                with open(DATA_FILE, "w") as f:
                    json.dump(classrooms, f)
                st.session_state.new_name = " "
                st.session_state.new_r = 3
                st.session_state.new_c = 3
                st.session_state.seat_layout = [[1 for _ in range(1)] for _ in range(1)]

                st.success(f"Classroom '{new_name}' saved with custom seat layout.")
                st.rerun()
            else:
                st.error("⚠️ Invalid or duplicate classroom name.")


    with tabs[1]:
        st.header("🗂 All Generated Seating Data")
        admin_seating_ref = db.reference("admin_seating")
        seating_data = admin_seating_ref.get()

        if seating_data:
            for key, records in seating_data.items():
                if not records:
                    continue

                # Convert to dataframe
                df_group = pd.DataFrame(records)
                subject = df_group["Subject"].iloc[0]
                date = df_group["Date"].iloc[0]

                st.markdown(f"### 📘 {subject} — 📅 {date}")
                st.dataframe(df_group, use_container_width=True)

                # Delete button for this subject+date group
                if st.button(f"🗑 Delete Seating ({subject} on {date})", key=f"delete_{key}"):
                    del seating_data[key]
                    admin_seating_ref.set(seating_data)

                    # Remove from student seating too
                    for _, entry in df_group.iterrows():
                        student_ref = db.reference(f"seating/{entry['Registration Number']}")
                        student_data = student_ref.get()
                        if isinstance(student_data, list):
                            updated_data = [
                                d for d in student_data
                                if not (d["Subject"] == subject and d["Date"] == date)
                            ]
                            if updated_data:
                                student_ref.set(updated_data)
                            else:
                                student_ref.delete()

                    st.success(f"🗑 Deleted seating for {subject} on {date}")
                    st.rerun()

                st.markdown("---")

            # --- Delete All ---
            if st.button("🚨 Delete ALL Seating Data", key="delete_all_btn"):
                admin_seating_ref.delete()
                db.reference("seating").delete()
                st.error("⚠️ All seating data has been deleted!")
                st.rerun()

            # Style buttons
            st.markdown("""
                <style>
                /* Normal delete buttons */
                div.stButton > button {
                    background-color: #004080 !important;
                    color: white !important;
                    border-radius: 6px !important;
                    margin-bottom: 8px !important;
                }
                /* Delete ALL button */
                button#delete_all_btn {
                    background-color: #f44336 !important;
                    color: white !important;
                    font-weight: bold !important;
                    border-radius: 8px !important;
                }
                </style>
            """, unsafe_allow_html=True)

        else:
            st.info("ℹ️ No seating arrangements found yet.")




# --- STAFF ---
elif st.session_state.role == "staff":
    tabs = st.tabs(["Home", "Search & Lookup"])

    with tabs[0]:
        st.header("🧑‍🏫 Upload & Generate Seating")
        uploaded = st.file_uploader("Upload Student Excel", type=["xlsx"])
        if uploaded:
            st.session_state.df = pd.read_excel(uploaded)
            st.success("Student data uploaded.")
            st.write("🔍 Columns:", st.session_state.df.columns.tolist())

        if st.session_state.df is not None:
            df_norm = st.session_state.df.copy()
            df_norm.columns = df_norm.columns.str.lower().str.strip()
            st.session_state.df = df_norm

            subjects = detect_subject_columns(df_norm.columns.tolist())
            subject_map = {orig: norm for orig, norm in zip(st.session_state.df.columns, df_norm.columns) if norm in subjects}

            if subject_map:
                selected_label = st.selectbox("Select Subject", list(subject_map.keys()))
                st.session_state.selected_subject = subject_map[selected_label]

                classrooms = json.load(open(DATA_FILE))
                exam_date = st.date_input("Exam Date", value=datetime.today(), min_value=datetime.today())
                st.session_state.exam_time = st.time_input("Exam Time", value=st.session_state.exam_time)

                if st.button("Generate Seating"):
                    seating_df = distribute_students(
                        df_norm, st.session_state.selected_subject, classrooms, exam_date, st.session_state.exam_time
                    )
                    if not seating_df.empty:
                        st.session_state["seating_df"] = seating_df
                        admin_key = f"{st.session_state.selected_subject.upper()}_{exam_date.strftime('%Y-%m-%d')}"
                        db.reference(f"admin_seating/{admin_key}").set(seating_df.to_dict(orient="records"))

                        for _, row in seating_df.iterrows():
                            ref = db.reference(f"seating/{row['Registration Number']}")
                            existing = ref.get() or []
                            if isinstance(existing, dict): existing = [existing]
                            existing.append(row.to_dict())
                            ref.set(existing)

                        st.dataframe(seating_df)
                        csv = seating_df.to_csv(index=False).encode("utf-8")
                        st.download_button("Download CSV", csv, f"Seating_{st.session_state.selected_subject}_{exam_date}.csv", "text/csv")
            else:
                st.warning("No valid subject columns found.")

    with tabs[1]:
        st.header("Search & Lookup")
        sid = st.text_input("Registration Number to lookup")
        if st.button("Lookup"):
            if "registration number" in st.session_state.df.columns:
                row = st.session_state.df[
                    st.session_state.df["registration number"].astype(str).str.upper() == sid.strip().upper()
                ]
                st.write(row.to_dict(orient="records")[0] if not row.empty else "Not found.")

# --- STUDENT ---
elif st.session_state.role == "student":
    tabs = st.tabs(["Home", "Search & Lookup"])
    uid = st.session_state.student_id

    # --- Home Tab ---
    with tabs[0]:
        st.header("🎓 Your Exam Details")
        seatings = db.reference(f"seating/{uid}").get()

        if seatings:
            # Ensure it's a list
            if isinstance(seatings, dict):
                seatings = [seatings]

            df = pd.DataFrame(seatings)
            desired_order = ["Subject", "Date", "Time", "Classroom", "Row","Column", "Registration Number"]
            df = df[[col for col in desired_order if col in df.columns]]

            st.dataframe(df)  # show all exams

            # Pick first exam for visualization
            student_seat = df.iloc[0]  # first exam
            classroom_name = student_seat["Classroom"]

            # Fetch classroom dimensions from classrooms.json
            with open(DATA_FILE, "r") as f:
                classrooms = json.load(f)

            classroom_rows = classrooms.get(classroom_name, {}).get("rows", 4)
            classroom_cols = classrooms.get(classroom_name, {}).get("cols", 5)
            student_row = int(student_seat["Row"]) - 1  # 0-indexed
            student_col = int(student_seat["Column"]) - 1

            st.subheader(f"📍 Your Seat in {classroom_name}")
            visualize_seating(classroom_rows, classroom_cols, student_row, student_col)
        else:
            st.info("No seating info yet.")

    # --- Search Tab ---
    with tabs[1]:
        st.header("📄 Hall Ticket:- ")

st.markdown("""
    <style>
    /* General Styling */
    .stApp {
        background-color: #f9f9fb;
        font-family: 'Segoe UI', sans-serif;
    }

    h1, h2, h3, h4 {
        color: #003366;
        font-weight: 600;
    }

    /* Button Styling */
    .stButton>button {
        background-color: #004080;
        color: white;
        border: none;
        border-radius: 7px;
        padding: 0.5em 1em;
        margin-top: 1.5rem;
        transition: 0.3s ease-in-out;
    }

    .stButton>button:hover {
        background-color: #0059b3;
        transform: scale(1.02);
    }

    div.block-container{
        padding-top: 0rem; 
        padding-bottom: 0rem;
    }

    /* Tabs Styling */
    .stTabs [role="tablist"] {
        display: flex;
        border-radius: 10px;
        background: #ffffff;
        padding: 0.3rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        gap: 8px;
    }

    .stTabs [role="tab"] {
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        font-size: 16px;
        color: #333;
        font-weight: 500;
        background-color: #f0f2f5;
        transition: background-color 0.2s ease, transform 0.2s ease;
    }

    .stTabs [role="tab"]:hover {
        background-color: #dbe9ff;
        transform: scale(1.01);
    }

    .stTabs [role="tab"][aria-selected="true"] {
        background-color: #004080;
        color: white;
        box-shadow: 0 2px 4px rgba(0, 64, 128, 0.2);
    }

    /* Sidebar Styling */
    .css-1d391kg, .css-1lcbmhc {
        background-color: #eaf0f6 !important;
        border-radius: 10px;
        padding: 20px;
    }

    /* DataFrame & Table */
    .stDataFrame {
        border-radius: 12px;
        border: 1px solid #dfe2e5;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* Inputs */
    input, select, textarea {
        border-radius: 6px !important;
        border: 1px solid #ccd6dd !important;
    }
    </style>
""", unsafe_allow_html=True)
