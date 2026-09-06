import streamlit as st
import tempfile
import os
import urllib.parse
import requests
import io
import time
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont

# Importaciones de MoviePy (compatible con v1 y v2)
try:
    from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
except ImportError:
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

# Compatibilidad de filtros PIL
try:
    LANCZOS_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    LANCZOS_FILTER = Image.LANCZOS

# Configuración de página
st.set_page_config(page_title="Creador Personalizado de Videos Tech", page_icon="🎬", layout="wide")

# --- FUNCIONES DE ADAPTACIÓN MOVIEPY ---
def fijar_duracion(clip, duracion):
    return clip.with_duration(duracion) if hasattr(clip, "with_duration") else clip.set_duration(duracion)

def fijar_audio(clip, audio_clip):
    return clip.with_audio(audio_clip) if hasattr(clip, "with_audio") else clip.set_audio(audio_clip)

# --- GENERACIÓN DE VOZ (Edge-TTS) ---
async def generar_audio_async(texto, ruta_salida, voz="es-MX-JorgeNeural", velocidad="+0%"):
    communicate = edge_tts.Communicate(texto, voz, rate=velocidad)
    await communicate.save(ruta_salida)

def generar_audio(texto, ruta_salida, voz="es-MX-JorgeNeural", velocidad="+0%"):
    try:
        asyncio.run(generar_audio_async(texto, ruta_salida, voz, velocidad))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generar_audio_async(texto, ruta_salida, voz, velocidad))

# --- BÚSQUEDA Y PROCESAMIENTO DE IMÁGENES REALES ---
def buscar_imagen_real_web(query):
    """Busca fotos reales usando Wikimedia Commons o DuckDuckGo."""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Búsqueda en Wikimedia Commons
    try:
        url_wiki = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&prop=imageinfo&iiprop=url&gsrsearch={urllib.parse.quote(query)}&gsrnamespace=6&format=json"
        res = requests.get(url_wiki, headers=headers, timeout=8).json()
        pages = res.get("query", {}).get("pages", {})
        for page in pages.values():
            info = page.get("imageinfo", [])
            if info:
                img_url = info[0].get("url")
                if img_url and img_url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    r = requests.get(img_url, headers=headers, timeout=8)
                    if r.status_code == 200:
                        return Image.open(io.BytesIO(r.content))
    except Exception:
        pass

    # 2. Búsqueda con DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            resultados = list(ddgs.images(query, max_results=3))
            for item in resultados:
                img_url = item.get("image")
                r = requests.get(img_url, headers=headers, timeout=8)
                if r.status_code == 200:
                    return Image.open(io.BytesIO(r.content))
    except Exception:
        pass

    # Imagen de respaldo
    img = Image.new("RGB", (960, 960), color=(20, 30, 45))
    return img

# --- COMPOSICIÓN DEL FRAME VERTICAL (1080x1920) ---
def crear_frame_diapositiva(imagen_base, titulo, texto_overlay):
    canvas = Image.new("RGBA", (1080, 1920), (10, 15, 26, 255))
    
    # Redimensionar la foto real manteniendo proporción dentro de un cuadro de 960x960
    img = imagen_base.convert("RGBA")
    img.thumbnail((960, 960), LANCZOS_FILTER)
    
    # Centrar la foto real
    x_pos = (1080 - img.width) // 2
    y_pos = (960 - img.height) // 2 + 280
    canvas.paste(img, (x_pos, y_pos), img if img.mode == 'RGBA' else None)

    draw = ImageDraw.Draw(canvas)

    try:
        font_titulo = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
        font_texto = ImageFont.truetype("FreeSansBold.ttf", 34)
    except IOError:
        font_titulo = font_texto = ImageFont.load_default()

    # Tarjeta de Título Superior
    draw.rounded_rectangle([60, 100, 1020, 220], radius=20, fill=(0, 0, 0, 230), outline=(0, 255, 200), width=4)
    draw.text((540, 160), str(titulo).upper(), font=font_titulo, fill=(0, 255, 200), anchor="mm")

    # Tarjeta Inferior de Especificaciones
    draw.rounded_rectangle([60, 1300, 1020, 1800], radius=25, fill=(15, 23, 42, 240), outline=(255, 255, 255), width=3)
    
    lineas = str(texto_overlay).split("\n")
    y_text = 1350
    for linea in lineas:
        if linea.strip():
            draw.text((100, y_text), f"• {linea.strip()}", font=font_texto, fill=(255, 255, 255))
            y_text += 65

    return canvas.convert("RGB")

# --- INTERFAZ STREAMLIT ---
st.title("🎬 Creador Personalizado de Videos Tech")
st.caption("Configura la duración, sube fotos reales y define tus propias escenas.")

# --- BARRA LATERAL: CONFIGURACIÓN GENERAL ---
st.sidebar.header("⚙️ Configuración General")
voz_locutor = st.sidebar.selectbox("Voz de la IA", [
    "es-MX-JorgeNeural (Hombre - México)",
    "es-MX-DaliaNeural (Mujer - México)",
    "es-ES-AlvaroNeural (Hombre - España)",
    "es-AR-TomasNeural (Hombre - Argentina)"
])

velocidad_voz = st.sidebar.select_slider("Velocidad de la locución", options=["-20%", "-10%", "+0%", "+10%", "+25%", "+50%"], value="+0%")

nombre_celular = st.text_input("📱 Nombre del Teléfono:", value="Poco X6 Pro")
num_escenas = st.number_input("🔢 Número de Escenas:", min_value=1, max_value=8, value=3, step=1)

