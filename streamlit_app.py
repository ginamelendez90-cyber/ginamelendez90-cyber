import streamlit as st
import statsapi  # Importa la librería de la API de MLB

# Configuración de la página
st.set_page_config(
    page_title="Analizador de MLB",
    page_icon="⚾",
    layout="wide"
)

st.title("⚾ Analizador y Predictor de Estadísticas de la MLB")
st.markdown("Panel avanzado con `MLB-StatsAPI` para evaluar rendimiento, hits, ponches y métricas clave de forma estable.")

# Barra lateral para navegación
st.sidebar.header("Opciones de Consulta")
opcion = st.sidebar.selectbox(
    "Selecciona una sección:",
    ["Equipos de la MLB", "Buscar Jugador", "Partidos del Día & Análisis"]
)

if opcion == "Equipos de la MLB":
    st.header("Información de Equipos")
    
    teams_data = statsapi.get("teams", {"sportId": 1})
    
    if teams_data and 'teams' in teams_data:
        teams = teams_data['teams']
        team_names = [team['name'] for team in teams]
        selected_team_name = st.selectbox("Selecciona un equipo:", team_names)
        
        selected_team = next(t for t in teams if t['name'] == selected_team_name)
        team_id = selected_team['id']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Detalles del Equipo")
            st.write(f"**Ciudad:** {selected_team.get('locationName', 'N/A')}")
            st.write(f"**Estadio:** {selected_team.get('venue', {}).get('name', 'N/A')}")
            st.write(f"**Liga:** {selected_team.get('league', {}).get('name', 'N/A')}")
            st.write(f"**División:** {selected_team.get('division', {}).get('name', 'N/A')}")
            st.write(f"**Año de Fundación:** {selected_team.get('firstYearOfPlay', 'N/A')}")

        with col2:
            st.subheader("Plantilla Actual (Roster)")
            try:
                roster = statsapi.roster(team_id)
                # st.code previene fallos de renderizado de React en cadenas largas
                st.code(str(roster), language="text")
            except Exception:
                st.info("No se pudo cargar el roster de este equipo.")
    else:
        st.error("No se pudieron cargar los equipos de la MLB.")

elif opcion == "Buscar Jugador":
    st.header("Buscador de Jugadores")
    player_name = st.text_input("Ingresa el nombre del jugador (ej. Shohei Ohtani):", "Shohei Ohtani")
    
    if player_name:
        players = statsapi.lookup_player(player_name)
        if players:
            player = players[0]
            player_id = player['id']
            
            st.success(f"¡Jugador encontrado: {player['fullName']}!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Posición:** {player.get('primaryPosition', {}).get('name', 'N/A')}")
                st.write(f"**Edad:** {player.get('currentAge', 'N/A')}")
                st.write(f"**Debut en MLB:** {player.get('mlbDebutDate', 'N/A')}")
            
            with col2:
                st.subheader("Métricas de Rendimiento (Temporada)")
                try:
                    hitting_stats = statsapi.player_stat_data(player_id, group="hitting", type="season")
                    if hitting_stats and 'stats' in hitting_stats[0]:
                        stats_data = hitting_stats[0]['stats']
                        st.metric(label="Promedio de Bateo (AVG)", value=stats_data.get('avg', '.000'))
                        st.metric(label="Hits Conectados", value=stats_data.get('hits', 0))
                        st.metric(label="Ponches (SO)", value=stats_data.get('strikeOuts', 0))
                    else:
                        st.info("Estadísticas de bateo no disponibles para este año.")
                except Exception:
                    st.info("Este jugador puede ser lanzador o no tiene registros activos este año.")
        else:
            st.warning("No se encontró ningún jugador con ese nombre.")

elif opcion == "Partidos del Día & Análisis":
    st.header("📅 Partidos y Análisis de Expectativas")
    date_to_check = st.date_input("Selecciona una fecha:")
    
    formatted_date = date_to_check.strftime("%m/%d/%Y")
    schedule = statsapi.schedule(date=formatted_date)
    
    if schedule:
        st.write(f"Se encontraron **{len(schedule)}** encuentros para esta fecha.")
        
        for game in schedule:
            away_name = game.get('away_name', 'Visitante')
            away_score = game.get('away_score', 0)
            home_name = game.get('home_name', 'Local')
            home_score = game.get('home_score', 0)
            status = game.get('status', 'Programado')
            game_pk = game.get('game_id')
            
            with st.expander(f"⚾ {away_name} ({away_score}) vs {home_name} ({home_score}) | Estado: {status}"):
                venue_info = game.get('venue_name', game.get('venue', 'No disponible'))
                detailed_state = game.get('detailed_state', 'N/A')
                
                st.write(f"**Estadio:** {venue_info}")
                st.write(f"**Detalle del juego:** {detailed_state}")
                
                if game_pk and st.button(f"🔍 Ver Boxscore / Datos (ID: {game_pk})", key=f"btn_{game_pk}"):
                    try:
                        box = statsapi.boxscore(game_pk)
                        # Uso de st.code para renderizado seguro en el navegador
                        st.code(str(box), language="text")
                    except Exception as e:
                        st.warning("El boxscore detallado aún no está disponible para este partido o ya finalizó sin datos en caché.")
    else:
        st.info("No hay partidos programados para esta fecha.")
