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

# Importaciones de MoviePy
try:
    from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
except ImportError:
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

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
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 429:
                time.sleep((intento + 1) * 2)
                continue
            res.raise_for_status()
            return Image.open(io.BytesIO(res.content))
        except Exception:
            time.sleep(1)
            
    img = Image.new("RGB", (1080, 1920), color=(15, 20, 30))
    return img

# --- DISEÑO DE DIAPOSITIVAS Y TEXTO OVERLAY ---
def crear_frame_diapositiva(imagen_base, titulo, texto_overlay):
    """Superpone tarjetas gráficas con especificaciones sobre la imagen."""
    img = imagen_base.convert("RGBA").resize((1080, 1920))
    
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

    draw.text((540, 180), str(titulo).upper(), font=font_titulo, fill=(0, 255, 200), anchor="mm")

    # Tarjeta inferior con ficha técnica
    draw.rounded_rectangle([60, 1400, 1020, 1800], radius=25, fill=(10, 15, 25, 220), outline=(255, 255, 255), width=3)
    
    lineas = str(texto_overlay).split("\n")
    y_pos = 1450
    for linea in lineas:
        if linea.strip():
            draw.text((100, y_pos), f"• {linea.strip()}", font=font_texto, fill=(255, 255, 255))
            y_pos += 60

    return img.convert("RGB")

# --- GUIÓN BASE DE RESPALDO GARANTIZADO ---
def obtener_guion_predeterminado(nombre_telefono):
    return [
        {
            "titulo": "GANCHO Y PRECIO",
            "texto_locucion": f"¡Este es el {nombre_telefono}! ¿Realmente vale la pena comprarlo?",
            "puntos_pantalla": "Precio estimado\nDiseño moderno\n¿Vale la pena?",
            "prompt_imagen": f"modern smartphone {nombre_telefono} floating in dark studio lighting"
        },
        {
            "titulo": "PANTALLA Y POTENCIA",
            "texto_locucion": "Cuenta con una pantalla muy fluida y rendimiento excelente para aplicaciones y juegos.",
            "puntos_pantalla": "Pantalla fluida 120Hz\nProcesador potente\nGran rendimiento",
            "prompt_imagen": "smartphone screen displaying bright vivid colors close up"
        },
        {
            "titulo": "CÁMARA Y BATERÍA",
            "texto_locucion": "Su cámara toma fotos nítidas y la batería te rinde durante todo el día.",
            "puntos_pantalla": "Cámara de alta resolución\nBatería de larga duración\nCarga rápida",
            "prompt_imagen": "close up of modern smartphone camera lens"
        },
        {
            "titulo": "VEREDICTO FINAL",
            "texto_locucion": "Es una alternativa sólida en su categoría si buscas gran relación calidad precio.",
            "puntos_pantalla": "Calificación: 8.5/10\nRecomendado\n¡Suscríbete para más!",
            "prompt_imagen": "aesthetic photo of smartphone on wooden desk"
        }
    ]

# --- GENERACIÓN DE GUIÓN EN LA NUBE ---
def generar_estructura_video_cloud(nombre_telefono):
    prompt_sistema = f"""
Eres un experto creador de contenido tech. Genera un guión estructurado en formato JSON para un video corto sobre el teléfono: "{nombre_telefono}".
Responde ÚNICAMENTE con un objeto JSON válido con esta estructura exacta sin explicaciones adicionales:

{{
  "escenas": [
    {{
      "titulo": "GANCHO Y PRECIO",
      "texto_locucion": "¡Este es el {nombre_telefono}! ¿Vale la pena por su precio?",
      "puntos_pantalla": "Precio estimado\\nGama destacada\\n¿Vale la pena?",
      "prompt_imagen": "modern smartphone floating in dark studio"
    }}
  ]
}}
"""
    try:
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": [{"role": "user", "content": prompt_sistema}],
            "model": "openai"
        }
        res = requests.post(url, json=payload, timeout=20)
        respuesta = res.text.strip()
        
        inicio = respuesta.find('{')
        fin = respuesta.rfind('}') + 1
        if inicio != -1 and fin > inicio:
            datos = json.loads(respuesta[inicio:fin])
            if isinstance(datos, dict) and "escenas" in datos and isinstance(datos["escenas"], list) and len(datos["escenas"]) > 0:
                return datos["escenas"]
    except Exception:
        pass
        
    return obtener_guion_predeterminado(nombre_telefono)

# --- INTERFAZ STREAMLIT ---
st.title("🤖 Generador Automático de Videos Tech (Nube)")
st.caption("Crea videos verticales (Shorts/Reels/TikTok) con voz neural e imágenes IA directamente en la nube.")

st.sidebar.header("⚙️ Configuración")
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
        
        # 1. Generar Guión en la nube
        with st.spinner("🧠 Investigando especificaciones y creando el guión..."):
            escenas = generar_estructura_video_cloud(nombre_celular)
            st.success(f"Guión preparado con {len(escenas)} escenas.")

        clips_video = []
        progreso = st.progress(0.0)

        # 2. Procesar cada escena
        for i, escena in enumerate(escenas):
            st.info(f"🎬 Procesando Escena {i+1}: {escena.get('titulo', 'Escena')}")
            
            # Generar Audio TTS
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
                generar_audio(escena.get("texto_locucion", "Generando video."), t_audio.name, voz=voz_codigo)
                audio_clip = AudioFileClip(t_audio.name)
                duracion = audio_clip.duration

            # Descargar Fondo
            img_base = descargar_imagen_telefono(escena.get("prompt_imagen", "smartphone"))
            
            # Crear Frame con overlay gráfico
            img_final = crear_frame_diapositiva(img_base, escena.get("titulo", "TECH"), escena.get("puntos_pantalla", ""))
            
            # Guardar frame e integrar clip
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_frame:
                img_final.save(t_frame.name)
                v_clip = ImageClip(t_frame.name).set_duration(duracion).set_audio(audio_clip)
                clips_video.append(v_clip)

            progreso.progress((i + 1) / len(escenas))
            time.sleep(0.5)

        # Validar que existan clips antes de concatenar
        if not clips_video:
            st.error("No se pudieron procesar las escenas del video. Intenta nuevamente.")
            st.stop()

        # 3. Renderizar Video Final
        with st.spinner("🎥 Renderizando el video vertical final..."):
            video_final = concatenate_videoclips(clips_video, method="compose")
            ruta_mp4 = tempfile.mktemp(suffix=".mp4")
            video_final.write_videofile(ruta_mp4, fps=24, codec="libx264", audio_codec="aac")

            video_final.close()

        st.success("🎉 ¡Video generado con éxito!")
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
