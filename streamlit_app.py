import streamlit as st
from supabase import create_client, Client
import time
import uuid

# Configuración de la página
st.set_page_config(page_title="UltraChat MVP", page_icon="💬", layout="centered")

# --- CONEXIÓN A SUPABASE ---
# Streamlit maneja automáticamente el cacheo de las conexiones para no saturar la base de datos
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

st.title("⚡️ UltraChat - Conectado a Supabase")

# --- SIMULACIÓN DE DATOS TEMPORALES ---
# Como aún no tenemos usuarios reales, creamos unas variables temporales.
# En un escenario real, sacarías estos IDs cuando el usuario inicia sesión.
TEST_USER_ID = "00000000-0000-0000-0000-000000000001" # Simula ser el usuario actual
TEST_ROOM_ID = "00000000-0000-0000-0000-000000000001" # Simula la sala de chat

# --- HISTORIAL DEL CHAT (Base de datos) ---
# Función para recuperar mensajes de Supabase
def fetch_messages():
    try:
        # Pide a Supabase todos los mensajes de la sala actual, ordenados por fecha de creación
        response = supabase.table("messages").select("*").eq("room_id", TEST_ROOM_ID).order("created_at").execute()
        return response.data
    except Exception as e:
        # Esto evitará que la app colapse si la tabla está vacía o hay un error de conexión
        st.error(f"Error al conectar con la base de datos. ¿Creaste los datos temporales en Supabase?: {e}")
        return []

# Obtener los mensajes y mostrarlos
messages_data = fetch_messages()

for msg in messages_data:
    # Si el mensaje lo envió el TEST_USER_ID, lo marcamos como "user" (nosotros)
    # Si no, lo marcamos como "assistant" (el otro participante de la sala)
    role = "user" if msg["sender_id"] == TEST_USER_ID else "assistant"
    with st.chat_message(role):
        st.markdown(msg["content"])

# --- ENVÍO DE NUEVOS MENSAJES ---
if prompt := st.chat_input("Escribe un mensaje..."):
    
    # 1. Mostrar el mensaje inmediatamente en la interfaz local
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Insertar el mensaje directamente en Supabase
    new_message_data = {
        "room_id": TEST_ROOM_ID,
        "sender_id": TEST_USER_ID,
        "content": prompt
    }
    
    # Supabase guarda el registro y la base de datos lo difunde automáticamente
    supabase.table("messages").insert(new_message_data).execute()
    
    # 3. Forzamos que Streamlit recargue la página para mostrar el historial actualizado
    st.rerun()
