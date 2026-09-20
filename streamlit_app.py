import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

# Configuración del Dashboard
st.set_page_config(
    page_title="MLB Analyst - Todos los Jugadores Activos & Probabilidad L5",
    page_icon="⚾",
    layout="wide"
)

st.title("⚾ Analizador MLB: Probabilidad de Hit para Próximo Juego (L5)")
st.markdown("Selecciona o busca cualquier jugador activo de la MLB para extraer sus últimos 5 partidos y calcular la probabilidad estimada de Hit.")
st.markdown("---")

# ==========================================
# EXTRACCIÓN DINÁMICA DE JUGADORES ACTIVOS
# ==========================================

@st.cache_data(ttl=86400)  # Se actualiza una vez al día
def obtener_directorio_jugadores_activos():
    """Obtiene la lista completa de bateadores activos de los 30 equipos de la MLB."""
    diccionario_jugadores = {}
    anio_actual = datetime.now().year
    
    try:
        # Obtener los 30 equipos de la MLB
        equipos = statsapi.get('teams', {'sportId': 1, 'season': anio_actual}).get('teams', [])
        
        for equipo in equipos:
            team_id = equipo.get('id')
            # Obtener el roster activo del equipo
            roster = statsapi.get('team_roster', {'teamId': team_id, 'rosterType': 'active'}).get('roster', [])
            
            for p in roster:
                person = p.get('person', {})
                posicion = p.get('position', {}).get('abbreviation', '')
                
                # Filtrar bateadores (excluir lanzadores puros, conservar lanzadores/bateadores como Ohtani)
                if posicion != 'P' or person.get('fullName') == 'Shohei Ohtani':
                    nombre = person.get('fullName')
                    player_id = person.get('id')
                    equipo_nom = equipo.get('teamName', '')
                    
                    if nombre and player_id:
                        etiqueta = f"{nombre} ({posicion} - {equipo_nom})"
                        diccionario_jugadores[etiqueta] = player_id
                        
        return dict(sorted(diccionario_jugadores.items()))
    except Exception:
        # Lista de respaldo en caso de fallo de conexión masiva
        return {
            "Shohei Ohtani (DH - Dodgers)": 660271,
            "Aaron Judge (OF - Yankees)": 592450,
            "Juan Soto (OF - Mets)": 665742,
            "Ronald Acuna Jr. (OF - Braves)": 660670,
            "Mookie Betts (IF - Dodgers)": 605141,
            "Vladimir Guerrero Jr. (1B - Blue Jays)": 665489
        }

def buscar_juego_por_fecha(player_id, fecha_str):
    """Extrae las estadísticas de un juego específico mediante consulta directa de Box Score."""
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
    """Garantiza la extracción de los últimos 5 juegos del jugador seleccionado."""
    registros = []
    anio_actual = datetime.now().year
    
    # Intentar logs de la temporada actual y anterior
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
    
    # Rastreo diario retroactivo si la lista aún no tiene 5 partidos
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
        
    df = df.sort_values(by='date', ascending=False).reset_index(drop=True)
    df_5 = df.head(5).copy()
    
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

def calcular_probabilidad_proximo_juego(df_5):
    """Calcula la probabilidad de dar Hit en el próximo juego mediante el modelo Poisson ponderado."""
    total_ab = df_5['AB'].sum()
    total_h = df_5['H'].sum()
    juegos_con_hit = (df_5['H'] > 0).sum()
    n_juegos = len(df_5)
    
    if total_ab == 0:
        return {"avg_5": 0.0, "prob_hit": 0.0, "estado": "Sin turnos", "emoji": "⚪", "muestra": 0}
        
    avg_5 = total_h / total_ab
    
    # Pesos por recencia (mayores al partido más reciente)
    pesos = np.array([0.35, 0.25, 0.20, 0.12, 0.08])[:n_juegos]
    pesos = pesos / pesos.sum()
    
    rates = np.where(df_5['AB'].values > 0, df_5['H'].values / df_5['AB'].values, 0)
    avg_ponderado = np.sum(rates * pesos)
    
    # Modelo Poisson sobre una media estimada de 3.8 turnos por juego
    lambda_hits = avg_ponderado * 3.8
    prob_hit = (1 - np.exp(-lambda_hits)) * 100
    
    if avg_5 >= 0.350 or juegos_con_hit >= 4:
        estado, emoji = "Tendencia Alta (Caliente)", "🔥"
    elif avg_5 <= 0.180 or juegos_con_hit <= 1:
        estado, emoji = "Tendencia Baja (Frío)", "❄️"
    else:
        estado, emoji = "Rendimiento Balanceado", "⚖️"
        
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

# ==========================================
# INTERFAZ Y BÚSQUEDA
# ==========================================

with st.spinner("Cargando lista completa de jugadores activos MLB..."):
    directorio_jugadores = obtener_directorio_jugadores_activos()

st.sidebar.header("🔍 Buscador de Jugadores")
st.sidebar.caption(f"Total de bateadores activos en catálogo: **{len(directorio_jugadores)}**")

# Selector múltiple con autocompletado para buscar cualquier jugador
opciones_nombres = list(directorio_jugadores.keys())
predeterminados = [opt for opt in opciones_nombres if "Ohtani" in opt or "Judge" in opt or "Soto" in opt][:3]

seleccionados = st.sidebar.multiselect(
    "Escribe el nombre del jugador:",
    options=opciones_nombres,
    default=predeterminados if predeterminados else opciones_nombres[:2]
)

if not seleccionados:
    st.info("Escribe o selecciona al menos un jugador en el panel izquierdo para calcular su probabilidad.")
else:
    for etiqueta_jugador in seleccionados:
        player_id = directorio_jugadores[etiqueta_jugador]
        
        with st.spinner(f"Analizando últimos 5 partidos de {etiqueta_jugador}..."):
            df_5 = obtener_ultimos_5_juegos_garantizado(player_id)
            
        if df_5 is None or df_5.empty:
            st.warning(f"No hay partidos registrados recientemente para **{etiqueta_jugador}**.")
            continue
            
        res_prob = calcular_probabilidad_proximo_juego(df_5)
        
        # Tarjeta de Resumen y Probabilidad
        with st.container():
            col_titulo, col_prob, col_avg, col_hits, col_muestra = st.columns([2.5, 1.2, 1, 1, 1])
            
            with col_titulo:
                st.subheader(f"{res_prob['emoji']} {etiqueta_jugador.split(' (')[0]}")
                st.caption(f"Estatus: **{res_prob['estado']}** | Juegos con Hit: **{res_prob['juegos_con_hit']}**")
                
            with col_prob:
                st.metric(
                    label="🎯 Prob. Hit Próx. Juego", 
                    value=f"{res_prob['prob_hit']}%"
                )
            with col_avg:
                st.metric("AVG (L5)", f"{res_prob['avg_5']:.3f}")
            with col_hits:
                st.metric("Hits / HR", f"{res_prob['total_h']} H / {res_prob['total_hr']} HR")
            with col_muestra:
                st.metric("Partidos L5", f"{res_prob['muestra']} / 5")
                
            st.markdown("**Registro detallado de los últimos 5 partidos:**")
            st.dataframe(df_5, use_container_width=True)
            st.markdown("---")
