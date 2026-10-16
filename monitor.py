#!/usr/bin/env python3
"""
Monitor de concursos.

Lee las páginas de config.FUENTES, decide para quién sirve cada concurso
(reglas.py), avisa al celular lo nuevo (avisos.py) y guarda el resultado
en data/ para la página web.

    python monitor.py

Variables de entorno:
    NTFY_CRISTIAN, NTFY_BIANCA  canales de ntfy (secretos de GitHub)
    PRUEBA=true               manda además un aviso de prueba a cada uno
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import avisos
import config
import fuentes
import reglas

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
CARPETA = "data"
DATOS = os.path.join(CARPETA, "concursos.json")
REVISION = os.path.join(CARPETA, "revision.json")
ESTADO = os.path.join(CARPETA, "estado.json")

FALLAS_PARA_AVISAR = 3      # revisiones seguidas sin poder leer una fuente
MAX_AVISOS_SUELTOS = 4      # más que esto en una corrida va en un resumen
DIAS_VIGENCIA_SIN_FECHA = 45

ESTADO_VACIO = {"vistos": {}, "fuentes": {}, "bienvenida": {}, "recordados": {}}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return json.loads(json.dumps(defecto))


def escribir_json(ruta, datos, compacto=False):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        if compacto:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        f.write("\n")


def fecha(iso):
    try:
        return date.fromisoformat(iso[:10]) if iso else None
    except ValueError:
        return None


def ddmm(d):
    return d.strftime("%d/%m") if d else ""


def ventana_texto(it):
    d, h = fecha(it.get("desde")), fecha(it.get("hasta"))
    if d and h and d != h:
        return f"del {ddmm(d)} al {ddmm(h)}"
    if h:
        return f"hasta el {ddmm(h)}" if not d else f"el {ddmm(h)}"
    if d:
        return f"desde el {ddmm(d)}"
    return "sin fecha publicada"


def titulo_corto(it):
    t = it["titulo"]
    t = re.sub(r"^(llamado a |llamar a )?concurso( nodocente)?( abierto| cerrado( interno| general| por sede)?)?"
               r"\s*[-:–.]?\s*", "", t, flags=re.I).strip() or it["titulo"]
    if len(t) > 80:
        m = re.search(r"desempe\w+\s+(?:como\s+)?(?:en\s+)?(.+)", t, re.I)
        if m:
            t = m.group(1)
    fin = re.search(r"\s*\(([^()]{2,40})\)\s*$", t)
    if fin and fin.group(1).lower() in t[:fin.start()].lower():
        t = t[:fin.start()]
    t = t[0].upper() + t[1:] if t else t
    return t if len(t) <= 90 else t[:88].rstrip() + "…"


def lugar_texto(it):
    return ", ".join(it.get("ciudades") or []) or "ciudad sin leer"


# --------------------------------------------------------------------------
# Completar y clasificar
# --------------------------------------------------------------------------

def aplicar_resolucion(it):
    """Requisitos excluyentes y no excluyentes, desde el texto de la resolución."""
    req = reglas.requisitos_resolucion(it.get("resolucion_texto"))
    if not req:
        return
    it["req"] = req
    hay_lista = any(req[k] for k in ("excluyentes", "generales", "suman", "otros"))
    if it["ambito"] == "nodocente" and hay_lista:
        # La resolución manda: el título hace falta solo si es requisito excluyente.
        it["titulo_requerido"] = reglas.titulo_de_excluyentes(req["excluyentes"])


def completar(it, fuente, hoy):
    texto = it.get("texto") or it["titulo"]
    anio = it.pop("anio_ref", None) or (fecha(it.get("publicado")) or hoy).year
    resolucion = it.get("resolucion_texto") or ""
    if not it.get("instancia"):
        it["instancia"] = reglas.detectar_instancia(texto)
    if it["ambito"] == "nodocente":
        if not it.get("categoria"):
            it["categoria"] = reglas.detectar_categoria(texto)
        if not it.get("agrupamiento"):
            it["agrupamiento"] = reglas.detectar_agrupamiento(texto)
        if "titulo_requerido" not in it:
            # En la universidad lo define el agrupamiento, no el nombre del cargo.
            it["titulo_requerido"] = reglas.titulo_requerido(agrupamiento=it.get("agrupamiento"))[0]
    elif "titulo_requerido" not in it:
        it["titulo_requerido"] = reglas.titulo_requerido(
            cargo=it["titulo"], requisitos=it.get("requisitos", ""))[0]
    if not it.get("ciudades"):
        it["ciudades"] = (reglas.detectar_ciudades(texto)
                          or ([fuente["ciudad_por_defecto"]] if fuente.get("ciudad_por_defecto") else []))
    if not it.get("desde") and not it.get("hasta"):
        d, h = reglas.fechas_inscripcion(texto, anio)
        if not (d or h) and resolucion:
            d, h = reglas.fechas_inscripcion(resolucion, anio)
        it["desde"], it["hasta"] = (d.isoformat() if d else None), (h.isoformat() if h else None)
    if resolucion:
        if not it.get("ciudades"):
            it["ciudades"] = reglas.detectar_ciudades(resolucion[:3000])
        if it["ambito"] == "nodocente" and not it.get("categoria"):
            it["categoria"] = reglas.detectar_categoria(resolucion[:3000])
        aplicar_resolucion(it)
    estado = reglas.estado_inscripcion(fecha(it.get("desde")), fecha(it.get("hasta")), hoy)
    fin = reglas.normalizar(it.get("estado_fuente") or "")
    if re.search(r"finaliz|desiert", fin) and estado != "por_abrir":
        estado = "cerrada"
    it["inscripcion"] = estado
    it["titulo_corto"] = titulo_corto(it)


def evaluar_todos(it, personas, locales):
    it["para"] = {}
    for p in personas:
        ev = reglas.evaluar(it, p, locales)
        if ev:
            it["para"][p["id"]] = ev


def vigente(it, hoy):
    """Abierta, por abrir, o sin fechas pero publicada hace poco."""
    if it["inscripcion"] in ("abierta", "por_abrir"):
        return True
    if it["inscripcion"] == "sin_fecha":
        ref = fecha(it.get("publicado")) or fecha(it.get("visto_desde")) or hoy
        return (hoy - ref).days <= DIAS_VIGENCIA_SIN_FECHA
    return False


def avisable(ev):
    return ev and ev["nivel"] in avisos.PRIORIDAD


# --------------------------------------------------------------------------
# Mensajes
# --------------------------------------------------------------------------

def nombre_fuente(it):
    f = next((x for x in config.FUENTES if x["id"] == it["fuente"]), None)
    return f["nombre"] if f else it["fuente"]


def mensaje_concurso(it, ev):
    cat = f" (cat. {it['categoria']})" if it.get("categoria") and it["ambito"] == "nodocente" else ""
    titulo = it["titulo_corto"] + cat
    detalle = it.get("detalle") if it.get("detalle") and len(it["detalle"]) < 80 else ""
    lugar = "" if detalle and lugar_texto(it) in detalle else f" {lugar_texto(it)}."
    lineas = [f"{ev['motivo']}. {nombre_fuente(it)}" + (f", {detalle}" if detalle else "")
              + "." + lugar,
              f"Inscripción: {ventana_texto(it)}."]
    lineas += ev.get("notas", [])[:2]
    horario = (it.get("req") or {}).get("horario")
    if horario:
        lineas.append(f"Horario: {horario}.")
    return titulo, "\n".join(lineas)


def linea_resumen(it, ev=None):
    cat = f"Cat. {it['categoria']}: " if it.get("categoria") and it["ambito"] == "nodocente" else ""
    linea = f"• {cat}{it['titulo_corto']} ({lugar_texto(it)}), {ventana_texto(it)}"
    if ev and any(n.startswith("Excluyente") for n in ev.get("notas", [])):
        linea += ". Ojo: tiene un requisito excluyente"
    return linea


def etiqueta(it):
    return ["scales"] if it["ambito"] == "judicial" else ["mortar_board"]


def pagina_de(persona):
    return f"{config.PAGINA}#{persona['id']}"


def avisar_nuevos(persona, nuevos):
    """Aviso por concurso, o un resumen si son muchos. Devuelve si salió."""
    if not nuevos:
        return True
    if len(nuevos) > MAX_AVISOS_SUELTOS:
        fuerte = any(ev["nivel"] == "fuerte" for _, ev in nuevos)
        cuerpo = "\n".join(linea_resumen(it, ev) for it, ev in nuevos[:12])
        if len(nuevos) > 12:
            cuerpo += f"\n… y {len(nuevos) - 12} más en la página."
        ok, _ = avisos.enviar(persona, f"{len(nuevos)} concursos nuevos para vos", cuerpo,
                              prioridad=4 if fuerte else 3, enlace=pagina_de(persona),
                              etiquetas=["bell"])
        return ok
    todo_ok = True
    for it, ev in nuevos:
        titulo, cuerpo = mensaje_concurso(it, ev)
        ok, _ = avisos.enviar(
            persona, titulo, cuerpo, prioridad=avisos.PRIORIDAD[ev["nivel"]],
            enlace=it.get("inscribir") or it["url"], etiquetas=etiqueta(it),
            botones=[("Ver el llamado", it["url"]), ("Abrir la página", pagina_de(persona))])
        todo_ok = todo_ok and ok
    return todo_ok


def criterio(persona):
    """Explicación en castellano de qué cuenta como 'para vos'."""
    nd = persona.get("nodocente")
    que = []
    if nd:
        que.append(f"ascensos (categorías 1 a {nd['categoria'] - 1}) en concursos abiertos, "
                   f"cerrados generales, cerrados por sede de {nd['sede']} y cerrados internos "
                   "de tu dependencia")
    else:
        que.append("concursos nodocentes abiertos al público")
    if persona.get("judiciales"):
        que.append("concursos judiciales abiertos a la comunidad")
    texto = " y ".join(que)
    if persona.get("titulos") == []:
        texto += (", siempre que no pidan título o acepten estudiantes" if persona.get("estudios")
                  else ", siempre que no pidan título terciario ni universitario")
    lugares = {"suave": f"los de {config.CIUDAD} suenan y los de otras ciudades llegan en silencio",
               "fuerte": "suenan los de cualquier ciudad",
               "no": f"solo avisan los de {config.CIUDAD}"}[persona.get("otras_ciudades", "suave")]
    return texto[0].upper() + texto[1:] + f". Avisos: {lugares}."


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def main():
    ahora = datetime.now(ZONA)
    hoy = ahora.date()
    estado = leer_json(ESTADO, ESTADO_VACIO)
    for k, v in ESTADO_VACIO.items():
        estado.setdefault(k, json.loads(json.dumps(v)))
    estado.pop("pdf", None)              # textos de resoluciones: solo en memoria
    ctx = fuentes.Contexto(hoy)
    locales = {config.CIUDAD, *getattr(config, "CERCANAS", [])}
    personas = config.PERSONAS

    # 1) Leer todas las fuentes ------------------------------------------------
    items, info_fuentes, nuevas_fuentes = [], [], set()
    alertas, recuperadas = [], []
    for f in config.FUENTES:
        ef = estado["fuentes"].setdefault(f["id"], {"fallas": 0, "base": False})
        error = None
        try:
            leidos = fuentes.LECTORES[f["lector"]](f, ctx)
        except fuentes.FuenteError as e:
            error = str(e)
        except Exception as e:                      # error de programación
            error = f"Error inesperado al leer ({type(e).__name__}: {str(e)[:150]})"
        if error:
            ef["fallas"] = ef.get("fallas", 0) + 1
            print(f"[!] {f['nombre']}: {error}", file=sys.stderr)
            if ef["fallas"] == FALLAS_PARA_AVISAR:
                alertas.append((f, error, ef["fallas"]))
            info_fuentes.append({"id": f["id"], "nombre": f["nombre"], "url": f["url"],
                                 "ambito": f["ambito"], "ok": False, "error": error,
                                 "fallas": ef["fallas"], "ultima_ok": ef.get("ultima_ok")})
            continue
        if ef.get("fallas", 0) >= FALLAS_PARA_AVISAR:
            recuperadas.append(f)
        ef["fallas"] = 0
        ef["ultima_ok"] = ahora.isoformat(timespec="minutes")
        if not ef.get("base"):
            nuevas_fuentes.add(f["id"])
            ef["base"] = True
        items.extend(leidos)
        info_fuentes.append({"id": f["id"], "nombre": f["nombre"], "url": f["url"],
                             "ambito": f["ambito"], "ok": True, "avisos": len(leidos),
                             "ultima_ok": ef["ultima_ok"]})
        print(f"[ok] {f['nombre']}: {len(leidos)} avisos")

    # 2) Un mismo llamado publicado en dos lugares cuenta una vez -------------
    unicos, claves = [], {}
    for it in items:
        clave = (it.get("dependencia"), it.get("resolucion")) if it["ambito"] == "nodocente" else None
        if clave and clave[1] and clave in claves:
            queda = claves[clave]
            queda.setdefault("tambien_en", []).append(it["url"])
            if it.get("resolucion_texto") and not queda.get("resolucion_texto"):
                queda["resolucion_texto"] = it["resolucion_texto"]
            continue
        if clave and clave[1]:
            claves[clave] = it
        unicos.append(it)
    items = unicos
    por_id = {f["id"]: f for f in config.FUENTES}
    for it in items:
        completar(it, por_id[it["fuente"]], hoy)

    # 3) Para quién sirve cada uno --------------------------------------------
    vistos = estado["vistos"]
    for it in items:
        reg = vistos.setdefault(it["id"], {"desde": hoy.isoformat(), "avisado": []})
        it["visto_desde"] = reg["desde"]
        it["para"] = {}
        evaluar_todos(it, personas, locales)

    # Para lo vigente que le importa a alguien, buscar la resolución en el
    # digesto si todavía no se leyó, y releer los requisitos excluyentes.
    carpetas = getattr(config, "CARPETAS_RESOLUCIONES", {})
    for it in items:
        if (it["ambito"] == "nodocente" and it["para"] and not it.get("req")
                and vigente(it, hoy) and re.match(r"\d+/\d{4}$", it.get("resolucion") or "")
                and it.get("dependencia") in carpetas):
            texto = fuentes.buscar_resolucion(ctx, carpetas[it["dependencia"]], it["resolucion"])
            if texto:
                it["resolucion_texto"] = texto
                aplicar_resolucion(it)
                evaluar_todos(it, personas, locales)

    # 4) Avisos ------------------------------------------------------------------
    resultado_avisos = {}
    prueba = os.environ.get("PRUEBA", "").lower() in ("1", "true", "si", "sí")
    for p in personas:
        pid = p["id"]
        r = resultado_avisos[pid] = {"canal": bool(avisos.canal(p))}
        if prueba and avisos.canal(p):
            ok, det = avisos.enviar(
                p, "Prueba del monitor de concursos",
                f"Hola, {p['nombre']}. Si ves esto, los avisos te llegan bien.",
                prioridad=4, enlace=pagina_de(p), etiquetas=["white_check_mark"])
            r["prueba"] = det

        relevantes = [(it, it["para"][pid]) for it in items
                      if avisable(it["para"].get(pid))]
        if not avisos.canal(p):
            continue                                # se avisa cuando tenga canal

        if not estado["bienvenida"].get(pid):
            # Primera vez con canal: un solo resumen de lo vigente, sin historia.
            vig = [(it, ev) for it, ev in relevantes if vigente(it, hoy)]
            vig.sort(key=lambda x: (x[1]["nivel"] != "fuerte", x[0].get("hasta") or "9999"))
            if vig:
                cuerpo = (f"Hoy hay {len(vig)} con inscripción abierta o por abrir que te "
                          "pueden servir:\n" + "\n".join(linea_resumen(it, ev) for it, ev in vig[:10]))
            else:
                cuerpo = "Por ahora no hay nada abierto para vos. Te aviso acá apenas aparezca."
            ok, det = avisos.enviar(p, "Monitor de concursos activado",
                                    cuerpo + "\nEl detalle está en la página.",
                                    prioridad=3, enlace=pagina_de(p), etiquetas=["tada"])
            r["bienvenida"] = det
            if ok:
                estado["bienvenida"][pid] = hoy.isoformat()
                for it, _ in relevantes:
                    vistos[it["id"]]["avisado"].append(pid)
            continue

        nuevos, de_fuente_nueva = [], []
        for it, ev in relevantes:
            reg = vistos[it["id"]]
            if pid in reg["avisado"]:
                continue
            if not vigente(it, hoy):
                reg["avisado"].append(pid)          # ya pasó: no tiene sentido avisar
                continue
            (de_fuente_nueva if it["fuente"] in nuevas_fuentes else nuevos).append((it, ev))
        nuevos.sort(key=lambda x: (x[1]["nivel"] != "fuerte", x[0].get("hasta") or "9999"))
        if avisar_nuevos(p, nuevos):
            for it, _ in nuevos:
                vistos[it["id"]]["avisado"].append(pid)
        if de_fuente_nueva:
            cuerpo = "\n".join(linea_resumen(it, ev) for it, ev in de_fuente_nueva[:10])
            ok, _ = avisos.enviar(p, "Nueva página revisada: hay concursos para vos", cuerpo,
                                  prioridad=3, enlace=pagina_de(p), etiquetas=["bell"])
            if ok:
                for it, _ in de_fuente_nueva:
                    vistos[it["id"]]["avisado"].append(pid)
        r["nuevos"] = len(nuevos) + len(de_fuente_nueva)

        # Recordatorio el día antes del cierre, solo para lo de la ciudad.
        manana = (hoy + timedelta(days=1)).isoformat()
        rec = estado["recordados"].setdefault(pid, [])
        for it, ev in relevantes:
            if (ev["nivel"] == "fuerte" and it["inscripcion"] == "abierta"
                    and it.get("hasta") == manana and it["id"] not in rec):
                ok, _ = avisos.enviar(
                    p, f"Cierra mañana: {it['titulo_corto']}",
                    f"La inscripción cierra el {ddmm(fecha(it['hasta']))}. "
                    f"{nombre_fuente(it)}, {lugar_texto(it)}.",
                    prioridad=4, enlace=it.get("inscribir") or it["url"],
                    etiquetas=["alarm_clock"])
                if ok:
                    rec.append(it["id"])

        # Mantenimiento: páginas que dejaron de leerse o volvieron.
        if p.get("avisos_tecnicos"):
            for f, error, n in alertas:
                avisos.enviar(p, f"No puedo leer: {f['nombre']}",
                              f"{error}.\nVan {n} revisiones seguidas. Mientras tanto, "
                              f"revisala a mano: {f['url']}",
                              prioridad=3, enlace=f["url"], etiquetas=["warning"])
            for f in recuperadas:
                avisos.enviar(p, f"Volvió a leerse: {f['nombre']}",
                              "La página volvió a responder y el monitor la revisa de nuevo.",
                              prioridad=2, etiquetas=["white_check_mark"])

    # 5) Guardar ----------------------------------------------------------------
    orden = {"abierta": 0, "por_abrir": 1, "sin_fecha": 2, "cerrada": 3}
    items.sort(key=lambda it: (orden.get(it["inscripcion"], 4),
                               -(fecha(it.get("hasta") or it.get("publicado") or it["visto_desde"])
                                 or hoy).toordinal()))
    publicos = []
    for it in items:
        d = {k: v for k, v in it.items() if k not in ("texto", "inscripcion_texto", "resolucion_texto")}
        if d.get("requisitos"):
            d["requisitos"] = d["requisitos"][:700]
        d["fuente_nombre"] = nombre_fuente(it)
        d["instancia_nombre"] = reglas.INSTANCIAS.get(it.get("instancia"), "Tipo sin identificar")
        if it.get("agrupamiento"):
            d["agrupamiento_nombre"] = reglas.AGRUPAMIENTOS.get(it["agrupamiento"])
        if it.get("titulo_requerido"):
            d["titulo_requerido_nombre"] = reglas.NOMBRE_TITULO[it["titulo_requerido"]]
        publicos.append(d)

    activos = {it["id"] for it in items}
    limite = (hoy - timedelta(days=400)).isoformat()
    estado["vistos"] = {k: v for k, v in vistos.items() if k in activos or v["desde"] >= limite}

    datos = {
        "personas": [{"id": p["id"], "nombre": p["nombre"], "criterio": criterio(p),
                      "nodocente": bool(p.get("nodocente"))} for p in personas],
        "concursos": publicos,
    }
    escribir_json(DATOS, datos)
    escribir_json(REVISION, {
        "revisado": ahora.isoformat(timespec="minutes"),
        "fuentes": info_fuentes,
        "avisos": resultado_avisos,
        "diagnostico": ctx.diagnostico,
    })
    escribir_json(ESTADO, estado)

    leidas = sum(1 for x in info_fuentes if x["ok"])
    print(f"\n{leidas}/{len(info_fuentes)} páginas leídas, {len(items)} concursos.")
    for p in personas:
        n = sum(1 for it in items if avisable(it["para"].get(p["id"])) and vigente(it, hoy))
        print(f"  {p['nombre']}: {n} vigentes que le sirven. Avisos: {resultado_avisos[p['id']]}")
    return 0 if leidas else 1


if __name__ == "__main__":
    sys.exit(main())
