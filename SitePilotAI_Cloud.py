import streamlit as st
from google import genai
from PIL import Image
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
import json
import os
import csv
import io
from datetime import datetime
from fpdf import FPDF 
from fpdf.enums import XPos, YPos

# ==========================================
# 1. PAGE CONFIG (MUST BE FIRST COMMAND)
# ==========================================
st.set_page_config(page_title="Site Pilot AI", layout="wide", page_icon="🏗️")

# ==========================================
# 2. SETUP & SECURE API CONFIGURATION
# ==========================================
try:
    ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("🚨 CONFIGURATION ERROR: GEMINI_API_KEY not found in Streamlit Cloud Secrets. Please add it to your app settings.")
    st.stop()

# ==========================================
# 3. ENTERPRISE ADAPTIVE CSS
# ==========================================
st.markdown("""
    <style>
    .stButton>button { border-radius: 6px; font-weight: 600; background-color: var(--primary-color); color: white; border: none; width: 100%; transition: all 0.2s; height: 3em; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .stButton>button:hover { filter: brightness(1.15); transform: translateY(-1px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .btn-clear>button { background-color: transparent; color: var(--text-color); border: 1px solid rgba(128, 128, 128, 0.4); box-shadow: none; }
    .btn-clear>button:hover { background-color: rgba(128, 128, 128, 0.1); }
    .tool-card { padding: 25px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); background-color: var(--secondary-background-color); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px; color: var(--text-color); }
    .report-box { padding: 20px; border-radius: 6px; background-color: rgba(128, 128, 128, 0.05); border-left: 4px solid var(--primary-color); border-top: 1px solid rgba(128, 128, 128, 0.1); border-right: 1px solid rgba(128, 128, 128, 0.1); border-bottom: 1px solid rgba(128, 128, 128, 0.1); color: var(--text-color); margin-top: 15px; font-size: 0.95em; overflow-x: auto; }
    .ref-header { background-color: var(--primary-color); color: white !important; padding: 8px 15px; border-radius: 6px 6px 0 0; font-weight: 600; font-size: 0.85em; letter-spacing: 0.5px; }
    .status-bar { padding: 12px 20px; border-radius: 8px; background-color: var(--secondary-background-color); border: 1px solid rgba(128, 128, 128, 0.2); color: var(--text-color); margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; font-weight: 500; }
    .hero-title { font-size: 3em; font-weight: 800; color: var(--text-color); margin-bottom: 0px; letter-spacing: -1px; }
    .hero-sub { font-size: 1.2em; opacity: 0.8; color: var(--text-color); margin-bottom: 40px; font-weight: 400; }
    .section-title { font-size: 1.4em; font-weight: 700; color: var(--text-color); margin-bottom: 5px; border-bottom: 2px solid rgba(128, 128, 128, 0.2); padding-bottom: 8px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. CLOUD-READY UTILITIES
# ==========================================
@st.cache_resource
def get_pdf_info(file_bytes):
    return pdfinfo_from_bytes(file_bytes)["Pages"]

@st.cache_data
def convert_single_page(file_bytes, page_num):
    # Added size compression: limits width to 1600px to prevent server RAM crashes
    return convert_from_bytes(file_bytes, first_page=page_num, last_page=page_num, size=(1600, None))[0]

def create_pdf_report(project_name, content, title):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(190, 10, f"Project: {project_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.set_font("helvetica", 'I', 12)
    pdf.cell(190, 10, f"Report: {title} | Generated: {datetime.now().strftime('%Y-%m-%d')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)
    
    def safe_write(text):
        pdf.set_font("helvetica", '', 10)
        clean_t = str(text).replace('**', '').replace('### ', '').replace('## ', '').replace('# ', '')
        encoded_t = clean_t.encode('latin-1', 'ignore').decode('latin-1').replace('\t', '    ')
        words = [w[:80] + '-' + w[80:] if len(w) > 80 else w for w in encoded_t.split(' ')]
        pdf.multi_cell(190, 6, text=' '.join(words))

    if isinstance(content, list): safe_write("\n".join([f"- {item}" for item in content]))
    else: safe_write(str(content))
        
    return bytes(pdf.output())

def run_ai_with_progress(file_bytes, target_pages, prompt_text, success_message="Task Complete!"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    d_imgs = []
    total_pages = len(target_pages)
    
    for idx, p_num in enumerate(target_pages):
        status_text.markdown(f"**⚙️ Processing Document Data (Page {p_num})...**")
        d_imgs.append(convert_single_page(file_bytes, p_num))
        progress_bar.progress(int(((idx + 1) / total_pages) * 85))
        
    status_text.markdown("**🧠 AI Engine Reviewing Scope...**")
    d_imgs.insert(0, prompt_text)
    
    response = ai_client.models.generate_content(
        model='gemini-2.5-pro',
        contents=d_imgs
    )
    
    progress_bar.progress(100)
    status_text.success(f"✅ {success_message}")
    return response.text

# ==========================================
# 5. SESSION INITIALIZATION
# ==========================================
keys_to_initialize = [
    'audit_results', 'takeoff_results', 'schedule_results', 'schedule_csv', 
    'doc_intel_results', 'est_results', 'submittal_results', 'drawing_index', 
    'audit_history', 'takeoff_history', 'schedule_history', 'intel_history', 
    'est_history', 'submittal_history', 'current_file', 'loaded_save_id'
]

for key in keys_to_initialize:
    if key not in st.session_state: 
        if 'history' in key or key in ['audit_results', 'takeoff_results', 'submittal_results']:
            st.session_state[key] = []
        elif key == 'drawing_index':
            st.session_state[key] = {}
        else:
            st.session_state[key] = ""

# ==========================================
# 6. SIDEBAR & SAVE SYSTEM
# ==========================================
with st.sidebar:
    st.markdown("## 🏗️ Site Pilot")
    st.caption("Enterprise OS v22.1")
    st.divider()
    
    st.markdown("### 📋 Document Uploads")
    uploaded_file = st.file_uploader("1️⃣ Base Drawings (.pdf)", type=["pdf"])
    spec_file = st.file_uploader("2️⃣ Project Specs (.pdf)", type=["pdf"])
    doc_file = st.file_uploader("3️⃣ Legal/Contracts (.pdf)", type=["pdf"])
    
    st.divider()
    st.markdown("### 💾 Save & Restore")
    save_file = st.file_uploader("4️⃣ Restore Project (.json)", type=["json"], help="Upload a previously downloaded save file here to restore your work.")
    
    # Export Current State to JSON
    export_state = {k: st.session_state[k] for k in keys_to_initialize if k in st.session_state and k != 'loaded_save_id'}
    json_state = json.dumps(export_state)
    
    st.download_button(
        label="💾 Download Save File",
        data=json_state,
        file_name=f"SitePilot_Save_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json",
        type="primary"
    )

# ==========================================
# 7. CLOUD MEMORY LOGIC
# ==========================================
# Handle new PDF uploads (Wipe old data if it's a completely new project)
if uploaded_file and st.session_state.current_file != uploaded_file.name:
    st.session_state.current_file = uploaded_file.name
    # Only wipe if we aren't actively restoring a save file
    if save_file is None or st.session_state.loaded_save_id != save_file.file_id:
        st.session_state.drawing_index = {}
        for h in ['audit', 'takeoff', 'schedule', 'est', 'intel', 'submittal']:
            st.session_state[f"{h}_history"] = []
            st.session_state[f"{h}_results"] = [] if h in ['audit', 'takeoff', 'submittal'] else ""
        st.session_state.schedule_csv = ""
    st.rerun()

# Handle Save File Restoration (Bulletproof JSON decode)
if save_file and st.session_state.loaded_save_id != save_file.file_id:
    try:
        saved_data = json.loads(save_file.getvalue().decode("utf-8"))
        for k, v in saved_data.items():
            st.session_state[k] = v
        st.session_state.loaded_save_id = save_file.file_id
        st.success("✅ Project state restored successfully!")
        st.rerun()
    except Exception as e:
        st.error("🚨 Invalid save file. Please upload a valid Site Pilot JSON.")

# ==========================================
# 8. MAIN LOGIC
# ==========================================
if uploaded_file:
    file_bytes = uploaded_file.read()
    total_pages = get_pdf_info(file_bytes)
    
    if not st.session_state.drawing_index:
        st.session_state.drawing_index = {str(i): f"Page {i}" for i in range(1, total_pages + 1)}

    st.markdown(f'<div class="status-bar"><span>📂 <strong>Project:</strong> {st.session_state.current_file}</span><span>📄 <strong>Total Sheets:</strong> {total_pages}</span></div>', unsafe_allow_html=True)

    with st.expander("🗂️ AI Drawing Indexer", expanded=False):
        st.markdown("Extract sheet names from title blocks to automatically rename dropdown menus.")
        c_idx1, c_idx2 = st.columns([1, 4])
        with c_idx1:
            if st.button("🔍 Run Auto-Index"):
                idx_prog = st.progress(0); idx_stat = st.empty(); new_index = {}
                for i in range(1, total_pages + 1):
                    img = convert_single_page(file_bytes, i)
                    try:
                        prompt = "Extract the Sheet Number and Sheet Title from this title block. Output ONLY in this exact format: 'SheetNumber - SheetTitle'."
                        res = ai_client.models.generate_content(model='gemini-2.5-pro', contents=[prompt, img])
                        new_index[str(i)] = res.text.strip().replace('\n', '')
                    except: new_index[str(i)] = f"Page {i}"
                    idx_prog.progress(int((i / total_pages) * 100))
                st.session_state.drawing_index = new_index
                idx_stat.success("✅ Indexing Complete!")
                st.rerun()

    page_opts = list(st.session_state.drawing_index.values())
    tab_vdc, tab_est, tab_admin = st.tabs(["🗺️ Plan Room & VDC", "🧮 Estimating & Docs", "📋 Admin & Specs"])

    # --- TAB 1: PLAN ROOM ---
    with tab_vdc:
        st.markdown('<div class="tool-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Workspace Setup</div>', unsafe_allow_html=True)
        c_sel1, c_sel2 = st.columns([3, 1])
        with c_sel1:
            all_selected = st.checkbox("☑️ Select Entire Drawing Set")
            default_selection = page_opts if all_selected else []
            target_docs = st.multiselect("Target Sheets:", page_opts, default=default_selection, label_visibility="collapsed")
        with c_sel2: 
            st.markdown('<div class="btn-clear">', unsafe_allow_html=True)
            if st.button("🧹 Clear Workspace"):
                st.session_state.audit_results = []; st.session_state.takeoff_results = []
                st.session_state.schedule_results = ""; st.session_state.schedule_csv = ""
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        c_view, c_tools = st.columns([1.5, 1])
        with c_view:
            st.markdown("#### 👁️ Sheet Viewer")
            selected_main = st.selectbox("Active View:", page_opts, label_visibility="collapsed")
            main_idx = int([k for k, v in st.session_state.drawing_index.items() if v == selected_main][0])
            st.markdown(f'<div class="ref-header">{selected_main}</div>', unsafe_allow_html=True)
            st.image(convert_single_page(file_bytes, main_idx), width='stretch')

        with c_tools:
            st.markdown("#### ⚙️ VDC Engines")
            # Clash Engine
            st.markdown('<div class="tool-card" style="padding: 15px;">', unsafe_allow_html=True)
            if st.button("🚀 Run Clash Audit"):
                if target_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in target_docs]
                    
                    # The upgraded "Superintendent" Prompt
                    clash_prompt = """
                    Act as a veteran Commercial Construction Superintendent. Analyze these drawings for critical, project-halting constructability issues. 
                    
                    CRITICAL INSTRUCTION: IGNORE minor drafting errors, text overlaps, or missing standard dimensions. 
                    
                    FOCUS EXCLUSIVELY ON THE FOLLOWING:
                    1. Structural vs. MEP Clashes: (e.g., ductwork, grease lines, or plumbing trenches intersecting footings, steel beams, or shear walls).
                    2. Architectural vs. MEP Clashes: (e.g., drop ceiling heights that do not leave enough plenum space for specified HVAC equipment).
                    3. Code & Life Safety: (e.g., egress paths blocked by door swings, missing fire-rated partitions).
                    4. Missing Critical Details: (e.g., missing slab depression dimensions, missing structural grid tie-ins).
                    
                    Output only the major, expensive issues. Start every single line strictly with 'ISSUE: '. Be brief and punchy.
                    """
                    
                    res = run_ai_with_progress(file_bytes, p_scan, clash_prompt, "Audit Complete!")
                    st.session_state.audit_results = [l.replace("ISSUE:", "").strip() for l in res.split("\n") if "ISSUE:" in l]
                    st.session_state.audit_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": "Audit", "results": st.session_state.audit_results})
                else: 
                    st.warning("Please select sheets first.")
                    
            if st.session_state.audit_results:
                st.markdown('<div class="report-box" style="border-left-color: #EF4444; padding: 10px;">', unsafe_allow_html=True)
                for issue in st.session_state.audit_results: st.write(f"🚩 {issue}")
                st.download_button("📥 Export PDF", create_pdf_report(st.session_state.current_file, st.session_state.audit_results, "Clash Audit"), "Audit.pdf", "application/pdf")
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Takeoff Engine
            st.markdown('<div class="tool-card" style="padding: 15px;">', unsafe_allow_html=True)
            if st.button("📊 Material Takeoff"):
                if target_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in target_docs]
                    res = run_ai_with_progress(file_bytes, p_scan, "Perform detailed material takeoff. Output continuous lines starting with 'TAKEOFF: '.", "Takeoff Complete!")
                    st.session_state.takeoff_results = [l.replace("TAKEOFF:", "").strip() for l in res.split("\n") if "TAKEOFF:" in l]
                    st.session_state.takeoff_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": "Takeoff", "results": st.session_state.takeoff_results})
                else: st.warning("Please select sheets first.")
            if st.session_state.takeoff_results:
                st.markdown('<div class="report-box" style="border-left-color: #10B981; padding: 10px;">', unsafe_allow_html=True)
                for item in st.session_state.takeoff_results: st.write(f"📦 {item}")
                st.download_button("📥 Export PDF", create_pdf_report(st.session_state.current_file, st.session_state.takeoff_results, "Takeoff"), "Takeoff.pdf", "application/pdf")
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Timeline Engine
            st.markdown('<div class="tool-card" style="padding: 15px;">', unsafe_allow_html=True)
            if st.button("📅 Project Timeline"):
                if target_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in target_docs]
                    prompt = f"Analyze drawings. Today is {datetime.now().strftime('%b %d, %Y')}. Generate projected chronological timeline."
                    st.session_state.schedule_results = run_ai_with_progress(file_bytes, p_scan, prompt, "Timeline Generated!")
                    st.session_state.schedule_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": "Timeline", "results": st.session_state.schedule_results})
                else: st.warning("Please select sheets first.")
            if st.session_state.schedule_results:
                st.markdown('<div class="report-box" style="padding: 10px;">', unsafe_allow_html=True)
                st.markdown(st.session_state.schedule_results)
                if st.button("📊 Expand to Excel/CSV", key="exp_csv"):
                    with st.spinner("Processing Gantt Data..."):
                        prompt = f"Convert this timeline to raw CSV format: Phase, Task Name, Duration (Days), Predecessors.\n\n{st.session_state.schedule_results}"
                        res = ai_client.models.generate_content(model='gemini-2.5-pro', contents=prompt)
                        st.session_state.schedule_csv = res.text.replace('```csv', '').replace('```', '').strip()
                        st.rerun()
                if st.session_state.schedule_csv:
                    st.download_button("📥 Download Excel (.csv)", st.session_state.schedule_csv, "Schedule.csv", "text/csv")
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        with st.expander("🗄️ VDC Archives (Recall Past Scans)"):
            ha1, ha2, ha3 = st.columns(3)
            with ha1:
                st.markdown("**Clash Audits**")
                for i, e in enumerate(st.session_state.audit_history):
                    with st.popover(f"🕒 {e['time']} Audit"):
                        for item in e['results']: st.write(f"- {item}")
                        st.download_button("📥 Download PDF", create_pdf_report(st.session_state.current_file, e['results'], "Audit"), f"Audit_{i}.pdf", key=f"dla_{i}")
            with ha2:
                st.markdown("**Material Takeoffs**")
                for i, e in enumerate(st.session_state.takeoff_history):
                    with st.popover(f"🕒 {e['time']} Takeoff"):
                        for item in e['results']: st.write(f"- {item}")
                        st.download_button("📥 Download PDF", create_pdf_report(st.session_state.current_file, e['results'], "Takeoff"), f"Takeoff_{i}.pdf", key=f"dlt_{i}")
            with ha3:
                st.markdown("**Project Timelines**")
                for i, e in enumerate(st.session_state.schedule_history):
                    with st.popover(f"🕒 {e['time']} Timeline"):
                        st.markdown(e['results'])
                        st.download_button("📥 Download PDF", create_pdf_report(st.session_state.current_file, e['results'], "Timeline"), f"Timeline_{i}.pdf", key=f"dls_{i}")

    # --- TAB 2: ESTIMATING ---
    with tab_est:
        col_est, col_doc = st.columns([1.2, 1])
        with col_est:
            st.markdown('<div class="tool-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">🧮 AI Estimator</div>', unsafe_allow_html=True)
            loc_multiplier = st.selectbox("Pricing Region:", ["National Average", "DMV Area (DC/MD/VA)", "New York", "Southeast"])
            if st.button("🧮 Generate Baseline Estimate"):
                if target_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in target_docs]
                    prompt = f"Act as independent Chief Estimator. Location: {loc_multiplier}. Generate a trade-grouped estimate with line items and a budget summary. Format: Markdown."
                    st.session_state.est_results = run_ai_with_progress(file_bytes, p_scan, prompt, "Estimate Complete!")
                    st.session_state.est_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": loc_multiplier, "results": st.session_state.est_results})
                else: st.warning("Please return to the VDC tab and select target sheets.")
            if st.session_state.est_results:
                st.markdown(f'<div class="report-box">{st.session_state.est_results}</div>', unsafe_allow_html=True)
                st.download_button("📥 Export Estimate PDF", create_pdf_report(st.session_state.current_file, st.session_state.est_results, "Estimate"), "Estimate.pdf", "application/pdf")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_doc:
            st.markdown('<div class="tool-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">📄 Document Intelligence</div>', unsafe_allow_html=True)
            if doc_file:
                if st.button("🔍 Analyze Document"):
                    d_bytes = doc_file.read()
                    p_scan = list(range(1, get_pdf_info(d_bytes) + 1))
                    prompt = "Summarize the primary purpose, key data points, financial impacts, and critical risks in this document."
                    st.session_state.doc_intel_results = run_ai_with_progress(d_bytes, p_scan, prompt, "Document Scanned!")
                    st.session_state.intel_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": doc_file.name, "results": st.session_state.doc_intel_results})
                if st.session_state.doc_intel_results: 
                    st.markdown(f'<div class="report-box" style="border-left-color: #8B5CF6;">{st.session_state.doc_intel_results}</div>', unsafe_allow_html=True)
                    st.download_button("📥 Export Summary PDF", create_pdf_report(st.session_state.current_file, st.session_state.doc_intel_results, "Doc Summary"), "Summary.pdf", "application/pdf")
            else: st.info("Upload a secondary PDF to Slot 3 in the sidebar.")
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        with st.expander("🗄️ Estimating & Doc Archives"):
            ea1, ea2 = st.columns(2)
            with ea1:
                st.markdown("**Estimates**")
                for i, e in enumerate(st.session_state.est_history):
                    with st.popover(f"🕒 {e['time']} | {e['desc']}"):
                        st.markdown(e['results'])
                        st.download_button("📥 PDF", create_pdf_report(st.session_state.current_file, e['results'], "Estimate"), f"Est_{i}.pdf", key=f"dle_{i}")
            with ea2:
                st.markdown("**Document Summaries**")
                for i, e in enumerate(st.session_state.intel_history):
                    with st.popover(f"🕒 {e['time']} | {e['desc']}"):
                        st.markdown(e['results'])
                        st.download_button("📥 PDF", create_pdf_report(st.session_state.current_file, e['results'], "Summary"), f"Doc_{i}.pdf", key=f"dli_{i}")

    # --- TAB 3: ADMIN ---
    with tab_admin:
        st.markdown('<div class="tool-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📋 Submittal Engine</div>', unsafe_allow_html=True)
        if spec_file:
            if st.button("🚀 Generate Submittal Register"):
                s_bytes = spec_file.read(); s_total = get_pdf_info(s_bytes)
                p_scan = list(range(1, s_total + 1, 10))
                prompt = "List required Shop Drawings, Product Data, and Samples. Start each with 'SUBMITTAL: '."
                res = run_ai_with_progress(s_bytes, p_scan, prompt, "Register Generated!")
                st.session_state.submittal_results = [l.replace("SUBMITTAL:", "").strip() for l in res.split("\n") if "SUBMITTAL:" in l]
                st.session_state.submittal_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": "Scan", "results": st.session_state.submittal_results})
            if st.session_state.submittal_results:
                st.markdown('<div class="report-box" style="border-left-color: #F59E0B;">', unsafe_allow_html=True)
                for s in st.session_state.submittal_results: st.write(f"📁 {s}")
                st.markdown('</div>', unsafe_allow_html=True)
                st.download_button("📥 Export Submittal Log PDF", create_pdf_report(st.session_state.current_file, st.session_state.submittal_results, "Submittal Register"), "Submittals.pdf", "application/pdf")
        else: st.info("Upload Specifications in Slot 2 to enable Submittal scanning.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        with st.expander("🗄️ Admin Archives"):
            st.markdown("**Submittal Registers**")
            for i, e in enumerate(st.session_state.submittal_history):
                with st.popover(f"🕒 {e['time']} Register"):
                    for item in e['results']: st.write(f"- {item}")
                    st.download_button("📥 PDF", create_pdf_report(st.session_state.current_file, e['results'], "Submittal Log"), f"Sub_{i}.pdf", key=f"dls_{i}")

# ==========================================
# 8. LANDING PAGE
# ==========================================
else:
    st.markdown('<div style="text-align:center; padding:100px;">', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">🏗️ Site Pilot AI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="hero-sub">Upload base drawings in the sidebar to initialize the project environment.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)







