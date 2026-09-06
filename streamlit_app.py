import streamlit as st
import pandas as pd
import plotly.express as px
import re
import base64
import requests
import io
import tempfile
import os
import textwrap
import urllib.parse
import numpy as np
import random
from PIL import Image, ImageDraw, ImageFont
import whisper

# Importaciones dinámicas compatibles con versiones legadas y modernas
try:
    from langchain_ollama import ChatOllama
except ImportError:
    from langchain_community.chat_models import ChatOllama

try:
    from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip
except ImportError:
    from moviepy import AudioFileClip, ImageClip, CompositeVideoClip

# Configuración inicial de la aplicación
st.set_page_config(
    page_title="Suite Multimedia y Analítica con IA",
    page_icon="🚀",
    layout="wide"
)

# Carga en caché del modelo Whisper para optimizar recursos
@st.cache_resource
def cargar_whisper():
    return whisper.load_model("tiny")

# Estilos predefinidos para la superposición de subtítulos
ESTILOS = {
    "🧸 Infantil / Niños": {
        "color_texto": (255, 235, 59),      # Amarillo brillante
        "color_borde": (233, 30, 99),       # Rosa/Magenta fuerte
        "color_fondo": (74, 20, 140, 210),  # Morado oscuro semi-transparente
        "emojis": ["🎈", "⭐", "🎵", "🧸", "✨", "🎉"],
        "tamanio_fuente": 42
    },
    "⚡ Neón / Pop": {
        "color_texto": (0, 255, 255),       # Cyan Neón
        "color_borde": (255, 0, 128),      # Neón Rosa
        "color_fondo": (10, 10, 20, 220),   # Azul muy oscuro
        "emojis": ["⚡", "🔥", "🎶", "💥"],
        "tamanio_fuente": 38
    },
    "✨ Elegante / Balada": {
        "color_texto": (255, 255, 255),     # Blanco puro
        "color_borde": (212, 175, 55),      # Dorado
        "color_fondo": (0, 0, 0, 180),      # Negro sutil
        "emojis": ["✨", "🌙", "💖"],
        "tamanio_fuente": 36
    }
}

# --- FUNCIONES DE ANÁLISIS DE DATOS E IMÁGENES ---

def extraer_tabla_de_imagen(archivo_imagen, base_url, modelo_vision="llama3.2-vision"):
    bytes_imagen = archivo_imagen.getvalue()
    b64_imagen = base64.b64encode(bytes_imagen).decode('utf-8')
    endpoint = f"{base_url.rstrip('/')}/api/chat"
    
    prompt = """Analiza la tabla presente en esta imagen y extrae todos sus datos.
Devuelve ÚNICAMENTE el contenido en formato CSV estándar (delimitado por comas), incluyendo los encabezados de columna.
NO agregues introducciones, comentarios ni explicaciones."""

    payload = {
        "model": modelo_vision,
        "messages": [{"role": "user", "content": prompt, "images": [b64_imagen]}],
        "stream": False
    }
    
    respuesta = requests.post(endpoint, json=payload, timeout=120)
    respuesta.raise_for_status()
    contenido = respuesta.json()["message"]["content"].strip()
    
    if "```" in contenido:
        match = re.search(r"
