import streamlit as st
import pandas as pd
import plotly.express as px
import re
import base64
import requests
import io
import tempfile
import os
import textwrap
import urllib.parse
import numpy as np
import random
from PIL import Image, ImageDraw, ImageFont
import whisper

# Importaciones dinámicas compatibles con versiones legadas y modernas
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

try:
    from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip
except ImportError:
    from moviepy import AudioFileClip, ImageClip, CompositeVideoClip

# Configuración inicial de la aplicación
st.set_page_config(
    page_title="Suite Multimedia y Analítica con IA",
    page_icon="🚀",
    layout="wide"
)

# Carga en caché del modelo Whisper para optimizar recursos
@st.cache_resource
def cargar_whisper():
    return whisper.load_model("tiny")

# Estilos predefinidos para la superposición de subtítulos
ESTILOS = {
    "🧸 Infantil / Niños": {
        "color_texto": (255, 235, 59),      # Amarillo brillante
        "color_borde": (233, 30, 99),       # Rosa/Magenta fuerte
        "color_fondo": (74, 20, 140, 210),  # Morado oscuro semi-transparente
        "emojis": ["🎈", "⭐", "🎵", "🧸", "✨", "🎉"],
        "tamanio_fuente": 42
    },
    "⚡ Neón / Pop": {
        "color_texto": (0, 255, 255),       # Cyan Neón
        "color_borde": (255, 0, 128),      # Neón Rosa
        "color_fondo": (10, 10, 20, 220),   # Azul muy oscuro
        "emojis": ["⚡", "🔥", "🎶", "💥"],
        "tamanio_fuente": 38
    },
    "✨ Elegante / Balada": {
        "color_texto": (255, 255, 255),     # Blanco puro
        "color_borde": (212, 175, 55),      # Dorado
        "color_fondo": (0, 0, 0, 180),      # Negro sutil
        "emojis": ["✨", "🌙", "💖"],
        "tamanio_fuente": 36
    }
}

# --- FUNCIONES DE ANÁLISIS DE DATOS E IMÁGENES ---

def extraer_tabla_de_imagen(archivo_imagen, base_url, modelo_vision="llama3.2-vision"):
    bytes_imagen = archivo_imagen.getvalue()
    b64_imagen = base64.b64encode(bytes_imagen).decode('utf-8')
    endpoint = f"{base_url.rstrip('/')}/api/chat"
    
    prompt = """Analiza la tabla presente en esta imagen y extrae todos sus datos.
Devuelve ÚNICAMENTE el contenido en formato CSV estándar (delimitado por comas), incluyendo los encabezados de columna.
NO agregues introducciones, comentarios ni explicaciones."""

    payload = {
        "model": modelo_vision,
        "messages": [{"role": "user", "content": prompt, "images": [b64_imagen]}],
        "stream": False
    }
    
    respuesta = requests.post(endpoint, json=payload, timeout=120)
    respuesta.raise_for_status()
    contenido = respuesta.json()["message"]["content"].strip()
    
    if "```" in contenido:
        patron_csv = r"```(?:csv)?\s*(.*?)\s*```"
        match = re.search(patron_csv, contenido, re.DOTALL)
        if match:
            contenido = match.group(1).strip()
            
    return pd.read_csv(io.StringIO(contenido))

def cargar_archivo_robusto(archivo, base_url, modelo_vision):
    nombre = archivo.name.lower()
    if nombre.endswith(('.png', '.jpg', '.jpeg')):
        with st.spinner("🖼️ Leyendo tabla desde la imagen con el modelo de visión..."):
            return extraer_tabla_de_imagen(archivo, base_url, modelo_vision)
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
    elif nombre.endswith('.xlsx'):
        return pd.read_excel(archivo, engine='openpyxl')
    elif nombre.endswith('.xls'):
        return pd.read_excel(archivo, engine='xlrd')
    elif nombre.endswith('.parquet'):
        return pd.read_parquet(archivo)
    elif nombre.endswith('.json'):
        return pd.read_json(archivo)
    else:
        raise ValueError("Formato no soportado.")

# --- FUNCIONES DE GENERACIÓN DE MULTIMEDIA E IA ---

def detectar_estilo_automatico(letra_completa, base_url, modelo_texto):
    prompt = f"""
Analiza la siguiente letra de canción y clasifícala en EXACTAMENTE una de estas tres categorías:
- Infantil (si menciona animales, juegos, tonos educativos, canciones de cuna o palabras sencillas para niños)
- Neon (si es música rápida, pop, urbana, electrónica o de fiesta)
- Elegante (si es una balada, canción romántica, poética o instrumental)

Letra de la canción:
"{letra_completa[:1000]}"

INSTRUCCIÓN: Responde ÚNICAMENTE con una palabra: 'Infantil', 'Neon' o 'Elegante'.
"""
    try:
        llm = ChatOllama(model=modelo_texto, temperature=0, base_url=base_url)
        respuesta = llm.invoke(prompt).content.strip().lower()
        if "infantil" in respuesta:
            return "🧸 Infantil / Niños"
        elif "neon" in respuesta:
            return "⚡ Neón / Pop"
        else:
            return "✨ Elegante / Balada"
    except Exception:
        return "🧸 Infantil / Niños"

