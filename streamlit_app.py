import streamlit as st
import tempfile
import os
import textwrap
import urllib.parse
import requests
import io
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

# Configuración de la ventana
st.set_page_config(
    page_title="Generador de Video Musical Dinámico con IA",
    page_icon="🎬",
    layout="wide"
)

# Carga en caché de Whisper
@st.cache_resource
def cargar_whisper():
    return whisper.load_model("tiny")

# Estilos visuales de subtítulos
ESTILOS = {
    "🧸 Infantil / Niños": {
        "color_texto": (255, 235, 59),      # Amarillo brillante
        "color_borde": (233, 30, 99),       # Rosa/Magenta
        "color_fondo": (40, 10, 80, 230),   # Morado oscuro
        "tamanio_fuente": 44
    },
    "⚡ Neón / Pop": {
        "color_texto": (0, 255, 255),       # Cyan Neón
        "color_borde": (255, 0, 128),      # Neón Rosa
        "color_fondo": (10, 10, 20, 230),   # Azul oscuro
        "tamanio_fuente": 42
    },
    "✨ Elegante / Balada": {
        "color_texto": (255, 255, 255),     # Blanco puro
        "color_borde": (212, 175, 55),      # Dorado
        "color_fondo": (0, 0, 0, 220),      # Negro sutil
        "tamanio_fuente": 38
    }
}

# --- FUNCIONES DE FUENTE Y SUBTÍTULOS ---

def obtener_fuente_robusta(tamanio):
    """Carga una fuente válida para garantizar legibilidad."""
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

def generar_frame_subtitulo(base_img_path_or_obj, texto, estilo_config, ancho=1280, alto=720):
    if isinstance(base_img_path_or_obj, str):
        img = Image.open(base_img_path_or_obj).convert("RGBA").resize((ancho, alto))
    else:
        img = base_img_path_or_obj.convert("RGBA").resize((ancho, alto))
        
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
    
    cx = ancho / 2
    cy = alto - 110
    
    pad_x = 30
    pad_y = 18
    caja = [
        cx - (tw / 2) - pad_x,
        cy - (th / 2) - pad_y,
        cx + (tw / 2) + pad_x,
        cy + (th / 2) + pad_y
    ]
    
    draw.rounded_rectangle(
        caja, 
        radius=18, 
        fill=estilo_config["color_fondo"],
        outline=estilo_config["color_borde"],
        width=4
    )
    
    draw.multiline_text(
        (cx, cy), 
        texto_formateado, 
        font=font, 
        fill=estilo_config["color_texto"], 
        align="center",
        anchor="mm"
    )
    
    return np.array(img.convert("RGB"))

# --- FUNCIONES DE IA Y IMÁGENES ---

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

def generar_prompt_escena(frase, base_url, modelo_texto):
    """Genera un prompt específico para la escena representada por una sola frase."""
    prompt_sistema = f"""
Create a short visual image prompt IN ENGLISH (max 12 words) for an AI image generator capturing the scene of this lyric:
"{frase}"
Output ONLY the English prompt, no explanations.
"""
    try:
        llm = ChatOllama(model=modelo_texto, temperature=0.7, base_url=base_url)
        prompt_escena = llm.invoke(prompt_sistema).content.strip()
        return prompt_escena.replace('"', '').replace('\n', ' ')
    except Exception:
        return f"artistic illustration of {frase[:30]}"

def descargar_imagen_generada(prompt_ingles, ancho=1280, alto=720):
    prompt_encoded = urllib.parse.quote(prompt_ingles)
    url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width={ancho}&height={alto}&nologo=true"
    respuesta = requests.get(url, timeout=30)
    respuesta.raise_for_status()
    return Image.open(io.BytesIO(respuesta.content))

# --- INTERFAZ ---
st.sidebar.header("⚙️ Configuración del Servidor")
url_defecto = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
base_url = st.sidebar.text_input("URL de Ollama (Local / Ngrok)", value=url_defecto)

modelo_texto = st.sidebar.selectbox(
    "Modelo LLM (Texto/Prompt)",
    ["qwen2.5-coder", "llama3", "llama3.1", "llama3.2"],
    index=0
)

st.title("🎬 Creador de Video Musical con Imágenes Dinámicas")
st.write("Genera videos musicales automáticos con cambio de fondo por escena o frase.")