st.markdown("---")
st.subheader("✏️ Configura tus Escenas y Duración")

escenas_config = []

# --- CONFIGURACIÓN DE CADA ESCENA ---
for i in range(num_escenas):
    with st.expander(f"🎬 Escena {i+1}", expanded=(i == 0)):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            titulo = st.text_input(f"Título Superior (Escena {i+1}):", value=f"PANTALLA Y PROCESADOR" if i==0 else f"CÁMARA Y BATERÍA" if i==1 else f"VEREDICTO FINAL", key=f"tit_{i}")
            locucion = st.text_area(f"Texto de Locución (Voz narrada):", value=f"El {nombre_celular} incluye una pantalla fluida a 120Hz y gran potencia.", key=f"loc_{i}")
            puntos = st.text_area(f"Puntos en Pantalla (Ficha Técnica):", value="• Pantalla AMOLED 120Hz\n• Procesador potente\n• Excelente fluidez", key=f"pts_{i}")

        with col2:
            st.markdown("**⏱️ Duración de la Escena:**")
            duracion_modo = st.radio("Sincronizar duración con:", ["Duración de la Voz", "Tiempo Fijo (Segundos)"], key=f"dur_mode_{i}")
            
            duracion_fija = 5.0
            if duracion_modo == "Tiempo Fijo (Segundos)":
                duracion_fija = st.number_input("Duración (seg):", min_value=2.0, max_value=30.0, value=6.0, step=0.5, key=f"dur_sec_{i}")

            st.markdown("**🖼️ Foto Real del Celular:**")
            origen_imagen = st.radio("Origen de la foto:", ["Buscar en la Web", "Subir Foto Real", "URL de Imagen"], key=f"img_src_{i}")
            
            imagen_escena = None
            if origen_imagen == "Subir Foto Real":
                uploaded_file = st.file_uploader(f"Subir foto para escena {i+1}:", type=["jpg", "jpeg", "png", "webp"], key=f"file_{i}")
                if uploaded_file is not None:
                    imagen_escena = Image.open(uploaded_file)
            elif origen_imagen == "URL de Imagen":
                url_input = st.text_input(f"Pega la URL de la foto:", key=f"url_{i}")
                if url_input:
                    try:
                        resp = requests.get(url_input, timeout=8)
                        if resp.status_code == 200:
                            imagen_escena = Image.open(io.BytesIO(resp.content))
                    except Exception:
                        st.warning("No se pudo cargar la imagen desde la URL.")

            busqueda_tag = st.text_input("Palabra de búsqueda web:", value=f"{nombre_celular} phone real product", key=f"kw_{i}") if origen_imagen == "Buscar en la Web" else ""

        escenas_config.append({
            "titulo": titulo,
            "texto_locucion": locucion,
            "puntos_pantalla": puntos,
            "duracion_modo": duracion_modo,
            "duracion_fija": duracion_fija,
            "origen_imagen": origen_imagen,
            "imagen_escena": imagen_escena,
            "busqueda_tag": busqueda_tag
        })

# --- BOTÓN PARA GENERAR VIDEO ---
if st.button("🚀 Crear Video Personalizado", type="primary") and nombre_celular:
    try:
        voz_codigo = voz_locutor.split(" ")[0]
        clips_video = []
        progreso = st.progress(0.0)

        for i, escena in enumerate(escenas_config):
            st.info(f"🎬 Procesando Escena {i+1} de {len(escenas_config)}: {escena['titulo']}")

            # 1. Generar Audio TTS
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
                generar_audio(escena["texto_locucion"], t_audio.name, voz=voz_codigo, velocidad=velocidad_voz)
                audio_clip = AudioFileClip(t_audio.name)
                duracion_audio = audio_clip.duration

            # 2. Determinar la duración final de la escena
            if escena["duracion_modo"] == "Tiempo Fijo (Segundos)":
                duracion_final = max(escena["duracion_fija"], duracion_audio)
            else:
                duracion_final = duracion_audio

            # 3. Obtener Imagen Real
            if escena["origen_imagen"] in ["Subir Foto Real", "URL de Imagen"] and escena["imagen_escena"] is not None:
                img_base = escena["imagen_escena"]
            else:
                img_base = buscar_imagen_real_web(escena["busqueda_tag"] if escena["busqueda_tag"] else f"{nombre_celular} smartphone")

            # 4. Crear Frame de la diapositiva
            img_final = crear_frame_diapositiva(img_base, escena["titulo"], escena["puntos_pantalla"])

            # 5. Crear Clip de Video
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_frame:
                img_final.save(t_frame.name)
                v_clip = ImageClip(t_frame.name)
                v_clip = fijar_duracion(v_clip, duracion_final)
                v_clip = fijar_audio(v_clip, audio_clip)
                clips_video.append(v_clip)

            progreso.progress((i + 1) / len(escenas_config))
            time.sleep(0.3)

        # 6. Renderizar Video Final
        with st.spinner("🎥 Renderizando el video final..."):
            video_final = concatenate_videoclips(clips_video, method="compose")
            ruta_mp4 = tempfile.mktemp(suffix=".mp4")
            video_final.write_videofile(ruta_mp4, fps=24, codec="libx264", audio_codec="aac")
            video_final.close()

        st.success(f"🎉 ¡Video de {len(clips_video)} escenas generado con éxito!")
        st.video(ruta_mp4)

        with open(ruta_mp4, "rb") as file:
            st.download_button(
                label="📥 Descargar Video MP4",
                data=file,
                file_name=f"{nombre_celular.replace(' ', '_')}_Review.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Error durante el proceso: {e}")
