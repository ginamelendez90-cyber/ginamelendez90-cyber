def calcular_probabilidad_poisson_hits(avg_season, avg_7d=None, avg_bvp=None, ab_bvp=0, est_ab=3.8):
    """Calcula la probabilidad de +0.5 Hits y proyecta el total de hits en 1,000 turnos al bat."""
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

    values = []
    weights = []

    if avg_s > 0:
        values.append(avg_s)
        weights.append(0.50 if avg_7 is not None else 0.80)

    if avg_7 is not None and avg_7 >= 0:
        values.append(avg_7)
        weights.append(0.35)

    if avg_b is not None and ab_bvp >= 3:
        values.append(avg_b)
        w_bvp = 0.15 if ab_bvp < 8 else 0.25
        weights.append(w_bvp)

    if not values:
        return 0.0, 0.0, 0

    total_weight = sum(weights)
    avg_ponderado = sum(v * w for v, w in zip(values, weights)) / total_weight

    # Lógica de 1,000 Turnos al Bat (AB)
    hits_por_mil = int(round(avg_ponderado * 1000))

    # Lambda = Hits esperados en el juego actual
    lam = avg_ponderado * est_ab
    prob_hit = (1 - math.exp(-lam)) * 100

    return round(avg_ponderado, 3), round(prob_hit, 1), hits_por_mil
