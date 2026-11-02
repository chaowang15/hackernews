// HackerNews pages - global JS (lightbox)

(function () {
  function qs(id) { return document.getElementById(id); }

  function ensureLightbox() {
    let lb = qs("hnLightbox");
    if (lb) return lb;

    const html = `
<div class="hn-lightbox" id="hnLightbox" aria-hidden="true">
  <div class="hn-lightbox-inner">
    <button class="hn-lightbox-close" id="hnLightboxClose" aria-label="Close">×</button>
    <img class="hn-lightbox-img" id="hnLightboxImg" src="" alt="full size image"/>
  </div>
</div>`;
    document.body.insertAdjacentHTML("beforeend", html);
    return qs("hnLightbox");
  }

  function openLightbox(src) {
    const lb = ensureLightbox();
    const lbImg = qs("hnLightboxImg");
    lbImg.src = src;
    lb.classList.add("is-open");
    lb.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    const lb = qs("hnLightbox");
    const lbImg = qs("hnLightboxImg");
    if (!lb || !lbImg) return;
    lb.classList.remove("is-open");
    lb.setAttribute("aria-hidden", "true");
    lbImg.src = "";
    document.body.style.overflow = "";
  }

  document.addEventListener("click", function (e) {
    const t = e.target;

    // Click image => open
    if (t && t.classList && t.classList.contains("hn-img")) {
      const src = t.getAttribute("data-full") || t.getAttribute("src");
      if (src) openLightbox(src);
      return;
    }

    // Close button
    if (t && t.id === "hnLightboxClose") {
      closeLightbox();
      return;
    }

    // Click overlay => close
    if (t && t.id === "hnLightbox") {
      closeLightbox();
      return;
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeLightbox();
  });
})();

// ===== Weekly / Monthly digest card-surface toggle =====
(function () {
  function toggleDigestDetails(header) {
    var card = header.closest('.hn-card');
    var details = card && card.querySelector('.hn-digest-details');
    if (!details) return;

    var willOpen = details.hasAttribute('hidden');
    if (willOpen) details.removeAttribute('hidden');
    else details.setAttribute('hidden', '');
    header.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    header.setAttribute('aria-label', willOpen ? 'Hide summary and image' : 'Show summary and image');
  }

  document.addEventListener('click', function (e) {
    var header = e.target.closest('.hn-digest-summary-header');
    if (!header) return;
    // Preserve the headline and HN score/comment links inside the card.
    if (e.target.closest('a, button')) return;
    toggleDigestDetails(header);
  });

  document.addEventListener('keydown', function (e) {
    var header = e.target.closest('.hn-digest-summary-header');
    if (!header || e.target !== header || (e.key !== 'Enter' && e.key !== ' ')) return;
    e.preventDefault();
    toggleDigestDetails(header);
  });
})();

// ===== Browser-local favorites (no account or server storage) =====
(function () {
  var STORAGE_KEY = 'hnFavoritesV1';
  var SORT_KEY = 'hnFavoritesSortV1';
  var favoriteSortMode = window.localStorage.getItem(SORT_KEY) || 'added';
  var TAG_COLORS = {
    'AI': 'blue', 'Programming': 'indigo', 'Security': 'red',
    'Science': 'teal', 'Business': 'amber', 'Finance': 'amber',
    'Hardware': 'slate', 'Open Source': 'green', 'Design': 'pink',
    'Web': 'cyan', 'DevOps': 'indigo', 'Data': 'violet',
    'Gaming': 'purple', 'Entertainment': 'purple', 'Politics': 'orange',
    'Health': 'emerald', 'Education': 'sky', 'Career': 'sky',
    'Privacy': 'red', 'Legal': 'orange', 'Culture': 'rose',
    'Space': 'teal', 'Energy': 'emerald', 'Startups': 'amber',
    'Show HN': 'green'
  };

  function loadFavorites() {
    try {
      var parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}');
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function saveFavorites(favorites) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
      return true;
    } catch (e) {
      return false;
    }
  }

  function favoriteKey(card) {
    var titleLink = card.querySelector('.hn-title a');
    return card.id || (titleLink && titleLink.href) || '';
  }

  function createdTimestamp(text) {
    var match = String(text || '').match(/Created:\s*([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})\s*\/\s*(\d{1,2}):(\d{2})/);
    if (!match) return 0;
    var months = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };
    if (months[match[1]] === undefined) return 0;
    return Date.UTC(Number(match[3]), months[match[1]], Number(match[2]), Number(match[4]), Number(match[5]));
  }

  function cardData(card) {
    var titleLink = card.querySelector('.hn-title a');
    var zh = card.querySelector('.hn-digest-summary-header .hn-meta');
    var summaryEn = card.querySelector('.hn-digest-details .hn-text-en');
    var summaryZh = card.querySelector('.hn-digest-details .hn-text-zh');
    var image = card.querySelector('.hn-digest-details img.hn-img');
    var score = card.querySelector('.hn-stat-score');
    var comments = card.querySelector('.hn-stat-comments');
    var created = card.querySelector('.hn-meta2-created');
    var hnTime = Number(card.getAttribute('data-hn-time') || 0);
    var tags = Array.prototype.map.call(card.querySelectorAll('.hn-tag'), function (tag) {
      return tag.textContent.trim();
    });
    var key = favoriteKey(card);
    return {
      key: key,
      title: titleLink ? titleLink.textContent.trim() : '',
      url: titleLink ? titleLink.href : '',
      titleZh: zh ? zh.textContent.trim() : '',
      summaryEn: summaryEn ? summaryEn.textContent.trim() : '',
      summaryZh: summaryZh ? summaryZh.textContent.trim() : '',
      imageUrl: image ? (image.getAttribute('data-full') || image.src) : '',
      scoreText: score ? score.textContent.trim() : '',
      commentsText: comments ? comments.textContent.trim() : '',
      commentsUrl: comments ? comments.href : (score ? score.href : ''),
      createdText: created ? created.textContent.trim() : '',
      createdAt: hnTime ? hnTime * 1000 : createdTimestamp(created ? created.textContent : ''),
      tags: tags,
      sourcePage: window.location.pathname + window.location.hash,
      savedAt: new Date().toISOString()
    };
  }

  function setFavoriteButtonState(button, isSaved) {
    button.classList.toggle('is-saved', isSaved);
    button.textContent = isSaved ? '★' : '☆';
    button.setAttribute('aria-label', isSaved ? 'Remove from favorites' : 'Add to favorites');
    button.setAttribute('title', isSaved ? 'Remove from favorites' : 'Add to favorites');
  }

  function updateFavoritesCount() {
    var count = Object.keys(loadFavorites()).length;
    document.querySelectorAll('.hn-favorites-count').forEach(function (node) {
      node.textContent = String(count);
    });
  }

  function createFavoriteButton(card) {
    var key = favoriteKey(card);
    if (!key || card.querySelector('.hn-favorite-btn')) return;
    var header = card.querySelector('.hn-digest-summary-header');
    var tags = header && header.querySelector('.hn-tags');
    if (!header || !tags) return;
    var actions = card.querySelector('.hn-card-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'hn-card-actions';
      tags.appendChild(actions);
    }
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'hn-favorite-btn';
    button.setAttribute('data-favorite-key', key);
    setFavoriteButtonState(button, !!loadFavorites()[key]);
    // Button events stop propagation so actions can share the card's stats row
    // without toggling the collapsible summary header.
    actions.appendChild(button);
  }

  function injectFavoriteButtons(root) {
    (root || document).querySelectorAll('.hn-card .hn-digest-summary-header').forEach(function (header) {
      createFavoriteButton(header.closest('.hn-card'));
    });
  }

  function injectFavoritesLink() {
    if (document.querySelector('.hn-favorites-nav')) return;
    var heading = document.querySelector('.hn-h1');
    if (!heading) return;
    var row = document.createElement('div');
    row.className = 'hn-heading-row';
    heading.parentNode.insertBefore(row, heading);
    row.appendChild(heading);
    var link = document.createElement('a');
    link.className = 'hn-favorites-nav';
    link.href = '/hackernews/favorites/';
    link.setAttribute('aria-label', 'Open favorite stories');
    link.innerHTML = '<span aria-hidden="true">★</span><span class="hn-favorites-label">Favorites</span><span class="hn-favorites-count">0</span>';
    row.appendChild(link);
    updateFavoritesCount();
  }

  function addText(parent, className, text, tagName) {
    if (!text) return null;
    var node = document.createElement(tagName || 'p');
    node.className = className;
    node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function renderFavoriteCard(item, index) {
    var card = document.createElement('div');
    card.className = 'hn-card hn-card-compact hn-no-collapse';
    card.id = item.key && item.key.indexOf('story-') === 0 ? item.key : '';
    card.setAttribute('data-tags', (item.tags || []).join(','));
    if (item.createdAt) card.setAttribute('data-created-time', String(item.createdAt));

    var body = document.createElement('div');
    body.className = 'hn-body';
    var header = document.createElement('div');
    header.className = 'hn-digest-summary-header';
    header.setAttribute('role', 'button');
    header.setAttribute('tabindex', '0');
    header.setAttribute('aria-expanded', 'true');
    header.setAttribute('aria-label', 'Hide summary and image');

    var title = document.createElement('p');
    title.className = 'hn-title';
    title.appendChild(document.createTextNode('(' + index + ') '));
    var titleLink = document.createElement('a');
    titleLink.href = item.url || '#';
    titleLink.target = '_blank';
    titleLink.rel = 'noopener noreferrer';
    titleLink.textContent = item.title || 'Untitled story';
    title.appendChild(titleLink);
    header.appendChild(title);
    addText(header, 'hn-meta hn-text-zh', item.titleZh);
    if (item.createdText) {
      var createdMeta = document.createElement('p');
      createdMeta.className = 'hn-meta2';
      addText(createdMeta, 'hn-meta2-created', item.createdText, 'span');
      header.appendChild(createdMeta);
    }

    var tags = document.createElement('div');
    tags.className = 'hn-tags';
    if (item.scoreText) {
      var score = document.createElement('a');
      score.className = 'hn-stat hn-stat-score';
      score.href = item.commentsUrl || '#';
      score.target = '_blank'; score.rel = 'noopener noreferrer';
      score.textContent = item.scoreText;
      tags.appendChild(score);
    }
    if (item.commentsText) {
      var comments = document.createElement('a');
      comments.className = 'hn-stat hn-stat-comments';
      comments.href = item.commentsUrl || '#';
      comments.target = '_blank'; comments.rel = 'noopener noreferrer';
      comments.textContent = item.commentsText;
      tags.appendChild(comments);
    }
    (item.tags || []).forEach(function (tagText) {
      var tag = document.createElement('span');
      tag.className = 'hn-tag hn-tag--' + (TAG_COLORS[tagText] || 'slate');
      tag.setAttribute('data-tag', tagText);
      tag.textContent = tagText;
      tags.appendChild(tag);
    });
    header.appendChild(tags);

    var details = document.createElement('div');
    details.className = 'hn-digest-details';
    addText(details, 'hn-text-en hn-digest-summary', item.summaryEn);
    addText(details, 'hn-text-zh hn-digest-summary', item.summaryZh);
    if (item.imageUrl) {
      var image = document.createElement('img');
      image.className = 'hn-img hn-digest-img';
      image.src = item.imageUrl;
      image.setAttribute('data-full', item.imageUrl);
      image.alt = 'preview image';
      image.loading = 'lazy';
      image.decoding = 'async';
      details.appendChild(image);
    }
    body.appendChild(header);
    body.appendChild(details);
    card.appendChild(body);
    return card;
  }

  function renderFavoritesPage() {
    var list = document.getElementById('hn-favorites-list');
    if (!list) return;
    var favorites = loadFavorites();
    var items = Object.keys(favorites).map(function (key) { return favorites[key]; });
    items.sort(function (a, b) {
      if (favoriteSortMode === 'created') {
        return Number(b.createdAt || createdTimestamp(b.createdText)) - Number(a.createdAt || createdTimestamp(a.createdText))
          || String(b.savedAt).localeCompare(String(a.savedAt));
      }
      return String(b.savedAt).localeCompare(String(a.savedAt));
    });
    list.textContent = '';
    var empty = document.getElementById('hn-favorites-empty');
    if (empty) empty.hidden = items.length > 0;
    items.forEach(function (item, index) {
      list.appendChild(renderFavoriteCard(item, index + 1));
    });
    injectFavoriteButtons(list);
    document.dispatchEvent(new CustomEvent('hn:favorites-rendered', { detail: { root: list } }));
  }

  function initFavoritesSort() {
    var list = document.getElementById('hn-favorites-list');
    if (!list || document.querySelector('.hn-favorites-sort-bar')) return;
    var bar = document.createElement('div');
    bar.className = 'hn-sort-bar hn-favorites-sort-bar';
    var label = document.createElement('span');
    label.className = 'hn-sort-label';
    label.textContent = 'Sort by:';
    bar.appendChild(label);
    [
      { key: 'added', text: 'Recently Added' },
      { key: 'created', text: 'Newest Stories' }
    ].forEach(function (mode) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'hn-sort-toggle-btn' + (favoriteSortMode === mode.key ? ' is-active' : '');
      button.setAttribute('data-favorites-sort', mode.key);
      button.textContent = mode.text;
      bar.appendChild(button);
    });
    list.parentNode.insertBefore(bar, list);
    bar.addEventListener('click', function (e) {
      var button = e.target.closest('[data-favorites-sort]');
      if (!button) return;
      favoriteSortMode = button.getAttribute('data-favorites-sort');
      window.localStorage.setItem(SORT_KEY, favoriteSortMode);
      bar.querySelectorAll('[data-favorites-sort]').forEach(function (candidate) {
        candidate.classList.toggle('is-active', candidate === button);
      });
      renderFavoritesPage();
    });
  }

  function hydrateFavoriteCreatedDates() {
    var favorites = loadFavorites();
    var missing = Object.keys(favorites).filter(function (key) {
      return !favorites[key].createdText && favorites[key].sourcePage && favorites[key].key;
    });
    if (!missing.length || typeof window.fetch !== 'function') return;
    var pages = {};
    var updates = {};
    missing.forEach(function (key) {
      var page = favorites[key].sourcePage.split('#')[0];
      if (!pages[page]) pages[page] = [];
      pages[page].push(key);
    });
    Promise.all(Object.keys(pages).map(function (page) {
      return window.fetch(page).then(function (response) {
        if (!response.ok) throw new Error('Page unavailable');
        return response.text();
      }).then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        pages[page].forEach(function (key) {
          var card = doc.getElementById(favorites[key].key);
          var created = card && card.querySelector('.hn-meta2-created');
          if (!created) return;
          var hnTime = Number(card.getAttribute('data-hn-time') || 0);
          updates[key] = {
            createdText: created.textContent.trim(),
            createdAt: hnTime ? hnTime * 1000 : createdTimestamp(created.textContent)
          };
        });
      }).catch(function () { /* Keep older favorite usable when its source page is unavailable. */ });
    })).then(function () {
      var current = loadFavorites();
      var changed = false;
      Object.keys(updates).forEach(function (key) {
        if (!current[key]) return;
        current[key].createdText = updates[key].createdText;
        current[key].createdAt = updates[key].createdAt;
        changed = true;
      });
      if (changed && saveFavorites(current)) renderFavoritesPage();
    });
  }

  document.addEventListener('click', function (e) {
    var button = e.target.closest('.hn-favorite-btn');
    if (!button) return;
    e.preventDefault();
    e.stopPropagation();
    var card = button.closest('.hn-card');
    var key = button.getAttribute('data-favorite-key') || favoriteKey(card);
    if (!card || !key) return;
    var favorites = loadFavorites();
    if (favorites[key]) delete favorites[key];
    else favorites[key] = cardData(card);
    if (!saveFavorites(favorites)) return;
    setFavoriteButtonState(button, !!favorites[key]);
    updateFavoritesCount();
    if (document.getElementById('hn-favorites-page')) renderFavoritesPage();
  });

  function initFavorites() {
    injectFavoritesLink();
    renderFavoritesPage();
    initFavoritesSort();
    injectFavoriteButtons(document);
    hydrateFavoriteCreatedDates();
  }

  window.addEventListener('storage', function (e) {
    if (e.key !== STORAGE_KEY) return;
    renderFavoritesPage();
    document.querySelectorAll('.hn-favorite-btn').forEach(function (button) {
      setFavoriteButtonState(button, !!loadFavorites()[button.getAttribute('data-favorite-key')]);
    });
    updateFavoritesCount();
  });

  initFavorites();
})();

