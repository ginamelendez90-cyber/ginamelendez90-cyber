import streamlit as st
import pandas as pd
import numpy as np
import statsapi
import plotly.express as px
import altair as alt
from datetime import datetime, timedelta

st.set_page_config(page_title="MLB Analyst - Detección y Explicación de Proyección", page_icon="⚾", layout="wide")

st.title("⚾ Analizador MLB: Proyección y Justificación de Hit")
st.markdown("Análisis sabermétrico automatizado con explicación cualitativa detallada y visualizaciones avanzadas.")
st.markdown("---")

PARK_FACTORS = {
    "Coors Field": {"factor": 1.12, "tipo": "Estadio Extremedamente Bateador (+12%)"},
    "Fenway Park": {"factor": 1.06, "tipo": "Estadio Bateador (+6%)"},
    "Great American Ball Park": {"factor": 1.05, "tipo": "Estadio Bateador (+5%)"},
    "Yankee Stadium": {"factor": 1.03, "tipo": "Estadio Ligeramente Bateador (+3%)"},
    "Wrigley Field": {"factor": 1.02, "tipo": "Estadio Neutral / Viento Dependiente (+2%)"},
    "Dodger Stadium": {"factor": 1.00, "tipo": "Estadio Neutral (1.00)"},
    "Truist Park": {"factor": 1.00, "tipo": "Estadio Neutral (1.00)"},
    "Minute Maid Park": {"factor": 0.99, "tipo": "Estadio Neutral (0.99)"},
    "Citi Field": {"factor": 0.95, "tipo": "Estadio Lanzador (-5%)"},
    "Petco Park": {"factor": 0.94, "tipo": "Estadio Lanzador (-6%)"},
    "T-Mobile Park": {"factor": 0.92, "tipo": "Estadio Altamente Lanzador (-8%)"},
    "LoanDepot Park": {"factor": 0.93, "tipo": "Estadio Lanzador (-7%)"}
}

@st.cache_data(ttl=86400)
def obtener_directorio_jugadores_activos():
    diccionario_jugadores = {}
    anio_actual = datetime.now().year
    try:
        jugadores = statsapi.get('sports_players', {'sportId': 1, 'season': anio_actual, 'gameType': 'R'})
        for p in jugadores.get('people', []):
            pos_code = p.get('primaryPosition', {}).get('abbreviation', '')
            nombre = p.get('fullName', '')
            player_id = p.get('id')
            
            if (pos_code != 'P' or nombre == 'Shohei Ohtani') and p.get('active', False):
                bat_side = p.get('batSide', {}).get('code', 'R')
                diccionario_jugadores[f"{nombre} ({pos_code})"] = {
                    "id": player_id,
                    "bat_side": bat_side
                }
        return dict(sorted(diccionario_jugadores.items()))
    except Exception:
        return {"Shohei Ohtani (DH)": {"id": 660271, "bat_side": "L"}}

