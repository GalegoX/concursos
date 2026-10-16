# Concursos

Revisa siete veces por día las páginas de concursos de la UNPSJB y de la
justicia del Chubut. Cuando aparece un llamado que le sirve a alguno de los
dos, le manda un aviso al celular **a esa persona**, y lo muestra en una
página con una vista para cada uno:

- **Galego** (nodocente, cat. 7, administrativo, FCNyCS, Comodoro): ascensos
  en concursos abiertos, cerrados generales, cerrados por sede de Comodoro y
  cerrados internos de su facultad.
- **Bianca** (externa): concursos abiertos al público de la universidad y de
  la justicia que no pidan título, o que acepten estudiantes.

Lo de Comodoro suena; lo de otras ciudades llega en silencio.

Página: https://galegox.github.io/concursos/
(con `#galego` o `#bianca` al final abre directo la vista de cada uno).

---

## Puesta en marcha

### 1. Publicar la página

En el repositorio: **Settings → Pages → Source: Deploy from a branch →
Branch: `main` / `(root)` → Save**. En un par de minutos queda en la
dirección de arriba.

### 2. Instalar ntfy en los dos celulares

Es una app gratuita que solo sirve para recibir avisos; no pide cuenta.
Buscala como **ntfy** en Play Store o App Store.

En cada celular: tocá **+**, escribí el nombre de canal de esa persona y
tocá **Suscribirse**. Cada uno tiene su propio canal, así que a cada uno le
llega solo lo suyo. Los nombres son difíciles de adivinar a propósito
(cualquiera que sepa el nombre podría leer esos avisos): no los publiques.

### 3. Guardar los canales en GitHub

**Settings → Secrets and variables → Actions → New repository secret**,
una vez por persona:

| Name | Secret |
|---|---|
| `NTFY_GALEGO` | el canal de Galego |
| `NTFY_BIANCA` | el canal de Bianca |

### 4. Probar

Pestaña **Actions → Revisar concursos → Run workflow**, tildá
**Mandar un aviso de prueba a cada celular** y tocá **Run workflow**.

En uno o dos minutos a cada celular le llegan dos avisos: la prueba y un
resumen de lo que hoy tiene inscripción abierta o por abrir para esa persona.
Desde ahí, solo avisa lo nuevo.

### 5. Limpiar las ramas de prueba

En **Code → Branches**, borrá `sondeo` y `sondeo-out` (el ícono de tacho).
Fueron solo para relevar cómo publica cada sitio.

---

## Qué se revisa

| Página | Cómo |
|---|---|
| UNPSJB, Rectorado (Personal Nodocente, Concursos) | tabla por instancias |
| UNPSJB, Facultad de Ingeniería | tabla de concursos nodocentes |
| UNPSJB, Cs. Naturales y Cs. de la Salud | publicaciones del sitio |
| UNPSJB, Humanidades y Cs. Sociales | publicaciones del sitio, y el PDF adjunto si hace falta |
| UNPSJB, Digesto (SUDOCU) | resoluciones de llamado de Rectorado, Naturales, Económicas, Jurídicas y delegaciones zonales |
| Poder Judicial del Chubut | listado de llamados, con requisitos y fechas |
| Ministerio Público Fiscal del Chubut | concursos abiertos, cerrados y de funcionarios |
| Defensa Pública del Chubut | cargos convocados |
| Defensoría General de la Nación | inscripciones vigentes que mencionan la zona |

No cubre:

- **MPF de la Nación**: su sitio rechaza las consultas que vienen de GitHub.
  Sus concursos de ingreso para Comodoro conviene mirarlos a mano de vez en
  cuando en mpf.gob.ar, sección Ingreso democrático.
- **Económicas** tiene su portal nodocente en construcción; mientras tanto
  se sigue por el digesto.
- **Consejo de la Magistratura**: son concursos de magistrados.

## Cómo saber si sigue funcionando

- La página dice a qué hora fue la última revisión. Si pasaron más de 14
  horas, lo avisa arriba de todo.
- Si una página no se puede leer durante tres revisiones seguidas, a Galego
  le llega un aviso, y la página lo muestra en rojo. Es a propósito: es peor
  un monitor que dice "no hay nada" cuando en realidad dejó de mirar.
- GitHub pausa las tareas programadas de los repositorios sin actividad
  durante 60 días. El monitor se reactiva solo en cada corrida, pero si
  alguna vez ves que dejó de correr, en **Actions → Revisar concursos** tocá
  **Run workflow**.

## Si cambia la situación de alguno

Todo está en `config.py`, con comentarios: categoría, agrupamiento,
dependencia y sede de Galego, títulos y carrera de Bianca, y si los
avisos de otras ciudades suenan, llegan en silencio o no llegan. Al
guardar el cambio, el monitor corre solo y aplica el criterio nuevo.

## Archivos

| Archivo | Qué hace |
|---|---|
| `config.py` | Personas, criterios y páginas que se revisan |
| `fuentes.py` | Un lector por sitio |
| `reglas.py` | Lee tipo de concurso, categoría, ciudad, fechas y título exigido, y decide para quién sirve |
| `avisos.py` | Manda los avisos por ntfy |
| `monitor.py` | Junta todo y guarda `data/` para la página |
| `index.html` | La página |
| `tests/` | Pruebas de las reglas con textos reales de los llamados |

Los avisos y la página sirven para enterarse a tiempo. Los requisitos y las
fechas se confirman siempre en el llamado oficial.
