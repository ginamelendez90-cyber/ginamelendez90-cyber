# ==========================================
# ARCHIVO: streamlit_app.py
# ==========================================
import streamlit as st
import pandas as pd
import plotly.express as px
import re

# Importación compatible con versiones actuales y legadas de LangChain
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

# Configuración de página
st.set_page_config(
    page_title="Analizador de Datos Multiformato con IA",
    page_icon="📊",
    layout="wide"
)

# Carga de archivos con tolerancias a múltiples codificaciones y separadores
def cargar_archivo_robusto(archivo):
    nombre = archivo.name.lower()
    
    if nombre.endswith(('.csv', '.txt')):
        try:
            return pd.read_csv(archivo)
        except Exception:
            archivo.seek(0)
            try:
                return pd.read_csv(archivo, sep=None, engine='python', encoding='latin-1')
            except Exception:
                archivo.seek(0)
                return pd.read_csv(archivo, sep=';', encoding='utf-8')

    elif nombre.endswith('.xlsx'):
        return pd.read_excel(archivo, engine='openpyxl')

    elif nombre.endswith('.xls'):
        return pd.read_excel(archivo, engine='xlrd')

    elif nombre.endswith('.parquet'):
        return pd.read_parquet(archivo)

    elif nombre.endswith('.json'):
        return pd.read_json(archivo)

    else:
        raise ValueError("Formato de archivo no soportado.")

st.title("📊 Analizador de Datos Universal con IA Privada")

# Sidebar: Configuración de servidor Ollama / Ngrok
st.sidebar.header("⚙️ Configuración")
url_defecto = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
base_url = st.sidebar.text_input("URL de Ollama (Local / Ngrok)", value=url_defecto)

nombre_modelo = st.sidebar.selectbox(
    "Modelo LLM",
    ["qwen2.5-coder", "llama3", "llama3.1", "llama3.2"],
    index=0,
    help="'qwen2.5-coder' ofrece mayor precisión generando código ejecutable de Plotly/Pandas."
)

# Selector de archivos
archivo = st.file_uploader(
    "Carga tu archivo de datos", 
    type=["csv", "xlsx", "xls", "parquet", "json", "txt"]
)

if archivo:
    try:
        df = cargar_archivo_robusto(archivo)
        st.success(f"¡Archivo '{archivo.name}' cargado con éxito!")
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        st.stop()

    # Resumen y estructura
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Filas", df.shape[0])
    c2.metric("Total Columnas", df.shape[1])
    c3.metric("Valores Nulos", df.isna().sum().sum())

    with st.expander("👀 Vista previa del conjunto de datos", expanded=False):
        st.dataframe(df.head(5), use_container_width=True)
        st.write("**Columnas detectadas:**", list(df.columns))

    st.divider()

    # Interfaz de consulta
    pregunta = st.text_input("💬 Haz una pregunta o solicita una visualización:")
    st.caption("Ejemplos: *'Gráfico de barras de ventas por región'*, *'Resumen numérico de la columna precio'*, *'Muestra los 5 elementos con mayor valor'*)")

    if pregunta:
        prompt = f"""
Eres un analista de datos experto. Tienes un DataFrame de Pandas llamado `df` con las siguientes columnas: {list(df.columns)}.

El usuario solicita: "{pregunta}"

INSTRUCCIONES OBLIGATORIAS:
1. Genera código Python utilizando `pandas` y/o `plotly.express` (importado como `px`).
2. Si la solicitud implica un gráfico, crea la figura de Plotly y asígnala a la variable `fig`.
3. Si la solicitud implica texto, número o tabla, asigna el resultado a la variable `resultado`.
4. Devuelve ÚNICAMENTE el código Python dentro de un bloque markdown ```python ... ```. No agregues saludos ni explicaciones fuera del código.
"""
        with st.spinner(f"Analizando con {nombre_modelo}..."):
            try:
                llm = ChatOllama(
                    model=nombre_modelo,
                    temperature=0,
                    base_url=base_url
                )

                respuesta = llm.invoke(prompt).content

                # Extraer bloque de código ejecutable
                match = re.search(r"```(?:python)?\s*(.*?)\s*```", respuesta, re.DOTALL)
                codigo = match.group(1).strip() if match else respuesta.strip()

                # Entorno controlado para ejecución
                entorno_local = {"df": df, "px": px, "pd": pd, "st": st}
                exec(codigo, entorno_local)

                # Renderizar gráfico si existe
                if "fig" in entorno_local and entorno_local["fig"] is not None:
                    st.plotly_chart(entorno_local["fig"], use_container_width=True)

                # Mostrar resultado si existe
                if "resultado" in entorno_local and entorno_local["resultado"] is not None:
                    st.write("**Resultado:**")
                    st.write(entorno_local["resultado"])

                with st.expander("🛠️ Ver código Python ejecutado"):
                    st.code(codigo, language="python")

            except Exception as e:
                st.error(f"❌ Error al ejecutar el análisis: {e}")
