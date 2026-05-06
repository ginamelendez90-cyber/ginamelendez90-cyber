import os
from binance.client import Client
from dotenv import load_dotenv
import pandas as pd

# 1. Cargar credenciales de forma segura
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET_KEY')

# 2. Inicializar el cliente de Binance
client = Client(api_key, api_secret)

def obtener_datos_mercado(symbol='BTCUSDT', intervalo='1h', limite=100):
    """
    Descarga datos de velas japonesas directamente de Binance.
    """
    try:
        # Obtener klines (velas)
        klines = client.get_klines(symbol=symbol, interval=intervalo, limit=limite)
        
        # Estructurar en un DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'
        ])
        
        # Limpieza de datos
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].apply(pd.to_numeric)
        
        return df[['timestamp', 'open', 'high', 'low', 'close']]
    
    except Exception as e:
        print(f"Error de conexión: {e}")
        return None

# 3. Ejemplo de ejecución
datos = obtener_datos_mercado(symbol='BTCUSDT', intervalo=Client.KLINE_INTERVAL_15MINUTE)

if datos is not None:
    # Aquí puedes aplicar tu lógica de trading
    # Ejemplo: Calcular una Media Móvil Simple (SMA)
    datos['SMA_20'] = datos['close'].rolling(window=20).mean()
    
    ultimo_precio = datos['close'].iloc[-1]
    print(f"Conexión exitosa. Último precio de BTC: {ultimo_precio}")
    print(datos.tail())
