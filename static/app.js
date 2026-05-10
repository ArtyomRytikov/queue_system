const state = {
    user: null,
    services: [],
    selectedServiceId: null,
    weekOffset: 0,
    availability: null,
    appointments: [],
    board: null,
    operatorWindows: [],
    selectedWindowId: null,
    operatorDashboard: null,
    adminOverview: null,
};

const weekdayMap = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const elements = {
    authSection: document.getElementById("authSection"),
    dashboardSection: document.getElementById("dashboardSection"),
    studentSection: document.getElementById("studentSection"),
    operatorSection: document.getElementById("operatorSection"),
    adminSection: document.getElementById("adminSection"),
    toast: document.getElementById("toast"),
    boardMetrics: document.getElementById("boardMetrics"),
    windowBoard: document.getElementById("windowBoard"),
    upcomingBoard: document.getElementById("upcomingBoard"),
    boardUpdatedLabel: document.getElementById("boardUpdatedLabel"),
    userNameLabel: document.getElementById("userNameLabel"),
    userMetaLabel: document.getElementById("userMetaLabel"),
    serviceCards: document.getElementById("serviceCards"),
    availabilityGrid: document.getElementById("availabilityGrid"),
    weekLabel: document.getElementById("weekLabel"),
    studentAppointments: document.getElementById("studentAppointments"),
    operatorWindowSelect: document.getElementById("operatorWindowSelect"),
    operatorCurrentCard: document.getElementById("operatorCurrentCard"),
    operatorQueueList: document.getElementById("operatorQueueList"),
    adminServicesList: document.getElementById("adminServicesList"),
    adminWindowsList: document.getElementById("adminWindowsList"),
    adminRulesList: document.getElementById("adminRulesList"),
    ruleWindowSelect: document.querySelector("#ruleForm select[name='window_id']"),
};

function showToast(message, isError = false) {
    const normalized =
        typeof message === "string"
            ? message
            : message?.message
                ? String(message.message)
                : JSON.stringify(message ?? "Неизвестная ошибка");
    elements.toast.textContent = normalized;
    elements.toast.classList.remove("hidden");
    elements.toast.style.background = isError ? "rgba(145, 42, 24, 0.94)" : "rgba(23, 34, 39, 0.92)";
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => elements.toast.classList.add("hidden"), 3200);
}

function formatDateTime(value) {
    return new Date(value).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function formatDate(value) {
    return new Date(value).toLocaleDateString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    });
}

function formatTime(value) {
    return new Date(value).toLocaleTimeString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
    });
}

function field(form, name) {
    return form.elements.namedItem(name);
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[char]));
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        credentials: "same-origin",
        ...options,
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        let message = data.detail || data.message || "Запрос завершился с ошибкой.";
        if (Array.isArray(message)) {
            message = message
                .map((item) => item.msg || item.message || JSON.stringify(item))
                .join("; ");
        } else if (typeof message === "object") {
            message = JSON.stringify(message);
        }
        throw new Error(message);
    }
    return data;
}

