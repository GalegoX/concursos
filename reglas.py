"""
Reglas: cómo se lee un aviso y a quién le sirve.

Primero se extraen datos del texto (tipo de concurso, categoría, ciudad,
fechas de inscripción, si pide título). Después, para cada persona, se decide
si el concurso le sirve y con qué fuerza avisar.

Ante la duda, el monitor avisa con una nota ("revisalo") en vez de callarse:
es peor perderse un concurso que recibir un aviso de más.
"""

import re
import unicodedata
from datetime import date

# --------------------------------------------------------------------------
# Texto
# --------------------------------------------------------------------------


def normalizar(texto):
    """Minúsculas, sin tildes y con los espacios colapsados."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\xa0", " ").lower()
    return re.sub(r"\s+", " ", t).strip()


def limpiar(texto):
    """Espacios colapsados, conservando mayúsculas y tildes (para mostrar)."""
    t = (texto or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------
# Tipo de concurso (instancia)
# --------------------------------------------------------------------------

INSTANCIAS = {
    "abierto": "Abierto al público",
    "general": "Cerrado general",
    "sede": "Cerrado por sede",
    "interno": "Cerrado interno",
    "cerrado": "Cerrado",
}

_PALABRA_INSTANCIA = re.compile(
    r"\b(cerrad[oa]s?|abiert[oa]s?|intern[oa]s?|extern[oa]s?|public[oa]s?)\b")


def _instancia_desde(t, pos):
    """Clasifica a partir de la palabra clave que empieza en pos."""
    resto = t[pos:pos + 45]
    if resto.startswith("cerrad"):
        if re.match(r"cerrad[oa]s?\W{0,3}general", resto):
            return "general"
        if re.match(r"cerrad[oa]s?\W{0,3}(por|de)\s+sede", resto):
            return "sede"
        if re.match(r"cerrad[oa]s?\W{0,3}intern", resto):
            return "interno"
        return "cerrado"
    if resto.startswith("abiert") or resto.startswith("extern") or resto.startswith("public"):
        return "abierto"
    if resto.startswith("intern"):
        return "interno"
    return None


def detectar_instancia(texto):
    """
    Devuelve abierto / general / sede / interno / cerrado, o None.

    Busca la primera palabra de tipo que aparezca después de "concurso", para
    no confundirse con frases como "habiéndose declarado desierto el cerrado
    general" que suelen venir más adelante en el mismo texto.
    """
    t = normalizar(texto)
    for m in re.finditer(r"\bconcursos?\b", t):
        tramo = t[m.end():m.end() + 70]
        corte = re.search(r"[.;|]", tramo)
        if corte:
            tramo = tramo[:corte.start()]
        p = _PALABRA_INSTANCIA.search(tramo)
        if p:
            inst = _instancia_desde(t, m.end() + p.start())
            if inst:
                return inst
    # Sin la palabra "concurso" cerca: frases sueltas inequívocas.
    if re.search(r"abiert[oa]s?\s+a\s+la\s+comunidad", t):
        return "abierto"
    for patron, inst in ((r"cerrad[oa]s?\W{0,3}general", "general"),
                         (r"cerrad[oa]s?\W{0,3}(por|de)\s+sede", "sede"),
                         (r"cerrad[oa]s?\W{0,3}intern", "interno")):
        if re.search(patron, t):
            return inst
    return None


# --------------------------------------------------------------------------
# Categoría y agrupamiento (nodocentes, CCT 366/06)
# --------------------------------------------------------------------------


def detectar_categoria(texto):
    t = normalizar(texto)
    for patron in (r"categoria\s*(?:n\s*[o°]?\.?\s*)?:?\s*0?([1-7])(?!\d)",
                   r"\bcat\.?\s*(?:n\s*[o°]?\.?\s*)?:?\s*0?([1-7])(?!\d)"):
        m = re.search(patron, t)
        if m:
            return int(m.group(1))
    return None


AGRUPAMIENTOS = {
    "administrativo": "Administrativo",
    "tp_a": "Técnico Profesional \"A\"",
    "tp_b": "Técnico Profesional \"B\"",
    "tp": "Técnico Profesional",
    "mantenimiento": "Mantenimiento, Producción y Servicios Generales",
    "asistencial": "Asistencial",
}


def _agrupamiento_de(fragmento):
    f = fragmento
    m = re.search(r"tecnic[oa]s?\W{0,3}profesional(?:es)?\W{0,4}\(?\W{0,2}([ab])\b", f)
    if m:
        return "tp_" + m.group(1)
    if re.search(r"tecnic[oa]s?\W{0,3}profesional", f):
        return "tp"
    if f.startswith("administrativ") or re.match(r"\W{0,3}administrativ", f):
        return "administrativo"
    if re.search(r"mantenimiento|servicios\s+generales|produccion\s+y\s+servicios", f):
        return "mantenimiento"
    if re.search(r"asistencial", f):
        return "asistencial"
    return None


def agrupamiento_de_celda(texto):
    """Para celdas que solo dicen el agrupamiento: 'Administrativo Tramo Inicial'."""
    return _agrupamiento_de(normalizar(texto))


def detectar_agrupamiento(texto):
    t = normalizar(texto)
    # 1) Lo que viene después de la palabra "agrupamiento" (o "Ag.").
    for m in re.finditer(r"\bagrup(?:amiento)?\b\.?\s*:?|\bag\.?\s+(?=t[eé]c|adm|mant)", t):
        clave = _agrupamiento_de(t[m.end():m.end() + 50].strip())
        if clave:
            return clave
    # 2) Abreviaturas y menciones sueltas.
    #    AAPP / AA-PP = Agrupamiento Administrativo, Planta Permanente.
    if re.search(r"\baa\W{0,2}pp\b|\baa\b", t):
        return "administrativo"
    m = re.search(r"tecnic[oa]s?\W{0,3}profesional(?:es)?\W{0,4}\(?\W{0,2}([ab])\b", t)
    if m:
        return "tp_" + m.group(1)
    if re.search(r"tecnic[oa]s?\W{0,3}profesional", t):
        return "tp"
    if re.search(r"maestranza|mantenimiento|servicios\s+generales", t):
        return "mantenimiento"
    return None


# --------------------------------------------------------------------------
# Ciudades
# --------------------------------------------------------------------------

_CIUDADES = [
    ("Comodoro Rivadavia", r"comodoro|\bc\.\s*rivadavia|\bcdro\.?\s*riv|\bcrd\b"),
    ("Trelew", r"trelew"),
    ("Puerto Madryn", r"madryn"),
    ("Esquel", r"esquel"),
    ("Rawson", r"rawson"),
    ("Sarmiento", r"\bsarmiento\b(?! \d)"),
    ("Lago Puelo", r"lago puelo|el hoyo"),
    ("Gaiman", r"gaiman"),
    ("Rada Tilly", r"rada tilly"),
    ("Trevelin", r"trevelin"),
    ("Río Mayo", r"rio mayo"),
    ("José de San Martín", r"jose de san martin"),
    ("Gobernador Costa", r"gobernador costa|gdor\.? costa"),
    ("Alto Río Senguer", r"rio senguer"),
    ("El Maitén", r"el maiten"),
    ("Dolavon", r"dolavon"),
    ("Corcovado", r"corcovado"),
    ("Tecka", r"\btecka\b"),
    ("Paso de Indios", r"paso de indios"),
    ("Camarones", r"camarones"),
    ("Caleta Olivia", r"caleta olivia"),
    ("Ushuaia", r"ushuaia"),
]

# Organismos centrales que no dicen la ciudad pero tienen sede fija.
_SEDES_IMPLICITAS = [
    (r"superior tribunal|procuracion general|consejo de la magistratura|"
     r"oficina de gestion unificada del fuero civil y comercial de rawson", "Rawson"),
]


def detectar_ciudades(texto):
    t = normalizar(texto)
    halladas = []
    for nombre, patron in _CIUDADES:
        m = re.search(patron, t)
        if m:
            halladas.append((m.start(), nombre))
    if not halladas:
        for patron, nombre in _SEDES_IMPLICITAS:
            if re.search(patron, t):
                return [nombre]
        return []
    return [n for _, n in sorted(halladas)]


# --------------------------------------------------------------------------
# Fechas de inscripción
# --------------------------------------------------------------------------

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Fechas completas: "28 de septiembre [de 2026]", "28/09[/2026]", "28-09-2026".
_RE_FECHAS = [
    re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(_MESES) +
               r")(?:\s+(?:de|del)\s+(?:ano\s+)?(\d{4}))?"),
    re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{2,4}))?\b"),
    re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b"),
]
# Días sueltos justo antes de una fecha completa: "05, 06 y 07 de octubre",
# "13 al 27 de agosto", "desde el día 4 al 17 de marzo".
_RE_DIAS_ANTES = re.compile(
    r"(\d{1,2})(?:\s*,\s*\d{1,2})*\s*(?:,|\by\b|\bal\b|\ba\b|-|–|hasta)\s*(?:el\s+)?(?:dia\s+)?$")
_RE_CLAVE_INSCRIPCION = re.compile(r"\b(?:inscrip|inscip|incrip|insrip)\w*|\bpostulac\w*")
_RE_FIN_TRAMO = re.compile(r"\b(horario|hora|examen|prueba|entrevista|impugnac|lugar|sorteo|"
                           r"evaluaci|resolucion|res\.)")


def _fechas_completas(tramo):
    """[(dia, mes, anio|None, inicio, fin)] en orden de aparición, sin solaparse."""
    out = []
    for i, rx in enumerate(_RE_FECHAS):
        for m in rx.finditer(tramo):
            d, mes, a = m.groups()
            mes = _MESES[mes] if i == 0 else int(mes)
            out.append((int(d), mes, int(a) if a else None, m.start(), m.end()))
    out.sort(key=lambda x: x[3])
    limpio = []
    for f in out:
        if limpio and f[3] < limpio[-1][4]:
            continue
        limpio.append(f)
    return limpio


def _armar(d, m, a):
    if a is not None and a < 100:
        a += 2000
    try:
        return date(a, m, d)
    except (TypeError, ValueError):
        return None


def ventana(desde, hasta, anio_ref):
    """
    Completa años faltantes y valida. desde/hasta son (dia, mes, anio|None);
    desde puede ser None. Devuelve (date|None, date|None).
    """
    d2, m2, a2 = hasta
    fin = _armar(d2, m2, a2 if a2 is not None else anio_ref)
    if fin is None:
        return None, None
    inicio = None
    if desde:
        d1, m1, a1 = desde
        inicio = _armar(d1, m1, a1 if a1 is not None else fin.year)
        if inicio and inicio > fin:          # cruza fin de año: 28/12 al 05/01
            inicio = _armar(d1, m1, fin.year - 1)
    return inicio, fin


def fechas_inscripcion(texto, anio_ref):
    """
    Busca la ventana de inscripción en el texto y devuelve (desde, hasta) como
    date (cualquiera puede ser None). Solo mira justo después de la palabra
    "inscripción" (o "postulaciones"), para no tomar la fecha de la resolución
    o del examen. anio_ref completa las fechas escritas sin año.
    """
    t = normalizar(texto)
    for m in _RE_CLAVE_INSCRIPCION.finditer(t):
        tramo = t[m.end():m.end() + 150]
        corte = _RE_FIN_TRAMO.search(tramo)
        if corte and corte.start() > 6:
            tramo = tramo[:corte.start()]
        fechas = _fechas_completas(tramo)
        if not fechas:
            continue
        f1 = fechas[0]
        if len(fechas) >= 2:
            entre = tramo[f1[4]:fechas[1][3]]
            if re.fullmatch(r"\s*(?:,|\by\b|\bal\b|\ba\b|-|–|hasta(?: el)?)\s*(?:el\s+)?(?:dia\s+)?", entre):
                return ventana(f1[:3], fechas[1][:3], anio_ref)
        antes = tramo[:f1[3]]
        sueltos = _RE_DIAS_ANTES.search(antes)
        if sueltos:
            return ventana((int(sueltos.group(1)), f1[1], f1[2]), f1[:3], anio_ref)
        if re.search(r"hasta|cierre|vence", antes):
            return ventana(None, f1[:3], anio_ref)
        dia = ventana(None, f1[:3], anio_ref)[1]
        return dia, dia
    return None, None


def rango(texto, anio_ref):
    """Para celdas que solo tienen el rango: '14/10/2026 al 20/10/2026'."""
    return fechas_inscripcion("inscripcion " + (texto or ""), anio_ref)


def estado_inscripcion(desde, hasta, hoy):
    """abierta / por_abrir / cerrada / sin_fecha."""
    if hasta is None and desde is None:
        return "sin_fecha"
    if desde and hoy < desde:
        return "por_abrir"
    if hasta and hoy > hasta:
        return "cerrada"
    if hasta is None and desde and hoy >= desde:
        return "sin_fecha"
    return "abierta"


# --------------------------------------------------------------------------
# Título que exige el cargo
# --------------------------------------------------------------------------

NIVELES_TITULO = {"terciario": 1, "universitario": 2, "abogacia": 3}
NOMBRE_TITULO = {
    "terciario": "título terciario o técnico",
    "universitario": "título universitario",
    "abogacia": "título de abogado/a",
}

_REQ_ABOGACIA = r"abogad[oa]|titulo de abogad|ciencias juridicas"
_REQ_UNIV = (r"titulo (?:universitario|de grado)|licenciad[oa]|contador[a]? publico|"
             r"psicolog[oa]|trabajador[a]? social|medic[oa]|ingenier[oa]|"
             r"arquitect[oa]|bioquimic[oa]|odontolog[oa]|psicopedagog[oa]")
_REQ_TERC = r"titulo (?:terciario|tecnico)|tecnicatura|tecnico superior|profesorado"
_OPCIONAL = r"valorar|preferent|deseable|se tendra en cuenta|sera considerad|plus|computar"

_CARGO_ABOGACIA = (r"\b(abogad|letrad|relator|funcionari|procurador|mediador|"
                   r"defensor|juez|jueza|magistrad|tecnico juridico|asesor[a]? de familia|"
                   r"fiscal general|fiscal adjunt)"
                   r"|\bsecretari[oa]\b(?!\s+administrativ)")
_CARGO_UNIV = (r"\b(profesional|licenciad|psicolog|trabajador[a]? social|medic[oa]|"
               r"contador|ingenier|arquitect|bioquimic|perito|odontolog|psicopedagog|"
               r"kinesiolog|jerarquic)")
_CARGO_SIN_TITULO = (r"\b(auxiliar|oficial|escribiente|ordenanza|maestranza|chofer|"
                     r"mayordom|portero|sereno|limpieza|mantenimiento|administrativ)")


_ACEPTA_ESTUDIANTES = (r"estudiante|alumn[oa] regular|materias aprobadas|cursando|"
                       r"avance de (?:la )?carrera|% de la carrera")


def lineas_requisitos(requisitos):
    """Separa los requisitos en (obligatorios, 'se valorará')."""
    req = normalizar(requisitos)
    lineas = [l.strip() for l in re.split(r"[.\n;•]|\s-\s|\b[a-h]\)", req) if l.strip()]
    opcionales = [l for l in lineas if re.search(_OPCIONAL, l)]
    obligatorias = [l for l in lineas if l not in opcionales]
    return obligatorias, opcionales


def acepta_estudiantes(requisitos):
    return any(re.search(_ACEPTA_ESTUDIANTES, l) for l in lineas_requisitos(requisitos)[0])


def menciona_area(texto, palabras):
    t = normalizar(texto)
    return any(normalizar(p) in t for p in palabras)


def titulo_requerido(cargo="", requisitos="", agrupamiento=None):
    """
    Devuelve (nivel, seguro): nivel es None (secundario alcanza), "terciario",
    "universitario" o "abogacia"; seguro dice si salió de los requisitos
    escritos o es una inferencia por el nombre del cargo.
    """
    if agrupamiento == "tp_a":
        return "universitario", True
    if agrupamiento in ("tp_b", "asistencial"):
        return "terciario", True

    if requisitos:
        texto = " ".join(lineas_requisitos(requisitos)[0])
        if re.search(_REQ_ABOGACIA, texto):
            return "abogacia", True
        if re.search(_REQ_UNIV, texto):
            return "universitario", True
        if re.search(_REQ_TERC, texto):
            return "terciario", True
        if re.search(r"secundari|nivel medio|estudios medios|polimodal", texto):
            return None, True

    c = normalizar(cargo)
    if re.search(_CARGO_ABOGACIA, c):
        return "abogacia", False
    if re.search(_CARGO_UNIV, c):
        return "universitario", False
    if re.search(_CARGO_SIN_TITULO, c):
        return None, False
    return None, False


def cumple_titulo(titulos, requerido):
    """titulos None = no se sabe (no se filtra)."""
    if requerido is None or titulos is None:
        return True
    tiene = max((NIVELES_TITULO.get(t, 0) for t in titulos), default=0)
    if requerido == "abogacia":
        return "abogacia" in titulos
    return tiene >= NIVELES_TITULO[requerido]


# --------------------------------------------------------------------------
# A quién le sirve
# --------------------------------------------------------------------------

def _fuerza_por_ciudad(item, persona, locales):
    ciudades = item.get("ciudades") or []
    if not ciudades:
        return "normal", ["No se pudo leer la ciudad. Revisalo en el llamado."]
    if any(c in locales for c in ciudades):
        return "fuerte", []
    pref = persona.get("otras_ciudades", "suave")
    if pref == "no":
        return "pagina", []
    if pref == "fuerte":
        return "fuerte", []
    return "suave", []


def evaluar(item, persona, locales):
    """
    Decide qué hacer con un concurso para una persona. locales es el conjunto
    de ciudades que cuentan como "acá" (Comodoro y alrededores).

    Devuelve None si no le corresponde (no aparece en su vista), o un dict:
      nivel: "fuerte" (aviso con sonido), "normal", "suave" (aviso
             silencioso), "seguir" (solo en la página: puede abrirse más
             adelante) o "pagina" (solo en la página: no cumple algo)
      motivo: frase corta que explica por qué le sirve o no
      notas: advertencias para revisar
    """
    inst = item.get("instancia")
    notas = []
    ciudades = item.get("ciudades") or []

    if item["ambito"] == "judicial":
        if not persona.get("judiciales"):
            return None
        if inst != "abierto":
            return None
        motivo = "Abierto a la comunidad"
    else:
        nd = persona.get("nodocente")
        cat = item.get("categoria")
        if nd is None:
            if inst != "abierto":
                return None
            motivo = "Abierto al público"
        else:
            if cat is not None and cat >= nd["categoria"]:
                return None                     # no es ascenso
            if cat is None:
                notas.append("No se pudo leer la categoría.")
            en_mi_sede = nd["sede"] in ciudades
            mia = item.get("dependencia") == nd["dependencia"]
            if inst in ("abierto", "general"):
                motivo = INSTANCIAS[inst]
            elif inst == "sede":
                if ciudades and not en_mi_sede:
                    return None
                if en_mi_sede:
                    motivo = "Cerrado por sede " + nd["sede"]
                else:
                    motivo = "Cerrado por sede"
                    notas.append("No se pudo leer de qué sede es: puede ser la tuya.")
            elif inst == "interno":
                if mia:
                    motivo = "Cerrado interno de tu dependencia"
                elif en_mi_sede or not ciudades:
                    return {"nivel": "seguir",
                            "motivo": "Cerrado interno de otra dependencia: si queda "
                                      "desierto, pasa a otra instancia donde podrías entrar.",
                            "notas": notas}
                else:
                    return None
            else:
                motivo = "Tipo de concurso sin identificar"
                notas.append("No se pudo leer si es abierto, general, por sede o interno.")

    requerido = item.get("titulo_requerido")
    estudios = persona.get("estudios") or {}
    area = estudios.get("area", [])
    req_txt = item.get("requisitos") or ""
    if requerido and not cumple_titulo(persona.get("titulos"), requerido):
        if estudios and req_txt and acepta_estudiantes(req_txt):
            notas.append("Acepta estudiantes: revisá cuántas materias aprobadas pide.")
        elif estudios and menciona_area(req_txt + " " + item.get("titulo", ""), area):
            return {"nivel": "pagina",
                    "motivo": "Pide " + NOMBRE_TITULO[requerido] + " de tu carrera",
                    "notas": notas + ["Te va a servir cuando te recibas."]}
        else:
            return {"nivel": "pagina", "motivo": "Pide " + NOMBRE_TITULO[requerido],
                    "notas": notas}
    if estudios and req_txt:
        opcionales = lineas_requisitos(req_txt)[1]
        if any(menciona_area(l, area) or "estudiante" in l for l in opcionales):
            notas.append("Valoran estudios afines a tu carrera: te suma.")
    if requerido and persona.get("titulos") is None:
        notas.append("Pide " + NOMBRE_TITULO[requerido] + ".")

    nd = persona.get("nodocente")
    if item["ambito"] == "nodocente" and nd:
        ag = item.get("agrupamiento")
        if ag and nd.get("agrupamiento") and ag != nd["agrupamiento"]:
            notas.append("Es de otro agrupamiento (" + AGRUPAMIENTOS[ag] + ").")

    if item["ambito"] == "judicial" and not item.get("requisitos") and not requerido:
        notas.append("Revisá los requisitos en el llamado.")

    nivel, notas_ciudad = _fuerza_por_ciudad(item, persona, locales)
    return {"nivel": nivel, "motivo": motivo, "notas": notas + notas_ciudad}