(function () {
  const btn = document.createElement("button");
  btn.className = "hn-goup";
  btn.type = "button";
  btn.textContent = "↑ Top";
  btn.setAttribute("aria-label", "Go to top");
  btn.style.display = "none";
  document.body.appendChild(btn);

  const CONTENT_MAX_W = 920; // must match --hn-maxw in CSS
  const GAP = 12; // gap between content edge and button
  const FALLBACK_RIGHT = 14; // fallback right when viewport is narrow

  const positionBtn = () => {
    const vw = window.innerWidth;
    const margin = (vw - CONTENT_MAX_W) / 2;
    if (margin > 80) {
      // Wide screen: place button just outside content right edge
      btn.style.right = (margin - btn.offsetWidth - GAP) + "px";
    } else {
      // Narrow screen: fallback to fixed right
      btn.style.right = FALLBACK_RIGHT + "px";
    }
  };

  const toggle = () => {
    const y = window.scrollY || document.documentElement.scrollTop || 0;
    if (y > 600) {
      btn.style.display = "block";
      positionBtn();
    } else {
      btn.style.display = "none";
    }
  };

  btn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  window.addEventListener("scroll", toggle, { passive: true });
  window.addEventListener("resize", positionBtn, { passive: true });
  toggle();
})();

(function () {
  // Keywords in image URLs that indicate placeholder/blank images
  var BLANK_URL_KEYWORDS = [
    "blank", "placeholder", "no-image", "noimage", "default-og",
    "default_og", "fallback", "missing", "empty"
  ];

  function markNoImage(img, reason) {
    img.classList.add("hn-img--hidden");
    img.setAttribute("data-img-status", reason || "bad");
    img.style.display = "none";
  }

  function markTiny(img) {
    img.classList.add("hn-img--tiny");
    img.removeAttribute("data-full"); // disable lightbox for tiny images
  }

  /** Check if the URL contains known blank/placeholder keywords */
  function isBlankUrl(src) {
    if (!src) return false;
    var lower = src.toLowerCase();
    for (var i = 0; i < BLANK_URL_KEYWORDS.length; i++) {
      if (lower.indexOf(BLANK_URL_KEYWORDS[i]) !== -1) return true;
    }
    return false;
  }

  /**
   * Use a small canvas sample to detect near-solid-color images.
   * Samples a grid of pixels; if colour variance is very low the
   * image is almost certainly a placeholder / blank.
   */
  function isNearSolidColor(img) {
    try {
      var w = img.naturalWidth, h = img.naturalHeight;
      if (!w || !h) return false;
      // Down-sample to a tiny canvas for speed
      var sw = Math.min(w, 32), sh = Math.min(h, 32);
      var c = document.createElement("canvas");
      c.width = sw; c.height = sh;
      var ctx = c.getContext("2d");
      ctx.drawImage(img, 0, 0, sw, sh);
      var data = ctx.getImageData(0, 0, sw, sh).data;
      // Sample every 4th pixel for speed
      var r0 = data[0], g0 = data[1], b0 = data[2];
      var maxDiff = 0;
      for (var i = 0; i < data.length; i += 16) {
        var dr = Math.abs(data[i] - r0);
        var dg = Math.abs(data[i + 1] - g0);
        var db = Math.abs(data[i + 2] - b0);
        var d = Math.max(dr, dg, db);
        if (d > maxDiff) maxDiff = d;
        if (maxDiff > 25) return false; // early exit — enough variance
      }
      return maxDiff <= 25;
    } catch (e) {
      // Canvas tainted by CORS — can't analyse, assume OK
      return false;
    }
  }

  function checkImageQuality(img) {
    var w = img.naturalWidth || 0;
    var h = img.naturalHeight || 0;
    if (w === 0 || h === 0) return;

    // 1. URL-based blank detection
    if (isBlankUrl(img.src)) {
      markNoImage(img, "blank-url");
      return;
    }

    // 2. Tiny image detection
    if (w < 160 || h < 120) {
      markTiny(img);
      return;
    }

    // 3. Near-solid-color detection (placeholder images)
    if (isNearSolidColor(img)) {
      markNoImage(img, "solid-color");
      return;
    }
  }

  function initImgGuards() {
    var imgs = document.querySelectorAll("img.hn-img");
    imgs.forEach(function (img) {
      // Pre-check: immediately hide images whose URL is clearly a placeholder
      // (no need to wait for load/error events)
      if (isBlankUrl(img.getAttribute("src") || "")) {
        markNoImage(img, "blank-url");
        return;
      }

      img.addEventListener("error", function () { markNoImage(img, "error"); }, { once: true });
      img.addEventListener("load", function () { checkImageQuality(img); }, { once: true });

      if (img.complete) {
        if ((img.naturalWidth || 0) === 0) markNoImage(img, "broken");
        else checkImageQuality(img);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initImgGuards);
  } else {
    initImgGuards();
  }
})();

// ===== Tag filter bar =====
(function () {
  function initTagFilter() {
    const list = document.querySelector(".hn-list");
    if (!list) return; // not a story page (e.g. index)

    // Favorites is rendered from localStorage and may change while this page is
    // open. Remove its previous generated controls before recalculating counts.
    var oldBar = list.parentNode.querySelector('.hn-filter-bar[data-hn-generated="true"]');
    var oldStatus = list.parentNode.querySelector('.hn-filter-status[data-hn-generated="true"]');
    if (oldBar) oldBar.remove();
    if (oldStatus) oldStatus.remove();

    const cards = Array.from(list.querySelectorAll(".hn-card[data-tags]"));
    if (!cards.length) return;

    // Collect all unique tags and their counts
    const tagCounts = {};
    cards.forEach(function (card) {
      var raw = card.getAttribute("data-tags") || "";
      if (!raw) return;
      raw.split(",").forEach(function (t) {
        var tag = t.trim();
        if (tag) tagCounts[tag] = (tagCounts[tag] || 0) + 1;
      });
    });

    var tagNames = Object.keys(tagCounts);
    if (!tagNames.length) return;

    // Sort tags by count descending, then alphabetically
    tagNames.sort(function (a, b) {
      if (tagCounts[b] !== tagCounts[a]) return tagCounts[b] - tagCounts[a];
      return a.localeCompare(b);
    });

    // Tag → CSS color class (must match TAG_COLOR_MAP in md_writer.py)
    var TAG_COLORS = {
      "AI": "blue", "Programming": "indigo", "Security": "red",
      "Science": "teal", "Business": "amber", "Finance": "amber",
      "Hardware": "slate", "Open Source": "green", "Design": "pink",
      "Web": "cyan", "DevOps": "indigo", "Data": "violet",
      "Gaming": "purple", "Entertainment": "purple", "Politics": "orange",
      "Health": "emerald", "Education": "sky", "Career": "sky",
      "Privacy": "red", "Legal": "orange", "Culture": "rose",
      "Space": "teal", "Energy": "emerald", "Startups": "amber",
      "Show HN": "green"
    };

    // Build the filter bar
    var bar = document.createElement("div");
    bar.className = "hn-filter-bar";
    bar.setAttribute('data-hn-generated', 'true');

    // "All" button
    var allBtn = document.createElement("button");
    allBtn.className = "hn-filter-btn hn-filter-btn--all is-active";
    allBtn.setAttribute("data-filter", "__all__");
    allBtn.textContent = "All (" + cards.length + ")";
    bar.appendChild(allBtn);

    // Tag buttons
    tagNames.forEach(function (tag) {
      var btn = document.createElement("button");
      var color = TAG_COLORS[tag] || "slate";
      btn.className = "hn-filter-btn hn-tag--" + color;
      btn.setAttribute("data-filter", tag);
      btn.textContent = tag + " (" + tagCounts[tag] + ")";
      bar.appendChild(btn);
    });

    // Status line
    var status = document.createElement("div");
    status.className = "hn-filter-status";
    status.setAttribute('data-hn-generated', 'true');
    status.style.display = "none";

    // Insert bar and status before hn-list
    list.parentNode.insertBefore(bar, list);
    list.parentNode.insertBefore(status, list);

    // State
    var activeTag = null;

    function applyFilter(tag) {
      if (tag === "__all__" || tag === activeTag) {
        // Reset
        activeTag = null;
        cards.forEach(function (c) { c.style.display = ""; });
        status.style.display = "none";
        // Update active state
        bar.querySelectorAll(".hn-filter-btn").forEach(function (b) {
          b.classList.remove("is-active");
        });
        allBtn.classList.add("is-active");

        // Re-number all visible cards
        renumberCards(cards);
        return;
      }

      activeTag = tag;
      var shown = 0;
      cards.forEach(function (c) {
        var tags = (c.getAttribute("data-tags") || "").split(",").map(function (s) { return s.trim(); });
        if (tags.indexOf(tag) !== -1) {
          c.style.display = "";
          shown++;
        } else {
          c.style.display = "none";
        }
      });

      // Update status
      status.textContent = "Showing " + shown + " of " + cards.length + " stories tagged \"" + tag + "\"";
      status.style.display = "block";

      // Update active state
      bar.querySelectorAll(".hn-filter-btn").forEach(function (b) {
        b.classList.remove("is-active");
        if (b.getAttribute("data-filter") === tag) b.classList.add("is-active");
      });

      // Re-number visible cards
      var visibleCards = cards.filter(function (c) { return c.style.display !== "none"; });
      renumberCards(visibleCards);
    }

    function renumberCards(visibleCards) {
      // Update the (N) prefix in hn-title
      visibleCards.forEach(function (card, idx) {
        var titleEl = card.querySelector(".hn-title");
        if (titleEl) {
          // Replace "(N) " at the start of the text content
          var firstText = titleEl.childNodes[0];
          if (firstText && firstText.nodeType === 3) {
            firstText.textContent = firstText.textContent.replace(/^\(\d+\)\s*/, "(" + (idx + 1) + ") ");
          }
        }
      });
    }

    // Click handler (event delegation)
    bar.addEventListener("click", function (e) {
      var btn = e.target.closest(".hn-filter-btn");
      if (!btn) return;
      var filter = btn.getAttribute("data-filter");
      applyFilter(filter);

      // GA4: track tag filter
      if (typeof gtag === 'function' && filter !== '__all__') {
        gtag('event', 'tag_filter', { tag_name: filter });
      }
    });

    // Card-level tags are non-clickable to prevent accidental taps on mobile
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTagFilter);
  } else {
    initTagFilter();
  }
  document.addEventListener('hn:favorites-rendered', initTagFilter);
})();

// ===== Hot / Top / New Sort Toggle (Trending pages only) =====
(function () {
  function initSortToggle() {
    // Only activate on Trending (top stories) pages
    var modeBadge = document.querySelector('.hn-mode-top');
    if (!modeBadge) return;

    var list = document.querySelector('.hn-list');
    if (!list) return;

    var cards = Array.from(list.querySelectorAll('.hn-card'));
    if (!cards.length) return;

    // Read sort keys from data attributes (hot_score computed at pipeline time)
    cards.forEach(function (card) {
      var hnTime = parseInt(card.getAttribute('data-hn-time') || '0', 10);
      var hnScore = parseInt(card.getAttribute('data-hn-score') || '0', 10);
      var hotScore = parseFloat(card.getAttribute('data-hot-score') || '0');
      card._sortData = {
        score: hnScore,
        time: hnTime,
        hot: hotScore
      };
    });

    // Build sort bar
    var sortBar = document.createElement('div');
    sortBar.className = 'hn-sort-bar';

    var label = document.createElement('span');
    label.className = 'hn-sort-label';
    label.textContent = 'Sort by:';
    sortBar.appendChild(label);

    var modes = [
      { key: 'hot', text: '\uD83D\uDD25 Hot', title: 'Sort by hotness (HN time-decay formula)' },
      { key: 'top', text: '\u2B06 Top', title: 'Sort by score (highest first)' },
      { key: 'new', text: '\uD83D\uDD52 New', title: 'Sort by time (newest first)' }
    ];

    var currentSort = 'hot';
    var sortBtns = {};

    modes.forEach(function (m) {
      var btn = document.createElement('button');
      btn.className = 'hn-sort-toggle-btn' + (m.key === 'hot' ? ' is-active' : '');
      btn.setAttribute('data-sort', m.key);
      btn.setAttribute('title', m.title);
      btn.textContent = m.text;
      sortBar.appendChild(btn);
      sortBtns[m.key] = btn;
    });

    // Insert sort bar before the filter bar or the list
    var filterBar = document.querySelector('.hn-filter-bar');
    if (filterBar) {
      filterBar.parentNode.insertBefore(sortBar, filterBar);
    } else {
      list.parentNode.insertBefore(sortBar, list);
    }

    // Hotness badge management
    function updateMetricHighlights(mode) {
      cards.forEach(function (card) {
        // --- Hotness badge ---
        var existing = card.querySelector('.hn-hot-badge');
        var hotVal = card._sortData.hot;
        var displayVal = hotVal >= 10 ? Math.round(hotVal) : hotVal.toFixed(1);
        if (existing) {
          existing.textContent = '\uD83D\uDD25 ' + displayVal;
          existing.style.display = '';
          existing.classList.toggle('hn-hot-badge--dim', mode !== 'hot');
        } else {
          var badge = document.createElement('span');
          badge.className = 'hn-hot-badge' + (mode === 'hot' ? '' : ' hn-hot-badge--dim');
          badge.title = 'Hotness score (HN time-decay formula)';
          badge.textContent = '\uD83D\uDD25 ' + displayVal;
          var tagsRow = card.querySelector('.hn-tags');
          if (tagsRow) {
            tagsRow.insertBefore(badge, tagsRow.firstChild);
          }
        }

        // --- Score highlight (only add highlight in Top mode, otherwise normal) ---
        var scoreEl = card.querySelector('.hn-stat-score');
        if (scoreEl) {
          scoreEl.classList.toggle('hn-stat--highlight', mode === 'top');
        }

        // --- Created time highlight (only add highlight in New mode, otherwise normal) ---
        var timeEl = card.querySelector('.hn-meta2-created');
        if (timeEl) {
          timeEl.classList.toggle('hn-meta2-created--highlight', mode === 'new');
        }
      });
    }

    function renumberVisible() {
      var visible = cards.filter(function (c) { return c.style.display !== 'none'; });
      visible.forEach(function (card, idx) {
        var titleEl = card.querySelector('.hn-title');
        if (titleEl) {
          var firstText = titleEl.childNodes[0];
          if (firstText && firstText.nodeType === 3) {
            firstText.textContent = firstText.textContent.replace(/^\(\d+\)\s*/, '(' + (idx + 1) + ') ');
          }
        }
      });
    }

    function applySort(mode) {
      var sorted = cards.slice();
      if (mode === 'hot') {
        sorted.sort(function (a, b) { return b._sortData.hot - a._sortData.hot; });
      } else if (mode === 'top') {
        sorted.sort(function (a, b) { return b._sortData.score - a._sortData.score; });
      } else if (mode === 'new') {
        sorted.sort(function (a, b) { return b._sortData.time - a._sortData.time; });
      }

      // Re-append cards in new order
      sorted.forEach(function (card) { list.appendChild(card); });

      // Update internal cards array to match new order
      cards = sorted;

      // Update metric highlights based on sort mode
      updateMetricHighlights(mode);

      // Re-number
      renumberVisible();
    }

    // Click handler
    sortBar.addEventListener('click', function (e) {
      var btn = e.target.closest('.hn-sort-toggle-btn');
      if (!btn) return;
      var newSort = btn.getAttribute('data-sort');
      if (newSort === currentSort) return;
      currentSort = newSort;
      // Update active state
      Object.keys(sortBtns).forEach(function (k) {
        sortBtns[k].classList.toggle('is-active', k === newSort);
      });
      applySort(newSort);

      // GA4: track sort change
      if (typeof gtag === 'function') {
        gtag('event', 'sort_change', { sort_mode: newSort });
      }
    });

    // Apply initial Hot sort
    applySort('hot');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSortToggle);
  } else {
    initSortToggle();
  }
})();

