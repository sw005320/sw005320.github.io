// Palette + light/dark controls, and expand/collapse-all buttons.
// Both preferences are per-browser only (localStorage), so they never travel
// with the page -- a first-time visitor gets the default palette and the OS
// light/dark setting.
(function () {
  var root = document.documentElement;
  var THEME_KEY = "sw-theme";
  var PALETTE_KEY = "sw-palette";

  function remember(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* blocked storage */ }
  }
  function recall(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  var savedTheme = recall(THEME_KEY);
  if (savedTheme) root.setAttribute("data-theme", savedTheme);
  root.setAttribute("data-palette", recall(PALETTE_KEY) || "paper");

  var swatches = [].slice.call(document.querySelectorAll(".swatch"));
  function markSwatches() {
    var current = root.getAttribute("data-palette");
    swatches.forEach(function (s) {
      s.setAttribute("aria-pressed", String(s.dataset.palette === current));
    });
  }
  markSwatches();

  swatches.forEach(function (s) {
    s.addEventListener("click", function () {
      root.setAttribute("data-palette", s.dataset.palette);
      remember(PALETTE_KEY, s.dataset.palette);
      markSwatches();
    });
  });

  var btn = document.getElementById("theme");
  if (btn) {
    btn.addEventListener("click", function () {
      var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      var now = root.getAttribute("data-theme") || (prefersDark ? "dark" : "light");
      var next = now === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      remember(THEME_KEY, next);
    });
  }

  document.querySelectorAll("[data-all]").forEach(function (b) {
    b.addEventListener("click", function () {
      var open = b.getAttribute("data-all") === "open";
      document.querySelectorAll("details.sec").forEach(function (d) {
        d.open = open;
      });
    });
  });
})();
