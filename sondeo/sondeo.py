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
    # Rectorado: variantes para entender la redireccion 307 -> 404
    "r_nofollow": "https://www.unp.edu.ar/index.php/webmail-2/concursos",
    "r_curl": "https://www.unp.edu.ar/index.php/webmail-2/concursos",
    "r_googlebot": "https://www.unp.edu.ar/index.php/webmail-2/concursos",
    "r_print": "https://www.unp.edu.ar/index.php?option=com_content&view=article&id=4671&tmpl=component&print=1",
    "r_nosef": "https://www.unp.edu.ar/index.php?option=com_content&view=article&id=4671",
    "r_cat133": "https://www.unp.edu.ar/index.php/133-concursos",
    # Economicas, sitio nuevo
    "fce_nodocentes": "https://www.fce.unp.edu.ar/no-docentes",
    # Digesto SUDOCU: consulta publica sin usuario
    "dig_cont": "https://huarpe.unp.edu.ar/sudocu/api/mpd/contenedores/",
    "dig_cont2": "https://huarpe.unp.edu.ar/sudocu/api/mpd/contenedores/?usuario=&id_area=",
    "dig_tipos": "https://huarpe.unp.edu.ar/sudocu/api/mpd/tipos",
    "dig_ver": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/getVersionUnloggedUser",
    "dig_guest1": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/documentos?idContenedor=1&offset=0&limit=10&dir=DESC&orden=nombre_plural",
    "dig_guest_t": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/documentos?idContenedor=1&offset=0&limit=10&dir=DESC&txtBusquedaTitulo=concurso",
}

VARIANTES_UA = {
    "_curl": "curl/8.5.0",
    "_googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
}


def bajar(sesion, url, verificar=True, clave=""):
    headers = {}
    for suf, ua in VARIANTES_UA.items():
        if clave.endswith(suf):
            headers["User-Agent"] = ua
    seguir = not clave.endswith("_nofollow")
    return sesion.get(url, timeout=60, allow_redirects=seguir, verify=verificar,
                      headers=headers)


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
                    r = bajar(s, url, clave=clave)
                except requests.exceptions.SSLError as e:
                    info["ssl_error"] = str(e)[:300]
                    urllib3.disable_warnings()
                    r = bajar(s, url, verificar=False, clave=clave)
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
                    headers={k: v for k, v in r.headers.items()
                             if k.lower() in ("location", "set-cookie", "server",
                                              "content-type", "x-powered-by", "cache-control")},
                    cookies=list(s.cookies.keys()),
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
