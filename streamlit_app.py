import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime

# Configuración inicial del Dashboard
st.set_page_config(
    page_title="MLB Analyst - Radar de Rendimiento", 
    page_icon="⚾", 
    layout="wide"
)

st.title("⚾ Sistema Analítico MLB: Rachas y Predicciones en Tiempo Real")
st.markdown("---")

# Lista predeterminada de jugadores estrella
JUGADORES_DEFAULT = [
    "Shohei Ohtani",
    "Aaron Judge",
    "Juan Soto",
    "Ronald Acuna Jr.",
    "Mookie Betts",
    "Vladimir Guerrero Jr.",
    "Freddie Freeman",
    "Rafael Devers"
]

@st.cache_data(ttl=3600)
def obtener_id_jugador(nombre):
    """Busca el ID oficial del jugador en la API de la MLB."""
    try:
        busqueda = statsapi.lookup_player(nombre)
        if busqueda:
            return busqueda[0]['id'], busqueda[0]['fullName']
    except Exception:
        pass
    return None, None

@st.cache_data(ttl=1800)
def obtener_ultimos_5_juegos(player_id):
    """Obtiene el registro detallado de los últimos 5 partidos del bateador."""
    try:
        año_actual = datetime.now().year
        logs = statsapi.player_game_logs(player_id, group="hitting", season=año_actual)
        
        # Fallback a la temporada anterior si la actual está en pausa o empezando
        if not logs:
            logs = statsapi.player_game_logs(player_id, group="hitting", season=año_actual - 1)
            
        if not logs:
            return None
            
        df_logs = pd.DataFrame(logs)
        
        # Filtrar los últimos 5 juegos y ordenarlos del más reciente al más antiguo
        df_last5 = df_logs.tail(5).copy()
        df_last5 = df_last5.iloc[::-1]
        
        # Mapeo y estandarización de columnas estadisticas
        columnas_clave = {
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
            'avg': 'AVG_Temp'
        }
        
        cols_presentes = [c for c in columnas_clave.keys() if c in df_last5.columns]
        df_resumen = df_last5[cols_presentes].rename(columns=columnas_clave)
        
        # Convertir métricas a entero
        cols_numericas = ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']
        for col in cols_numericas:
            if col in df_resumen.columns:
                df_resumen[col] = pd.to_numeric(df_resumen[col], errors='coerce').fillna(0).astype(int)
                
        return df_resumen
    except Exception:
        return None

def generar_prediccion_analitica(df_5):
    """
    Algoritmo de predicción basado en Distribución de Poisson y Ponderación por Recencia.
    Calcula la probabilidad estimada de conectar al menos 1 HIT en el próximo juego.
    """
    total_ab = df_5['AB'].sum()
    total_h = df_5['H'].sum()
    total_hr = df_5['HR'].sum()
    
    juegos_con_hit = (df_5['H'] > 0).sum()
    
    if total_ab == 0:
        return {
            "avg_5": 0.0,
            "prob_hit": 0.0,
            "status": "Sin turnos recientes",
            "emoji": "⚪",
            "juegos_con_hit": "0/5",
            "total_h": 0,
            "total_hr": 0,
            "tb_promedio": 0.0
        }
    
    # 1. Promedio de bateo básico (L5)
    avg_5 = total_h / total_ab
    
    # 2. Ponderación por recencia (juegos más recientes reciben mayor peso)
    pesos = np.array([0.35, 0.25, 0.20, 0.12, 0.08])[:len(df_5)]
    pesos = pesos / pesos.sum()
    
    hits_array = df_5['H'].values
    ab_array = df_5['AB'].values
    
    rates = np.where(ab_array > 0, hits_array / ab_array, 0)
    avg_ponderado = np.sum(rates * pesos)
    
    # 3. Estimación de Poisson para Hits (Asumiendo media de 3.8 AB/juego)
    ab_esperados = 3.8
    lambda_hits = avg_ponderado * ab_esperados
    
    # P(X >= 1 Hit) = 1 - e^(-lambda)
    prob_hit = (1 - np.exp(-lambda_hits)) * 100
    
    # 4. Promedio de bases totales por juego (TB)
    tb_totales = df_5['H'].sum() + df_5['2B'].sum() + (2 * df_5['3B'].sum()) + (3 * df_5['HR'].sum())
    tb_promedio = tb_totales / len(df_5)
    
    # Clasificación de la tendencia del bateador
    if avg_5 >= 0.350 or juegos_con_hit >= 4:
        status = "🔥 En Racha Caliente"
        emoji = "🔥"
    elif avg_5 <= 0.170 or juegos_con_hit <= 1:
        status = "❄️ Racha Fría"
        emoji = "❄️"
    else:
        status = "⚖️ Rendimiento Estable"
        emoji = "⚖️"
        
    return {
        "avg_5": round(avg_5, 3),
        "prob_hit": round(min(prob_hit, 92.5), 1), # Umbral ajustado
        "status": status,
        "emoji": emoji,
        "juegos_con_hit": f"{juegos_con_hit}/5",
        "total_h": total_h,
        "total_hr": total_hr,
        "tb_promedio": round(tb_promedio, 2)
    }

# ==========================================
# INTERFAZ DE USUARIO (PANEL LATERAL Y PRINCIPAL)
# ==========================================

st.sidebar.header("⚙️ Panel de Jugadores")
jugadores_seleccionados = st.sidebar.multiselect(
    "Selecciona los jugadores a analizar:",
    options=JUGADORES_DEFAULT,
    default=JUGADORES_DEFAULT[:4]
)

# Permitir agregar cualquier otro jugador de la MLB por texto
nuevo_jugador = st.sidebar.text_input("Añadir otro jugador (Nombre exacto):")
if nuevo_jugador and nuevo_jugador not in jugadores_seleccionados:
    jugadores_seleccionados.append(nuevo_jugador)

st.subheader("📊 Métricas de los Últimos 5 Juegos & Modelado Predictivo")

if not jugadores_seleccionados:
    st.info("Selecciona al menos un jugador en el panel lateral para desplegar el análisis.")
else:
    for nombre in jugadores_seleccionados:
        p_id, p_nombre = obtener_id_jugador(nombre)
        
        if not p_id:
            st.error(f"No se encontró registro oficial en MLB para: **{nombre}**")
            continue
            
        df_5 = obtener_ultimos_5_juegos(p_id)
        
        if df_5 is None or df_5.empty:
            st.warning(f"Sin partidos recientes registrados para **{p_nombre}**.")
            continue
            
        # Calcular proyección analítica
        pred = generar_prediccion_analitica(df_5)
        
        # Tarjeta visual del jugador
        with st.container():
            col_info, col1, col2, col3, col4 = st.columns([2.5, 1, 1, 1, 1])
            
            with col_info:
                st.markdown(f"### {pred['emoji']} {p_nombre}")
                st.caption(f"Tendencia: **{pred['status']}** | Consistencia: **{pred['juegos_con_hit']} juegos con Hit**")
                
            with col1:
                st.metric("AVG (L5)", f"{pred['avg_5']:.3f}")
            with col2:
                st.metric("Hits / HR (L5)", f"{pred['total_h']} H / {pred['total_hr']} HR")
            with col3:
                st.metric("Bases Totales / J", f"{pred['tb_promedio']}")
            with col4:
                st.metric("Prob. Hit Próx. Juego", f"{pred['prob_hit']}%")
            
            # Tabla desplegable con el desglose partido a partido
            with st.expander(f"📋 Ver tabla detallada de últimos 5 partidos de {p_nombre}"):
                st.dataframe(df_5, use_container_width=True)
                
            st.markdown("---")
