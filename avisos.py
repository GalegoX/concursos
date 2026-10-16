"""
Avisos al celular por ntfy (https://ntfy.sh).

Cada persona tiene su propio canal: un nombre difícil de adivinar guardado
como secreto en GitHub. El celular, con la app ntfy suscripta a ese canal,
recibe la notificación al instante.

Prioridades: 4 suena y vibra; 3 es normal; 2 llega en silencio.
"""

import os

import requests

PRIORIDAD = {"fuerte": 4, "normal": 3, "suave": 2}
SERVIDOR = "https://ntfy.sh"


def canal(persona):
    return os.environ.get(persona["secreto_ntfy"], "").strip()


def enviar(persona, titulo, mensaje, prioridad=3, enlace=None, etiquetas=None,
           botones=None):
    """Devuelve (enviado, detalle). Nunca lanza: un aviso caído no frena el resto."""
    topic = canal(persona)
    if not topic:
        return False, "sin canal configurado"
    cuerpo = {
        "topic": topic,
        "title": titulo[:120],
        "message": mensaje[:3800],
        "priority": prioridad,
        "tags": etiquetas or [],
    }
    if enlace:
        cuerpo["click"] = enlace
    if botones:
        cuerpo["actions"] = [{"action": "view", "label": t[:40], "url": u, "clear": True}
                             for t, u in botones[:3]]
    try:
        r = requests.post(SERVIDOR, json=cuerpo, timeout=30)
        if r.status_code == 200:
            return True, "enviado"
        return False, f"ntfy respondió {r.status_code}: {r.text[:120]}"
    except requests.RequestException as e:
        return False, f"no se pudo conectar con ntfy ({type(e).__name__})"
