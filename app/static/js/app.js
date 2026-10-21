/* TaskFlow front-end. Talks to the Flask JSON API; no data is stored in the browser. */
(function () {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  /* ---------- Toasts (used on every page) ---------- */
  function showToast(message, type = "success") {
    const container = $("#toastContainer");
    const icons = { success: "bi-check-circle-fill", danger: "bi-exclamation-triangle-fill", info: "bi-info-circle-fill" };
    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute("role", type === "danger" ? "alert" : "status");
    const body = document.createElement("div");
    body.className = "d-flex";
    const inner = document.createElement("div");
    inner.className = "toast-body";
    const icon = document.createElement("i");
    icon.className = `bi ${icons[type] || icons.info}`;
    icon.setAttribute("aria-hidden", "true");
    const text = document.createElement("span");
    text.textContent = message;
    inner.append(icon, text);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close btn-close-white me-2 m-auto";
    close.setAttribute("data-bs-dismiss", "toast");
    close.setAttribute("aria-label", "Close");
    body.append(inner, close);
    toast.append(body);
    container.append(toast);
    toast.addEventListener("hidden.bs.toast", () => toast.remove());
    new bootstrap.Toast(toast, { delay: type === "danger" ? 6000 : 3500 }).show();
  }

  /* ---------- Mobile sidebar ---------- */
  const sidebar = $("#sidebar");
  const backdrop = $("#sidebarBackdrop");
  const toggle = $("#sidebarToggle");
  function setSidebar(open) {
    sidebar.classList.toggle("open", open);
    backdrop.classList.toggle("show", open);
    toggle.setAttribute("aria-expanded", String(open));
  }
  toggle.addEventListener("click", () => setSidebar(!sidebar.classList.contains("open")));
  backdrop.addEventListener("click", () => setSidebar(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setSidebar(false); });

  /* ---------- Dashboard only ---------- */
  const grid = $("#taskGrid");
  if (!grid) return;

  const state = {
    q: "",
    status: grid.dataset.presetStatus || "",
    priority: grid.dataset.presetPriority || "",
    due: "",
    sort: "created_desc",
  };
  const tasksById = new Map();
  let totalInDb = 0;
  let firstLoad = true;
  let requestCounter = 0;

  const taskModalEl = $("#taskModal");
  const deleteModalEl = $("#deleteModal");
  const taskModal = new bootstrap.Modal(taskModalEl);
  const deleteModal = new bootstrap.Modal(deleteModalEl);
  const form = $("#taskForm");
  const saveBtn = $("#saveTaskBtn");
  const confirmDeleteBtn = $("#confirmDeleteBtn");
  let pendingDeleteId = null;

  /* ---------- API helper ---------- */
  async function api(url, options = {}) {
    let response;
    try {
      response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
    } catch (networkError) {
      const err = new Error("Cannot reach the server. Check that the containers are running.");
      err.fieldErrors = {};
      throw err;
    }
    let data = null;
    try { data = await response.json(); } catch (_) { /* body was not JSON */ }
    if (!response.ok) {
      const err = new Error((data && data.error) || "Something went wrong. Please try again.");
      err.fieldErrors = (data && data.errors) || {};
      throw err;
    }
    return data;
  }

  /* ---------- Small DOM helper ---------- */
  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    }
    node.append(...children);
    return node;
  }
  const icon = (name) => el("i", { class: `bi ${name}`, "aria-hidden": "true" });

  /* ---------- Dates ---------- */
  function parseDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  function dueText(task) {
    if (!task.due_date) return "No due date";
    const due = parseDate(task.due_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const days = Math.round((due - today) / 86400000);
    const pretty = due.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    if (task.is_overdue) return `Overdue by ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} (${pretty})`;
    if (days === 0) return "Due today";
    if (days === 1) return "Due tomorrow";
    return `Due ${pretty}`;
  }

  /* ---------- Rendering ---------- */
  function renderSkeletons() {
    grid.replaceChildren(...Array.from({ length: 6 }, () => el("div", { class: "skeleton" })));
  }

  function renderCard(task) {
    const done = task.status === "completed";
    const statusSelect = el("select", {
      class: "form-select",
      "aria-label": `Change status of ${task.title}`,
      onchange: (e) => changeStatus(task.id, e.target.value),
    });
    [["todo", "To Do"], ["in_progress", "In Progress"], ["completed", "Completed"]].forEach(([value, label]) => {
      const option = el("option", { value, text: label });
      if (value === task.status) option.selected = true;
      statusSelect.append(option);
    });

    const checkBtn = el("button", {
      type: "button",
      class: "check-btn",
      "aria-label": done ? `Reopen ${task.title}` : `Mark ${task.title} as completed`,
      onclick: () => changeStatus(task.id, done ? "todo" : "completed"),
    }, icon(done ? "bi-check-circle-fill" : "bi-circle"));

    const card = el("article", { class: `task-card prio-${task.priority} ${done ? "is-done" : ""}` },
      el("div", { class: "task-head" }, checkBtn, el("h3", { class: "task-title", text: task.title })),
    );
    if (task.description) card.append(el("p", { class: "task-desc", text: task.description }));
    card.append(
      el("div", { class: "badges" },
        el("span", { class: `badge-pill st-${task.status}`, text: task.status_label }),
        el("span", { class: `badge-pill pr-${task.priority}` }, icon("bi-flag-fill"), document.createTextNode(`${task.priority_label} priority`)),
      ),
      el("div", { class: `due ${task.is_overdue ? "overdue" : ""}` }, icon(task.is_overdue ? "bi-exclamation-circle-fill" : "bi-calendar-event"), el("span", { text: dueText(task) })),
      el("div", { class: "task-foot" },
        statusSelect,
        el("div", { class: "card-actions" },
          el("button", { type: "button", "aria-label": `Edit ${task.title}`, title: "Edit", onclick: () => openEdit(task.id) }, icon("bi-pencil")),
          el("button", { type: "button", class: "delete-action", "aria-label": `Delete ${task.title}`, title: "Delete", onclick: () => openDelete(task.id) }, icon("bi-trash3")),
        ),
      ),
    );
    return card;
  }

  function renderTasks(tasks) {
    tasksById.clear();
    tasks.forEach((t) => tasksById.set(t.id, t));
    const empty = $("#emptyState");
    if (tasks.length === 0) {
      grid.replaceChildren();
      grid.classList.add("d-none");
      empty.classList.remove("d-none");
      const filtering = totalInDb > 0;
      $("#emptyTitle").textContent = filtering ? "No tasks match your filters" : "No tasks yet";
      $("#emptyText").textContent = filtering
        ? "Try a different search or clear the filters to see everything."
        : "Add your first task to start tracking your work.";
      $("#emptyAction").textContent = filtering ? "Clear filters" : "Add your first task";
    } else {
      empty.classList.add("d-none");
      grid.classList.remove("d-none");
      grid.replaceChildren(...tasks.map(renderCard));
    }
    $("#resultCount").textContent = `${tasks.length} ${tasks.length === 1 ? "task" : "tasks"} shown`;
  }

  function renderStats(stats) {
    totalInDb = stats.total;
    $$("[data-stat]").forEach((node) => { node.textContent = stats[node.dataset.stat]; });
    $$("[data-count]").forEach((node) => { node.textContent = stats[node.dataset.count]; });
    $("#progressPercent").textContent = `${stats.completion_percent}%`;
    $("#progressFill").style.width = `${stats.completion_percent}%`;
    $("#progressBar").setAttribute("aria-valuenow", stats.completion_percent);
    $("#progressText").textContent = stats.total
      ? `${stats.completed} of ${stats.total} tasks completed`
      : "Add a task to start tracking progress";
    $("#overdueCount").textContent = stats.overdue;
    $("#overdueChip").classList.toggle("d-none", stats.overdue === 0);
  }

  /* ---------- Loading data ---------- */
  async function refresh() {
    const ticket = ++requestCounter;
    const params = new URLSearchParams();
    Object.entries(state).forEach(([key, value]) => { if (value) params.set(key, value); });
    grid.setAttribute("aria-busy", "true");
    if (firstLoad) renderSkeletons(); else grid.classList.add("is-refreshing");
    try {
      const [taskData, stats] = await Promise.all([api(`/api/tasks?${params}`), api("/api/stats")]);
      if (ticket !== requestCounter) return; // a newer request already replaced this one
      renderStats(stats);
      renderTasks(taskData.tasks);
    } catch (err) {
      if (ticket !== requestCounter) return;
      grid.replaceChildren();
      showToast(err.message, "danger");
    } finally {
      if (ticket === requestCounter) {
        firstLoad = false;
        grid.classList.remove("is-refreshing");
        grid.setAttribute("aria-busy", "false");
      }
    }
  }

  /* ---------- Filters ---------- */
  function syncControls() {
    $("#searchInput").value = state.q;
    $("#filterStatus").value = state.status;
    $("#filterPriority").value = state.priority;
    $("#filterDue").value = state.due;
    $("#sortBy").value = state.sort;
  }
  let searchTimer;
  $("#searchInput").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.q = e.target.value.trim(); refresh(); }, 300);
  });
  [["#filterStatus", "status"], ["#filterPriority", "priority"], ["#filterDue", "due"], ["#sortBy", "sort"]].forEach(([selector, key]) => {
    $(selector).addEventListener("change", (e) => { state[key] = e.target.value; refresh(); });
  });
  function clearFilters() {
    Object.assign(state, { q: "", status: "", priority: "", due: "", sort: "created_desc" });
    syncControls();
    refresh();
  }

  /* ---------- Add / edit ---------- */
  function clearErrors() {
    $$(".is-invalid", form).forEach((n) => n.classList.remove("is-invalid"));
    $$(".invalid-feedback", form).forEach((n) => { n.textContent = ""; });
  }
  function showFieldErrors(errors) {
    Object.entries(errors).forEach(([field, message]) => {
      const input = form.elements[field];
      const feedback = $(`#err-${field}`);
      if (input && feedback) {
        input.classList.add("is-invalid");
        feedback.textContent = message;
      }
    });
    const first = $(".is-invalid", form);
    if (first) first.focus();
  }
  function setBusy(button, busy, label) {
    button.disabled = busy;
    $(".spinner-border", button).classList.toggle("d-none", !busy);
    if (label) $(".btn-label", button).textContent = label;
  }

  function openCreate() {
    form.reset();
    clearErrors();
    $("#taskId").value = "";
    $("#taskPriority").value = "medium";
    $("#taskStatus").value = state.status || "todo";
    if (state.priority) $("#taskPriority").value = state.priority;
    $("#taskModalTitle").textContent = "Add new task";
    $(".btn-label", saveBtn).textContent = "Add task";
    taskModal.show();
  }
  function openEdit(id) {
    const task = tasksById.get(id);
    if (!task) return;
    form.reset();
    clearErrors();
    $("#taskId").value = task.id;
    $("#taskTitle").value = task.title;
    $("#taskDescription").value = task.description;
    $("#taskStatus").value = task.status;
    $("#taskPriority").value = task.priority;
    $("#taskDue").value = task.due_date || "";
    $("#taskModalTitle").textContent = "Edit task";
    $(".btn-label", saveBtn).textContent = "Save changes";
    taskModal.show();
  }
  taskModalEl.addEventListener("shown.bs.modal", () => $("#taskTitle").focus());

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearErrors();
    const id = $("#taskId").value;
    const payload = {
      title: $("#taskTitle").value.trim(),
      description: $("#taskDescription").value.trim(),
      status: $("#taskStatus").value,
      priority: $("#taskPriority").value,
      due_date: $("#taskDue").value || null,
    };
    if (!payload.title) {
      showFieldErrors({ title: "Enter a title for the task." });
      return;
    }
    const editing = Boolean(id);
    setBusy(saveBtn, true, editing ? "Saving..." : "Adding...");
    try {
      await api(editing ? `/api/tasks/${id}` : "/api/tasks", { method: editing ? "PUT" : "POST", body: JSON.stringify(payload) });
      taskModal.hide();
      showToast(editing ? "Task updated." : "Task added.");
      await refresh();
    } catch (err) {
      showFieldErrors(err.fieldErrors || {});
      showToast(err.message, "danger");
    } finally {
      setBusy(saveBtn, false, editing ? "Save changes" : "Add task");
    }
  });

  /* ---------- Status change ---------- */
  async function changeStatus(id, status) {
    try {
      await api(`/api/tasks/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
      const labels = { todo: "To Do", in_progress: "In Progress", completed: "Completed" };
      showToast(`Task moved to ${labels[status]}.`);
    } catch (err) {
      showToast(err.message, "danger");
    }
    await refresh();
  }

  /* ---------- Delete ---------- */
  function openDelete(id) {
    const task = tasksById.get(id);
    if (!task) return;
    pendingDeleteId = id;
    $("#deleteTaskName").textContent = task.title;
    deleteModal.show();
  }
  confirmDeleteBtn.addEventListener("click", async () => {
    if (pendingDeleteId === null) return;
    setBusy(confirmDeleteBtn, true, "Deleting...");
    try {
      await api(`/api/tasks/${pendingDeleteId}`, { method: "DELETE" });
      deleteModal.hide();
      showToast("Task deleted.");
      await refresh();
    } catch (err) {
      showToast(err.message, "danger");
    } finally {
      pendingDeleteId = null;
      setBusy(confirmDeleteBtn, false, "Delete task");
    }
  });

  /* ---------- Wire up and start ---------- */
  $("#addTaskBtn").addEventListener("click", openCreate);
  $("#emptyAction").addEventListener("click", () => (totalInDb > 0 ? clearFilters() : openCreate()));
  syncControls();
  refresh();
})();
