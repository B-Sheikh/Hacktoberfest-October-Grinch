"""Office domain helpers"""
from app import settings
from app.intelligence import physics as p

def area_residents(c, lat, lon, radius):
    return [dict(row) for row in c.execute('SELECT * FROM residents WHERE consent=1 ORDER BY name')
            if p.haversine((lat,lon),(row['lat'],row['lon']))*1000 <= radius]


def sms_message(alert, token):
    link=f'{settings.PUBLIC_BASE_URL}/report/{token}'
    return (alert['message']+' '+link) if alert['message'] else settings.TEXT['sms'].format(hazard=alert['hazard'],link=link)
