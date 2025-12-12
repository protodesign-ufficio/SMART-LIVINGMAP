# ais_generator.py

import socket
import time
import math
from dataclasses import dataclass
from typing import Union, List, Optional
from pyais.encode import encode_dict

# ——— UDP Config ———
UDP_IP = "0.0.0.0"
UDP_PORT = 10110
_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_ais_sentence(sentence: str) -> None:
    """Invia una singola riga NMEA via UDP."""
    _sock.sendto((sentence + "\r\n").encode('ascii'), (UDP_IP, UDP_PORT))


# ——— “Struct” per i parametri ———
@dataclass
class PositionReportParams:
    mmsi: Union[int, str]
    latitude: float
    longitude: float
    speed: float = 0.0
    course: float = 360.0
    heading: int = 511
    # Usare preferibilmente `timestamp`, altrimenti `second` di default
    timestamp: Optional[int] = None
    second: int = 60
    talker_id: str = "AIVDM"
    radio_channel: str = "A"

@dataclass
class StaticVoyageParams:
    mmsi: Union[int, str]
    callsign: str
    name: str
    ship_type: int
    to_bow: int
    to_stern: int
    to_port: int
    to_starboard: int
    eta_month: int
    eta_day: int
    eta_hour: int
    eta_minute: int
    draft: float
    destination: str
    talker_id: str = "AIVDM"
    radio_channel: str = "A"


# ——— Funzioni di generazione ———
def generate_position_report(params: PositionReportParams) -> List[str]:
    """Genera i frammenti NMEA per un Position Report (Type 1)."""
    sec = params.timestamp if params.timestamp is not None else params.second
    data = {
        "type":    1,
        "mmsi":    params.mmsi,
        "lat":     params.latitude,
        "lon":     params.longitude,
        "speed":   params.speed,
        "course":  params.course,
        "heading": params.heading,
        "second":  sec
    }
    return encode_dict(data, talker_id=params.talker_id, radio_channel=params.radio_channel)


def generate_static_voyage_report(params: StaticVoyageParams) -> List[str]:
    """Genera i frammenti NMEA per un Static & Voyage Report (Type 5)."""
    data = {
        "type":         5,
        "mmsi":         params.mmsi,
        "callsign":     params.callsign,
        "name":         params.name,
        "ship_type":    params.ship_type,
        "to_bow":       params.to_bow,
        "to_stern":     params.to_stern,
        "to_port":      params.to_port,
        "to_starboard": params.to_starboard,
        "eta_month":    params.eta_month,
        "eta_day":      params.eta_day,
        "eta_hour":     params.eta_hour,
        "eta_minute":   params.eta_minute,
        "draught":      int(params.draft * 10),  # in decimetri
        "destination":  params.destination
    }
    return encode_dict(data, talker_id=params.talker_id, radio_channel=params.radio_channel)


# ——— Esempio: traiettoria circolare a velocità costante ———
if __name__ == "__main__":
    # Configurazione generica
    pos_cfg = PositionReportParams(
        mmsi=19261926, latitude=40.35, longitude=14.43,
        speed=15.0, course=0.0, heading=0, timestamp=None
    )
    stat_cfg = StaticVoyageParams(
        mmsi=19261926,
        callsign="CALLGAE", name="GAETA01", ship_type=70,
        to_bow=50, to_stern=20, to_port=10, to_starboard=10,
        eta_month=5, eta_day=15, eta_hour=18, eta_minute=30,
        draft=5.5, destination="NAPOLI"
    )

    # Traiettoria circolare: parametri
    SPEED_KNOTS = 15.0          # velocità desiderata in nodi
    RADIUS_M = 500.0            # raggio del cerchio in metri
    UPDATE_INTERVAL = 1.0       # intervallo tra report di posizione (s)

    # calcoli precomputati
    v_m_s = SPEED_KNOTS * 0.514444  # converti nodi -> m/s
    omega = v_m_s / RADIUS_M        # velocità angolare (rad/s)
    angle = 0.0

    center_lat = pos_cfg.latitude
    center_lon = pos_cfg.longitude
    center_lat_rad = math.radians(center_lat)
    R_earth = 6371000.0  # metri

    # invia una volta la static/voyage (non serve ripetere ogni secondo)
    try:
        for frag in generate_static_voyage_report(stat_cfg):
            print("STAT➔", frag)
            send_ais_sentence(frag)

        # loop principale: aggiorna la posizione seguendo il cerchio
        while True:
            # calcola nuova posizione usando offset (x east, y north)
            x = RADIUS_M * math.cos(angle)
            y = RADIUS_M * math.sin(angle)

            # delta lat/lon in gradi
            dlat = (y / R_earth) * (180.0 / math.pi)
            dlon = (x / (R_earth * math.cos(center_lat_rad))) * (180.0 / math.pi)

            new_lat = center_lat + dlat
            new_lon = center_lon + dlon

            # aggiorna campo nel struct e timestamp/second
            pos_cfg.latitude = new_lat
            pos_cfg.longitude = new_lon
            pos_cfg.speed = SPEED_KNOTS
            pos_cfg.course = (math.degrees(angle) + 90.0) % 360.0
            pos_cfg.heading = int(pos_cfg.course) if pos_cfg.course < 360 else 511
            pos_cfg.timestamp = int(time.time()) % 60

            # genera e invia frammenti NMEA
            for frag in generate_position_report(pos_cfg):
                print("POS ➔", frag)
                send_ais_sentence(frag)

            # incrementa angolo in base al dt
            angle += omega * UPDATE_INTERVAL
            # normalizza angolo
            if angle > 2 * math.pi:
                angle -= 2 * math.pi

            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        print('\nInterrotto dall\'utente')
    except Exception as e:
        print('Errore:', e)
    finally:
        try:
            _sock.close()
        except Exception:
            pass
