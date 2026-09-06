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

# --- VOZ NEURAL (Edge-TTS) ---
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

# --- GENERADOR DE IMAGEN REAL / TARJETA GRÁFICA DE RESPALDO ---
def obtener_imagen_celular(nombre_telefono, escena_tag=""):
    """Intenta descargar imagen de internet o crea una tarjeta gráfica tech de alta calidad."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Intento por API directa de imágenes
    try:
        prompt = urllib.parse.quote(f"{nombre_telefono} smartphone {escena_tag}")
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1080&nologo=true"
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content))
    except Exception:
        pass

    # 2. Respaldo: Tarjeta Visual Elegante (Smartphone Concept Layout)
    img = Image.new("RGB", (1080, 1080), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    
    # Marco de mockup de teléfono
    draw.rounded_rectangle([340, 100, 740, 980], radius=40, fill=(30, 41, 59), outline=(56, 189, 248), width=6)
    draw.rounded_rectangle([360, 140, 720, 940], radius=25, fill=(15, 23, 42))
    draw.ellipse([520, 160, 560, 200], fill=(56, 189, 248)) # Módulo de cámara
    
    try:
        font_card = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    except IOError:
        font_card = ImageFont.load_default()
        
    draw.text((540, 550), nombre_telefono.upper(), font=font_card, fill=(255, 255, 255), anchor="mm")
    return img

# --- COMPOSICIÓN DE DIAPOSITIVA (FORMATO VERTICAL 9:16) ---
def crear_frame_diapositiva(imagen_base, titulo, texto_overlay):
    canvas = Image.new("RGBA", (1080, 1920), (10, 15, 26, 255))
    
    # Ajustar imagen al centro del canvas
    img_resized = imagen_base.convert("RGBA").resize((960, 960))
    canvas.paste(img_resized, (60, 280), img_resized)

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
    y_pos = 1350
    for linea in lineas:
        if linea.strip():
            draw.text((100, y_pos), f"• {linea.strip()}", font=font_texto, fill=(255, 255, 255))
            y_pos += 65

    return canvas.convert("RGB")

# --- GARANTIZAR 4 ESCENAS COMPLETAS ---
def obtener_guion_base(nombre_telefono):
    """Guión base garantizado de 4 escenas completas."""
    return [
        {
            "titulo": "PRECIO Y GAMA",
            "texto_locucion": f"¡Ponemos a prueba el {nombre_telefono}! Vamos a revisar sus especificaciones y si vale la pena.",
            "puntos_pantalla": f"Modelo: {nombre_telefono}\nGama de producto\n¿Vale la pena comprarlo?",
            "tag_imagen": "official design"
        },
        {
            "titulo": "PANTALLA Y PROCESADOR",
            "texto_locucion": "En pantalla ofrece fluidez para contenido multimedia y un procesador optimizado para juegos.",
            "puntos_pantalla": "Pantalla fluida de alta tasa de refresco\nProcesador de alto rendimiento\nFluidez en multitarea",
            "tag_imagen": "display screen gaming"
        },
        {
            "titulo": "CÁMARAS Y BATERÍA",
            "texto_locucion": "Su sistema de cámaras captura buena calidad de detalle y la batería rinde para todo el día.",
            "puntos_pantalla": "Cámara principal de alta resolución\nBatería de larga duración\nCarga rápida integrada",
            "tag_imagen": "camera lens detail"
        },
        {
            "titulo": "VEREDICTO FINAL",
            "texto_locucion": "Es una alternativa muy sólida dentro de su rango de precio este año.",
            "puntos_pantalla": "Calificación: 8.8/10\nRecomendado\n¡Suscríbete para más reviews!",
            "tag_imagen": "back view smartphone"
        }
    ]

def generar_especificaciones_reales(nombre_telefono):
    prompt_sistema = f"""
Genera un guión estructurado en JSON para un video corto sobre el teléfono: "{nombre_telefono}".
Responde ÚNICAMENTE con un JSON válido que contenga exactamente 4 escenas en la lista "escenas":