@st.cache_data(ttl=1800)
def auto_detectar_proximo_partido(player_id, bat_side):
    hoy = datetime.now().strftime('%Y-%m-%d')
    futuro = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    detalles = {
        "fecha": "Sin partido inmediato programado",
        "rival": "Por definir",
        "condicion": "N/A",
        "estadio": "Estadio Estándar",
        "factor_campo": 1.00,
        "desc_estadio": "Neutral (1.00)",
        "pitcher_nombre": "Por Anunciar / Reliever",
        "pitcher_mano": "R",
        "pitcher_era": "N/A",
        "perfil_pitcher": "Lanzador Promedio / Estándar",
        "factor_pitcher": 1.00
    }
    
    try:
        p_data = statsapi.player_stat_data(player_id, group="hitting", type="season")
        team_id = p_data.get('current_team_id')
        
        if not team_id:
            return detalles

        juegos = statsapi.schedule(team=team_id, start_date=hoy, end_date=futuro)
        if juegos:
            proximo = juegos[0]
            detalles["fecha"] = proximo.get('game_date', hoy)
            es_home = proximo.get('home_id') == team_id
            detalles["condicion"] = "Local" if es_home else "Visitante"
            detalles["rival"] = proximo.get('away_name') if es_home else proximo.get('home_name')
            
            venue_name = proximo.get('venue_name', 'Estadio Estándar')
            detalles["estadio"] = venue_name
            if venue_name in PARK_FACTORS:
                detalles["factor_campo"] = PARK_FACTORS[venue_name]["factor"]
                detalles["desc_estadio"] = PARK_FACTORS[venue_name]["tipo"]
                
            pitcher_key = 'away_probable_pitcher' if es_home else 'home_probable_pitcher'
            pitcher_nombre = proximo.get(pitcher_key, '')
            
            if pitcher_nombre:
                detalles["pitcher_nombre"] = pitcher_nombre
                lookup = statsapi.lookup_player(pitcher_nombre)
                if lookup:
                    p_id = lookup[0]['id']
                    pitch_hand = lookup[0].get('pitchHand', {}).get('code', 'R')
                    detalles["pitcher_mano"] = pitch_hand
                    
                    es_platoon = (bat_side == 'L' and pitch_hand == 'R') or (bat_side == 'R' and pitch_hand == 'L') or bat_side == 'S'
                    
                    try:
                        p_stat_data = statsapi.player_stat_data(p_id, group="pitching", type="season")
                        p_stats = p_stat_data.get('stats', [])
                        era_val = float(p_stats[0].get('stats', {}).get('era', '4.00')) if p_stats else 4.00
                        detalles["pitcher_era"] = f"{era_val:.2f}"
                    except Exception:
                        era_val = 4.00

                    if era_val <= 3.20:
                        detalles["perfil_pitcher"] = "Ace / Lanzador Dominante (-12%)"
                        detalles["factor_pitcher"] = 0.88
                    elif era_val >= 4.80:
                        detalles["perfil_pitcher"] = "Abridor Débil (+12%)"
                        detalles["factor_pitcher"] = 1.12
                    elif es_platoon:
                        detalles["perfil_pitcher"] = f"Ventaja Mano Opuesta ({bat_side} vs {pitch_hand}HP) (+6%)"
                        detalles["factor_pitcher"] = 1.06
                    else:
                        detalles["perfil_pitcher"] = f"Desventaja Misma Mano ({bat_side} vs {pitch_hand}HP) (-4%)"
                        detalles["factor_pitcher"] = 0.96
    except Exception:
        pass
        
    return detalles

@st.cache_data(ttl=3600)
def obtener_stats_temporada(player_id):
    anio_actual = datetime.now().year
    for yr in [anio_actual, anio_actual - 1]:
        try:
            res = statsapi.player_stat_data(player_id, group="hitting", type="season", season=yr)
            stats = res.get('stats', [])
            if stats:
                s_data = stats[0].get('stats', {})
                avg_val = s_data.get('avg', '.250')
                return {
                    'avg_season': float(avg_val) if avg_val not in ['.---', ''] else 0.250,
                    'games': int(s_data.get('gamesPlayed', 0)),
                    'year': yr
                }
        except Exception:
            pass
    return {'avg_season': 0.250, 'games': 0, 'year': anio_actual}

@st.cache_data(ttl=1800)
def obtener_ultimos_juegos_detallados(player_id):
    anio_actual = datetime.now().year
    registros = []
    es_previo = False
    
    for yr in [anio_actual, anio_actual - 1]:
        try:
            data = statsapi.player_stat_data(player_id, group="hitting", type="gameLog", season=yr)
            groups = data.get('stats', [])
            
            for grp in groups:
                game_logs = grp.get('stats', [])
                for item in game_logs:
                    s = item.get('stat', {})
                    opp = item.get('opponent', {})
                    opp_name = opp.get('name', 'N/A') if isinstance(opp, dict) else str(opp)
                    
                    registros.append({
                        'date': item.get('date', ''),
                        'opponent': opp_name,
                        'ab': int(s.get('atBats', 0)),
                        'h': int(s.get('hits', 0)),
                        'doubles': int(s.get('doubles', 0)),
                        'triples': int(s.get('triples', 0)),
                        'homeRuns': int(s.get('homeRuns', 0)),
                        'rbi': int(s.get('rbi', 0)),
                        'baseOnBalls': int(s.get('baseOnBalls', 0)),
                        'strikeOuts': int(s.get('strikeOuts', 0)),
                        'avg': s.get('avg', '.000')
                    })
            if registros:
                if yr < anio_actual:
                    es_previo = True
                break
        except Exception:
            pass
            
    df = pd.DataFrame(registros) if registros else pd.DataFrame()
    if df.empty:
        return None, "5.º al 9.º Bate (Menos Turnos)", False
        
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date', ascending=False).reset_index(drop=True)
    
    # Extraemos hasta 15 juegos para tendencias ricas y 5 para cálculo rápido
    df_15 = df.head(15).copy()
    df_5 = df.head(5).copy()

    columnas = {
        'date': 'Fecha', 'opponent': 'Rival', 'ab': 'AB', 'h': 'H',
        'doubles': '2B', 'triples': '3B', 'homeRuns': 'HR',
        'rbi': 'CI', 'baseOnBalls': 'BB', 'strikeOuts': 'K'
    }
    
    # Procesar dataframe de 15 juegos completo para gráficos
    cols_presentes = [c for c in columnas.keys() if c in df_15.columns]
    df_final_15 = df_15[cols_presentes].rename(columns=columnas)

    for col in ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']:
        if col in df_final_15.columns:
            df_final_15[col] = pd.to_numeric(df_final_15[col], errors='coerce').fillna(0).astype(int)
            
    if 'Fecha' in df_final_15.columns:
        df_final_15['Fecha'] = pd.to_datetime(df_final_15['Fecha']).dt.strftime('%Y-%m-%d')
        
    # Calcular promedio acumulado o rolling AVG por juego para la gráfica
    df_final_15['AVG_Juego'] = np.where(df_final_15['AB'] > 0, df_final_15['H'] / df_final_15['AB'], 0.0)
    df_final_15['AVG_Movil'] = df_final_15['H'].cumsum() / df_final_15['AB'].cumsum().replace(0, 1)

    avg_ab = df_final_15.head(5)['AB'].mean() if 'AB' in df_final_15.columns else 3.5
    pos_lineup = "1.º al 4.º Bate (Líderes de Turnos)" if avg_ab >= 3.8 else "5.º al 9.º Bate (Menos Turnos)"
    
    return df_final_15, pos_lineup, es_previo

