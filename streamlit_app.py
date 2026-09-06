import asyncio
import io
import os
import tempfile
import urllib.parse
import edge_tts
from PIL import Image, ImageDraw, ImageFont
import requests
import streamlit as st

# Importaciones compatibles con MoviePy v1 y v2
try:
  from moviepy.editor import (
      AudioFileClip,
      CompositeAudioClip,
      ImageClip,
      concatenate_videoclips,
  )
except ImportError:
  from moviepy import (
      AudioFileClip,
      CompositeAudioClip,
      ImageClip,
      concatenate_videoclips,
  )

try:
  LANCZOS_FILTER = Image.Resampling.LANCZOS
except AttributeError:
  LANCZOS_FILTER = Image.LANCZOS

st.set_page_config(
    page_title="Creador de Videos Tech Pro - Modo VS",
    page_icon="🎬",
    layout="wide",
)

TEMAS = {
    "Cyberpunk Neon (Azul/Cian)": {
        "bg": (10, 15, 28, 255),
        "card": (18, 26, 45, 255),
        "accent": (0, 225, 255),
        "text": (255, 255, 255),
    },
    "Apple Minimalist (Blanco)": {
        "bg": (245, 245, 247, 255),
        "card": (255, 255, 255, 255),
        "accent": (0, 113, 227),
        "text": (29, 29, 31),
    },
    "Gamer Red (Negro/Rojo)": {
        "bg": (15, 5, 5, 255),
        "card": (35, 12, 12, 255),
        "accent": (255, 0, 51),
        "text": (255, 255, 255),
    },
    "Gold Luxury (Dorado/Negro)": {
        "bg": (18, 15, 10, 255),
        "card": (38, 30, 18, 255),
        "accent": (212, 175, 55),
        "text": (255, 255, 255),
    },
}

FORMATOS = {
    "9:16 Vertical (TikTok / Reels / Shorts)": (1080, 1920),
    "16:9 Horizontal (YouTube Tradicional)": (1920, 1080),
    "1:1 Cuadrado (Post Instagram / FB)": (1080, 1080),
}


# --- FUNCIONES ADAPTADORAS MOVIEPY ---
def fijar_duracion(clip, duracion):
  return (
      clip.with_duration(duracion)
      if hasattr(clip, "with_duration")
      else clip.set_duration(duracion)
  )


def fijar_audio(clip, audio_clip):
  return (
      clip.with_audio(audio_clip)
      if hasattr(clip, "with_audio")
      else clip.set_audio(audio_clip)
  )


def recortar_audio(clip, t_inicio, t_fin):
  if hasattr(clip, "subclipped"):
    return clip.subclipped(t_inicio, t_fin)
  elif hasattr(clip, "subclip"):
    return clip.subclip(t_inicio, t_fin)
  return clip


def ajustar_volumen(clip, factor):
  if hasattr(clip, "multiply_volume"):
    return clip.multiply_volume(factor)
  elif hasattr(clip, "volumex"):
    return clip.volumex(factor)
  return clip


@st.cache_resource
def cargar_fuente_hd(tamano):
  fuentes_sistema = [
      "DejaVuSans-Bold.ttf",
      "FreeSansBold.ttf",
      "arial.ttf",
      "Arial.ttf",
  ]
  for f in fuentes_sistema:
    try:
      return ImageFont.truetype(f, tamano)
    except IOError:
      continue
  return ImageFont.load_default()


async def generar_audio_async(
    texto, ruta_salida, voz="es-MX-JorgeNeural", velocidad="+0%"
):
  communicate = edge_tts.Communicate(texto, voz, rate=velocidad)
  await communicate.save(ruta_salida)


def generar_audio(
    texto, ruta_salida, voz="es-MX-JorgeNeural", velocidad="+0%"
):
  try:
    asyncio.run(generar_audio_async(texto, ruta_salida, voz, velocidad))
  except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        generar_audio_async(texto, ruta_salida, voz, velocidad)
    )


