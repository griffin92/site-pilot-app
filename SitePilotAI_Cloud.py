import streamlit as st
import google.generativeai as genai
from PIL import Image
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
import json, os, csv, io
from datetime import datetime
from fpdf import FPDF 

# --- 1. SETUP & SECURE API CONFIG ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("🚨 BACKEND ACCESS DENIED: Ensure your .streamlit/secrets.toml file is configured.")
    st.stop()

st.set_page_config(page_title="Site Pilot AI", layout="wide", page_icon="🏗️")

# --- 2. ENTERPRISE CSS (Adaptive Light/Dark Theme) ---
st.markdown("""
    <style>
    /* Main Buttons */
    .stButton>button { border-radius: 6px; font-weight: 600; background-color: var(--primary-color); color: white; border: none; width: 100%; transition: all 0.2s; height: 3em; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .stButton>button:hover { filter: brightness(1.15); transform: translateY(-1px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    
    /* Secondary/Clear Buttons */
    .btn-clear>button { background-color: transparent; color: var(--text-color); border: 1px solid rgba(128, 128, 128, 0.4); box-shadow: none; }
    .btn-clear>button:hover { background-color: rgba(128, 128, 128, 0.1); }
    
    /* Tool Cards (Adaptive Backgrounds) */
    .tool-card { padding: 25px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); background-color: var(--secondary-background-color); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px; color: var(--text-color); }
    .report-box { padding: 20px; border-radius: 6px; background-color: rgba(128, 128, 128, 0.05); border-left: 4px solid var(--primary-color); border-top: 1px solid rgba(128, 128, 128, 0.1); border-right: 1px solid rgba(128, 128, 128, 0.1); border-bottom: 1px solid rgba(128, 128, 128, 0.1); color: var(--text-color); margin-top: 15px; font-size: 0.95em; overflow-x: auto; }
    
    /* Headers (Adaptive Text) */
    .ref-header { background-color: var(--primary-color); color: white !important; padding: 8px 15px; border-radius: 6px 6px 0 0; font-weight: 600; font-size: 0.85em; letter-spacing: 0.5px; }
    .status-bar { padding: 12px 20px; border-radius: 8px; background-color: var(--secondary-background-color); border: 1px solid rgba(128, 128, 128, 0.2); color: var(--text-color); margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; font-weight: 500; }
    
    /* Typography (Inherits Theme Colors) */
    .hero-title { font-size: 3em; font-weight: 800; color: var(--text-color); margin-bottom: 0px; letter-spacing: -1px; }
    .hero-sub { font-size: 1.2em; opacity: 0.8; color: var(--text-color); margin-bottom: 40px; font-weight: 400; }
    .section-title { font-size: 1.4em; font-weight: 700; color: var(--text-color); margin-bottom: 5px; border-bottom: 2px solid rgba(128, 128, 128, 0.2); padding-bottom: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CORE UTILITIES ---
@st.cache_resource
def get_pdf_info(file_bytes):
    return pdfinfo_from_bytes(file_bytes)["Pages"]

@st.cache_data
def convert_single_page(file_bytes, page_num):
    return convert_from_bytes(file_bytes, first_page=page_num, last_page=page_num)[0]

def save_json(filename, data, suffix):
    with open(f"{filename}_{suffix}.json", 'w') as f: json.dump(data, f)

def load_json(filename, suffix, default):
    path = f"{filename}_{suffix}.json"
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, 'r') as f: return json.load(f)
    return default

def create_pdf_report(project_name, content, title):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"Project: {project_name}", ln=True, align='L')
    pdf.set_font("Arial", 'I', 12)
    pdf.cell(190, 10, f"Report: {title} | Generated: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='L')
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)
    
    def safe_write(text):
        pdf.set_font("Arial", '', 10)
        clean_t = text.replace('**', '').replace('### ', '').replace('## ', '').replace('# ', '')
        encoded_t = clean_t.encode('latin-1', 'ignore').decode('latin-1').replace('\t', '    ')
        words = [w[:80] + '-' + w[80:] if len(w) > 80 else w for w in encoded_t.split(' ')]
        pdf.multi_cell(190, 6, txt=' '.join(words))

    if isinstance(content, list): safe_write("\n".join([f"- {item}" for item in content]))
    else: safe_write(str(content))
        
    pdf_out = pdf.output(dest="S")
    if isinstance(pdf_out, str): return pdf_out.encode("latin-1")
    else: return bytes(pdf_out)

def run_ai_with_progress(file_bytes, target_pages, prompt_text, success_message="Task Complete!"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    d_imgs = []
    total_pages = len(target_pages)
    
    for idx, p_num in enumerate(target_pages):
        status_text.markdown(f"**⚙️ Extracting Page {p_num} of {total_pages}...**")
        d_imgs.append(convert_single_page(file_bytes, p_num))
        progress_bar.progress(int(((idx + 1) / total_pages) * 85))
        
    status_text.markdown("**🧠 Processing Document Intelligence...**")
    d_imgs.insert(0, prompt_text)
    
    model = genai.GenerativeModel('gemini-2.5-pro')
    res = model.generate_content(d_imgs)
    
    progress_bar.progress(100)
    status_text.success(f"✅ {success_message}")
    return res.text

# --- 4. SESSION INITIALIZATION ---
keys = [
    'audit_results', 'takeoff_results', 'schedule_results', 'schedule_csv', 'doc_intel_results', 'est_results', 'submittal_results',
    'drawing_index', 'audit_history', 'takeoff_history', 'schedule_history', 'intel_history', 'est_history', 'submittal_history',
    'current_file'
]
for k in keys:
    if k not in st.session_state: 
        st.session_state[k] = [] if 'history' in k or k in ['audit_results', 'takeoff_results', 'submittal_results'] else "" if k != 'drawing_index' else {}

# --- 5. ENHANCED SIDEBAR ---
with st.sidebar:
    st.markdown("## 🏗️ Site Pilot")
    st.caption("v18.3 Data Failsafe Build")
    st.divider()
    st.markdown("### 📋 Setup Checklist")
    uploaded_file = st.file_uploader("1️⃣ Base Drawings (.pdf)", type=["pdf"])
    spec_file = st.file_uploader("2️⃣ Project Manual/Specs (.pdf)", type=["pdf"])
    doc_file = st.file_uploader("3️⃣ Legal/Contracts (.pdf)", type=["pdf"])
    st.divider()
    st.info("💡 **Pro-Tip:** Upload all project documents before starting your workflow to allow seamless cross-referencing.")

# --- 6. DATA LOADER ---
if uploaded_file:
    if st.session_state.current_file != uploaded_file.name:
        st.session_state.current_file = uploaded_file.name
        fname = uploaded_file.name
        st.session_state.drawing_index = load_json(fname, "index", {})
        st.session_state.audit_results = load_json(fname, "audit", [])
        st.session_state.takeoff_results = load_json(fname, "takeoff", [])
        st.session_state.schedule_results = load_json(fname, "schedule", "")
        st.session_state.schedule_csv = load_json(fname, "schedule_csv", "")
        st.session_state.est_results = load_json(fname, "estimate", "")
        st.session_state.doc_intel_results = load_json(fname, "intel", "")
        st.session_state.submittal_results = load_json(fname, "submittals", [])
        
        st.session_state.audit_history = load_json(fname, "audit_history", [])
        st.session_state.takeoff_history = load_json(fname, "takeoff_history", [])
        st.session_state.schedule_history = load_json(fname, "schedule_history", [])
        st.session_state.est_history = load_json(fname, "est_history", [])
        st.session_state.intel_history = load_json(fname, "intel_history", [])
        st.session_state.submittal_history = load_json(fname, "submittal_history", [])
        st.rerun()
        
    file_bytes = uploaded_file.read(); total_pages = get_pdf_info(file_bytes)
    if not st.session_state.drawing_index:
        st.session_state.drawing_index = {str(i): f"Page {i}" for i in range(1, total_pages + 1)}
        save_json(uploaded_file.name, st.session_state.drawing_index, "index")

# --- 7. MAIN STAGE UI ---
if not uploaded_file:
    st.markdown('<div class="hero-title">Site Pilot</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">The AI Operating System for Commercial Construction.</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        st.markdown('<div class="tool-card"><h4>🗺️ VDC & Coordination</h4><p>Automate drawing indexing, run clash detection, and project master schedules.</p></div>', unsafe_allow_html=True)
    with c2: 
        st.markdown('<div class="tool-card"><h4>🧮 Estimating Engine</h4><p>Generate blind baseline estimates to verify subcontractor bids and protect margins.</p></div>', unsafe_allow_html=True)
    with c3: 
        st.markdown('<div class="tool-card"><h4>📋 Document Control</h4><p>Instantly extract submittal logs and summarize complex legal contracts.</p></div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="status-bar"><span>📂 <strong>Active Project:</strong> {st.session_state.current_file}</span><span>📄 <strong>Total Sheets:</strong> {total_pages}</span></div>', unsafe_allow_html=True)
    
    with st.expander("🗂️ AI Drawing Indexer (Title Block Extraction)"):
        st.markdown("Convert generic page numbers into structured sheet names (e.g., 'M-101 Mechanical Plan').")
        c_idx1, c_idx2 = st.columns([1, 4])
        with c_idx1:
            if st.button("🔍 Run Auto-Index"):
                idx_prog = st.progress(0); idx_stat = st.empty(); new_index = {}
                model = genai.GenerativeModel('gemini-2.5-pro')
                for i in range(1, total_pages + 1):
                    idx_stat.markdown(f"*Reading Page {i}...*")
                    img = convert_single_page(file_bytes, i)
                    try:
                        res = model.generate_content(["Extract the Sheet Number and Sheet Title from this title block. Output ONLY in this exact format: 'SheetNumber - SheetTitle'.", img])
                        new_index[str(i)] = res.text.strip().replace('\n', '').replace('**', '')
                    except:
                        new_index[str(i)] = f"Page {i}"
                    idx_prog.progress(int((i / total_pages) * 100))
                st.session_state.drawing_index = new_index
                save_json(uploaded_file.name, new_index, "index")
                idx_stat.success("✅ Indexing Complete!"); st.rerun()

    page_opts = list(st.session_state.drawing_index.values())
    tab_vdc, tab_est, tab_admin = st.tabs(["🗺️ Plan Room & VDC", "🧮 Estimating & Docs", "📋 Admin & Specs"])

    # --- TAB 1: PLAN ROOM ---
    with tab_vdc:
        st.markdown('<div class="tool-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Workspace Setup</div>', unsafe_allow_html=True)
        c_sel1, c_sel2 = st.columns([3, 1])
        with c_sel1:
            all_selected = st.checkbox("☑️ Select Entire Drawing Set")
            if all_selected: target_docs = st.multiselect("Target Sheets:", page_opts, default=page_opts, label_visibility="collapsed")
            else: target_docs = st.multiselect("Target Sheets:", page_opts, placeholder="Select sheets for VDC analysis...", label_visibility="collapsed")
        with c_sel2: 
            st.markdown('<div class="btn-clear">', unsafe_allow_html=True)
            if st.button("🧹 Clear Workspace"):
                st.session_state.audit_results = []; st.session_state.takeoff_results = []; st.session_state.schedule_results = ""; st.session_state.schedule_csv = ""
                save_json(uploaded_file.name, [], "audit"); save_json(uploaded_file.name, [], "takeoff"); save_json(uploaded_file.name, "", "schedule"); save_json(uploaded_file.name, "", "schedule_csv")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        c_view, c_tools = st.columns([1.5, 1])
        
        with c_view:
            st.markdown("#### 👁️ Sheet Viewer")
            selected_main = st.selectbox("Active View:", page_opts, label_visibility="collapsed")
            main_idx = int([k for k, v in st.session_state.drawing_index.items() if v == selected_main][0])
            st.markdown(f'<div class="ref-header">{selected_main}</div>', unsafe_allow_html=True)
            st.image(convert_single_page(file_bytes, main_idx), use_container_width=True)

        with c_tools:
            st.markdown("#### ⚙️ VDC Engines")
            
            st.markdown('<div class="tool-card" style="padding: 15px;">', unsafe_allow_html=True)
            if st.button("🚀 Run Clash Audit"):
                if target_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in target_docs]
                    res = run_ai_with_progress(file_bytes, p_scan, "Identify physical clashes or missing dimensions. Start each with 'ISSUE: '.", "Audit Complete!")
                    st.session_state.audit_results = [l.replace("ISSUE:", "").strip() for l in res.split("\n") if "ISSUE:" in l]
                    save_json(uploaded_file.name, st.session_state.audit_results, "audit")
                    st.session_state.audit_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": f"Audit ({len(target_docs)} sheets)", "results": st.session_state.audit_results})
                    save_json(uploaded_file.name, st.session_state.audit_history, "audit_history")
                else: st.warning("Select target sheets first.")
            if st.session_state.audit_results:
                st.markdown('<div class="report-box" style="border-left-color: #EF4444; padding: 10px;">', unsafe_allow_html=True)
                for issue in st.session_state.audit_results: st.write(f"🚩 {issue}")
                st.download_button("📥 Export PDF", create_pdf_report(st.session_state.current_file, st.session_state.audit_results, "Clash Audit"), "Audit.pdf", "application/pdf")
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="tool-card" style="padding: 15px;">', unsafe_allow_html=True)
            if st.button("📊 Material Takeoff"):
                if target_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in target_docs]
                    res = run_ai_with_progress(file_bytes, p_scan, "Perform strict material takeoff. Output continuous lines starting with 'TAKEOFF: '.", "Takeoff Complete!")
                    st.session_state.takeoff_results = [l.replace("TAKEOFF:", "").strip() for l in res.split("\n") if "TAKEOFF:" in l]
                    save_json(uploaded_file.name, st.session_state.takeoff_results, "takeoff")
                    st.session_state.takeoff_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": f"Takeoff ({len(target_docs)} sheets)", "results": st.session_state.takeoff_results})
                    save_json(uploaded_file.name, st.session_state.takeoff_history, "takeoff_history")
                else: st.warning("Select target sheets first.")
            if st.session_state.takeoff_results:
                st.markdown('<div class="report-box" style="border-left-color: #10B981; padding: 10px;">', unsafe_allow_html=True)
                for item in st.session_state.takeoff_results: st.write(f"📦 {item}")
                st.download_button("📥 Export PDF", create_pdf_report(st.session_state.current_file, st.session_state.takeoff_results, "Takeoff"), "Takeoff.pdf", "application/pdf")
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="tool-card" style="padding: 15px;">', unsafe_allow_html=True)
            if st.button("📅 Project Timeline"):
                if target_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in target_docs]
                    prompt = f"Analyze drawings. Today is {datetime.now().strftime('%b %d, %Y')}. Generate a projected chronological timeline with major phases."
                    st.session_state.schedule_results = run_ai_with_progress(file_bytes, p_scan, prompt, "Timeline Projected!")
                    st.session_state.schedule_csv = "" # Clear old CSV if any
                    save_json(uploaded_file.name, st.session_state.schedule_results, "schedule")
                    st.session_state.schedule_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": f"Timeline ({len(target_docs)} sheets)", "results": st.session_state.schedule_results})
                    save_json(uploaded_file.name, st.session_state.schedule_history, "schedule_history")
                else: st.warning("Select target sheets first.")
            
            if st.session_state.schedule_results:
                st.markdown('<div class="report-box" style="padding: 10px;">', unsafe_allow_html=True)
                st.markdown(st.session_state.schedule_results)
                
                # Secondary Expansion Tools
                c_sh1, c_sh2 = st.columns(2)
                with c_sh1:
                    st.download_button("📥 Export Narrative PDF", create_pdf_report(st.session_state.current_file, st.session_state.schedule_results, "Timeline"), "Timeline.pdf", "application/pdf")
                with c_sh2:
                    if st.button("📊 Expand to Excel/CSV", key="exp_csv"):
                        with st.spinner("Calculating line-item durations..."):
                            model = genai.GenerativeModel('gemini-2.5-pro')
                            prompt = f"Take this narrative schedule and expand it into a granular line-item schedule. Estimate duration in days. Output STRICTLY as a raw CSV format with columns: Phase, Task Name, Duration (Days), Predecessors. Do not use markdown blocks.\n\n{st.session_state.schedule_results}"
                            res = model.generate_content(prompt)
                            st.session_state.schedule_csv = res.text.replace('```csv', '').replace('```', '').strip()
                            save_json(uploaded_file.name, st.session_state.schedule_csv, "schedule_csv")
                            st.rerun()

                if st.session_state.get('schedule_csv'):
                    st.divider()
                    st.markdown("**Detailed Tabular Schedule**")
                    st.download_button("📥 Download Excel (.csv)", st.session_state.schedule_csv, "Detailed_Schedule.csv", "text/csv", type="primary")
                    try:
                        reader = csv.reader(io.StringIO(st.session_state.schedule_csv))
                        data = list(reader)
                        if len(data) > 1:
                            header = data[0]
                            md = f"| {' | '.join(header)} |\n| {' | '.join(['---']*len(header))} |\n"
                            for row in data[1:]:
                                row_clean = [col.replace('|', '-') for col in row]
                                md += f"| {' | '.join(row_clean)} |\n"
                            st.markdown(md)
                    except:
                        st.info("Preview unavailable. Please download the CSV file.")

                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        with st.expander("🗄️ VDC Archives (Project Ledger)"):
            ha1, ha2, ha3 = st.columns(3)
            with ha1:
                st.markdown("**Audits**")
                for i, e in enumerate(st.session_state.audit_history):
                    with st.popover(f"🕒 {e['time']} | {e['desc']}"):
                        for item in e['results']: st.write(f"- {item}")
                        pdf_bytes = create_pdf_report(st.session_state.current_file, e['results'], f"Clash Audit ({e['time']})")
                        st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Audit_Archive_{i}.pdf", mime="application/pdf", key=f"dl_a_hist_{i}")
            with ha2:
                st.markdown("**Takeoffs**")
                for i, e in enumerate(st.session_state.takeoff_history):
                    with st.popover(f"🕒 {e['time']} | {e['desc']}"):
                        for item in e['results']: st.write(f"- {item}")
                        pdf_bytes = create_pdf_report(st.session_state.current_file, e['results'], f"Material Takeoff ({e['time']})")
                        st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Takeoff_Archive_{i}.pdf", mime="application/pdf", key=f"dl_t_hist_{i}")
            with ha3:
                st.markdown("**Timelines**")
                for i, e in enumerate(st.session_state.schedule_history):
                    with st.popover(f"🕒 {e['time']} | {e['desc']}"): 
                        st.markdown(e['results'])
                        pdf_bytes = create_pdf_report(st.session_state.current_file, e['results'], f"Project Timeline ({e['time']})")
                        st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Timeline_Archive_{i}.pdf", mime="application/pdf", key=f"dl_s_hist_{i}")

    # --- TAB 2: ESTIMATING & DOCS ---
    with tab_est:
        col_est, col_doc = st.columns([1.2, 1])
        
        with col_est:
            st.markdown('<div class="tool-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">🧮 AI Estimator</div>', unsafe_allow_html=True)
            st.caption("Generate detailed, trade-grouped cost estimates based on drawing geometry and standardized market rates.")
            
            c_e1, c_e2 = st.columns(2)
            with c_e1:
                est_all = st.checkbox("☑️ Full Plan Set", key="est_all_box")
                if est_all: t_est_docs = st.multiselect("Sheets:", page_opts, default=page_opts, label_visibility="collapsed", key="e_all")
                else: t_est_docs = st.multiselect("Sheets:", page_opts, placeholder="Select sheets...", label_visibility="collapsed", key="e_some")
            with c_e2: loc_multiplier = st.selectbox("Pricing Region:", ["National Average", "DMV Area (DC/MD/VA)", "New York", "Southeast"], label_visibility="collapsed")

            if st.button("🧮 Generate Baseline Estimate"):
                if t_est_docs:
                    p_scan = [int([k for k, v in st.session_state.drawing_index.items() if v == d][0]) for d in t_est_docs]
                    prompt = f"Act as an independent Chief Estimator. Location: {loc_multiplier}. Perform a detailed quantity takeoff. Apply standard industry pricing for materials and labor. Group findings by Trade or CSI Division. List scope items, quantities, and unit costs. Conclude with a budget summary (Subtotal, GC Fees, Contingency). You are a blind 3rd party. Format in Markdown."
                    st.session_state.est_results = run_ai_with_progress(file_bytes, p_scan, prompt, "Estimate Generated!")
                    save_json(uploaded_file.name, st.session_state.est_results, "estimate")
                    st.session_state.est_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": f"Estimate - {loc_multiplier}", "results": st.session_state.est_results})
                    save_json(uploaded_file.name, st.session_state.est_history, "est_history")
                else: st.warning("Select sheets to estimate.")

            if st.session_state.est_results:
                st.markdown(f'<div class="report-box">{st.session_state.est_results}</div>', unsafe_allow_html=True)
                st.download_button("📥 Export Estimate PDF", create_pdf_report(st.session_state.current_file, st.session_state.est_results, f"Baseline Estimate ({loc_multiplier})"), "Estimate.pdf", "application/pdf")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_doc:
            st.markdown('<div class="tool-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">📄 Document Intelligence</div>', unsafe_allow_html=True)
            st.caption("Summarize complex external PDFs (Contracts, RFIs, Geotech) uploaded in Slot 3.")
            
            if doc_file:
                if st.button("🔍 Analyze Document"):
                    d_bytes = doc_file.read(); p_scan = list(range(1, get_pdf_info(d_bytes) + 1))
                    prompt = "Analyze this document. Provide a comprehensive summary including its primary purpose, key data points, financial impacts, and critical risks the project team should be aware of."
                    st.session_state.doc_intel_results = run_ai_with_progress(d_bytes, p_scan, prompt, "Document Summarized!")
                    save_json(uploaded_file.name, st.session_state.doc_intel_results, "intel")
                    st.session_state.intel_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": f"Doc: {doc_file.name}", "results": st.session_state.doc_intel_results})
                    save_json(uploaded_file.name, st.session_state.intel_history, "intel_history")
                
                if st.session_state.doc_intel_results: 
                    st.markdown(f'<div class="report-box" style="border-left-color: #8B5CF6;">{st.session_state.doc_intel_results}</div>', unsafe_allow_html=True)
                    st.download_button("📥 Export Summary PDF", create_pdf_report(st.session_state.current_file, st.session_state.doc_intel_results, "Document Summary"), "Doc_Summary.pdf", "application/pdf")
            else:
                st.info("Upload a document in Slot 3 to enable intelligence.")
                
            st.divider()
            st.markdown('<div class="btn-clear">', unsafe_allow_html=True)
            if st.button("🧹 Clear Financial Workspace"):
                st.session_state.est_results = ""; st.session_state.doc_intel_results = ""
                save_json(uploaded_file.name, "", "estimate"); save_json(uploaded_file.name, "", "intel"); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        with st.expander("🗄️ Financial Archives (Project Ledger)"):
            he1, he2 = st.columns(2)
            with he1:
                st.markdown("**Estimates**")
                for i, e in enumerate(st.session_state.est_history):
                    with st.popover(f"🕒 {e['time']} | {e['desc']}"): 
                        st.markdown(e['results'])
                        pdf_bytes = create_pdf_report(st.session_state.current_file, e['results'], f"Baseline Estimate ({e['time']})")
                        st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Estimate_Archive_{i}.pdf", mime="application/pdf", key=f"dl_e_hist_{i}")
            with he2:
                st.markdown("**Document Scans**")
                for i, e in enumerate(st.session_state.intel_history):
                    with st.popover(f"🕒 {e['time']} | {e['desc']}"): 
                        st.markdown(e['results'])
                        pdf_bytes = create_pdf_report(st.session_state.current_file, e['results'], f"Document Summary ({e['time']})")
                        st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"DocScan_Archive_{i}.pdf", mime="application/pdf", key=f"dl_doc_hist_{i}")

    # --- TAB 3: ADMIN & SPECS ---
    with tab_admin:
        st.markdown('<div class="tool-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📋 Submittal Engine</div>', unsafe_allow_html=True)
        st.caption("Deep-scan Project Manuals (Slot 2) to automatically generate comprehensive Submittal and Shop Drawing registers.")
        
        if spec_file:
            if st.button("🚀 Generate Submittal Register"):
                s_bytes = spec_file.read(); s_total = get_pdf_info(s_bytes)
                p_scan = list(range(1, s_total + 1, 5 if s_total < 50 else 10))
                prompt = "Act as a Project Engineer. Scan these specs for 'Submittal' requirements. Create a list of Shop Drawings, Product Data, and Samples required. CRITICAL RULE: Format every single item as a continuous line starting exactly with 'SUBMITTAL: '."
                res = run_ai_with_progress(s_bytes, p_scan, prompt, "Register Generated!")
                st.session_state.submittal_results = [l.replace("SUBMITTAL:", "").strip() for l in res.split("\n") if "SUBMITTAL:" in l]
                save_json(uploaded_file.name, st.session_state.submittal_results, "submittals")
                st.session_state.submittal_history.insert(0, {"time": datetime.now().strftime("%I:%M %p"), "desc": "Submittal Scan", "results": st.session_state.submittal_results})
                save_json(uploaded_file.name, st.session_state.submittal_history, "submittal_history")
            
            if st.session_state.submittal_results:
                st.markdown('<div class="report-box" style="border-left-color: #F59E0B;">', unsafe_allow_html=True)
                for item in st.session_state.submittal_results: st.write(f"📁 {item}")
                st.download_button("📥 Export Submittal Register PDF", create_pdf_report(st.session_state.current_file, st.session_state.submittal_results, "Submittal Register"), "Submittals.pdf", "application/pdf")
                st.markdown('</div>', unsafe_allow_html=True)
                
            st.divider()
            st.markdown('<div class="btn-clear">', unsafe_allow_html=True)
            if st.button("🧹 Clear Admin Workspace"):
                st.session_state.submittal_results = []; save_json(uploaded_file.name, [], "submittals"); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Upload Specifications in Slot 2 to enable Submittal scanning.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        with st.expander("🗄️ Admin Archives (Project Ledger)"):
            st.markdown("**Submittal Registers**")
            for i, e in enumerate(st.session_state.submittal_history):
                with st.popover(f"🕒 {e['time']} | {e['desc']}"):
                    for item in e['results']: st.write(f"- {item}")
                    pdf_bytes = create_pdf_report(st.session_state.current_file, e['results'], f"Submittal Register ({e['time']})")
                    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Submittal_Archive_{i}.pdf", mime="application/pdf", key=f"dl_sub_hist_{i}")
