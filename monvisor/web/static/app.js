// MonVisor web UI — review toggles + generate trigger.

document.addEventListener("click", async (e) => {
  const tbtn = e.target.closest(".toggle button");
  if (tbtn) {
    const wrap = tbtn.closest(".toggle");
    const id = wrap.dataset.id;
    const monitor = tbtn.dataset.v === "1";
    const fd = new FormData();
    fd.append("monitor", monitor ? "true" : "false");
    try {
      const r = await fetch(`/api/services/${id}/decision`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(r.status);
      wrap.querySelector(".t-yes").classList.toggle("on", monitor);
      wrap.querySelector(".t-no").classList.toggle("on", !monitor);
    } catch (err) {
      alert("Failed to save decision: " + err);
    }
    return;
  }

  const gen = e.target.closest("#generate-btn");
  if (gen) {
    const env = gen.dataset.env;
    const status = document.getElementById("gen-status");
    gen.disabled = true;
    status.textContent = "Generating configs… this can take a moment.";
    try {
      const r = await fetch(`/api/env/${env}/generate`, { method: "POST" });
      if (!r.ok) throw new Error(r.status);
      status.textContent = "Configs generated. See ~/.monvisor/configs/.";
    } catch (err) {
      status.textContent = "Generation failed: " + err;
    } finally {
      gen.disabled = false;
    }
  }
});
