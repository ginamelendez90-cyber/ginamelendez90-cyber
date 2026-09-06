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

# Importaciones compatibles con MoviePy v1 y v2
try:
    from moviepy.editor import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips
except ImportError:
    from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips

# Resampling compatible con PIL
try:
    LANCZOS_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    LANCZOS_FILTER = Image.LANCZOS

# Configuración de página de Streamlit
st.set_page_config(page_title="Creador de Videos Tech Pro", page_icon="🎬", layout="wide")

# --- TEMAS Y FORMATOS DE VIDEO ---
TEMAS = {
    "Cyberpunk Neon (Azul/Cian)": {
        "bg": (10, 15, 28, 255), "card": (18, 26, 45, 255),
        "accent": (0, 225, 255), "text": (255, 255, 255), "subtext": (180, 200, 220)
    },
    "Apple Minimalist (Blanco)": {
        "bg": (245, 245, 247, 255), "card": (255, 255, 255, 255),
        "accent": (0, 113, 227), "text": (29, 29, 31), "subtext": (100, 100, 105)
    },
    "Gamer Red (Negro/Rojo)": {
        "bg": (15, 5, 5, 255), "card": (35, 12, 12, 255),
        "accent": (255, 0, 51), "text": (255, 255, 255), "subtext": (220, 180, 180)
    },
    "Gold Luxury (Dorado/Negro)": {
        "bg": (18, 15, 10, 255), "card": (38, 30, 18, 255),
        "accent": (212, 175, 55), "text": (255, 255, 255), "subtext": (220, 200, 160)
    }
}

FORMATOS = {
    "9:16 Vertical (TikTok / Reels / Shorts)": (1080, 1920),
    "16:9 Horizontal (YouTube Tradicional)": (1920, 1080),
    "1:1 Cuadrado (Post Instagram / FB)": (1080, 1080)
}

# --- FUNCIONES ADAPTADORAS MOVIEPY ---
def fijar_duracion(clip, duracion):
    return clip.with_duration(duracion) if hasattr(clip, "with_duration") else clip.set_duration(duracion)

def fijar_audio(clip, audio_clip):
    return clip.with_audio(audio_clip) if hasattr(clip, "with_audio") else clip.set_audio(audio_clip)

# --- GARANTIZAR FUENTES TIPOGRÁFICAS EN EL SERVIDOR ---
@st.cache_resource
def cargar_fuente_hd(tamano):
    fuentes_sistema = ["DejaVuSans-Bold.ttf", "FreeSansBold.ttf", "arial.ttf", "Arial.ttf"]
    for f in fuentes_sistema:
        try:
            return ImageFont.truetype(f, tamano)
        except IOError:
            continue

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

# --- FORMATEADOR DE SPECS Y DIBUJO DE ESTRELLAS/RATING ---
def formatear_lineas_specs(texto_raw, draw, font, max_width):
    lineas_resultado = []
    for l in str(texto_raw).split("\n"):
        l_str = l.strip()
        if not l_str:
            continue
        prefix = "⚡ " if not any(l_str.startswith(c) for c in ["•", "⚡", "🔹", "⭐", "📊"]) else ""
        texto_completo = prefix + l_str
        words = texto_completo.split(" ")
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
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

