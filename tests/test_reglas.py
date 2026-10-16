"""
Pruebas de reglas.py con textos tal como aparecen en las páginas reales.

    python -m unittest discover -s tests
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reglas  # noqa: E402

D = date
LOCALES = {"Comodoro Rivadavia", "Rada Tilly"}
# Perfiles fijos para las pruebas (independientes de config.py, que puede cambiar).
CRISTIAN = {
    "id": "cristian", "judiciales": False, "titulos": None, "otras_ciudades": "suave",
    "nodocente": {"categoria": 7, "agrupamiento": "administrativo",
                  "dependencia": "fcnycs", "sede": "Comodoro Rivadavia"},
}
BIANCA = {
    "id": "bianca", "nodocente": None, "judiciales": True, "titulos": [], "otras_ciudades": "suave",
    "estudios": {"carrera": "Licenciatura en Administración",
                 "area": ["administracion", "ciencias economicas", "contador", "contable"]},
}


class Fechas(unittest.TestCase):
    CASOS = [
        # MPF del Chubut
        ("Fecha de inscripción: 13 y 14 de octubre de 2026", 2026, D(2026, 10, 13), D(2026, 10, 14)),
        ("Fecha de inscripción: 05, 06 y 07 de Octubre de 2026", 2026, D(2026, 10, 5), D(2026, 10, 7)),
        ("Fechas de inscipción: 28 de septiembre al 9 de octubre de 2026", 2026, D(2026, 9, 28), D(2026, 10, 9)),
        ("Fecha de inscripción: 17, 18 y 19 de septiembre de 2026 de 08:00 a 13:00 horas", 2026,
         D(2026, 9, 17), D(2026, 9, 19)),
        ("Inscripciones: día 6 al 20 de agosto de 2026.", 2026, D(2026, 8, 6), D(2026, 8, 20)),
        ("Fecha de inscripción: 16 al 30 de junio.", 2026, D(2026, 6, 16), D(2026, 6, 30)),
        ("Fecha de inscripción: 26 de mayo al 6 de junio.", 2026, D(2026, 5, 26), D(2026, 6, 6)),
        ("Fecha de Inscripción: 06 y 07 de agosto de 2026, de 08,00 a 13,00 hs.", 2026,
         D(2026, 8, 6), D(2026, 8, 7)),
        ("Fecha de inscripción desde el día 27 de julio al 07 de agosto de 2026", 2026,
         D(2026, 7, 27), D(2026, 8, 7)),
        ("Inscripciones: del 31 de marzo al 15 de abril de 2026 en el horario de 08 a 13 horas.", 2026,
         D(2026, 3, 31), D(2026, 4, 15)),
        ("Las postulaciones serán recibidas desde el día 4 al 17 de marzo de 2026.", 2026,
         D(2026, 3, 4), D(2026, 3, 17)),
        ("Incripciones: del 22 de agosto al 4 de septiembre de 2025", 2025, D(2025, 8, 22), D(2025, 9, 4)),
        ("Postulaciones hasta el día 6 de marzo a las 13hs.", 2019, None, D(2019, 3, 6)),
        # Defensa Pública
        ("APERTURA Y CIERRE DE INSCRIPCIÓN: Los días comprendidos entre desde el 9 y el 23 de "
         "octubre del año 2026 hasta las 13:00 hs.", 2026, D(2026, 10, 9), D(2026, 10, 23)),
        ("APERTURA Y CIERRE DE INSCRIPCIÓN: Los días comprendidos entre el 23 de septiembre y el "
         "3 de octubre del año 2026.", 2026, D(2026, 9, 23), D(2026, 10, 3)),
        ("INSCRIPCIÓN: Los días comprendidos entre el 26 de diciembre de 2025 y el 04 de enero de 2026.",
         2025, D(2025, 12, 26), D(2026, 1, 4)),
        # UNPSJB
        ("FECHA DE INSCRIPCIÓN: 07/10/2026 hasta 14/10/2026 LUGAR: Comodoro Rivadavia", 2026,
         D(2026, 10, 7), D(2026, 10, 14)),
        ("INSCRIPCIÓN: 28/09 al 02/10/2026", 2026, D(2026, 9, 28), D(2026, 10, 2)),
        # Defensoría de la Nación
        ("inscripcion CONCURSO Nº 225: ... (Del 22/6/26 al 8/7/26)", 2026, D(2026, 6, 22), D(2026, 7, 8)),
    ]

    def test_ventanas(self):
        for texto, anio, desde, hasta in self.CASOS:
            with self.subTest(texto=texto):
                self.assertEqual(reglas.fechas_inscripcion(texto, anio), (desde, hasta))

    def test_no_toma_fechas_fuera_de_la_inscripcion(self):
        texto = "Resolución 531/2026 del 04/09/2026. Examen: 15/10/2026."
        self.assertEqual(reglas.fechas_inscripcion(texto, 2026), (None, None))

    def test_estado(self):
        hoy = D(2026, 10, 16)
        self.assertEqual(reglas.estado_inscripcion(D(2026, 10, 20), D(2026, 10, 29), hoy), "por_abrir")
        self.assertEqual(reglas.estado_inscripcion(D(2026, 10, 9), D(2026, 10, 23), hoy), "abierta")
        self.assertEqual(reglas.estado_inscripcion(D(2026, 10, 1), D(2026, 10, 7), hoy), "cerrada")
        self.assertEqual(reglas.estado_inscripcion(None, None, hoy), "sin_fecha")


class Lectura(unittest.TestCase):
    def test_instancia(self):
        casos = {
            "LLAMADOS A CONCURSO INTERNO CERRADO": "interno",
            "LLAMADOS A CONCURSO ABIERTO": "abierto",
            "Llamar a Concurso Cerrado por Sede para cubrir un cargo": "sede",
            "CONCURSO CERRADO GENERAL para la cobertura de 1 (un) cargo": "general",
            "Concurso cerrado interno cat. 7 AAPP – Área Económica Financiera FHCS": "interno",
            "llama a concurso abierto a la comunidad de antecedentes y oposición": "abierto",
            "Concurso Abierto Cat 7, habiéndose declarado desierto el cerrado general": "abierto",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(reglas.detectar_instancia(texto), esperado)

    def test_categoria(self):
        self.assertEqual(reglas.detectar_categoria("Administrativo Tramo Intermedio (Cat. 04)"), 4)
        self.assertEqual(reglas.detectar_categoria("cargo Categoría 05; Agrupamiento"), 5)
        self.assertEqual(reglas.detectar_categoria("Concurso cerrado interno cat. 7 AAPP"), 7)
        self.assertIsNone(reglas.detectar_categoria("Res. R/11 Nº 575/2026"))

    def test_agrupamiento(self):
        self.assertEqual(reglas.agrupamiento_de_celda('Técnico Profesional "B" Tramo Inicial (Cat. 06)'), "tp_b")
        self.assertEqual(reglas.agrupamiento_de_celda("Administrativo Tramo Mayor (Cat. 03)"), "administrativo")
        self.assertEqual(reglas.agrupamiento_de_celda("Mantenimiento, Producción y Serv. Grales."), "mantenimiento")
        self.assertEqual(reglas.detectar_agrupamiento("Concurso cerrado interno cat. 5 AAPP – Area"), "administrativo")
        self.assertEqual(reglas.detectar_agrupamiento(
            "cargo dentro del Agrupamiento Técnico Profesional “A” en el área de Informática"), "tp_a")

    def test_ciudades(self):
        self.assertEqual(reglas.detectar_ciudades("Delegación Zonal Sede Esquel (Biblioteca)"), ["Esquel"])
        self.assertEqual(reglas.detectar_ciudades("Dirección Adminstración - Superior Tribunal"), ["Rawson"])
        self.assertEqual(reglas.detectar_ciudades("OUMPF Pto Madryn, C. Rivadavia y Lago Puelo"),
                         ["Puerto Madryn", "Comodoro Rivadavia", "Lago Puelo"])

    def test_titulo_por_requisitos(self):
        req = ("serán requisitos: a) Poseer título universitario de grado de Abogado/a, legalizado...")
        self.assertEqual(reglas.titulo_requerido("Coordinador Ejecutivo", req)[0], "abogacia")
        req = "a) Poseer título universitario de grado en Ciencias Económicas"
        self.assertEqual(reglas.titulo_requerido("Profesional Jerárquico", req)[0], "universitario")
        req = "c) Acreditar estudios primarios completos. Se valorará ser estudiante de Abogacía."
        self.assertIsNone(reglas.titulo_requerido("Auxiliar Superior", req)[0])

    def test_titulo_por_cargo(self):
        self.assertEqual(reglas.titulo_requerido("Abogado/a Adjunto/a")[0], "abogacia")
        self.assertEqual(reglas.titulo_requerido("Llamado a concurso Funcionario/a de Fiscalía")[0], "abogacia")
        self.assertEqual(reglas.titulo_requerido("Profesional B")[0], "universitario")
        self.assertIsNone(reglas.titulo_requerido("Prosecretario Administrativo")[0])
        self.assertIsNone(reglas.titulo_requerido(
            "Llamado a concurso Auxiliar Administrativo para la OUMPF (un cargo)")[0])


class Resoluciones(unittest.TestCase):
    """Fragmentos de resoluciones de llamado reales (UNPSJB, 2026)."""

    BIBLIOTECA = (
        "FECHA DE INSCRIPCIÓN: 27/10/2026 hasta 02/11/2026 FECHA DE IMPUGNACIÓN Y OBSERVACIONES: "
        "04/11/2026 hasta 10/11/2026 REQUISITOS: -Lugar de trabajo: Biblioteca Central de la UNPSJB "
        "Comodoro Rivadavia. -Horario de trabajo: lunes a viernes de 14:00 a 21:00 hs. -Cumplir con "
        "todo lo dispuesto en la Ordenanza Digital Consejo Superior N° 210: a) Tener como mínimo "
        "DIECIOCHO (18) años. -Poseer titulo secundario completo (excluyente). -Poseer título "
        "profesional de bibliotecario emitido por una institución oficial de nivel superior "
        "(terciaria o universitaria) de 3 (tres) años o más de duración (excluyente). -Presentación "
        "de un CV ACTUALIZADO (excluyente). PERFIL DEL CARGO: El técnico superior especializado...")
    CIENCIA = (
        "REQUISITOS GENERALES: -Serán requisitos generales para el ingreso o promoción, los "
        "establecidos en la Ordenanza Digital Consejo Superior Nº 210, Art. 3. -Lugar de trabajo: "
        "Sede Comodoro Rivadavia. -Título del Nivel Secundario (Excluyente). -Título en Tecnicatura "
        "Universitaria en Gestión y Administración de Universidades (No Excluyente). PERFIL DEL CARGO: -Actitud")
    HUMANIDADES = (
        "Art. 2º) Establecer los tiempos: - 1 al 22 de octubre de 2026: difusión del concurso; "
        "- 23 al 29 de octubre de 2026: inscripción, a realizarse en la oficina de despacho. "
        "- 30 de octubre al 5 de noviembre de 2026: período de impugnación. Art. 4º) Los "
        "requisitos para postularse al llamado presente serán los que siguen: - Lugar de trabajo: "
        "Comodoro Rivadavia, Chubut; - Estudios Secundarios Completos (Excluyente); -Estudios "
        "universitarios/terciarios (no excluyente); Art. 5º) Recomendar aspectos")
    REMITE = ("Art. 3°) El jurado, los aspectos constitutivos del puesto para la categoría, los "
              "requisitos para postularse, los aspectos constitutivos del perfil y la recomendación "
              "de aproximaciones de temas para el concurso son los estipulados por la Resolución "
              "Digital D/12 FHyCS N° 753/2025. Art. 4°) Regístrese")

    def test_biblioteca(self):
        req = reglas.requisitos_resolucion(self.BIBLIOTECA)
        self.assertEqual(len(req["excluyentes"]), 1)
        self.assertIn("bibliotecario", req["excluyentes"][0])
        self.assertEqual(req["horario"], "lunes a viernes de 14:00 a 21:00 hs")
        self.assertEqual(reglas.titulo_de_excluyentes(req["excluyentes"]), "terciario")
        self.assertEqual(reglas.fechas_inscripcion(self.BIBLIOTECA, 2026), (D(2026, 10, 27), D(2026, 11, 2)))

    def test_no_excluyentes_suman(self):
        req = reglas.requisitos_resolucion(self.CIENCIA)
        self.assertEqual(req["excluyentes"], [])
        self.assertEqual(len(req["suman"]), 1)
        self.assertIsNone(reglas.titulo_de_excluyentes(req["excluyentes"]))

    def test_humanidades(self):
        req = reglas.requisitos_resolucion(self.HUMANIDADES)
        self.assertEqual(req["excluyentes"], [])
        self.assertEqual(req["suman"], ["Estudios universitarios/terciarios"])
        self.assertEqual(reglas.fechas_inscripcion(self.HUMANIDADES, 2026), (D(2026, 10, 23), D(2026, 10, 29)))

    def test_remite_a_otra_resolucion(self):
        self.assertEqual(reglas.requisitos_resolucion(self.REMITE)["remite"], "753/2025")

    def test_excluyente_en_la_evaluacion(self):
        req = reglas.requisitos_resolucion(self.BIBLIOTECA)
        item = {"ambito": "nodocente", "titulo": "Técnico/a Superior en Biblioteca", "instancia": "abierto",
                "categoria": 5, "ciudades": ["Comodoro Rivadavia"], "req": req,
                "titulo_requerido": reglas.titulo_de_excluyentes(req["excluyentes"])}
        ev = reglas.evaluar(item, CRISTIAN, LOCALES)       # sin títulos cargados: avisa y advierte
        self.assertEqual(ev["nivel"], "fuerte")
        self.assertTrue(ev["notas"][0].startswith("Excluyente: Poseer título profesional de bibliotecario"))
        ev = reglas.evaluar(item, BIANCA, LOCALES)         # sin ese título: solo en la página
        self.assertEqual(ev["nivel"], "pagina")
        self.assertEqual(ev["motivo"], "Pide un título excluyente")


def aviso(**campos):
    base = {"ambito": "nodocente", "titulo": "Cargo", "ciudades": ["Comodoro Rivadavia"]}
    base.update(campos)
    return base


class ParaQuien(unittest.TestCase):
    def nivel(self, item, persona):
        ev = reglas.evaluar(item, persona, LOCALES)
        return ev["nivel"] if ev else None

    def test_cristian(self):
        # Ascenso en Comodoro en instancias donde puede inscribirse: suena.
        for inst in ("abierto", "general", "sede"):
            self.assertEqual(self.nivel(aviso(instancia=inst, categoria=5), CRISTIAN), "fuerte")
        self.assertEqual(self.nivel(aviso(instancia="interno", categoria=4, dependencia="fcnycs"),
                                    CRISTIAN), "fuerte")
        # Cerrado interno de otra dependencia en Comodoro: para seguir, sin aviso.
        self.assertEqual(self.nivel(aviso(instancia="interno", categoria=4, dependencia="rectorado"),
                                    CRISTIAN), "seguir")
        # Categoría 7 no es ascenso; por sede de otra ciudad no lo habilita.
        self.assertIsNone(self.nivel(aviso(instancia="abierto", categoria=7), CRISTIAN))
        self.assertIsNone(self.nivel(aviso(instancia="sede", categoria=5, ciudades=["Trelew"]), CRISTIAN))
        # Abierto en otra ciudad: aviso silencioso.
        self.assertEqual(self.nivel(aviso(instancia="abierto", categoria=6, ciudades=["Esquel"]), CRISTIAN),
                         "suave")
        # Lo judicial no le corresponde.
        self.assertIsNone(self.nivel(aviso(ambito="judicial", instancia="abierto"), CRISTIAN))

    def test_bianca(self):
        self.assertEqual(self.nivel(aviso(ambito="judicial", instancia="abierto"), BIANCA), "fuerte")
        self.assertEqual(self.nivel(aviso(ambito="judicial", instancia="abierto", ciudades=["Trelew"]),
                                    BIANCA), "suave")
        self.assertEqual(self.nivel(aviso(ambito="judicial", instancia="abierto",
                                          titulo_requerido="abogacia"), BIANCA), "pagina")
        self.assertIsNone(self.nivel(aviso(ambito="judicial", instancia="cerrado"), BIANCA))
        # Universidad: solo abiertos, y que no pidan título.
        self.assertEqual(self.nivel(aviso(instancia="abierto", categoria=7), BIANCA), "fuerte")
        self.assertEqual(self.nivel(aviso(instancia="abierto", categoria=5, titulo_requerido="terciario"),
                                    BIANCA), "pagina")
        self.assertIsNone(self.nivel(aviso(instancia="general", categoria=5), BIANCA))

    def test_bianca_estudiante(self):
        # Pide título pero acepta estudiantes: le avisa, con nota.
        req = "a) Título universitario de grado o ser estudiante avanzado con 20 materias aprobadas."
        ev = reglas.evaluar(aviso(ambito="judicial", instancia="abierto", requisitos=req,
                                  titulo_requerido="universitario"), BIANCA, LOCALES)
        self.assertEqual(ev["nivel"], "fuerte")
        self.assertTrue(any("estudiantes" in n for n in ev["notas"]))
        # Pide el título de su carrera: en la página, marcado como de su carrera.
        req = "a) Poseer título universitario de grado en Ciencias Económicas, legalizado."
        ev = reglas.evaluar(aviso(ambito="judicial", instancia="abierto", requisitos=req,
                                  titulo_requerido="universitario"), BIANCA, LOCALES)
        self.assertEqual(ev["nivel"], "pagina")
        self.assertIn("de tu carrera", ev["motivo"])
        # Valoran estudios afines y no pide título: le avisa y le dice que suma.
        req = "a) Estudios secundarios completos. b) Se valorará ser estudiante de Administración."
        ev = reglas.evaluar(aviso(ambito="judicial", instancia="abierto", requisitos=req),
                            BIANCA, LOCALES)
        self.assertEqual(ev["nivel"], "fuerte")
        self.assertTrue(any("te suma" in n for n in ev["notas"]))


if __name__ == "__main__":
    unittest.main()
