import streamlit as st
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="UltraChat Pro", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 2. SISTEMA DE AUTH ---
if "user" not in st.session_state:
    st.session_state.user = None

def login_ui():
    st.title("🔐 Login / Registro")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Contraseña", type="password", key="l_pass")
        if st.button("Entrar"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with tab2:
        email = st.text_input("Email", key="r_email")
        password = st.text_input("Contraseña", type="password", key="r_pass")
        if st.button("Crear cuenta"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("¡Cuenta creada! Ya puedes iniciar sesión.")
            except Exception as e:
                st.error(f"Error: {e}")
    st.stop()

if not st.session_state.user:
    login_ui()

# --- 3. LOGICA DE CHAT ---

def get_or_create_room(my_id, target_id):
    # Buscar si ya existe una sala privada (is_group=false) entre estos dos usuarios
    rooms = supabase.rpc("get_private_room", {"user1": my_id, "user2": target_id}).execute().data
    
    if rooms:
        return rooms[0]['room_id']
    
    # Si no existe, crear sala y participantes
    new_room = supabase.table("rooms").insert({"is_group": False}).execute().data[0]
    room_id = new_room['id']
    supabase.table("participants").insert([
        {"room_id": room_id, "user_id": my_id},
        {"room_id": room_id, "user_id": target_id}
    ]).execute()
    return room_id

# --- 4. INTERFAZ PRINCIPAL ---
st.sidebar.title(f"Bienvenido, {st.session_state.user.email}")
if st.sidebar.button("Cerrar Sesión"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# Listar usuarios para chatear
users = supabase.table("profiles").select("*").neq("id", st.session_state.user.id).execute().data

st.sidebar.subheader("Contactos")
target_user = None
for u in users:
    if st.sidebar.button(f"👤 {u['username'] or u['id'][:8]}"):
        target_user = u

# Área de Chat
if target_user:
    st.header(f"Chat con {target_user['username']}")
    room_id = get_or_create_room(st.session_state.user.id, target_user['id'])
    
    # Cargar mensajes
    messages = supabase.table("messages").select("*").eq("room_id", room_id).order("created_at").execute().data
    
    for msg in messages:
        role = "user" if msg["sender_id"] == st.session_state.user.id else "assistant"
        with st.chat_message(role):
            st.write(msg["content"])
            
    # Input
    if prompt := st.chat_input("Mensaje..."):
        supabase.table("messages").insert({
            "room_id": room_id,
            "sender_id": st.session_state.user.id,
            "content": prompt
        }).execute()
        st.rerun()
else:
    st.info("Selecciona un usuario en la barra lateral para empezar a chatear.")