# --- COMPOSICIÓN DINÁMICA DE DIAPOSITIVAS MULTI-FORMATO Y TEMA ---
def crear_frame_diapositiva(imagen_base, titulo, texto_specs, tema, dimensiones, handle_usuario="", logo_img=None):
    W, H = dimensiones
    colores = TEMAS[tema]
    
    canvas = Image.new("RGBA", (W, H), colores["bg"])
    draw = ImageDraw.Draw(canvas)

    # Escala de fuentes ajustada a la resolución
    f_factor = min(W, H) / 1080.0
    font_badge = cargar_fuente_hd(int(26 * f_factor))
    font_titulo = cargar_fuente_hd(int(42 * f_factor))
    font_specs = cargar_fuente_hd(int(34 * f_factor))
    font_handle = cargar_fuente_hd(int(24 * f_factor))

    # MARCA DE AGUA / LOGO O HANDLE
    if handle_usuario:
        draw.text((int(W * 0.05), int(H * 0.03)), handle_usuario, font=font_handle, fill=colores["accent"])

    if logo_img:
        try:
            logo = logo_img.convert("RGBA")
            logo.thumbnail((int(140 * f_factor), int(140 * f_factor)), LANCZOS_FILTER)
            canvas.paste(logo, (int(W * 0.85 - logo.width / 2), int(H * 0.02)), logo)
        except Exception:
            pass

    # DISTRIBUCIÓN SEGÚN FORMATO
    if H > W:  # 9:16 Vertical
        # Título
        draw.rounded_rectangle([int(W*0.05), int(H*0.07), int(W*0.95), int(H*0.14)], radius=15, fill=colores["card"], outline=colores["accent"], width=3)
        draw.text((W//2, int(H*0.105)), str(titulo).upper(), font=font_titulo, fill=colores["text"], anchor="mm")

        # Foto
        img = imagen_base.convert("RGBA")
        img.thumbnail((int(W*0.85), int(H*0.42)), LANCZOS_FILTER)
        x_img = (W - img.width) // 2
        y_img = int(H*0.16) + (int(H*0.42) - img.height) // 2
        draw.rounded_rectangle([x_img - 6, y_img - 6, x_img + img.width + 6, y_img + img.height + 6], radius=12, fill=colores["card"])
        canvas.paste(img, (x_img, y_img), img if img.mode == 'RGBA' else None)

        # Specs
        top_specs = int(H * 0.60)
        lineas = formatear_lineas_specs(texto_specs, draw, font_specs, max_width=int(W * 0.80))
        line_height = int(54 * f_factor)
        bottom_specs = min(top_specs + len(lineas) * line_height + 60, int(H * 0.94))
        draw.rounded_rectangle([int(W*0.05), top_specs, int(W*0.95), bottom_specs], radius=20, fill=colores["card"], outline=colores["accent"], width=3)
        
        y_txt = top_specs + 30
        for lin in lineas:
            draw.text((int(W*0.09), y_txt), lin, font=font_specs, fill=colores["text"])
            y_txt += line_height

    else:  # 16:9 Horizontal o 1:1 Cuadrado
        # Lado Izquierdo: Imagen | Lado Derecho: Especificaciones
        img = imagen_base.convert("RGBA")
        max_w_img = int(W * 0.42)
        max_h_img = int(H * 0.75)
        img.thumbnail((max_w_img, max_h_img), LANCZOS_FILTER)
        
        x_img = int(W * 0.05) + (max_w_img - img.width) // 2
        y_img = int(H * 0.15) + (max_h_img - img.height) // 2
        draw.rounded_rectangle([x_img - 6, y_img - 6, x_img + img.width + 6, y_img + img.height + 6], radius=12, fill=colores["card"])
        canvas.paste(img, (x_img, y_img), img if img.mode == 'RGBA' else None)

        # Derecha: Título + Specs
        draw.rounded_rectangle([int(W*0.50), int(H*0.12), int(W*0.95), int(H*0.22)], radius=12, fill=colores["card"], outline=colores["accent"], width=3)
        draw.text((int(W*0.725), int(H*0.17)), str(titulo).upper(), font=font_titulo, fill=colores["text"], anchor="mm")

        top_specs = int(H * 0.26)
        lineas = formatear_lineas_specs(texto_specs, draw, font_specs, max_width=int(W * 0.40))
        line_height = int(48 * f_factor)
        bottom_specs = min(top_specs + len(lineas) * line_height + 50, int(H * 0.90))
        draw.rounded_rectangle([int(W*0.50), top_specs, int(W*0.95), bottom_specs], radius=18, fill=colores["card"], outline=colores["accent"], width=3)

        y_txt = top_specs + 25
        for lin in lineas:
            draw.text((int(W*0.53), y_txt), lin, font=font_specs, fill=colores["text"])
            y_txt += line_height

    return canvas.convert("RGB")

# --- INTERFAZ STREAMLIT ---
st.title("🎬 Creador Profesional de Videos Tech")
st.caption("Personalización completa: temas, formatos, música de fondo, marcas de agua y gráficos.")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("🎨 Estilo y Diseño")
    tema_elegido = st.selectbox("Tema de Color:", list(TEMAS.keys()))
    formato_elegido = st.selectbox("Formato de Video:", list(FORMATOS.keys()))
    handle_social = st.text_input("🏷️ Tu usuario / Canal (Marca de agua):", value="@TuCanalTech")

with col_right:
    st.subheader("🎵 Audio y Locución")
    voz_locutor = st.selectbox("Voz de la IA:", [
        "es-MX-JorgeNeural (Hombre - México)",
        "es-MX-DaliaNeural (Mujer - México)",
        "es-ES-AlvaroNeural (Hombre - España)",
        "es-AR-TomasNeural (Hombre - Argentina)"
    ])
    velocidad_voz = st.select_slider("Velocidad de locución:", options=["-20%", "-10%", "+0%", "+10%", "+25%"], value="+0%")
    
    archivo_musica = st.file_uploader("🎵 Música de Fondo (Opcional - MP3):", type=["mp3", "wav"])
    volumen_musica = st.slider("Volumen de la música de fondo:", min_value=0.05, max_value=0.40, value=0.15, step=0.05)

st.markdown("---")
col_logo, col_phone = st.columns([1, 2])
with col_logo:
    uploaded_logo = st.file_uploader("🖼️ Logo de tu Canal (PNG transparente):", type=["png"])
    logo_image = Image.open(uploaded_logo) if uploaded_logo else None

with col_phone:
    nombre_celular = st.text_input("📱 Modelo del Celular / Producto:", value="Poco X6 Pro")
    num_escenas = st.number_input("🔢 Número de Escenas:", min_value=1, max_value=6, value=3, step=1)

st.markdown("---")
st.subheader("✏️ Configurar Escenas")

escenas_config = []

for i in range(num_escenas):
    with st.expander(f"🎬 Escena {i+1}", expanded=(i == 0)):
        c1, c2 = st.columns([2, 1])
        with c1:
            tit = st.text_input(f"Título (Escena {i+1}):", value="PANTALLA Y RENDIMIENTO" if i==0 else "CÁMARAS Y BATERÍA" if i==1 else "VEREDICTO FINAL", key=f"t_{i}")
            loc = st.text_area(f"Locución hablada:", value=f"El {nombre_celular} ofrece máxima potencia e increíble pantalla.", key=f"l_{i}")
            pts_def = "Pantalla: 6.67\" AMOLED 120Hz\nProcesador: Dimensity 8300 Ultra\nRAM / Algo: 12GB UFS 4.0\n⭐ Calificación: 9.5/10" if i==0 else "Cámara: 64 MP OIS + 8 MP\nBatería: 5000 mAh (67W)\n⭐ Rendimiento: 9.0/10"
            pts = st.text_area(f"Specs / Gráficos en pantalla:", value=pts_def, key=f"p_{i}")

        with c2:
            st.markdown("**⏱️ Duración:**")
            dur_m = st.radio("Sincronización:", ["Voz de la IA", "Tiempo Fijo (Seg)"], key=f"dm_{i}")
            dur_f = st.number_input("Segundos:", min_value=2.0, max_value=20.0, value=6.0, step=0.5, key=f"df_{i}") if dur_m == "Tiempo Fijo (Seg)" else 6.0

            st.markdown("**🖼️ Imagen:**")
            orig_img = st.radio("Origen:", ["Buscar en Web", "Subir Foto", "URL Directa"], key=f"oi_{i}")
            
            img_escena = None
            if orig_img == "Subir Foto":
                f_up = st.file_uploader(f"Foto escena {i+1}:", type=["jpg", "png", "webp"], key=f"fu_{i}")
                if f_up:
                    img_escena = Image.open(f_up)
            elif orig_img == "URL Directa":
                u_in = st.text_input(f"URL foto:", key=f"ui_{i}")
                if u_in:
                    try:
                        r = requests.get(u_in, timeout=6)
                        if r.status_code == 200:
                            img_escena = Image.open(io.BytesIO(r.content))
                    except Exception:
                        pass

            kw_search = st.text_input("Búsqueda web:", value=f"{nombre_celular} phone", key=f"kw_{i}") if orig_img == "Buscar en Web" else ""

            if st.button(f"👁️ Previsualizar Escena {i+1}", key=f"prev_{i}"):
                img_t = img_escena if (orig_img != "Buscar en Web" and img_escena) else buscar_imagen_real_web(kw_search)
                dims = FORMATOS[formato_elegido]
                f_prev = crear_frame_diapositiva(img_t, tit, pts, tema_elegido, dims, handle_usuario=handle_social, logo_img=logo_image)
                st.image(f_prev, caption=f"Vista previa ({formato_elegido.split()[0]})", width=360)

        escenas_config.append({
            "titulo": tit, "texto_locucion": loc, "puntos_pantalla": pts,
            "duracion_modo": dur_m, "duracion_fija": dur_f,
            "origen_imagen": orig_img, "imagen_escena": img_escena, "busqueda_tag": kw_search
        })

# --- RENDERIZADO DEL VIDEO FINAL ---
if st.button("🚀 Renderizar Video Profesional", type="primary") and nombre_celular:
    try:
        voz_code = voz_locutor.split(" ")[0]
        dimensiones = FORMATOS[formato_elegido]
        clips_video = []
        progreso = st.progress(0.0)

        # Cargar música de fondo si se subió
        clip_musica_global = None
        if archivo_musica is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_m:
                t_m.write(archivo_musica.read())
                clip_musica_global = AudioFileClip(t_m.name)

        for i, escena in enumerate(escenas_config):
            st.info(f"🎬 Procesando Escena {i+1}/{len(escenas_config)}: {escena['titulo']}")

            # 1. Generar Audio TTS
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
                generar_audio(escena["texto_locucion"], t_audio.name, voz=voz_code, velocidad=velocidad_voz)
                audio_voz_clip = AudioFileClip(t_audio.name)
                dur_audio = audio_voz_clip.duration

            # 2. Calcular Duración
            duracion_final = max(escena["duracion_fija"], dur_audio) if escena["duracion_modo"] == "Tiempo Fijo (Seg)" else dur_audio

            # 3. Obtener Imagen
            if escena["origen_imagen"] in ["Subir Foto", "URL Directa"] and escena["imagen_escena"] is not None:
                img_base = escena["imagen_escena"]
            else:
                img_base = buscar_imagen_real_web(escena["busqueda_tag"] if escena["busqueda_tag"] else f"{nombre_celular} phone")

            # 4. Crear Frame
            img_final = crear_frame_diapositiva(
                img_base, escena["titulo"], escena["puntos_pantalla"],
                tema_elegido, dimensiones, handle_usuario=handle_social, logo_img=logo_image
            )

            # 5. Mezclar Audio (Voz + Música de Fondo)
            if clip_musica_global:
                # Subclip de música del tamaño de la escena
                m_sub = clip_musica_global.subclip(0, min(duracion_final, clip_musica_global.duration))
                m_sub = m_sub.volumex(volumen_musica)
                audio_mezclado = CompositeAudioClip([audio_voz_clip, m_sub])
            else:
                audio_mezclado = audio_voz_clip

            # 6. Crear Clip de Video
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_frame:
                img_final.save(t_frame.name)
                v_clip = ImageClip(t_frame.name)
                v_clip = fijar_duracion(v_clip, duracion_final)
                v_clip = fijar_audio(v_clip, audio_mezclado)
                clips_video.append(v_clip)

            progreso.progress((i + 1) / len(escenas_config))

        # Renderizar Video MP4 Final
        with st.spinner("🎥 Uniendo clips y exportando video final..."):
            video_final = concatenate_videoclips(clips_video, method="compose")
            ruta_mp4 = tempfile.mktemp(suffix=".mp4")
            video_final.write_videofile(ruta_mp4, fps=24, codec="libx264", audio_codec="aac")
            video_final.close()

        st.success("🎉 ¡Video renderizado exitosamente!")
        st.video(ruta_mp4)

        with open(ruta_mp4, "rb") as file:
            st.download_button(
                label="📥 Descargar Video MP4",
                data=file,
                file_name=f"{nombre_celular.replace(' ', '_')}_ProVideo.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Error durante el renderizado: {e}")
