import streamlit as st
import tempfile
import os
from moviepy.editor import AudioFileClip, ImageClip

st.set_page_config(page_title="Convertidor de Audio a Video", page_icon="🎬")

st.title("🎬 Convertidor de Audio a Video")
st.write("Combina una canción con una imagen de portada para crear un video MP4.")

# Carga de archivos
col1, col2 = st.columns(2)

with col1:
    archivo_audio = st.file_uploader("1. Selecciona el Audio", type=["mp3", "wav", "m4a"])

with col2:
    archivo_imagen = st.file_uploader("2. Selecciona la Portada (Imagen)", type=["png", "jpg", "jpeg"])

if archivo_audio and archivo_imagen:
    # Mostrar vista previa de la imagen y audio
    st.image(archivo_imagen, caption="Portada seleccionada", width=300)
    st.audio(archivo_audio)

    if st.button("🚀 Generar Video", type="primary"):
        with st.spinner("Procesando y renderizando el video... Esto puede tomar unos segundos."):
            try:
                # Guardar archivos subidos en archivos temporales
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_audio.name)[1]) as temp_audio:
                    temp_audio.write(archivo_audio.read())
                    ruta_audio = temp_audio.name

                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(archivo_imagen.name)[1]) as temp_img:
                    temp_img.write(archivo_imagen.read())
                    ruta_img = temp_img.name

                ruta_video_salida = tempfile.mktemp(suffix=".mp4")

                # Proceso de creación del video con MoviePy
                audio_clip = AudioFileClip(ruta_audio)
                
                # Crear clip de imagen con la misma duración que el audio
                video_clip = ImageClip(ruta_img).set_duration(audio_clip.duration)
                video_clip = video_clip.set_audio(audio_clip)

                # Exportar el video resultante (codec h264/aac para máxima compatibilidad)
                video_clip.write_videofile(
                    ruta_video_salida,
                    fps=1,  # 1 FPS es suficiente para imagen estática y procesa muy rápido
                    codec="libx264",
                    audio_codec="aac"
                )

                # Cerrar clips para liberar memoria
                audio_clip.close()
                video_clip.close()

                # Mostrar resultado
                st.success("¡Video generado con éxito!")
                st.video(ruta_video_salida)

                # Botón de descarga
                with open(ruta_video_salida, "rb") as file:
                    st.download_button(
                        label="📥 Descargar Video MP4",
                        data=file,
                        file_name=f"{os.path.splitext(archivo_audio.name)[0]}.mp4",
                        mime="video/mp4"
                    )

            except Exception as e:
                st.error(f"Error al generar el video: {e}")