function renderBoard() {
    if (!state.board) {
        return;
    }

    const metrics = [
        { label: "Всего записей сегодня", value: state.board.today_total },
        { label: "Сейчас вызываются", value: state.board.in_progress },
        { label: "Завершено", value: state.board.completed },
    ];

    elements.boardMetrics.innerHTML = metrics
        .map(
            (item) => `
                <article class="metric-card">
                    <span class="eyebrow">${item.label}</span>
                    <strong>${item.value}</strong>
                </article>
            `
        )
        .join("");

    elements.windowBoard.innerHTML =
        state.board.windows
            .map(
                (window) => `
                    <article class="window-card">
                        <strong>${escapeHtml(window.name)}</strong>
                        <small>${escapeHtml(window.location || "Локация не указана")}</small>
                        <div class="top-gap">
                            <span class="status-pill">${window.current ? "Идет прием" : "Окно свободно"}</span>
                        </div>
                        <div class="top-gap">
                            ${
                                window.current
                                    ? `
                                        <strong>${escapeHtml(window.current.booking_code)}</strong>
                                        <small>${escapeHtml(window.current.student_name)}</small>
                                        <small>${escapeHtml(window.current.service_name)}</small>
                                    `
                                    : `<small>Ожидает следующего студента</small>`
                            }
                        </div>
                        <div class="top-gap">
                            ${
                                window.next.length
                                    ? window.next
                                          .map(
                                              (item) => `
                                                <div class="upcoming-item">
                                                    <strong>${escapeHtml(item.booking_code)}</strong>
                                                    <small>${formatTime(item.scheduled_start)} · ${escapeHtml(item.student_name)}</small>
                                                </div>
                                            `
                                          )
                                          .join("")
                                    : `<small>Следующих записей пока нет</small>`
                            }
                        </div>
                    </article>
                `
            )
            .join("") || `<div class="empty-state panel">Активных окон пока нет.</div>`;

    elements.upcomingBoard.innerHTML =
        state.board.upcoming
            .map(
                (item) => `
                    <article class="upcoming-item">
                        <strong>${escapeHtml(item.booking_code)}</strong>
                        <small>${formatDateTime(item.scheduled_start)}</small>
                        <small>${escapeHtml(item.service_name)} · ${escapeHtml(item.window_name)}</small>
                    </article>
                `
            )
            .join("") || `<div class="empty-state queue-item">Ближайших записей пока нет.</div>`;

    elements.boardUpdatedLabel.textContent = new Date().toLocaleTimeString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
    });
}

function renderUserState() {
    const user = state.user;
    const loggedIn = Boolean(user);
    elements.authSection.classList.toggle("hidden", loggedIn);
    elements.dashboardSection.classList.toggle("hidden", !loggedIn);

    if (!loggedIn) {
        elements.studentSection.classList.add("hidden");
        elements.operatorSection.classList.add("hidden");
        elements.adminSection.classList.add("hidden");
        return;
    }

    elements.userNameLabel.textContent = user.full_name;
    elements.userMetaLabel.textContent = `${user.role} · ${user.email}`;

    const isStudent = user.role === "STUDENT";
    const isOperator = user.role === "OPERATOR" || user.role === "ADMIN";
    const isAdmin = user.role === "ADMIN";

    elements.studentSection.classList.toggle("hidden", !isStudent);
    elements.operatorSection.classList.toggle("hidden", !isOperator);
    elements.adminSection.classList.toggle("hidden", !isAdmin);
}

function renderServices() {
    elements.serviceCards.innerHTML = state.services
        .map(
            (service) => `
                <button
                    type="button"
                    class="service-card ${service.id === state.selectedServiceId ? "active" : ""}"
                    data-service-id="${service.id}"
                    style="background: linear-gradient(160deg, ${service.color}1f, rgba(255,255,255,0.95));"
                >
                    <strong>${escapeHtml(service.name)}</strong>
                    <div class="muted">${escapeHtml(service.description)}</div>
                    <div class="top-gap"><small>${service.duration_minutes} минут</small></div>
                </button>
            `
        )
        .join("");
}

function renderAvailability() {
    if (!state.selectedServiceId || !state.availability) {
        elements.weekLabel.textContent = "Неделя";
        elements.availabilityGrid.innerHTML = `<div class="empty-state day-column">Выберите услугу, чтобы увидеть свободные слоты.</div>`;
        return;
    }

    elements.weekLabel.textContent = `Неделя с ${formatDate(state.availability.week_start)}`;
    elements.availabilityGrid.innerHTML = state.availability.days
        .map((day) => {
            const slots = day.slots.length
                ? `<div class="slot-list">${day.slots
                      .map(
                          (slot) => `
                            <button
                                type="button"
                                class="slot-card"
                                data-book-window="${slot.window_id}"
                                data-book-start="${slot.start}"
                            >
                                <strong>${formatTime(slot.start)} - ${formatTime(slot.end)}</strong>
                                <small>${escapeHtml(slot.window_name)}</small>
                            </button>
                        `
                      )
                      .join("")}</div>`
                : `<div class="empty-state queue-item">Свободных мест нет</div>`;

            return `
                <article class="day-column">
                    <h3>${weekdayMap[day.weekday]} · ${day.label}</h3>
                    ${slots}
                </article>
            `;
        })
        .join("");
}