// ===== Card Collapse/Expand Toggle (News pages) =====
(function () {
  function initCardCollapse() {
    var list = document.querySelector('.hn-list');
    if (!list) return;

    // Inject collapse button into each card (skip cards with hn-no-collapse)
    var cards = list.querySelectorAll('.hn-card');
    cards.forEach(function (card) {
      if (card.classList.contains('hn-no-collapse')) return;
      if (card.querySelector('.hn-digest-summary-header')) return;
      var body = card.querySelector('.hn-body');
      if (!body) return;
      var btn = document.createElement('button');
      btn.className = 'hn-collapse-btn';
      btn.setAttribute('aria-label', 'Collapse card');
      btn.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14"><polyline class="hn-collapse-chevron" points="4,6 8,10 12,6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      body.insertBefore(btn, body.firstChild);
    });
    var legacyCards = Array.prototype.filter.call(cards, function (card) {
      return !!card.querySelector('.hn-collapse-btn');
    });

    // Event delegation for collapse toggle
    list.addEventListener('click', function (e) {
      var btn = e.target.closest('.hn-collapse-btn');
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      var card = btn.closest('.hn-card');
      if (!card) return;
      var isCollapsed = card.classList.toggle('is-collapsed');
      btn.setAttribute('aria-label', isCollapsed ? 'Expand card' : 'Collapse card');
    });

    // "Collapse All" / "Expand All" button in the stats bar or subtitle area
    var stats = document.querySelector('.hn-stats');
    if (stats && legacyCards.length > 0) {
      var allBtn = document.createElement('button');
      allBtn.className = 'hn-collapse-all-btn';
      allBtn.textContent = 'Collapse All';
      allBtn.addEventListener('click', function () {
        var allCollapsed = legacyCards.every(function (card) {
          return card.classList.contains('is-collapsed');
        });
        legacyCards.forEach(function (card) {
          if (allCollapsed) {
            card.classList.remove('is-collapsed');
          } else {
            card.classList.add('is-collapsed');
          }
          var b = card.querySelector('.hn-collapse-btn');
          if (b) b.setAttribute('aria-label', allCollapsed ? 'Collapse card' : 'Expand card');
        });
        allBtn.textContent = allCollapsed ? 'Collapse All' : 'Expand All';
      });
      stats.appendChild(allBtn);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCardCollapse);
  } else {
    initCardCollapse();
  }
})();

