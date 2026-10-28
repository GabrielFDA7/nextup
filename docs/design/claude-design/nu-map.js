(function () {
  if (window.customElements.get('nu-map')) return;
  if (!document.getElementById('nu-map-kf')) {
    var s = document.createElement('style');
    s.id = 'nu-map-kf';
    s.textContent = '@keyframes nuPulse{0%{transform:scale(.5);opacity:.5}100%{transform:scale(1.9);opacity:0}}';
    document.head.appendChild(s);
  }
  // Plano próprio 400x440 (norte para cima, entrada embaixo). Usado pelas telas do turno 1.
  var P = {
    jungle: [96, 284, 'Jungle Cruise'], thunder: [46, 162, 'Big Thunder'], peter: [166, 130, 'Peter Pan'],
    dwarfs: [230, 90, 'Seven Dwarfs'], dumbo: [300, 66, 'Dumbo'], tron: [350, 120, 'TRON'],
    space: [346, 202, 'Space Mountain']
  };
  var DOTS = [[148, 152], [74, 254], [34, 206], [292, 256], [326, 276], [262, 70], [196, 114], [128, 296], [270, 206], [188, 74], [120, 190]];
  var uid = 0;
  function st(x) { return ' style="' + x + '"'; }
  function esc(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
  function smoothPath(p) {
    if (p.length < 2) return '';
    var d = 'M' + p[0][0] + ' ' + p[0][1];
    for (var i = 0; i < p.length - 1; i++) {
      var p0 = p[i - 1] || p[i], p1 = p[i], p2 = p[i + 1], p3 = p[i + 2] || p2;
      d += ' C' + (p1[0] + (p2[0] - p0[0]) / 6).toFixed(1) + ' ' + (p1[1] + (p2[1] - p0[1]) / 6).toFixed(1) + ' ' +
        (p2[0] - (p3[0] - p1[0]) / 6).toFixed(1) + ' ' + (p2[1] - (p3[1] - p1[1]) / 6).toFixed(1) + ' ' + p2[0] + ' ' + p2[1];
    }
    return d;
  }

  class NuMap extends HTMLElement {
    static get observedAttributes() { return ['look', 'view', 'hero', 'tag', 'stops', 'route', 'me', 'pick', 'dim', 'data']; }
    connectedCallback() {
      this.style.display = 'block'; this.style.width = '100%'; this.style.height = '100%'; this.style.overflow = 'hidden';
      if (!this._click) {
        this._click = function (e) {
          var svg = this.querySelector('svg'); if (!svg || !svg.getScreenCTM()) return;
          var pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
          var p = pt.matrixTransform(svg.getScreenCTM().inverse());
          this.dispatchEvent(new CustomEvent('nu-pick', { bubbles: true, detail: { x: Math.round(p.x), y: Math.round(p.y) } }));
        }.bind(this);
        this.addEventListener('click', this._click);
      }
      this.render();
    }
    attributeChangedCallback() { if (this.isConnected) this.render(); }
    render() {
      var id = 'nm' + (++uid);
      var look = this.getAttribute('look') || 'a', B = look === 'b', C = look === 'c';
      var view = this.getAttribute('view') || '0 0 400 440';
      var D = null, raw = this.getAttribute('data');
      if (raw) { try { D = JSON.parse(raw); } catch (e) { D = null; } }
      var pins, heroPt, me, dots, routePts, smooth = false;
      if (D) {
        pins = D.pins || []; heroPt = D.hero || null; me = D.me || null; dots = D.dots || []; routePts = D.route || []; smooth = true;
      } else {
        var stops = (this.getAttribute('stops') || '').split(',').filter(function (k) { return P[k]; });
        var hero = this.getAttribute('hero');
        var meA = this.getAttribute('me');
        me = (meA === 'none' || this.getAttribute('pick') === '1') ? null : (meA || '200,330').split(',').map(Number);
        pins = stops.map(function (k, i) { return { x: P[k][0], y: P[k][1], n: i + 1, label: P[k][2] }; });
        heroPt = hero && P[hero] ? { x: P[hero][0], y: P[hero][1], tag: this.getAttribute('tag') || '' } : null;
        dots = DOTS.slice();
        if (stops.indexOf('dumbo') < 0 && hero !== 'dumbo') dots.push([300, 66, 1]);
        routePts = this.getAttribute('route') === '1' && pins.length ? (me ? [me] : []).concat(pins.map(function (p) { return [p.x, p.y]; })) : [];
      }
      var o = [];
      function land(v) { return 'fill:var(' + v + ')' + (B ? ';stroke:var(--m-stroke);stroke-width:2' : ''); }
      var water = B ? 'fill:url(#' + id + 'h);stroke:var(--m-stroke);stroke-width:2' : 'fill:var(--m-water)';
      o.push('<defs><pattern id="' + id + 'h" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="7" height="7"' + st('fill:var(--m-bg)') + '/><line x1="0" y1="0" x2="0" y2="7"' + st('stroke:var(--m-water);stroke-width:1.6') + '/></pattern></defs>');
      o.push('<rect x="-200" y="-200" width="800" height="900"' + st('fill:var(--m-bg)') + '/>');
      o.push('<path d="M-200 394 Q200 372 600 394 L600 700 L-200 700 Z"' + st(water) + '/>');
      o.push('<ellipse cx="62" cy="182" rx="56" ry="64"' + st(land('--m-l1')) + '/>');
      o.push('<ellipse cx="110" cy="272" rx="76" ry="44"' + st(land('--m-l2')) + '/>');
      o.push('<ellipse cx="150" cy="160" rx="42" ry="36"' + st(land('--m-l2')) + '/>');
      o.push('<ellipse cx="220" cy="106" rx="80" ry="52"' + st(land('--m-l1')) + '/>');
      o.push('<ellipse cx="302" cy="68" rx="48" ry="32"' + st(land('--m-l2')) + '/>');
      o.push('<ellipse cx="314" cy="226" rx="72" ry="62"' + st(land('--m-l1')) + '/>');
      o.push('<ellipse cx="354" cy="122" rx="38" ry="32"' + st(land('--m-l2')) + '/>');
      o.push('<ellipse cx="100" cy="112" rx="52" ry="30"' + st(water) + '/>');
      o.push('<ellipse cx="98" cy="110" rx="22" ry="10"' + st(land('--m-l2')) + '/>');
      o.push('<circle cx="200" cy="240" r="46"' + st(water) + '/>');
      o.push('<circle cx="200" cy="240" r="33"' + st(land('--m-l2')) + '/>');
      o.push('<rect x="183" y="272" width="34" height="112" rx="6"' + st(land('--m-l2')) + '/>');
      var pw = B ? 2.5 : (C ? 6 : 9);
      var ps = 'fill:none;stroke:var(--m-path);stroke-width:' + pw + ';stroke-linecap:round;stroke-linejoin:round';
      ['M200 384 L200 274', 'M200 240 L128 268', 'M200 240 L156 174', 'M200 240 L214 152', 'M200 240 L282 226',
        'M64 262 Q40 210 46 162 Q90 140 166 130 Q200 98 230 90 Q290 58 350 120 Q366 160 346 202 Q330 240 282 226',
        'M128 268 Q92 292 64 262'].forEach(function (d) { o.push('<path d="' + d + '"' + st(ps) + '/>'); });
      var ls = 'fill:var(--m-text);font-size:' + (B ? 10 : 9.5) + 'px;font-weight:' + (B ? 800 : 700) + ';letter-spacing:1.6px;text-anchor:middle';
      [['FRONTIERLAND', 60, 236], ['ADVENTURELAND', 118, 308], ['FANTASYLAND', 222, 150], ['TOMORROWLAND', 318, 280], ['MAIN STREET', 246, 352]]
        .forEach(function (l) { o.push('<text x="' + l[1] + '" y="' + l[2] + '"' + st(ls) + '>' + l[0] + '</text>'); });
      dots.forEach(function (d) { o.push('<circle cx="' + d[0] + '" cy="' + d[1] + '" r="' + (d[2] ? 5 : 3.5) + '"' + st('fill:var(--m-dot)') + '/>'); });

      if (routePts.length > 1) {
        var rd = smooth ? smoothPath(routePts) : 'M' + routePts.map(function (p) { return p[0] + ' ' + p[1]; }).join(' L');
        if (C) o.push('<path d="' + rd + '"' + st('fill:none;stroke:var(--m-route);stroke-width:' + (smooth ? 14 : 12) + ';opacity:' + (smooth ? .16 : .22) + ';stroke-linecap:round;stroke-linejoin:round') + '/>');
        var rs = B ? 'stroke-width:4;stroke-dasharray:9 6' : (C ? (smooth ? 'stroke-width:5;stroke-dasharray:0.1 10;stroke-linecap:round' : 'stroke-width:3') : 'stroke-width:4;stroke-dasharray:0.1 9;stroke-linecap:round');
        o.push('<path d="' + rd + '"' + st('fill:none;stroke:var(--m-route);stroke-linejoin:round;' + rs) + '/>');
      }
      var halo = 'paint-order:stroke;stroke:var(--m-bg);stroke-width:4px;stroke-linejoin:round;';
      if (me) {
        o.push('<circle cx="' + me[0] + '" cy="' + me[1] + '" r="16"' + st('fill:var(--m-me);transform-box:fill-box;transform-origin:center;animation:nuPulse 2.2s ease-out infinite') + '/>');
        o.push('<circle cx="' + me[0] + '" cy="' + me[1] + '" r="8.5"' + st('fill:var(--m-me);stroke:#fff;stroke-width:3') + '/>');
        o.push('<text x="' + (me[0] + 16) + '" y="' + (me[1] + 5) + '"' + st(halo + 'fill:var(--m-pin);font-size:12px;font-weight:800') + '>' + (B ? 'VOCÊ' : 'Você') + '</text>');
      }
      pins.forEach(function (p) {
        var x = p.x, y = p.y;
        if (B) o.push('<rect x="' + (x - 13) + '" y="' + (y - 13) + '" width="26" height="26" rx="3"' + st('fill:var(--m-pin);stroke:var(--m-pin-ring);stroke-width:2') + '/>');
        else {
          if (C) o.push('<circle cx="' + x + '" cy="' + y + '" r="18"' + st('fill:none;stroke:var(--m-pin);stroke-width:1.5;opacity:.4') + '/>');
          o.push('<circle cx="' + x + '" cy="' + y + '" r="' + (C ? 12 : 13) + '"' + st('fill:var(--m-pin);stroke:var(--m-pin-ring);stroke-width:' + (C ? 0 : 3)) + '/>');
        }
        o.push('<text x="' + x + '" y="' + (y + 5) + '"' + st('fill:var(--m-pin-ink);font-size:14px;font-weight:800;text-anchor:middle') + '>' + p.n + '</text>');
        var right = x < 290, name = B ? String(p.label).toUpperCase() : p.label;
        o.push('<text x="' + (right ? x + 20 : x - 20) + '" y="' + (y + 4) + '"' + st(halo + 'fill:var(--m-pin);font-size:' + (B ? 10.5 : 11.5) + 'px;font-weight:' + (B ? 800 : 700) + ';text-anchor:' + (right ? 'start' : 'end')) + '>' + esc(name) + '</text>');
      });
      if (heroPt) {
        var hx = heroPt.x, hy = heroPt.y, tag = heroPt.tag || '';
        if (B) {
          o.push('<rect x="' + (hx - 17) + '" y="' + (hy - 17) + '" width="34" height="34" rx="3"' + st('fill:var(--m-hero);stroke:var(--m-stroke);stroke-width:3') + '/>');
          o.push('<path d="M' + (hx - 5) + ' ' + (hy - 8) + ' L' + (hx + 8) + ' ' + hy + ' L' + (hx - 5) + ' ' + (hy + 8) + ' Z"' + st('fill:var(--m-hero-ink)') + '/>');
        } else {
          o.push('<circle cx="' + hx + '" cy="' + hy + '" r="19"' + st('fill:var(--m-hero);stroke:var(--m-pin-ring);stroke-width:3') + '/>');
          o.push('<path transform="translate(' + hx + ' ' + (hy + 0.5) + ')" d="M0 -9 L2.6 -3 L9 -2.8 L4 1.4 L5.6 8 L0 4.4 L-5.6 8 L-4 1.4 L-9 -2.8 L-2.6 -3 Z"' + st('fill:var(--m-hero-ink)') + '/>');
        }
        if (tag) {
          var w = tag.length * 7 + 26, ty = hy - 52, tx = Math.max(w / 2 + 14, Math.min(386 - w / 2, hx));
          o.push('<rect x="' + (tx - w / 2) + '" y="' + ty + '" width="' + w + '" height="26" rx="' + (B ? 3 : 13) + '"' + st('fill:var(--m-label-bg)') + '/>');
          o.push('<path d="M' + (hx - 6) + ' ' + (ty + 26) + ' L' + hx + ' ' + (ty + 33) + ' L' + (hx + 6) + ' ' + (ty + 26) + ' Z"' + st('fill:var(--m-label-bg)') + '/>');
          o.push('<text x="' + tx + '" y="' + (ty + 17.5) + '"' + st('fill:var(--m-label-ink);font-size:12.5px;font-weight:800;text-anchor:middle') + '>' + esc(B ? tag.toUpperCase() : tag) + '</text>');
        }
      }
      if (this.getAttribute('dim') === '1') o.push('<rect x="-200" y="-200" width="800" height="900"' + st('fill:var(--m-bg);opacity:.35') + '/>');
      this.innerHTML = '<svg viewBox="' + view + '" preserveAspectRatio="xMidYMid slice"' + st('display:block;width:100%;height:100%;font-family:inherit;cursor:' + (D && D.pick ? 'crosshair' : 'default')) + '>' + o.join('') + '</svg>';
    }
  }
  window.customElements.define('nu-map', NuMap);
})();
