const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return response.json();
};

const showView = (name) => {
  document.querySelectorAll(".journal-panel").forEach((panel) => panel.classList.add("hidden"));
  document.querySelector(`#${name}-view`).classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
};

const loadHealth = async () => {
  const status = document.querySelector("#journal-status");
  try {
    const data = await api("/api/journal/health");
    status.textContent = data.ok ? `Local only · ${data.stats.journal_events} events` : "Unavailable";
  } catch {
    status.textContent = "Local preview";
  }
};

const loadTimeline = async () => {
  const list = document.querySelector("#timeline-list");
  list.textContent = "Loading...";
  try {
    const data = await api("/api/journal/timeline");
    list.innerHTML = data.events.map((event) => `
      <article class="event-row">
        <div class="event-meta">${event.event_ts} · ${event.source} · ${event.project_id}</div>
        <strong>${event.title}</strong>
        <p>${event.summary}</p>
      </article>
    `).join("");
  } catch {
    list.textContent = "Timeline API is not connected in this static preview.";
  }
};

const loadProjects = async () => {
  const list = document.querySelector("#project-list");
  list.textContent = "Loading...";
  try {
    const data = await api("/api/journal/projects");
    list.innerHTML = data.projects.map((project) => `
      <article class="project-row">
        <strong>${project.label}</strong>
        <p>${project.project_id} · ${project.folder_hashes.length} folders</p>
      </article>
    `).join("");
  } catch {
    list.textContent = "Project API is not connected in this static preview.";
  }
};

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.view));
});

document.querySelector("#refresh-timeline").addEventListener("click", loadTimeline);
document.querySelector("#refresh-projects").addEventListener("click", loadProjects);

document.querySelector("#manual-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  const result = await api("/api/journal/manual-entry", { method: "POST", body: JSON.stringify(payload) });
  document.querySelector("#manual-result").textContent = JSON.stringify(result, null, 2);
});

document.querySelectorAll("[data-period]").forEach((button) => {
  button.addEventListener("click", async () => {
    const result = await api("/api/journal/generate-summary", {
      method: "POST",
      body: JSON.stringify({ period_type: button.dataset.period }),
    });
    document.querySelector("#summary-result").textContent = JSON.stringify(result, null, 2);
  });
});

document.querySelectorAll("[data-export]").forEach((button) => {
  button.addEventListener("click", async () => {
    const result = await api("/api/journal/export", {
      method: "POST",
      body: JSON.stringify({ export_type: button.dataset.export, period_type: "daily" }),
    });
    document.querySelector("#export-result").textContent = JSON.stringify(result, null, 2);
  });
});

loadHealth();
loadTimeline();