def generar_prompt_visual(letra_completa, base_url, modelo_texto):
    prompt_sistema = f"""
You are an art director. Read these lyrics and create a detailed visual prompt IN ENGLISH for an AI image generator.
Describe the scene, mood, artistic style, and main subject.
Keep it under 30 words. Output ONLY the English prompt, nothing else.

Lyrics:
"{letra_completa[:1000]}"
"""
    try:
        llm = ChatOllama(model=modelo_texto, temperature=0.7, base_url=base_url)
        prompt_imagen = llm.invoke(prompt_sistema).content.strip()
        return prompt_imagen.replace('"', '').replace('\n', ' ')
    except Exception:
        return "artistic colorful illustration representing music and rhythm, cinematic lighting, 8k"

def descargar_imagen_generada(prompt_ingles, ancho=1280, alto=720):
    prompt_encoded = urllib.parse.quote(prompt_ingles)
    url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width={ancho}&height={alto}&nologo=true"
    respuesta = requests.get(url, timeout=40)
    respuesta.raise_for_status()
    return Image.open(io.BytesIO(respuesta.content))

def generar_frame_subtitulo(base_img_path, texto, estilo_config, ancho=1280, alto=720):
    img = Image.open(base_img_path).convert("RGBA").resize((ancho, alto))
    if not texto.strip():
        return np.array(img.convert("RGB"))
        
    draw = ImageDraw.Draw(img)
    if estilo_config.get("emojis"):
        emoji = random.choice(estilo_config["emojis"])
        texto = f"{emoji} {texto.strip()} {emoji}"
        
    lineas = textwrap.wrap(texto, width=30)
    texto_formateado = "\n".join(lineas)
    
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", estilo_config["tamanio_fuente"])
    except IOError:
        font = ImageFont.load_default()
        
    bbox = draw.multiline_textbbox((0, 0), texto_formateado, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    x = (ancho - tw) / 2
    y = alto - th - 90
    pad = 20
    
    draw.rounded_rectangle(
        [x - pad, y - pad, x + tw + pad, y + th + pad], 
        radius=20, 
        fill=estilo_config["color_fondo"],
        outline=estilo_config["color_borde"],
        width=4
    )
    draw.multiline_text((x, y), texto_formateado, font=font, fill=estilo_config["color_texto"], align="center")
    
    return np.array(img.convert("RGB"))

# --- BARRA LATERAL (CONFIGURACIÓN GLOBAL) ---
st.sidebar.header("⚙️ Configuración del Servidor")
url_defecto = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
base_url = st.sidebar.text_input("URL de Ollama (Local / Ngrok)", value=url_defecto)

modelo_texto = st.sidebar.selectbox(
    "Modelo LLM (Texto/Código)",
    ["qwen2.5-coder", "llama3", "llama3.1", "llama3.2"],
    index=0
)

modelo_vision = st.sidebar.selectbox(
    "Modelo Visión (Imágenes)",
    ["llama3.2-vision", "llava"],
    index=0
)

# --- NAVEGACIÓN PRINCIPAL POR PESTAÑAS ---
tab_analisis, tab_multimedia = st.tabs(["📊 Analizador de Datos e Imágenes", "🎬 Generador de Video con Letra"])

# ==========================================
# PESTAÑA 1: ANALIZADOR DE DATOS
# ==========================================
with tab_analisis:
    st.header("Analizador de Datos Universal")
    
    archivo_datos = st.file_uploader(
        "Carga un archivo de datos (CSV, Excel, JSON, Parquet) o una imagen con una tabla", 
        type=["csv", "xlsx", "xls", "parquet", "json", "txt", "png", "jpg", "jpeg"],
        key="uploader_datos"
    )

    if archivo_datos:
        try:
            if archivo_datos.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                st.image(archivo_datos, caption="Imagen cargada", width=350)

            df = cargar_archivo_robusto(archivo_datos, base_url, modelo_vision)
            st.success(f"¡Datos cargados correctamente desde '{archivo_datos.name}'!")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Filas detectadas", df.shape[0])
            c2.metric("Columnas detectadas", df.shape[1])
            c3.metric("Valores Nulos", df.isna().sum().sum())

            with st.expander("👀 Ver DataFrame extraído", expanded=True):
                st.dataframe(df, use_container_width=True)

            st.divider()
            pregunta = st.text_input("💬 Consulta o pide un gráfico sobre tus datos:", key="pregunta_datos")

            if pregunta:
                prompt = f"""
Eres un analista de datos. Tienes un DataFrame de Pandas `df` con las columnas: {list(df.columns)}.
El usuario pide: "{pregunta}"
INSTRUCCIONES:
1. Genera código Python usando pandas o plotly.express (px).
2. Si es gráfico, asígnalo a `fig`. Si es texto/tabla, asigna a `resultado`.
3. Devuelve ÚNICAMENTE el código en un bloque markdown con tres acentos graves python.
"""
                with st.spinner("Analizando información..."):
                    llm = ChatOllama(model=modelo_texto, temperature=0, base_url=base_url)
                    respuesta = llm.invoke(prompt).content
                    
                    patron_codigo = r"```(?:python)?\s*(.*?)\s*```"
                    match = re.search(patron_codigo, respuesta, re.DOTALL)
                    codigo = match.group(1).strip() if match else respuesta.strip()

                    entorno_local = {"df": df, "px": px, "pd": pd, "st": st}
                    exec(codigo, entorno_local)

                    if "fig" in entorno_local and entorno_local["fig"] is not None:
                        st.plotly_chart(entorno_local["fig"], use_container_width=True)

                    if "resultado" in entorno_local and entorno_local["resultado"] is not None:
                        st.write("**Resultado:**")
                        st.write(entorno_local["resultado"])

                    with st.expander("🛠️ Ver código Python ejecutado"):
                        st.code(codigo, language="python")

        except Exception as e:
            st.error(f"Error procesando la fuente de datos: {e}")

# ==========================================
# PESTAÑA 2: GENERADOR DE VIDEO CON LETRA
# ==========================================
with tab_multimedia:
    st.header("Creador de Video con Letra y Estilo Automático")
    
    col_a, col_b = st.columns(2)
    with col_a:
        archivo_audio = st.file_uploader("1. Audio de la canción", type=["mp3", "wav", "m4a"], key="uploader_audio")
    with col_b:
        archivo_imagen = st.file_uploader("2. Imagen de Portada (Opcional)", type=["png", "jpg", "jpeg"], key="uploader_img_vid")

    modo_estilo = st.radio("Modo de diseño:", ["🤖 Detección Automática por IA", "🎨 Seleccionar Manualmente"], inline=True)
    estilo_manual = None
    if modo_estilo == "🎨 Seleccionar Manualmente":
        estilo_manual = st.selectbox("Elige la temática visual:", list(ESTILOS.keys()))

    if archivo_audio and st.button("🚀 Generar Video Completo", type="primary"):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_audio.name)[1]) as t_audio:
                t_audio.write(archivo_audio.read())
                ruta_audio = t_audio.name

            ruta_salida = tempfile.mktemp(suffix=".mp4")

            with st.spinner("🎧 Transcribiendo letra con IA..."):
                resultado_whisper = cargar_whisper().transcribe(ruta_audio, language="es")
                segmentos = resultado_whisper.get("segments", [])
                letra_completa = " ".join([s["text"] for s in segmentos])

            if modo_estilo == "🤖 Detección Automática por IA":
                with st.spinner("🧠 Analizando la temática de la letra..."):
                    nombre_estilo = detectar_estilo_automatico(letra_completa, base_url, modelo_texto)
            else:
                nombre_estilo = estilo_manual
                
            config_estilo = ESTILOS[nombre_estilo]
            st.info(f"🎨 **Estilo asignado:** {nombre_estilo}")

            if archivo_imagen is not None:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_img:
                    t_img.write(archivo_imagen.read())
                    ruta_img = t_img.name
            else:
                with st.spinner("🎨 Diseñando portada temática con IA según la letra..."):
                    prompt_arte = generar_prompt_visual(letra_completa, base_url, modelo_texto)
                    st.caption(f"✨ **Prompt de imagen:** *{prompt_arte}*")
                    
                    img_objeto = descargar_imagen_generada(prompt_arte)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_img:
                        img_objeto.save(t_img.name)
                        ruta_img = t_img.name
                    st.image(img_objeto, caption="Portada generada automáticamente", width=350)

            with st.spinner("🎬 Ensamblando video y sincronizando subtítulos..."):
                audio_clip = AudioFileClip(ruta_audio)
                duracion_total = audio_clip.duration

                fondo_base = ImageClip(ruta_img).set_duration(duracion_total)
                clips_subtitulos = [fondo_base]

                for seg in segmentos:
                    inicio = seg["start"]
                    fin = min(seg["end"], duracion_total)
                    duracion_seg = fin - inicio
                    
                    if duracion_seg > 0 and seg["text"].strip():
                        frame_np = generar_frame_subtitulo(ruta_img, seg["text"], config_estilo)
                        txt_clip = (ImageClip(frame_np)
                                    .set_start(inicio)
                                    .set_duration(duracion_seg))
                        clips_subtitulos.append(txt_clip)

                video_final = CompositeVideoClip(clips_subtitulos).set_audio(audio_clip)
                video_final.write_videofile(ruta_salida, fps=2, codec="libx264", audio_codec="aac")

                audio_clip.close()
                video_final.close()

            st.success("¡Video generado exitosamente!")
            st.video(ruta_salida)

            with open(ruta_salida, "rb") as file:
                st.download_button(
                    label="📥 Descargar Video MP4",
                    data=file,
                    file_name=f"{os.path.splitext(archivo_audio.name)[0]}_con_letra.mp4",
                    mime="video/mp4"
                )

        except Exception as e:
            st.error(f"Error durante el procesamiento del video: {e}")