{{
  "escenas": [
    {{
      "titulo": "PRECIO Y GAMA",
      "texto_locucion": "Analizamos el {nombre_telefono}.",
      "puntos_pantalla": "Precio aproximado\\nGama del equipo\\n¿Vale la pena?",
      "tag_imagen": "front design"
    }},
    {{
      "titulo": "PANTALLA Y PROCESADOR",
      "texto_locucion": "Muestra los datos de pantalla y procesador.",
      "puntos_pantalla": "Pantalla AMOLED / IPS\\nProcesador principal\\nExperiencia en juegos",
      "tag_imagen": "screen display"
    }},
    {{
      "titulo": "CÁMARAS Y BATERÍA",
      "texto_locucion": "Detalles de cámaras y batería.",
      "puntos_pantalla": "Megapíxeles principales\\nCapacidad de Batería (mAh)\\nCarga Rápida (W)",
      "tag_imagen": "camera module"
    }},
    {{
      "titulo": "VEREDICTO FINAL",
      "texto_locucion": "Conclusión del teléfono.",
      "puntos_pantalla": "Puntuación final\\nLo mejor del equipo\\n¡Suscríbete!",
      "tag_imagen": "back side"
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
            if "escenas" in datos and len(datos["escenas"]) >= 3:
                return datos["escenas"]
    except Exception:
        pass

    return obtener_guion_base(nombre_telefono)

# --- INTERFAZ STREAMLIT ---
st.title("📱 Creador Automático de Videos Tech")
st.caption("Crea videos verticales completos (4 escenas) con locución neural y especificaciones.")

st.sidebar.header("⚙️ Opciones")
voz_locutor = st.sidebar.selectbox("Voz de la IA", [
    "es-MX-JorgeNeural (Hombre - México)",
    "es-MX-DaliaNeural (Mujer - México)",
    "es-ES-AlvaroNeural (Hombre - España)",
    "es-AR-TomasNeural (Hombre - Argentina)"
])

nombre_celular = st.text_input("📱 Escribe el modelo exacto del teléfono:", value="Poco X6 Pro")

if st.button("🚀 Crear Video Completo (4 Escenas)", type="primary") and nombre_celular:
    try:
        voz_codigo = voz_locutor.split(" ")[0]
        
        # 1. Obtener especificaciones y escenas
        with st.spinner("🧠 Generando ficha técnica e investigación..."):
            escenas = generar_especificaciones_reales(nombre_celular)
            st.success(f"Guión listo con {len(escenas)} escenas garantizadas.")

        clips_video = []
        progreso = st.progress(0.0)

        # 2. Procesar las 4 escenas
        for i, escena in enumerate(escenas):
            st.info(f"🎬 Procesando Escena {i+1} de {len(escenas)}: {escena.get('titulo')}")
            
            # Generar Audio
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
                generar_audio(escena.get("texto_locucion", ""), t_audio.name, voz=voz_codigo)
                audio_clip = AudioFileClip(t_audio.name)
                duracion = audio_clip.duration

            # Descargar o Generar Imagen de Respaldo
            img_base = obtener_imagen_celular(nombre_celular, escena.get("tag_imagen", ""))
            
            # Generar Frame con specs superpuestas
            img_final = crear_frame_diapositiva(img_base, escena.get("titulo", "TECH"), escena.get("puntos_pantalla", ""))
            
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
        with st.spinner("🎥 Renderizando el video final..."):
            video_final = concatenate_videoclips(clips_video, method="compose")
            ruta_mp4 = tempfile.mktemp(suffix=".mp4")
            video_final.write_videofile(ruta_mp4, fps=24, codec="libx264", audio_codec="aac")
            video_final.close()

        st.success("🎉 ¡Video de 4 escenas generado con éxito!")
        st.video(ruta_mp4)

        with open(ruta_mp4, "rb") as file:
            st.download_button(
                label="📥 Descargar Video MP4 (Shorts/Reels)",
                data=file,
                file_name=f"{nombre_celular.replace(' ', '_')}_Review.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Error durante el proceso: {e}")
