// static/app.js

// ========== AUTH & APP SHELL ==========

// Simple helper: API fetch with auth header and redirect on 401/403
async function apiFetch(url, options = {}) {
  const token = localStorage.getItem("access_token");

  const headers = options.headers || {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  options.headers = headers;

  const res = await fetch(url, options);

  // Auth guard: if unauthorized, force login
  if (res.status === 401 || res.status === 403) {
    console.warn("User is not authenticated. Redirecting to login...");
    localStorage.removeItem("access_token");
    showAuthSection();
  }

  return res;
}

// Show login/signup, hide main app
function showAuthSection() {
  const authSection = document.getElementById("auth-section");
  const mainSection = document.getElementById("main-section");
  const headerRight = document.getElementById("header-right");
  const welcomeLabel = document.getElementById("welcome-label");

  if (authSection) authSection.style.display = "flex";
  if (mainSection) mainSection.style.display = "none";
  if (headerRight) headerRight.style.display = "none";
  if (welcomeLabel) welcomeLabel.textContent = "";
}

// Show main app, hide auth
function showMainSection(username) {
  const authSection = document.getElementById("auth-section");
  const mainSection = document.getElementById("main-section");
  const headerRight = document.getElementById("header-right");
  const welcomeLabel = document.getElementById("welcome-label");

  if (authSection) authSection.style.display = "none";
  if (mainSection) mainSection.style.display = "block";
  if (headerRight) headerRight.style.display = "flex";
  if (welcomeLabel && username) {
    welcomeLabel.textContent = `Signed in as ${username}`;
  }
}

// ========== INITIAL LOAD ==========

window.onload = () => {
  setupAuthTabs();
  setupAuthHandlers();
  setupLogoutHandler();
  setupSectorAnalyticsButton();

  const token = localStorage.getItem("access_token");
  const username = localStorage.getItem("username");

  if (!token) {
    showAuthSection();
  } else {
    showMainSection(username || "");
    loadCompaniesAndDashboard();
  }
};

// ========== AUTH UI TABS (Login / Signup) ==========

function setupAuthTabs() {
  const tabs = document.querySelectorAll(".auth-tab");
  const loginPanel = document.getElementById("login-box");
  const registerPanel = document.getElementById("register-box");

  if (!tabs || !loginPanel || !registerPanel) return;

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("auth-tab-active"));
      tab.classList.add("auth-tab-active");

      const target = tab.dataset.tab;
      if (target === "login") {
        loginPanel.classList.add("auth-panel-active");
        registerPanel.classList.remove("auth-panel-active");
      } else {
        registerPanel.classList.add("auth-panel-active");
        loginPanel.classList.remove("auth-panel-active");
      }
    });
  });
}

// ========== AUTH HANDLERS (Login / Signup) ==========

function setupAuthHandlers() {
  const btnLogin = document.getElementById("btn-login");
  const btnRegister = document.getElementById("btn-register");

  if (btnLogin) {
    btnLogin.onclick = handleLogin;
  }
  if (btnRegister) {
    btnRegister.onclick = handleRegister;
  }
}

async function handleLogin() {
  const u = document.getElementById("login-username").value.trim();
  const p = document.getElementById("login-password").value.trim();
  const msg = document.getElementById("login-msg");
  if (msg) {
    msg.style.color = "";
    msg.textContent = "";
  }

  if (!u || !p) {
    if (msg) msg.textContent = "Username and password are required.";
    return;
  }

  const body = new URLSearchParams();
  body.append("username", u);
  body.append("password", p);

  const res = await fetch("/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (res.ok) {
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("username", u);
    showMainSection(u);
    loadCompaniesAndDashboard();
  } else {
    const data = await res.json().catch(() => ({}));
    if (msg) {
      msg.style.color = "";
      msg.textContent = data.detail || "Login failed.";
    }
  }
}