def calcular_probabilidad_y_diagnostico(df_15, stats_season, proximo_info):
    df_5 = df_15.head(5) if df_15 is not None and not df_15.empty else None
    if df_5 is None or df_5.empty or df_5['AB'].sum() == 0:
        avg_reciente = stats_season['avg_season']
    else:
        n_juegos = len(df_5)
        pesos = np.array([0.35, 0.25, 0.20, 0.12, 0.08])[:n_juegos]
        pesos = pesos / pesos.sum()

        rates = np.where(df_5['AB'].values > 0, df_5['H'].values / df_5['AB'].values, 0)
        avg_reciente = np.sum(rates * pesos)

    avg_season = stats_season['avg_season']
    avg_base = (avg_reciente * 0.40) + (avg_season * 0.60)
    
    factor_picheo = proximo_info["factor_pitcher"]
    factor_parque = proximo_info["factor_campo"]
    
    avg_proyectado = avg_base * factor_picheo * factor_parque
    lambda_hits = avg_proyectado * 3.8
    prob_hit = round(min((1 - np.exp(-lambda_hits)) * 100, 94.0), 1)

    return {
        "avg_reciente": round(avg_reciente, 3),
        "avg_season": round(avg_season, 3),
        "avg_base": round(avg_base, 3),
        "factor_picheo": factor_picheo,
        "factor_parque": factor_parque,
        "avg_proyectado": round(avg_proyectado, 3),
        "lambda_hits": round(lambda_hits, 2),
        "prob_hit": prob_hit
    }

