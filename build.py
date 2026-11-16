"""Genera el sitio de InGot (ingot.mx) en _site/.

- Portada: plantilla/inicio.html (+ efecto de partículas + últimas publicaciones).
- Contenido: una página con todas las publicaciones y una página por publicación,
  a partir de los archivos Markdown de contenido/ (los escribe el panel /admin).
- sitemap.xml, robots.txt y llms.txt.
- 404.html para direcciones que no existen (noindex y fuera del sitemap).

Netlify lo corre en cada cambio (ver netlify.toml). En local:
    python build.py                 # genera _site/
    python build.py --sin-particulas
"""
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown
import yaml

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "_site"
DOMINIO = "https://ingot.mx"
DESCRIPCION = "Hacemos visible el valor de tu empresa. Ayudamos a empresas del sector industrial a construir presencia, visibilidad y contenido de su mercado."
# JPG de la foto de portada, 1200×627, sin transparencia. Solo Open Graph de inicio y /blog/.
OG_PORTADA = "/assets/colada-og.jpg"
OG_PORTADA_ALT = "Colada de metal fundido en una planta"
OG_PORTADA_ANCHO = "1200"
OG_PORTADA_ALTO = "627"

# Enlaces que dependen de datos que aún no tenemos: se muestran solo si se llenan.
VER_CASO_URL = ""     # p. ej. /blog/caso-servicios-financieros/
AVISO_URL = ""        # p. ej. /aviso-de-privacidad/
# Imagen del caso InHedge (16:10). Para publicarla, sustituye el archivo
# assets/caso-inhedge/caso-placeholder.webp. Si cambia la ruta, actualiza este valor.
CASO_IMAGEN = "/assets/caso-inhedge/caso-placeholder.webp"

SOCIAL = [
    ("LinkedIn", "https://www.linkedin.com/company/ingotmarketing/",
     '<rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/>'
     '<circle cx="8" cy="8" r="1.3" fill="currentColor"/>'
     '<path d="M8 11v6M12 17v-6M12 13.6c0-1.6 1.1-2.6 2.5-2.6s2.5 1 2.5 2.6V17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'),
]
SOCIAL_HTML = '<div class="social">' + "".join(
    f'<a href="{url}" target="_blank" rel="noopener" aria-label="InGot en {name}" title="{name}">'
    f'<svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg></a>'
    for name, url, icon in SOCIAL) + "</div>"

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PLAY = '<span class="play" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M5 3l8 5-8 5z" fill="#EEEAE2"/></svg></span>'
esc = html.escape


def unir_ultimas(texto):
    """Evita una palabra sola al final si el navegador no tiene text-wrap: balance.

    En escritorio las dos últimas palabras van juntas. En móvil el CSS deja que
    se separen si no caben en la línea.
    """
    partes = texto.rsplit(" ", 1)
    if len(partes) != 2 or not partes[0].strip() or not partes[1].strip():
        return texto
    cabeza, ultima = partes
    previas = cabeza.rsplit(" ", 1)
    if len(previas) == 2:
        return f'{previas[0]} <span class="no-huerfana">{previas[1]} {ultima}</span>'
    return f'<span class="no-huerfana">{cabeza} {ultima}</span>'


def titulo_html(texto):
    return unir_ultimas(esc(texto))


def equilibrar_encabezados(fragmento):
    def repl(m):
        tag, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
        if "<" in inner:
            return m.group(0)
        return f"<{tag}{attrs}>{unir_ultimas(inner)}</{tag}>"

    return re.sub(r"<(h[123])(\s[^>]*)?>(.*?)</\1>", repl, fragmento, flags=re.I | re.S)