// ===== Top Stories Show More/Less Toggle =====
(function () {
  function initTopStoriesToggle() {
    var btn = document.getElementById('hn-top-stories-toggle');
    if (!btn) return;
    var list = btn.closest('.hn-top-stories-list');
    if (!list) return;
    var expanded = false;
    btn.addEventListener('click', function () {
      expanded = !expanded;
      if (expanded) {
        list.classList.add('is-expanded');
        btn.textContent = 'Show less \u25B2';
      } else {
        list.classList.remove('is-expanded');
        btn.textContent = 'Show more \u25BC';
        // Scroll back to the top stories section
        var section = list.closest('.hn-top-stories-section');
        if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTopStoriesToggle);
  } else {
    initTopStoriesToggle();
  }
})();

// ===== Global Search (Index page only) =====
(function () {
  var PAGE_SIZE = 20;

  function initSearch() {
    var input = document.getElementById("hn-search-input");
    if (!input) return; // not the index page

    var statusEl = document.getElementById("hn-search-status");
    var resultsEl = document.getElementById("hn-search-results");
    var moreBtn = document.getElementById("hn-search-more");
    var gridEl = document.querySelector(".hn-grid");
    var ruleEl = resultsEl ? resultsEl.nextElementSibling : null; // the <hr> after results

    var fuse = null;
    var allResults = [];      // Fuse results (with .item and .score)
    var sortedResults = [];    // sorted view for display
    var displayCount = 0;
    var indexData = null;
    var currentSort = 'date'; // default sort
    var currentQuery = ''; // current search query for highlighting
    var sortEl = document.getElementById('hn-search-sort');

    // Tag color map (same as tag filter)
    var TAG_COLORS = {
      "AI": "blue", "Programming": "indigo", "Security": "red",
      "Science": "teal", "Business": "amber", "Finance": "amber",
      "Hardware": "slate", "Open Source": "green", "Design": "pink",
      "Web": "cyan", "DevOps": "indigo", "Data": "violet",
      "Gaming": "purple", "Entertainment": "purple", "Politics": "orange",
      "Health": "emerald", "Education": "sky", "Career": "sky",
      "Privacy": "red", "Legal": "orange", "Culture": "rose",
      "Space": "teal", "Energy": "emerald", "Startups": "amber",
      "Show HN": "green"
    };

    // Load Fuse.js from CDN
    function loadFuse(cb) {
      if (window.Fuse) { cb(); return; }
      var s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js";
      s.onload = cb;
      s.onerror = function () {
        statusEl.textContent = "Failed to load search library.";
      };
      document.head.appendChild(s);
    }

    // Load search index
    function loadIndex(cb) {
      if (indexData) { cb(indexData); return; }
      var xhr = new XMLHttpRequest();
      xhr.open("GET", "/hackernews/search_index.json", true);
      xhr.onload = function () {
        if (xhr.status === 200) {
          try {
            indexData = JSON.parse(xhr.responseText);
            cb(indexData);
          } catch (e) {
            statusEl.textContent = "Failed to parse search index.";
          }
        } else {
          statusEl.textContent = "Failed to load search index.";
        }
      };
      xhr.onerror = function () {
        statusEl.textContent = "Network error loading search index.";
      };
      xhr.send();
    }

    function initFuse(data) {
      fuse = new Fuse(data, {
        keys: [
          { name: "t", weight: 0.4 },    // title English
          { name: "z", weight: 0.3 },    // title Chinese
          { name: "tags", weight: 0.2 }, // tags
          { name: "by", weight: 0.1 }    // author
        ],
        threshold: 0.35,
        ignoreLocation: true,
        includeScore: true,
        minMatchCharLength: 2
      });
    }

    // Highlight matching keywords in text
    function highlightText(text, query) {
      if (!text || !query) return text || '';
      // Split query into individual words, escape regex special chars
      var words = query.trim().split(/\s+/).filter(function (w) { return w.length >= 2; });
      if (!words.length) return text;
      var escaped = words.map(function (w) {
        return w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      });
      var pattern = new RegExp('(' + escaped.join('|') + ')', 'gi');
      return text.replace(pattern, '<mark class="hn-highlight">$1</mark>');
    }

    function renderResult(item) {
      var typeLabel = item.type === "top" ? "Trending" : "Daily Best";
      var typeClass = item.type === "top" ? "hn-type-top" : "hn-type-best";

      var tagsHtml = "";
      if (item.tags && item.tags.length) {
        tagsHtml = item.tags.map(function (tag) {
          var color = TAG_COLORS[tag] || "slate";
          return "<span class='hn-tag hn-tag--" + color + "'>" + tag + "</span>";
        }).join(" ");
      }

      var metaParts = [];
      if (item.date) metaParts.push(item.date);
      if (item.score) metaParts.push(item.score + " points");
      if (item.by) metaParts.push("by " + highlightText(item.by, currentQuery));
      if (item.comments > 0) {
        metaParts.push("<a href='" + item.hn_url + "' target='_blank' rel='noopener noreferrer'>" + item.comments + " comments</a>");
      }

      var html = "<div class='hn-search-item'>";
      html += "<div class='hn-search-item-header'>";
      html += "<span class='hn-row-type " + typeClass + "'>" + typeLabel + "</span>";
      var anchor = item.id ? '#story-' + item.id : '';
      html += "<a class='hn-search-item-title' href='" + item.page + anchor + "'>" + highlightText(item.t, currentQuery) + "</a>";
      html += "</div>";
      if (item.z) {
        html += "<div class='hn-search-item-zh'>" + highlightText(item.z, currentQuery) + "</div>";
      }
      html += "<div class='hn-search-item-meta'>" + metaParts.join(" · ") + "</div>";
      if (tagsHtml) {
        html += "<div class='hn-search-item-tags'>" + tagsHtml + "</div>";
      }

      html += "</div>";
      return html;
    }

    function applySortAndShow() {
      // Build sortedResults from allResults based on currentSort
      sortedResults = allResults.slice(); // copy
      if (currentSort === 'date') {
        sortedResults.sort(function (a, b) {
          var ai = a.item || a, bi = b.item || b;
          return (bi.date || '').localeCompare(ai.date || '') || (bi.score || 0) - (ai.score || 0);
        });
      } else if (currentSort === 'score') {
        sortedResults.sort(function (a, b) {
          var ai = a.item || a, bi = b.item || b;
          return (bi.score || 0) - (ai.score || 0);
        });
      }
      // 'relevance' keeps the original Fuse order (already sorted by match score)
      showResults();
    }

    function showResults() {
      var end = Math.min(displayCount, sortedResults.length);
      var html = "";
      for (var i = 0; i < end; i++) {
        html += renderResult(sortedResults[i].item || sortedResults[i]);
      }
      resultsEl.innerHTML = html;
      resultsEl.style.display = end > 0 ? "block" : "none";

      // Show/hide "Show more" button
      if (end < sortedResults.length) {
        moreBtn.style.display = "block";
        moreBtn.textContent = "Show more results (" + (sortedResults.length - end) + " remaining)";
      } else {
        moreBtn.style.display = "none";
      }

      // Show/hide sort toggle
      if (sortEl) {
        sortEl.style.display = sortedResults.length > 0 ? "" : "none";
      }

      // Hide the day grid when showing search results
      if (gridEl) {
        gridEl.style.display = sortedResults.length > 0 ? "none" : "";
      }
    }

    function doSearch(query) {
      query = query.trim();
      if (!query || query.length < 2) {
        // Clear search
        allResults = [];
        sortedResults = [];
        displayCount = 0;
        currentQuery = '';
        resultsEl.innerHTML = "";
        resultsEl.style.display = "none";
        moreBtn.style.display = "none";
        statusEl.textContent = "";
        if (sortEl) sortEl.style.display = "none";
        if (gridEl) gridEl.style.display = "";
        return;
      }

      if (!fuse) {
        statusEl.textContent = "Loading...";
        loadFuse(function () {
          loadIndex(function (data) {
            initFuse(data);
            doSearch(query);
          });
        });
        return;
      }

      allResults = fuse.search(query);
      currentQuery = query;
      displayCount = PAGE_SIZE;
      statusEl.textContent = "Found " + allResults.length + " result" + (allResults.length !== 1 ? "s" : "") + " for \"" + query + "\"";
      applySortAndShow();

      // GA4: track search event
      if (typeof gtag === 'function') {
        gtag('event', 'search_query', {
          search_term: query.substring(0, 100),
          results_count: allResults.length
        });
      }
    }

    // Debounce input
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        doSearch(input.value);
      }, 300);
    });

    // Enter key triggers immediate search
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        clearTimeout(timer);
        doSearch(input.value);
      }
    });

    // "Show more" button
    if (moreBtn) {
      moreBtn.addEventListener("click", function () {
        displayCount += PAGE_SIZE;
        showResults();
      });
    }

    // Sort toggle buttons
    if (sortEl) {
      var sortBtns = sortEl.querySelectorAll('.hn-sort-btn');
      sortBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
          var newSort = btn.getAttribute('data-sort');
          if (newSort === currentSort) return;
          currentSort = newSort;
          // Update active class
          sortBtns.forEach(function (b) { b.classList.remove('hn-sort-active'); });
          btn.classList.add('hn-sort-active');
          // Re-sort and re-display from top
          displayCount = PAGE_SIZE;
          applySortAndShow();
        });
      });
    }

    // Preload index on focus (lazy load)
    var preloaded = false;
    input.addEventListener("focus", function () {
      if (preloaded) return;
      preloaded = true;
      loadFuse(function () {
        loadIndex(function (data) {
          initFuse(data);
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSearch);
  } else {
    initSearch();
  }
})();


// ===== Tag Bubble Chart (Trends page) =====
(function () {
  function initBubbleChart() {
    var container = document.getElementById('hn-tag-cloud');
    if (!container) return;

    var chartEl = document.getElementById('hn-bubble-chart');
    var tooltip = document.getElementById('hn-tag-cloud-tooltip');
    var body = document.getElementById('hn-tag-cloud-body');

    // Tag color map (hex)
    var TAG_COLORS = {
      "AI": "#3b82f6", "Programming": "#6366f1", "Security": "#ef4444",
      "Science": "#14b8a6", "Business": "#f59e0b", "Finance": "#d97706",
      "Hardware": "#64748b", "Open Source": "#22c55e", "Design": "#ec4899",
      "Web": "#06b6d4", "DevOps": "#818cf8", "Data": "#8b5cf6",
      "Gaming": "#a855f7", "Entertainment": "#c084fc", "Politics": "#f97316",
      "Health": "#10b981", "Education": "#0ea5e9", "Career": "#0ea5e9",
      "Privacy": "#ef4444", "Legal": "#f97316", "Culture": "#f43f5e",
      "Space": "#14b8a6", "Energy": "#10b981", "Startups": "#eab308",
      "Show HN": "#22c55e"
    };

    var chartRendered = false;

    function loadData(cb) {
      var xhr = new XMLHttpRequest();
      xhr.open('GET', '/hackernews/tag_cloud.json', true);
      xhr.onload = function () {
        if (xhr.status === 200) {
          try { cb(JSON.parse(xhr.responseText)); } catch (e) { /* ignore */ }
        }
      };
      xhr.send();
    }

    function renderChart() {
      loadData(function (data) {
        if (!data || !data.tags || !data.tags.length) return;

        var tags = data.tags;
        var totalStories = data.total_stories || 1;
        var maxCount = tags[0].count;
        var minCount = tags[tags.length - 1].count;

        // Container dimensions
        var rect = body.getBoundingClientRect();
        var W = Math.min(rect.width - 16, 880);
        var H = 300;
        chartEl.style.width = W + 'px';
        chartEl.style.height = H + 'px';
        chartEl.innerHTML = '';

        // Bubble radius scaling
        var MIN_R = 22;
        var MAX_R = 62;
        function radius(count) {
          if (maxCount === minCount) return (MIN_R + MAX_R) / 2;
          var t = (count - minCount) / (maxCount - minCount);
          return MIN_R + Math.sqrt(t) * (MAX_R - MIN_R);
        }

        // Build bubble data
        var bubbles = tags.map(function (t) {
          var r = radius(t.count);
          var color = TAG_COLORS[t.tag] || '#64748b';
          return {
            tag: t.tag,
            count: t.count,
            r: r,
            color: color,
            x: W / 2 + (Math.random() - 0.5) * W * 0.3,
            y: H / 2 + (Math.random() - 0.5) * H * 0.3,
            vx: 0,
            vy: 0
          };
        });

        // Simple force simulation: center gravity + collision
        var cx = W / 2;
        var cy = H / 2;
        var GRAVITY = 0.012;
        var DAMPING = 0.88;
        var COLLISION_STRENGTH = 0.6;

        function simulate(steps) {
          for (var s = 0; s < steps; s++) {
            // Center gravity
            for (var i = 0; i < bubbles.length; i++) {
              var b = bubbles[i];
              b.vx += (cx - b.x) * GRAVITY;
              b.vy += (cy - b.y) * GRAVITY;
            }

            // Collision resolution
            for (var i = 0; i < bubbles.length; i++) {
              for (var j = i + 1; j < bubbles.length; j++) {
                var a = bubbles[i];
                var b = bubbles[j];
                var dx = b.x - a.x;
                var dy = b.y - a.y;
                var dist = Math.sqrt(dx * dx + dy * dy) || 1;
                var minDist = a.r + b.r + 3;
                if (dist < minDist) {
                  var overlap = (minDist - dist) / dist * COLLISION_STRENGTH;
                  var mx = dx * overlap;
                  var my = dy * overlap;
                  a.vx -= mx;
                  a.vy -= my;
                  b.vx += mx;
                  b.vy += my;
                }
              }
            }

            // Update positions with damping
            for (var i = 0; i < bubbles.length; i++) {
              var b = bubbles[i];
              b.vx *= DAMPING;
              b.vy *= DAMPING;
              b.x += b.vx;
              b.y += b.vy;
              // Boundary constraints
              if (b.x - b.r < 0) { b.x = b.r; b.vx *= -0.5; }
              if (b.x + b.r > W) { b.x = W - b.r; b.vx *= -0.5; }
              if (b.y - b.r < 0) { b.y = b.r; b.vy *= -0.5; }
              if (b.y + b.r > H) { b.y = H - b.r; b.vy *= -0.5; }
            }
          }
        }

        // Run simulation
        simulate(200);

        // Create SVG
        var svgNS = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(svgNS, 'svg');
        svg.setAttribute('width', W);
        svg.setAttribute('height', H);
        svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
        svg.style.display = 'block';
        svg.style.margin = '0 auto';

        // Defs for filters
        var defs = document.createElementNS(svgNS, 'defs');
        var filter = document.createElementNS(svgNS, 'filter');
        filter.setAttribute('id', 'bubble-shadow');
        filter.setAttribute('x', '-20%');
        filter.setAttribute('y', '-20%');
        filter.setAttribute('width', '140%');
        filter.setAttribute('height', '140%');
        var feGauss = document.createElementNS(svgNS, 'feGaussianBlur');
        feGauss.setAttribute('in', 'SourceAlpha');
        feGauss.setAttribute('stdDeviation', '3');
        feGauss.setAttribute('result', 'blur');
        var feOffset = document.createElementNS(svgNS, 'feOffset');
        feOffset.setAttribute('in', 'blur');
        feOffset.setAttribute('dx', '0');
        feOffset.setAttribute('dy', '2');
        feOffset.setAttribute('result', 'shadow');
        var feFlood = document.createElementNS(svgNS, 'feFlood');
        feFlood.setAttribute('flood-color', 'rgba(0,0,0,0.15)');
        feFlood.setAttribute('result', 'color');
        var feComp = document.createElementNS(svgNS, 'feComposite');
        feComp.setAttribute('in', 'color');
        feComp.setAttribute('in2', 'shadow');
        feComp.setAttribute('operator', 'in');
        feComp.setAttribute('result', 'colorShadow');
        var feMerge = document.createElementNS(svgNS, 'feMerge');
        var feMerge1 = document.createElementNS(svgNS, 'feMergeNode');
        feMerge1.setAttribute('in', 'colorShadow');
        var feMerge2 = document.createElementNS(svgNS, 'feMergeNode');
        feMerge2.setAttribute('in', 'SourceGraphic');
        feMerge.appendChild(feMerge1);
        feMerge.appendChild(feMerge2);
        filter.appendChild(feGauss);
        filter.appendChild(feOffset);
        filter.appendChild(feFlood);
        filter.appendChild(feComp);
        filter.appendChild(feMerge);
        defs.appendChild(filter);
        svg.appendChild(defs);

        // Render bubbles
        var bubbleEls = [];
        bubbles.forEach(function (b, idx) {
          var g = document.createElementNS(svgNS, 'g');
          g.setAttribute('class', 'hn-bubble');
          g.setAttribute('data-idx', idx);
          g.style.cursor = 'pointer';

          // Circle
          var circle = document.createElementNS(svgNS, 'circle');
          circle.setAttribute('cx', b.x);
          circle.setAttribute('cy', b.y);
          circle.setAttribute('r', b.r);
          circle.setAttribute('fill', b.color);
          circle.setAttribute('fill-opacity', '0.18');
          circle.setAttribute('stroke', b.color);
          circle.setAttribute('stroke-width', '2');
          circle.setAttribute('stroke-opacity', '0.6');
          circle.setAttribute('filter', 'url(#bubble-shadow)');
          g.appendChild(circle);

          // Tag label
          var text = document.createElementNS(svgNS, 'text');
          text.setAttribute('x', b.x);
          text.setAttribute('y', b.y - (b.r > 30 ? 5 : 0));
          text.setAttribute('text-anchor', 'middle');
          text.setAttribute('dominant-baseline', 'central');
          text.setAttribute('fill', b.color);
          text.setAttribute('font-family', 'Inter, -apple-system, sans-serif');
          text.setAttribute('font-weight', '700');
          // Font size based on bubble radius
          var fs = Math.max(10, Math.min(b.r * 0.42, 20));
          text.setAttribute('font-size', fs + 'px');
          text.textContent = b.tag;
          g.appendChild(text);

          // Count label (below tag name, only for larger bubbles)
          if (b.r > 30) {
            var countText = document.createElementNS(svgNS, 'text');
            countText.setAttribute('x', b.x);
            countText.setAttribute('y', b.y + fs * 0.7 + 2);
            countText.setAttribute('text-anchor', 'middle');
            countText.setAttribute('dominant-baseline', 'central');
            countText.setAttribute('fill', b.color);
            countText.setAttribute('font-family', 'Inter, -apple-system, sans-serif');
            countText.setAttribute('font-weight', '500');
            countText.setAttribute('font-size', (fs * 0.65) + 'px');
            countText.setAttribute('opacity', '0.7');
            countText.textContent = b.count;
            g.appendChild(countText);
          }

          svg.appendChild(g);
          bubbleEls.push({ g: g, circle: circle, data: b });
        });

        chartEl.appendChild(svg);
        chartRendered = true;

        // Hover interaction
        var currentHover = -1;

        svg.addEventListener('mousemove', function (e) {
          var svgRect = svg.getBoundingClientRect();
          var mx = (e.clientX - svgRect.left) * (W / svgRect.width);
          var my = (e.clientY - svgRect.top) * (H / svgRect.height);

          var hitIdx = -1;
          for (var i = bubbles.length - 1; i >= 0; i--) {
            var b = bubbles[i];
            var dx = mx - b.x;
            var dy = my - b.y;
            if (dx * dx + dy * dy <= b.r * b.r) {
              hitIdx = i;
              break;
            }
          }

          if (hitIdx !== currentHover) {
            // Reset previous
            if (currentHover >= 0) {
              var prev = bubbleEls[currentHover];
              prev.circle.setAttribute('fill-opacity', '0.18');
              prev.circle.setAttribute('stroke-width', '2');
              prev.circle.setAttribute('stroke-opacity', '0.6');
              prev.g.style.transform = '';
            }
            currentHover = hitIdx;

            if (hitIdx >= 0) {
              var el = bubbleEls[hitIdx];
              el.circle.setAttribute('fill-opacity', '0.30');
              el.circle.setAttribute('stroke-width', '3');
              el.circle.setAttribute('stroke-opacity', '1');
              svg.style.cursor = 'pointer';

              var b = el.data;
              var pct = (b.count / totalStories * 100).toFixed(1);
              tooltip.innerHTML = '<b>' + b.tag + '</b>: ' + b.count + ' stories (' + pct + '%)';
              tooltip.style.display = 'block';

              var cr = chartEl.getBoundingClientRect();
              tooltip.style.left = (e.clientX - cr.left + 14) + 'px';
              tooltip.style.top = (e.clientY - cr.top - 32) + 'px';
            } else {
              svg.style.cursor = 'default';
              tooltip.style.display = 'none';
            }
          } else if (hitIdx >= 0) {
            var cr = chartEl.getBoundingClientRect();
            tooltip.style.left = (e.clientX - cr.left + 14) + 'px';
            tooltip.style.top = (e.clientY - cr.top - 32) + 'px';
          }
        });

        svg.addEventListener('mouseleave', function () {
          if (currentHover >= 0) {
            var prev = bubbleEls[currentHover];
            prev.circle.setAttribute('fill-opacity', '0.18');
            prev.circle.setAttribute('stroke-width', '2');
            prev.circle.setAttribute('stroke-opacity', '0.6');
            prev.g.style.transform = '';
          }
          currentHover = -1;
          tooltip.style.display = 'none';
          svg.style.cursor = 'default';
        });

        // Click => trigger search
        svg.addEventListener('click', function (e) {
          var svgRect = svg.getBoundingClientRect();
          var mx = (e.clientX - svgRect.left) * (W / svgRect.width);
          var my = (e.clientY - svgRect.top) * (H / svgRect.height);

          for (var i = bubbles.length - 1; i >= 0; i--) {
            var b = bubbles[i];
            var dx = mx - b.x;
            var dy = my - b.y;
            if (dx * dx + dy * dy <= b.r * b.r) {
              var searchInput = document.getElementById('hn-search-input');
              if (searchInput) {
                searchInput.value = b.tag;
                searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                searchInput.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
              break;
            }
          }
        });

        // Responsive: redraw on resize
        var resizeTimer;
        window.addEventListener('resize', function () {
          clearTimeout(resizeTimer);
          resizeTimer = setTimeout(function () {
            chartRendered = false;
            renderChart();
          }, 300);
        });
      });
    }

    // Render immediately
    renderChart();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBubbleChart);
  } else {
    initBubbleChart();
  }
})();


// ===== Stream Graph (Trends page) =====
(function () {
  function initStreamGraph() {
    var container = document.getElementById('hn-stream-wrap');
    if (!container) return;

    var chartEl = document.getElementById('hn-stream-chart');
    var tooltip = document.getElementById('hn-stream-tooltip');
    var legendEl = document.getElementById('hn-stream-legend');
    var subtitleEl = document.getElementById('hn-stream-subtitle');
    var rangeBar = document.getElementById('hn-stream-range-bar');

    var TAG_COLORS = {
      'AI': '#e74c3c', 'Programming': '#3498db', 'Security': '#e67e22',
      'Business': '#9b59b6', 'Privacy': '#1abc9c', 'Open Source': '#27ae60',
      'Hardware': '#f39c12', 'DevOps': '#2980b9', 'Politics': '#c0392b',
      'Legal': '#8e44ad', 'Show HN': '#16a085', 'Web': '#d35400',
      'Design': '#e91e63', 'Science': '#00bcd4', 'Culture': '#ff9800',
      'Data': '#607d8b', 'Finance': '#4caf50', 'Health': '#f44336',
      'Education': '#3f51b5', 'Gaming': '#ff5722', 'Startups': '#795548',
      'Entertainment': '#9c27b0', 'Career': '#009688', 'Other': '#95a5a6'
    };
    function tagColor(tag) { return TAG_COLORS[tag] || '#95a5a6'; }

    var RANGE_LABELS = { 7: 'past week', 14: 'past 2 weeks', 30: 'past month' };

    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/hackernews/tag_trend.json', true);
    xhr.onload = function () {
      if (xhr.status !== 200) return;
      var data;
      try { data = JSON.parse(xhr.responseText); } catch (e) { return; }
      if (!data || !data.tags || !data.series || data.series.length < 2) return;

      var allTags = data.tags.filter(function (t) { return t !== 'Other'; });
      var allSeries = data.series;
      var legendBuilt = false;

      /** Filter series to the last N days and render the chart */
      function renderChart(days) {
        // Filter series to last N days
        var series, tags;
        if (allSeries.length <= days) {
          series = allSeries;
        } else {
          series = allSeries.slice(allSeries.length - days);
        }
        tags = allTags;

        if (series.length < 2) return;

        var dates = series.map(function (s) { return s.date; });

        // Update subtitle
        if (subtitleEl) {
          var actual = series.length;
          var label = RANGE_LABELS[days] || ('past ' + days + ' days');
          var suffix = actual < days ? ' (' + actual + ' days available)' : '';
          subtitleEl.textContent = 'Daily tag distribution over the ' + label + suffix;
        }

        // Compute stacked values
        var stacked = [];
        for (var t = 0; t < tags.length; t++) stacked.push([]);
        for (var d = 0; d < series.length; d++) {
          var y0 = 0;
          for (var t = 0; t < tags.length; t++) {
            var val = series[d][tags[t]] || 0;
            stacked[t].push({ y0: y0, y1: y0 + val, val: val });
            y0 += val;
          }
        }

        var maxY = 0;
        for (var d = 0; d < series.length; d++) {
          var last = stacked[tags.length - 1][d];
          if (last.y1 > maxY) maxY = last.y1;
        }
        if (maxY === 0) maxY = 1;

        // SVG dimensions
        var W = 800, H = 360;
        var padL = 45, padR = 20, padT = 20, padB = 40;
        var plotW = W - padL - padR;
        var plotH = H - padT - padB;

        function xPos(i) { return padL + (i / Math.max(dates.length - 1, 1)) * plotW; }
        function yPos(v) { return padT + plotH - (v / maxY) * plotH; }

        // Monotone cubic interpolation
        function monotonePath(xs, ys) {
          var n = xs.length;
          if (n < 2) return 'M' + xs[0] + ',' + ys[0];
          if (n === 2) return 'M' + xs[0] + ',' + ys[0] + 'L' + xs[1] + ',' + ys[1];
          var ms = [];
          for (var i = 0; i < n - 1; i++) ms.push((ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]));
          var ts = [ms[0]];
          for (var i = 1; i < n - 1; i++) {
            if (ms[i - 1] * ms[i] <= 0) ts.push(0);
            else ts.push((ms[i - 1] + ms[i]) / 2);
          }
          ts.push(ms[n - 2]);
          var d = 'M' + xs[0].toFixed(2) + ',' + ys[0].toFixed(2);
          for (var i = 0; i < n - 1; i++) {
            var dx = (xs[i + 1] - xs[i]) / 3;
            d += 'C' + (xs[i] + dx).toFixed(2) + ',' + (ys[i] + ts[i] * dx).toFixed(2)
              + ',' + (xs[i + 1] - dx).toFixed(2) + ',' + (ys[i + 1] - ts[i + 1] * dx).toFixed(2)
              + ',' + xs[i + 1].toFixed(2) + ',' + ys[i + 1].toFixed(2);
          }
          return d;
        }

        function buildAreaPath(tagIdx) {
          var pts = stacked[tagIdx];
          var n = pts.length;
          if (n < 2) return '';
          var topX = [], topY = [];
          for (var i = 0; i < n; i++) { topX.push(xPos(i)); topY.push(yPos(pts[i].y1)); }
          var botX = [], botY = [];
          for (var i = n - 1; i >= 0; i--) { botX.push(xPos(i)); botY.push(yPos(pts[i].y0)); }
          var topPath = monotonePath(topX, topY);
          var botPath = monotonePath(botX, botY);
          return topPath + 'L' + botX[0].toFixed(2) + ',' + botY[0].toFixed(2)
            + botPath.substring(botPath.indexOf('L') !== -1 ? botPath.indexOf('L') : botPath.indexOf('C'))
            + 'Z';
        }

        // Clear previous chart
        chartEl.innerHTML = '';

        // Create SVG
        var svgNS = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(svgNS, 'svg');
        svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
        svg.setAttribute('width', W);
        svg.setAttribute('height', H);
        svg.style.display = 'block';
        svg.style.margin = '0 auto';

        // Y-axis grid lines
        var gridSteps = 5;
        var gridStep = Math.ceil(maxY / gridSteps);
        for (var g = 0; g <= maxY; g += gridStep) {
          var gy = yPos(g);
          var line = document.createElementNS(svgNS, 'line');
          line.setAttribute('x1', padL); line.setAttribute('x2', W - padR);
          line.setAttribute('y1', gy); line.setAttribute('y2', gy);
          line.setAttribute('stroke', '#ddd'); line.setAttribute('stroke-width', '0.5');
          svg.appendChild(line);
          var label = document.createElementNS(svgNS, 'text');
          label.setAttribute('x', padL - 8); label.setAttribute('y', gy + 4);
          label.setAttribute('text-anchor', 'end'); label.setAttribute('font-size', '11');
          label.setAttribute('fill', '#999'); label.setAttribute('font-family', 'system-ui, sans-serif');
          label.textContent = g;
          svg.appendChild(label);
        }

        // Draw area paths
        var pathEls = [];
        for (var t = tags.length - 1; t >= 0; t--) {
          var path = document.createElementNS(svgNS, 'path');
          path.setAttribute('d', buildAreaPath(t));
          path.setAttribute('fill', tagColor(tags[t]));
          path.setAttribute('fill-opacity', '0.7');
          path.setAttribute('stroke', tagColor(tags[t]));
          path.setAttribute('stroke-width', '0.5');
          path.setAttribute('stroke-opacity', '0.3');
          path.setAttribute('class', 'hn-stream-path');
          path.setAttribute('data-tag', tags[t]);
          svg.appendChild(path);
          pathEls[t] = path;
        }

        // X-axis date labels — show a reasonable number based on date count
        var maxLabels = days <= 7 ? dates.length : (days <= 14 ? 7 : 10);
        var labelStep = dates.length <= maxLabels ? 1 : Math.ceil(dates.length / maxLabels);
        for (var d = 0; d < dates.length; d++) {
          if (d % labelStep !== 0 && d !== dates.length - 1) continue;
          var lx = xPos(d);
          var label = document.createElementNS(svgNS, 'text');
          label.setAttribute('x', lx);
          label.setAttribute('y', H - padB + 20);
          label.setAttribute('text-anchor', 'middle');
          label.setAttribute('font-size', '11');
          label.setAttribute('fill', '#999');
          label.setAttribute('font-family', 'system-ui, sans-serif');
          var parts = dates[d].split('-');
          label.textContent = parts[1] + '-' + parts[2];
          svg.appendChild(label);
        }

        chartEl.appendChild(svg);

        // Hover interaction
        var currentHighlight = -1;
        svg.addEventListener('mousemove', function (e) {
          var rect = svg.getBoundingClientRect();
          var scaleX = W / rect.width;
          var scaleY = H / rect.height;
          var mx = (e.clientX - rect.left) * scaleX;
          var my = (e.clientY - rect.top) * scaleY;
          var dateIdx = -1, minDist = Infinity;
          for (var i = 0; i < dates.length; i++) {
            var dist = Math.abs(mx - xPos(i));
            if (dist < minDist) { minDist = dist; dateIdx = i; }
          }
          if (dateIdx < 0 || mx < padL - 10 || mx > W - padR + 10) {
            tooltip.style.display = 'none'; resetHL(); return;
          }
          var hitTag = -1;
          for (var t = 0; t < tags.length; t++) {
            var yy0 = yPos(stacked[t][dateIdx].y0);
            var yy1 = yPos(stacked[t][dateIdx].y1);
            if (my >= yy1 && my <= yy0) { hitTag = t; break; }
          }
          if (hitTag >= 0) {
            if (currentHighlight !== hitTag) {
              resetHL();
              for (var t = 0; t < tags.length; t++) {
                pathEls[t].setAttribute('fill-opacity', t !== hitTag ? '0.2' : '0.9');
              }
              currentHighlight = hitTag;
            }
            tooltip.innerHTML = '<b>' + tags[hitTag] + '</b><br>' + dates[dateIdx] + ': ' + stacked[hitTag][dateIdx].val + ' stories';
            tooltip.style.display = 'block';
            var tx = e.clientX - container.getBoundingClientRect().left + 12;
            var ty = e.clientY - container.getBoundingClientRect().top - 10;
            if (tx + 150 > container.offsetWidth) tx -= 170;
            tooltip.style.left = tx + 'px'; tooltip.style.top = ty + 'px';
          } else {
            tooltip.style.display = 'none'; resetHL();
          }
        });
        svg.addEventListener('mouseleave', function () { tooltip.style.display = 'none'; resetHL(); });
        function resetHL() {
          if (currentHighlight >= 0) {
            for (var t = 0; t < tags.length; t++) pathEls[t].setAttribute('fill-opacity', '0.7');
            currentHighlight = -1;
          }
        }

        // Build legend only once
        if (!legendBuilt) {
          legendEl.innerHTML = '';
          for (var t = 0; t < tags.length; t++) {
            var item = document.createElement('span');
            item.className = 'hn-stream-legend-item';
            var swatch = document.createElement('span');
            swatch.className = 'hn-stream-legend-swatch';
            swatch.style.background = tagColor(tags[t]);
            item.appendChild(swatch);
            item.appendChild(document.createTextNode(tags[t]));
            legendEl.appendChild(item);
          }
          legendBuilt = true;
        }
      }

      // Initial render with 1-week (7 days)
      renderChart(7);

      // Range button click handler
      if (rangeBar) {
        rangeBar.addEventListener('click', function (e) {
          var btn = e.target;
          if (!btn.classList.contains('hn-stream-range-btn')) return;
          var days = parseInt(btn.getAttribute('data-range'), 10);
          if (!days) return;
          // Update active state
          var btns = rangeBar.querySelectorAll('.hn-stream-range-btn');
          for (var i = 0; i < btns.length; i++) btns[i].classList.remove('hn-stream-range-active');
          btn.classList.add('hn-stream-range-active');
          // Re-render chart
          renderChart(days);
        });
      }
    };
    xhr.send();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStreamGraph);
  } else {
    initStreamGraph();
  }
})();


