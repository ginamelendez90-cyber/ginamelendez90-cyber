import streamlit as st
import tempfile
import os
import urllib.parse
import requests
import io
import time
import textwrap
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont

# Importaciones compatibles con MoviePy v1 y v2
try:
    from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
except ImportError:
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

# Resampling compatible con PIL
try:
    LANCZOS_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    LANCZOS_FILTER = Image.LANCZOS

# Configuración de página de Streamlit
st.set_page_config(page_title="Creador Tech - Fuentes HD", page_icon="📱", layout="wide")

# --- FUNCIONES ADAPTADORAS MOVIEPY ---
def fijar_duracion(clip, duracion):
    return clip.with_duration(duracion) if hasattr(clip, "with_duration") else clip.set_duration(duracion)

def fijar_audio(clip, audio_clip):
    return clip.with_audio(audio_clip) if hasattr(clip, "with_audio") else clip.set_audio(audio_clip)

# --- GARANTIZAR FUENTES TIPOGRÁFICAS EN EL SERVIDOR (SOLUCIÓN AL TEXTO INVISIBLE) ---
@st.cache_resource
def cargar_fuente_hd(tamano):
    """Garantiza la carga de una fuente tipográfica de gran tamaño en cualquier servidor en la nube."""
    # 1. Probar fuentes locales del sistema
    fuentes_sistema = ["DejaVuSans-Bold.ttf", "FreeSansBold.ttf", "arial.ttf", "Arial.ttf"]
    for f in fuentes_sistema:
        try:
            return ImageFont.truetype(f, tamano)
        except IOError:
            continue

    # 2. Descargar automáticamente Roboto-Bold si el servidor Linux no tiene fuentes
    ruta_temp = os.path.join(tempfile.gettempdir(), "Roboto-Bold.ttf")
    if not os.path.exists(ruta_temp):
        try:
            url_font = "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto-Bold.ttf"
            res = requests.get(url_font, timeout=10)
            if res.status_code == 200:
                with open(ruta_temp, "wb") as file:
                    file.write(res.content)
        except Exception:
            pass

    if os.path.exists(ruta_temp):
        try:
            return ImageFont.truetype(ruta_temp, tamano)
        except Exception:
            pass

    # 3. Respaldo para versiones recientes de PIL
    try:
        return ImageFont.load_default(size=tamano)
    except TypeError:
        return ImageFont.load_default()

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

# --- BÚSQUEDA DE IMÁGENES REALES ---
def buscar_imagen_real_web(query):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Búsqueda en Wikimedia
    try:
        url_wiki = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&prop=imageinfo&iiprop=url&gsrsearch={urllib.parse.quote(query)}&gsrnamespace=6&format=json"
        res = requests.get(url_wiki, headers=headers, timeout=6).json()
        pages = res.get("query", {}).get("pages", {})
        for page in pages.values():
            info = page.get("imageinfo", [])
            if info:
                img_url = info[0].get("url")
                if img_url and img_url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    r = requests.get(img_url, headers=headers, timeout=6)
                    if r.status_code == 200:
                        return Image.open(io.BytesIO(r.content))
    except Exception:
        pass

    # Búsqueda alternativa DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            resultados = list(ddgs.images(query, max_results=3))
            for item in resultados:
                img_url = item.get("image")
                r = requests.get(img_url, headers=headers, timeout=6)
                if r.status_code == 200:
                    return Image.open(io.BytesIO(r.content))
    except Exception:
        pass

    return Image.new("RGB", (900, 900), color=(15, 23, 42))

# --- AJUSTE Y MULTILÍNEA DE TEXTO ---
def formatear_lineas_specs(texto_raw, draw, font, max_width=860):
    lineas_resultado = []
    lineas_originales = str(texto_raw).split("\n")
    
    for l in lineas_originales:
        l_str = l.strip()
        if not l_str:
            continue
            
        prefix = "⚡ " if not (l_str.startswith("•") or l_str.startswith("⚡") or l_str.startswith("🔹")) else ""
        texto_completo = prefix + l_str
        
        words = texto_completo.split(" ")
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lineas_resultado.append(" ".join(current_line))
                    current_line = ["   " + word]
                else:
                    lineas_resultado.append(word)
        if current_line:
            lineas_resultado.append(" ".join(current_line))
            
    return lineas_resultado