def etiquetar_tablas(fragmento):
    """En móvil cada celda muestra el nombre de su columna (data-label). El texto no cambia."""
    def tabla(m):
        bloque = m.group(0)
        heads = re.findall(r"<th\b[^>]*>(.*?)</th>", bloque, flags=re.I | re.S)
        labels = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip() for h in heads]
        if not labels:
            return bloque
        n = {"i": 0}

        def td(tm):
            i = n["i"]
            n["i"] += 1
            attrs, inner = tm.group(1) or "", tm.group(2)
            if "data-label=" in attrs:
                return tm.group(0)
            lab = esc(labels[i % len(labels)])
            return f'<td data-label="{lab}"{attrs}>{inner}</td>'

        return re.sub(r"<td(\s[^>]*)?>(.*?)</td>", td, bloque, flags=re.I | re.S)

    return re.sub(r"<table\b[^>]*>.*?</table>", tabla, fragmento, flags=re.I | re.S)


# ── publicaciones ─────────────────────────────────────────────────────────────

def youtube_id(url):
    m = re.search(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/))([\w-]{11})", url or "")
    return m.group(1) if m else None


def a_fecha(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return dt.datetime(1970, 1, 1)


def leer_publicaciones():
    pubs = []
    for f in sorted((RAIZ / "contenido").glob("*.md")):
        txt = f.read_text(encoding="utf-8")
        md = markdown.Markdown(extensions=["extra", "sane_lists", "nl2br", "toc"], extension_configs={"toc": {"toc_depth": "2-4"}})
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", txt, re.S)
        meta, cuerpo = (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, txt)
        if meta.get("borrador"):
            continue
        fecha = a_fecha(meta.get("fecha"))
        modificada = a_fecha(meta.get("fecha_modificacion")) if meta.get("fecha_modificacion") else None
        vid = youtube_id(meta.get("video"))
        imagen = meta.get("imagen") or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")
        seo = meta.get("seo") or {}
        slug = re.sub(r"[^a-z0-9-]+", "-", str(meta.get("slug") or f.stem).lower()).strip("-") or f.stem
        titulo = str(meta.get("titulo") or f.stem)
        resumen = str(meta.get("resumen") or "")
        pubs.append({
            "slug": slug,
            "titulo": titulo,
            "resumen": resumen,
            "meta_title": str(seo.get("meta_title") or "").strip() or f"{titulo} · InGot",
            "meta_description": str(seo.get("meta_description") or "").strip() or resumen or DESCRIPCION,
            "keyword": str(seo.get("keyword") or "").strip(),
            "imagen_alt": str(meta.get("imagen_alt") or ""),
            "tipo": meta.get("tipo") or ("Video" if meta.get("video") else "Artículo"),
            "fecha": fecha,
            "modificada": modificada.date().isoformat() if modificada else "",
            "fecha_txt": f"{fecha.day} {MESES[fecha.month - 1]} {fecha.year}",
            "imagen": imagen,
            "video": meta.get("video") or "",
            "video_id": vid,
            # nl2br: respeta los saltos de línea de texto pegado sin líneas en blanco
            "html": md.convert(cuerpo),
            "indice": [(t["id"], t["name"]) for t in md.toc_tokens if t["level"] == 2],
            "archivo": f,
        })
    pubs.sort(key=lambda p: p["fecha"], reverse=True)
    return pubs


def tarjeta(p):
    fondo = f' style="background-image:url(\'{esc(p["imagen"])}\')"' if p["imagen"] else ""
    clase = "img" if p["imagen"] else "img sin"     # sin imagen: símbolo de InGot de relleno
    play = PLAY if p["tipo"] == "Video" else ""
    return (f'<a class="post-card" href="/blog/{p["slug"]}/">'
            f'<div class="{clase}"{fondo}>{play}</div>'
            f'<div class="txt"><span class="meta">{esc(p["tipo"])} · {p["fecha_txt"]}</span>'
            f'<h3>{titulo_html(p["titulo"])}</h3>'
            + (f'<p>{esc(p["resumen"])}</p>' if p["resumen"] else "") + "</div></a>")


# ── páginas ───────────────────────────────────────────────────────────────────

def plantilla():
    t = (RAIZ / "plantilla" / "inicio.html").read_text(encoding="utf-8")
    ver_caso = (f'<a class="cta blanco" href="{VER_CASO_URL}">Ver el caso <span class="flecha" aria-hidden="true">→</span></a>'
                if VER_CASO_URL else "")
    t = (t.replace("__LOGO__", "/assets/marca/ingot-02.svg")
          .replace("__VER_CASO__", ver_caso)
          .replace("__CASO_IMG__", CASO_IMAGEN)
          .replace("__LINKEDIN__", SOCIAL_HTML)
          .replace("__AVISO__", f'<a href="{AVISO_URL}">Aviso de privacidad</a>' if AVISO_URL else ""))
    return t


DESC_BLOG = (
    "Artículos de InGot sobre presencia, visibilidad y mercados para empresas del sector industrial "
    "en México: marca, sitio web, LinkedIn y contenido técnico."
)


def script_ld(datos):
    crudo = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{crudo}</script>'


def url_imagen(imagen):
    if not imagen:
        return ""
    return imagen if str(imagen).startswith("http") else DOMINIO + imagen


def ld_migas(pasos):
    """pasos: lista de (nombre, url absoluta)."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": nombre, "item": url}
            for i, (nombre, url) in enumerate(pasos, 1)
        ],
    }


def ld_blog(pubs):
    """CollectionPage + Blog, ItemList de lo publicado y migas Inicio > Blog."""
    elementos = []
    for i, p in enumerate(pubs, 1):
        url = f"{DOMINIO}/blog/{p['slug']}/"
        posting = {
            "@type": "BlogPosting",
            "headline": p["titulo"],
            "url": url,
            "datePublished": p["fecha"].date().isoformat(),
            "inLanguage": "es-MX",
        }
        img = url_imagen(p["imagen"])
        if img:
            posting["image"] = img
        elementos.append({
            "@type": "ListItem",
            "position": i,
            "name": p["titulo"],
            "url": url,
            "item": posting,
        })
    lista = DOMINIO + "/blog/#list"
    migas = DOMINIO + "/blog/#breadcrumb"
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": ["CollectionPage", "Blog"],
                "@id": DOMINIO + "/blog/#webpage",
                "url": DOMINIO + "/blog/",
                "name": "Blog de marketing para el sector industrial",
                "description": DESC_BLOG,
                "inLanguage": "es-MX",
                "isPartOf": {"@id": DOMINIO + "/#website"},
                "publisher": {"@id": DOMINIO + "/#organization"},
                "mainEntity": {"@id": lista},
                "breadcrumb": {"@id": migas},
            },
            {
                "@type": "ItemList",
                "@id": lista,
                "name": "Artículos publicados",
                "numberOfItems": len(elementos),
                "itemListOrder": "https://schema.org/ItemListOrderDescending",
                "itemListElement": elementos,
            },
            {
                "@type": "BreadcrumbList",
                "@id": migas,
                "itemListElement": ld_migas([
                    ("Inicio", DOMINIO + "/"),
                    ("Blog", DOMINIO + "/blog/"),
                ])["itemListElement"],
            },
        ],
    }


def texto_llms(pubs):
    """Descripción para asistentes. Solo enlaza artículos ya publicados."""
    lineas = [
        "# InGot",
        "",
        "> Marketing para empresas del sector industrial. Hacemos visible el valor de tu empresa.",
        "",
        "InGot ayuda a empresas del sector industrial a construir una presencia profesional, "
        "aumentar su visibilidad y comunicar con claridad lo que las hace valiosas. "
        "El trabajo cubre México, Estados Unidos y Latinoamérica, y sigue cuatro pilares en este orden:",
        "",
        "- **Te ves profesional.** Identidad, sitio web, LinkedIn y presentaciones a la altura de la planta.",
        "- **Te encuentran.** SEO, contenido y páginas por producto para que un comprador te encuentre en Google o en asistentes de IA.",
        "- **Confían en ti.** Artículos técnicos, reportes y estudios que demuestran conocimiento del mercado.",
        "- **Te eligen.** Fichas técnicas y materiales comerciales para que el equipo cierre.",
        "",
        "El proceso empieza con un preview de la presencia actual. Si hay una oportunidad clara, "
        "sigue una auditoría y después la construcción del sitio, la marca y el contenido, con acompañamiento mensual.",
        "",
        "## Contacto",
        "",
        f"- [Contacto]({DOMINIO}/#contacto)",
        "",
        "## Artículos",
        "",
    ]
    if pubs:
        for p in pubs:
            resumen = f": {p['resumen']}" if p["resumen"] else ""
            lineas.append(f"- [{p['titulo']}]({DOMINIO}/blog/{p['slug']}/){resumen}")
    else:
        lineas.append("Todavía no hay artículos publicados.")
    lineas.append("")
    return "\n".join(lineas)


def _git(args):
    try:
        proc = subprocess.run(
            ["git", "-C", str(RAIZ), *args],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout or ""


def _dia_git(salida):
    linea = (salida or "").strip()
    return linea if re.fullmatch(r"\d{4}-\d{2}-\d{2}", linea) else None


def fecha_commit(ruta):
    """Fecha YYYY-MM-DD del último commit que tocó el archivo.

    En un clon superficial (Netlify usa depth 1) `git log -- archivo` devuelve
    HEAD aunque ese commit no haya tocado el archivo. Esa fecha no se usa.
    """
    rel = Path(ruta).resolve().relative_to(RAIZ).as_posix()
    shallow = (_git(["rev-parse", "--is-shallow-repository"]) or "").strip() == "true"
    if shallow:
        tocados = {ln.strip() for ln in (_git(["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"]) or "").splitlines()}
        if rel not in tocados:
            return None
        return _dia_git(_git(["log", "-1", "--format=%cs"]))
    return _dia_git(_git(["log", "-1", "--format=%cs", "--", rel]))


def preguntas_visibles(html_art):
    """Pares de la sección visible «Preguntas frecuentes». Vacío si no hay pregunta y respuesta."""
    seccion = re.search(
        r"<h2[^>]*>\s*Preguntas frecuentes\s*</h2>(.*?)(?=<h2\b|$)",
        html_art, re.I | re.S)
    if not seccion:
        return []
    paras = re.findall(r"<p>(.*?)</p>", seccion.group(1), re.S)
    faqs = []
    i = 0
    while i < len(paras) - 1:
        preg = re.fullmatch(r"<strong>(.+?)</strong>", paras[i].strip(), re.S)
        if not preg:
            i += 1
            continue
        pregunta = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", preg.group(1)))).strip()
        respuesta = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", paras[i + 1]))).strip()
        if not pregunta.endswith("?") or not respuesta or respuesta.endswith("?"):
            i += 1
            continue
        faqs.append((pregunta, respuesta))
        i += 2
    return faqs


def ld_sitio():
    linkedin = next(url for nombre, url, _icono in SOCIAL if nombre == "LinkedIn")
    org = DOMINIO + "/#organization"
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": org,
                "name": "InGot Marketing",
                "url": DOMINIO + "/",
                "logo": DOMINIO + "/assets/logo-oscuro.png",
                "email": "info@ingot.mx",
                "telephone": "+528127186576",
                "areaServed": [
                    {"@type": "Country", "name": "México"},
                    {"@type": "Country", "name": "Estados Unidos"},
                    {"@type": "Place", "name": "Latinoamérica"},
                ],
                "sameAs": [linkedin],
            },
            {
                "@type": "WebSite",
                "@id": DOMINIO + "/#website",
                "name": "InGot Marketing",
                "url": DOMINIO + "/",
                "publisher": {"@id": org},
                "inLanguage": "es-MX",
            },
        ],
    }


def meta(titulo, descripcion, ruta, imagen="", tipo="website", extra="", social=False):
    if social:
        img = DOMINIO + OG_PORTADA
    else:
        img = imagen if imagen.startswith("http") else DOMINIO + (imagen or "/assets/colada.webp")
    lineas = [
        f'<link rel="canonical" href="{DOMINIO}{ruta}">',
        '<meta property="og:locale" content="es_MX">',
        '<meta property="og:site_name" content="InGot">',
        f'<meta property="og:type" content="{tipo}">',
        f'<meta property="og:title" content="{esc(titulo)}">',
        f'<meta property="og:description" content="{esc(descripcion)}">',
        f'<meta property="og:url" content="{DOMINIO}{ruta}">',
        f'<meta property="og:image" content="{esc(img)}">',
    ]
    if social:
        lineas += [
            f'<meta property="og:image:width" content="{OG_PORTADA_ANCHO}">',
            f'<meta property="og:image:height" content="{OG_PORTADA_ALTO}">',
            f'<meta property="og:image:alt" content="{esc(OG_PORTADA_ALT)}">',
            f'<meta name="twitter:image" content="{esc(img)}">',
        ]
    lineas.append('<meta name="twitter:card" content="summary_large_image">')
    return "\n".join(lineas) + extra


def cabeza(t, titulo, descripcion, ruta, imagen="", tipo="website", extra="", social=False):
    return (t.replace("__TITULO__", esc(titulo)).replace("__DESCRIPCION__", esc(descripcion))
             .replace("__META_EXTRA__", meta(titulo, descripcion, ruta, imagen, tipo, extra, social)))


def subpagina(t, titulo, descripcion, ruta, cuerpo, imagen="", tipo="website", extra="", social=False):
    """Encabezado y pie de la portada alrededor de un contenido propio."""
    t = cabeza(t, titulo, descripcion, ruta, imagen, tipo, extra, social)
    inicio = t[:t.index('<div class="hero-campo">')]
    pie = t[t.index("<footer>"):t.index("</footer>") + len("</footer>")]
    return inicio + "<main>\n" + cuerpo + "\n</main>\n\n" + pie + "\n</body>\n</html>\n"


def fila_inicio(p, primero):
    resumen = f'{esc(p["resumen"])}<br>' if p["resumen"] else ""
    nuevo = '<span class="marca-nuevo">Nuevo</span>' if primero else ""
    return (f'<a href="/blog/{p["slug"]}/">'
            f'<div class="meta"><span class="mono marcas"><span class="cat">{esc(p["tipo"])}</span>{nuevo}</span>'
            f'<span class="mono fecha">{p["fecha_txt"]}</span></div>'
            f'<h3>{titulo_html(p["titulo"])}</h3>'
            f'<div class="bd">{resumen}<span class="lnk">Leer artículo →</span></div></a>')


def portada(t, pubs, particulas):
    filas = "\n".join(fila_inicio(p, i == 0) for i, p in enumerate(pubs[:3]))
    bloque = (
        '<section class="blog reveal" id="blog">\n'
        '  <div class="g">\n'
        '    <h2 class="disp">Lo último del blog.</h2>\n'
        '    <a class="lnk" href="/blog/">Ver todos los artículos</a>\n'
        '  </div>\n'
        f'  <div class="blog-lista">\n{filas}\n  </div>\n'
        '</section>\n'
    )
    t = cabeza(t, "InGot Marketing · Marketing para empresas del sector industrial", DESCRIPCION, "/", social=True).replace("__CONTENIDO_INICIO__", bloque)
    t = t.replace("</head>", script_ld(ld_sitio()) + "\n</head>", 1)
    # El campo de partículas solo se inyecta si la plantilla lo pide. La portada v5 usa fotografía.
    if particulas and "__CAMPO__" in t:
        js = (RAIZ / "plantilla" / "particulas.js").read_text(encoding="utf-8")
        t = t.replace("__CAMPO__", '<canvas id="campo" aria-hidden="true"></canvas>')
        t = t.replace("</body>", f"<script>\n{js}</script>\n</body>", 1)
    else:
        t = t.replace("__CAMPO__", "")
    return t


def pagina_lista(t, pubs):
    if not pubs:
        lista = '<p class="vacio">Pronto publicaremos aquí artículos.</p>'
    elif len(pubs) == 1:
        lista = '<div class="posts posts-uno">' + tarjeta(pubs[0]) + "</div>"
    else:
        lista = '<div class="posts">' + "".join(tarjeta(p) for p in pubs) + "</div>"
    cuerpo = ('<section>\n  <div class="wrap">\n    <div class="head">\n'
              '      <div><div class="eyebrow">Blog</div><h1>Artículos.</h1></div>\n'
              '    </div>\n    ' + lista + '\n  </div>\n</section>')
    return subpagina(
        t,
        "Blog de marketing para el sector industrial · InGot",
        DESC_BLOG,
        "/blog/",
        cuerpo,
        extra="\n" + script_ld(ld_blog(pubs)),
        social=True,
    )


def pagina_publicacion(t, p):
    if p["video_id"]:
        medio = (f'<div class="video"><iframe src="https://www.youtube-nocookie.com/embed/{p["video_id"]}" '
                 f'title="{esc(p["titulo"])}" loading="lazy" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>')
    elif p["video"]:
        medio = f'<p><a class="btn" href="{esc(p["video"])}" target="_blank" rel="noopener">Ver el video →</a></p>'
    elif p["imagen"]:
        medio = f'<img class="portada" src="{esc(p["imagen"])}" alt="{esc(p["imagen_alt"])}">'
    else:
        medio = ""
    indice = ""
    if len(p["indice"]) >= 2:
        indice = ('<nav class="indice" aria-label="En este artículo"><span>En este artículo</span>'
                  + "".join(f'<a href="#{i}">{n}</a>' for i, n in p["indice"]) + "</nav>")
    cuerpo = ('<article class="articulo">\n'
              '  <header class="art-head">\n'
              '    <a class="volver" href="/blog/">← Blog</a>\n'
              f'    <span class="eyebrow">{esc(p["tipo"])} · {p["fecha_txt"]}</span>\n'
              f'    <h1>{titulo_html(p["titulo"])}</h1>\n'
              + (f'    <p class="resumen">{esc(p["resumen"])}</p>\n' if p["resumen"] else "")
              + '  </header>\n'
              f'  {medio}\n'
              '  <div class="art-grid">\n'
              f'    <div class="cuerpo">{equilibrar_encabezados(etiquetar_tablas(p["html"]))}</div>\n'
              '    <aside class="art-aside">' + indice
              + '<div class="art-cta"><strong>¿Tu presencia refleja el valor de tu empresa?</strong>'
              '<p>Te mostramos qué vemos antes de trabajar juntos.</p>'
              '<a href="/#contacto" class="btn">Quiero mi Preview sin costo →</a></div></aside>\n'
              '  </div>\n'
              '</article>')
    ruta = f'/blog/{p["slug"]}/'
    img = p["imagen"] if p["imagen"].startswith("http") else DOMINIO + (p["imagen"] or "/assets/colada.webp")
    # Datos estructurados de artículo para Google (lo que hace Yoast en WordPress)
    ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["titulo"],
          "description": p["meta_description"], "image": img, "datePublished": p["fecha"].date().isoformat(),
          "dateModified": p["modificada"] or fecha_commit(p["archivo"]) or p["fecha"].date().isoformat(),
          "mainEntityOfPage": DOMINIO + ruta, "inLanguage": "es-MX",
          "author": {"@type": "Organization", "name": "InGot", "url": DOMINIO},
          "publisher": {"@type": "Organization", "name": "InGot",
                        "logo": {"@type": "ImageObject", "url": DOMINIO + "/assets/logo-oscuro.png"}}}
    if p["keyword"]:
        ld["keywords"] = p["keyword"]
    extra = (f'\n<meta property="article:published_time" content="{p["fecha"].date().isoformat()}">'
             f'\n{script_ld(ld)}'
             f'\n{script_ld(ld_migas([("Inicio", DOMINIO + "/"), ("Blog", DOMINIO + "/blog/"), (p["titulo"], DOMINIO + ruta)]))}')
    faqs = preguntas_visibles(p["html"])
    if faqs:
        extra += "\n" + script_ld({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": pregunta,
                 "acceptedAnswer": {"@type": "Answer", "text": respuesta}}
                for pregunta, respuesta in faqs
            ],
        })
    return subpagina(t, p["meta_title"], p["meta_description"], ruta, cuerpo, p["imagen"], "article", extra)


def pagina_404(t):
    cuerpo = (
        '<section class="pagina-404">\n'
        '  <div class="wrap">\n'
        '    <div class="head">\n'
        '      <div class="eyebrow">404</div>\n'
        '      <h1>No encontramos esta página.</h1>\n'
        '    </div>\n'
        '    <p>La dirección no existe o cambió. Puedes volver al inicio, leer el blog o escribirnos.</p>\n'
        '    <div class="acciones">\n'
        '      <a class="lnk" href="/">Inicio</a>\n'
        '      <a class="lnk" href="/blog/">Blog</a>\n'
        '      <a class="lnk" href="/#contacto">Contacto</a>\n'
        '    </div>\n'
        '  </div>\n'
        '</section>'
    )
    return subpagina(
        t,
        "Página no encontrada · InGot",
        "Esta página no existe. Vuelve al inicio, al blog o al contacto de InGot.",
        "/404.html",
        cuerpo,
        extra='\n<meta name="robots" content="noindex">',
    )


def main():
    particulas = "--sin-particulas" not in sys.argv
    pubs = leer_publicaciones()
    t = plantilla()
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    SALIDA.mkdir()
    shutil.copytree(RAIZ / "assets", SALIDA / "assets")
    shutil.copytree(RAIZ / "static", SALIDA, dirs_exist_ok=True)

    def escribir(ruta, texto):
        destino = SALIDA / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")

    escribir("index.html", portada(t, pubs, particulas))
    escribir("blog/index.html", pagina_lista(t, pubs))
    escribir("404.html", pagina_404(t))
    for p in pubs:
        escribir(f"blog/{p['slug']}/index.html", pagina_publicacion(t, p))

    hoy = dt.date.today().isoformat()
    # Solo páginas públicas. 404.html lleva noindex y no entra aquí. Los borradores
    # tampoco: leer_publicaciones ya los dejó fuera, y llms.txt usa la misma lista.
    urls = [("/", hoy), ("/blog/", hoy)] + [(f"/blog/{p['slug']}/", p["fecha"].date().isoformat()) for p in pubs]
    mapa = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{DOMINIO}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n")
    assert f"{DOMINIO}/404" not in mapa
    escribir("sitemap.xml", mapa)
    # /llms.txt se puede rastrear: no está bajo /admin/.
    robots = f"User-agent: *\nDisallow: /admin/\nSitemap: {DOMINIO}/sitemap.xml\n"
    assert "llms.txt" not in robots
    escribir("robots.txt", robots)
    escribir("llms.txt", texto_llms(pubs))
    html_portada = (SALIDA / "index.html").read_text(encoding="utf-8")
    sobrantes = re.findall(r"__[A-Z_]+__", html_portada)
    assert not sobrantes, sobrantes
    campo = 'id="campo"' in html_portada
    print(f"ok: {len(pubs)} publicaciones, partículas={'sí' if campo else 'no'}")


if __name__ == "__main__":
    main()
