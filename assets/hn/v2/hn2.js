/* Hacker News Daily · Neon Glass front end (pages rendered by news_scraper/site_v2.py) */
(function () {
  'use strict';
  var R = document.documentElement;
  var CFG = window.HN2CFG || { base: '/hackernews/', ext: '' };
  var FK = 'hnFavoritesV1';
  var SORT_KEY = 'hnFavoritesSortV1';
  var TC = {
    'AI': '#8b5cf6', 'Programming': '#3b82f6', 'Security': '#ef4444', 'Science': '#10b981',
    'Hardware': '#f59e0b', 'Privacy': '#ec4899', 'Open Source': '#22c55e', 'Politics': '#f97316',
    'Business': '#0ea5e9', 'Web': '#06b6d4', 'Culture': '#d946ef', 'Show HN': '#ff6600',
    'Legal': '#64748b', 'Design': '#f472b6', 'DevOps': '#14b8a6', 'Data': '#6366f1',
    'Health': '#4ade80', 'Energy': '#eab308', 'Gaming': '#a855f7', 'Education': '#60a5fa',
    'Finance': '#84cc16', 'Startups': '#fb7185', 'Entertainment': '#c084fc', 'Career': '#2dd4bf', 'Space': '#818cf8', 'Code': '#f43f5e'
  };

  function url(p) {
    if (!CFG.ext) return CFG.base + p;
    return CFG.base + (p === '' || p.slice(-1) === '/' ? p + 'index.html' : p + CFG.ext);
  }
  function dayUrl(d) {
    var a = d.split('-');
    return url(a[0] + '/' + a[1] + '/' + a[2] + '/top_stories_' + a[1] + a[2] + a[0]);
  }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }

  /* ---- scheme / view / language ---- */
  window.setScheme = function () {
    R.dataset.scheme = R.dataset.scheme === 'dark' ? 'light' : 'dark';
    store('hn-scheme-a', R.dataset.scheme);
  };
  function sync() {
    $$('[data-set]').forEach(function (b) {
      var kv = b.dataset.set.split(':');
      b.classList.toggle('on', R.dataset[kv[0]] === kv[1]);
    });
  }
  $$('[data-set]').forEach(function (b) {
    b.addEventListener('click', function () {
      var kv = b.dataset.set.split(':');
      R.dataset[kv[0]] = kv[1];
      store('hn-' + kv[0], kv[1]);
      sync();
    });
  });
  sync();

  /* ---- tag filter on reader pages ---- */
  /* ---- reader filters: one tag chip + the All / Open source scope ---- */
  var scope = (new URLSearchParams(location.search).get('only') === 'code') ? 'code'
    : (sessionStorage.getItem('hn-scope') || 'all');
  function applyFilters() {
    var sel = document.querySelector('.filters .tag.sel'), t = sel ? sel.dataset.t : null, n = 0;
    $$('.stories .story').forEach(function (s) {
      var tags = s.dataset.tags.split('|');
      var ok = (!t || tags.indexOf(t) >= 0) && (scope !== 'code' || tags.indexOf('Code') >= 0);
      s.hidden = !ok;
      n += ok ? 1 : 0;
    });
    var k = document.getElementById('count');
    if (k) k.textContent = n;
    $$('[data-scope]').forEach(function (b) { b.classList.toggle('on', b.dataset.scope === scope); });
  }
  function bindFilters() {
    $$('.filters .tag').forEach(function (c) {
      c.onclick = function (ev) {
        ev.preventDefault();
        var was = c.classList.contains('sel');
        $$('.filters .tag').forEach(function (x) { x.classList.remove('sel'); });
        if (!was) c.classList.add('sel');
        applyFilters();
      };
    });
    $$('[data-scope]').forEach(function (b) {
      b.onclick = function () {
        scope = b.dataset.scope;
        try { sessionStorage.setItem('hn-scope', scope); } catch (e) { /* private mode */ }
        var u = new URL(location.href);
        if (scope === 'code') u.searchParams.set('only', 'code'); else u.searchParams.delete('only');
        history.replaceState(null, '', u);
        applyFilters();
      };
    });
    if ($$('[data-scope]').length) applyFilters();
  }
  bindFilters();

  /* ---- home: top-stories modes and archive months ---- */
  $$('.modes button').forEach(function (b) {
    b.addEventListener('click', function () {
      $$('.modes button,.tblock').forEach(function (x) { x.classList.toggle('on', x.dataset.mode === b.dataset.mode); });
    });
  });
  $$('.mchip').forEach(function (b) {
    b.addEventListener('click', function () {
      $$('.mchip,.mpanel').forEach(function (x) { x.classList.toggle('on', x.dataset.m === b.dataset.m); });
    });
  });

  /* ---- image fallback ---- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fallbackHTML(cls, d, tag) {
    return '<div class="' + cls + ' fb" style="--c:' + (TC[tag] || '#94a3b8') + '" data-tag="' + esc(tag) + '">' +
      '<img class="fbi" src="https://www.google.com/s2/favicons?domain=' + encodeURIComponent(d) + '&sz=64" alt="" loading="lazy">' +
      '<span class="fbd">' + esc(d) + '</span></div>';
  }
  function fixImgs(root) {
    $$('img.th,img.cimg,img.limg', root).forEach(function (i) {
      function swap() {
        var cls = i.className.split(' ')[0];
        var box = (cls === 'limg' || cls === 'cimg') && i.closest('.lead,.card');
        if (box) {  /* home: switch to the text layout, as for stories without an image */
          box.classList.add('noimg');
          if (cls === 'cimg') { i.remove(); return; }
          var d = i.dataset.d || '';
          var band = document.createElement('div');
          band.className = 'band';
          band.innerHTML = '<img class="fbi" src="https://www.google.com/s2/favicons?domain=' + encodeURIComponent(d) + '&sz=64" alt=""><span>' + esc(d) + '</span>';
          if (cls === 'limg') box.querySelector('.ltxt').prepend(band);
          i.remove();
          return;
        }
        var w = document.createElement('div');
        w.innerHTML = fallbackHTML(cls, i.dataset.d || '', i.dataset.tag || '');
        if (i.parentNode) i.parentNode.replaceChild(w.firstChild, i);
      }
      if (i.complete && i.naturalWidth === 0 && i.src) swap();
      else i.addEventListener('error', swap, { once: true });
    });
    $$('img.fbi', root).forEach(function (i) {
      i.addEventListener('error', function () { i.remove(); }, { once: true });
    });
  }
  fixImgs();

  /* ---- keyboard: "/" opens search ---- */
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== '/' || /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
    ev.preventDefault();
    var q = document.getElementById('q');
    if (q) q.focus(); else location.href = url('search/');
  });

  /* ---- favorites (same storage format as the previous site) ---- */
  function favs() {
    try {
      var f = JSON.parse(localStorage.getItem(FK) || '{}');
      return f && typeof f === 'object' && !Array.isArray(f) ? f : {};
    } catch (e) { return {}; }
  }
  function txt(s, c) { var n = s.querySelector(c); return n ? n.textContent.trim() : ''; }
  function favData(s) {
    var img = s.querySelector('img.th');
    return {
      key: 'story-' + s.dataset.id, title: txt(s, '.st .en'), url: s.querySelector('.st a').href,
      titleZh: txt(s, '.st .zh'), summaryEn: txt(s, '.sum.full .en'), summaryZh: txt(s, '.sum.full .zh'),
      imageUrl: img ? img.src : '', scoreText: s.dataset.score, commentsText: s.dataset.comments,
      commentsUrl: s.dataset.hn, createdAt: Number(s.dataset.time || 0) * 1000,
      tags: s.dataset.tags ? s.dataset.tags.split('|') : [], sourcePage: location.pathname + '#story-' + s.dataset.id,
      savedAt: new Date().toISOString()
    };
  }
  function favSync() {
    var f = favs();
    $$('.story').forEach(function (s) {
      var b = s.querySelector('.fav');
      if (!b) return;
      var on = !!f['story-' + s.dataset.id];
      b.classList.toggle('on', on);
      b.textContent = on ? '★' : '☆';
      b.title = on ? 'Remove from favorites' : 'Save to favorites';
    });
    var n = Object.keys(f).length;
    $$('.favn').forEach(function (x) { x.textContent = n; x.hidden = !n; });
  }
  var onFavChange = null;
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.fav');
    if (!b) return;
    ev.preventDefault();
    var s = b.closest('.story'), f = favs(), k = 'story-' + s.dataset.id;
    if (f[k]) { delete f[k]; tombstone([k]); } else f[k] = favData(s);
    store(FK, JSON.stringify(f));
    favSync();
    if (onFavChange) onFavChange();
    Sync.soon();
  });
  favSync();

  /* ---- favorites sync across the owner's devices via a private GitHub Gist ----
     Enabled only on browsers where a gist-scoped token was saved (favorites page with ?sync).
     Merge = union by key, newest savedAt wins; deletions are kept as tombstones for 120 days. */
  var TK = 'hnSyncToken', GK = 'hnSyncGist', TOMB = 'hnFavTombstones', LAST = 'hnSyncLast';
  var GIST_FILE = 'hn-favorites.json', GIST_DESC = 'HN Daily favorites (sync)';
  function tombs() { try { return JSON.parse(localStorage.getItem(TOMB) || '{}'); } catch (e) { return {}; } }
  function tombstone(keys) {
    var t = tombs(), now = new Date().toISOString();
    keys.forEach(function (k) { t[k] = now; });
    store(TOMB, JSON.stringify(t));
  }
  var Sync = {
    token: function () { return localStorage.getItem(TK) || ''; },
    status: function (msg) { $$('.syncstat').forEach(function (n) { n.textContent = msg; }); },
    api: function (path, opt) {
      opt = opt || {};
      opt.headers = { 'Authorization': 'Bearer ' + Sync.token(), 'Accept': 'application/vnd.github+json' };
      if (opt.body) opt.headers['Content-Type'] = 'application/json';
      return fetch('https://api.github.com' + path, opt).then(function (r) {
        if (!r.ok) throw new Error('GitHub ' + r.status);
        return r.json();
      });
    },
    findGist: function () {
      var id = localStorage.getItem(GK);
      if (id) return Sync.api('/gists/' + id).catch(function () { localStorage.removeItem(GK); return Sync.findGist(); });
      return Sync.api('/gists?per_page=100').then(function (list) {
        var g = list.filter(function (x) { return x.files && x.files[GIST_FILE]; })[0];
        if (g) return Sync.api('/gists/' + g.id);
        return Sync.api('/gists', { method: 'POST', body: JSON.stringify({
          description: GIST_DESC, public: false,
          files: (function () { var f = {}; f[GIST_FILE] = { content: '{"favorites":{},"tombstones":{}}' }; return f; })()
        }) });
      }).then(function (g) { store(GK, g.id); return g; });
    },
    readRemote: function (g) {
      var file = g.files[GIST_FILE];
      var body = file && file.truncated ? fetch(file.raw_url).then(function (r) { return r.text(); }) : Promise.resolve(file ? file.content : '');
      return body.then(function (t) { try { return JSON.parse(t || '{}'); } catch (e) { return {}; } });
    },
    merge: function (remote) {
      var lf = favs(), rf = remote.favorites || {}, t = tombs(), rt = remote.tombstones || {}, out = {};
      Object.keys(rt).forEach(function (k) { if (!t[k] || rt[k] > t[k]) t[k] = rt[k]; });
      Object.keys(lf).concat(Object.keys(rf)).forEach(function (k) {
        var a = lf[k], b = rf[k], v = !a ? b : !b ? a : (String(b.savedAt) > String(a.savedAt) ? b : a);
        if (v && !(t[k] && t[k] >= String(v.savedAt || ''))) out[k] = v;
      });
      var cutoff = new Date(Date.now() - 120 * 864e5).toISOString();
      Object.keys(t).forEach(function (k) { if (t[k] < cutoff || out[k]) delete t[k]; });
      return { favorites: out, tombstones: t };
    },
    run: function () {
      if (!Sync.token() || Sync.busy) return Promise.resolve();
      Sync.busy = true;
      Sync.status(R.dataset.lang === 'zh' ? '同步中…' : 'Syncing…');
      var gist;
      return Sync.findGist().then(function (g) { gist = g; return Sync.readRemote(g); }).then(function (remote) {
        var m = Sync.merge(remote), body = JSON.stringify(m);
        store(FK, JSON.stringify(m.favorites));
        store(TOMB, JSON.stringify(m.tombstones));
        favSync();
        if (onFavChange) onFavChange();
        if (body === JSON.stringify({ favorites: remote.favorites || {}, tombstones: remote.tombstones || {} })) return;
        var files = {}; files[GIST_FILE] = { content: body };
        return Sync.api('/gists/' + gist.id, { method: 'PATCH', body: JSON.stringify({ files: files }) });
      }).then(function () {
        store(LAST, String(Date.now()));
        var n = Object.keys(favs()).length, t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        Sync.status(R.dataset.lang === 'zh' ? '已同步 ' + n + ' 条 · ' + t : 'Synced ' + n + ' · ' + t);
      }).catch(function (err) {
        Sync.status((R.dataset.lang === 'zh' ? '同步失败：' : 'Sync failed: ') + err.message);
      }).then(function () { Sync.busy = false; });
    },
    soon: function () {
      if (!Sync.token()) return;
      clearTimeout(Sync._t);
      Sync._t = setTimeout(Sync.run, 1500);
    }
  };
  if (Sync.token() && Date.now() - Number(localStorage.getItem(LAST) || 0) > 60000) Sync.run();

  /* ---- share: native share sheet on phones, clipboard elsewhere (card and full views only) ---- */
  var SHARE_ICON = '<svg class="ico" viewBox="0 0 24 24"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>';
  function toast(msg) {
    var t = document.querySelector('.toast') || document.body.appendChild(Object.assign(document.createElement('div'), { className: 'toast' }));
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('on'); }, 1800);
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.shr');
    if (!b) return;
    ev.preventDefault();
    var s = b.closest('.story'), zh = R.dataset.lang === 'zh';
    var title = txt(s, zh ? '.st .zh' : '.st .en') || txt(s, '.st .en');
    var line = txt(s, zh ? '.sum.one .zh' : '.sum.one .en');
    var link = /^\d+$/.test(s.dataset.id) && Number(s.dataset.id) > 1e7
      ? location.origin + CFG.base + 'share/' + s.dataset.id + '.html'
      : location.origin + location.pathname + '#story-' + s.dataset.id;
    var text = title + (line ? '\n' + line : '');
    if (navigator.share && matchMedia('(pointer: coarse)').matches) {
      navigator.share({ title: title, text: text, url: link }).catch(function () {});
      return;
    }
    var all = text + '\n' + link;
    (navigator.clipboard ? navigator.clipboard.writeText(all) : Promise.reject()).then(function () {
      toast(zh ? '已复制，可以粘贴分享' : 'Copied — paste to share');
    }, function () { window.prompt(zh ? '复制下面的内容' : 'Copy this', all); });
    if (window.gtag) gtag('event', 'share_story', { story_id: s.dataset.id });
  });

  /* ---- client-rendered stories (favorites, search) mirror the static markup ---- */
  function first(s, zh) {
    s = (s || '').trim();
    var re = zh ? /[。！？]/g : /[.!?](?=\s|$)/g, m, min = zh ? 15 : 30;
    while ((m = re.exec(s))) { if (m.index + 1 >= min) return s.slice(0, m.index + 1); }
    return s;
  }
  function dom(u) { return (u || '').replace(/^https?:\/\/(www\.)?/, '').split('/')[0]; }
  function tagH(t) { return '<span class="tag" data-t="' + esc(t) + '" style="--c:' + (TC[t] || '#94a3b8') + '">' + esc(t) + '</span>'; }
  function storyHTML(o, i) {
    var d = dom(o.url), tags = o.tags || [];
    var th = o.img
      ? '<img class="th" loading="lazy" src="' + esc(o.img) + '" data-d="' + esc(d) + '" data-tag="' + esc(tags[0] || '') + '" referrerpolicy="no-referrer" alt="">'
      : fallbackHTML('th', d, tags[0] || '');
    var day = o.date ? '<a class="sday" href="' + dayUrl(o.date) + '#story-' + o.id + '">' + esc(o.date) + '</a>' : '';
    return '<article class="story" data-id="' + esc(o.id) + '" data-tags="' + esc(tags.join('|')) + '" data-score="' + esc(o.score) +
      '" data-comments="' + esc(o.comments) + '" data-hn="' + esc(o.hn) + '" data-time="' + (o.time || 0) + '">' +
      '<a class="thumb" href="' + esc(o.url) + '" target="_blank" rel="noopener">' + th + '</a><button class="fav" aria-label="favorite">☆</button><button class="shr" aria-label="share" title="Share">' + SHARE_ICON + '</button>' +
      '<div class="sbody"><div class="rk">' + String(i + 1).padStart(2, '0') + '</div>' +
      '<h3 class="st"><a href="' + esc(o.url) + '" target="_blank" rel="noopener"><span class="en">' + esc(o.t) + '</span><span class="zh">' + esc(o.z || o.t) + '</span></a><span class="dom">' + esc(d) + '</span></h3>' +
      '<p class="sum one"><span class="en">' + esc(first(o.se)) + '</span><span class="zh">' + esc(first(o.sz, 1)) + '</span></p>' +
      '<p class="sum full"><span class="en">' + esc(o.se) + '</span><span class="zh">' + esc(o.sz) + '</span></p>' +
      '<div class="sfoot"><span class="tags">' + tags.map(tagH).join('') + '</span>' + day +
      '<span class="metas"><span class="m ic-up">' + esc(o.score) + '</span><a class="m ic-chat" href="' + esc(o.hn) + '" target="_blank" rel="noopener">' + esc(o.comments) + '</a></span></div></div></article>';
  }
  function chipsFor(list) {
    var c = {};
    list.forEach(function (o) { (o.tags || []).forEach(function (t) { c[t] = (c[t] || 0) + 1; }); });
    return Object.keys(c).sort(function (a, b) { return c[b] - c[a]; }).map(function (t) {
      return '<a class="tag" href="#" data-t="' + esc(t) + '" style="--c:' + (TC[t] || '#94a3b8') + '">' + esc(t) + '<b>' + c[t] + '</b></a>';
    }).join('');
  }

  function favoritesPage() {
    function render() {
      var f = favs(), sort = localStorage.getItem(SORT_KEY) || 'added';
      var list = Object.keys(f).map(function (k) {
        var v = f[k];
        return {
          id: String(v.key || k).replace('story-', ''), t: v.title, z: v.titleZh, url: v.url, se: v.summaryEn, sz: v.summaryZh,
          img: v.imageUrl, tags: v.tags, score: v.scoreText, comments: v.commentsText, hn: v.commentsUrl,
          time: (v.createdAt || 0) / 1000, saved: v.savedAt
        };
      });
      list.sort(sort === 'score'
        ? function (a, b) { return (parseInt(b.score, 10) || 0) - (parseInt(a.score, 10) || 0); }
        : function (a, b) { return String(b.saved).localeCompare(String(a.saved)); });
      $$('[data-sort]').forEach(function (b) { b.classList.toggle('on', b.dataset.sort === sort); });
      document.getElementById('count').textContent = list.length;
      document.getElementById('empty').hidden = !!list.length;
      document.querySelector('.filters').innerHTML = chipsFor(list);
      document.querySelector('.stories').innerHTML = list.map(storyHTML).join('');
      fixImgs(); favSync(); bindFilters();
    }
    onFavChange = render;
    $$('[data-sort]').forEach(function (b) {
      b.onclick = function () { store(SORT_KEY, b.dataset.sort); render(); };
    });
    document.getElementById('clear').onclick = function () {
      if (confirm(R.dataset.lang === 'zh' ? '清空全部收藏？' : 'Remove all favorites?')) { tombstone(Object.keys(favs())); store(FK, '{}'); render(); Sync.soon(); }
    };
    render();
    syncPanel();
  }

  /* Owner-only sync settings: visible when a token is saved, or when the page is opened with ?sync. */
  function syncPanel() {
    var box = document.getElementById('syncbox');
    var setup = new URLSearchParams(location.search).has('sync');
    if (!box || (!Sync.token() && !setup)) return;
    var zh = R.dataset.lang === 'zh';
    box.hidden = false;
    if (!Sync.token()) {
      box.innerHTML = '<b>' + (zh ? '多设备同步' : 'Sync across devices') + '</b>' +
        '<input id="synctoken" type="password" autocomplete="off" placeholder="GitHub token (gist scope)">' +
        '<button class="ghost" id="syncsave">' + (zh ? '保存并同步' : 'Save & sync') + '</button><span class="syncstat"></span>';
      document.getElementById('syncsave').onclick = function () {
        var v = document.getElementById('synctoken').value.trim();
        if (!v) return;
        store(TK, v);
        syncPanel();
        Sync.run();
      };
      return;
    }
    box.innerHTML = '<b>' + (zh ? '多设备同步已开启' : 'Device sync on') + '</b><span class="syncstat"></span>' +
      '<button class="ghost" id="syncnow">' + (zh ? '立即同步' : 'Sync now') + '</button>' +
      '<button class="ghost" id="syncoff">' + (zh ? '在此设备关闭' : 'Turn off here') + '</button>';
    document.getElementById('syncnow').onclick = Sync.run;
    document.getElementById('syncoff').onclick = function () {
      if (!confirm(zh ? '在这台设备上关闭同步？（收藏保留在本机）' : 'Turn off sync on this device? (favorites stay here)')) return;
      [TK, GK, LAST].forEach(function (k) { localStorage.removeItem(k); });
      box.hidden = true;
    };
    Sync.status(localStorage.getItem(LAST) ? (zh ? '上次同步 ' : 'Last sync ') + new Date(Number(localStorage.getItem(LAST))).toLocaleString() : '');
  }

  function searchPage() {
    var IDX = null, shown = 60, res = [];
    var q = document.getElementById('q'), P = new URLSearchParams(location.search);
    var sort = P.get('sort') || 'relevance', tagF = P.get('tag') || '';
    q.value = P.get('q') || '';
    function ph() { if (!q.dataset.phEn) q.dataset.phEn = q.placeholder; q.placeholder = R.dataset.lang === 'zh' ? q.dataset.phZh : q.dataset.phEn; }
    ph();
    $$('[data-set^="lang:"]').forEach(function (b) { b.addEventListener('click', ph); });
    fetch(CFG.base + 'search/manifest.json').then(function (r) { return r.json(); }).then(function (man) {
      return Promise.all(man.shards.map(function (m) {
        return fetch(CFG.base + 'search/' + m + '.json').then(function (r) { return r.json(); });
      }));
    }).then(function (parts) {
      IDX = [];
      parts.forEach(function (rows) {
        rows.forEach(function (a) {
          IDX.push({
            id: a[0], t: a[1], z: a[2], url: a[3], tags: a[4], score: a[5], date: a[6], se: a[7], sz: a[8], comments: a[9],
            img: a[10], hn: 'https://news.ycombinator.com/item?id=' + a[0],
            s: (a[1] + ' ' + a[2] + ' ' + a[4].join(' ') + ' ' + (a[3] || '')).toLowerCase(),
            tt: (a[1] + ' ' + a[2]).toLowerCase()
          });
        });
      });
      document.getElementById('total').textContent = IDX.length.toLocaleString();
      run();
    });
    function run() {
      if (!IDX) return;
      var terms = q.value.toLowerCase().split(/\s+/).filter(Boolean);
      res = IDX.filter(function (o) {
        return (!tagF || o.tags.indexOf(tagF) >= 0) && terms.every(function (t) { return o.s.indexOf(t) >= 0; });
      });
      if (sort === 'date') res.sort(function (a, b) { return b.date.localeCompare(a.date) || b.score - a.score; });
      else if (sort === 'score' || !terms.length) res.sort(function (a, b) { return b.score - a.score; });
      else {
        var rel = function (o) { return terms.filter(function (t) { return o.tt.indexOf(t) >= 0; }).length; };
        res.sort(function (a, b) { return rel(b) - rel(a) || b.score - a.score; });
      }
      shown = 60;
      draw();
      var u = new URL(location.href);
      if (q.value) u.searchParams.set('q', q.value); else u.searchParams.delete('q');
      if (tagF) u.searchParams.set('tag', tagF); else u.searchParams.delete('tag');
      if (sort !== 'relevance') u.searchParams.set('sort', sort); else u.searchParams.delete('sort');
      history.replaceState(null, '', u);
    }
    function draw() {
      document.getElementById('count').textContent = res.length.toLocaleString();
      document.querySelector('.stories').innerHTML = res.slice(0, shown).map(storyHTML).join('');
      fixImgs(); favSync();
      document.getElementById('more').hidden = res.length <= shown;
      $$('[data-sort]').forEach(function (b) { b.classList.toggle('on', b.dataset.sort === sort); });
      $$('.filters .tag').forEach(function (c) { c.classList.toggle('sel', c.dataset.t === tagF); });
    }
    var tm;
    q.addEventListener('input', function () { clearTimeout(tm); tm = setTimeout(run, 120); });
    $$('[data-sort]').forEach(function (b) { b.onclick = function () { sort = b.dataset.sort; run(); }; });
    $$('.filters .tag').forEach(function (c) {
      c.onclick = function (ev) { ev.preventDefault(); tagF = tagF === c.dataset.t ? '' : c.dataset.t; run(); };
    });
    document.getElementById('more').onclick = function () { shown += 60; draw(); };
    q.focus();
  }

  window.HN2 = { favoritesPage: favoritesPage, searchPage: searchPage };
})();
