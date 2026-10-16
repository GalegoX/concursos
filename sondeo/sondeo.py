"""
Sondeo de fuentes: baja cada pagina candidata tal cual la ve un navegador
y guarda el HTML crudo para programar los lectores sobre la estructura real.
No es parte del monitor; se borra cuando terminan las pruebas.
"""
import json
import os
import sys
import time

import requests
import urllib3

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

URLS = {
    # Universidad
    "unp_rectorado": "https://www.unp.edu.ar/index.php/webmail-2/concursos",
    "unp_home": "https://www.unp.edu.ar/",
    "ing_concursos": "https://www.unp.edu.ar/ingenieria/index.php/es/nodocentes/342-personal-nodocente-concursos",
    "fce_concursos": "https://web.sistemasfce.com.ar/wordpress/index.php/concursos-nodocentes/",
    "fce_wp_pages": "https://web.sistemasfce.com.ar/wordpress/index.php/wp-json/wp/v2/pages?search=concurso&per_page=20",
    "fce_wp_posts": "https://web.sistemasfce.com.ar/wordpress/index.php/wp-json/wp/v2/posts?search=concurso&per_page=20",
    "fcn_home": "https://www.fcn.unp.edu.ar/",
    "fcn_wp_posts": "https://www.fcn.unp.edu.ar/wp-json/wp/v2/posts?search=concurso&per_page=20",
    "fcn_wp_pages": "https://www.fcn.unp.edu.ar/wp-json/wp/v2/pages?search=concurso&per_page=20",
    "fcn_feed": "https://www.fcn.unp.edu.ar/feed/",
    "fhcs_home": "https://www.fhcs.unp.edu.ar/",
    "fhcs_wp_posts": "https://www.fhcs.unp.edu.ar/wp-json/wp/v2/posts?search=concurso&per_page=30",
    "fhcs_feed": "https://www.fhcs.unp.edu.ar/feed/",
    "fhcs_concursos": "https://www.fhcs.unp.edu.ar/concursos/",
    "fhcs_post": "https://www.fhcs.unp.edu.ar/concurso-cerrado-interno-cat-5-aapp-area-administrativa-puerto-madryn-fhcs/",
    "fcj_a": "https://www.fcj.unp.edu.ar/",
    "fcj_b": "https://fcj.unp.edu.ar/",
    "fcj_c": "https://www.juridicas.unp.edu.ar/",
    "digesto_mpd": "https://huarpe.unp.edu.ar/sudocu/mpd/",
    "digesto_raiz": "https://huarpe.unp.edu.ar/sudocu/",
    # Justicia provincial
    "jus_listado": "https://apps1cloud.juschubut.gov.ar/concursos/pages/listadoconcursos.aspx",
    "jus_rrhh": "https://www.juschubut.gov.ar/organizacion/dependientes-administracion-general/direccion-de-recursos-humanos/llamados-a-concurso.html",
    "jus_servicios": "https://www.juschubut.gov.ar/servicios/concursos/",
    "mpf_concursos": "https://www.mpfchubut.gov.ar/ciudadano/concursos",
    "mpf_abiertos": "https://www.mpfchubut.gov.ar/concursos/concursos-abiertos",
    "defensa_a": "https://www.defensachubut.gov.ar/",
    "defensa_b": "https://defensachubut.gov.ar/",
    # Justicia nacional con sede en Comodoro
    "mpfn_ingreso": "https://www.mpf.gob.ar/ingreso-democratico/",
    "mpfn_feed": "https://www.mpf.gob.ar/ingreso-democratico/feed/",
    "mpfn_novedad": "https://www.mpf.gob.ar/ingreso-democratico/novedad/convocatoria-concurso-no-98-servicios-auxiliares-comodoro-rivadavia/",
    "mpd_home": "https://www.mpd.gov.ar/",
}


def bajar(sesion, url, verificar=True):
    return sesion.get(url, timeout=45, allow_redirects=True, verify=verificar)


def main():
    os.makedirs("out/raw", exist_ok=True)
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.5",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    resumen = {}
    for clave, url in URLS.items():
        t0 = time.time()
        info = {"url": url}
        for intento in range(2):
            try:
                try:
                    r = bajar(s, url)
                except requests.exceptions.SSLError as e:
                    info["ssl_error"] = str(e)[:300]
                    urllib3.disable_warnings()
                    r = bajar(s, url, verificar=False)
                    info["sin_verificar_ssl"] = True
                ctype = r.headers.get("content-type", "")
                ext = "json" if "json" in ctype else ("xml" if "xml" in ctype else "html")
                with open(f"out/raw/{clave}.{ext}", "wb") as f:
                    f.write(r.content)
                info.update(
                    status=r.status_code, final=r.url, ctype=ctype,
                    size=len(r.content), secs=round(time.time() - t0, 1),
                    server=r.headers.get("server"), encoding=r.encoding,
                    apparent=r.apparent_encoding, archivo=f"{clave}.{ext}",
                    historial=[h.status_code for h in r.history],
                )
                info.pop("error", None)
                break
            except Exception as e:
                info["error"] = f"{type(e).__name__}: {str(e)[:300]}"
                time.sleep(4)
        resumen[clave] = info
        print(f"{clave:16} {info.get('status', '---')} {info.get('size', 0):>8} "
              f"{info.get('secs', '')}s {info.get('error', '')}", flush=True)

    with open("out/resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=1, ensure_ascii=False)

    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text
        print("IP del runner:", ip)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
