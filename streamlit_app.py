import streamlit as st
import tempfile
import os
import urllib.parse
import requests
import io
import random
import time
import json
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from duckduckgo_search import DDGS

# Importaciones de MoviePy (compatibilidad v1 y v2)
try:
    from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
except ImportError:
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

# Configuración de página
st.set_page_config(page_title="Auto Tech Video Generator", page_icon="📱", layout="wide")

# --- ADAPTACIÓN MOVIEPY ---
def fijar_duracion(clip, duracion):
    return clip.with_duration(duracion) if hasattr(clip, "with_duration") else clip.set_duration(duracion)

def fijar_audio(clip, audio_clip):
    return clip.with_audio(audio_clip) if hasattr(clip, "with_audio") else clip.set_audio(audio_clip)

# --- VOZ (Edge-TTS) ---
async def generar_audio_async(texto, ruta_salida, voz="es-MX-JorgeNeural"):
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(ruta_salida)

def generar_audio(texto, ruta_salida, voz="es-MX-JorgeNeural"):
    try:
        asyncio.run(generar_audio_async(texto, ruta_salida, voz))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generar_audio_async(texto, ruta_salida, voz))

# --- BÚSQUEDA DE IMÁGENES REALES DEL TELÉFONO ---
def buscar_imagen_real_telefono(nombre_telefono, consulta_especifica=""):
    """Busca y descarga imágenes reales del celular específico en internet."""
    query = f"{nombre_telefono} {consulta_especifica} official phone product"
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.images(query, max_results=5))
            for res in resultados:
                url_img = res.get("image")
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(url_img, headers=headers, timeout=10)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content))
                    return img
    except Exception:
        pass
        
    # Imagen de respaldo si falla la búsqueda
    img = Image.new("RGB", (1080, 1920), color=(15, 20, 30))
    return img

# --- DISEÑO DE MARCO Y TARJETAS TÉCNICAS ---
def crear_frame_diapositiva(imagen_base, titulo, texto_overlay):
    """Adapta la foto real del celular al formato vertical 9:16 y le agrega las specs reales."""
    # Crear lienzo vertical 1080x1920
    canvas = Image.new("RGBA", (1080, 1920), (15, 20, 30, 255))
    
    # Redimensionar la imagen real manteniendo proporción
    img_aspect = imagen_base.width / imagen_base.height
    new_width = 960
    new_height = int(new_width / img_aspect)
    
    if new_height > 1000:
        new_height = 1000
        new_width = int(new_height * img_aspect)
        
    img_resized = imagen_base.resize((new_width, new_height)).convert("RGBA")
    
    # Centrar la imagen en la parte superior/media
    x_pos = (1080 - new_width) // 2
    canvas.paste(img_resized, (x_pos, 300), img_resized if img_resized.mode == 'RGBA' else None)

    draw = ImageDraw.Draw(canvas)

    try:
        font_titulo = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
        font_texto = ImageFont.truetype("FreeSansBold.ttf", 34)
    except IOError:
        font_titulo = font_texto = ImageFont.load_default()

    # Tarjeta de título superior
    draw.rounded_rectangle([60, 100, 1020, 220], radius=20, fill=(0, 0, 0, 220), outline=(0, 255, 200), width=4)
    draw.text((540, 160), str(titulo).upper(), font=font_titulo, fill=(0, 255, 200), anchor="mm")

    # Tarjeta inferior con especificaciones reales
    draw.rounded_rectangle([60, 1350, 1020, 1820], radius=25, fill=(10, 15, 25, 230), outline=(255, 255, 255), width=3)
    
    lineas = str(texto_overlay).split("\n")
    y_pos = 1390
    for linea in lineas:
        if linea.strip():
            draw.text((100, y_pos), f"• {linea.strip()}", font=font_texto, fill=(255, 255, 255))
            y_pos += 60

    return canvas.convert("RGB")

