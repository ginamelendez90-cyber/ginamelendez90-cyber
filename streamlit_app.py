import streamlit as st
import statsapi
import math
from datetime import datetime

st.set_page_config(
    page_title="Analizador Avanzado de MLB",
    page_icon="⚾",
    layout="wide"
)

CURRENT_YEAR = datetime.now().year

# -----------------------------------------------------------------------------
# FUNCIONES OPTIMIZADAS CON CACHÉ DE STREAMLIT
# -----------------------------------------------------------------------------

@st.cache_data(ttl=1800)
def obtener_partidos(fecha_str):
    """Obtiene el calendario de partidos para una fecha."""
    try:
        return statsapi.schedule(date=fecha_str)
    except Exception as e:
        st.error(f"Error cargando calendario: {e}")
        return []

@st.cache_data(ttl=1800)
def obtener_abridores_probables(game_pk):
    """Extrae abridores probables de un partido."""
    try:
        g_data = statsapi.get("game", {"gamePk": game_pk})
        probables = g_data.get('gameData', {}).get('probablePitchers', {})
        return {
            'away_id': probables.get('away', {}).get('id'),
            'away_name': probables.get('away', {}).get('fullName', 'Por determinar'),
            'home_id': probables.get('home', {}).get('id'),
            'home_name': probables.get('home', {}).get('fullName', 'Por determinar')
        }
    except Exception:
        return {'away_id': None, 'away_name': 'Desconocido', 'home_id': None, 'home_name': 'Desconocido'}

@st.cache_data(ttl=1800)
def obtener_racha_7dias(player_id, season):
    """Consulta la racha en los últimos 7 días."""
    try:
        data = statsapi.get("people", {
            "personIds": player_id,
            "hydrate": f"stats(group=[hitting],type=lastXDays,limit=7,season={season})"
        })
        if data and 'people' in data:
            stats = data['people'][0].get('stats', [])
            for st_group in stats:
                splits = st_group.get('splits', [])
                if splits:
                    s = splits[0].get('stat', {})
                    return {
                        'avg': s.get('avg', '.000'),
                        'hits': s.get('hits', 0),
                        'gp': s.get('gamesPlayed', 0)
                    }
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
def obtener_bvp(batter_id, pitcher_id):
    """Obtiene el historial directo BvP."""
    if not batter_id or not pitcher_id:
        return None
    try:
        data = statsapi.get("stats", {
            "stats": "vsPlayer",
            "group": "hitting",
            "personId": batter_id,
            "opposingPlayerId": pitcher_id
        })
        if data and 'stats' in data and data['stats']:
            splits = data['stats'][0].get('splits', [])
            if splits:
                s = splits[0].get('stat', {})
                return {
                    'ab': s.get('atBats', 0),
                    'avg': s.get('avg', '.000'),
                    'hits': s.get('hits', 0)
                }
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
def obtener_roster_equipo(team_id):
    """Obtiene el roster del equipo de forma segura."""
    try:
        roster_raw = statsapi.roster(team_id)
        # Parseo alternativo directo si se requiere estructura limpia
        roster_data = statsapi.get("team_roster", {"teamId": team_id})
        return roster_data.get('roster', []) if roster_data else []
    except Exception:
        return []

def calcular_probabilidad_poisson_hits(avg_season, avg_7d=None, avg_bvp=None, ab_bvp=0, est_ab=3.8):
    try:
        avg_s = float(avg_season) if avg_season else 0.0
    except ValueError:
        avg_s = 0.0

    try:
        avg_7 = float(avg_7d) if avg_7d is not None else None
    except (ValueError, TypeError):
        avg_7 = None

    try:
        avg_b = float(avg_bvp) if avg_bvp is not None else None
    except (ValueError, TypeError):
        avg_b = None

    values, weights = [], []

    if avg_s > 0:
        values.append(avg_s)
        weights.append(0.50 if avg_7 is not None else 0.80)

    if avg_7 is not None and avg_7 >= 0:
        values.append(avg_7)
        weights.append(0.35)

    if avg_b is not None and ab_bvp >= 3:
        values.append(avg_b)
        weights.append(0.15 if ab_bvp < 8 else 0.25)

    if not values:
        return 0.0, 0.0, 0

    total_weight = sum(weights)
    avg_ponderado = sum(v * w for v, w in zip(values, weights)) / total_weight

    hits_1000 = int(round(avg_ponderado * 1000))
    lam = avg_ponderado * est_ab
    prob_hit = (1 - math.exp(-lam)) * 100

    return round(avg_ponderado, 3), round(prob_hit, 1), hits_1000

# -----------------------------------------------------------------------------
# INTERFAZ DE STREAMLIT
# -----------------------------------------------------------------------------

st.title("⚾ Analizador y Predictor MLB (Poisson + BvP)")

st.sidebar.header("Opciones")
opcion = st.sidebar.selectbox("Selecciona una sección:", ["Partidos del Día & Proyección", "Buscar Jugador"])

