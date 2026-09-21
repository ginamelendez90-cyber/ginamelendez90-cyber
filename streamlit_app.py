import requests
import pandas as pd
import streamlit as st

# --- FUNCIÓN PARA OBTENER CUOTAS EN TIEMPO REAL ---
@st.cache_data(ttl=900)  # Caché de 15 minutos para no agotar las 500 peticiones gratuitas
def obtener_cuotas_mlb_api(api_key, region="us", markets="h2h,totals"):
    """
    Obtiene las cuotas en vivo de la MLB desde The Odds API.
    Markets:
      - 'h2h': Moneyline (Ganador del partido)
      - 'totals': Over/Under de carreras
    """
    if not api_key:
        return None

    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        'apiKey': api_key,
        'regions': region,        # us, eu, uk, au
        'markets': markets,       # h2h, totals, spreads
        'oddsFormat': 'decimal'   # decimal o american
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error en la API de Cuotas ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        st.error(f"Error de conexión con The Odds API: {e}")
        return None

def calcular_ev(prob_modelo_pct, cuota_decimal):
    """Calcula el Expected Value (EV) porcentual."""
    prob_decimal = prob_modelo_pct / 100.0
    ev = (prob_decimal * cuota_decimal) - 1
    return round(ev * 100, 2)

# --- CÓDIGO PARA AGREGAR EN TU INTERFAZ DE STREAMLIT ---

# 1. Agregar campo de API Key en la Barra Lateral
st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Conexión a Casas de Apuestas")
odds_api_key = st.sidebar.text_input("The Odds API Key:", type="password", help="Consíguela gratis en the-odds-api.com")

# 2. Pestaña de Análisis +EV (Agregar junto a las otras pestañas)
# tab_montecarlo, tab_lineup, tab_vivo, tab_ev = st.tabs([...])

def render_tab_ev(away_name, home_name, prob_away_mc, prob_home_mc, total_esperado_mc):
    st.header("💰 Detector de Apuestas de Valor (+EV)")
    st.markdown("Compara las probabilidades del modelo Monte Carlo contra las cuotas en tiempo real de las casas de apuestas.")

    cuotas_json = obtener_cuotas_mlb_api(odds_api_key) if odds_api_key else None
    
    # Si no hay API Key o falla la API, usar datos de prueba (Demo)
    if not cuotas_json:
        st.info("💡 **Modo Demo Activo**: Ingresa tu *Odds API Key* en el panel lateral para obtener cuotas en vivo. Mostrando datos de ejemplo:")
        cuotas_demo = [
            {
                "bookmaker": "Pinnacle",
                "away_odds": 2.15,
                "home_odds": 1.75,
                "total_line": 8.5,
                "over_odds": 1.95,
                "under_odds": 1.90
            },
            {
                "bookmaker": "DraftKings",
                "away_odds": 2.05,
                "home_odds": 1.80,
                "total_line": 8.5,
                "over_odds": 1.87,
                "under_odds": 1.95
            }
        ]
    else:
        # Extraer cuotas reales del JSON devuelto por la API
        cuotas_demo = []
        for juego in cuotas_json:
            # Coincidencia de nombres de equipos
            if away_name.lower() in juego.get('away_team', '').lower() or home_name.lower() in juego.get('home_team', '').lower():
                for bookmaker in juego.get('bookmakers', []):
                    b_name = bookmaker.get('title')
                    h2h_odds = {}
                    totals_odds = {}
                    
                    for market in bookmaker.get('markets', []):
                        if market.get('key') == 'h2h':
                            for outcome in market.get('outcomes', []):
                                if away_name.lower() in outcome.get('name', '').lower():
                                    h2h_odds['away'] = outcome.get('price')
                                else:
                                    h2h_odds['home'] = outcome.get('price')
                        elif market.get('key') == 'totals':
                            for outcome in market.get('outcomes', []):
                                totals_odds['line'] = outcome.get('point')
                                if outcome.get('name') == 'Over':
                                    totals_odds['over'] = outcome.get('price')
                                else:
                                    totals_odds['under'] = outcome.get('price')
                    
                    cuotas_demo.append({
                        "bookmaker": b_name,
                        "away_odds": h2h_odds.get('away', 1.0),
                        "home_odds": h2h_odds.get('home', 1.0),
                        "total_line": totals_odds.get('line', '-'),
                        "over_odds": totals_odds.get('over', 1.0),
                        "under_odds": totals_odds.get('under', 1.0)
                    })

    # PROCESAMIENTO Y MATRIZ +EV
    filas_ev = []
    for item in cuotas_demo:
        ev_away = calcular_ev(prob_away_mc, item['away_odds'])
        ev_home = calcular_ev(prob_home_mc, item['home_odds'])
        
        # Selección de recomendación
        rec_away = f"🚀 +EV ({ev_away:+.1f}%)" if ev_away > 2.0 else "❌ Sin Valor"
        rec_home = f"🚀 +EV ({ev_home:+.1f}%)" if ev_home > 2.0 else "❌ Sin Valor"

        filas_ev.append({
            "Casa de Apuestas": item['bookmaker'],
            f"Cuota {away_name}": item['away_odds'],
            f"EV {away_name}": f"{ev_away:+.2f}%",
            f"Diagnóstico {away_name}": rec_away,
            f"Cuota {home_name}": item['home_odds'],
            f"EV {home_name}": f"{ev_home:+.2f}%",
            f"Diagnóstico {home_name}": rec_home,
        })

    df_ev = pd.DataFrame(filas_ev)
    
    st.subheader("🎯 Oportunidades Ganador del Partido (Moneyline)")
    st.dataframe(df_ev, use_container_width=True, hide_index=True)

    # RECOMENDACIÓN DESTACADA
    max_ev_away = max([f['EV ' + away_name] for f in filas_ev]) if filas_ev else "0%"
    max_ev_home = max([f['EV ' + home_name] for f in filas_ev]) if filas_ev else "0%"

    c1, c2 = st.columns(2)
    c1.info(f"**Modelo:** Probabilidad {away_name} = **{prob_away_mc:.1f}%**\n\n**Máximo EV Disponible:** {max_ev_away}")
    c2.info(f"**Modelo:** Probabilidad {home_name} = **{prob_home_mc:.1f}%**\n\n**Máximo EV Disponible:** {max_ev_home}")
