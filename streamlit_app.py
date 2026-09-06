# ==========================================
# ARCHIVO: streamlit_app.py
# ==========================================
import streamlit as st
import pandas as pd
import plotly.express as px
import re

# Importación segura compatible con versiones antiguas y recientes de LangChain
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

# Configuración de la página
st.set_page_config(
    page_title="Analizador de Datos con IA",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Analizador de Datos con IA Privada (Ollama)")

# Sidebar: Configuración de la conexión y modelo
st.sidebar.header("⚙️ Configuración")

# Lee la URL pública de Ngrok definida en Secrets o usa localhost por defecto
url_defecto = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
base_url = st.sidebar.text_input("URL de Ollama (Servidor / Ngrok)", value=url_defecto)

nombre_modelo = st.sidebar.selectbox(
    "Modelo LLM",
    ["llama3", "qwen2.5-coder", "llama3.1", "llama3.2"],
    index=0,
    help="Si vas a hacer muchas gráficas, 'qwen2.5-coder' genera código más preciso."
)

st.sidebar.info("💡 Si usas Streamlit Cloud, asegúrate de tener iniciado el túnel de Ngrok en tu PC.")

# Carga de datos
archivo = st.file_uploader("Carga un archivo (CSV o Excel)", type=["csv", "xlsx"])

if archivo:
    # 1. Lectura dinámica del archivo
    try:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.stop()

    # 2. Métricas rápidas y vista previa
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Filas", df.shape[0])
    c2.metric("Total Columnas", df.shape[1])
    c3.metric("Valores Nulos", df.isna().sum().sum())

    with st.expander("👀 Vista previa de datos y estructura", expanded=False):
        st.dataframe(df.head(5), use_container_width=True)
        st.write("**Columnas disponibles:**", list(df.columns))

    st.divider()

    # 3. Interfaz de consulta
    pregunta = st.text_input("💬 Haz una pregunta o pide un gráfico sobre tus datos:")
    st.caption("Ejemplos: *'Promedio de ventas por categoría'*, *'Gráfico de barras de los 5 productos más caros'*, *'Resumen estadístico de precios'*)")

    if pregunta:
        # Prompt estructurado para forzar respuesta en código ejecutable
        prompt = f"""
Eres un analista de datos experto. Tienes un DataFrame de Pandas llamado `df` con las siguientes columnas: {list(df.columns)}.

El usuario solicita: "{pregunta}"

INSTRUCCIONES OBLIGATORIAS:
1. Genera código Python utilizando `pandas` y/o `plotly.express` (importado como `px`).
2. Si la solicitud implica un gráfico, crea la figura de Plotly y asígnala a la variable `fig`.
3. Si la solicitud implica un texto, número o tabla, asigna el valor a la variable `resultado`.
4. Devuelve ÚNICAMENTE el código Python dentro de un bloque markdown ```python ... ```. No agregues saludos, ni explicaciones fuera del bloque de código.
"""
        with st.spinner(f"Analizando información con {nombre_modelo}..."):
            try:
                # Inicializar cliente de Ollama
                llm = ChatOllama(
                    model=nombre_modelo,
                    temperature=0,
                    base_url=base_url
                )

                respuesta = llm.invoke(prompt).content

                # Extraer bloque de código Python mediante expresiones regulares
                match = re.search(r"```(?:python)?\s*(.*?)\s*```", respuesta, re.DOTALL)
                codigo = match.group(1).strip() if match else respuesta.strip()

                # Entorno aislado para ejecutar el código
                entorno_local = {"df": df, "px": px, "pd": pd, "st": st}
                exec(codigo, entorno_local)

                # Visualizar gráfico de Plotly si existe
                if "fig" in entorno_local and entorno_local["fig"] is not None:
                    st.plotly_chart(entorno_local["fig"], use_container_width=True)

                # Mostrar texto o tabla si existe
                if "resultado" in entorno_local and entorno_local["resultado"] is not None:
                    st.write("**Resultado:**")
                    st.write(entorno_local["resultado"])

                # Desplegable para auditoría del código
                with st.expander("🛠️ Ver código Python generado"):
                    st.code(codigo, language="python")

            except Exception as e:
                st.error(f"❌ Error durante la ejecución del análisis: {e}")
                st.warning("Tip: Si hay errores de código, intenta cambiar el modelo en la barra lateral a 'qwen2.5-coder'.")