col_a, col_b = st.columns(2)
with col_a:
    archivo_audio = st.file_uploader("1. Audio de la canción", type=["mp3", "wav", "m4a"], key="uploader_audio")
with col_b:
    archivo_imagen = st.file_uploader("2. Portada fija inicial (Opcional)", type=["png", "jpg", "jpeg"], key="uploader_img_vid")

modo_imagen = st.radio(
    "🖼️ Modo de Imágenes de Fondo:",
    ["🖼️ Cambiar imagen por cada frase/escena", "📌 Una sola imagen fija para toda la canción"],
    horizontal=True
)

modo_estilo = st.radio(
    "🎨 Estilo de Subtítulos:", 
    ["🤖 Detección Automática por IA", "🎨 Seleccionar Manualmente"], 
    horizontal=True
)

estilo_manual = None
if modo_estilo == "🎨 Seleccionar Manualmente":
    estilo_manual = st.selectbox("Elige la temática visual:", list(ESTILOS.keys()))

if archivo_audio and st.button("🚀 Generar Video Musical", type="primary"):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_audio.name)[1]) as t_audio:
            t_audio.write(archivo_audio.read())
            ruta_audio = t_audio.name

        ruta_salida = tempfile.mktemp(suffix=".mp4")

        # 1. Transcripción
        with st.spinner("🎧 Transcribiendo letra y sincronizando tiempos..."):
            resultado_whisper = cargar_whisper().transcribe(ruta_audio, language="es")
            segmentos = resultado_whisper.get("segments", [])
            letra_completa = " ".join([s["text"] for s in segmentos])

        # 2. Estilo
        if modo_estilo == "🤖 Detección Automática por IA":
            with st.spinner("🧠 Analizando tono de la letra..."):
                nombre_estilo = detectar_estilo_automatico(letra_completa, base_url, modelo_texto)
        else:
            nombre_estilo = estilo_manual
            
        config_estilo = ESTILOS[nombre_estilo]
        st.info(f"🎨 **Estilo asignado:** {nombre_estilo}")

        # 3. Preparación de portada base o fallback
        ruta_img_base = None
        if archivo_imagen is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_img:
                t_img.write(archivo_imagen.read())
                ruta_img_base = t_img.name
        else:
            with st.spinner("🎨 Generando portada inicial..."):
                prompt_inicial = generar_prompt_escena(letra_completa[:200], base_url, modelo_texto)
                img_obj = descargar_imagen_generada(prompt_inicial)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_img:
                    img_obj.save(t_img.name)
                    ruta_img_base = t_img.name

        # 4. Creación de Clips de Video
        with st.spinner("🎬 Generando escenas e integrando subtítulos centrados..."):
            audio_clip = AudioFileClip(ruta_audio)
            duracion_total = audio_clip.duration
            clips = []

            progreso = st.progress(0.0)
            total_seg = len(segmentos)

            for i, seg in enumerate(segmentos):
                inicio = seg["start"]
                fin = min(seg["end"], duracion_total)
                duracion_seg = fin - inicio
                frase = seg["text"].strip()

                if duracion_seg > 0 and frase:
                    img_actual = ruta_img_base

                    # Si el usuario quiere múltiples imágenes cambiantes
                    if modo_imagen == "🖼️ Cambiar imagen por cada frase/escena":
                        try:
                            prompt_escena = generar_prompt_escena(frase, base_url, modelo_texto)
                            img_obj_escena = descargar_imagen_generada(prompt_escena)
                            img_actual = img_obj_escena
                        except Exception:
                            img_actual = ruta_img_base # Si falla descarga, usa la base

                    frame_np = generar_frame_subtitulo(img_actual, frase, config_estilo)
                    txt_clip = (ImageClip(frame_np)
                                .set_start(inicio)
                                .set_duration(duracion_seg))
                    clips.append(txt_clip)

                progreso.progress((i + 1) / total_seg)

            if not clips:
                # Fondo estático en caso de audio instrumental sin letra
                clips.append(ImageClip(ruta_img_base).set_duration(duracion_total))

            video_final = CompositeVideoClip(clips).set_audio(audio_clip)
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
        st.error(f"Error generando el video: {e}")