# --- DISEÑO DEL FRAME VERTICAL CON BORDES Y LETRAS HD (1080x1920) ---
def crear_frame_diapositiva(imagen_base, titulo, texto_specs, badge_categoria="FICHA TÉCNICA"):
    canvas = Image.new("RGBA", (1080, 1920), (10, 15, 28, 255))
    draw = ImageDraw.Draw(canvas)

    # Cargar Fuentes HD con tamaños exactos
    font_badge = cargar_fuente_hd(30)
    font_titulo = cargar_fuente_hd(48)
    font_specs = cargar_fuente_hd(38)

    # 1. CUADRO SUPERIOR (BADGE + TÍTULO)
    # Badge superior
    draw.rounded_rectangle([60, 60, 400, 120], radius=15, fill=(0, 225, 255, 255))
    draw.text((230, 90), badge_categoria.upper(), font=font_badge, fill=(10, 15, 28), anchor="mm")

    # Tarjeta de Título
    draw.rounded_rectangle([60, 140, 1020, 270], radius=20, fill=(18, 26, 45, 255), outline=(0, 225, 255), width=4)
    draw.text((540, 205), str(titulo).upper(), font=font_titulo, fill=(255, 255, 255), anchor="mm")

    # 2. CONTENEDOR DE LA FOTO REAL
    img = imagen_base.convert("RGBA")
    img.thumbnail((920, 800), LANCZOS_FILTER)
    
    x_img = (1080 - img.width) // 2
    y_img = 290 + (800 - img.height) // 2
    
    # Fondo para la imagen
    draw.rounded_rectangle([x_img - 8, y_img - 8, x_img + img.width + 8, y_img + img.height + 8], radius=15, fill=(25, 35, 60))
    canvas.paste(img, (x_img, y_img), img if img.mode == 'RGBA' else None)

    # 3. CUADRO INFERIOR DE SPECS
    lineas_formateadas = formatear_lineas_specs(texto_specs, draw, font_specs, max_width=860)
    
    line_height = 62
    padding_v = 40
    altura_specs = len(lineas_formateadas) * line_height + (padding_v * 2)
    
    top_specs = 1150
    bottom_specs = min(top_specs + altura_specs, 1850)

    # Fondo oscuro de alto contraste con borde brillante
    draw.rounded_rectangle([50, top_specs, 1030, bottom_specs], radius=25, fill=(12, 18, 32, 255), outline=(0, 225, 255), width=4)

    # Dibujar líneas de texto
    y_text = top_specs + padding_v
    for linea in lineas_formateadas:
        draw.text((90, y_text), linea, font=font_specs, fill=(255, 255, 255))
        y_text += line_height

    return canvas.convert("RGB")

# --- INTERFAZ STREAMLIT ---
st.title("📱 Creador de Videos Tech (Texto e Imágenes HD)")
st.caption("Garantiza visibilidad completa de títulos y especificaciones técnicas en pantalla.")

st.sidebar.header("⚙️ Configuración")
voz_locutor = st.sidebar.selectbox("Voz de la IA", [
    "es-MX-JorgeNeural (Hombre - México)",
    "es-MX-DaliaNeural (Mujer - México)",
    "es-ES-AlvaroNeural (Hombre - España)",
    "es-AR-TomasNeural (Hombre - Argentina)"
])

velocidad_voz = st.sidebar.select_slider("Velocidad de locución", options=["-20%", "-10%", "+0%", "+10%", "+25%"], value="+0%")

nombre_celular = st.text_input("📱 Modelo del Celular:", value="Poco X6 Pro")
num_escenas = st.number_input("🔢 Número de Escenas:", min_value=1, max_value=6, value=3, step=1)

st.markdown("---")
st.subheader("✏️ Configuración de Escenas")

escenas_config = []

