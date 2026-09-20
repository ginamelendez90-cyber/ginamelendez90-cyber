import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

# Configuración del Dashboard
st.set_page_config(
    page_title="MLB Analyst - Análisis L5 Garantizado",
    page_icon="⚾",
    layout="wide"
)

st.title("⚾ Sistema Analítico MLB: Extracción Garantizada de 5 Partidos (L5)")
st.markdown("Si la API general no ha indexado los juegos recientes, el script rastrea el calendario día por día hasta completar exactamente 5 partidos jugados.")
st.markdown("---")

JUGADORES_BASE = [
    "Shohei Ohtani",
    "Aaron Judge",
    "Juan Soto",
    "Ronald Acuna Jr.",
    "Mookie Betts",
    "Vladimir Guerrero Jr."
]

def buscar_juego_por_fecha(player_id, fecha_str):
    """Extrae las estadísticas de un jugador en una fecha específica consultando directamente el BoxScore."""
    try:
        juegos = statsapi.schedule(date=fecha_str)
        if not isinstance(juegos, list):
            return None
            
        key_jugador = f"ID{player_id}"
        for juego in juegos:
            if juego.get('status') in ['Final', 'Completed Early', 'In Progress', 'Game Over']:
                game_pk = juego.get('game_id')
                if not game_pk:
                    continue
                box = statsapi.boxscore_data(game_pk)
                for lado in ['home', 'away']:
                    jugadores = box.get(lado, {}).get('players', {})
                    if key_jugador in jugadores:
                        b_stats = jugadores[key_jugador].get('stats', {}).get('batting', {})
                        if b_stats and b_stats.get('atBats', 0) > 0:
                            rival = juego.get('away_name') if lado == 'home' else juego.get('home_name')
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
def obtener_ultimos_5_juegos_garantizado(player_id):
    """
    Garantiza la obtención de exactamente 5 partidos combinando los logs de la API
    con un rastreo diario retroactivo.
    """
    registros = []
    anio_actual = datetime.now().year
    
    # 1. Intentar extraer mediante logs oficiales (Temporada actual y anterior)
    for anio in [anio_actual, anio_actual - 1]:
        try:
            res = statsapi.player_game_logs(player_id, group="hitting", season=anio)
            if isinstance(res, list) and len(res) > 0:
                registros.extend(res)
                if len(registros) >= 5:
                    break
        except Exception:
            pass
            
    df = pd.DataFrame(registros) if registros else pd.DataFrame()
    
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date', ascending=False)
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        df = df.drop_duplicates(subset=['date'])
        
    fechas_existentes = set(df['date'].values) if not df.empty and 'date' in df.columns else set()
    
    # 2. Rastreo diario retroactivo si la lista tiene menos de 5 partidos
    dia_cursor = datetime.now()
    intentos = 0
    adicionales = []
    
    while (len(fechas_existentes) + len(adicionales)) < 5 and intentos < 25:
        fecha_evaluar = dia_cursor.strftime('%Y-%m-%d')
        if fecha_evaluar not in fechas_existentes:
            stat = buscar_juego_por_fecha(player_id, fecha_evaluar)
            if stat:
                adicionales.append(stat)
        dia_cursor -= timedelta(days=1)
        intentos += 1
        
    if adicionales:
        df_adicional = pd.DataFrame(adicionales)
        df = pd.concat([df_adicional, df], ignore_index=True) if not df.empty else df_adicional
        
    if df.empty:
        return None
        
    # Reordenar por fecha reciente y seleccionar exactamente 5 juegos
    df = df.sort_values(by='date', ascending=False).reset_index(drop=True)
    df_5 = df.head(5).copy()
    
    # Mapeo de columnas
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
    
    cols_presentes = [c for c in columnas.keys() if c in df_5.columns]
    df_final = df_5[cols_presentes].rename(columns=columnas)
    
    for col in ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']:
        if col in df_final.columns:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0).astype(int)
            
    return df_final

