// Tema aplicado antes de desenhar a página, para não "piscar" o tema errado.
// Sem escolha salva, segue o tema do sistema operacional. É um arquivo à parte (e não um <script>
// dentro do HTML) para a política de segurança de conteúdo poder proibir qualquer script inline.
(function () {
  var theme = null;
  try { theme = localStorage.getItem("datavision-theme"); } catch (e) {}
  if (theme !== "light" && theme !== "dark") {
    theme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  document.documentElement.classList.toggle("dark", theme === "dark");
})();
