// Vista previa del panel /admin: cómo se ve en Google + revisión SEO (estilo Yoast) + el artículo.
// Usa los globales que expone Decap CMS: CMS, createClass y h.
(function () {
  if (!window.CMS) return
  CMS.registerPreviewStyle('/admin/preview.css')

  // compara sin acentos ni mayúsculas
  var norm = function (s) {
    return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, ' ').trim()
  }
  var contiene = function (texto, kw) { return !!kw && norm(texto).indexOf(norm(kw)) !== -1 }
  var largo = function (s) { return String(s || '').trim().length }

  function revisar(d) {
    var kw = (d.seo && d.seo.keyword) || ''
    var titulo = d.titulo || ''
    var metaT = (d.seo && d.seo.meta_title) || titulo
    var metaD = (d.seo && d.seo.meta_description) || d.resumen || ''
    var cuerpo = d.body || ''
    var primerParrafo = (cuerpo.split(/\n\s*\n/).find(function (p) { return p.trim() && !/^\s*#/.test(p) }) || '')
    var h2 = (cuerpo.match(/^##\s+\S/gm) || []).length
    var h1Cuerpo = (cuerpo.match(/^#\s+\S/gm) || []).length
    var enlaces = (cuerpo.match(/\]\((https?:\/\/|\/)[^)]+\)/g) || []).length
    var palabras = norm(cuerpo.replace(/[#>*_\[\]()`-]/g, ' ')).split(' ').filter(Boolean).length
    var slugKw = norm(kw).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    var lt = largo(metaT), ld = largo(metaD)
    return [
      [!!kw, 'Keyword principal definida', kw ? '“' + kw + '”' : 'Escribe la keyword en la sección SEO'],
      [contiene(titulo, kw), 'Keyword en el título (H1)', ''],
      [contiene(metaT, kw), 'Keyword en el meta title', ''],
      [contiene(metaD, kw), 'Keyword en la meta description', ''],
      [!!slugKw && (d.slug || '').indexOf(slugKw) !== -1, 'Keyword en la URL (slug)', d.slug ? '/contenido/' + d.slug + '/' : 'Falta el slug'],
      [contiene(primerParrafo, kw), 'Keyword en el primer párrafo', ''],
      [lt >= 30 && lt <= 60, 'Largo del meta title', lt + ' caracteres (ideal 50–60)'],
      [ld >= 120 && ld <= 160, 'Largo de la meta description', ld + ' caracteres (ideal 120–160)'],
      [h2 > 0, 'Secciones con H2', h2 + (h2 === 1 ? ' encabezado H2' : ' encabezados H2')],
      [h1Cuerpo === 0, 'Un solo H1 (el título)', h1Cuerpo ? 'Cambia a H2 los H1 del contenido' : ''],
      [enlaces > 0, 'Enlaces en el texto', enlaces + (enlaces === 1 ? ' enlace' : ' enlaces')],
      [palabras >= 300, 'Extensión del texto', palabras + ' palabras (recomendado 300 o más)'],
      [!d.imagen || !!d.imagen_alt, 'Texto alternativo de la portada', d.imagen && !d.imagen_alt ? 'Describe la imagen de portada' : '']
    ]
  }

  var Vista = createClass({
    render: function () {
      var e = this.props.entry
      var d = e.get('data').toJS()
      var metaT = (d.seo && d.seo.meta_title) || d.titulo || 'Título del artículo'
      var metaD = (d.seo && d.seo.meta_description) || d.resumen || 'Aquí va la meta description.'
      var checks = revisar(d)
      var ok = checks.filter(function (c) { return c[0] }).length
      var img = this.props.getAsset(d.imagen)
      return h('div', { className: 'ig' },
        h('section', { className: 'ig-panel' },
          h('div', { className: 'ig-label' }, 'Así se vería en Google'),
          h('div', { className: 'serp' },
            h('div', { className: 'serp-url' }, 'ingot.mx › contenido › ' + (d.slug || 'slug')),
            h('div', { className: 'serp-title' }, metaT.length > 60 ? metaT.slice(0, 60) + '…' : metaT),
            h('div', { className: 'serp-desc' }, metaD.length > 160 ? metaD.slice(0, 160) + '…' : metaD))),
        h('section', { className: 'ig-panel' },
          h('div', { className: 'ig-label' }, 'Revisión SEO · ' + ok + ' de ' + checks.length),
          h('ul', { className: 'checks' }, checks.map(function (c, i) {
            return h('li', { key: i, className: c[0] ? 'ok' : 'no' },
              h('span', { className: 'dot' }),
              h('span', null, h('strong', null, c[1]), c[2] ? h('em', null, ' · ' + c[2]) : null))
          }))),
        h('article', { className: 'ig-art' },
          h('div', { className: 'ig-meta' }, (d.tipo || 'Artículo') + (d.fecha ? ' · ' + d.fecha : '')),
          h('h1', null, d.titulo || 'Título del artículo'),
          d.resumen ? h('p', { className: 'ig-resumen' }, d.resumen) : null,
          img && d.imagen ? h('img', { className: 'ig-portada', src: img.toString(), alt: d.imagen_alt || '' }) : null,
          h('div', { className: 'cuerpo' }, this.props.widgetFor('body'))))
    }
  })
  CMS.registerPreviewTemplate('contenido', Vista)
})()