async function handleRegister() {
  const email = document.getElementById("reg-email").value.trim();
  const u = document.getElementById("reg-username").value.trim();
  const p = document.getElementById("reg-password").value.trim();
  const msg = document.getElementById("reg-msg");
  if (msg) {
    msg.style.color = "";
    msg.textContent = "";
  }

  if (!email || !u || !p) {
    if (msg) msg.textContent = "Email, username and password are required.";
    return;
  }

  const res = await apiFetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, username: u, password: p }),
  });

  if (res.ok) {
    if (msg) {
      msg.style.color = "#16a34a";
      msg.textContent = "Account created. Please check your email to verify.";
    }
  } else {
    const data = await res.json().catch(() => ({}));
    if (msg) {
      msg.style.color = "";
      msg.textContent = data.detail || "Registration failed.";
    }
  }
}

// ========== LOGOUT ==========

function setupLogoutHandler() {
  const btnLogout = document.getElementById("btn-logout");
  if (!btnLogout) return;

  btnLogout.onclick = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("username");
    showAuthSection();
  };
}

// ========== COMPANIES & DASHBOARD ==========

async function loadCompaniesAndDashboard() {
  await Promise.all([loadCompanies(), loadDashboard()]);
  loadSectorAnalytics(); // auto-refresh sector analytics when data changes
}

// ----- Companies list -----

async function loadCompanies() {
  const listDiv = document.getElementById("company-list");
  const addMsg = document.getElementById("add-msg");
  const addBtn = document.getElementById("btn-add-company");

  if (!listDiv) return;

  // --- Wire up ADD COMPANY button (only once) ---
  if (addBtn && !addBtn.dataset.bound) {
    addBtn.dataset.bound = "1"; // prevent multiple bindings

    addBtn.addEventListener("click", async () => {
      const name = document.getElementById("new-name").value.trim();
      const ticker = document.getElementById("new-ticker").value.trim();
      const segment = document.getElementById("new-segment").value.trim();

      if (addMsg) {
        addMsg.style.color = "";
        addMsg.textContent = "";
      }

      if (!name || !ticker || !segment) {
        if (addMsg) {
          addMsg.style.color = "red";
          addMsg.textContent = "Please fill all fields (name, ticker, segment).";
        }
        return;
      }

      const res = await apiFetch("/companies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, ticker, segment }),
      });

      if (res.ok) {
        if (addMsg) {
          addMsg.style.color = "green";
          addMsg.textContent = "Company added.";
        }
        document.getElementById("new-name").value = "";
        document.getElementById("new-ticker").value = "";
        document.getElementById("new-segment").value = "";

        await loadCompaniesAndDashboard(); // refresh list + dashboard
      } else {
        const data = await res.json().catch(() => ({}));
        if (addMsg) {
          addMsg.style.color = "red";
          addMsg.textContent = data.detail || "Failed to add company.";
        }
      }
    });
  }

  // --- LOAD EXISTING COMPANIES & RENDER DELETE BUTTONS ---
  listDiv.innerHTML = "Loading companies...";

  const res = await apiFetch("/companies");
  if (!res.ok) {
    listDiv.textContent = "Error loading companies.";
    return;
  }

  const data = await res.json();

  if (!Array.isArray(data) || data.length === 0) {
    listDiv.textContent = "No companies added yet.";
    return;
  }

  const ul = document.createElement("ul");
  ul.style.listStyle = "none";
  ul.style.padding = "0";

  data.forEach((c) => {
    const li = document.createElement("li");
    li.style.display = "flex";
    li.style.justifyContent = "space-between";
    li.style.alignItems = "center";
    li.style.marginBottom = "8px";

    li.innerHTML = `
      <span>${c.name} (${c.ticker}) – ${c.segment}</span>
      <button class="btn btn-sm btn-outline" data-id="${c.id}">Delete</button>
    `;
    ul.appendChild(li);
  });

  listDiv.innerHTML = "";
  listDiv.appendChild(ul);

  // Attach DELETE handlers
  ul.querySelectorAll("button[data-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      if (!id) return;

      const confirmDelete = confirm("Are you sure you want to delete this company?");
      if (!confirmDelete) return;

      const resp = await apiFetch(`/companies/${id}`, { method: "DELETE" });
      if (resp.ok) {
        await loadCompaniesAndDashboard(); // refresh after delete
      } else {
        alert("Failed to delete company.");
      }
    });
  });
}


// ----- Add company -----