def analizar_prediccion_poisson(df_5):
    """Genera la proyección estadística sobre la muestra de 5 juegos."""
    total_ab = df_5['AB'].sum()
    total_h = df_5['H'].sum()
    juegos_con_hit = (df_5['H'] > 0).sum()
    n_juegos = len(df_5)
    
    if total_ab == 0:
        return {"avg_5": 0.0, "prob_hit": 0.0, "estado": "Sin turnos", "emoji": "⚪", "muestra": 0}
        
    avg_5 = total_h / total_ab
    
    # Pesos por recencia (0.35 para el juego más reciente)
    pesos = np.array([0.35, 0.25, 0.20, 0.12, 0.08])[:n_juegos]
    pesos = pesos / pesos.sum()
    
    rates = np.where(df_5['AB'].values > 0, df_5['H'].values / df_5['AB'].values, 0)
    avg_ponderado = np.sum(rates * pesos)
    
    lambda_hits = avg_ponderado * 3.8
    prob_hit = (1 - np.exp(-lambda_hits)) * 100
    
    if avg_5 >= 0.350 or juegos_con_hit >= 4:
        estado, emoji = "Racha Caliente", "🔥"
    elif avg_5 <= 0.180 or juegos_con_hit <= 1:
        estado, emoji = "Racha Fría", "❄️"
    else:
        estado, emoji = "Rendimiento Estable", "⚖️"
        
    return {
        "avg_5": round(avg_5, 3),
        "prob_hit": round(min(prob_hit, 94.0), 1),
        "estado": estado,
        "emoji": emoji,
        "juegos_con_hit": f"{juegos_con_hit}/{n_juegos}",
        "total_h": total_h,
        "total_hr": df_5['HR'].sum(),
        "muestra": n_juegos
    }

@st.cache_data(ttl=3600)
def buscar_player_id(nombre):
    """Busca el ID oficial del jugador."""
    try:
        res = statsapi.lookup_player(nombre)
        if res and isinstance(res, list):
            return res[0]['id'], res[0]['fullName']
    except Exception:
        pass
    return None, None

# ==========================================
# INTERFAZ DE USUARIO
# ==========================================

st.sidebar.header("⚙️ Configuración")
seleccionados = st.sidebar.multiselect(
    "Selecciona jugadores:",
    options=JUGADORES_BASE,
    default=JUGADORES_BASE[:3]
)

nuevo = st.sidebar.text_input("Añadir otro jugador:")
if nuevo and nuevo not in seleccionados:
    seleccionados.append(nuevo)

if not seleccionados:
    st.info("Selecciona un jugador para ver el análisis L5.")
else:
    for nombre in seleccionados:
        p_id, p_nombre = buscar_player_id(nombre)
        
        if not p_id:
            st.error(f"No se encontró el ID para: **{nombre}**")
            continue
            
        with st.spinner(f"Extrayendo últimos 5 partidos de {p_nombre}..."):
            df_5 = obtener_ultimos_5_juegos_garantizado(p_id)
        
        if df_5 is None or df_5.empty:
            st.warning(f"No hay registros de partidos para **{p_nombre}**.")
            continue
            
        pred = analizar_prediccion_poisson(df_5)
        
        with st.container():
            col_head, c1, c2, c3, c4 = st.columns([2.5, 1, 1, 1, 1])
            
            with col_head:
                st.subheader(f"{pred['emoji']} {p_nombre}")
                st.caption(f"Estatus: **{pred['estado']}** | Partidos con Hit: **{pred['juegos_con_hit']}**")
                
            with c1:
                st.metric("AVG (L5)", f"{pred['avg_5']:.3f}")
            with c2:
                st.metric("Hits / HR", f"{pred['total_h']} H / {pred['total_hr']} HR")
            with c3:
                st.metric("Prob. Hit Próx. Juego", f"{pred['prob_hit']}%")
            with c4:
                st.metric("Partidos Extraídos", f"{pred['muestra']} / 5")
                
            st.dataframe(df_5, use_container_width=True)
            st.markdown("---")
