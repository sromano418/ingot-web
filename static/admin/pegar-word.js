// Pegar desde Word o Google Docs en el campo Contenido de /admin.
// El editor de Decap pega texto plano y se pierden párrafos, títulos, listas y tablas.
// Aquí se intercepta el pegado, se convierte el HTML del portapapeles a Markdown
// (títulos ##, listas -, tablas | |) y se vuelve a pegar como texto.
// Usa TurndownService (cargado en index.html).
(function () {
  if (!window.TurndownService) return
  var YA = '__igPegado'

  function quitar(n) { if (n && n.parentNode) n.parentNode.removeChild(n) }
  function envolver(n, tag, doc) {
    var w = doc.createElement(tag)
    while (n.firstChild) w.appendChild(n.firstChild)
    n.appendChild(w)
  }

  // Word manda las listas como párrafos con "mso-list" y la viñeta escrita a mano.
  function listasDeWord(doc) {
    var ps = Array.prototype.slice.call(doc.querySelectorAll('p'))
    var actual = null
    ps.forEach(function (p) {
      var estilo = p.getAttribute('style') || ''
      var esLista = /mso-list:\s*l\d/i.test(estilo) || /^MsoListParagraph/i.test(p.className || '')
      if (!esLista) { actual = null; return }
      var marca = p.querySelector('span[style*="mso-list:Ignore"], span[style*="mso-list: Ignore"]')
      var textoMarca = marca ? marca.textContent.trim() : ''
      quitar(marca)
      var nivel = +((estilo.match(/level(\d)/i) || [])[1] || 1)
      var tipo = /^[0-9a-z]{1,3}[.)]$/i.test(textoMarca) ? 'ol' : 'ul'
      var prev = p.previousElementSibling
      if (!actual || prev !== actual.ultimo) actual = { raiz: null, pila: [], ultimo: null }
      // pila de listas por nivel
      while (actual.pila.length > nivel) actual.pila.pop()
      while (actual.pila.length < nivel) {
        var l = doc.createElement(tipo)
        if (!actual.pila.length) { p.parentNode.insertBefore(l, p); actual.raiz = l }
        else {
          var padre = actual.pila[actual.pila.length - 1]
          var li0 = padre.lastElementChild || padre.appendChild(doc.createElement('li'))
          li0.appendChild(l)
        }
        actual.pila.push(l)
      }
      var li = doc.createElement('li')
      while (p.firstChild) li.appendChild(p.firstChild)
      actual.pila[actual.pila.length - 1].appendChild(li)
      actual.ultimo = p
      // el <p> vacío se queda como marcador para saber si el siguiente es contiguo
      p.setAttribute('data-ig-vacio', '1')
    })
    Array.prototype.slice.call(doc.querySelectorAll('p[data-ig-vacio]')).forEach(quitar)
  }

  function limpiar(html) {
    var doc = new DOMParser().parseFromString(html, 'text/html')
    var b = doc.body
    Array.prototype.slice.call(b.querySelectorAll('style,meta,link,script,title,xml,o\\:p')).forEach(quitar)
    // comentarios (Word mete <!--[if ...]-->)
    var it = doc.createTreeWalker(b, NodeFilter.SHOW_COMMENT), c, coms = []
    while ((c = it.nextNode())) coms.push(c)
    coms.forEach(quitar)
    // imágenes locales del portapapeles de Word (file://) no se pueden subir así
    Array.prototype.slice.call(b.querySelectorAll('img')).forEach(function (im) {
      if (!/^https?:/i.test(im.getAttribute('src') || '')) quitar(im)
    })
    // Google Docs envuelve todo en <b style="font-weight:normal">
    Array.prototype.slice.call(b.querySelectorAll('b[id^="docs-internal-guid"]')).forEach(function (x) {
      while (x.firstChild) x.parentNode.insertBefore(x.firstChild, x)
      quitar(x)
    })
    // negritas e itálicas que vienen como estilo
    Array.prototype.slice.call(b.querySelectorAll('span[style]')).forEach(function (s) {
      var st = s.getAttribute('style')
      if (/font-weight:\s*(bold|[6-9]00)/i.test(st)) envolver(s, 'strong', doc)
      if (/font-style:\s*italic/i.test(st)) envolver(s, 'em', doc)
    })
    listasDeWord(doc)
    // Títulos de Word con estilo pero sin etiqueta (Mac a veces manda class="MsoTitle"/"Heading")
    Array.prototype.slice.call(b.querySelectorAll('p[class]')).forEach(function (p) {
      var m = /^(?:MsoHeading|Heading|Ttulo|Titulo)(\d)/i.exec(p.className)
      if (m) {
        var h = doc.createElement('h' + Math.min(+m[1], 6))
        while (p.firstChild) h.appendChild(p.firstChild)
        p.parentNode.replaceChild(h, p)
      }
    })
    // El H1 de la página es el título: los títulos del texto bajan un nivel si traen H1
    if (b.querySelector('h1')) {
      Array.prototype.slice.call(b.querySelectorAll('h1,h2,h3,h4,h5')).forEach(function (h) {
        var n = Math.min(+h.tagName[1] + 1, 4)
        var x = doc.createElement('h' + n)
        while (h.firstChild) x.appendChild(h.firstChild)
        h.parentNode.replaceChild(x, h)
      })
    }
    // párrafos vacíos
    Array.prototype.slice.call(b.querySelectorAll('p')).forEach(function (p) {
      if (!p.textContent.replace(/ /g, ' ').trim() && !p.querySelector('img')) quitar(p)
    })
    return b
  }

  var td = new TurndownService({ headingStyle: 'atx', bulletListMarker: '-', emDelimiter: '*', strongDelimiter: '**', codeBlockStyle: 'fenced' })
  // Tablas como en GitHub: | a | b |
  td.addRule('tabla', {
    filter: 'table',
    replacement: function (_, tabla) {
      var filas = Array.prototype.slice.call(tabla.querySelectorAll('tr')).filter(function (tr) {
        var t = tr.closest('table'); return t === tabla
      })
      if (!filas.length) return ''
      var celda = function (x) { return x.textContent.replace(/ /g, ' ').replace(/\s+/g, ' ').trim().replace(/\|/g, '\\|') }
      var filasTxt = filas.map(function (tr) { return Array.prototype.slice.call(tr.children).map(celda) })
      var cols = Math.max.apply(null, filasTxt.map(function (f) { return f.length }))
      var linea = function (f) { var r = f.slice(); while (r.length < cols) r.push(''); return '| ' + r.join(' | ') + ' |' }
      var sep = '|' + new Array(cols + 1).join(' --- |')
      return '\n\n' + [linea(filasTxt[0]), sep].concat(filasTxt.slice(1).map(linea)).join('\n') + '\n\n'
    }
  })
  td.remove(['style', 'script'])

  function aMarkdown(html) {
    var md = td.turndown(limpiar(html))
    return md.replace(/ /g, ' ').replace(/^(\s*)([-*]|\d+\.)[ ]{2,}/gm, '$1$2 ')
      .replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim() + '\n'
  }

  var espera = function (ms) { return new Promise(function (r) { setTimeout(r, ms) }) }

  // El campo tiene dos modos: Markdown (texto) y Texto enriquecido. En Markdown la barra de
  // botones queda deshabilitada.
  function controlDe(editor) {
    var n = editor
    while (n && !n.querySelector('button[role="switch"]')) n = n.parentElement
    return n
  }
  function enMarkdown(control) {
    var b = control && control.querySelector('[class*="ToolbarButton"]')
    return !!(b && b.disabled)
  }

  function pegarTexto(destino, md) {
    var dt = new DataTransfer()
    dt.setData('text/plain', md)
    var otro = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })
    otro[YA] = true
    destino.dispatchEvent(otro)
  }

  // En Texto enriquecido el editor de Decap pierde tablas y negritas al pegar HTML.
  // Se pasa un momento a Markdown, se pega al final y se regresa.
  // Al cambiar de modo Decap vuelve a dibujar el campo: se ubica de nuevo por la posición del interruptor
  function interruptor(i) { return document.querySelectorAll('button[role="switch"]')[i] }
  function editorJunto(sw) {
    var n = sw
    while (n && !n.querySelector('[data-slate-editor="true"]')) n = n.parentElement
    return n && n.querySelector('[data-slate-editor="true"]')
  }
  async function pegarEnEnriquecido(control, editor, md) {
    var tenia = editor.textContent.replace(/﻿/g, '').trim().length > 0
    var sw = control.querySelector('button[role="switch"]')
    var i = Array.prototype.indexOf.call(document.querySelectorAll('button[role="switch"]'), sw)
    sw.click()
    await espera(350)
    var raw = editorJunto(interruptor(i))
    if (!raw) return
    raw.focus()
    var hojas = raw.querySelectorAll('[data-slate-string], [data-slate-zero-width]')
    var ultima = hojas[hojas.length - 1]
    var txt = ultima && (ultima.firstChild || ultima)
    if (txt) {
      var r = document.createRange()
      var fin = ultima.hasAttribute('data-slate-zero-width') ? 0 : (txt.textContent || '').length
      r.setStart(txt, fin); r.collapse(true)
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r)
      await espera(60)
    }
    pegarTexto(raw, (tenia ? '\n\n' : '') + md)
    await espera(250)
    interruptor(i).click()
  }
  window.igAMarkdown = aMarkdown // para pruebas desde la consola
  window.igLimpiar = function (h) { return limpiar(h).innerHTML }

  document.addEventListener('paste', function (ev) {
    if (ev[YA]) return
    var editor = ev.target && ev.target.closest && ev.target.closest('[data-slate-editor="true"]')
    if (!editor) return
    var cd = ev.clipboardData
    var html = cd && cd.getData('text/html')
    if (!html || !/<(p|h[1-6]|li|table|br|div)\b/i.test(html)) return
    var md
    try { md = aMarkdown(html) } catch (e) { return } // si falla, pega normal
    if (!md.trim()) return
    ev.preventDefault()
    ev.stopImmediatePropagation()
    var control = controlDe(editor)
    if (!control || enMarkdown(control)) pegarTexto(ev.target, md)
    else pegarEnEnriquecido(control, editor, md)
  }, true)
})()