def generar_explicacion_cualitativa(df_15, res, proximo_info):
    puntos = []
    df_5 = df_15.head(5) if df_15 is not None and not df_15.empty else None
    
    if df_5 is not None and not df_5.empty and 'H' in df_5.columns:
        juegos_con_hit = (df_5['H'] > 0).sum()
        n_juegos = len(df_5)
        hits_ultimo_juego = df_5.iloc[0]['H']
        
        if juegos_con_hit >= 4:
            puntos.append(f"🔥 **Consistencia alta:** Conectó hit en {juegos_con_hit} de sus últimos {n_juegos} juegos.")
        elif juegos_con_hit <= 1:
            puntos.append(f"❄️ **Alta irregularidad:** Solo conectó hit en {juegos_con_hit} de los últimos {n_juegos} partidos.")
        else:
            puntos.append(f"📊 **Frecuencia moderada:** Conectó hit en {juegos_con_hit} de {n_juegos} partidos.")

        if hits_ultimo_juego > 0:
            puntos.append(f"⚡ **Inercia a favor:** Bateó {hits_ultimo_juego} hit(s) en su juego más reciente.")
        else:
            puntos.append("🛡️ **Inercia en contra:** Se fue en blanco en su último partido.")
    else:
        puntos.append("📊 **Rendimiento Regular:** Proyectado sobre la base del promedio general de la temporada.")

    if res['factor_picheo'] > 1.00:
        porc = int(round((res['factor_picheo'] - 1) * 100))
        puntos.append(f"🎯 **Duelo Favorable:** Enfrenta a **{proximo_info['pitcher_nombre']}** ({proximo_info['perfil_pitcher']}), incrementando su expectativa un **+{porc}%**.")
    elif res['factor_picheo'] < 1.00:
        porc = int(round((1 - res['factor_picheo']) * 100))
        puntos.append(f"🛡️ **Enfrentamiento Exigente:** **{proximo_info['pitcher_nombre']}** ({proximo_info['perfil_pitcher']}) penaliza la expectativa en un **-{porc}%**.")
    else:
        puntos.append(f"⚾ **Escenario Neutral:** Enfrentamiento contra **{proximo_info['pitcher_nombre']}** dentro del estándar.")
        
    if res['factor_parque'] > 1.00:
        porc = int(round((res['factor_parque'] - 1) * 100))
        puntos.append(f"🏟️ **Ventaja de Parque:** **{proximo_info['estadio']}** favorece a los bateadores en un **+{porc}%**.")
    elif res['factor_parque'] < 1.00:
        porc = int(round((1 - res['factor_parque']) * 100))
        puntos.append(f"🏟️ **Estadio para Lanzadores:** **{proximo_info['estadio']}** reduce la expectativa de imparables en un **-{porc}%**.")

    if res['prob_hit'] >= 72.0:
        conclusion = f"💡 **Conclusión:** Se proyecta un alto **{res['prob_hit']}%** de probabilidad de conectar al menos 1 hit."
    elif res['prob_hit'] >= 60.0:
        conclusion = f"💡 **Conclusión:** Sólido **{res['prob_hit']}%**, representando una opción con probabilidad favorable."
    else:
        conclusion = f"💡 **Conclusión:** Expectativa moderada/baja (**{res['prob_hit']}%**) debido a las condiciones del duelo."
        
    return puntos, conclusion

# ==========================================
# DESPLIEGUE EN INTERFAZ DE STREAMLIT
# ==========================================

directorio = obtener_directorio_jugadores_activos()
opciones = list(directorio.keys())

jugador_sel = st.sidebar.selectbox("Selecciona Jugador a Analizar:", opciones)

