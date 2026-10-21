// Small enhancements. The app works without this file; it only adds live feedback.

// 1. Live risk rating on the hazard form, using the matrix embedded in the page.
(function () {
  const el = document.getElementById("matrix-data");
  if (!el) return;
  const matrix = JSON.parse(el.textContent);
  document.querySelectorAll("[data-score]").forEach(function (box) {
    const prefix = box.dataset.score;
    const l = box.querySelector("select[name=" + prefix + "_likelihood]");
    const c = box.querySelector("select[name=" + prefix + "_consequence]");
    const out = box.querySelector(".result");
    function update() {
      const cell = matrix[l.value + "-" + c.value];
      out.innerHTML = "";
      if (!cell) { out.innerHTML = '<span class="risk none">Not scored</span><small>Pick both values to calculate the rating.</small>'; return; }
      const chip = document.createElement("span");
      chip.className = "risk"; chip.style.setProperty("--rc", cell.color);
      const b = document.createElement("b"); b.textContent = cell.code;
      chip.append(b, cell.label);
      const note = document.createElement("small"); note.textContent = cell.action;
      out.append(chip, note);
    }
    l.addEventListener("change", update); c.addEventListener("change", update); update();
  });
})();

// 2. Add / remove measure rows on the hazard form.
(function () {
  const tpl = document.getElementById("measure-row");
  const list = document.getElementById("new-measures");
  if (!tpl || !list) return;
  document.querySelectorAll("[data-measure]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const row = tpl.content.firstElementChild.cloneNode(true);
      const input = row.querySelector("input[name=m_text]");
      input.value = btn.dataset.measure;
      list.appendChild(row);
      if (btn.dataset.measure) btn.remove(); else input.focus();
    });
  });
  list.addEventListener("click", function (e) {
    if (e.target.matches("[data-remove]")) e.target.closest(".newm").remove();
  });
})();

// 3. Progress slider label on the task page.
(function () {
  const r = document.getElementById("progress");
  const o = document.getElementById("progress-out");
  if (r && o) r.addEventListener("input", function () { o.textContent = r.value + "%"; });
})();
