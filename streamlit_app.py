import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Analista MLB - Datos en Tiempo Real",
    page_icon="⚾",
    layout="wide"
)

st.title("⚾ Sistema de Extracción y Predicción MLB")
st.markdown("Consulta en tiempo real utilizando el motor de **MLB-StatsAPI**.")
st.markdown("---")

# Lista sugerida de jugadores destacados
JUGADORES_BASE = [
    "Shohei Ohtani",
    "Aaron Judge",
    "Juan Soto",
    "Ronald Acuna Jr.",
    "Mookie Betts",
    "Vladimir Guerrero Jr."
]

@st.cache_data(ttl=3600)
def buscar_jugador(nombre):
    """Obtiene el ID oficial del jugador desde la API de la MLB."""
    try:
        resultados = statsapi.lookup_player(nombre)
        if resultados:
            return resultados[0]['id'], resultados[0]['fullName']
    except Exception:
        pass
    return None, None

@st.cache_data(ttl=1800)
def extraer_ultimos_juegos(player_id, cantidad_juegos=5):
    """Extrae el registro detallado de los últimos N juegos del bateador."""
    try:
        anio_actual = datetime.now().year
        # Intentar obtener partidos de la temporada actual
        logs = statsapi.player_game_logs(player_id, group="hitting", season=anio_actual)
        
        # Si la temporada no ha iniciado o está en pausa, consultar la anterior
        if not logs:
            logs = statsapi.player_game_logs(player_id, group="hitting", season=anio_actual - 1)
            
        if not logs:
            return None
            
        df = pd.DataFrame(logs)
        
        # Seleccionar los últimos N partidos y reordenar (más reciente primero)
        df_ultimos = df.tail(cantidad_juegos).iloc[::-1].copy()
        
        # Mapeo de columnas para presentación profesional
        columnas = {
            'date': 'Fecha',
            'opponent': 'Rival',
            'ab': 'AB',
            'h': 'H',
            'doubles': '2B',
            'triples': '3B',
            'homeRuns': 'HR',
            'rbi': 'CI',
            'baseOnBalls': 'BB',
            'strikeOuts': 'K',
            'avg': 'AVG'
        }
        
        cols_existentes = [c for c in columnas.keys() if c in df_ultimos.columns]
        df_resumen = df_ultimos[cols_existentes].rename(columns=columnas)
        
        # Asegurar formato numérico entero en métricas clave
        for c in ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']:
            if c in df_resumen.columns:
                df_resumen[c] = pd.to_numeric(df_resumen[c], errors='coerce').fillna(0).astype(int)
                
        return df_resumen
    except Exception:
        return None

def modelo_prediccion_poisson(df_juegos):
    """
    Modelo estadístico: Calcula la probabilidad de conectar al menos 1 HIT
    en el próximo juego basándose en la media ponderada de los partidos recientes.
    """
    total_ab = df_juegos['AB'].sum()
    total_h = df_juegos['H'].sum()
    juegos_con_hit = (df_juegos['H'] > 0).sum()
    n_juegos = len(df_juegos)
    
    if total_ab == 0 or n_juegos == 0:
        return {"avg": 0.0, "prob_hit": 0.0, "estado": "Sin datos", "emoji": "⚪"}
    
    # Promedio directo
    avg_reciente = total_h / total_ab
    
    # Pesos por recencia (da mayor importancia a los partidos más recientes)
    pesos = np.array([0.35, 0.25, 0.20, 0.12, 0.08])[:n_juegos]
    pesos = pesos / pesos.sum()
    
    hits = df_juegos['H'].values
    turnos = df_juegos['AB'].values
    
    tasas = np.where(turnos > 0, hits / turnos, 0)
    avg_ponderado = np.sum(tasas * pesos)
    
    # Estimación del modelo de Poisson (promedio asumido de 3.8 AB por partido)
    lambda_hits = avg_ponderado * 3.8
    prob_hit = (1 - np.exp(-lambda_hits)) * 100
    
    # Clasificación de tendencia
    if avg_reciente >= 0.350 or juegos_con_hit >= 4:
        estado, emoji = "Racha Caliente", "🔥"
    elif avg_reciente <= 0.180 or juegos_con_hit <= 1:
        estado, emoji = "Racha Fría", "❄️"
    else:
        estado, emoji = "Rendimiento Estándar", "⚖️"
        
    return {
        "avg": round(avg_reciente, 3),
        "prob_hit": round(min(prob_hit, 95.0), 1),
        "estado": estado,
        "emoji": emoji,
        "consistencia": f"{juegos_con_hit}/{n_juegos}",
        "total_hits": total_h,
        "total_hr": df_juegos['HR'].sum()
    }

# ==========================================
# PANEL DE CONTROL E INTERFAZ
# ==========================================

st.sidebar.header("🔍 Selección de Bateadores")
seleccion = st.sidebar.multiselect(
    "Selecciona los jugadores a analizar:",
    options=JUGADORES_BASE,
    default=JUGADORES_BASE[:3]
)

otro_jugador = st.sidebar.text_input("Buscar otro jugador por nombre exacto:")
if otro_jugador and otro_jugador not in seleccion:
    seleccion.append(otro_jugador)

if not seleccion:
    st.info("Selecciona al menos un jugador en el menú lateral para comenzar el análisis.")
else:
    for nombre in seleccion:
        player_id, nombre_oficial = buscar_jugador(nombre)
        
        if not player_id:
            st.error(f"No se encontró el registro oficial de: **{nombre}**")
            continue
            
        df_juegos = extraer_ultimos_juegos(player_id, cantidad_juegos=5)
        
        if df_juegos is None or df_juegos.empty:
            st.warning(f"No hay partidos recientes registrados para **{nombre_oficial}**.")
            continue
            
        pred = modelo_prediccion_poisson(df_juegos)
        
        # Despliegue de métricas
        with st.container():
            col_titulo, col1, col2, col3, col4 = st.columns([2.5, 1, 1, 1, 1])
            
            with col_titulo:
                st.subheader(f"{pred['emoji']} {nombre_oficial}")
                st.caption(f"Estatus: **{pred['estado']}** | Juegos conectando Hit: **{pred['consistencia']}**")
                
            with col1:
                st.metric("AVG (Últimos 5)", f"{pred['avg']:.3f}")
            with col2:
                st.metric("Hits / HR", f"{pred['total_hits']} H / {pred['total_hr']} HR")
            with col3:
                st.metric("Probabilidad Hit", f"{pred['prob_hit']}%")
            with col4:
                st.metric("Muestra", "5 Juegos")
                
            with st.expander(f"📊 Detalle partido a partido de {nombre_oficial}"):
                st.dataframe(df_juegos, use_container_width=True)
                
            st.markdown("---")
