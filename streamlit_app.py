import streamlit as st
import statsapi  # Importa la librería de la API de MLB

# Configuración de la página
st.set_page_config(
    page_title="Analizador de MLB",
    page_icon="⚾",
    layout="wide"
)

st.title("⚾ Analizador de Estadísticas de la MLB")
st.markdown("Bienvenido a tu panel de control de béisbol impulsado por **Streamlit** y `MLB-StatsAPI`.")

# Barra lateral para navegación
st.sidebar.header("Opciones de Consulta")
opcion = st.sidebar.selectbox(
    "Selecciona una sección:",
    ["Equipos de la MLB", "Buscar Jugador", "Partidos del Día"]
)

if opcion == "Equipos de la MLB":
    st.header("Información de Equipos")
    
    # Obtener la lista de equipos de la MLB
    teams = statsapi.get_teams()
    
    team_names = [team['name'] for team in teams['teams']]
    selected_team_name = st.selectbox("Selecciona un equipo:", team_names)
    
    # Buscar el ID del equipo seleccionado
    selected_team = next(t for t in teams['teams'] if t['name'] == selected_team_name)
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
        roster = statsapi.roster(team_id)
        # El roster devuelto suele ser texto plano formateado, podemos mostrarlo o procesarlo
        st.text(roster)

elif opcion == "Buscar Jugador":
    st.header("Buscador de Jugadores")
    player_name = st.text_input("Ingresa el nombre del jugador (ej. Shohei Ohtani):", "Shohei Ohtani")
    
    if player_name:
        players = statsapi.lookup_player(player_name)
        if players:
            player = players[0]
            player_id = player['id']
            
            st.success(f"¡Jugador encontrado: {player['fullName']}!")
            
            col1, col2 = st.sidebar, st.empty() # Estructura visual
            st.write(f"**Posición:** {player.get('primaryPosition', {}).get('name', 'N/A')}")
            st.write(f"**Edad:** {player.get('currentAge', 'N/A')}")
            st.write(f"**Debut en MLB:** {player.get('mlbDebutDate', 'N/A')}")
            
            # Obtener estadísticas de bateo o pitcheo si están disponibles
            st.subheader("Estadísticas de la Trayectoria")
            try:
                stats = statsapi.player_stat_data(player_id, group="hitting", type="career")
                st.json(stats)
            except Exception:
                st.info("No se pudieron cargar estadísticas detalladas para este jugador.")
        else:
            st.warning("No se encontró ningún jugador con ese nombre.")

elif opcion == "Partidos del Día":
    st.header("Marcadores y Partidos")
    date_to_check = st.date_input("Selecciona una fecha:")
    
    # Formatear la fecha a MM/DD/YYYY que usa la API
    formatted_date = date_to_check.strftime("%m/%d/%Y")
    
    schedule = statsapi.schedule(date=formatted_date)
    
    if schedule:
        for game in schedule:
            with st.expander(f"{game['away_name']} ({game['away_score']}) vs {game['home_name']} ({game['home_score']}) - {game['status']}:"):
                st.write(f"**Estadio:** {game['venue']}")
                st.write(f"**Estado del juego:** {game['detailed_state']}")
    else:
        st.info("No hay partidos programados para esta fecha.")
