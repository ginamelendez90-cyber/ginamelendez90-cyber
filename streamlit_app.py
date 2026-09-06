import streamlit as st
import tempfile
import os
import textwrap
import urllib.parse
import requests
import io
import random
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import whisper

# Importaciones dinámicas compatibles
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

try:
    from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip
except ImportError:
    from moviepy import AudioFileClip, ImageClip, CompositeVideoClip

# Configuración de Streamlit
st.set_page_config(
    page_title="Generador de Video Musical Dinámico",
    page_icon="🎬",
    layout="wide"
)

# Carga diferida de Whisper
@st.cache_resource
def cargar_whisper():
    return whisper.load_model("tiny")

# Estilos visuales de subtítulos
ESTILOS = {
    "🧸 Infantil / Niños": {
        "color_texto": (255, 235, 59),      # Amarillo
        "color_borde": (233, 30, 99),       # Rosa
        "color_fondo": (40, 10, 80, 230),   # Morado
        "tamanio_fuente": 44
    },
    "⚡ Neón / Pop": {
        "color_texto": (0, 255, 255),       # Cyan
        "color_borde": (255, 0, 128),      # Rosa Neón
        "color_fondo": (10, 10, 20, 230),   # Azul oscuro
        "tamanio_fuente": 42
    },
    "✨ Elegante / Balada": {
        "color_texto": (255, 255, 255),     # Blanco
        "color_borde": (212, 175, 55),      # Dorado
        "color_fondo": (0, 0, 0, 220),      # Negro
        "tamanio_fuente": 38
    }
}

# --- FUNCIONES DE RENDERING Y FUENTES ---

def obtener_fuente_robusta(tamanio):
    fuentes_sistema = [
        "DejaVuSans-Bold.ttf",
        "FreeSansBold.ttf",
        "LiberationSans-Bold.ttf",
        "arial.ttf"
    ]
    for ruta_fuente in fuentes_sistema:
        try:
            return ImageFont.truetype(ruta_fuente, tamanio)
        except IOError:
            continue
    try:
        return ImageFont.load_default(size=tamanio)
    except TypeError:
        return ImageFont.load_default()

def generar_frame_subtitulo(base_img_obj, texto, estilo_config, ancho=1280, alto=720):
    img = base_img_obj.convert("RGBA").resize((ancho, alto))
    texto_limpio = texto.strip()
    
    if not texto_limpio:
        return np.array(img.convert("RGB"))
        
    draw = ImageDraw.Draw(img)
    tamanio = estilo_config.get("tamanio_fuente", 40)
    font = obtener_fuente_robusta(tamanio)
    
    lineas = textwrap.wrap(texto_limpio, width=28)
    texto_formateado = "\n".join(lineas)
    
    bbox = draw.multiline_textbbox((0, 0), texto_formateado, font=font, align="center")
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    cx, cy = ancho / 2, alto - 110
    pad_x, pad_y = 30, 18
    
    caja = [
        cx - (tw / 2) - pad_x,
        cy - (th / 2) - pad_y,
        cx + (tw / 2) + pad_x,
        cy + (th / 2) + pad_y
    ]
    
    draw.rounded_rectangle(caja, radius=18, fill=estilo_config["color_fondo"], outline=estilo_config["color_borde"], width=4)
    draw.multiline_text((cx, cy), texto_formateado, font=font, fill=estilo_config["color_texto"], align="center", anchor="mm")
    
    return np.array(img.convert("RGB"))

# --- FUNCIONES DE IA DE IMAGEN Y PROMPTS CON SISTEMA DE REINTENTOS ---

def descargar_imagen_generada(prompt_ingles, ancho=1280, alto=720, reintentos_max=3):
    prompt_encoded = urllib.parse.quote(prompt_ingles)
    seed_aleatorio = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width={ancho}&height={alto}&nologo=true&seed={seed_aleatorio}"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for intento in range(reintentos_max):
        try:
            respuesta = requests.get(url, headers=headers, timeout=30)
            if respuesta.status_code == 429:
                # Si nos limita el servidor, esperamos progresivamente (3s, 6s, 9s)
                tiempo_espera = (intento + 1) * 3
                time.sleep(tiempo_espera)
                continue
            respuesta.raise_for_status()
            return Image.open(io.BytesIO(respuesta.content))
        except Exception as e:
            if intento == reintentos_max - 1:
                raise e
            time.sleep(3)
            
    raise Exception("No se pudo obtener la imagen tras varios reintentos por límite de tráfico.")

def generar_prompt_escena(texto_escena, base_url, modelo_texto):
    prompt_sistema = f"""
You are a visual director. Create a vivid 10-word visual scene prompt IN ENGLISH for an AI image generator based on these lyrics:
"{texto_escena}"
Output ONLY the English visual prompt, no commentary.
"""
    try:
        llm = ChatOllama(model=modelo_texto, temperature=0.7, base_url=base_url)
        res = llm.invoke(prompt_sistema).content.strip()
        return res.replace('"', '').replace('\n', ' ')
    except Exception:
        return f"artistic illustration of {texto_escena[:30]}"

