import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

# Configuración del Dashboard
st.set_page_config(
    page_title="MLB Analyst - Análisis L5",
    page_icon="⚾",
    layout="wide"
)

st.title("⚾ Analista MLB: Extracción Dinámica de Últimos 5 Partidos")
st.markdown("---")

# Lista por defecto de jugadores a analizar
JUGADORES_BASE = [
    "Shohei Ohtani",
    "Aaron Judge",
    "Juan Soto",
    "Ronald Acuna Jr.",
    "Mookie Betts",
    "Vladimir Guerrero Jr."
]

def obtener_stat_ayer_directo(player_id, fecha_str):
    """
    Consulta directamente el Box Score del calendario para obtener
    las estadísticas de un jugador en la fecha indicada si aún no aparecen en el historial.
    """
    try:
        juegos = statsapi.schedule(date=fecha_str)
        key_jugador = f"ID{player_id}"
        
        for juego in juegos:
            if juego.get('status') in ['Final', 'Completed Early', 'In Progress']:
                game_pk = juego['game_id']
                box = statsapi.boxscore_data(game_pk)
                
                for lado in ['home', 'away']:
                    jugadores = box.get(lado, {}).get('players', {})
                    if key_jugador in jugadores:
                        b_stats = jugadores[key_jugador].get('stats', {}).get('batting', {})
                        if b_stats and b_stats.get('atBats', 0) > 0:
                            rival = juego['away_name'] if lado == 'home' else juego['home_name']
                            return {
                                'date': fecha_str,
                                'opponent': f"vs {rival}",
                                'ab': b_stats.get('atBats', 0),
                                'h': b_stats.get('hits', 0),
                                'doubles': b_stats.get('doubles', 0),
                                'triples': b_stats.get('triples', 0),
                                'homeRuns': b_stats.get('homeRuns', 0),
                                'rbi': b_stats.get('rbi', 0),
                                'baseOnBalls': b_stats.get('baseOnBalls', 0),
                                'strikeOuts': b_stats.get('strikeOuts', 0)
                            }
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
def obtener_ultimos_5_juegos(player_id):
    """
    Llama los últimos 5 partidos jugados combinando logs históricos
    y consulta directa por Box Score para asegurar máxima actualización.
    """
    anio_actual = datetime.now().year
    logs = statsapi.player_game_logs(player_id, group="hitting", season=anio_actual)
    
    if not logs:
        logs = statsapi.player_game_logs(player_id, group="hitting", season=anio_actual - 1)
        
    df = pd.DataFrame(logs) if logs else pd.DataFrame()
    
    # Fecha de ayer en formato YYYY-MM-DD
    ayer_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Verificar si el juego de ayer ya fue indexado
    fecha_incluida = False
    if not df.empty and 'date' in df.columns:
        fecha_incluida = ayer_str in df['date'].values
        
    # Si ayer no está en los logs, buscar directamente en el Box Score del calendario
    if not fecha_incluida:
        stat_ayer = obtener_stat_ayer_directo(player_id, ayer_str)
        if stat_ayer:
            df_ayer = pd.DataFrame([stat_ayer])
            df = pd.concat([df, df_ayer], ignore_index=True)
            
    if df.empty:
        return None
        
    # Ordenar por fecha más reciente
    if 'date' in df.columns:
        df = df.sort_values(by='date', ascending=False)
        
    # Extraer exactamente los últimos 5 partidos
    df_5 = df.head(5).copy()
    
    # Normalizar nombres de columnas
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
        'strikeOuts': 'K'
    }
    
    cols_existentes = [c for c in columnas.keys() if c in df_5.columns]
    df_final = df_5[cols_existentes].rename(columns=columnas)
    
    # Formatear números
    for col in ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']:
        if col in df_final.columns:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0).astype(int)
            
    return df_final

