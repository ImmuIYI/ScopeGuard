import streamlit as st
from supabase import create_client
import google.generativeai as genai
from pypdf import PdfReader
import time

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="ScopeGuard", page_icon="🛡️", layout="wide")

# --- SESSION PERSISTENCE FIX ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets missing. Please configure .streamlit/secrets.toml")
    st.stop()

# Initialize connection
if 'supabase' not in st.session_state:
    st.session_state['supabase'] = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = st.session_state['supabase']

# Initialize State
if 'user' not in st.session_state: st.session_state['user'] = None
if 'current_chat_id' not in st.session_state: st.session_state['current_chat_id'] = None
if 'contract_content' not in st.session_state: st.session_state['contract_content'] = ""
if 'email_content' not in st.session_state: st.session_state['email_content'] = ""
if 'ai_response' not in st.session_state: st.session_state['ai_response'] = None

# --- REPLACE YOUR EXISTING CSS BLOCK WITH THIS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #E2E8F0;
        background-color: #0F172A; /* Match main background */
    }

    /* Main Background */
    .stApp { background-color: #0F172A; }

    /* Sidebar Background */
    [data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #1E293B;
    }
    
    /* --- NEW HEADER TITLE FIX --- */
    
    /* 1. Hide the default Streamlit top decoration */
    header[data-testid="stHeader"] {
        background-color: #0F172A !important;
        z-index: 999;
    }
    
    /* 2. Hide the old title class if it exists */
    .app-title { display: none; }

    /* Inputs (Text Area & Text Input) */
    .stTextArea textarea, .stTextInput input {
        background-color: #1E293B !important; 
        color: #F8FAFC !important;
        border: 1px solid #334155 !important; 
        border-radius: 8px; 
        padding: 10px 15px;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #818CF8 !important; 
        box-shadow: 0 0 0 1px #818CF8 !important;
    }

    /* Remove "Press Enter to Apply" Text */
    div[data-testid="InputInstructions"] { display: none !important; }

    /* Primary Gradient Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
        color: white; 
        border: none; 
        padding: 0.5rem 1rem; 
        border-radius: 8px; 
        font-weight: 600; 
        width: 100%;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover { 
        opacity: 0.9; 
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    /* Profile Box in Sidebar */
    .user-profile {
        display: flex; align-items: center; 
        padding: 12px; 
        background: #1E293B; 
        border: 1px solid #334155; 
        border-radius: 10px; 
        margin-bottom: 20px;
    }
    /* Push content up so the header sits at the very top */
    .block-container {
        padding-top: 1rem !important; /* Reduced from default */
        padding-bottom: 5rem !important;
    }
    .user-avatar {
        width: 32px; height: 32px; border-radius: 50%;
        background: linear-gradient(135deg, #A78BFA, #6366F1);
        color: white; display: flex; justify-content: center; 
        align-items: center; font-weight: 700; margin-right: 10px; font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)
# --- MAIN CONTENT (Adaptive Header) ---
    
    # This header is "Sticky". It stays at the top but moves when Sidebar collapses.
st.markdown("""
    <div style="
        position: sticky; 
        top: 0; 
        z-index: 1000; 
        background-color: #0F172A; 
        padding: 10px 0px 20px 0px;
        border-bottom: 1px solid #1E293B;
        margin-bottom: 20px;
        display: flex; 
        align-items: center; 
        gap: 12px;
    ">
        <span style="font-size: 2rem;">🛡️</span> 
        <span style="
            font-size: 1.8rem; 
            font-weight: 800; 
            font-family: 'Inter', sans-serif;
            background: linear-gradient(to right, #C7D2FE, #818CF8); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent;
        ">
            ScopeGuard
        </span>
</div>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---

def get_ai_response(contract, email, tone):
    genai.configure(api_key=GOOGLE_API_KEY)
    # Auto-discovery fallback
    
    model_name = next((m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name), 'models/gemini-pro')
   
    model = genai.GenerativeModel(model_name)
    
    chat = model.start_chat(history=[
        {"role": "user", "parts": [f"CONTRACT RULES:\n{contract}"]},
        {"role": "model", "parts": ["I have memorized the contract rules."]}
    ])
    prompt = f"Client Email: '{email}'\nTone: {tone}\nTask: Check for scope violation and draft a response. Use Markdown formatting (bolding, lists) to make it clear."
    return chat.send_message(prompt).text

def save_chat_history(title, contract, email, response):
    uid = st.session_state['user'].id
    data = {"user_id": uid, "title": title, "contract_text": contract, "client_email": email, "ai_response": response}
    if st.session_state['current_chat_id']:
        supabase.table("chat_history").update(data).eq("id", st.session_state['current_chat_id']).execute()
    else:
        if not title: title = (email[:30] + '...') if len(email) > 30 else email
        data["title"] = title
        res = supabase.table("chat_history").insert(data).execute()
        if res.data: st.session_state['current_chat_id'] = res.data[0]['id']

def load_chat(chat_id):
    res = supabase.table("chat_history").select("*").eq("id", chat_id).execute()
    if res.data:
        data = res.data[0]
        st.session_state['current_chat_id'] = data['id']
        st.session_state['contract_content'] = data['contract_text']
        st.session_state['email_content'] = data['client_email']
        st.session_state['ai_response'] = data['ai_response']
        st.rerun()

def new_chat():
    st.session_state['current_chat_id'] = None
    st.session_state['contract_content'] = ""
    st.session_state['email_content'] = ""
    st.session_state['ai_response'] = None
    st.rerun()

# --- 4. SETTINGS DIALOG (NEW FEATURE) ---
@st.dialog("⚙️ Account Settings")
def show_settings_dialog():
    tab_account, tab_theme = st.tabs(["👤 Account", "🎨 Theme"])
    
    with tab_account:
        st.write(f"**Email:** `{st.session_state['user'].email}`")
        st.markdown("---")
        
        # A. Update Password
        with st.expander("🔒 Update Password"):
            old_pass = st.text_input("Current Password", type="password")
            new_pass_1 = st.text_input("New Password", type="password")
            new_pass_2 = st.text_input("Confirm New Password", type="password")
            
            if st.button("Update Password"):
                if new_pass_1 != new_pass_2: st.error("New passwords do not match.")
                elif len(new_pass_1) < 6: st.error("Password too short.")
                else:
                    try:
                        # Verify old password first
                        auth = supabase.auth.sign_in_with_password({
                            "email": st.session_state['user'].email, "password": old_pass
                        })
                        if auth.user:
                            supabase.auth.update_user({"password": new_pass_1})
                            st.success("✅ Password updated!")
                    except: st.error("Incorrect current password.")

        # B. Delete Account
        with st.expander("🚨 Delete Account"):
            st.warning("Permanent action.")
            del_pass = st.text_input("Password", type="password", key="del_pass_input")
            verif_code = st.text_input("Verification Code (Check Email)", placeholder="Enter 123456")
            
            if st.button("Permanently Delete", type="primary"):
                if verif_code == "123456": 
                    try:
                        auth = supabase.auth.sign_in_with_password({
                            "email": st.session_state['user'].email, "password": del_pass
                        })
                        if auth.user:
                            st.success("Account deleted.")
                            # Note: Actual deletion requires admin backend, this simulates it for UI
                            time.sleep(2)
                            st.session_state['user'] = None
                            st.rerun()
                    except: st.error("Incorrect Password.")
                else: st.error("Invalid Verification Code.")

    with tab_theme:
        st.write("Customize appearance")
        theme = st.radio("Select Mode", ["Dark (Default)", "Light High Contrast"])
        if theme == "Light High Contrast":
            st.markdown("""<style>.stApp { background-color: #ffffff !important; color: #000000 !important; } .stTextArea textarea { background-color: #f0f0f0 !important; color: black !important; border: 2px solid black !important; }</style>""", unsafe_allow_html=True)

# --- 5. MAIN APP LAYOUT ---

# A. LOGIN SCREEN
if not st.session_state['user']:
    st.markdown("<h1 style='text-align: center; margin-top: 40px;'>🛡️ ScopeGuard</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; margin-bottom: 40px;'>AI Legal Defense for Freelancers</p>", unsafe_allow_html=True)
    
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            # CHANGE: We wrap this in a form so it submits reliably on the first try
            
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            # Hides the "Press Enter" instruction via CSS we added earlier
            if st.button("Enter Dashboard"):
                if not email or not password:
                    st.warning("Please fill in all fields.")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state['user'] = res.user
                        st.rerun()
                    except Exception as e: st.error("Login failed. Check credentials.")

        with tab2:
            n_email = st.text_input("New Email")
            n_pass = st.text_input("New Password", type="password")
            if st.button("Create Account"):
                if not n_email or not n_pass:
                    st.warning("Please fill in all fields.")
                else:
                    try:
                        supabase.auth.sign_up({"email": n_email, "password": n_pass})
                        st.success("Account created! Check email or try logging in.")
                    except Exception as e: st.error("Signup failed.")

# B. MAIN DASHBOARD
else:
    # --- REPLACE THE CONTENT INSIDE 'with st.sidebar:' ---
    with st.sidebar:
        
        user_email = st.session_state['user'].email
        avatar_letter = user_email[0].upper() if user_email else "U"
        st.markdown(f"""
            <div class="user-profile">
                <div class="user-avatar">{avatar_letter}</div>
                <div style="overflow: hidden; text-overflow: ellipsis; font-size: 0.85rem; color: #E2E8F0;">{user_email}</div>
            </div>
        """, unsafe_allow_html=True)

        # 2. Action Buttons
        if st.button("＋ New Defense", use_container_width=True):
           new_chat()

        st.markdown("---")
        st.markdown('<p style="font-size: 0.75rem; color: #64748B; font-weight: 600; margin-bottom: 10px; letter-spacing: 0.5px;">RECENT ACTIVITY</p>', unsafe_allow_html=True)
        
        # 3. History List (With Unique Keys)
        history = supabase.table("chat_history").select("id, title").eq("user_id", st.session_state['user'].id).order("created_at", desc=True).limit(10).execute()
        if history.data:
            for i, item in enumerate(history.data):
                # Truncate long titles
                display_title = (item['title'][:18] + '..') if len(item['title']) > 18 else item['title']
                if st.button(f"💬 {display_title}", key=f"hist_{item['id']}_{i}", use_container_width=True):
                    load_chat(item['id'])

        # 4. Spacer (Pushes content down)
        st.markdown("<div style='height: 28vh;'></div>", unsafe_allow_html=True)
        
        # 5. Bottom Menu (Settings & Logout)
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⚙️", help="Settings", use_container_width=True):
                show_settings_dialog()
        with col2:
            if st.button("🚪", help="Log Out", use_container_width=True):
                supabase.auth.sign_out()
                st.session_state['user'] = None
                st.rerun()

    # --- MAIN CONTENT ---
    st.markdown('<div class="app-title">ScopeGuard</div>', unsafe_allow_html=True)
    tone = st.select_slider("Response Tone", options=["Polite", "Professional", "Strict"], value="Professional")

    # DEFENSE FORM
    with st.form("defense_form"):
        st.markdown("### 1. The Rules (Contract)")
        tab_txt, tab_pdf = st.tabs(["Text", "PDF"])
        
        with tab_txt:
            contract_txt = st.text_area("Contract Terms", value=st.session_state['contract_content'], height=150, label_visibility="collapsed", placeholder="Paste contract here...")
        with tab_pdf:
            pdf = st.file_uploader("Upload PDF", type="pdf", label_visibility="collapsed")
            if pdf:
                reader = PdfReader(pdf)
                contract_txt = "\n".join([page.extract_text() for page in reader.pages])
                st.session_state['contract_content'] = contract_txt
                st.success("PDF Attached")

        st.markdown("### 2. The Demand (Client Email)")
        email_txt = st.text_area("Client Email", value=st.session_state['email_content'], height=200, label_visibility="collapsed", placeholder="Paste client email here...")

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("⚡ GENERATE RESPONSE")
        
        if submitted:
            st.session_state['contract_content'] = contract_txt 
            st.session_state['email_content'] = email_txt 
            
            if not contract_txt or not email_txt:
                st.warning("Missing input data.")
            else:
                with st.spinner("Drafting defense..."):
                    response = get_ai_response(contract_txt, email_txt, tone)
                    st.session_state['ai_response'] = response
                    title = email_txt.split('\n')[0][:25] + "..." if email_txt else "New Chat"
                    save_chat_history(title, contract_txt, email_txt, response)
                    st.rerun()

    # --- RESULTS DISPLAY ---
    if st.session_state['ai_response']:
        st.markdown("### Generated Draft")
        
        # Using a styled container + standard st.markdown to render bolding/lists correctly
        with st.container(border=True):
            st.markdown(st.session_state['ai_response'])
            
        st.caption("Tip: Copy the text above directly into your email app.")