def agrupar_en_escenas(segmentos, duracion_minima=10.0):
    """Agrupa subtítulos pequeños en bloques de tiempo (escenas) para reducir consumo de API."""
    escenas = []
    escena_actual = {"start": 0.0, "end": 0.0, "text": ""}
    
    for seg in segmentos:
        if not escena_actual["text"]:
            escena_actual["start"] = seg["start"]
            
        escena_actual["text"] += " " + seg["text"].strip()
        escena_actual["end"] = seg["end"]
        
        if (escena_actual["end"] - escena_actual["start"]) >= duracion_minima:
            escenas.append(escena_actual)
            escena_actual = {"start": escena_actual["end"], "end": escena_actual["end"], "text": ""}
            
    if escena_actual["text"]:
        escenas.append(escena_actual)
        
    return escenas

# --- INTERFAZ DE USUARIO ---
st.sidebar.header("⚙️ Configuración Servidor")
url_defecto = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
base_url = st.sidebar.text_input("URL Ollama", value=url_defecto)

modelo_texto = st.sidebar.selectbox("Modelo LLM", ["qwen2.5-coder", "llama3", "llama3.1", "llama3.2"], index=0)

st.title("🎬 Creador de Video Musical con Cambio Dinámico de Fondo")

col_a, col_b = st.columns(2)
with col_a:
    archivo_audio = st.file_uploader("1. Audio de la canción", type=["mp3", "wav", "m4a"])
with col_b:
    archivo_imagen = st.file_uploader("2. Portada fija de respaldo (Opcional)", type=["png", "jpg", "jpeg"])

modo_imagen = st.radio(
    "🖼️ Generación de Fondos:",
    ["🖼️ Cambiar de imagen cada 8-12 segundos (Varias escenas)", "📌 Una sola imagen fija todo el video"],
    horizontal=True
)

estilo_seleccionado = st.selectbox("🎨 Elige la temática visual de los subtítulos:", list(ESTILOS.keys()))

if archivo_audio and st.button("🚀 Generar Video Musical", type="primary"):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_audio.name)[1]) as t_audio:
            t_audio.write(archivo_audio.read())
            ruta_audio = t_audio.name

        ruta_salida = tempfile.mktemp(suffix=".mp4")
        config_estilo = ESTILOS[estilo_seleccionado]

        # 1. Transcripción
        with st.spinner("🎧 Transcribiendo letra con Whisper..."):
            resultado_whisper = cargar_whisper().transcribe(ruta_audio, language="es")
            segmentos = resultado_whisper.get("segments", [])

        # 2. Cargar imagen por defecto
        if archivo_imagen is not None:
            img_base = Image.open(archivo_imagen)
        else:
            img_base = Image.new('RGB', (1280, 720), color=(20, 20, 40))

        audio_clip = AudioFileClip(ruta_audio)
        duracion_total = audio_clip.duration

        # 3. Procesar Escenas
        clips_finales = []
        
        if modo_imagen == "🖼️ Cambiar de imagen cada 8-12 segundos (Varias escenas)":
            escenas = agrupar_en_escenas(segmentos, duracion_minima=10.0)
            st.info(f"🎨 Se han generado **{len(escenas)} escenas dinámicas** para este video.")
            
            progreso = st.progress(0.0)
            
            for idx, esc in enumerate(escenas):
                t_inicio = esc["start"]
                t_fin = min(esc["end"], duracion_total)
                dur = t_fin - t_inicio

                if dur <= 0:
                    continue

                # Pausa breve anti-saturación antes de pedir la siguiente imagen
                if idx > 0:
                    time.sleep(2.5)

                # Intentar descargar imagen única para la escena con reintentos
                try:
                    prompt_escena = generar_prompt_escena(esc["text"], base_url, modelo_texto)
                    img_escena = descargar_imagen_generada(prompt_escena)
                except Exception as err:
                    st.warning(f"⚠️ Fondo {idx+1} usó imagen base de respaldo: {err}")
                    img_escena = img_base

                # Crear fondo para la escena
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_file:
                    img_escena.save(t_file.name)
                    bg_clip = ImageClip(t_file.name).set_start(t_inicio).set_duration(dur)
                    clips_finales.append(bg_clip)

                progreso.progress((idx + 1) / len(escenas))
        else:
            # Fondo Fijo
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_file:
                img_base.save(t_file.name)
                bg_clip = ImageClip(t_file.name).set_duration(duracion_total)
                clips_finales.append(bg_clip)

        # 4. Superponer los Subtítulos Centrados
        with st.spinner("🎬 Sincronizando subtítulos en pantalla..."):
            for seg in segmentos:
                inicio = seg["start"]
                fin = min(seg["end"], duracion_total)
                dur_seg = fin - inicio
                frase = seg["text"].strip()

                if dur_seg > 0 and frase:
                    # Generar frame transparente con texto centrado
                    img_transparente = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
                    frame_txt = generar_frame_subtitulo(img_transparente, frase, config_estilo)
                    
                    txt_clip = (ImageClip(frame_txt)
                                .set_start(inicio)
                                .set_duration(dur_seg))
                    clips_finales.append(txt_clip)

            # Renderizado final con MoviePy
            video_final = CompositeVideoClip(clips_finales).set_audio(audio_clip)
            video_final.write_videofile(ruta_salida, fps=2, codec="libx264", audio_codec="aac")

            audio_clip.close()
            video_final.close()

        st.success("¡Video dinámico generado con éxito!")
        st.video(ruta_salida)

        with open(ruta_salida, "rb") as file:
            st.download_button(
                label="📥 Descargar Video MP4",
                data=file,
                file_name=f"{os.path.splitext(archivo_audio.name)[0]}_dinamico.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Error procesando el video: {e}")
