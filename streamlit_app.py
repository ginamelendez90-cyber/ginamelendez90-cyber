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
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Importaciones dinámicas de LangChain y MoviePy
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

try:
    from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
except ImportError:
    from moviepy import AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips

# Configuración de página
st.set_page_config(page_title="Auto Tech Video Generator", page_icon="📱", layout="wide")

# --- FUNCIONES DE VOZ (Edge-TTS) ---
async def generar_audio_async(texto, ruta_salida, voz="es-MX-JorgeNeural"):
    """Genera audio con voz hiperrealista usando Edge-TTS."""
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(ruta_salida)

def generar_audio(texto, ruta_salida, voz="es-MX-JorgeNeural"):
    """Manejo seguro de bucle asíncrono para Streamlit."""
    try:
        asyncio.run(generar_audio_async(texto, ruta_salida, voz))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generar_audio_async(texto, ruta_salida, voz))

# --- GENERACIÓN DE IMÁGENES ---
def descargar_imagen_telefono(prompt_ingles, reintentos_max=3):
    prompt_encoded = urllib.parse.quote(prompt_ingles)
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1080&height=1920&nologo=true&seed={seed}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for intento in range(reintentos_max):
        try:
            res = requests.get(url, headers=headers, timeout=25)
            if res.status_code == 429:
                time.sleep((intento + 1) * 3)
                continue
            res.raise_for_status()
            return Image.open(io.BytesIO(res.content))
        except Exception:
            time.sleep(2)
            
    # Fondo por defecto si la API falla
    img = Image.new("RGB", (1080, 1920), color=(15, 20, 30))
    return img

# --- DISEÑO DE DIAPOSITIVAS Y TEXTO OVERLAY ---
def crear_frame_diapositiva(imagen_base, titulo, texto_overlay):
    """Superpone tarjetas gráficas con especificaciones sobre la imagen."""
    img = imagen_base.convert("RGBA").resize((1080, 1920))
    
    # Capa oscura general para contraste
    overlay = Image.new("RGBA", (1080, 1920), (0, 0, 0, 100))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Tarjeta de título superior
    draw.rounded_rectangle([60, 120, 1020, 240], radius=20, fill=(0, 0, 0, 200), outline=(0, 255, 200), width=4)
    try:
        font_titulo = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
        font_texto = ImageFont.truetype("FreeSansBold.ttf", 36)
    except IOError:
        font_titulo = font_texto = ImageFont.load_default()

    draw.text((540, 180), titulo.upper(), font=font_titulo, fill=(0, 255, 200), anchor="mm")

    # Tarjeta inferior con ficha técnica
    draw.rounded_rectangle([60, 1400, 1020, 1800], radius=25, fill=(10, 15, 25, 220), outline=(255, 255, 255), width=3)
    
    lineas = texto_overlay.split("\n")
    y_pos = 1450
    for linea in lineas:
        if linea.strip():
            draw.text((100, y_pos), f"• {linea.strip()}", font=font_texto, fill=(255, 255, 255))
            y_pos += 60

    return img.convert("RGB")

# --- GENERACIÓN DE GUIÓN CON OLLAMA ---
def generar_estructura_video(nombre_telefono, base_url, modelo):
    prompt_sistema = f"""
Eres un experto creador de contenido tech. Genera un guión estructurado en formato JSON para un video corto (Vertical 9:16) sobre el teléfono: "{nombre_telefono}".
Responde ÚNICAMENTE con un objeto JSON válido con este formato exacta y sin textos adicionales:

{{
  "escenas": [
    {{
      "titulo": "GANCHO Y PRECIO",
      "texto_locucion": "¡Este es el {nombre_telefono}! ¿Realmente vale la pena por su precio o es una trampa?",
      "puntos_pantalla": "Precio estimado\\nGama media/alta\\n¿Vale la pena?",
      "prompt_imagen": "modern smartphone {nombre_telefono} floating in dark background, high resolution studio light, 8k"
    }},
    {{
      "titulo": "PANTALLA Y POTENCIA",
      "texto_locucion": "Cuenta con una pantalla fluida y un procesador capaz de correr cualquier juego sin despeinarse.",
      "puntos_pantalla": "Pantalla AMOLED 120Hz\\nProcesador de alta potencia\\nIdeal para gaming",
      "prompt_imagen": "smartphone screen showing vibrant colorful 3d video game graphic, ultra detailed"
    }},
    {{
      "titulo": "CÁMARA Y BATERÍA",
      "texto_locucion": "En fotos cumple bastante bien y su batería te dura todo el día con carga rápida.",
      "puntos_pantalla": "Cámara principal de alta resolución\\nBatería de 5000 mAh\\nCarga rápida incluida",
      "prompt_imagen": "close up of smartphone camera lens module with metallic reflections"
    }},
    {{
      "titulo": "VEREDICTO FINAL",
      "texto_locucion": "Si buscas gran rendimiento sin gastar de más, es una opción excelente este año.",
      "puntos_pantalla": "Calificación: 8.5/10\\nRecomendado para comprar\\n¡Suscríbete para más!",
      "prompt_imagen": "smartphone placed on a clean wooden desk next to wireless earbuds, aesthetic photo"
    }}
  ]
}}
"""
    llm = ChatOllama(model=modelo, temperature=0.5, base_url=base_url)
    respuesta = llm.invoke(prompt_sistema).content.strip()
    
    # Extraer JSON limpio
    inicio = respuesta.find('{')
    fin = respuesta.rfind('}') + 1
    return json.loads(respuesta[inicio:fin])

