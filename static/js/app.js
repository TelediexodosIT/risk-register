// Small enhancements. Pages still work without this file, except the "add action" pop-up.

// 1. Light / dark toggle (remembered per browser).
document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var root = document.documentElement;
    var current = root.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    var next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  });
});

// 2. Mobile menu.
document.querySelectorAll("[data-menu]").forEach(function (el) {
  el.addEventListener("click", function () {
    var open = document.body.classList.toggle("nav-open");
    document.querySelectorAll("button[data-menu]").forEach(function (b) { b.setAttribute("aria-expanded", open); });
  });
});
document.addEventListener("keydown", function (e) { if (e.key === "Escape") document.body.classList.remove("nav-open"); });

// 3. Progress slider label on the action page.
(function () {
  var r = document.getElementById("progress"), o = document.getElementById("progress-out");
  if (r && o) r.addEventListener("input", function () { o.textContent = r.value + "%"; });
})();

// 4. Risk task form: "manual add" for the hazard, live risk rating from the sliders, actions pop-up.
(function () {
  var form = document.getElementById("risk-task-form");
  if (!form) return;
  var data = JSON.parse(document.getElementById("rt-data").textContent);
  var greek = document.documentElement.lang === "el";

  var hz = form.querySelector("select[name=hazard]"), hzManual = document.getElementById("hazard-manual-box");
  function syncHazard() { hzManual.hidden = hz.value !== "__manual__"; }
  if (hz) { hz.addEventListener("change", syncHazard); syncHazard(); }

  function label(item) { return greek ? item.label : item.label_en; }
  document.querySelectorAll("[data-score]").forEach(function (box) {
    var p = box.dataset.score;
    var l = box.querySelector("input[name=" + p + "_l]"), c = box.querySelector("input[name=" + p + "_c]");
    var lOut = box.querySelector("[data-out=l]"), cOut = box.querySelector("[data-out=c]"), out = box.querySelector(".result");
    function update() {
      var lv = data.levels.l[l.value], cv = data.levels.c[c.value];
      lOut.textContent = lv.code + " · " + label(lv);
      cOut.textContent = cv.code + " · " + label(cv);
      var cell = data.matrix[lv.id + "-" + cv.id];
      out.innerHTML = "";
      if (!cell) return;
      var chip = document.createElement("span"); chip.className = "risk"; chip.style.setProperty("--rc", cell.color);
      var b = document.createElement("b"); b.textContent = cell.code; chip.append(b, greek ? cell.label : cell.label_en);
      var note = document.createElement("small"); note.textContent = greek ? cell.action : cell.action_en;
      out.append(chip, note);
    }
    l.addEventListener("input", update); c.addEventListener("input", update); update();
  });

  var dlg = document.getElementById("action-dialog"), list = document.getElementById("pending-actions");
  var tpl = document.getElementById("pending-row");
  document.querySelectorAll("[data-open-action]").forEach(function (b) {
    b.addEventListener("click", function () {
      dlg.querySelector("[name=d_measure]").value = "";
      dlg.querySelector("[name=d_manual]").value = "";
      dlg.querySelector("#d-manual-box").hidden = true;
      dlg.querySelector(".err").hidden = true;
      dlg.showModal();
    });
  });
  var dMeasure = dlg.querySelector("[name=d_measure]");
  dMeasure.addEventListener("change", function () {
    dlg.querySelector("#d-manual-box").hidden = dMeasure.value !== "__manual__";
  });
  dlg.querySelectorAll("[data-close]").forEach(function (b) { b.addEventListener("click", function () { dlg.close(); }); });
  dlg.querySelector("[data-add]").addEventListener("click", function () {
    var text = dMeasure.value === "__manual__" ? dlg.querySelector("[name=d_manual]").value.trim() : dMeasure.value;
    var owner = dlg.querySelector("[name=d_owner]"), due = dlg.querySelector("[name=d_due]").value;
    var remind = dlg.querySelector("[name=d_remind]").value;
    if (!text || !owner.value) { dlg.querySelector(".err").hidden = false; return; }
    var row = tpl.content.firstElementChild.cloneNode(true);
    row.querySelector("[name=m_text]").value = text;
    row.querySelector("[name=m_owner]").value = owner.value;
    row.querySelector("[name=m_due]").value = due;
    row.querySelector("[name=m_remind]").value = remind;
    row.querySelector("[data-text]").textContent = text;
    row.querySelector("[data-meta]").textContent = owner.options[owner.selectedIndex].text + (due ? " · " + due.split("-").reverse().join("/") : "");
    list.appendChild(row);
    list.hidden = false;
    dlg.close();
  });
  list.addEventListener("click", function (e) {
    if (e.target.matches("[data-remove]")) e.target.closest("li").remove();
  });
})();
