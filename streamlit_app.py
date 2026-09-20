import pandas as pd
import numpy as np
from datetime import timedelta

class AnalistaMLB:
    def __init__(self, url_repositorio):
        """
        Inicializa el analista con la URL raw del repositorio de GitHub.
        Ejemplo de URL: 'https://raw.githubusercontent.com/usuario/repo/main/mlb_stats_2026.csv'
        """
        self.url_repositorio = url_repositorio
        self.df = None

    def cargar_datos(self):
        """Extrae los datos actualizados del repositorio."""
        try:
            # Pandas lee directamente desde la URL Raw de GitHub
            self.df = pd.read_csv(self.url_repositorio)
            
            # Limpieza y estandarización básica de columnas
            self.df.columns = self.df.columns.str.lower().str.replace(' ', '_')
            
            # Asegurar formato de fecha si existe la columna
            if 'fecha' in self.df.columns:
                self.df['fecha'] = pd.to_datetime(self.df['fecha'])
                self.df = self.df.sort_values(by=['jugador', 'fecha'])
                
            print("✅ Datos extraídos y estructurados correctamente.")
            return self.df
            
        except Exception as e:
            print(f"❌ Error al extraer los datos: {e}")
            return None

    def calcular_racha_actual_hits(self, nombre_jugador):
        """
        Calcula la racha actual de juegos consecutivos conectando al menos 1 hit.
        """
        if self.df is None or self.df.empty:
            raise ValueError("Los datos no han sido cargados.")

        # Filtrar jugador y ordenar de más reciente a más antiguo
        df_jugador = self.df[self.df['jugador'] == nombre_jugador].sort_values(by='fecha', ascending=False)
        
        racha = 0
        for _, juego in df_jugador.iterrows():
            # Si el jugador tuvo turnos al bate (AB) y conectó hit (H)
            if juego.get('ab', 0) > 0:
                if juego.get('h', 0) > 0:
                    racha += 1
                else:
                    # La racha se rompe en el primer juego sin hits
                    break
                    
        return racha

    def identificar_jugadores_calientes(self, ultimos_n_juegos=7, min_turnos=15):
        """
        Devuelve un DataFrame con los jugadores de mejor rendimiento (AVG y OPS) 
        en sus últimos 'N' juegos para identificar rachas de desempeño.
        """
        if self.df is None or self.df.empty:
            raise ValueError("Los datos no han sido cargados.")

        # Obtener los últimos N juegos por jugador
        ultimos_juegos = self.df.groupby('jugador').tail(ultimos_n_juegos)
        
        # Agrupar estadísticas
        stats_recientes = ultimos_juegos.groupby('jugador').agg(
            juegos_jugados=('fecha', 'count'),
            ab_total=('ab', 'sum'),
            h_total=('h', 'sum'),
            bb_total=('bb', 'sum'),
            tb_total=('tb', 'sum') # Bases totales
        ).reset_index()

        # Filtrar por muestra mínima de turnos para evitar anomalías
        stats_recientes = stats_recientes[stats_recientes['ab_total'] >= min_turnos].copy()

        # Calcular métricas avanzadas (AVG, OBP, SLG, OPS)
        stats_recientes['avg_reciente'] = stats_recientes['h_total'] / stats_recientes['ab_total']
        
        # OBP = (H + BB) / (AB + BB) - Simplificado para el ejemplo
        stats_recientes['obp_reciente'] = (stats_recientes['h_total'] + stats_recientes['bb_total']) / \
                                          (stats_recientes['ab_total'] + stats_recientes['bb_total'])
                                          
        # SLG = TB / AB
        stats_recientes['slg_reciente'] = stats_recientes['tb_total'] / stats_recientes['ab_total']
        
        # OPS = OBP + SLG
        stats_recientes['ops_reciente'] = stats_recientes['obp_reciente'] + stats_recientes['slg_reciente']

        # Ordenar por OPS (mejor indicador de impacto ofensivo)
        top_jugadores = stats_recientes.sort_values(by='ops_reciente', ascending=False)
        
        return top_jugadores.round(3)

# ==========================================
# Ejecución del Script
# ==========================================
if __name__ == "__main__":
    # URL Raw del CSV en GitHub (reemplazar con el repositorio específico)
    GITHUB_RAW_URL = "https://raw.githubusercontent.com/tu_usuario/mlb_data/main/dataset_diario.csv"
    
    analista = AnalistaMLB(GITHUB_RAW_URL)
    datos = analista.cargar_datos()
    
    if datos is not None:
        # 1. Analizar racha de un jugador específico
        jugador_ejemplo = "Shohei Ohtani"
        racha = analista.calcular_racha_actual_hits(jugador_ejemplo)
        print(f"\n🔥 Racha actual de {jugador_ejemplo}: {racha} juegos consecutivos con hit.")
        
        # 2. Obtener el top de jugadores en los últimos 7 juegos
        top_momento = analista.identificar_jugadores_calientes(ultimos_n_juegos=7)
        print("\n📈 Top Jugadores de la última semana (Por OPS):")
        print(top_momento[['jugador', 'ab_total', 'avg_reciente', 'ops_reciente']].head(5))
