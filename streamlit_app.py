import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

st.set_page_config(page_title="MLB Analyst - Análisis Cualitativo & L5 Garantizado", page_icon="⚾", layout="wide")

st.title("⚾ Analizador MLB: Probabilidad Explicada e Historial L5 Garantizado")
st.markdown("---")

@st.cache_data(ttl=86400)
def obtener_directorio_jugadores_activos():
    diccionario_jugadores = {}
    anio_actual = datetime.now().year
    try:
        equipos = statsapi.get('teams', {'sportId': 1, 'season': anio_actual}).get('teams', [])
        for equipo in equipos:
            team_id = equipo.get('id')
            roster = statsapi.get('team_roster', {'teamId': team_id, 'rosterType': 'active'}).get('roster', [])
            for p in roster:
                person = p.get('person', {})
                posicion = p.get('position', {}).get('abbreviation', '')
                if posicion != 'P' or person.get('fullName') == 'Shohei Ohtani':
                    nombre = person.get('fullName')
                    player_id = person.get('id')
                    equipo_nom = equipo.get('teamName', '')
                    if nombre and player_id:
                        diccionario_jugadores[f"{nombre} ({posicion} - {equipo_nom})"] = player_id
        return dict(sorted(diccionario_jugadores.items()))
    except Exception:
        return {"Shohei Ohtani (DH - Dodgers)": 660271, "Aaron Judge (OF - Yankees)": 592450}

def buscar_juego_por_fecha(player_id, fecha_str):
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
                                'date': fecha_str, 'opponent': f"vs {rival}",
                                'ab': b_stats.get('atBats', 0), 'h': b_stats.get('hits', 0),
                                'doubles': b_stats.get('doubles', 0), 'triples': b_stats.get('triples', 0),
                                'homeRuns': b_stats.get('homeRuns', 0), 'rbi': b_stats.get('rbi', 0),
                                'baseOnBalls': b_stats.get('baseOnBalls', 0), 'strikeOuts': b_stats.get('strikeOuts', 0)
                            }
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
def obtener_ultimos_5_juegos_garantizado(player_id):
    registros = []
    anio_actual = datetime.now().year
    
    # 1. BÚSQUEDA PROFUNDA: Revisa los últimos 4 años (Regular, Pretemporada 'S' y Postemporada 'P')
    for anio in range(anio_actual, anio_actual - 4, -1):
        # A) Intentar player_game_logs de hitting
        try:
            logs = statsapi.player_game_logs(player_id, group="hitting", season=anio)
            if isinstance(logs, list) and len(logs) > 0:
                for l in logs:
                    registros.append({
                        'date': l.get('date', ''),
                        'opponent': l.get('opponent', 'N/A'),
                        'ab': l.get('ab', l.get('atBats', 0)),
                        'h': l.get('h', l.get('hits', 0)),
                        'doubles': l.get('doubles', 0),
                        'triples': l.get('triples', 0),
                        'homeRuns': l.get('homeRuns', 0),
                        'rbi': l.get('rbi', 0),
                        'baseOnBalls': l.get('baseOnBalls', l.get('bb', 0)),
                        'strikeOuts': l.get('strikeOuts', l.get('so', 0))
                    })
                if len(registros) >= 5:
                    break
        except Exception:
            pass
            
        # B) Si no hay suficientes partidos en la temporada regular, escanear splits (Pretemporada 'S', Playoffs 'P')
        if len(registros) < 5:
            for game_type in ['S', 'P', 'R']:
                try:
                    params = {
                        'stats': 'gameLog',
                        'personId': player_id,
                        'group': 'hitting',
                        'season': anio,
                        'gameType': game_type
                    }
                    res = statsapi.get('stats', params)
                    splits = res.get('stats', [])[0].get('splits', []) if res.get('stats') else []
                    for s in splits:
                        stat = s.get('stat', {})
                        fecha = s.get('date', '')
                        opp = s.get('opponent', {}).get('name', 'N/A')
                        if stat and fecha and stat.get('atBats', 0) > 0:
                            registros.append({
                                'date': fecha,
                                'opponent': f"vs {opp}",
                                'ab': stat.get('atBats', 0),
                                'h': stat.get('hits', 0),
                                'doubles': stat.get('doubles', 0),
                                'triples': stat.get('triples', 0),
                                'homeRuns': stat.get('homeRuns', 0),
                                'rbi': stat.get('rbi', 0),
                                'baseOnBalls': stat.get('baseOnBalls', 0),
                                'strikeOuts': stat.get('strikeOuts', 0)
                            })
                    if len(registros) >= 5:
                        break
                except Exception:
                    pass
        if len(registros) >= 5:
            break

    df = pd.DataFrame(registros) if registros else pd.DataFrame()
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date', ascending=False)
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        df = df.drop_duplicates(subset=['date'])

    # 2. ESCÁNER DE RESPALDO DIARIO: Si aún no se completan 5 juegos, escanear boxscores por fecha
    fechas_existentes = set(df['date'].values) if not df.empty and 'date' in df.columns else set()
    dia_cursor = datetime.now()
    intentos = 0
    adicionales = []

    while (len(fechas_existentes) + len(adicionales)) < 5 and intentos < 30:
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

    # Formateo final para la tabla
    df = df.sort_values(by='date', ascending=False).reset_index(drop=True)
    df_5 = df.head(5).copy()

    columnas = {
        'date': 'Fecha', 'opponent': 'Rival', 'ab': 'AB', 'h': 'H',
        'doubles': '2B', 'triples': '3B', 'homeRuns': 'HR',
        'rbi': 'CI', 'baseOnBalls': 'BB', 'strikeOuts': 'K'
    }
    cols_presentes = [c for c in columnas.keys() if c in df_5.columns]
    df_final = df_5[cols_presentes].rename(columns=columnas)

    for col in ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']:
        if col in df_final.columns:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0).astype(int)

    return df_final

