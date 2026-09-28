/* Elite Academy website behaviour — ported from the design system's enhance() and extended.
   Every page works without this file; it adds filters, the day picker, the photo viewer,
   SAQR chat and small form helpers. No inline scripts (the Content-Security-Policy forbids them). */
(function () {
  "use strict";
  var doc = document, root = doc.documentElement;
  root.classList.add("js");
  var rtl = root.dir === "rtl", lang = root.lang === "ar" ? "ar" : "en";
  function $(sel, el) { return (el || doc).querySelector(sel); }
  function $$(sel, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(sel)); }
  function L(en, ar) { return lang === "ar" ? ar : en; }

  /* ---------- header drawer ---------- */
  function toggleMenu(btn, open) {
    var drawer = $("#" + btn.getAttribute("aria-controls"));
    if (!drawer) return;
    open = open == null ? !drawer.classList.contains("is-open") : open;
    drawer.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", String(open));
  }

  /* ---------- filters (programs, schedule) ---------- */
  function applyFilters(scope) {
    var active = {};
    $$("[data-filter]", scope).forEach(function (group) {
      var on = $('[aria-pressed="true"]', group);
      active[group.getAttribute("data-filter")] = on ? on.getAttribute("data-value") : "";
    });
    var items = $$("[data-groups], .ea-slot, .ea-wc", scope), shown = 0;
    items.forEach(function (el) {
      var ok = true;
      if (active.groups && el.hasAttribute("data-groups")) ok = el.getAttribute("data-groups").split(",").map(function (s) { return s.trim(); }).indexOf(active.groups) > -1;
      ["code", "age", "disc"].forEach(function (k) { if (active[k] && el.getAttribute("data-" + k) !== active[k]) ok = false; });
      el.hidden = !ok;
    });
    // Empty state: what the visitor can actually see (the day list on phones, the week grid on desktop).
    var week = $(".ea-week", scope), list;
    if (week && getComputedStyle(week).display !== "none") list = $$(".ea-wc", week);
    else if ($(".ea-daygroup", scope)) list = $$(".ea-slot", $(".ea-daygroup:not([hidden])", scope) || scope);
    else list = $$("[data-groups]", scope);
    list.forEach(function (el) { if (!el.hidden) shown++; });
    var empty = $("[data-filter-empty]", scope);
    if (empty) empty.hidden = shown > 0;
  }
  function filterScope(el) { return el.closest("[data-schedule]") || el.closest("section") || doc; }

  /* ---------- schedule day picker ---------- */
  function selectDay(tab, focus) {
    var bar = tab.parentNode, scope = filterScope(tab);
    $$('[data-ea="day"]', bar).forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
    });
    $$(".ea-daygroup", scope).forEach(function (g) { g.hidden = g.getAttribute("data-day") !== tab.getAttribute("data-day"); });
    if (focus) tab.focus();
    applyFilters(scope);
  }
  function initSchedules() {
    var params = new URLSearchParams(location.search);
    $$("[data-schedule]").forEach(function (sc) {
      var preset = params.get("branch") || sc.getAttribute("data-preset-branch");
      if (preset) {
        var chip = $('[data-filter="code"] [data-value="' + preset + '"]', sc);
        if (chip) $$('[data-filter="code"] [data-ea="chip"]', sc).forEach(function (c) { c.setAttribute("aria-pressed", String(c === chip)); });
      }
      var tab = $('[data-ea="day"][aria-selected="true"]', sc) || $('[data-ea="day"]', sc);
      if (tab) selectDay(tab, false); else applyFilters(sc);
    });
  }

  /* ---------- photo viewer ---------- */
  var viewerReturn = null;
  function viewerMove(v, d, absolute) {
    var slides = $$(".ea-viewer-slide", v), n = slides.length;
    var i = absolute != null ? absolute : (+v.getAttribute("data-i") || 0) + d;
    i = Math.max(0, Math.min(n - 1, i));
    v.setAttribute("data-i", i);
    $(".ea-viewer-track", v).style.transform = "translateX(" + (rtl ? i * 100 : -i * 100) + "%)";
    var c = $('[data-ea="count"]', v); if (c) c.textContent = (i + 1) + " / " + n;
    var cap = $('[data-ea="caption"]', v), text = slides[i] && slides[i].getAttribute("data-caption");
    if (cap && text) cap.textContent = text;
    slides.forEach(function (s, j) { s.setAttribute("aria-hidden", String(j !== i)); });
    var prev = $('[data-ea="prev"]', v), next = $('[data-ea="next"]', v);
    if (prev) prev.disabled = i === 0;
    if (next) next.disabled = i === n - 1;
  }
  function openViewer(index, from) {
    var overlay = $("[data-viewer-overlay]"); if (!overlay) return;
    viewerReturn = from;
    overlay.hidden = false; overlay.classList.add("is-open");
    doc.body.style.overflow = "hidden";
    var v = $(".ea-viewer", overlay);
    viewerMove(v, 0, index);
    v.focus();
  }
  function closeViewer() {
    var overlay = $("[data-viewer-overlay]"); if (!overlay || overlay.hidden) return;
    overlay.hidden = true; overlay.classList.remove("is-open");
    doc.body.style.overflow = "";
    if (viewerReturn) viewerReturn.focus();
  }
  function initViewer() {
    $$(".ea-viewer").forEach(function (v) {
      var x0 = null;
      v.addEventListener("pointerdown", function (e) { x0 = e.clientX; });
      v.addEventListener("pointerup", function (e) {
        if (x0 == null) return;
        var dx = e.clientX - x0; x0 = null;
        if (Math.abs(dx) > 40) viewerMove(v, (dx < 0) !== rtl ? 1 : -1);
      });
      v.addEventListener("keydown", function (e) {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); viewerMove(v, (e.key === "ArrowRight") !== rtl ? 1 : -1); }
        if (e.key === "Tab") trapFocus(e, v);
      });
    });
  }
  function trapFocus(e, box) {
    var f = $$("a[href], button:not([disabled]), input, [tabindex]:not([tabindex='-1'])", box).filter(function (el) { return el.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && doc.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && doc.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  /* ---------- SAQR ---------- */
  var saqr = { panel: null, opened: false, returnTo: null, busy: false };
  function csrf() { var m = doc.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/); return m ? decodeURIComponent(m[1]) : ""; }
  function saqrButtons(open) { $$('[data-ea="saqr"]').forEach(function (b) { b.setAttribute("aria-expanded", String(open)); }); }
  function openSaqr(from) {
    var p = saqr.panel; if (!p) return;
    saqr.returnTo = from || doc.activeElement;
    var overlay = $("[data-saqr-overlay]"), dock = $("[data-saqr-dock]");
    var phone = !window.matchMedia("(min-width: 960px)").matches;
    if (phone && overlay) { overlay.appendChild(p); p.classList.add("ea-saqr--sheet"); overlay.classList.add("is-open"); }
    else if (dock) { dock.insertBefore(p, dock.firstChild); p.classList.remove("ea-saqr--sheet"); }
    p.hidden = false; saqrButtons(true);
    if (!saqr.opened) { saqr.opened = true; saqrSend("", true); }
    var input = $("input", p); if (input) input.focus();
  }
  function closeSaqr() {
    var p = saqr.panel; if (!p || p.hidden) return;
    p.hidden = true; saqrButtons(false);
    var overlay = $("[data-saqr-overlay]"); if (overlay) overlay.classList.remove("is-open");
    if (saqr.returnTo && saqr.returnTo.focus) saqr.returnTo.focus();
  }
  function saqrAdd(cls, text) {
    var log = $("[data-saqr-log]", saqr.panel), el = doc.createElement("div");
    el.className = "ea-msg " + cls;
    el.textContent = text;
    el.style.whiteSpace = "pre-line";
    log.appendChild(el); log.scrollTop = log.scrollHeight;
    return el;
  }
  function saqrReply(data) {
    var log = $("[data-saqr-log]", saqr.panel);
    var msg = saqrAdd("ea-msg--bot", data.text || "");
    if (data.link) {
      var a = doc.createElement("a");
      a.href = data.link; a.rel = "noopener"; a.target = "_blank";
      a.textContent = " " + (data.link_label || "WhatsApp");
      msg.appendChild(doc.createElement("br")); msg.appendChild(a);
    }
    if (data.action === "trial") {
      var trial = saqr.panel.getAttribute("data-trial");
      if (trial) {
        var t = doc.createElement("a");
        t.className = "ea-btn ea-btn--primary ea-btn--sm";
        t.href = trial + "?source=saqr" + (data.branch ? "&branch=" + encodeURIComponent(data.branch) : "") + "#trial";
        t.textContent = L("Open the booking form", "افتح نموذج الحجز");
        log.appendChild(t);
      }
    }
    if (data.chips && data.chips.length) {
      var q = doc.createElement("div"); q.className = "ea-quick";
      data.chips.forEach(function (label) {
        var b = doc.createElement("button"); b.type = "button"; b.className = "ea-chip"; b.textContent = label;
        b.addEventListener("click", function () { q.remove(); saqrSend(label); });
        q.appendChild(b);
      });
      log.appendChild(q);
    }
    log.scrollTop = log.scrollHeight;
  }
  function saqrSend(text, silent) {
    if (saqr.busy) return;
    var p = saqr.panel;
    if (!silent) saqrAdd("ea-msg--me", text);
    var log = $("[data-saqr-log]", p), typing = doc.createElement("div");
    typing.className = "ea-msg ea-msg--bot ea-typing"; typing.setAttribute("aria-label", L("SAQR is typing", "صقر يكتب"));
    typing.innerHTML = "<i></i><i></i><i></i>";
    log.appendChild(typing); log.scrollTop = log.scrollHeight;
    saqr.busy = true;
    fetch(p.getAttribute("data-endpoint"), {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(), "Accept": "application/json" },
      body: JSON.stringify({ message: text, lang: lang })
    }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { typing.remove(); saqrReply(data); })
      .catch(function () {
        typing.remove();
        saqrAdd("ea-msg--bot", L("Sorry, I can't answer right now. Please WhatsApp the branch.", "عذراً، لا أستطيع الرد الآن. يرجى مراسلة الفرع عبر واتساب."));
      })
      .then(function () { saqr.busy = false; });
  }
  function initSaqr() {
    saqr.panel = $("#ea-saqr");
    if (!saqr.panel) return;
    var form = $("[data-saqr-form]", saqr.panel);
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var input = $("input", form), text = input.value.trim();
      if (!text) return;
      input.value = ""; saqrSend(text);
    });
    saqr.panel.addEventListener("keydown", function (e) { if (e.key === "Tab" && saqr.panel.classList.contains("ea-saqr--sheet")) trapFocus(e, saqr.panel); });
    var overlay = $("[data-saqr-overlay]");
    if (overlay) overlay.addEventListener("click", function (e) { if (e.target === overlay) closeSaqr(); });
  }

  /* ---------- trial form: programs follow the chosen branch ---------- */
  function syncPrograms(form) {
    var checked = $('input[name="branch"]:checked', form), select = $('select[name="program"]', form);
    if (!checked || !select) return;
    var code = checked.value;
    $$("optgroup", select).forEach(function (g) {
      var on = g.getAttribute("data-code") === code;
      g.hidden = !on; g.disabled = !on;
    });
    var opt = select.options[select.selectedIndex];
    if (opt && opt.parentNode.tagName === "OPTGROUP" && opt.parentNode.disabled) {
      var first = $('optgroup[data-code="' + code + '"] option', select);
      select.value = first ? first.value : "unsure";
    }
  }
  function initTrialForms() {
    $$("[data-trial-form]").forEach(function (form) {
      syncPrograms(form);
      form.addEventListener("change", function (e) { if (e.target.name === "branch") syncPrograms(form); });
    });
  }

  /* ---------- portal: one-time code ---------- */
  function initOtp() {
    $$("[data-otp-form]").forEach(function (form) {
      var boxes = $$(".ea-otp input", form);
      function fill(digits, start) {
        digits.split("").forEach(function (d, k) { if (boxes[start + k]) boxes[start + k].value = d; });
        var next = boxes[Math.min(start + digits.length, boxes.length - 1)]; next.focus();
        if (boxes.every(function (b) { return /^\d$/.test(b.value); })) form.requestSubmit ? form.requestSubmit() : form.submit();
      }
      boxes.forEach(function (box, i) {
        box.addEventListener("input", function () {
          var digits = box.value.replace(/[٠-٩]/g, function (c) { return String(c.charCodeAt(0) - 1632); }).replace(/\D/g, "");
          box.value = "";
          if (digits) fill(digits.slice(0, boxes.length - i), i);
        });
        box.addEventListener("keydown", function (e) {
          if (e.key === "Backspace" && !box.value && i > 0) { boxes[i - 1].focus(); boxes[i - 1].value = ""; }
        });
        box.addEventListener("paste", function (e) {
          var t = (e.clipboardData || window.clipboardData).getData("text").replace(/\D/g, "");
          if (t) { e.preventDefault(); fill(t.slice(0, boxes.length), 0); }
        });
      });
    });
    $$("[data-resend]").forEach(function (btn) {
      var left = +btn.getAttribute("data-wait") || 0, label = btn.getAttribute(lang === "ar" ? "data-label-ar" : "data-label-en");
      function tick() {
        if (left <= 0) { btn.disabled = false; btn.textContent = label; return; }
        btn.disabled = true;
        btn.textContent = label + " " + L("in", "بعد") + " 0:" + (left < 10 ? "0" : "") + left;
        left -= 1; setTimeout(tick, 1000);
      }
      tick();
    });
  }

  /* ---------- shop ---------- */
  function initCheckout() {
    var box = $("[data-fulfilment]"); if (!box) return;
    function sync() {
      var v = ($('input[name="fulfilment"]:checked', box) || {}).value || "pickup";
      $$("[data-show-for]").forEach(function (el) { el.hidden = el.getAttribute("data-show-for") !== v; });
    }
    box.addEventListener("change", sync); sync();
  }

  /* ---------- one click handler for everything ---------- */
  doc.addEventListener("click", function (e) {
    var t = e.target.closest("[data-ea]"); if (!t) return;
    var k = t.getAttribute("data-ea");
    if (k === "chip") {
      $$('[data-ea="chip"]', t.parentNode).forEach(function (c) { c.setAttribute("aria-pressed", String(c === t)); });
      applyFilters(filterScope(t));
    } else if (k === "clear-filters") {
      var scope = filterScope(t);
      $$("[data-filter]", scope).forEach(function (g) { $$('[data-ea="chip"]', g).forEach(function (c, i) { c.setAttribute("aria-pressed", String(i === 0)); }); });
      applyFilters(scope);
    } else if (k === "day") { selectDay(t, false); }
    else if (k === "menu") { toggleMenu(t); }
    else if (k === "prev" || k === "next") { viewerMove(t.closest(".ea-viewer"), k === "next" ? 1 : -1); }
    else if (k === "open-viewer") { openViewer(+t.getAttribute("data-index") || 0, t); }
    else if (k === "viewer-close") { closeViewer(); }
    else if (k === "saqr") { if (saqr.panel && !saqr.panel.hidden) closeSaqr(); else openSaqr(t); }
    else if (k === "saqr-close") { closeSaqr(); }
    else if (k === "qty") {
      var input = $("input", t.parentNode), v = (+input.value || 1) + (+t.getAttribute("data-step"));
      input.value = Math.max(+input.min || 1, Math.min(+input.max || 10, v));
    }
  });
  doc.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeViewer(); closeSaqr();
      var menu = $('[data-ea="menu"][aria-expanded="true"]'); if (menu) { toggleMenu(menu, false); menu.focus(); }
    }
    var tab = e.target.closest && e.target.closest('[data-ea="day"]');
    if (tab && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
      var tabs = $$('[data-ea="day"]', tab.parentNode), i = tabs.indexOf(tab);
      var step = (e.key === "ArrowRight") !== rtl ? 1 : -1;
      selectDay(tabs[(i + step + tabs.length) % tabs.length], true);
      e.preventDefault();
    }
  });
  window.addEventListener("resize", function () { $$("[data-schedule]").forEach(applyFilters); });

  function ready() {
    initSchedules(); initViewer(); initSaqr(); initTrialForms(); initOtp(); initCheckout();
    $$("section").forEach(function (s) { if ($('[data-filter="groups"]', s)) applyFilters(s); });
    var focusEl = $("[data-autofocus]") || $('[aria-invalid="true"]');
    if (focusEl) { focusEl.focus(); if (focusEl.scrollIntoView) focusEl.scrollIntoView({ block: "center" }); }
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", ready); else ready();
})();
