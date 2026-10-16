"""
Lectores de las páginas de concursos: uno por sitio.

Cada lector devuelve una lista de avisos (dicts) con lo que la página trae
ordenado. Lo que falta (tipo de concurso, categoría, ciudad, fechas, título
exigido) lo completa monitor.py usando reglas.py.

Si una página no responde o cambió de formato, el lector lanza FuenteError
con una explicación en castellano. El monitor la muestra en la página y avisa,
en vez de informar "no hay concursos" cuando en realidad dejó de mirar.
"""

import io
import re
import time
from datetime import date, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import reglas
from reglas import limpiar, normalizar

# El sitio de la UNP tiene un filtro anti-robots que desvía a los programas
# que se hacen pasar por navegador. Este monitor se presenta como lo que es,
# y solo si un sitio lo rechaza prueba con la identificación de un navegador.
UA_MONITOR = "monitor-concursos/1.0 (+https://github.com/GalegoX/concursos)"
UA_NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


class FuenteError(Exception):
    """La página no se pudo leer. El mensaje se muestra tal cual en la página."""


class Contexto:
    """Lo que comparten todos los lectores en una revisión."""

    def __init__(self, hoy, cache_pdf=None):
        self.hoy = hoy
        self.cache_pdf = cache_pdf if cache_pdf is not None else {}
        self.sesion = requests.Session()
        self.sesion.headers.update({
            "Accept-Language": "es-AR,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })
        self.diagnostico = {}

    def get(self, url, params=None, timeout=45):
        """
        Descarga con reintentos. Si el sitio tarda o da error interno, reintenta
        igual; solo si lo rechaza (o lo desvía) prueba con otra identificación.
        """
        ultimo = "No respondió"
        for ua in (UA_MONITOR, UA_NAVEGADOR):
            rechazado = False
            for intento in range(3):
                try:
                    r = self.sesion.get(url, params=params, timeout=timeout,
                                        headers={"User-Agent": ua})
                except requests.Timeout:
                    ultimo = f"No respondió en {timeout} segundos"
                    time.sleep(5 * (intento + 1))
                    continue
                except requests.RequestException as e:
                    ultimo = f"No respondió ({type(e).__name__})"
                    time.sleep(5 * (intento + 1))
                    continue
                desviada = "attempt=" in r.url
                if r.status_code == 200 and not desviada:
                    self.diagnostico.setdefault("identificacion", {})[url[:90]] = (
                        "monitor" if ua == UA_MONITOR else "navegador")
                    return r
                if r.status_code >= 500:
                    ultimo = f"El sitio respondió con un error interno ({r.status_code})"
                    time.sleep(5 * (intento + 1))
                    continue
                if desviada:
                    ultimo = "El sitio desvió la consulta a una dirección que no existe"
                elif r.status_code == 404:
                    ultimo = "La página no existe (error 404): puede haberse mudado"
                else:
                    ultimo = f"El sitio rechazó la consulta (error {r.status_code})"
                rechazado = True
                break
            if not rechazado:
                break               # tarda o falla igual: cambiar de identificación no ayuda
        raise FuenteError(ultimo)

    def texto_pdf(self, url, paginas=3):
        """Texto de las primeras páginas de un PDF (vacío si es escaneado)."""
        if url in self.cache_pdf:
            return self.cache_pdf[url]
        texto = ""
        try:
            r = self.get(url, timeout=60)
            if len(r.content) <= 15_000_000:
                from pypdf import PdfReader
                lector = PdfReader(io.BytesIO(r.content))
                partes = [(p.extract_text() or "") for p in lector.pages[:paginas]]
                texto = limpiar(" ".join(partes))[:6000]
        except Exception:
            texto = ""
        self.cache_pdf[url] = texto
        return texto


def _sopa(r):
    return BeautifulSoup(r.content, "lxml")


def _txt(el):
    return limpiar(el.get_text(" ")) if el is not None else ""


def _fecha_dmy(texto):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", texto or "")
    if not m:
        return None
    d, mth, a = (int(x) for x in m.groups())
    if a < 100:
        a += 2000
    try:
        return date(a, mth, d)
    except ValueError:
        return None


def _iso(d):
    return d.isoformat() if d else None


def aviso(fuente, id_local, titulo, url, **campos):
    a = {
        "id": f"{fuente['id']}:{id_local}",
        "fuente": fuente["id"],
        "ambito": fuente["ambito"],
        "titulo": limpiar(titulo),
        "url": url,
    }
    a.update({k: v for k, v in campos.items() if v not in (None, "", [])})
    return a


def numero_resolucion(texto, anio_defecto):
    """'Res. R/11 Nº 575/2026' -> '575/2026'."""
    t = normalizar(texto)
    m = re.search(r"(?<![/\d])(\d{1,5})\s*/\s*(\d{4})", t)
    if m:
        return f"{int(m.group(1))}/{m.group(2)}"
    m = re.search(r"n\W{0,3}(\d{1,5})", t) or re.search(r"\b(\d{1,5})\b", t)
    if m:
        return f"{int(m.group(1))}/{anio_defecto}"
    return None


_NODOCENTE = re.compile(
    r"no\s*-?\s*docente|\baa\W{0,2}pp\b|\bcat(?:egoria)?\.?\s*0?[1-7](?!\d)|"
    r"agrupamiento|planta permanente|tramo (?:inicial|intermedio|mayor)")


def es_nodocente(texto):
    return bool(_NODOCENTE.search(normalizar(texto)))


# --------------------------------------------------------------------------
# UNPSJB
# --------------------------------------------------------------------------

def leer_rectorado(fuente, ctx):
    """
    Tabla 'Personal Nodocente (Concursos)'. Viene en secciones
    ('LLAMADOS A CONCURSO INTERNO CERRADO', 'LLAMADOS A CONCURSO ABIERTO'...)
    con columnas Resolución, Dependencia y Puesto, Agrupamiento y Tramo,
    Publicación, Inscripción, Impugnaciones y Evaluación.
    """
    soup = _sopa(ctx.get(fuente["url"], timeout=fuente.get("timeout", 45)))
    cuerpo = soup.find(attrs={"itemprop": "articleBody"}) or soup
    tablas = [t for t in cuerpo.find_all("table") if "resoluc" in normalizar(_txt(t))[:600]]
    if not tablas:
        raise FuenteError("No se encontró la tabla de concursos: la página cambió de formato.")
    avisos = []
    for tabla in tablas:
        instancia, seccion, cols = None, "", None
        for tr in tabla.find_all("tr"):
            celdas = [_txt(td) for td in tr.find_all(["td", "th"])]
            llenas = [c for c in celdas if c]
            if not llenas:
                continue
            if len(llenas) == 1:
                if "concurso" in normalizar(llenas[0]):
                    seccion = llenas[0]
                    instancia = reglas.detectar_instancia(llenas[0])
                continue
            norm = [normalizar(c) for c in celdas]
            if any("resoluc" in c for c in norm) and not any(re.search(r"\d{3,}", c) for c in celdas):
                cols = norm
                continue
            if not cols or len(celdas) != len(cols):
                continue
            fila = dict(zip(cols, celdas))

            def col(*claves):
                for k, v in fila.items():
                    if any(c in k for c in claves):
                        return v
                return ""

            res = col("resoluc")
            puesto = col("puesto", "dependencia", "asunto", "observac")
            agrup = col("agrupamiento", "tramo")
            publicacion = reglas.rango(col("publicac"), ctx.hoy.year)
            desde, hasta = reglas.rango(col("inscrip"), ctx.hoy.year)
            evaluacion = _fecha_dmy(col("evaluac"))
            anio = (publicacion[0] or desde or ctx.hoy).year
            num = numero_resolucion(res, anio)
            if not num:
                continue
            partes = [p.strip() for p in re.split(r"\s*[•·]\s*", puesto, maxsplit=1)]
            cargo = partes[-1]
            dependencia_txt = partes[0] if len(partes) > 1 else ""
            texto = " ".join(x for x in (seccion, res, puesto, agrup) if x)
            categoria = reglas.detectar_categoria(agrup) or reglas.detectar_categoria(texto)
            if not categoria and re.fullmatch(r"0?[1-7]", col("categor").strip() or "x"):
                categoria = int(col("categor"))
            ciudades = reglas.detectar_ciudades(puesto) or [fuente["ciudad_por_defecto"]]
            avisos.append(aviso(
                fuente, num, cargo, fuente["url"],
                detalle=dependencia_txt, texto=texto, resolucion=num,
                instancia=instancia or reglas.detectar_instancia(texto),
                categoria=categoria,
                agrupamiento=reglas.agrupamiento_de_celda(agrup) or reglas.detectar_agrupamiento(texto),
                ciudades=ciudades, dependencia=fuente["dependencia"],
                desde=_iso(desde), hasta=_iso(hasta),
                publicado=_iso(publicacion[0]), evaluacion=_iso(evaluacion),
            ))
    return avisos


def leer_ingenieria(fuente, ctx):
    """Tabla Resolución | fecha | categoría | Asunto/Observaciones | Inscripciones."""
    soup = _sopa(ctx.get(fuente["url"], timeout=fuente.get("timeout", 45)))
    tabla = next((t for t in soup.find_all("table") if "asunto" in normalizar(_txt(t))[:400]), None)
    if tabla is None:
        raise FuenteError("No se encontró la tabla de concursos: la página cambió de formato.")
    filas = tabla.find_all("tr")
    cols = [normalizar(_txt(c)) for c in filas[0].find_all(["td", "th"])]
    avisos = []
    for tr in filas[1:]:
        tds = tr.find_all(["td", "th"])
        if len(tds) != len(cols):
            continue
        fila = dict(zip(cols, (_txt(td) for td in tds)))

        def col(*claves):
            for k, v in fila.items():
                if any(c in k for c in claves):
                    return v
            return ""

        res, asunto = col("resoluc"), col("asunto", "observac")
        if not res or not asunto:
            continue
        publicado = _fecha_dmy(col("fecha"))
        anio = publicado.year if publicado else ctx.hoy.year
        insc = normalizar(col("inscrip"))
        # La columna de inscripciones trae nombres de personas: solo se toma el estado.
        if "desiert" in insc:
            estado = "Declarado desierto"
        elif "finaliz" in insc:
            estado = "Finalizado"
        elif insc:
            estado = "Con inscriptos"
        else:
            estado = None
        enlace = tr.find("a", href=True)
        url = urljoin(fuente["url"], enlace["href"]) if enlace else fuente["url"]
        cat_col = col("categor").strip()
        categoria = int(cat_col) if re.fullmatch(r"0?[1-7]", cat_col) else reglas.detectar_categoria(asunto)
        num = numero_resolucion(res, anio)
        avisos.append(aviso(
            fuente, num, asunto, url, texto=asunto, resolucion=num,
            categoria=categoria, dependencia=fuente["dependencia"],
            publicado=_iso(publicado), estado_fuente=estado,
        ))
    if not avisos:
        raise FuenteError("La tabla de concursos está vacía o cambió de formato.")
    return avisos


def leer_wordpress(fuente, ctx):
    """Sitios WordPress de facultades: publicaciones que mencionan 'concurso'."""
    base = fuente["url"].rstrip("/")
    r = ctx.get(base + "/wp-json/wp/v2/posts",
                params={"search": "concurso", "per_page": 30,
                        "_fields": "id,date,link,title,content"})
    try:
        posts = r.json()
    except ValueError:
        raise FuenteError("La consulta de publicaciones no devolvió datos válidos.")
    if not isinstance(posts, list):
        raise FuenteError("La consulta de publicaciones devolvió un formato inesperado.")
    avisos = []
    for p in posts:
        titulo = limpiar(BeautifulSoup(p["title"]["rendered"], "lxml").get_text(" "))
        cont = BeautifulSoup(p["content"]["rendered"] or "", "lxml")
        cuerpo = _txt(cont)
        if not es_nodocente(titulo + " " + cuerpo):
            continue
        pdfs = [urljoin(p["link"], a["href"]) for a in cont.find_all("a", href=True)
                if a["href"].lower().split("?")[0].endswith(".pdf")]
        texto_pdf = ctx.texto_pdf(pdfs[0]) if (pdfs and len(cuerpo) < 400) else ""
        texto = " ".join(x for x in (titulo, cuerpo, texto_pdf) if x)
        publicado = p.get("date", "")[:10] or None
        anio = int(publicado[:4]) if publicado else ctx.hoy.year
        m = re.search(r"\b(\d{1,4})\s*/\s*(\d{4})\b", normalizar(cuerpo + " " + texto_pdf[:800]))
        avisos.append(aviso(
            fuente, p["id"], titulo, p["link"], texto=texto[:3000],
            dependencia=fuente["dependencia"], publicado=publicado,
            pdf=pdfs[0] if pdfs else None,
            resolucion=f"{int(m.group(1))}/{m.group(2)}" if m else None,
            anio_ref=anio,
        ))
    return avisos


# Un llamado (no una modificación, rectificación, recurso o designación).
_DIGESTO_LLAMADO = re.compile(
    r"\b(llam\w*|convoca\w*|autoriz\w* (?:el )?llamado|declar\w* abierta la inscripci\w*|"
    r"apertura de (?:la )?inscripci\w*)\b.*concurso|concurso.*\bllamad")
_DIGESTO_NO_ES_LLAMADO = re.compile(
    r"^(modific|rectific|hacer lugar|aprob|design|sustanci|declar\w* desiert|dej\w* sin efecto|"
    r"autoriz\w* (?:el )?pago|prorrog|integr)")
_DIGESTO_DOCENTE = re.compile(
    r"\bprofesor|\bjtp\b|jefe de trabajos|ayudante|\bayte\b|catedra|asignatura|"
    r"dedicacion (?:simple|semi|exclusiva)|(?<!no )\bdocentes?\b")
_DIGESTO_NODOCENTE = re.compile(r"ord\W*cs\W*n\W*186")


def leer_digesto(fuente, ctx):
    """
    Consulta pública del digesto (SUDOCU) por carpeta, buscando 'concurso' en
    el título. Se queda con los llamados nodocentes.
    """
    avisos, errores, respondieron = [], [], 0
    for carpeta, (dependencia, ciudad) in fuente["carpetas"].items():
        try:
            r = ctx.get(fuente["url"], params={
                "idContenedor": carpeta, "offset": 0, "limit": 30,
                "dir": "DESC", "txtBusquedaTitulo": "concurso"})
            datos = r.json()
        except (FuenteError, ValueError) as e:
            errores.append(f"carpeta {carpeta}: {e}")
            continue
        respondieron += 1
        muestras = ctx.diagnostico.setdefault("digesto_titulos", {})
        docs = datos.get("documents") or []
        muestras[str(carpeta)] = [limpiar(d.get("titulo"))[:120] for d in docs[:8]]
        for d in docs:
            titulo = limpiar(d.get("titulo"))
            n = normalizar(titulo)
            if (not _DIGESTO_LLAMADO.search(n) or _DIGESTO_NO_ES_LLAMADO.search(n)
                    or _DIGESTO_DOCENTE.search(n)):
                continue
            if not (es_nodocente(n) or _DIGESTO_NODOCENTE.search(n)):
                continue
            nro = d.get("nro") if isinstance(d.get("nro"), dict) else {}
            res = (f"{nro['nro']}/{nro['anio']}" if nro.get("nro") and nro.get("anio") else None)
            publicado = (d.get("fecha") or "")[:10] or None
            avisos.append(aviso(
                fuente, d["id"], titulo, f"https://huarpe.unp.edu.ar/{d['id']}",
                texto=" ".join(x for x in (titulo, limpiar(d.get("descripcion") or "")) if x),
                dependencia=dependencia, resolucion=res, publicado=publicado,
                ciudades=reglas.detectar_ciudades(titulo) or ([ciudad] if ciudad else None),
                detalle=datos.get("folder_name"),
            ))
    if respondieron == 0:
        raise FuenteError("No respondió ninguna carpeta del digesto. " + "; ".join(errores[:2]))
    if errores:
        ctx.diagnostico["digesto_errores"] = errores
    return avisos


# --------------------------------------------------------------------------
# Justicia del Chubut
# --------------------------------------------------------------------------

def leer_judicial(fuente, ctx):
    """Listado del sistema de concursos del Poder Judicial (grilla ASP.NET)."""
    soup = _sopa(ctx.get(fuente["url"], timeout=fuente.get("timeout", 45)))
    grilla = soup.find("table", id=re.compile(r"gridRrhhConcursos$"))
    if grilla is None:
        raise FuenteError("No se encontró la grilla de concursos: la página cambió de formato.")
    avisos = []
    for tr in grilla.find_all("tr", recursive=False):
        if tr.find("td", recursive=False) is None:
            continue

        def span(sufijo):
            return tr.find("span", id=re.compile(sufijo + "$"))

        cargo = _txt(span("_lblCargo"))
        if not cargo:
            continue
        tipo = _txt(span("_lblConcurso")).replace("Concurso:", "").strip()
        org_el = span("_lblcircuOrg")
        organismo = _txt(org_el)
        circ = _txt(org_el.find("span", class_="circ")) if org_el else ""
        desc = _txt(span("_lblDesc"))
        req = _txt(tr.find("div", class_="requisitosList"))
        fechas = [_txt(td) for td in tr.select("table.range-fechas td")]
        desde = _fecha_dmy(fechas[0]) if fechas else None
        hasta = _fecha_dmy(fechas[2]) if len(fechas) > 2 else None
        horario = fechas[3] if len(fechas) > 3 else ""
        id_el = tr.find("a", attrs={"idconcurso": True})
        id_local = id_el["idconcurso"] if id_el else normalizar(cargo + organismo)[:60]
        inscribir = next((a["href"] for a in tr.find_all("a", href=True)
                          if "forms" in a["href"] or "inscrib" in normalizar(_txt(a))), None)
        res = re.search(r"n\W{0,3}(\d{3,6}/\d{4})", normalizar(desc))
        # La resolución se firma en Rawson: la ciudad sale del organismo.
        ciudades = reglas.detectar_ciudades(organismo)
        if not ciudades:
            desc_sin_firma = re.sub(r"rawson,?\s*chubut", "", normalizar(desc))
            ciudades = reglas.detectar_ciudades(desc_sin_firma[:600])
        avisos.append(aviso(
            fuente, id_local, cargo, fuente["url"],
            detalle=organismo, texto=f"{cargo}. {tipo}. {organismo}",
            instancia="abierto" if "abiert" in normalizar(tipo) else "cerrado",
            ciudades=ciudades, requisitos=req[:1500],
            desde=_iso(desde), hasta=_iso(hasta), horario=horario,
            publicado=_iso(_fecha_dmy(_txt(span("_lblFechaConcurso")))),
            resolucion=res.group(1) if res else None, inscribir=inscribir,
            circunscripcion=circ,
        ))
    return avisos


_MESES_CORTOS = {"ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4, "may": 5,
                 "jun": 6, "jul": 7, "ago": 8, "aug": 8, "sep": 9, "set": 9, "oct": 10,
                 "nov": 11, "dic": 12, "dec": 12}


def _fecha_corta(texto):
    """'22 Sep 26, 09:35 am' -> date."""
    m = re.search(r"(\d{1,2})\s+([a-z]{3})\w*\.?\s+(\d{2,4})", normalizar(texto))
    if not m or m.group(2) not in _MESES_CORTOS:
        return None
    a = int(m.group(3))
    try:
        return date(a + 2000 if a < 100 else a, _MESES_CORTOS[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def leer_mpf(fuente, ctx):
    """Feed de concursos del MPF (Joomla + SP Page Builder)."""
    soup = _sopa(ctx.get(fuente["url"], timeout=fuente.get("timeout", 45)))
    entradas = soup.select("div.sppb-addon-article")
    if not entradas:
        raise FuenteError("No se encontró el listado de concursos: la página cambió de formato.")
    avisos, vistos = [], set()
    for e in entradas:
        a = e.select_one(".sppb-article-title a")
        if a is None or a["href"] in vistos:
            continue
        vistos.add(a["href"])
        titulo = _txt(a)
        categoria = _txt(e.select_one(".sppb-meta-category"))
        etiquetas = [_txt(t) for t in e.select(".tags .label")]
        estados = [t for t in etiquetas if re.search(r"finaliz|vigente", normalizar(t))]
        lugares = [t for t in etiquetas if t not in estados]
        intro = _txt(e.select_one(".sppb-article-introtext"))
        publicado = _fecha_corta(_txt(e.select_one(".sppb-meta-date")))
        anio = publicado.year if publicado else ctx.hoy.year
        desde, hasta = reglas.fechas_inscripcion(intro, anio)
        c = normalizar(categoria)
        if "cerrad" in c:
            instancia = "cerrado"
        elif "abiert" in c or "funcionario" in c or "fiscal" in c:
            instancia = "abierto"
        else:
            instancia = reglas.detectar_instancia(titulo)
        ciudades = []
        for x in lugares + [titulo]:
            for ciudad in reglas.detectar_ciudades(x):
                if ciudad not in ciudades:
                    ciudades.append(ciudad)
        slug = a["href"].rstrip("/").rsplit("/", 1)[-1][:90]
        avisos.append(aviso(
            fuente, slug, titulo, urljoin(fuente["url"], a["href"]),
            detalle=categoria, texto=f"{titulo}. {intro}", instancia=instancia,
            ciudades=ciudades, desde=_iso(desde), hasta=_iso(hasta),
            publicado=_iso(publicado), inscripcion_texto=intro,
            estado_fuente=estados[0].capitalize() if estados else None,
        ))
    return avisos


def leer_defensa(fuente, ctx):
    """
    Página 'Cargos convocados por el Ministerio de la Defensa Pública'
    (WordPress): bloques con la ciudad como título, la descripción del cargo,
    la ventana de inscripción y el enlace a la disposición en PDF.
    """
    soup = _sopa(ctx.get(fuente["url"], timeout=fuente.get("timeout", 45)))
    primer_pdf = soup.find("a", href=re.compile(r"wp-content/uploads/.*\.pdf$", re.I))
    if primer_pdf is None:
        raise FuenteError("No se encontraron disposiciones: la página cambió de formato.")
    contenedor = primer_pdf.find_parent("div", class_="wpb_wrapper") or primer_pdf.find_parent("div")
    avisos, bloque = [], None

    def cerrar(b):
        if not b or not b.get("pdf"):
            return
        texto = " ".join(b["parrafos"])
        n = normalizar(texto)
        m = re.search(r"cargos? de (.+?) (?:para|en) (?:la|el|los|las) (.+?)(?: de la ciudad| de \w+ \w+\.|\.|$)", texto, re.I)
        cargo = limpiar(m.group(1)) if m else (b["parrafos"][0][:120] if b["parrafos"] else "Cargo sin leer")
        detalle = limpiar(m.group(2)) if m else ""
        anio_m = re.search(r"/uploads/(\d{4})/(\d{2})/", b["pdf"])
        anio = int(anio_m.group(1)) if anio_m else ctx.hoy.year
        desde, hasta = reglas.fechas_inscripcion(texto, anio)
        ciudades = reglas.detectar_ciudades(b["ciudad"]) or reglas.detectar_ciudades(texto)
        num = re.search(r"(\d{1,3})\s*/\s*(\d{2,4})", normalizar(b["disposicion"]))
        id_local = f"{num.group(1)}/{num.group(2)}" if num else b["pdf"].rsplit("/", 1)[-1]
        avisos.append(aviso(
            fuente, id_local, cargo, b["pdf"], detalle=detalle, texto=texto[:2000],
            instancia=reglas.detectar_instancia(texto) or ("abierto" if "comunidad" in n else None),
            ciudades=ciudades, desde=_iso(desde), hasta=_iso(hasta),
            publicado=f"{anio_m.group(1)}-{anio_m.group(2)}-01" if anio_m else None,
            resolucion=b["disposicion"],
        ))

    for el in contenedor.find_all(["h1", "h2", "h3", "h4", "p"], recursive=True):
        t = _txt(el)
        if not t:
            continue
        if el.name in ("h2", "h3", "h4") and not re.search(r"llamado a concurso", normalizar(t)):
            cerrar(bloque)
            bloque = {"ciudad": t, "parrafos": [], "pdf": None, "disposicion": ""}
            continue
        if bloque is None:
            continue
        enlace = el.find("a", href=re.compile(r"\.pdf$", re.I))
        if enlace and re.search(r"disposici", normalizar(t)) and not bloque["pdf"]:
            bloque["pdf"] = urljoin(fuente["url"], enlace["href"])
            bloque["disposicion"] = t
        elif not enlace:
            bloque["parrafos"].append(t)
    cerrar(bloque)
    return avisos


# --------------------------------------------------------------------------
# Justicia nacional
# --------------------------------------------------------------------------

def leer_mpd_nacion(fuente, ctx):
    """
    'Inscripciones Vigentes' de la Defensoría General de la Nación: es
    nacional, así que solo se guardan los que mencionan ciudades de la zona.
    """
    soup = _sopa(ctx.get(fuente["url"], timeout=fuente.get("timeout", 45)))
    main = soup.find("main") or soup
    if "inscripciones vigentes" not in normalizar(_txt(main))[:600]:
        raise FuenteError("No se encontró 'Inscripciones Vigentes': la página cambió de formato.")
    avisos, seccion = [], ""
    for a in main.find_all("a", href=True):
        t = _txt(a)
        n = normalizar(t)
        if "click to collapse" in n or n.startswith("+ -"):
            seccion = n
            continue
        if not n.startswith("concurso"):
            continue
        ciudades = reglas.detectar_ciudades(t)
        if not ciudades:
            continue
        if "juridic" in seccion or "magistrad" in seccion:
            requerido = "abogacia"
        elif "medico" in seccion or "psicolog" in seccion:
            requerido = "universitario"
        else:
            requerido = None
        num = re.search(r"concurso n\W{0,3}(\d+)", n)
        desde, hasta = reglas.fechas_inscripcion("inscripcion " + t, ctx.hoy.year)
        avisos.append(aviso(
            fuente, num.group(1) if num else n[:60], re.sub(r"\(del .*?\)", "", t, flags=re.I),
            urljoin(fuente["url"], a["href"]), detalle=seccion.replace("+ -", "").replace(
                "click to collapse", "").strip().title(),
            texto=t, instancia="abierto", ciudades=ciudades,
            desde=_iso(desde), hasta=_iso(hasta), titulo_requerido=requerido,
        ))
    return avisos


LECTORES = {
    "rectorado": leer_rectorado,
    "ingenieria": leer_ingenieria,
    "wordpress": leer_wordpress,
    "digesto": leer_digesto,
    "judicial": leer_judicial,
    "mpf": leer_mpf,
    "defensa": leer_defensa,
    "mpd_nacion": leer_mpd_nacion,
}