function studentActionButtons(appointment) {
    const actions = [];
    if (appointment.status === "BOOKED") {
        actions.push(`<button class="mini-button" data-kind="neutral" data-action="checkin" data-id="${appointment.id}">Я пришел</button>`);
        actions.push(`<button class="mini-button" data-kind="danger" data-action="cancel" data-id="${appointment.id}">Отменить</button>`);
    }
    if (appointment.status === "CHECKED_IN") {
        actions.push(`<button class="mini-button" data-kind="danger" data-action="cancel" data-id="${appointment.id}">Отменить</button>`);
    }
    return actions.length ? `<div class="queue-actions">${actions.join("")}</div>` : "";
}

function renderStudentAppointments() {
    elements.studentAppointments.innerHTML =
        state.appointments
            .map(
                (appointment) => `
                    <article class="queue-item">
                        <strong>${escapeHtml(appointment.booking_code)} · ${escapeHtml(appointment.service.name)}</strong>
                        <small>${formatDateTime(appointment.scheduled_start)} · ${escapeHtml(appointment.window.name)}</small>
                        <div class="top-gap"><span class="status-pill">${appointment.status}</span></div>
                        ${appointment.notes ? `<div class="top-gap"><small>${escapeHtml(appointment.notes)}</small></div>` : ""}
                        ${studentActionButtons(appointment)}
                    </article>
                `
            )
            .join("") || `<div class="empty-state queue-item">Записей пока нет. Выберите услугу и свободный слот.</div>`;
}

function operatorItemActions(item) {
    const actions = [];
    if (item.status === "BOOKED") {
        actions.push(`<button class="mini-button" data-kind="success" data-op-action="checkin" data-id="${item.id}">Отметить приход</button>`);
    }
    actions.push(`<button class="mini-button" data-kind="danger" data-op-action="noshow" data-id="${item.id}">Неявка</button>`);
    return `<div class="queue-actions">${actions.join("")}</div>`;
}

function renderOperatorDashboard() {
    if (!state.operatorDashboard) {
        elements.operatorCurrentCard.innerHTML = "Нет данных";
        elements.operatorQueueList.innerHTML = "";
        return;
    }

    const current = state.operatorDashboard.current;
    elements.operatorCurrentCard.innerHTML = current
        ? `
            <strong>${escapeHtml(current.booking_code)}</strong>
            <div class="top-gap">${escapeHtml(current.student.full_name)}</div>
            <small>${escapeHtml(current.service.name)} · ${formatDateTime(current.scheduled_start)}</small>
            <div class="queue-actions">
                <button class="mini-button" data-kind="success" data-op-action="complete" data-id="${current.id}">Завершить</button>
                <button class="mini-button" data-kind="danger" data-op-action="noshow" data-id="${current.id}">Неявка</button>
            </div>
        `
        : "Нет активного вызова";

    elements.operatorQueueList.innerHTML =
        state.operatorDashboard.waiting
            .map(
                (item) => `
                    <article class="queue-item">
                        <strong>${escapeHtml(item.booking_code)} · ${escapeHtml(item.student.full_name)}</strong>
                        <small>${escapeHtml(item.service.name)} · ${formatDateTime(item.scheduled_start)}</small>
                        <div class="top-gap"><span class="status-pill">${item.status}</span></div>
                        ${operatorItemActions(item)}
                    </article>
                `
            )
            .join("") || `<div class="empty-state queue-item">Очередь по выбранному окну пуста.</div>`;
}