// ----- Dashboard table -----
function buildDashboardTable(companies) {
  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  thead.innerHTML = `
    <tr>
      <th>Name</th>
      <th>Ticker</th>
      <th>Segment</th>
      <th>Price</th>
      <th>Revenue</th>
      <th>Net Margin</th>
      <th>ROE</th>
      <th>Debt/Equity</th>
      <th>1Y Return</th>
      <th>P/E</th>
      <th>P/B</th>
      <th>EV/EBITDA</th>
    </tr>
  `;
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  companies.forEach((c) => {
    const tr = document.createElement("tr");
    tr.dataset.id = c.id;
    tr.innerHTML = `
      <td>${c.name}</td>
      <td>${c.ticker}</td>
      <td>${c.segment}</td>
      <td>${formatNumber(c.price)}</td>
      <td>${formatNumber(c.revenue)}</td>
      <td>${formatPercent(c.net_margin)}</td>
      <td>${formatPercent(c.roe)}</td>
      <td>${formatNumber(c.debt_to_equity)}</td>
      <td>${formatPercent(c.one_year_return)}</td>
      <td>${formatNumber(c.pe)}</td>
      <td>${formatNumber(c.pb)}</td>
      <td>${formatNumber(c.ev_to_ebitda)}</td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  // Row click => detail + analytics
  tbody.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => {
      const id = row.dataset.id;
      if (id) loadCompanyDetail(id);
    });
  });

  return table;
}

async function loadDashboard() {
  const container = document.getElementById("dashboard-table");
  if (!container) return;

  container.innerHTML = "Loading dashboard...";

  const res = await apiFetch("/dashboard");
  if (!res.ok) {
    container.textContent = "Error loading dashboard.";
    return;
  }

  const data = await res.json();
  const companies = data.companies || [];

  if (companies.length === 0) {
    container.textContent = "No companies available.";
    return;
  }

  // Group by segment
  const bySegment = {};
  companies.forEach((c) => {
    const seg = c.segment || "Unclassified";
    if (!bySegment[seg]) bySegment[seg] = [];
    bySegment[seg].push(c);
  });

  container.innerHTML = "";

  Object.keys(bySegment)
    .sort()
    .forEach((segment) => {
      const segTitle = document.createElement("h3");
      segTitle.textContent = segment;
      container.appendChild(segTitle);

      const table = buildDashboardTable(bySegment[segment]);
      container.appendChild(table);
    });
}


// Helpers for formatting numbers/percentages
function formatNumber(x) {
  if (x === null || x === undefined) return "-";
  const n = Number(x);
  if (Number.isNaN(n)) return "-";
  if (Math.abs(n) >= 1_000_000_000) {
    return (n / 1_000_000_000).toFixed(2) + "B";
  }
  if (Math.abs(n) >= 1_000_000) {
    return (n / 1_000_000).toFixed(2) + "M";
  }
  if (Math.abs(n) >= 1_000) {
    return (n / 1_000).toFixed(2) + "K";
  }
  return n.toFixed(2);
}

function formatPercent(x) {
  if (x === null || x === undefined) return "-";
  const n = Number(x);
  if (Number.isNaN(n)) return "-";
  return (n * 100).toFixed(1) + "%";
}

// ========== COMPANY DETAIL & ANALYTICS ==========

async function loadCompanyDetail(id) {
  const container = document.getElementById("detail-content");
  if (!container) return;

  container.innerHTML = "Loading company detail...";

  const res = await apiFetch(`/companies/${id}/detail`);
  if (!res.ok) {
    container.textContent = "Error loading detail.";
    return;
  }

  const data = await res.json();

  const info = data.info || {};
  const ratios = data.ratios || {};
  const income = data.income_statement;
  const balance = data.balance_sheet;
  const cash = data.cash_flow;

  const detailDiv = document.createElement("div");

  // Info section
  const infoKeys = Object.keys(info);
  if (infoKeys.length > 0) {
    const infoSection = document.createElement("div");
    const h3 = document.createElement("h3");
    h3.textContent = "Snapshot";
    infoSection.appendChild(h3);

    const ul = document.createElement("ul");
    ul.style.listStyle = "none";
    ul.style.padding = "0";
    infoKeys.slice(0, 10).forEach((key) => {
     
      const tr = document.createElement("tr");
      const td1 = document.createElement("td");
      const td2 = document.createElement("td");
      td1.textContent = key.toUpperCase();
      td2.textContent = `${info[key]}`;
      tr.appendChild(td1);
      tr.appendChild(td2);
       ul.appendChild(tr);
      
    });
    infoSection.appendChild(ul);
    detailDiv.appendChild(infoSection);
  }

  // Ratios section
  const ratiosSection = document.createElement("div");
  const h3r = document.createElement("h3");
  h3r.textContent = "Key Ratios";
  ratiosSection.appendChild(h3r);

  const rTable = document.createElement("table");
  rTable.className = "data-table";
  const rBody = document.createElement("tbody");
  [
    ["Price", ratios.price],
    ["Revenue", ratios.revenue],
    ["Net Income", ratios.net_income],
    ["Net Margin", ratios.net_margin, true],
    ["ROE", ratios.roe, true],
    ["Debt/Equity", ratios.debt_to_equity],
    ["Current Ratio", ratios.current_ratio],
    ["1Y Return", ratios.one_year_return, true],
  ].forEach(([label, val, isPct]) => {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    const td2 = document.createElement("td");
    td1.textContent = label;
    td2.textContent = isPct ? formatPercent(val) : formatNumber(val);
    tr.appendChild(td1);
    tr.appendChild(td2);
    rBody.appendChild(tr);
  });
  rTable.appendChild(rBody);
  ratiosSection.appendChild(rTable);
  detailDiv.appendChild(ratiosSection);

  // Statements
  if (income) {
    detailDiv.appendChild(renderStatement("Income Statement (last 3 periods)", income));
  }
  if (balance) {
    detailDiv.appendChild(renderStatement("Balance Sheet (last 3 periods)", balance));
  }
  if (cash) {
    detailDiv.appendChild(renderStatement("Cash Flow (last 3 periods)", cash));
  }

  container.innerHTML = "";
  container.appendChild(detailDiv);

  // Load company-specific Gemini analytics
  loadCompanyAnalytics(id);
}

function renderStatement(title, stmt) {
  const section = document.createElement("div");
  const h3 = document.createElement("h3");
  h3.textContent = title;
  section.appendChild(h3);

  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headRow.innerHTML = `<th>Item</th>${stmt.columns
    .map((c) => `<th>${c}</th>`)
    .join("")}`;
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (let i = 0; i < stmt.index.length; i++) {
    const row = document.createElement("tr");
    const label = stmt.index[i];
    const vals = stmt.data[i] || [];
    row.innerHTML =
      `<td>${label}</td>` +
      vals
        .map((v) =>
          v === null || v === undefined
            ? "<td>-</td>"
            : `<td>${typeof v === "number" ? formatNumber(v) : v}</td>`
        )
        .join("");
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  section.appendChild(table);
  return section;
}

// ========== SECTOR & COMPANY ANALYTICS (GEMINI) ==========

function setupSectorAnalyticsButton() {
  const btnSector = document.getElementById("btn-refresh-sector-analytics");
  if (!btnSector) return;
  btnSector.onclick = () => loadSectorAnalytics();
}

async function loadSectorAnalytics() {
  const container = document.getElementById("sector-analytics-text");
  if (!container) return;

  container.textContent = "Generating sector insights (via Gemini)...";

  const res = await apiFetch("/analytics/sector");
  if (!res.ok) {
    container.textContent = "Error generating sector insights.";
    return;
  }

  const data = await res.json().catch(() => ({}));
  container.textContent = data.text || "No analysis generated.";
}

async function loadCompanyAnalytics(id) {
  const container = document.getElementById("company-analytics-text");
  if (!container) return;

  container.textContent = "Generating company insights (via Gemini)...";

  const res = await apiFetch(`/analytics/company/${id}`);
  if (!res.ok) {
    container.textContent = "Error generating company insights.";
    return;
  }

  const data = await res.json().catch(() => ({}));
  container.textContent = data.text || "No analysis generated.";
}