// ===== Language Toggle (News pages) =====
(function () {
  function initLangToggle() {
    // Only run on pages that have .hn-list (news card pages)
    var list = document.querySelector('.hn-list');
    if (!list) return;

    // Build the segmented control
    var wrap = document.createElement('div');
    wrap.className = 'hn-lang-toggle';

    var modes = [
      { key: 'en', label: 'EN' },
      { key: 'bi', label: '\u53cc' },  // 双
      { key: 'zh', label: '\u4e2d' }   // 中
    ];

    var slider = document.createElement('div');
    slider.className = 'hn-lang-slider';
    wrap.appendChild(slider);

    var btns = [];
    modes.forEach(function (m, i) {
      var btn = document.createElement('button');
      btn.className = 'hn-lang-btn';
      btn.setAttribute('data-lang', m.key);
      btn.textContent = m.label;
      btn.title = m.key === 'en' ? 'English only' : m.key === 'zh' ? '\u4e2d\u6587 only' : 'Bilingual';
      wrap.appendChild(btn);
      btns.push(btn);
    });

    // Determine where to place the language toggle:
    // - Trending pages (have sort bar): append to sort bar (right side)
    // - Best/other pages (no sort bar): create a standalone row
    var sortBar = document.querySelector('.hn-sort-bar');
    if (sortBar) {
      // Trending page: append to sort bar, will be pushed right via CSS flex
      wrap.classList.add('hn-lang-toggle--in-sort');
      sortBar.appendChild(wrap);
    } else {
      // Best/other pages: create a standalone toolbar row
      var toolbar = document.createElement('div');
      toolbar.className = 'hn-lang-toolbar';
      toolbar.appendChild(wrap);
      // Insert before the filter bar or the list
      var filterBar = document.querySelector('.hn-filter-bar');
      if (filterBar) {
        filterBar.parentNode.insertBefore(toolbar, filterBar);
      } else if (list) {
        list.parentNode.insertBefore(toolbar, list);
      }
    }

    // Page-wide card control lives beside the language selector because both
    // controls change how the entire news list is displayed.
    var toggleAllBtn = document.createElement('button');
    toggleAllBtn.type = 'button';
    toggleAllBtn.className = 'hn-toggle-all-btn';
    if (sortBar) sortBar.appendChild(toggleAllBtn);
    else toolbar.appendChild(toggleAllBtn);

    function collapsibleCards() {
      return Array.prototype.map.call(
        list.querySelectorAll('.hn-card .hn-digest-summary-header'),
        function (header) {
          return {
            header: header,
            details: header.closest('.hn-card').querySelector('.hn-digest-details')
          };
        }
      ).filter(function (item) { return !!item.details; });
    }

    function updateToggleAllButton() {
      var cards = collapsibleCards();
      if (!cards.length) {
        toggleAllBtn.hidden = true;
        return;
      }
      toggleAllBtn.hidden = false;
      var anyExpanded = cards.some(function (item) {
        return !item.details.hasAttribute('hidden');
      });
      toggleAllBtn.textContent = anyExpanded ? 'Collapse All' : 'Expand All';
      toggleAllBtn.setAttribute('aria-label', anyExpanded ? 'Collapse all story cards' : 'Expand all story cards');
    }

    toggleAllBtn.addEventListener('click', function () {
      var cards = collapsibleCards();
      var shouldCollapse = cards.some(function (item) {
        return !item.details.hasAttribute('hidden');
      });
      cards.forEach(function (item) {
        if (shouldCollapse) item.details.setAttribute('hidden', '');
        else item.details.removeAttribute('hidden');
        item.header.setAttribute('aria-expanded', shouldCollapse ? 'false' : 'true');
        item.header.setAttribute('aria-label', shouldCollapse ? 'Show summary and image' : 'Hide summary and image');
      });
      updateToggleAllButton();
    });

    // Keep the label correct after individual card toggles or Favorites rerenders.
    new MutationObserver(updateToggleAllButton).observe(list, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['hidden']
    });
    updateToggleAllButton();

    // State
    var STORAGE_KEY = 'hn-lang-mode';
    var currentMode = localStorage.getItem(STORAGE_KEY) || 'bi';

    function applyMode(mode) {
      currentMode = mode;
      localStorage.setItem(STORAGE_KEY, mode);

      // Update button active state
      btns.forEach(function (btn, i) {
        if (btn.getAttribute('data-lang') === mode) {
          btn.classList.add('hn-lang-active');
          // Move slider
          slider.style.transform = 'translateX(' + (i * 100) + '%)';
        } else {
          btn.classList.remove('hn-lang-active');
        }
      });

      // Apply visibility via class on the list container
      list.classList.remove('hn-lang-en', 'hn-lang-zh', 'hn-lang-bi');
      list.classList.add('hn-lang-' + mode);
    }

    // Click handlers
    btns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var lang = btn.getAttribute('data-lang');
        applyMode(lang);

        // GA4: track language switch
        if (typeof gtag === 'function') {
          gtag('event', 'language_switch', { language: lang });
        }
      });
    });

    // Initialize
    applyMode(currentMode);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLangToggle);
  } else {
    initLangToggle();
  }
})();