function fillRuleWindowOptions() {
    const windows = state.adminOverview?.windows || state.operatorWindows;
    if (!elements.ruleWindowSelect) {
        return;
    }
    elements.ruleWindowSelect.innerHTML = windows
        .map((window) => `<option value="${window.id}">${escapeHtml(window.name)}</option>`)
        .join("");
}

function renderAdminOverview() {
    if (!state.adminOverview) {
        return;
    }

    elements.adminServicesList.innerHTML =
        state.adminOverview.services
            .map(
                (service) => `
                    <article class="queue-item">
                        <strong>${escapeHtml(service.name)}</strong>
                        <small>${service.duration_minutes} минут · ${service.is_active ? "Активна" : "Отключена"}</small>
                        <div class="top-gap">${service.description ? escapeHtml(service.description) : "<small>Без описания</small>"}</div>
                        <div class="queue-actions">
                            <button class="mini-button" data-admin-edit="service" data-id="${service.id}">Редактировать</button>
                        </div>
                    </article>
                `
            )
            .join("");

    elements.adminWindowsList.innerHTML =
        state.adminOverview.windows
            .map(
                (window) => `
                    <article class="queue-item">
                        <strong>${escapeHtml(window.name)}</strong>
                        <small>${escapeHtml(window.location || "Локация не указана")}</small>
                        <div class="top-gap"><span class="status-pill">${window.is_active ? "Активно" : "Выключено"}</span></div>
                        <div class="queue-actions">
                            <button class="mini-button" data-admin-edit="window" data-id="${window.id}">Редактировать</button>
                        </div>
                    </article>
                `
            )
            .join("");

    elements.adminRulesList.innerHTML =
        state.adminOverview.rules
            .map(
                (rule) => `
                    <article class="queue-item">
                        <strong>${escapeHtml(rule.window_name)}</strong>
                        <small>${weekdayMap[rule.weekday]} · ${rule.start_time} - ${rule.end_time}</small>
                        <small>Шаг: ${rule.step_minutes} мин</small>
                        <div class="queue-actions">
                            <button class="mini-button" data-admin-edit="rule" data-id="${rule.id}">Редактировать</button>
                        </div>
                    </article>
                `
            )
            .join("");

    fillRuleWindowOptions();
}

async function loadBoard() {
    state.board = await api("/api/board");
    renderBoard();
}

async function loadServices() {
    const data = await api("/api/services");
    state.services = data.services;
    if (!state.selectedServiceId && state.services.length) {
        state.selectedServiceId = state.services[0].id;
    }
    renderServices();
}

async function loadStudentAvailability() {
    if (!state.selectedServiceId) {
        return;
    }
    state.availability = await api(`/api/student/availability?service_id=${state.selectedServiceId}&week_offset=${state.weekOffset}`);
    renderAvailability();
}

async function loadStudentAppointments() {
    const data = await api("/api/student/appointments");
    state.appointments = data.appointments;
    renderStudentAppointments();
}

async function loadOperatorWindows() {
    const data = await api("/api/operator/windows");
    state.operatorWindows = data.windows;
    if (!state.selectedWindowId && state.operatorWindows.length) {
        state.selectedWindowId = state.operatorWindows[0].id;
    }
    elements.operatorWindowSelect.innerHTML = state.operatorWindows
        .map((window) => `<option value="${window.id}">${escapeHtml(window.name)}</option>`)
        .join("");
    if (state.selectedWindowId) {
        elements.operatorWindowSelect.value = String(state.selectedWindowId);
    }
}

async function loadOperatorDashboard() {
    if (!state.selectedWindowId) {
        return;
    }
    state.operatorDashboard = await api(`/api/operator/dashboard?window_id=${state.selectedWindowId}`);
    renderOperatorDashboard();
}

