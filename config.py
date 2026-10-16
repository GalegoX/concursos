"""
Configuración del monitor de concursos.

Es el único archivo que hace falta tocar a mano. Si cambia la situación de
alguno de los dos (asciende, cambia de sede, termina una carrera), se edita
acá y en la próxima revisión ya filtra con los datos nuevos.
"""

# Ciudad donde viven. Lo que salga acá (o en las cercanas) avisa con sonido.
# Lo de otras ciudades depende de "otras_ciudades" en cada persona.
CIUDAD = "Comodoro Rivadavia"
CERCANAS = ["Rada Tilly"]

# Dirección de la página publicada (se usa en los avisos).
PAGINA = "https://galegox.github.io/concursos/"

PERSONAS = [
    {
        "id": "galego",
        "nombre": "Galego",
        # Nombre del secreto de GitHub donde está su canal de ntfy.
        "secreto_ntfy": "NTFY_GALEGO",
        # Situación de revista como nodocente de la UNPSJB.
        # None si no es nodocente (entonces solo le sirven los abiertos).
        "nodocente": {
            "categoria": 7,
            "agrupamiento": "administrativo",
            # Dependencia donde trabaja: habilita los cerrados internos de ahí.
            "dependencia": "fcnycs",
            # Sede donde trabaja: habilita los cerrados por sede de esa ciudad.
            "sede": "Comodoro Rivadavia",
        },
        # True si quiere avisos de concursos judiciales abiertos a la comunidad.
        "judiciales": False,
        # Títulos terminados, para los cargos que piden título.
        #   None  = no filtrar por título (avisa igual, con una nota)
        #   []    = secundario completo
        #   o una lista con "terciario", "universitario" y/o "abogacia".
        "titulos": None,
        # Concursos de otras ciudades: "suave" (aviso silencioso),
        # "no" (solo en la página) o "fuerte" (igual que los de acá).
        "otras_ciudades": "suave",
        # Recibe los avisos de mantenimiento (por ejemplo, si una página
        # deja de poder leerse y hay que revisar el monitor).
        "avisos_tecnicos": True,
    },
    {
        "id": "bianca",
        "nombre": "Bianca",
        "secreto_ntfy": "NTFY_BIANCA",
        # Externa a la universidad: solo concursos abiertos al público.
        "nodocente": None,
        "judiciales": True,
        # Secundario completo, sin título terciario ni universitario.
        "titulos": [],
        # Carrera en curso: hace que avisen los llamados que aceptan
        # estudiantes y marca los que piden o valoran estudios de su área.
        "estudios": {
            "carrera": "Licenciatura en Administración (con materias aprobadas)",
            "area": ["administracion", "ciencias economicas", "contador", "contable"],
        },
        "otras_ciudades": "suave",
        "avisos_tecnicos": False,
    },
]

# Páginas que se revisan. "lector" indica cómo se lee cada una (fuentes.py).
# Si una página se muda de dirección, se cambia la url acá.
FUENTES = [
    # --- Universidad (UNPSJB), concursos nodocentes ---
    {
        "id": "rectorado",
        "nombre": "UNPSJB, Rectorado",
        "ambito": "nodocente",
        "lector": "rectorado",
        "dependencia": "rectorado",
        # El Rectorado está en Comodoro; las delegaciones dicen su ciudad.
        "ciudad_por_defecto": "Comodoro Rivadavia",
        # El sitio de la UNP a veces tarda mucho en responder.
        "timeout": 90,
        "url": "https://www.unp.edu.ar/index.php/webmail-2/concursos",
    },
    {
        "id": "ingenieria",
        "nombre": "UNPSJB, Facultad de Ingeniería",
        "ambito": "nodocente",
        "lector": "ingenieria",
        "dependencia": "ingenieria",
        "timeout": 90,
        "url": "https://www.unp.edu.ar/ingenieria/index.php/es/nodocentes/342-personal-nodocente-concursos",
    },
    {
        "id": "fcnycs",
        "nombre": "UNPSJB, Facultad de Cs. Naturales y Cs. de la Salud",
        "ambito": "nodocente",
        "lector": "wordpress",
        "dependencia": "fcnycs",
        "url": "https://www.fcn.unp.edu.ar/",
    },
    {
        "id": "humanidades",
        "nombre": "UNPSJB, Facultad de Humanidades y Cs. Sociales",
        "ambito": "nodocente",
        "lector": "wordpress",
        "dependencia": "humanidades",
        "url": "https://www.fhcs.unp.edu.ar/",
    },
    {
        # Red de seguridad: resoluciones publicadas en el digesto (SUDOCU)
        # de unidades que no tienen una página de concursos, más las del
        # Rector y las de tu facultad por si no se anuncian en la web.
        "id": "digesto",
        "nombre": "UNPSJB, Digesto de resoluciones",
        "ambito": "nodocente",
        "lector": "digesto",
        "url": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/documentos",
        # carpeta del digesto: (dependencia, ciudad si la carpeta la implica)
        "carpetas": {
            38: ("rectorado", None),           # Resoluciones digitales R/11
            22: ("fcnycs", None),              # FCNyCS, Resoluciones Decano
            15: ("economicas", None),          # FCE, Resoluciones Decano
            17: ("economicas", None),          # FCE, Resoluciones Consejo Directivo
            24: ("juridicas", None),           # FCJ, Resoluciones digitales
            25: ("juridicas", None),           # FCJ, Ad referéndum
            33: ("delegacion_comodoro", "Comodoro Rivadavia"),
            36: ("delegacion_trelew", "Trelew"),
            34: ("delegacion_madryn", "Puerto Madryn"),
            35: ("delegacion_esquel", "Esquel"),
        },
    },
    # --- Justicia del Chubut ---
    {
        "id": "judicial",
        "nombre": "Poder Judicial del Chubut",
        "ambito": "judicial",
        "lector": "judicial",
        "url": "https://apps1cloud.juschubut.gov.ar/concursos/pages/listadoconcursos.aspx",
    },
    {
        "id": "mpf",
        "nombre": "Ministerio Público Fiscal del Chubut",
        "ambito": "judicial",
        "lector": "mpf",
        "url": "https://www.mpfchubut.gov.ar/ciudadano/concursos",
    },
    {
        "id": "defensa",
        "nombre": "Defensa Pública del Chubut",
        "ambito": "judicial",
        "lector": "defensa",
        "url": "https://www.defensachubut.gov.ar/?page_id=11595",
    },
    {
        # Nacional: solo se toman los que mencionan ciudades de la zona.
        "id": "defensoria_nacion",
        "nombre": "Defensoría General de la Nación",
        "ambito": "judicial",
        "lector": "mpd_nacion",
        "url": "https://www.mpd.gov.ar/index.php/secretaria-de-concursos-n/inscripciones-vigentes",
    },
]