if jugador_sel:
    nombre_solo = jugador_sel.split(' (')[0]
    player_data = directorio[jugador_sel]
    p_id = player_data["id"]
    bat_side = player_data["bat_side"]
    
    with st.spinner("Extrayendo estadísticas e información del próximo partido..."):
        df_15, pos_lineup_detectada, es_previo = obtener_ultimos_juegos_detallados(p_id)
        stats_season = obtener_stats_temporada(p_id)
        proximo_info = auto_detectar_proximo_partido(p_id, bat_side)
        res = calcular_probabilidad_y_diagnostico(df_15, stats_season, proximo_info)
        
    st.subheader(f"⚾ {nombre_solo}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 Probabilidad de Hit", f"{res['prob_hit']}%")
    c2.metric("AVG Proyectado", f"{res['avg_proyectado']:.3f}")
    c3.metric("AVG Reciente (Racha)", f"{res['avg_reciente']:.3f}")
    c4.metric("AVG Temporada", f"{res['avg_season']:.3f}")
    
    st.markdown("---")
    
    # JUSTIFICACIÓN CUALITATIVA
    st.subheader(f"🧠 Justificación del resultado ({res['prob_hit']}% de probabilidad)")
    puntos_explicativos, conclusion_final = generar_explicacion_cualitativa(df_15, res, proximo_info)
    
    for p in puntos_explicativos:
        st.markdown(f"* {p}")
        
    st.info(conclusion_final)
    
    # --------------------------------------------------
    # NUEVAS VISUALIZACIONES GRÁFICAS (Plotly & Altair)
    # --------------------------------------------------
    st.markdown("---")
    st.subheader("📈 Visualizaciones Sabermétricas Avanzadas")
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("##### 📉 Tendencia de AVG (Últimos Juegos)")
        if df_15 is not None and not df_15.empty:
            # Ordenamos cronológicamente para el gráfico de líneas (de más antiguo a más reciente)
            df_chart = df_15.iloc[::-1].copy()
            
            fig_trend = px.line(
                df_chart, 
                x='Fecha', 
                y='AVG_Movil', 
                markers=True,
                labels={'AVG_Movil': 'Promedio Móvil Acumulado', 'Fecha': 'Fecha del Juego'},
                title="Evolución del Promedio Reciente"
            )
            fig_trend.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=300)
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("No hay suficientes datos gráficos disponibles.")

    with col_g2:
        st.markdown("##### 📊 Impacto de Factores en la Proyección")
        # Preparamos dataset para gráfico de barras de factores (Verde si > 1.0, Rojo si < 1.0)
        factores_data = pd.DataFrame({
            'Factor': ['Factor Parque', 'Factor Picheo', 'Inercia Reciente'],
            'Impacto (%)': [
                round((res['factor_parque'] - 1.0) * 100, 1),
                round((res['factor_picheo'] - 1.0) * 100, 1),
                round((res['avg_reciente'] - res['avg_season']) * 100, 1)
            ]
        })
        factores_data['Direccion'] = factores_data['Impacto (%)'].apply(lambda x: 'Positivo' if x >= 0 else 'Negativo')
        
        chart_factors = alt.Chart(factores_data).mark_bar().encode(
            x=alt.X('Impacto (%):Q', title='Impacto Neto (%)'),
            y=alt.Y('Factor:N', sort='-x', title=''),
            color=alt.Color('Direccion:N', scale=alt.Scale(domain=['Positivo', 'Negativo'], range=['#2ca02c', '#d62728']), legend=None)
        ).properties(height=260)
        
        st.altair_chart(chart_factors, use_container_width=True)

    # FICHA TÉCNICA
    st.markdown("---")
    st.markdown("📌 **Ficha Técnica Extraída Automáticamente:**")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"* **Próximo Rival:** {proximo_info['rival']} ({proximo_info['condicion']})")
        st.markdown(f"* **Fecha del Partido:** {proximo_info['fecha'][:10]}")
    with col_b:
        st.markdown(f"* **Estadio:** {proximo_info['estadio']}")
        st.markdown(f"* **Factor de Parque:** {proximo_info['desc_estadio']}")
    with col_c:
        st.markdown(f"* **Abridor Rival:** {proximo_info['pitcher_nombre']} ({proximo_info['pitcher_mano']}HP)")
        st.markdown(f"* **Ajuste de Picheo:** {proximo_info['perfil_pitcher']} (ERA: {proximo_info['pitcher_era']})")
        
    st.caption(f"🏏 **Alineación Estimada:** {pos_lineup_detectada} (~3.8 turnos al bate proyectados). Batea a la: **{bat_side}**.")
    
    # EXPLICACIÓN MATEMÁTICA
    with st.expander("🧮 Ver Desglose de Fórmulas Matemáticas"):
        st.markdown(f"""
        1. **Promedio Ponderado Base (AVG base):**  
            $$40\% \\cdot \\text{{Racha}} ({res['avg_reciente']:.3f}) + 60\% \\cdot \\text{{Temporada}} ({res['avg_season']:.3f}) = {res['avg_base']:.3f}$$
        
        2. **Ajustes por Entorno (AVG proyectado):**  
            $$\\text{{Base}} ({res['avg_base']:.3f}) \\times \\text{{Picheo}} ({res['factor_picheo']:.2f}) \\times \\text{{Parque}} ({res['factor_parque']:.2f}) = {res['avg_proyectado']:.3f}$$
        
        3. **Distribución de Poisson:**  
            $$\\lambda = \\text{{AVG}}_{{\\text{{proyectado}}}} \\times 3.8 \\text{{ AB}} = {res['lambda_hits']:.2f} \\text{{ hits esperados}}$$
            $$P(X \\ge 1) = 1 - e^{{-\\lambda}} = \\mathbf{{{res['prob_hit']}\\%}}$$
        """)

    st.markdown("---")
    
    # TABLA DE LOS ÚLTIMOS PARTIDOS
    df_5_tabla = df_15.head(5) if df_15 is not None else None
    if df_5_tabla is not None and not df_5_tabla.empty:
        if es_previo:
            st.warning("⚠️ Sin partidos en la temporada actual. Mostrando historial de la temporada anterior.")
        st.markdown("##### 📊 Últimos 5 Partidos Registrados")
        # Removemos las columnas auxiliares de cálculo para mostrar limpia la tabla al usuario
        cols_mostrar = [c for c in df_5_tabla.columns if c not in ['AVG_Juego', 'AVG_Movil']]
        st.dataframe(df_5_tabla[cols_mostrar], use_container_width=True)
    else:
        st.warning(f"⚠️ El jugador no registra partidos oficiales recientes. Proyección basada en promedio general ({stats_season['avg_season']:.3f}).")