def buscar_imagen_real_web(query):
  headers = {"User-Agent": "Mozilla/5.0"}
  try:
    url_wiki = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&prop=imageinfo&iiprop=url&gsrsearch={urllib.parse.quote(query)}&gsrnamespace=6&format=json"
    res = requests.get(url_wiki, headers=headers, timeout=6).json()
    pages = res.get("query", {}).get("pages", {})
    for page in pages.values():
      info = page.get("imageinfo", [])
      if info and info[0].get("url").lower().endswith(
          (".jpg", ".jpeg", ".png", ".webp")
      ):
        r = requests.get(info[0].get("url"), headers=headers, timeout=6)
        if r.status_code == 200:
          return Image.open(io.BytesIO(r.content))
  except Exception:
    pass
  return Image.new("RGB", (900, 900), color=(15, 23, 42))


def formatear_lineas_specs(texto_raw, draw, font, max_width):
  lineas_resultado = []
  for l in str(texto_raw).split("\n"):
    l_str = l.strip()
    if not l_str:
      continue
    prefix = (
        "⚡ "
        if not any(l_str.startswith(c) for c in ["•", "⚡", "🔹", "⭐", "📊"])
        else ""
    )
    words = (prefix + l_str).split(" ")
    current_line = []
    for word in words:
      test_line = " ".join(current_line + [word])
      bbox = draw.textbbox((0, 0), test_line, font=font)
      if (bbox[2] - bbox[0]) <= max_width:
        current_line.append(word)
      else:
        if current_line:
          lineas_resultado.append(" ".join(current_line))
          current_line = [word]
        else:
          lineas_resultado.append(word)
    if current_line:
      lineas_resultado.append(" ".join(current_line))
  return lineas_resultado