// ===== Share Button (copy anchor link to clipboard) =====
(function () {
  // SVG share icon (box with upward arrow, iOS-style)
  var SHARE_SVG = '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    + '<path d="M4 8V13a1 1 0 001 1h6a1 1 0 001-1V8"/>'
    + '<polyline points="5,4 8,1 11,4"/>'
    + '<line x1="8" y1="1" x2="8" y2="10"/>'
    + '</svg>';

  function injectShareButtons(root) {
    var cards = (root || document).querySelectorAll('.hn-card[id]');
    // Keep share and favorite controls at the right edge of the stats/tags row.
    cards.forEach(function (card) {
      if (card.querySelector('.hn-share-btn')) return;
      var tags = card.querySelector('.hn-digest-summary-header .hn-tags');
      if (!tags) return;
      var actions = card.querySelector('.hn-card-actions');
      if (!actions) {
        actions = document.createElement('div');
        actions.className = 'hn-card-actions';
        tags.appendChild(actions);
      }

      var btn = document.createElement('button');
      btn.className = 'hn-share-btn';
      btn.setAttribute('type', 'button');
      btn.setAttribute('aria-label', 'Copy link to this story');
      btn.setAttribute('title', 'Copy link');
      btn.innerHTML = SHARE_SVG;
      actions.appendChild(btn);
    });
  }

  function initShareButtons() {
    var list = document.querySelector('.hn-list');
    if (!list) return;

    injectShareButtons(list);

    // Toast element (reusable)
    var toast = document.createElement('div');
    toast.className = 'hn-share-toast';
    toast.textContent = 'Link copied!';
    document.body.appendChild(toast);

    var toastTimer = null;

    function showToast(x, y) {
      clearTimeout(toastTimer);
      // Position near the button
      toast.style.left = x + 'px';
      toast.style.top = (y - 36) + 'px';
      toast.classList.add('is-visible');
      toastTimer = setTimeout(function () {
        toast.classList.remove('is-visible');
      }, 1600);
    }

    function copyToClipboard(text, btn) {
      var rect = btn.getBoundingClientRect();
      var cx = rect.left + rect.width / 2;
      var cy = rect.top + window.scrollY;

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          showToast(cx, cy);
        }).catch(function () {
          fallbackCopy(text, cx, cy);
        });
      } else {
        fallbackCopy(text, cx, cy);
      }
    }

    function fallbackCopy(text, cx, cy) {
      // Fallback for older browsers / mobile
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.top = '-9999px';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try {
        document.execCommand('copy');
        showToast(cx, cy);
      } catch (e) {
        // Silent fail
      }
      document.body.removeChild(ta);
    }

    // Event delegation
    list.addEventListener('click', function (e) {
      var btn = e.target.closest('.hn-share-btn');
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();

      var card = btn.closest('.hn-card[id]');
      if (!card) return;

      // Build the share URL pointing to the OG redirect page
      var storyId = card.getAttribute('id');
      // storyId is like 'story-47091419', extract the numeric part
      var numericId = storyId.replace('story-', '');
      var url = window.location.origin + '/hackernews/share/' + numericId + '.html';
      copyToClipboard(url, btn);

      // GA4: track share event
      if (typeof gtag === 'function') {
        var titleEl = card.querySelector('.hn-title');
        var titleText = titleEl ? titleEl.textContent.replace(/^\(\d+\)\s*/, '').substring(0, 80) : '';
        gtag('event', 'share_story', {
          story_id: numericId,
          story_title: titleText,
          page_type: document.querySelector('.hn-mode-top') ? 'trending' : document.querySelector('.hn-mode-best') ? 'daily_best' : document.querySelector('.hn-mode-weekly') ? 'weekly' : 'other'
        });
      }
    });

    document.addEventListener('hn:favorites-rendered', function (e) {
      injectShareButtons(e.detail && e.detail.root ? e.detail.root : document);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initShareButtons);
  } else {
    initShareButtons();
  }
})();

// ===== GA4: Track external link clicks (🔗 icon) =====
(function () {
  function initExternalLinkTracking() {
    // Track clicks on external article links (🔗 icons and hn-top-ext-link)
    document.addEventListener('click', function (e) {
      var link = e.target.closest('a[target="_blank"]');
      if (!link) return;

      // Only track links within hn-wrap (our site content)
      if (!link.closest('.hn-wrap')) return;

      // Skip HN discussion links (news.ycombinator.com)
      var href = link.getAttribute('href') || '';
      if (href.indexOf('news.ycombinator.com') !== -1) return;

      // GA4: track external link click
      if (typeof gtag === 'function') {
        var card = link.closest('.hn-card[id]');
        var storyId = card ? card.getAttribute('id').replace('story-', '') : '';
        gtag('event', 'click_external_link', {
          story_id: storyId,
          link_url: href.substring(0, 200)
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initExternalLinkTracking);
  } else {
    initExternalLinkTracking();
  }
})();

