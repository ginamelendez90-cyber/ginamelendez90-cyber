import streamlit as st
import pandas as pd
import plotly.express as px
import re
import base64
import requests
import io

# Importación segura compatible con versiones actuales y antiguas de LangChain
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

# Configuración inicial de la página
st.set_page_config(
    page_title="Analizador Universal de Datos e Imágenes",
    page_icon="📊",
    layout="wide"
)

# Función para extraer tablas desde imágenes usando visión artificial (Ollama API)
def extraer_tabla_de_imagen(archivo_imagen, base_url, modelo_vision="llama3.2-vision"):
    bytes_imagen = archivo_imagen.getvalue()
    b64_imagen = base64.b64encode(bytes_imagen).decode('utf-8')
    
    endpoint = f"{base_url.rstrip('/')}/api/chat"
    
    prompt = """Analiza la tabla presente en esta imagen y extrae todos sus datos.
Devuelve ÚNICAMENTE el contenido en formato CSV estándar (delimitado por comas), incluyendo los encabezados de columna.
NO agregues introducciones, comentarios ni explicaciones. Si usas bloques markdown, entrega solo el código CSV dentro."""

    payload = {
        "model": modelo_vision,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [b64_imagen]
            }
        ],
        "stream": False
    }
    
    respuesta = requests.post(endpoint, json=payload, timeout=120)
    respuesta.raise_for_status()
    contenido = respuesta.json()["message"]["content"].strip()
    
    # Limpieza de markdown
    if "```" in contenido:
        match = re.search(r"```(?:csv)?\s*(.*?)\s*```", contenido, re.DOTALL)
        if match:
            contenido = match.group(1).strip()
            
    return pd.read_csv(io.StringIO(contenido))

# Cargador de archivos multiformato con tolerancia a errores de codificación
def cargar_archivo_robusto(archivo, base_url, modelo_vision):
    nombre = archivo.name.lower()
    
    # 1. Procesamiento de imágenes (PNG/JPG/JPEG)
    if nombre.endswith(('.png', '.jpg', '.jpeg')):
        with st.spinner("🖼️ Leyendo tabla desde la imagen con el modelo de visión..."):
            return extraer_tabla_de_imagen(archivo, base_url, modelo_vision)

    # 2. Archivos de texto o CSV
    elif nombre.endswith(('.csv', '.txt')):
        try:
            return pd.read_csv(archivo)
        except Exception:
            archivo.seek(0)
            try:
                return pd.read_csv(archivo, sep=None, engine='python', encoding='latin-1')
            except Exception:
                archivo.seek(0)
                return pd.read_csv(archivo, sep=';', encoding='utf-8')

    # 3. Hojas de cálculo Excel
    elif nombre.endswith('.xlsx'):
        return pd.read_excel(archivo, engine='openpyxl')
    elif nombre.endswith('.xls'):
        return pd.read_excel(archivo, engine='xlrd')

    # 4. Formatos estructurados adicionales
    elif nombre.endswith('.parquet'):
        return pd.read_parquet(archivo)
    elif nombre.endswith('.json'):
        return pd.read_json(archivo)

    else:
        raise ValueError("Formato de archivo no soportado.")

# --- INTERFAZ PRINCIPAL ---
st.title("📊 Analizador Universal de Datos e Imágenes con IA")

# Sidebar: Configuración de modelos y conexión
st.sidebar.header("⚙️ Configuración del Servidor")
url_defecto = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
base_url = st.sidebar.text_input("URL de Ollama (Local / Ngrok)", value=url_defecto)

modelo_texto = st.sidebar.selectbox(
    "Modelo para código/análisis",
    ["qwen2.5-coder", "llama3", "llama3.1", "llama3.2"],
    index=0,
    help="'qwen2.5-coder' es el más preciso generando gráficos y código de Pandas."
)

modelo_vision = st.sidebar.selectbox(
    "Modelo de Visión (Imágenes)",
    ["llama3.2-vision", "llava"],
    index=0
)

# Carga de archivos
archivo = st.file_uploader(
    "Carga tu archivo de datos (CSV, Excel, Parquet, JSON) o una imagen con una tabla (PNG, JPG)", 
    type=["csv", "xlsx", "xls", "parquet", "json", "txt", "png", "jpg", "jpeg"]
)

if archivo:
    try:
        # Previsualizar la imagen si es el caso
        if archivo.name.lower().endswith(('.png', '.jpg', '.jpeg')):
            st.image(archivo, caption="Imagen cargada", use_column_width=True)

        df = cargar_archivo_robusto(archivo, base_url, modelo_vision)
        st.success(f"¡Datos cargados correctamente desde '{archivo.name}'!")
        
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo o la imagen: {e}")
        st.info("Asegúrate de que Ollama esté en ejecución y tengas instalado el modelo de visión (`ollama pull llama3.2-vision`).")
        st.stop()

    # Métricas y vista previa
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas detectadas", df.shape[0])
    c2.metric("Columnas detectadas", df.shape[1])
    c3.metric("Valores Nulos", df.isna().sum().sum())

    with st.expander("👀 Ver estructura y datos cargados", expanded=True):
        st.dataframe(df, use_container_width=True)
        st.write("**Columnas:**", list(df.columns))

    st.divider()

    # Interfaz de consulta en lenguaje natural
    pregunta = st.text_input("💬 Pide un gráfico o realiza una pregunta sobre los datos:")
    st.caption("Ejemplos: *'Genera un gráfico de barras del total por categoría'*, *'Muestra los 5 valores más altos'*, *'Resumen de promedios'*)")

    if pregunta:
        prompt = f"""
Eres un analista de datos experto. Tienes un DataFrame de Pandas llamado `df` con las siguientes columnas: {list(df.columns)}.

El usuario solicita: "{pregunta}"

INSTRUCCIONES OBLIGATORIAS:
1. Genera código Python utilizando `pandas` y/o `plotly.express` (importado como `px`).
2. Si la solicitud implica un gráfico, crea la figura de Plotly y asígnala a la variable `fig`.
3. Si la solicitud implica texto, tabla o número, asigna el resultado a la variable `resultado`.
4. Devuelve ÚNICAMENTE el código Python dentro de un bloque markdown ```python ... ```. No agregues saludos ni explicaciones fuera del bloque.
"""
        with st.spinner("Procesando análisis con el modelo de IA..."):
            try:
                llm = ChatOllama(
                    model=modelo_texto,
                    temperature=0,
                    base_url=base_url
                )

                respuesta = llm.invoke(prompt).content

                # Extraer código Python con expresiones regulares
                match = re.search(r"```(?:python)?\s*(.*?)\s*```", respuesta, re.DOTALL)
                codigo = match.group(1).strip() if match else respuesta.strip()

                # Entorno aislado para ejecutar el código dinámico
                entorno_local = {"df": df, "px": px, "pd": pd, "st": st}
                exec(codigo, entorno_local)

                # Renderizar figura si existe
                if "fig" in entorno_local and entorno_local["fig"] is not None:
                    st.plotly_chart(entorno_local["fig"], use_container_width=True)

                # Mostrar resultado de texto/tabla si existe
                if "resultado" in entorno_local and entorno_local["resultado"] is not None:
                    st.write("**Resultado:**")
                    st.write(entorno_local["resultado"])

                with st.expander("🛠️ Ver código Python generado"):
                    st.code(codigo, language="python")

            except Exception as e:
                st.error(f"❌ Error al ejecutar el análisis: {e}")