# --- INTERFAZ STREAMLIT ---
st.title("🤖 Generador Automático de Videos de Tecnología")
st.caption("Crea videos verticales (Shorts/Reels/TikTok) con voz neural e imágenes generadas por IA.")

st.sidebar.header("⚙️ Configuración")
base_url = st.sidebar.text_input("URL Ollama", value="http://localhost:11434")
modelo_llm = st.sidebar.selectbox("Modelo LLM", ["qwen2.5-coder", "llama3", "llama3.1", "llama3.2"], index=0)
voz_locutor = st.sidebar.selectbox("Voz de la IA", [
    "es-MX-JorgeNeural (Hombre - México)",
    "es-MX-DaliaNeural (Mujer - México)",
    "es-ES-AlvaroNeural (Hombre - España)",
    "es-AR-TomasNeural (Hombre - Argentina)"
])

nombre_celular = st.text_input("📱 Escribe el modelo del teléfono:", value="Poco X6 Pro")

if st.button("🚀 Crear Video Automático", type="primary") and nombre_celular:
    try:
        voz_codigo = voz_locutor.split(" ")[0]
        
        # 1. Generar Guión con Ollama
        with st.spinner("🧠 Ollama está investigando las especificaciones y creando el guión..."):
            estructura = generar_estructura_video(nombre_celular, base_url, modelo_llm)
            escenas = estructura.get("escenas", [])
            st.success(f"Guión generado con {len(escenas)} escenas.")

        clips_video = []
        progreso = st.progress(0.0)

        # 2. Procesar cada escena
        for i, escena in enumerate(escenas):
            st.info(f"🎬 Procesando Escena {i+1}: {escena['titulo']}")
            
            # Generar Audio TTS
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
                generar_audio(escena["texto_locucion"], t_audio.name, voz=voz_codigo)
                audio_clip = AudioFileClip(t_audio.name)
                duracion = audio_clip.duration

            # Descargar Fondo
            img_base = descargar_imagen_telefono(escena["prompt_imagen"])
            
            # Crear Frame con overlay gráfico
            img_final = crear_frame_diapositiva(img_base, escena["titulo"], escena["puntos_pantalla"])
            
            # Guardar frame e integrar clip
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_frame:
                img_final.save(t_frame.name)
                v_clip = ImageClip(t_frame.name).set_duration(duracion).set_audio(audio_clip)
                clips_video.append(v_clip)

            progreso.progress((i + 1) / len(escenas))
            time.sleep(1)

        # 3. Renderizar Video Final
        with st.spinner("🎥 Renderizando el video vertical final..."):
            video_final = concatenate_videoclips(clips_video, method="compose")
            ruta_mp4 = tempfile.mktemp(suffix=".mp4")
            video_final.write_videofile(ruta_mp4, fps=24, codec="libx264", audio_codec="aac")

            video_final.close()

        st.success("🎉 ¡Video generado completamente gratis!")
        st.video(ruta_mp4)

        with open(ruta_mp4, "rb") as file:
            st.download_button(
                label="📥 Descargar Video Vertical (Shorts/Reels)",
                data=file,
                file_name=f"{nombre_celular.replace(' ', '_')}_Review.mp4",
                mime="video/mp4"
            )

    except Exception as e:
        st.error(f"Error durante el proceso: {e}")
