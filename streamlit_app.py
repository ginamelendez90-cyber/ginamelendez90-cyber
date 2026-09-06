import streamlit as st
import tempfile
import os
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import whisper

try:
    from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip
except ImportError:
    from moviepy import AudioFileClip, ImageClip, CompositeVideoClip

st.set_page_config(page_title="Generador de Video con Letra", page_icon="🎵")

st.title("🎵 Generador de Video con Letra Automática")
st.write("Sube una canción y una imagen: la IA extraerá la letra y la sincronizará en el video.")

# Cargar el modelo de Whisper (modelo 'tiny' para optimizar memoria)
@st.cache_resource
def cargar_whisper():
    return whisper.load_model("tiny")

# Función para superponer texto sobre la imagen sin usar ImageMagick
def generar_imagen_con_subtitulo(base_img_path, texto, ancho=1280, alto=720):
    img = Image.open(base_img_path).convert("RGB").resize((ancho, alto))
    if not texto.strip():
        return np.array(img)
        
    draw = ImageDraw.Draw(img)
    lineas = textwrap.wrap(texto.strip(), width=35)
    texto_formateado = "\n".join(lineas)
    
    # Cargar fuente por defecto
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except IOError:
        font = ImageFont.load_default()
        
    # Calcular posición del texto
    bbox = draw.multiline_textbbox((0, 0), texto_formateado, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    x = (ancho - tw) / 2
    y = alto - th - 80  # Posicionar en el tercio inferior
    
    # Dibujar cuadro de fondo oscuro semi-transparente
    pad = 15
    draw.rectangle([x - pad, y - pad, x + tw + pad, y + th + pad], fill=(0, 0, 0, 180))
    draw.multiline_text((x, y), texto_formateado, font=font, fill="white", align="center")
    
    return np.array(img)

# Entradas de archivo
col1, col2 = st.columns(2)
with col1:
    archivo_audio = st.file_uploader("1. Audio (MP3, WAV)", type=["mp3", "wav", "m4a"])
with col2:
    archivo_imagen = st.file_uploader("2. Imagen de Fondo", type=["png", "jpg", "jpeg"])

if archivo_audio and archivo_imagen:
    st.image(archivo_imagen, caption="Fondo", width=250)
    st.audio(archivo_audio)

    if st.button("🚀 Extraer Letra y Crear Video", type="primary"):
        try:
            # 1. Guardar archivos temporales
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_audio.name)[1]) as t_audio:
                t_audio.write(archivo_audio.read())
                ruta_audio = t_audio.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_imagen.name)[1]) as t_img:
                t_img.write(archivo_imagen.read())
                ruta_img = t_img.name

            ruta_salida = tempfile.mktemp(suffix=".mp4")

            # 2. Transcribir audio con Whisper
            with st.spinner("🎧 Transcribiendo letra con IA..."):
                modelo = cargar_whisper()
                resultado = modelo.transcribe(ruta_audio, language="es")
                segmentos = resultado.get("segments", [])

            # Mostrar la letra detectada
            with st.expander("📝 Ver letra extraída"):
                for seg in segmentos:
                    st.write(f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}")

            # 3. Ensamblar Video con MoviePy
            with st.spinner("🎬 Renderizando video con subtítulos..."):
                audio_clip = AudioFileClip(ruta_audio)
                duracion_total = audio_clip.duration

                # Clip de fondo base
                fondo_base = ImageClip(ruta_img).set_duration(duracion_total)
                clips_subtitulos = [fondo_base]

                # Crear clips individuales para cada fragmento de la letra
                for seg in segmentos:
                    inicio = seg["start"]
                    fin = min(seg["end"], duracion_total)
                    duracion_seg = fin - inicio
                    
                    if duracion_seg > 0 and seg["text"].strip():
                        frame_np = generar_imagen_con_subtitulo(ruta_img, seg["text"])
                        txt_clip = (ImageClip(frame_np)
                                    .set_start(inicio)
                                    .set_duration(duracion_seg))
                        clips_subtitulos.append(txt_clip)

                # Componer video final
                video_final = CompositeVideoClip(clips_subtitulos).set_audio(audio_clip)
                video_final.write_videofile(
                    ruta_salida,
                    fps=2,  # 2 FPS para procesamiento ultra-rápido de texto
                    codec="libx264",
                    audio_codec="aac"
                )

                # Cerrar referencias
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
            st.error(f"Error procesando el video: {e}")
