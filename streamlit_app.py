import streamlit as st
import time

# Configuración de la página
st.set_page_config(page_title="UltraChat MVP", page_icon="💬", layout="centered")

st.title("⚡️ UltraChat - Modo Desarrollo")

# Inicializar el historial de chat en el estado de la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar los mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Capturar el nuevo mensaje del usuario
if prompt := st.chat_input("Escribe tu mensaje aquí..."):
    
    # 1. Mostrar el mensaje del usuario en la UI
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 2. Guardar el mensaje en el estado
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 3. Simular la respuesta del "otro usuario" o servidor
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Simulamos un pequeño retraso de red
        simulated_response = f"He recibido tu mensaje: '{prompt}'. (Aquí conectaremos Supabase pronto)"
        
        for chunk in simulated_response.split():
            full_response += chunk + " "
            time.sleep(0.05)
            message_placeholder.markdown(full_response + "▌")
        
        message_placeholder.markdown(full_response)
    
    # 4. Guardar la respuesta en el estado
    st.session_state.messages.append({"role": "assistant", "content": full_response})
