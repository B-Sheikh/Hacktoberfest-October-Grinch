"""Citizen domain helpers"""
import secrets

def token_alert(c, token):
    return c.execute('SELECT alert_id FROM recipients WHERE token=? UNION SELECT alert_id FROM public_links WHERE token=?',(token,token)).fetchone()


def public_link(c, alert_id):
    c.execute('INSERT OR IGNORE INTO public_links(alert_id,token) VALUES (?,?)',(alert_id,secrets.token_urlsafe(32)))
    token=c.execute('SELECT token FROM public_links WHERE alert_id=?',(alert_id,)).fetchone()['token']
    return f'/report/{token}'
