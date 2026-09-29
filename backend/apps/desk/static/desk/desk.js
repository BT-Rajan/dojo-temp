/* Desk helpers: branch switch, signature pad, sale totals, card-scanner focus. No inline scripts (CSP). */
(function () {
  "use strict";
  var doc = document;
  function $(s, el) { return (el || doc).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(s)); }

  $$("[data-autosubmit]").forEach(function (el) { el.addEventListener("change", function () { el.form.submit(); }); });

  document.querySelectorAll("[data-print]").forEach(function (b) { b.addEventListener("click", function () { window.print(); }); });

  // Confirm before irreversible actions.
  doc.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Signature pad (rules agreement, signed on screen).
  $$("[data-signature]").forEach(function (canvas) {
    var input = doc.getElementById(canvas.getAttribute("data-signature"));
    var ctx = canvas.getContext("2d"), drawing = false, used = false;
    function size() {
      var r = canvas.getBoundingClientRect();
      canvas.width = r.width * 2; canvas.height = r.height * 2;
      ctx.scale(2, 2); ctx.lineWidth = 2.2; ctx.lineCap = "round"; ctx.strokeStyle = getComputedStyle(canvas).color;
    }
    size();
    function pos(e) { var r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    canvas.addEventListener("pointerdown", function (e) { drawing = true; used = true; var p = pos(e); ctx.beginPath(); ctx.moveTo(p[0], p[1]); canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", function (e) { if (!drawing) return; var p = pos(e); ctx.lineTo(p[0], p[1]); ctx.stroke(); });
    function end() { if (drawing) { drawing = false; input.value = used ? canvas.toDataURL("image/png") : ""; } }
    canvas.addEventListener("pointerup", end); canvas.addEventListener("pointerleave", end);
    var clear = doc.querySelector('[data-signature-clear="' + canvas.id + '"]');
    if (clear) clear.addEventListener("click", function () { ctx.clearRect(0, 0, canvas.width, canvas.height); used = false; input.value = ""; });
  });

  // Point of sale: live totals (the server recalculates everything).
  var sell = $("[data-sell]");
  if (sell) {
    var fmt = function (n) { return (Math.round(n * 1000) / 1000).toFixed(3); };
    var recalc = function () {
      var total = 0;
      $$("[data-line]", sell).forEach(function (row) {
        var sel = $("select[name^=item_]", row), opt = sel.options[sel.selectedIndex];
        var price = parseFloat(opt && opt.getAttribute("data-price") || "0");
        var qty = parseInt($("input[name^=qty_]", row).value || "1", 10);
        var free = $("input[name^=free_]", row);
        if (free && free.checked) price = 0;
        var d = $("select[name^=discount_]", row), dopt = d && d.options[d.selectedIndex];
        var gross = price * qty, disc = 0;
        if (dopt && dopt.getAttribute("data-percent")) disc = gross * parseFloat(dopt.getAttribute("data-percent")) / 100;
        if (dopt && dopt.getAttribute("data-amount")) disc = Math.min(gross, parseFloat(dopt.getAttribute("data-amount")));
        $("[data-line-total]", row).textContent = fmt(gross - disc);
        row.querySelectorAll("[data-for-variant]").forEach(function (el) { el.hidden = !(opt && opt.value.indexOf("v:") === 0); });
        row.querySelectorAll("[data-for-option]").forEach(function (el) { el.hidden = !(opt && opt.value.indexOf("p:") === 0 && opt.getAttribute("data-validity")); });
        total += gross - disc;
      });
      $("[data-total]", sell).textContent = fmt(total);
      var paid = 0;
      $$("input[name^=pay_amount_]", sell).forEach(function (i) { paid += parseFloat(i.value || "0"); });
      var left = $("[data-left]", sell); left.textContent = fmt(total - paid);
      left.parentNode.classList.toggle("dk-flag", Math.abs(total - paid) > 0.0005);
      var first = $("input[name=pay_amount_0]", sell);
      if (first && !first.dataset.touched) first.value = total ? fmt(total) : "";
    };
    sell.addEventListener("input", function (e) { if (e.target.name && e.target.name.indexOf("pay_amount_") === 0) e.target.dataset.touched = "1"; recalc(); });
    sell.addEventListener("change", recalc);
    recalc();
  }

  // Keep the card-scanner box focused on the check-in screen (scanners type like a keyboard).
  var scan = $("[data-scan]");
  if (scan && !doc.querySelector("[aria-invalid=true]")) scan.focus();
})();