# --- DIBUJO DE FRAME INDIVIDUAL ---
def crear_frame_diapositiva(
    imagen_base,
    titulo,
    texto_specs,
    tema,
    dimensiones,
    handle_usuario="",
    logo_img=None,
):
  W, H = dimensiones
  colores = TEMAS[tema]
  canvas = Image.new("RGBA", (W, H), colores["bg"])
  draw = ImageDraw.Draw(canvas)
  f_factor = min(W, H) / 1080.0

  font_titulo = cargar_fuente_hd(int(42 * f_factor))
  font_specs = cargar_fuente_hd(int(32 * f_factor))
  font_handle = cargar_fuente_hd(int(24 * f_factor))

  if handle_usuario:
    draw.text(
        (int(W * 0.05), int(H * 0.03)),
        handle_usuario,
        font=font_handle,
        fill=colores["accent"],
    )

  draw.rounded_rectangle(
      [int(W * 0.05), int(H * 0.07), int(W * 0.95), int(H * 0.14)],
      radius=15,
      fill=colores["card"],
      outline=colores["accent"],
      width=3,
  )
  draw.text(
      (W // 2, int(H * 0.105)),
      str(titulo).upper(),
      font=font_titulo,
      fill=colores["text"],
      anchor="mm",
  )

  img = imagen_base.convert("RGBA")
  img.thumbnail((int(W * 0.85), int(H * 0.42)), LANCZOS_FILTER)
  x_img = (W - img.width) // 2
  y_img = int(H * 0.16) + (int(H * 0.42) - img.height) // 2
  canvas.paste(img, (x_img, y_img), img if img.mode == "RGBA" else None)

  top_specs = int(H * 0.60)
  lineas = formatear_lineas_specs(
      texto_specs, draw, font_specs, max_width=int(W * 0.80)
  )
  line_height = int(50 * f_factor)
  draw.rounded_rectangle(
      [
          int(W * 0.05),
          top_specs,
          int(W * 0.95),
          min(top_specs + len(lineas) * line_height + 50, int(H * 0.94)),
      ],
      radius=20,
      fill=colores["card"],
      outline=colores["accent"],
      width=3,
  )

  y_txt = top_specs + 25
  for lin in lineas:
    draw.text(
        (int(W * 0.09), y_txt), lin, font=font_specs, fill=colores["text"]
    )
    y_txt += line_height

  return canvas.convert("RGB")


# --- DIBUJO DE FRAME VS (PANTALLA DIVIDIDA) ---
def crear_frame_vs(
    img_a,
    nombre_a,
    specs_a,
    img_b,
    nombre_b,
    specs_b,
    titulo,
    tema,
    dimensiones,
    handle_usuario="",
):
  W, H = dimensiones
  colores = TEMAS[tema]
  canvas = Image.new("RGBA", (W, H), colores["bg"])
  draw = ImageDraw.Draw(canvas)
  f_factor = min(W, H) / 1080.0

  font_titulo = cargar_fuente_hd(int(36 * f_factor))
  font_nombre = cargar_fuente_hd(int(30 * f_factor))
  font_specs = cargar_fuente_hd(int(24 * f_factor))
  font_vs = cargar_fuente_hd(int(42 * f_factor))
  font_handle = cargar_fuente_hd(int(22 * f_factor))

  if handle_usuario:
    draw.text(
        (int(W * 0.05), int(H * 0.02)),
        handle_usuario,
        font=font_handle,
        fill=colores["accent"],
    )

  # Banner Superior
  draw.rounded_rectangle(
      [int(W * 0.05), int(H * 0.05), int(W * 0.95), int(H * 0.11)],
      radius=12,
      fill=colores["card"],
      outline=colores["accent"],
      width=3,
  )
  draw.text(
      (W // 2, int(H * 0.08)),
      str(titulo).upper(),
      font=font_titulo,
      fill=colores["text"],
      anchor="mm",
  )

  col_w = int(W * 0.42)

  # Nombres de los teléfonos
  draw.rounded_rectangle(
      [int(W * 0.05), int(H * 0.13), int(W * 0.47), int(H * 0.18)],
      radius=10,
      fill=colores["card"],
  )
  draw.text(
      (int(W * 0.26), int(H * 0.155)),
      str(nombre_a).upper(),
      font=font_nombre,
      fill=colores["accent"],
      anchor="mm",
  )

  draw.rounded_rectangle(
      [int(W * 0.53), int(H * 0.13), int(W * 0.95), int(H * 0.18)],
      radius=10,
      fill=colores["card"],
  )
  draw.text(
      (int(W * 0.74), int(H * 0.155)),
      str(nombre_b).upper(),
      font=font_nombre,
      fill=colores["accent"],
      anchor="mm",
  )

  # Img Teléfono A
  i1 = img_a.convert("RGBA")
  i1.thumbnail((col_w, int(H * 0.30)), LANCZOS_FILTER)
  x1 = int(W * 0.05) + (col_w - i1.width) // 2
  y1 = int(H * 0.19) + (int(H * 0.30) - i1.height) // 2
  canvas.paste(i1, (x1, y1), i1 if i1.mode == "RGBA" else None)

  # Img Teléfono B
  i2 = img_b.convert("RGBA")
  i2.thumbnail((col_w, int(H * 0.30)), LANCZOS_FILTER)
  x2 = int(W * 0.53) + (col_w - i2.width) // 2
  y2 = int(H * 0.19) + (int(H * 0.30) - i2.height) // 2
  canvas.paste(i2, (x2, y2), i2 if i2.mode == "RGBA" else None)

  # Círculo VS central
  cx, cy = W // 2, int(H * 0.34)
  r_vs = int(40 * f_factor)
  draw.ellipse(
      [cx - r_vs, cy - r_vs, cx + r_vs, cy + r_vs],
      fill=(255, 0, 51, 255),
      outline=(255, 255, 255),
      width=3,
  )
  draw.text((cx, cy), "VS", font=font_vs, fill=(255, 255, 255), anchor="mm")

  # Cajas de Especificaciones
  top_specs = int(H * 0.51)
  bot_specs = int(H * 0.94)

  draw.rounded_rectangle(
      [int(W * 0.05), top_specs, int(W * 0.47), bot_specs],
      radius=15,
      fill=colores["card"],
      outline=colores["accent"],
      width=2,
  )
  draw.rounded_rectangle(
      [int(W * 0.53), top_specs, int(W * 0.95), bot_specs],
      radius=15,
      fill=colores["card"],
      outline=colores["accent"],
      width=2,
  )

  # Specs Teléfono A
  lineas_a = formatear_lineas_specs(
      specs_a, draw, font_specs, max_width=int(col_w * 0.88)
  )
  y_t = top_specs + 20
  for l in lineas_a:
    draw.text((int(W * 0.07), y_t), l, font=font_specs, fill=colores["text"])
    y_t += int(38 * f_factor)

  # Specs Teléfono B
  lineas_b = formatear_lineas_specs(
      specs_b, draw, font_specs, max_width=int(col_w * 0.88)
  )
  y_t = top_specs + 20
  for l in lineas_b:
    draw.text((int(W * 0.55), y_t), l, font=font_specs, fill=colores["text"])
    y_t += int(38 * f_factor)

  return canvas.convert("RGB")


# --- INTERFAZ STREAMLIT ---
st.title("🎬 Creador de Videos Tech - Modo VS & Review")

col_left, col_right = st.columns([1, 1])
with col_left:
  st.subheader("⚙️ Configuración General")
  modo_video = st.radio(
      "Modo de Video:", ["Comparativa VS (2 Teléfonos)", "Review Individual"]
  )
  tema_elegido = st.selectbox("Tema de Color:", list(TEMAS.keys()))
  formato_elegido = st.selectbox("Formato de Video:", list(FORMATOS.keys()))
  handle_social = st.text_input(
      "🏷️ Marca de agua / Usuario:", value="@TuCanalTech"
  )

with col_right:
  st.subheader("🎵 Audio")
  voz_locutor = st.selectbox(
      "Voz de la IA:",
      [
          "es-MX-JorgeNeural (Hombre)",
          "es-MX-DaliaNeural (Mujer)",
          "es-ES-AlvaroNeural (Hombre)",
      ],
  )
  archivo_musica = st.file_uploader("🎵 Música (MP3):", type=["mp3"])
  volumen_musica = st.slider(
      "Volumen de la música:", 0.01, 0.20, 0.04, step=0.01
  )

st.markdown("---")

if modo_video == "Comparativa VS (2 Teléfonos)":
  st.subheader("⚔️ Configurar Duelo de Teléfonos")
  col_a, col_b = st.columns(2)

  with col_a:
    st.markdown("### 📱 Teléfono A")
    nombre_a = st.text_input("Modelo A:", value="Poco X6 Pro")
    specs_a = st.text_area(
        "Specs A:",
        value=(
            "Pantalla: AMOLED 120Hz\nProcesador: Dimensity 8300\nBatería: 5000"
            " mAh\nCámara: 64 MP OIS\n⭐ Puntaje: 9.2/10"
        ),
    )
    img_a_up = st.file_uploader("Foto Teléfono A (Opcional):", type=["jpg", "png"])

  with col_b:
    st.markdown("### 📱 Teléfono B")
    nombre_b = st.text_input("Modelo B:", value="Redmi Note 13 Pro+")
    specs_b = st.text_area(
        "Specs B:",
        value=(
            "Pantalla: AMOLED 120Hz\nProcesador: Dimensity 7200\nBatería: 5000"
            " mAh\nCámara: 200 MP OIS\n⭐ Puntaje: 8.9/10"
        ),
    )
    img_b_up = st.file_uploader("Foto Teléfono B (Opcional):", type=["jpg", "png"])

  num_escenas = st.number_input("Número de Escenas VS:", 1, 5, 2)
  escenas_config = []

  for i in range(num_escenas):
    with st.expander(f"🎬 Escena VS {i+1}", expanded=(i == 0)):
      tit = st.text_input(
          f"Título Ronda {i+1}:",
          value="PANTALLA Y POTENCIA" if i == 0 else "CÁMARAS Y VEREDICTO",
          key=f"vst_{i}",
      )
      loc = st.text_area(
          f"Locución Ronda {i+1}:",
          value=(
              f"En pantalla y potencia, el {nombre_a} supera al {nombre_b}"
              " gracias a su procesador Dimensity 8300."
          ),
          key=f"vsl_{i}",
      )

      if st.button(f"👁️ Previsualizar VS {i+1}", key=f"vsprev_{i}"):
        i1 = (
            Image.open(img_a_up)
            if img_a_up
            else buscar_imagen_real_web(f"{nombre_a} phone")
        )
        i2 = (
            Image.open(img_b_up)
            if img_b_up
            else buscar_imagen_real_web(f"{nombre_b} phone")
        )
        f_prev = crear_frame_vs(
            i1,
            nombre_a,
            specs_a,
            i2,
            nombre_b,
            specs_b,
            tit,
            tema_elegido,
            FORMATOS[formato_elegido],
            handle_social,
        )
        st.image(f_prev, caption="Vista Previa VS", width=360)

      escenas_config.append({
          "titulo": tit,
          "locucion": loc,
          "is_vs": True,
          "nombre_a": nombre_a,
          "specs_a": specs_a,
          "img_a_up": img_a_up,
          "nombre_b": nombre_b,
          "specs_b": specs_b,
          "img_b_up": img_b_up,
      })

else:
  # Lógica de Review Individual
  nombre_celular = st.text_input("📱 Modelo:", value="Poco X6 Pro")
  tit = st.text_input("Título:", value="REVIEW COMPLETA")
  loc = st.text_area(
      "Locución:", value=f"Análisis completo del {nombre_celular}."
  )
  pts = st.text_area("Specs:", value="Pantalla: 120Hz\nBatería: 5000 mAh")
  escenas_config = [{
      "titulo": tit,
      "locucion": loc,
      "is_vs": False,
      "nombre": nombre_celular,
      "specs": pts,
  }]

# --- RENDERIZADO DEL VIDEO ---
if st.button("🚀 Renderizar Video", type="primary"):
  try:
    voz_code = voz_locutor.split(" ")[0]
    dimensiones = FORMATOS[formato_elegido]
    clips_video = []
    progreso = st.progress(0.0)

    clip_musica_global = None
    if archivo_musica:
      with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_m:
        t_m.write(archivo_musica.read())
        clip_musica_global = AudioFileClip(t_m.name)

    for i, esc in enumerate(escenas_config):
      st.info(f"🎬 Procesando Escena {i+1}/{len(escenas_config)}")

      # TTS
      with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_audio:
        generar_audio(esc["locucion"], t_audio.name, voz=voz_code)
        audio_voz = AudioFileClip(t_audio.name)
        audio_voz = ajustar_volumen(audio_voz, 1.3)
        duracion = audio_voz.duration

      # Generar Imagen
      if esc["is_vs"]:
        i1 = (
            Image.open(esc["img_a_up"])
            if esc["img_a_up"]
            else buscar_imagen_real_web(f"{esc['nombre_a']} phone")
        )
        i2 = (
            Image.open(esc["img_b_up"])
            if esc["img_b_up"]
            else buscar_imagen_real_web(f"{esc['nombre_b']} phone")
        )
        frame = crear_frame_vs(
            i1,
            esc["nombre_a"],
            esc["specs_a"],
            i2,
            esc["nombre_b"],
            esc["specs_b"],
            esc["titulo"],
            tema_elegido,
            dimensiones,
            handle_social,
        )
      else:
        i1 = buscar_imagen_real_web(f"{esc['nombre']} phone")
        frame = crear_frame_diapositiva(
            i1,
            esc["titulo"],
            esc["specs"],
            tema_elegido,
            dimensiones,
            handle_social,
        )

      # Audio Mezclado
      if clip_musica_global:
        m_sub = recortar_audio(
            clip_musica_global, 0, min(duracion, clip_musica_global.duration)
        )
        m_sub = ajustar_volumen(m_sub, volumen_musica)
        audio_mix = CompositeAudioClip([audio_voz, m_sub])
      else:
        audio_mix = audio_voz

      # Exportar Frame a Video
      with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t_f:
        frame.save(t_f.name)
        v_clip = ImageClip(t_f.name)
        v_clip = fijar_duracion(v_clip, duracion)
        v_clip = fijar_audio(v_clip, audio_mix)
        clips_video.append(v_clip)

      progreso.progress((i + 1) / len(escenas_config))

    video_final = concatenate_videoclips(clips_video, method="compose")
    ruta_mp4 = tempfile.mktemp(suffix=".mp4")
    video_final.write_videofile(
        ruta_mp4, fps=24, codec="libx264", audio_codec="aac"
    )
    video_final.close()

    st.success("🎉 ¡Video VS renderizado exitosamente!")
    st.video(ruta_mp4)

  except Exception as e:
    st.error(f"Error durante el renderizado: {e}")
