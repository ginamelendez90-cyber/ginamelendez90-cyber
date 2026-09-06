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
    page_title="Generador de Video con Letra e IA",
    page_icon="🎬",
    layout="wide"
)

# Carga en caché de Whisper
@st.cache_resource
def cargar_whisper():
    return whisper.load_model("tiny")

# Configuración de colores y estilos de subtítulos
ESTILOS = {
    "🧸 Infantil / Niños": {
        "color_texto": (255, 235, 59),      # Amarillo brillante
        "color_borde": (233, 30, 99),       # Rosa/Magenta
        "color_fondo": (40, 10, 80, 230),   # Morado oscuro con alta opacidad
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

# --- FUNCIONES DE RENDERIZADO Y PROCESAMIENTO ---

def obtener_fuente_robusta(tamanio):
    """Carga una fuente válida del sistema para evitar texto diminuto o invisible."""
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
            
    # Respaldo para versiones modernas de Pillow si no hay fuentes del SO
    try:
        return ImageFont.load_default(size=tamanio)
    except TypeError:
        return ImageFont.load_default()

def generar_frame_subtitulo(base_img_path, texto, estilo_config, ancho=1280, alto=720):
    img = Image.open(base_img_path).convert("RGBA").resize((ancho, alto))
    texto_limpio = texto.strip()
    
    if not texto_limpio:
        return np.array(img.convert("RGB"))
        
    draw = ImageDraw.Draw(img)
    tamanio = estilo_config.get("tamanio_fuente", 40)
    font = obtener_fuente_robusta(tamanio)
    
    # Ajuste de líneas de texto
    lineas = textwrap.wrap(texto_limpio, width=28)
    texto_formateado = "\n".join(lineas)
    
    # Cálculo preciso de caja y centro
    bbox = draw.multiline_textbbox((0, 0), texto_formateado, font=font, align="center")
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    # Coordenadas centrales exactas (Abajo y al centro)
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
    
    # Fondo con bordes redondeados
    draw.rounded_rectangle(
        caja, 
        radius=18, 
        fill=estilo_config["color_fondo"],
        outline=estilo_config["color_borde"],
        width=4
    )
    
    # Renderizado centrado mediante anclaje 'mm' (middle-middle)
    draw.multiline_text(
        (cx, cy), 
        texto_formateado, 
        font=font, 
        fill=estilo_config["color_texto"], 
        align="center",
        anchor="mm"
    )
    
    return np.array(img.convert("RGB"))

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

# --- INTERFAZ DE USUARIO ---
st.sidebar.header("⚙️ Configuración del Servidor")
url_defecto = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
base_url = st.sidebar.text_input("URL de Ollama (Local / Ngrok)", value=url_defecto)

modelo_texto = st.sidebar.selectbox(
    "Modelo LLM (Texto/Prompt)",
    ["qwen2.5-coder", "llama3", "llama3.1", "llama3.2"],
    index=0
)

st.title("🎬 Creador de Video Musical con Letra Dinámica")
st.write("Sube un archivo de audio y genera un video con subtítulos centrados y legibles.")

col_a, col_b = st.columns(2)
with col_a:
    archivo_audio = st.file_uploader("1. Audio de la canción", type=["mp3", "wav", "m4a"], key="uploader_audio")
with col_b:
    archivo_imagen = st.file_uploader("2. Imagen de Portada (Opcional)", type=["png", "jpg", "jpeg"], key="uploader_img_vid")

modo_estilo = st.radio(
    "Modo de diseño:", 
    ["🤖 Detección Automática por IA", "🎨 Seleccionar Manualmente"], 
    horizontal=True
)

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
