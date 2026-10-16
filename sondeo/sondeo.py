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
    # Rectorado: la direccion de siempre redirige a un 404
    "r_http": "http://www.unp.edu.ar/index.php/webmail-2/concursos",
    "r_sinwww": "https://unp.edu.ar/index.php/webmail-2/concursos",
    "r_nodocente": "https://www.unp.edu.ar/index.php/component/content/article?id=4671",
    "r_buscar": "https://www.unp.edu.ar/index.php?option=com_search&searchword=concurso&searchphrase=all&ordering=newest&limit=50",
    "r_finder": "https://www.unp.edu.ar/index.php/component/finder/search?q=concurso",
    "r_feed": "https://www.unp.edu.ar/index.php?format=feed&type=rss",
    "r_docentes": "https://www.unp.edu.ar/index.php/2-uncategorised/5418-concursos-docentes",
    # Economicas se mudo a fce.unp.edu.ar
    "fce_home": "https://www.fce.unp.edu.ar/",
    "fce_wp_posts": "https://www.fce.unp.edu.ar/wp-json/wp/v2/posts?search=concurso&per_page=20",
    "fce_wp_pages": "https://www.fce.unp.edu.ar/wp-json/wp/v2/pages?search=concurso&per_page=20",
    "fce_wordpress": "https://www.fce.unp.edu.ar/wordpress/",
    # Defensa Publica del Chubut
    "def_concursos": "https://www.defensachubut.gov.ar/?page_id=11595",
    "def_wp_page": "https://www.defensachubut.gov.ar/wp-json/wp/v2/pages/11595",
    "def_wp_posts": "https://www.defensachubut.gov.ar/wp-json/wp/v2/posts?search=concurso&per_page=20",
    # Defensoria General de la Nacion (ingreso por jurisdiccion)
    "mpd_vigentes": "https://www.mpd.gov.ar/index.php/secretaria-de-concursos-n/inscripciones-vigentes",
    "mpd_tecadm": "https://www.mpd.gov.ar/index.php/secretaria-de-concursos-n/agrupamiento-tecnico-administrativo-c",
    "mpd_servaux": "https://www.mpd.gov.ar/index.php/secretaria-de-concursos-n/agrupamiento-servicios-auxiliares-c",
    "mpd_ingreso": "https://www.mpd.gov.ar/index.php/ingreso-democratico",
    # MPF de la Nacion (la primera vez dio 500)
    "mpfn_ingreso": "https://www.mpf.gob.ar/ingreso-democratico/",
    "fiscales_buscar": "https://www.fiscales.gob.ar/?s=ingreso+democratico",
    "fiscales_wp": "https://www.fiscales.gob.ar/wp-json/wp/v2/posts?search=concurso%20ingreso&per_page=20",
    # Digesto SUDOCU: buscar como consulta los documentos
    "dig_js": "https://huarpe.unp.edu.ar/sudocu/mpd/mpd.min.js",
}


def bajar(sesion, url, verificar=True):
    return sesion.get(url, timeout=60, allow_redirects=True, verify=verificar)


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
