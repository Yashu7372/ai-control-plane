const apiBase = window.AI_CONTROL_PLANE_API || "http://localhost:8000";

async function loadJson(path, target) {
  const element = document.getElementById(target);
  try {
    const response = await fetch(`${apiBase}${path}`);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    element.textContent = JSON.stringify(await response.json(), null, 2);
  } catch (error) {
    element.textContent = `Unavailable: ${error.message}`;
  }
}

loadJson("/health", "health");
loadJson("/approvals", "approvals");
