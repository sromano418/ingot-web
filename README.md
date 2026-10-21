# ingot.mx

Sitio web de InGot Marketing.

- `plantilla/` — portada (HTML y estilos) y efecto de partículas.
- `contenido/` — artículos y videos en Markdown. Se editan desde https://ingot.mx/admin/
- `assets/` — logos, fotos e imágenes subidas desde el panel.
- `build.py` — genera el sitio en `_site/`. Netlify lo corre en cada cambio.

Para probar en local: `pip install -r requirements.txt` y `python build.py`.