async function loadAdminOverview() {
    state.adminOverview = await api("/api/admin/overview");
    renderAdminOverview();
}

async function loadSession() {
    try {
        const data = await api("/api/auth/me");
        state.user = data.user;
    } catch (error) {
        state.user = null;
    }
    renderUserState();
}

async function refreshDashboard() {
    if (!state.user) {
        return;
    }
    if (state.user.role === "STUDENT") {
        await loadServices();
        await loadStudentAvailability();
        await loadStudentAppointments();
    }
    if (state.user.role === "OPERATOR" || state.user.role === "ADMIN") {
        await loadOperatorWindows();
        await loadOperatorDashboard();
    }
    if (state.user.role === "ADMIN") {
        await loadServices();
        await loadAdminOverview();
    }
}

function resetForms() {
    document.getElementById("serviceForm").reset();
    document.getElementById("windowForm").reset();
    document.getElementById("ruleForm").reset();
    document.querySelector("#serviceForm input[name='id']").value = "";
    document.querySelector("#windowForm input[name='id']").value = "";
    document.querySelector("#ruleForm input[name='id']").value = "";
}

async function handleLogin(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
    });
    state.user = data.user;
    renderUserState();
    await refreshDashboard();
    showToast("Вход выполнен.");
}

async function handleRegister(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    const data = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
    });
    state.user = data.user;
    renderUserState();
    await loadServices();
    await loadStudentAvailability();
    await loadStudentAppointments();
    showToast("Аккаунт создан, вы уже в системе.");
}

async function handleLogout() {
    await api("/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
    state.user = null;
    state.availability = null;
    state.appointments = [];
    state.operatorDashboard = null;
    state.adminOverview = null;
    renderUserState();
    renderAvailability();
    renderStudentAppointments();
    showToast("Вы вышли из системы.");
}

async function bookSlot(windowId, scheduledStart) {
    await api("/api/student/appointments", {
        method: "POST",
        body: JSON.stringify({
            service_id: state.selectedServiceId,
            window_id: Number(windowId),
            scheduled_start: scheduledStart,
            notes: "",
        }),
    });
    await Promise.all([loadStudentAvailability(), loadStudentAppointments(), loadBoard()]);
    showToast("Запись подтверждена.");
}

async function studentAction(action, id) {
    if (action === "checkin") {
        await api(`/api/student/appointments/${id}/check-in`, {
            method: "POST",
            body: JSON.stringify({}),
        });
        showToast("Вы отмечены как пришедший.");
    }

    if (action === "cancel") {
        const note = window.prompt("Если хотите, добавьте причину отмены.", "") || "";
        await api(`/api/student/appointments/${id}/cancel`, {
            method: "POST",
            body: JSON.stringify({ note }),
        });
        showToast("Запись отменена.");
    }

    await Promise.all([loadStudentAvailability(), loadStudentAppointments(), loadBoard()]);
}

async function operatorAction(action, id = null) {
    if (action === "next") {
        await api(`/api/operator/windows/${state.selectedWindowId}/next`, {
            method: "POST",
            body: JSON.stringify({}),
        });
        showToast("Следующий студент вызван.");
    }

    if (action === "complete") {
        const note = window.prompt("Комментарий к завершению приема", "") || "";
        await api(`/api/operator/appointments/${id}/complete`, {
            method: "POST",
            body: JSON.stringify({ note }),
        });
        showToast("Прием завершен.");
    }

    if (action === "noshow") {
        const note = window.prompt("Комментарий к неявке", "") || "";
        await api(`/api/operator/appointments/${id}/no-show`, {
            method: "POST",
            body: JSON.stringify({ note }),
        });
        showToast("Неявка отмечена.");
    }

    if (action === "checkin") {
        await api(`/api/operator/appointments/${id}/check-in`, {
            method: "POST",
            body: JSON.stringify({}),
        });
        showToast("Студент отмечен как пришедший.");
    }

    await Promise.all([loadOperatorDashboard(), loadBoard()]);
}

function fillServiceForm(service) {
    const form = document.getElementById("serviceForm");
    field(form, "name").value = service.name;
    field(form, "description").value = service.description;
    field(form, "duration_minutes").value = service.duration_minutes;
    field(form, "color").value = service.color;
    field(form, "is_active").checked = service.is_active;
    field(form, "id").value = service.id;
}

function fillWindowForm(windowItem) {
    const form = document.getElementById("windowForm");
    field(form, "name").value = windowItem.name;
    field(form, "location").value = windowItem.location;
    field(form, "is_active").checked = windowItem.is_active;
    field(form, "id").value = windowItem.id;
}

function fillRuleForm(rule) {
    const form = document.getElementById("ruleForm");
    field(form, "window_id").value = rule.window_id;
    field(form, "weekday").value = rule.weekday;
    field(form, "start_time").value = rule.start_time;
    field(form, "end_time").value = rule.end_time;
    field(form, "step_minutes").value = rule.step_minutes;
    field(form, "is_active").checked = rule.is_active;
    field(form, "id").value = rule.id;
}

async function submitServiceForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        name: field(form, "name").value,
        description: field(form, "description").value,
        duration_minutes: Number(field(form, "duration_minutes").value),
        color: field(form, "color").value,
        is_active: field(form, "is_active").checked,
    };
    const id = field(form, "id").value;
    await api(id ? `/api/admin/services/${id}` : "/api/admin/services", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    showToast(id ? "Услуга обновлена." : "Услуга создана.");
    form.reset();
    field(form, "id").value = "";
    await Promise.all([loadServices(), loadAdminOverview()]);
}