# --- GENERAR GUIÓN CON DATOS TÉCNICOS REALES ---
def generar_especificaciones_reales(nombre_telefono):
    prompt_sistema = f"""
Eres un analista de tecnología. Dame la ficha técnica REAL e investigada del celular: "{nombre_telefono}".
Responde ÚNICAMENTE con un JSON válido siguiendo esta estructura exacta:

{{
  "escenas": [
    {{
      "titulo": "FICHA TÉCNICA Y PRECIO",
      "texto_locucion": "Analizamos el {nombre_telefono}. Descubre si vale la pena.",
      "puntos_pantalla": "Precio estimado\\nGama del equipo\\n¿Vale la pena?",
      "busqueda_imagen": "phone front preview"
    }},
    {{
      "titulo": "PANTALLA Y PROCESADOR",
      "texto_locucion": "Muestra los datos reales de la pantalla y el chip de este dispositivo.",
      "puntos_pantalla": "Escribe aquí la pantalla exacta (ej. AMOLED 120Hz)\\nEscribe aquí el procesador exacto\\nRendimiento general",
      "busqueda_imagen": "screen display close up"
    }},
    {{
      "titulo": "CÁMARAS Y BATERÍA",
      "texto_locucion": "Estas son sus cámaras principales y la capacidad real de su batería.",
      "puntos_pantalla": "Escribe los Megapíxeles reales de las cámaras\\nCapacidad exacta de Batería (mAh)\\nVelocidad de carga rápida (W)",
      "busqueda_imagen": "camera module back"
    }},
    {{
      "titulo": "VEREDICTO Y NOTA",
      "texto_locucion": "En conclusión, esto es lo mejor y lo peor de este teléfono.",
      "puntos_pantalla": "Calificación final\\nLo mejor del equipo\\n¡Suscríbete!",
      "busqueda_imagen": "back panel design"
    }}
  ]
}}
"""
    try:
        url = "https://text.pollinations.ai/"
        payload = {"messages": [{"role": "user", "content": prompt_sistema}], "model": "openai"}
        res = requests.post(url, json=payload, timeout=20)
        respuesta = res.text.strip()
        
        inicio = respuesta.find('{')
        fin = respuesta.rfind('}') + 1
        if inicio != -1 and fin > inicio:
            datos = json.loads(respuesta[inicio:fin])
            if "escenas" in datos and len(datos["escenas"]) > 0:
                return datos["escenas"]
    except Exception:
        pass

    # Datos por defecto en caso de falla
    return [
        {
            "titulo": "INFORMACIÓN DEL EQUIPO",
            "texto_locucion": f"Revisemos el {nombre_telefono}.",
            "puntos_pantalla": f"Modelo: {nombre_telefono}\nDiseño oficial\nEspecificaciones",
            "busqueda_imagen": "phone"
        }
    ]

# --- INTERFAZ STREAMLIT ---
st.title("📱 Creador de Videos Tech con Fotos y Specs Reales")
st.caption("Genera videos verticales buscando las fotografías reales del teléfono y sus especificaciones exactas.")

st.sidebar.header("⚙️ Opciones")
voz_locutor = st.sidebar.selectbox("Voz de la IA", [
    "es-MX-JorgeNeural (Hombre - México)",
    "es-MX-DaliaNeural (Mujer - México)",
    "es-ES-AlvaroNeural (Hombre - España)"
])

nombre_celular = st.text_input("📱 Escribe el modelo exacto del teléfono:", value="Poco X6 Pro")

if st.button("🚀 Crear Video con Fotos Reales", type="primary") and nombre_celular:
    try:
        voz_codigo = voz_locutor.split(" ")[0]
        
        # 1. Obtener especificaciones reales
        with st.spinner("🔍 Buscando ficha técnica real del celular..."):
            escenas = generar_especificaciones_reales(nombre_celular)
            st.success(f"Ficha técnica cargada con {len(escenas)} secciones.")

        clips_video = []
        progreso = st.progress(0.0)

        # 2. Procesar cada escena
        for i, escena in enumerate(escenas):
            st.info(f"📸 Obteniendo fotos reales para: {escena.get('titulo')}")
            
            # Generar Audio
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
                generar_audio(escena.get("texto_locucion", ""), t_audio.name, voz=voz_codigo)
                audio_clip = AudioFileClip(t_audio.name)
                duracion = audio_clip.duration

            # Descargar FOTO REAL del dispositivo
            img_real = buscar_imagen_real_telefono(nombre_celular, escena.get("busqueda_imagen", ""))
            
            # Crear Frame con specs superpuestas
            img_final = crear_frame_diapositiva(img_real, escena.get("titulo", "TECH"), escena.get("puntos_pantalla", ""))
            
            # Crear Clip de video
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_frame:
                img_final.save(t_frame.name)
                v_clip = ImageClip(t_frame.name)
                v_clip = fijar_duracion(v_clip, duracion)
                v_clip = fijar_audio(v_clip, audio_clip)
                clips_video.append(v_clip)

            progreso.progress((i + 1) / len(escenas))
            time.sleep(0.5)

        # 3. Renderizar Video Final
        with st.spinner("🎥 Ensamblando video vertical final..."):
            video_final = concatenate_videoclips(clips_video, method="compose")
            ruta_mp4 = tempfile.mktemp(suffix=".mp4")
            video_final.write_videofile(ruta_mp4, fps=24, codec="libx264", audio_codec="aac")
            video_final.close()

        st.success("🎉 ¡Video generado con imágenes y especificaciones reales!")
        st.video(ruta_mp4)

        with open(ruta_mp4, "rb") as file:
            st.download_button(
                label="📥 Descargar Video MP4",
                data=file,
                file_name=f"{nombre_celular.replace(' ', '_')}_Review_Real.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Error durante el proceso: {e}")
