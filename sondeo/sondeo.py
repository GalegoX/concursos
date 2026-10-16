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
    "dig_640": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/documentos?idContenedor=38&offset=0&limit=5&txtBusquedaNRO=640",
    "dig_575": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/documentos?idContenedor=38&offset=0&limit=5&txtBusquedaNRO=575",
    "dig_596": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/documentos?idContenedor=38&offset=0&limit=5&txtBusquedaNRO=596",
    "dig_38_concurso": "https://huarpe.unp.edu.ar/sudocu/api/mpd/guest/documentos?idContenedor=38&offset=0&limit=60&dir=DESC&txtBusquedaTitulo=concurso",
    "fhcs_ext_pdf": "https://www.fhcs.unp.edu.ar/wp-content/uploads/2026/10/AA-4-Sec-Ext.pdf",
    "fhcs_sede_pdf": "https://www.fhcs.unp.edu.ar/wp-content/uploads/2026/03/Concurso-Cat-5-AA-PP-por-sede-Docentes.pdf",
}

VARIANTES_UA = {}


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

    import glob
    from bs4 import BeautifulSoup
    for ruta in glob.glob("out/raw/dig_*.json"):
        try:
            datos = json.load(open(ruta, encoding="utf-8"))
        except Exception:
            continue
        for d in (datos.get("documents") or [])[:6]:
            base = ruta[:-5] + "_" + d["id"][:8]
            html = (d.get("atributos") or {}).get("contenido") or ""
            texto = " ".join(BeautifulSoup(html, "html.parser").get_text(" ").split())
            open(base + ".txt", "w", encoding="utf-8").write(d.get("titulo", "") + "\n\n" + texto)
            for nombre, archivo in [("adj_" + a[:8], a) for a in (d.get("archivos_adjuntos") or [])[:3]] + [("doc", d.get("documento"))]:
                if not archivo:
                    continue
                try:
                    r = s.get("https://huarpe.unp.edu.ar/sudocu/api/archivos/publico/" + archivo,
                              params={"id_archivo": archivo, "id_documento": d["id"]}, timeout=60)
                    open(f"{base}_{nombre}.bin", "wb").write(r.content)
                    resumen[f"{base}_{nombre}"] = {"status": r.status_code, "ctype": r.headers.get("content-type"), "size": len(r.content)}
                except Exception as e:
                    resumen[f"{base}_{nombre}"] = {"error": str(e)[:200]}

    with open("out/resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=1, ensure_ascii=False)

    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text
        print("IP del runner:", ip)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