def analizar_prediccion_poisson(df_5):
    """Calcula la probabilidad de conectar Hit en el próximo juego mediante Poisson ponderado."""
    total_ab = df_5['AB'].sum()
    total_h = df_5['H'].sum()
    juegos_con_hit = (df_5['H'] > 0).sum()
    
    if total_ab == 0:
        return {"avg_5": 0.0, "prob_hit": 0.0, "estado": "Sin turnos", "emoji": "⚪"}
        
    avg_5 = total_h / total_ab
    
    # Pesos por recencia (0.35 para el partido más reciente, 0.08 para el 5to más antiguo)
    pesos = np.array([0.35, 0.25, 0.20, 0.12, 0.08])[:len(df_5)]
    pesos = pesos / pesos.sum()
    
    rates = np.where(df_5['AB'].values > 0, df_5['H'].values / df_5['AB'].values, 0)
    avg_ponderado = np.sum(rates * pesos)
    
    # Estimación de Poisson sobre una base de 3.8 AB por juego
    lambda_hits = avg_ponderado * 3.8
    prob_hit = (1 - np.exp(-lambda_hits)) * 100
    
    if avg_5 >= 0.350 or juegos_con_hit >= 4:
        estado, emoji = "Caliente (Alta Racha)", "🔥"
    elif avg_5 <= 0.180 or juegos_con_hit <= 1:
        estado, emoji = "Frío (Baja Racha)", "❄️"
    else:
        estado, emoji = "Rendimiento Estable", "⚖️"
        
    return {
        "avg_5": round(avg_5, 3),
        "prob_hit": round(min(prob_hit, 93.5), 1),
        "estado": estado,
        "emoji": emoji,
        "juegos_con_hit": f"{juegos_con_hit}/5",
        "total_h": total_h,
        "total_hr": df_5['HR'].sum()
    }

@st.cache_data(ttl=3600)
def buscar_player_id(nombre):
    """Busca el ID del jugador."""
    try:
        res = statsapi.lookup_player(nombre)
        if res:
            return res[0]['id'], res[0]['fullName']
    except Exception:
        pass
    return None, None

# ==========================================
# DESPLIEGUE EN INTERFAZ
# ==========================================

st.sidebar.header("🔍 Panel de Filtros")
seleccionados = st.sidebar.multiselect(
    "Selecciona jugadores a procesar:",
    options=JUGADORES_BASE,
    default=JUGADORES_BASE[:3]
)

nuevo = st.sidebar.text_input("Agregar otro jugador por nombre:")
if nuevo and nuevo not in seleccionados:
    seleccionados.append(nuevo)

if not seleccionados:
    st.info("Selecciona al menos un jugador para ejecutar el análisis de los últimos 5 partidos.")
else:
    for nombre in seleccionados:
        p_id, p_nombre = buscar_player_id(nombre)
        
        if not p_id:
            st.error(f"Jugador no encontrado en la base de datos de MLB: **{nombre}**")
            continue
            
        df_5 = obtener_ultimos_5_juegos(p_id)
        
        if df_5 is None or df_5.empty:
            st.warning(f"No se registraron juegos recientes para **{p_nombre}**.")
            continue
            
        pred = analizar_prediccion_poisson(df_5)
        
        # Rendimiento del jugador
        with st.container():
            col_head, c1, c2, c3, c4 = st.columns([2.5, 1, 1, 1, 1])
            
            with col_head:
                st.subheader(f"{pred['emoji']} {p_nombre}")
                st.caption(f"Tendencia: **{pred['estado']}** | Juegos con Hit: **{pred['juegos_con_hit']}**")
                
            with c1:
                st.metric("AVG (L5)", f"{pred['avg_5']:.3f}")
            with c2:
                st.metric("Hits / HR", f"{pred['total_h']} H / {pred['total_hr']} HR")
            with c3:
                st.metric("Prob. Hit Próx. Juego", f"{pred['prob_hit']}%")
            with c4:
                st.metric("Partidos Analizados", f"{len(df_5)}")
                
            # Tabla de los 5 partidos
            st.markdown("**Desglose de los Últimos 5 Partidos:**")
            st.dataframe(df_5, use_container_width=True)
            st.markdown("---")
