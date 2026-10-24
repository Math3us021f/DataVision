document.getElementById("logout-button").addEventListener("click", async () => {
    await apiRequest("/logout", { method: "POST" });
    window.location.href = "/login";
});