def calcular_probabilidad_y_diagnostico(df_5):
    total_ab = df_5['AB'].sum()
    total_h = df_5['H'].sum()
    juegos_con_hit = (df_5['H'] > 0).sum()
    n_juegos = len(df_5)

    if total_ab == 0:
        return {"prob_hit": 0.0, "diagnostico": "El jugador no registra turnos oficiales recientes."}

    avg_5 = total_h / total_ab
    pesos = np.array([0.35, 0.25, 0.20, 0.12, 0.08])[:n_juegos]
    pesos = pesos / pesos.sum()

    rates = np.where(df_5['AB'].values > 0, df_5['H'].values / df_5['AB'].values, 0)
    avg_ponderado = np.sum(rates * pesos)

    # Cálculo de Poisson
    lambda_hits = avg_ponderado * 3.8
    prob_hit = round(min((1 - np.exp(-lambda_hits)) * 100, 94.0), 1)

    # Evaluación de la narrativa cualitativa
    hit_ultimo_juego = df_5.iloc[0]['H'] > 0
    hits_ultimo_juego = df_5.iloc[0]['H']

    razones = []
    if juegos_con_hit >= 4:
        razones.append(f"**Consistencia alta:** Ha conectado hit en {juegos_con_hit} de sus últimos 5 juegos.")
    elif juegos_con_hit <= 1:
        razones.append(f"**Alta irregularidad:** Solo ha conectado hit en {juegos_con_hit} de los últimos 5 partidos.")
    else:
        razones.append(f"**Frecuencia moderada:** Marcó hit en {juegos_con_hit} de 5 partidos.")

    if hit_ultimo_juego:
        razones.append(f"**Inercia a favor:** Viene de batear {hits_ultimo_juego} hit(s) en su juego más reciente, lo que eleva el peso de su proyección.")
    else:
        razones.append("**Inercia en contra:** Se fue en blanco en su último partido, reduciendo su ponderación inmediata.")

    if avg_5 >= 0.300:
        razones.append(f"**Ritmo de contacto:** Su promedio reciente de **.{int(avg_5*1000):03d}** sostiene la expectativa de evitar el cero.")
    else:
        razones.append(f"**Contacto frío:** Mantiene un promedio comprimido de **.{int(avg_5*1000):03d}** en la muestra analizada.")

    diagnostico_texto = " ".join(razones)

    return {
        "avg_5": round(avg_5, 3),
        "prob_hit": prob_hit,
        "juegos_con_hit": f"{juegos_con_hit}/{n_juegos}",
        "total_h": total_h,
        "total_hr": df_5['HR'].sum(),
        "diagnostico": diagnostico_texto
    }

# INTERFAZ DE USUARIO
directorio = obtener_directorio_jugadores_activos()
opciones = list(directorio.keys())
predet = [o for o in opciones if "Ohtani" in o or "Judge" in o][:2]

seleccionados = st.sidebar.multiselect("Selecciona jugador:", options=opciones, default=predet if predet else opciones[:1])

if seleccionados:
    for etiqueta in seleccionados:
        pid = directorio[etiqueta]
        df_5 = obtener_ultimos_5_juegos_garantizado(pid)

        st.subheader(f"⚾ {etiqueta.split(' (')[0]}")

        if df_5 is not None and not df_5.empty:
            res = calcular_probabilidad_y_diagnostico(df_5)

            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                st.metric("🎯 Prob. Hit Próx. Juego", f"{res['prob_hit']}%")
            with c2:
                st.metric("Promedio L5", f"{res['avg_5']:.3f}")
            with c3:
                st.metric("Hits / HR en L5", f"{res['total_h']} H / {res['total_hr']} HR")

            # Explicación cualitativa en palabras
            st.info(f"**¿Por qué esta probabilidad?**\n\n{res['diagnostico']}")

            # TABLA GARANTIZADA DE LOS ÚLTIMOS 5 PARTIDOS
            st.dataframe(df_5, use_container_width=True)
            st.markdown("---")
        else:
            st.error("No se encontraron registros de turnos oficiales para este jugador en la búsqueda reciente.")
