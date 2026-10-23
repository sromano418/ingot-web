"""Genera el sitio de InGot (ingot.mx) en _site/.

- Portada: plantilla/inicio.html (+ efecto de partículas + últimas publicaciones).
- Contenido: una página con todas las publicaciones y una página por publicación,
  a partir de los archivos Markdown de contenido/ (los escribe el panel /admin).
- sitemap.xml y robots.txt para Google.

Netlify lo corre en cada cambio (ver netlify.toml). En local:
    python build.py                 # genera _site/
    python build.py --sin-particulas
"""
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

import markdown
import yaml

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "_site"
DOMINIO = "https://ingot.mx"
DESCRIPCION = "Marketing apoyado por inteligencia artificial para empresas del sector industrial. Hacemos visible el valor de tu empresa."

# Enlaces que dependen de datos que aún no tenemos: se muestran solo si se llenan.
VER_CASO_URL = ""     # p. ej. /blog/caso-servicios-financieros/
AVISO_URL = ""        # p. ej. /aviso-de-privacidad/

SOCIAL = [
    ("Instagram", "https://www.instagram.com/ingotmarketing/",
     '<rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.8"/>'
     '<circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.8"/>'
     '<circle cx="17.4" cy="6.6" r="1.2" fill="currentColor"/>'),
    ("LinkedIn", "https://www.linkedin.com/company/ingotmarketing/",
     '<rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/>'
     '<circle cx="8" cy="8" r="1.3" fill="currentColor"/>'
     '<path d="M8 11v6M12 17v-6M12 13.6c0-1.6 1.1-2.6 2.5-2.6s2.5 1 2.5 2.6V17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'),
    ("Facebook", "https://www.facebook.com/ingotmarketing",
     '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/>'
     '<path d="M13.2 21v-7.6h2.4l.4-2.8h-2.8V8.9c0-.8.3-1.4 1.4-1.4H16V5.1c-.3 0-1.1-.1-2-.1-2 0-3.4 1.2-3.4 3.5v2.1H8.3v2.8h2.3V21" fill="currentColor"/>'),
]
SOCIAL_HTML = '<div class="social">' + "".join(
    f'<a href="{url}" target="_blank" rel="noopener" aria-label="InGot en {name}" title="{name}">'
    f'<svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg></a>'
    for name, url, icon in SOCIAL) + "</div>"

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
PLAY = '<span class="play" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M5 3l8 5-8 5z" fill="#EEEAE2"/></svg></span>'
esc = html.escape


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
            "fecha_txt": f"{fecha.day} {MESES[fecha.month - 1]} {fecha.year}",
            "imagen": imagen,
            "video": meta.get("video") or "",
            "video_id": vid,
            # nl2br: respeta los saltos de línea de texto pegado sin líneas en blanco
            "html": md.convert(cuerpo),
            "indice": [(t["id"], t["name"]) for t in md.toc_tokens if t["level"] == 2],
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
            f'<h3>{esc(p["titulo"])}</h3>'
            + (f'<p>{esc(p["resumen"])}</p>' if p["resumen"] else "") + "</div></a>")


# ── páginas ───────────────────────────────────────────────────────────────────

def plantilla():
    t = (RAIZ / "plantilla" / "inicio.html").read_text(encoding="utf-8")
    t = (t.replace("__FAVICON__", "/assets/favicon.png").replace("__LOGO__", "/assets/logo-oscuro.png")
          .replace("__HERO__", "/assets/portada.webp").replace("__WHY__", "/assets/industria.webp")
          .replace("__VER_CASO__", f'<div style="margin-top:auto;padding-top:8px"><a href="{VER_CASO_URL}" class="btn">Ver caso →</a></div>' if VER_CASO_URL else "")
          .replace("__LINKEDIN__", SOCIAL_HTML)
          .replace("__AVISO__", f'<a href="{AVISO_URL}">Aviso de privacidad</a>' if AVISO_URL else ""))
    return t


def meta(titulo, descripcion, ruta, imagen="", tipo="website", extra=""):
    img = imagen if imagen.startswith("http") else DOMINIO + (imagen or "/assets/portada.webp")
    return (f'<link rel="canonical" href="{DOMINIO}{ruta}">\n'
            f'<meta property="og:type" content="{tipo}">\n'
            f'<meta property="og:title" content="{esc(titulo)}">\n'
            f'<meta property="og:description" content="{esc(descripcion)}">\n'
            f'<meta property="og:url" content="{DOMINIO}{ruta}">\n'
            f'<meta property="og:image" content="{esc(img)}">\n'
            f'<meta name="twitter:card" content="summary_large_image">' + extra)


def cabeza(t, titulo, descripcion, ruta, imagen="", tipo="website", extra=""):
    return (t.replace("__TITULO__", esc(titulo)).replace("__DESCRIPCION__", esc(descripcion))
             .replace("__META_EXTRA__", meta(titulo, descripcion, ruta, imagen, tipo, extra)))


