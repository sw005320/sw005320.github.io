// Live search + year filter for the publications page.
(function () {
  var q = document.getElementById("q");
  var year = document.getElementById("year");
  var status = document.getElementById("status");
  if (!q) return;

  var items = [].slice.call(document.querySelectorAll(".entries li"));
  items.forEach(function (li) {
    li.dataset.text = li.textContent.toLowerCase();
    li.dataset.html = li.innerHTML;
  });

  function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // Wrap matches in <mark>, but only inside text nodes so tags survive.
  function highlight(li, term) {
    if (!term) {
      li.innerHTML = li.dataset.html;
      return;
    }
    var re = new RegExp("(" + escapeRe(term) + ")", "ig");
    var tmp = document.createElement("div");
    tmp.innerHTML = li.dataset.html;
    var walker = document.createTreeWalker(tmp, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (n) {
      if (!re.test(n.nodeValue)) return;
      re.lastIndex = 0;
      var span = document.createElement("span");
      span.innerHTML = n.nodeValue.replace(re, "<mark>$1</mark>");
      n.parentNode.replaceChild(span, n);
    });
    li.innerHTML = tmp.innerHTML;
  }

  function apply() {
    var term = q.value.trim().toLowerCase();
    var y = year.value;
    var shown = 0;

    items.forEach(function (li) {
      var ok = (!term || li.dataset.text.indexOf(term) !== -1) &&
               (!y || li.dataset.year === y);
      li.classList.toggle("hide", !ok);
      if (ok) {
        shown++;
        highlight(li, term);
      }
    });

    document.querySelectorAll("details.sec").forEach(function (d) {
      var vis = d.querySelectorAll(".entries li:not(.hide)").length;
      var badge = d.querySelector(".shown");
      if (badge) badge.textContent = vis;
      if (term || y) d.open = vis > 0;
    });

    status.textContent = (term || y)
      ? shown + " matching " + (shown === 1 ? "entry" : "entries")
      : "";
  }

  var timer;
  function debounced() {
    clearTimeout(timer);
    timer = setTimeout(apply, 120);
  }

  q.addEventListener("input", debounced);
  year.addEventListener("change", apply);
})();