if opcion == "Partidos del Día & Proyección":
    date_to_check = st.date_input("Selecciona fecha:", datetime.now())
    formatted_date = date_to_check.strftime("%m/%d/%Y")
    
    with st.spinner("Cargando calendario de encuentros..."):
        schedule = obtener_partidos(formatted_date)
    
    if schedule:
        # Usamos un selector directo en lugar de botones dentro de un for
        opciones_juegos = {
            f"{g['away_name']} vs {g['home_name']} ({g.get('status', 'Programado')})": g 
            for g in schedule
        }
        
        juego_seleccionado_str = st.selectbox("Selecciona el partido a analizar:", list(opciones_juegos.keys()))
        game = opciones_juegos[juego_seleccionado_str]
        game_pk = game.get('game_id')
        
        if game_pk:
            st.divider()
            abridores = obtener_abridores_probables(game_pk)
            
            st.subheader("🥎 Lanzadores Abridores Probables")
            c1, c2 = st.columns(2)
            c1.info(f"**Visitante:** {abridores['away_name']}")
            c2.info(f"**Local:** {abridores['home_name']}")
            
            away_id = game.get('away_id')
            home_id = game.get('home_id')
            
            col_away, col_home = st.columns(2)
            
            # --- EQUIPO VISITANTE ---
            with col_away:
                st.markdown(f"### ✈️ {game['away_name']}")
                roster_away = obtener_roster_equipo(away_id) if away_id else []
                
                if roster_away:
                    count = 0
                    for m in roster_away:
                        pos = m.get('position', {}).get('abbreviation', '')
                        if pos == 'P': continue
                        if count >= 5: break  # Límite a los primeros 5 bateadores
                        
                        pid = m.get('person', {}).get('id')
                        pname = m.get('person', {}).get('fullName')
                        
                        p_raw = statsapi.get("people", {"personIds": pid, "hydrate": f"stats(group=hitting,type=season,season={CURRENT_YEAR})"})
                        splits = p_raw.get('people', [{}])[0].get('stats', [{}])[0].get('splits', []) if p_raw else []
                        
                        if splits:
                            s = splits[0].get('stat', {})
                            avg_season = s.get('avg', '.000')
                            
                            r7 = obtener_racha_7dias(pid, CURRENT_YEAR)
                            avg_7d = r7['avg'] if (r7 and r7['gp'] > 0) else None
                            
                            avg_bvp, ab_bvp = None, 0
                            if abridores['home_id']:
                                bvp = obtener_bvp(pid, abridores['home_id'])
                                if bvp and bvp['ab'] > 0:
                                    avg_bvp, ab_bvp = bvp['avg'], bvp['ab']
                            
                            avg_pond, prob_hit, hits_1000 = calcular_probabilidad_poisson_hits(
                                avg_season, avg_7d, avg_bvp, ab_bvp
                            )
                            
                            st.markdown(f"**👤 {pname}** ({pos})")
                            st.write(f"- Temp: `{avg_season}` | 7D: `{avg_7d or 'N/A'}` | BvP: `{avg_bvp or 'N/A'}`")
                            st.write(f"- Proyección: **{hits_1000} Hits** en 1,000 AB")
                            st.metric("Probabilidad +0.5 Hits", f"{prob_hit}%")
                            st.progress(min(int(prob_hit), 100))
                            st.divider()
                            count += 1
                else:
                    st.warning("No se pudo cargar el roster del equipo visitante.")

            # --- EQUIPO LOCAL ---
            with col_home:
                st.markdown(f"### 🏠 {game['home_name']}")
                roster_home = obtener_roster_equipo(home_id) if home_id else []
                
                if roster_home:
                    count = 0
                    for m in roster_home:
                        pos = m.get('position', {}).get('abbreviation', '')
                        if pos == 'P': continue
                        if count >= 5: break
                        
                        pid = m.get('person', {}).get('id')
                        pname = m.get('person', {}).get('fullName')
                        
                        p_raw = statsapi.get("people", {"personIds": pid, "hydrate": f"stats(group=hitting,type=season,season={CURRENT_YEAR})"})
                        splits = p_raw.get('people', [{}])[0].get('stats', [{}])[0].get('splits', []) if p_raw else []
                        
                        if splits:
                            s = splits[0].get('stat', {})
                            avg_season = s.get('avg', '.000')
                            
                            r7 = obtener_racha_7dias(pid, CURRENT_YEAR)
                            avg_7d = r7['avg'] if (r7 and r7['gp'] > 0) else None
                            
                            avg_bvp, ab_bvp = None, 0
                            if abridores['away_id']:
                                bvp = obtener_bvp(pid, abridores['away_id'])
                                if bvp and bvp['ab'] > 0:
                                    avg_bvp, ab_bvp = bvp['avg'], bvp['ab']
                            
                            avg_pond, prob_hit, hits_1000 = calcular_probabilidad_poisson_hits(
                                avg_season, avg_7d, avg_bvp, ab_bvp
                            )
                            
                            st.markdown(f"**👤 {pname}** ({pos})")
                            st.write(f"- Temp: `{avg_season}` | 7D: `{avg_7d or 'N/A'}` | BvP: `{avg_bvp or 'N/A'}`")
                            st.write(f"- Proyección: **{hits_1000} Hits** en 1,000 AB")
                            st.metric("Probabilidad +0.5 Hits", f"{prob_hit}%")
                            st.progress(min(int(prob_hit), 100))
                            st.divider()
                            count += 1
                else:
                    st.warning("No se pudo cargar el roster del equipo local.")
    else:
        st.info("No hay partidos programados o registrados para esta fecha.")

elif opcion == "Buscar Jugador":
    st.header("Buscador Directo")
    player_name = st.text_input("Jugador:", "Shohei Ohtani")
    if player_name:
        res = statsapi.lookup_player(player_name)
        if res:
            st.json(res[0])
        else:
            st.warning("Jugador no encontrado.")
