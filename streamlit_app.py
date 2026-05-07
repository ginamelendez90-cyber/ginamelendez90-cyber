import re

def analizar_completo(texto):
    bloques = re.split(r'ÚLTIMOS PARTIDOS:', texto)
    resumen = []

    for bloque in bloques:
        if not bloque.strip(): continue
        
        nombre = bloque.strip().split('\n')[0].strip().replace('.', '')
        # Extraer sets y estado G/P
        partidos = re.findall(r'(\d)\s+(\d)\s+([GP])', bloque)
        
        total_partidos = len(partidos)
        victorias = sum(1 for p in partidos if p[2] == 'G')
        
        juegos_por_partido = []
        for p in partidos:
            s1, s2 = int(p[0]), int(p[1])
            # Estimación de juegos: 1 set ganado suele promediar 9-10 juegos (ej. 6-3, 6-4)
            # Un 2-0 suele tener ~19 juegos, un 2-1 suele tener ~28 juegos.
            total_juegos = (s1 + s2) * 9.5 
            juegos_por_partido.append(total_juegos)
            
        avg_juegos = sum(juegos_por_partido) / total_partidos if total_partidos > 0 else 0
        
        resumen.append({
            "nombre": nombre,
            "win_rate": victorias / total_partidos,
            "avg_juegos": avg_juegos,
            "racha": f"{victorias}-{total_partidos - victorias}"
        })
    return resumen

def generar_pronostico(stats):
    j1, j2 = stats[0], stats[1]
    
    # 1. Ganador y Probabilidad
    ganador = j1 if j1['win_rate'] > j2['win_rate'] else j2
    prob = (max(j1['win_rate'], j2['win_rate']) / (j1['win_rate'] + j2['win_rate'])) * 100

    # 2. Marcador en Sets
    diff = abs(j1['win_rate'] - j2['win_rate'])
    sets = "2-1" if diff < 0.20 else "2-0"

    # 3. Puntos (Juegos) Esperados
    # Si se espera un 2-1, la línea sube. Si ambos son competitivos, sube.
    base_juegos = (j1['avg_juegos'] + j2['avg_juegos']) / 2
    if sets == "2-1":
        linea_juegos = base_juegos + 2.5
    else:
        linea_juegos = base_juegos - 1.5

    return {
        "ganador": ganador['nombre'],
        "prob": round(prob, 1),
        "sets": sets,
        "juegos_totales": round(linea_juegos, 1)
    }

# --- DATA CRUDA (Pega aquí tu información) ---
data = """
ÚLTIMOS PARTIDOS: BASILASHVILI N.
05.05.26 ROM Hijikata R. Basilashvili N. 0 2 G
04.05.26 ROM Moller E. Basilashvili N. 1 2 G
28.04.26 MAU Basilashvili N. Kopp S. 0 2 P
22.04.26 MAD Basilashvili N. Ofner S. 0 2 P
21.04.26 MAD Kypson P. Basilashvili N. 1 2 G

ÚLTIMOS PARTIDOS: MERIDA AGUILAR D.
05.05.26 ROM Merida Aguilar D. Barrios Vera T. 2 1 G
04.05.26 ROM Merida Aguilar D. McDonald M. 2 0 G
27.04.26 MAD Tsitsipas S. Merida Aguilar D. 2 0 P
25.04.26 MAD Merida Aguilar D. Moutet C. 2 0 G
23.04.26 MAD Trungelliti M. Merida Aguilar D. 1 2 G
"""

# Ejecución
stats = analizar_completo(data)
p = generar_pronostico(stats)

print(f"📊 PROBABLE GANADOR: {p['ganador']} ({p['prob']}%)")
print(f"🎾 MARCADOR DE SETS: {p['sets']}")
print(f"📈 TOTAL JUEGOS ESTIMADOS: {p['juegos_totales']}")
print(f"📉 LÍNEA RECOMENDADA: Over {p['juegos_totales'] - 1.5}")