for i in range(num_escenas):
    with st.expander(f"🎬 Escena {i+1}", expanded=(i == 0)):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            titulo = st.text_input(f"Título (Escena {i+1}):", value="PANTALLA Y PROCESADOR" if i==0 else "CÁMARA Y BATERÍA" if i==1 else "VEREDICTO FINAL", key=f"tit_{i}")
            locucion = st.text_area(f"Locución (Voz):", value=f"El {nombre_celular} destaca por su pantalla AMOLED a 120Hz y alta potencia.", key=f"loc_{i}")
            
            puntos_default = "Pantalla: 6.67\" AMOLED 120Hz HDR10+\nProcesador: Dimensity 8300 Ultra\nMemoria: 12GB RAM + 512GB UFS 4.0\nSistema: HyperOS Android 14" if i==0 else "Cámara Principal: 64 MP OIS\nGran Angular: 8 MP + Macro 2 MP\nBatería: 5000 mAh\nCarga Rápida: 67W en caja"
            puntos = st.text_area(f"Especificaciones Técnicas en Pantalla:", value=puntos_default, key=f"pts_{i}")

        with col2:
            st.markdown("**⏱️ Duración:**")
            duracion_modo = st.radio("Modo:", ["Sincronizar con Voz", "Segundos Fijos"], key=f"dur_mode_{i}")
            duracion_fija = 6.0
            if duracion_modo == "Segundos Fijos":
                duracion_fija = st.number_input("Segundos:", min_value=2.0, max_value=20.0, value=6.0, step=0.5, key=f"dur_sec_{i}")

            st.markdown("**🖼️ Imagen Real:**")
            origen_imagen = st.radio("Origen:", ["Buscar en Web", "Subir Imagen", "URL Directa"], key=f"img_src_{i}")
            
            imagen_escena = None
            if origen_imagen == "Subir Imagen":
                file_up = st.file_uploader(f"Subir foto para escena {i+1}:", type=["jpg", "png", "webp"], key=f"file_{i}")
                if file_up:
                    imagen_escena = Image.open(file_up)
            elif origen_imagen == "URL Directa":
                url_in = st.text_input(f"URL de foto:", key=f"url_{i}")
                if url_in:
                    try:
                        r = requests.get(url_in, timeout=6)
                        if r.status_code == 200:
                            imagen_escena = Image.open(io.BytesIO(r.content))
                    except Exception:
                        st.warning("No se pudo cargar la imagen desde la URL.")

            busqueda_tag = st.text_input("Búsqueda web:", value=f"{nombre_celular} product phone", key=f"kw_{i}") if origen_imagen == "Buscar en Web" else ""

            # Botón de Vista Previa para verificar que el texto sí se ve
            if st.button(f"👁️ Previsualizar Escena {i+1}", key=f"prev_btn_{i}"):
                img_temp = imagen_escena if (origen_imagen != "Buscar en Web" and imagen_escena) else buscar_imagen_real_web(busqueda_tag)
                frame_prev = crear_frame_diapositiva(img_temp, titulo, puntos)
                st.image(frame_prev, caption=f"Vista previa con texto HD - Escena {i+1}", width=320)

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

# --- PROCESAMIENTO Y RENDER ---
if st.button("🚀 Generar Video Final", type="primary") and nombre_celular:
    try:
        voz_codigo = voz_locutor.split(" ")[0]
        clips_video = []
        progreso = st.progress(0.0)

        for i, escena in enumerate(escenas_config):
            st.info(f"🎬 Procesando Escena {i+1}/{len(escenas_config)}: {escena['titulo']}")

            # 1. Generar Audio
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
                generar_audio(escena["texto_locucion"], t_audio.name, voz=voz_codigo, velocidad=velocidad_voz)
                audio_clip = AudioFileClip(t_audio.name)
                dur_audio = audio_clip.duration

            # 2. Calcular Duración
            duracion_final = max(escena["duracion_fija"], dur_audio) if escena["duracion_modo"] == "Segundos Fijos" else dur_audio

            # 3. Imagen Base
            if escena["origen_imagen"] in ["Subir Imagen", "URL Directa"] and escena["imagen_escena"] is not None:
                img_base = escena["imagen_escena"]
            else:
                img_base = buscar_imagen_real_web(escena["busqueda_tag"] if escena["busqueda_tag"] else f"{nombre_celular} phone")

            # 4. Crear Frame con Fuentes HD Garantizadas
            img_final = crear_frame_diapositiva(img_base, escena["titulo"], escena["puntos_pantalla"])

            # 5. Crear Clip
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_frame:
                img_final.save(t_frame.name)
                v_clip = ImageClip(t_frame.name)
                v_clip = fijar_duracion(v_clip, duracion_final)
                v_clip = fijar_audio(v_clip, audio_clip)
                clips_video.append(v_clip)

            progreso.progress((i + 1) / len(escenas_config))

        # Renderizar Video MP4
        with st.spinner("🎥 Uniendo escenas y renderizando video en alta calidad..."):
            video_final = concatenate_videoclips(clips_video, method="compose")
            ruta_mp4 = tempfile.mktemp(suffix=".mp4")
            video_final.write_videofile(ruta_mp4, fps=24, codec="libx264", audio_codec="aac")
            video_final.close()

        st.success("🎉 ¡Video renderizado con textos HD visibles!")
        st.video(ruta_mp4)

        with open(ruta_mp4, "rb") as file:
            st.download_button(
                label="📥 Descargar Video MP4",
                data=file,
                file_name=f"{nombre_celular.replace(' ', '_')}_Specs_HD.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Ocurrió un detalle durante el proceso: {e}")