def subpagina(t, titulo, descripcion, ruta, cuerpo, imagen="", tipo="website", extra=""):
    """Encabezado y pie de la portada alrededor de un contenido propio."""
    t = cabeza(t, titulo, descripcion, ruta, imagen, tipo, extra)
    inicio = t[:t.index('<div class="hero-campo">')]
    pie = t[t.index("<footer>"):t.index("</footer>") + len("</footer>")]
    return inicio + "<main>\n" + cuerpo + "\n</main>\n\n" + pie + "\n</body>\n</html>\n"


def portada(t, pubs, particulas):
    if pubs:
        bloque = (
            '<section class="light">\n  <div class="wrap">\n    <div class="head">\n'
            '      <div><div class="eyebrow">Blog</div><h2>Lo último que publicamos.</h2></div>\n'
            '      <div class="lead" style="align-items:flex-start"><a href="/blog/" class="btn">Ver todo el blog →</a></div>\n'
            '    </div>\n    <div class="posts">' + "".join(tarjeta(p) for p in pubs[:3]) + '</div>\n  </div>\n</section>\n')
    else:
        bloque = ""
    t = cabeza(t, "InGot", DESCRIPCION, "/").replace("__CONTENIDO_INICIO__", bloque)
    if particulas:
        js = (RAIZ / "plantilla" / "particulas.js").read_text(encoding="utf-8")
        t = t.replace("__CAMPO__", '<canvas id="campo" aria-hidden="true"></canvas>')
        t = t.replace("</body>", f"<script>\n{js}</script>\n</body>", 1)
    else:
        t = t.replace("__CAMPO__", "")
    return t


def pagina_lista(t, pubs):
    if pubs:
        lista = '<div class="posts">' + "".join(tarjeta(p) for p in pubs) + "</div>"
    else:
        lista = '<p class="vacio">Pronto publicaremos aquí artículos y videos.</p>'
    cuerpo = ('<section>\n  <div class="wrap">\n    <div class="head">\n'
              '      <div><div class="eyebrow">Blog</div><h2>Artículos y videos.</h2></div>\n'
              '    </div>\n    ' + lista + '\n  </div>\n</section>')
    return subpagina(t, "Blog · InGot", "Artículos y videos de InGot sobre presencia, visibilidad y mercados para empresas del sector industrial.", "/blog/", cuerpo)


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
              f'    <h1>{esc(p["titulo"])}</h1>\n'
              + (f'    <p class="resumen">{esc(p["resumen"])}</p>\n' if p["resumen"] else "")
              + '  </header>\n'
              f'  {medio}\n'
              '  <div class="art-grid">\n'
              f'    <div class="cuerpo">{p["html"]}</div>\n'
              '    <aside class="art-aside">' + indice
              + '<div class="art-cta"><strong>¿Tu presencia refleja el valor de tu empresa?</strong>'
              '<p>Te mostramos qué vemos antes de trabajar juntos.</p>'
              '<a href="/#contacto" class="btn">Quiero mi Preview sin costo →</a></div></aside>\n'
              '  </div>\n'
              '</article>')
    ruta = f'/blog/{p["slug"]}/'
    img = p["imagen"] if p["imagen"].startswith("http") else DOMINIO + (p["imagen"] or "/assets/portada.webp")
    # Datos estructurados de artículo para Google (lo que hace Yoast en WordPress)
    ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["titulo"],
          "description": p["meta_description"], "image": img, "datePublished": p["fecha"].date().isoformat(),
          "mainEntityOfPage": DOMINIO + ruta, "inLanguage": "es-MX",
          "author": {"@type": "Organization", "name": "InGot Marketing", "url": DOMINIO},
          "publisher": {"@type": "Organization", "name": "InGot Marketing",
                        "logo": {"@type": "ImageObject", "url": DOMINIO + "/assets/logo-oscuro.png"}}}
    if p["keyword"]:
        ld["keywords"] = p["keyword"]
    extra = (f'\n<meta property="article:published_time" content="{p["fecha"].date().isoformat()}">'
             f'\n<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<" + chr(92) + "/")}</script>')
    return subpagina(t, p["meta_title"], p["meta_description"], ruta, cuerpo, p["imagen"], "article", extra)


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
    for p in pubs:
        escribir(f"blog/{p['slug']}/index.html", pagina_publicacion(t, p))

    hoy = dt.date.today().isoformat()
    urls = [("/", hoy), ("/blog/", hoy)] + [(f"/blog/{p['slug']}/", p["fecha"].date().isoformat()) for p in pubs]
    escribir("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             + "".join(f"  <url><loc>{DOMINIO}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n")
    escribir("robots.txt", f"User-agent: *\nDisallow: /admin/\nSitemap: {DOMINIO}/sitemap.xml\n")
    sobrantes = re.findall(r"__[A-Z_]+__", (SALIDA / "index.html").read_text(encoding="utf-8"))
    assert not sobrantes, sobrantes
    print(f"ok: {len(pubs)} publicaciones, partículas={'sí' if particulas else 'no'}")


if __name__ == "__main__":
    main()