async function submitWindowForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        name: field(form, "name").value,
        location: field(form, "location").value,
        is_active: field(form, "is_active").checked,
    };
    const id = field(form, "id").value;
    await api(id ? `/api/admin/windows/${id}` : "/api/admin/windows", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    showToast(id ? "Окно обновлено." : "Окно создано.");
    form.reset();
    field(form, "id").value = "";
    await Promise.all([loadOperatorWindows(), loadAdminOverview()]);
}

async function submitRuleForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        window_id: Number(field(form, "window_id").value),
        weekday: Number(field(form, "weekday").value),
        start_time: field(form, "start_time").value,
        end_time: field(form, "end_time").value,
        step_minutes: Number(field(form, "step_minutes").value),
        is_active: field(form, "is_active").checked,
    };
    const id = field(form, "id").value;
    await api(id ? `/api/admin/rules/${id}` : "/api/admin/rules", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    showToast(id ? "Расписание обновлено." : "Правило расписания создано.");
    form.reset();
    field(form, "id").value = "";
    await loadAdminOverview();
}

function installEvents() {
    document.getElementById("loginForm").addEventListener("submit", (event) =>
        handleLogin(event).catch((error) => showToast(error.message, true))
    );

    document.getElementById("registerForm").addEventListener("submit", (event) =>
        handleRegister(event).catch((error) => showToast(error.message, true))
    );

    document.getElementById("logoutBtn").addEventListener("click", () =>
        handleLogout().catch((error) => showToast(error.message, true))
    );

    document.getElementById("refreshBoardBtn").addEventListener("click", () =>
        loadBoard().catch((error) => showToast(error.message, true))
    );

    document.getElementById("refreshDashboardBtn").addEventListener("click", () =>
        refreshDashboard().catch((error) => showToast(error.message, true))
    );

    document.getElementById("weekPrevBtn").addEventListener("click", async () => {
        state.weekOffset = Math.max(0, state.weekOffset - 1);
        try {
            await loadStudentAvailability();
        } catch (error) {
            showToast(error.message, true);
        }
    });

    document.getElementById("weekNextBtn").addEventListener("click", async () => {
        state.weekOffset = Math.min(8, state.weekOffset + 1);
        try {
            await loadStudentAvailability();
        } catch (error) {
            showToast(error.message, true);
        }
    });

    elements.serviceCards.addEventListener("click", async (event) => {
        const card = event.target.closest("[data-service-id]");
        if (!card) {
            return;
        }
        state.selectedServiceId = Number(card.dataset.serviceId);
        renderServices();
        try {
            await loadStudentAvailability();
        } catch (error) {
            showToast(error.message, true);
        }
    });

    elements.availabilityGrid.addEventListener("click", (event) => {
        const card = event.target.closest("[data-book-window]");
        if (!card) {
            return;
        }
        bookSlot(card.dataset.bookWindow, card.dataset.bookStart).catch((error) => showToast(error.message, true));
    });

    elements.studentAppointments.addEventListener("click", (event) => {
        const button = event.target.closest("[data-action]");
        if (!button) {
            return;
        }
        studentAction(button.dataset.action, button.dataset.id).catch((error) => showToast(error.message, true));
    });

    elements.operatorWindowSelect.addEventListener("change", async (event) => {
        state.selectedWindowId = Number(event.target.value);
        try {
            await loadOperatorDashboard();
        } catch (error) {
            showToast(error.message, true);
        }
    });

    document.getElementById("nextAppointmentBtn").addEventListener("click", () =>
        operatorAction("next").catch((error) => showToast(error.message, true))
    );

    elements.operatorCurrentCard.addEventListener("click", (event) => {
        const button = event.target.closest("[data-op-action]");
        if (!button) {
            return;
        }
        operatorAction(button.dataset.opAction, button.dataset.id).catch((error) => showToast(error.message, true));
    });

    elements.operatorQueueList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-op-action]");
        if (!button) {
            return;
        }
        operatorAction(button.dataset.opAction, button.dataset.id).catch((error) => showToast(error.message, true));
    });

    document.getElementById("serviceForm").addEventListener("submit", (event) =>
        submitServiceForm(event).catch((error) => showToast(error.message, true))
    );

    document.getElementById("windowForm").addEventListener("submit", (event) =>
        submitWindowForm(event).catch((error) => showToast(error.message, true))
    );

    document.getElementById("ruleForm").addEventListener("submit", (event) =>
        submitRuleForm(event).catch((error) => showToast(error.message, true))
    );

    elements.adminServicesList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-admin-edit='service']");
        if (!button) {
            return;
        }
        const service = state.adminOverview.services.find((item) => item.id === Number(button.dataset.id));
        if (service) {
            fillServiceForm(service);
        }
    });

    elements.adminWindowsList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-admin-edit='window']");
        if (!button) {
            return;
        }
        const windowItem = state.adminOverview.windows.find((item) => item.id === Number(button.dataset.id));
        if (windowItem) {
            fillWindowForm(windowItem);
        }
    });

    elements.adminRulesList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-admin-edit='rule']");
        if (!button) {
            return;
        }
        const rule = state.adminOverview.rules.find((item) => item.id === Number(button.dataset.id));
        if (rule) {
            fillRuleForm(rule);
        }
    });
}

async function bootstrap() {
    installEvents();
    resetForms();
    await loadBoard();
    await loadServices();
    await loadSession();
    if (state.user) {
        await refreshDashboard();
    } else {
        renderAvailability();
        renderStudentAppointments();
    }

    window.setInterval(() => {
        loadBoard().catch(() => null);
        if (state.user?.role === "STUDENT") {
            loadStudentAppointments().catch(() => null);
        }
        if (state.user?.role === "OPERATOR" || state.user?.role === "ADMIN") {
            loadOperatorDashboard().catch(() => null);
        }
    }, 20000);
}

bootstrap().catch((error) => showToast(error.message, true));
