const state = {
  user: null,
  ready: false,
  contexts: { pf: true, pj: false },
  context: "pf",
  view: "capa",
  month: currentMonth(),
  calendarMonth: currentMonth(),
  summary: null,
  calendar: null,
  accounts: [],
  categories: [],
  transactions: [],
  loans: [],
  goals: [],
  company: null,
  users: [],
  filter: {},
};

const titles = {
  capa: "Capa",
  contas: "Contas bancárias",
  lancamentos: "Lançamentos",
  investimentos: "Investimentos",
  tipos: "Tipo de lançamento",
  emprestimos: "Empréstimos",
  metas: "Metas",
  simulacao: "Simulação",
  empresa: "Empresa",
  usuarios: "Acesso",
};

const ledes = {
  capa: "O que entrou, saiu e foi investido neste mês.",
  contas: "A conta é um nome livre: banco, carteira, cofre ou pessoa.",
  lancamentos: "Entrada, saída, investimento ou transferência entre contas suas.",
  investimentos: "O que saiu da conta para investir neste mês. Não é cotação e não soma o que já estava investido.",
  tipos: "Você nomeia os tipos. Subtipo é opcional.",
  emprestimos: "Price ou SAC. Cada parcela vira uma saída no mês.",
  metas: "O quanto você guardou é informado na mão. O sistema não deduz sozinho.",
  simulacao: "Uma parcela a mais neste mês, sem gravar nada.",
  empresa: "Acompanha o teto do MEI e o DAS. Não emite guia nem declaração.",
  usuarios: "Você administra o espaço e cria os demais acessos.",
};

const app = document.querySelector("#app");
boot();

async function boot() {
  const session = await api("/api/session");
  state.ready = session.ready;
  state.user = session.user;
  state.contexts = session.contexts || state.contexts;
  if (state.user) {
    state.context = preferredContext();
    await refresh();
  }
  render();
}

function preferredContext() {
  const preferred = state.user && state.user.last_context;
  if (preferred && state.contexts[preferred]) return preferred;
  return state.contexts.pf ? "pf" : "pj";
}

async function rememberContext() {
  const context = state.context;
  state.user = await api("/api/context", { method: "PUT", body: JSON.stringify({ context }) });
}

async function refresh() {
  const query = `context=${state.context}&month=${state.month}`;
  const jobs = [
    api(`/api/summary?${query}`),
    api(`/api/accounts?context=${state.context}`),
    api(`/api/categories?context=${state.context}`),
    api(`/api/transactions?${query}`),
    api(`/api/loans?context=${state.context}`),
    api(`/api/goals?context=${state.context}`),
  ];
  if (state.context === "pj") jobs.push(api(`/api/company?year=${state.month.slice(0, 4)}`));
  if (state.user.role === "admin") jobs.push(api("/api/users"));
  const [summary, accounts, categories, transactions, loans, goals, extra, users] = await Promise.all(jobs);
  state.summary = summary;
  state.accounts = accounts;
  state.categories = categories;
  state.transactions = transactions;
  state.loans = loans;
  state.goals = goals;
  state.company = state.context === "pj" ? extra : null;
  state.users = state.user.role === "admin" ? (state.context === "pj" ? users : extra) : [];
  state.calendar = state.calendarMonth === state.month
    ? state.summary
    : await api(`/api/summary?context=${state.context}&month=${state.calendarMonth}`);
}

function render() {
  if (!state.ready) { document.documentElement.dataset.context = "pf"; return renderAuth("Criar administrador", "/api/setup", "Criar"); }
  if (!state.user) { document.documentElement.dataset.context = "pf"; return renderAuth("Entrar", "/api/login", "Entrar"); }
  document.documentElement.dataset.context = state.context;
  const nav = [
    ["capa", "Capa"],
    ["lancamentos", "Lançamentos"],
    ["investimentos", "Investimentos"],
    ["emprestimos", "Empréstimos"],
    ["metas", "Metas"],
    ["simulacao", "Simulação"],
    ["tipos", "Tipo de lançamento"],
    ["contas", "Contas bancárias"],
  ];
  if (state.context === "pj") nav.push(["empresa", "Empresa"]);
  if (state.user.role === "admin") nav.push(["usuarios", "Acesso"]);
  app.innerHTML = `
    <div class="app">
      <aside class="sidebar">
        <div class="brand"><span class="mark">F</span><div><strong>Finances</strong><small>${escapeHtml(state.user.name)}</small></div></div>
        ${state.contexts.pf && state.contexts.pj ? `<div class="switch">
          <button type="button" data-context="pf" class="${state.context === "pf" ? "active" : ""}">Pessoa física</button>
          <button type="button" data-context="pj" class="${state.context === "pj" ? "active" : ""}">Pessoa jurídica</button>
        </div>` : ""}
        <nav class="nav">${nav.map(([id, label]) => `<button type="button" data-view="${id}" class="${state.view === id ? "active" : ""}">${label}</button>`).join("")}</nav>
        <button type="button" id="logout" class="ghost">Sair</button>
      </aside>
      <main>
        <div class="stage">
          <header class="top">
            <div>
              ${state.view === "capa" ? "" : `<p class="where">${state.context === "pj" ? "Lançando em pessoa jurídica" : "Lançando em pessoa física"}</p>`}
              <h1>${titles[state.view]}</h1>
              <p class="lede">${ledes[state.view]}</p>
            </div>
            <div class="row">
              <div class="month">
                <button type="button" id="prev" class="icon" aria-label="Mês anterior">‹</button>
                <strong>${escapeHtml(monthLabel(state.month))}</strong>
                <button type="button" id="next" class="icon" aria-label="Próximo mês">›</button>
              </div>
              <button type="button" id="create" class="primary">${createLabel()}</button>
            </div>
          </header>
          <section id="view"></section>
        </div>
      </main>
    </div>
    <dialog id="modal"></dialog>`;
  document.querySelector("#view").innerHTML = views[state.view]();
  document.querySelectorAll("[data-view]").forEach((button) => button.onclick = () => { state.view = button.dataset.view; state.filter = {}; render(); });
  document.querySelectorAll(".switch [data-context]").forEach((button) => button.onclick = (event) => switchContext(event, button.dataset.context));
  document.querySelector("#logout").onclick = async () => { await api("/api/logout", { method: "POST", body: "{}" }); state.user = null; render(); };
  document.querySelector("#prev").onclick = () => shiftMonth(-1);
  document.querySelector("#next").onclick = () => shiftMonth(1);
  const create = document.querySelector("#create");
  create.hidden = state.view === "simulacao" || state.view === "empresa";
  create.onclick = () => openCreate();
  bindView();
}

let contextSwitch = false;

async function switchContext(event, next) {
  if (event) event.stopPropagation();
  if (!next || next === state.context || contextSwitch) return;
  const previous = state.context;
  const previousView = state.view;
  state.context = next;
  if (state.view === "empresa" && state.context !== "pj") state.view = "capa";
  document.documentElement.dataset.context = state.context;
  contextSwitch = true;
  try {
    try {
      await rememberContext();
    } catch (error) {
      state.context = previous;
      state.view = previousView;
      document.documentElement.dataset.context = state.context;
      await notice(error.message);
      return;
    }
    try {
      await refresh();
    } catch (error) {
      await notice(error.message);
    }
    render();
  } finally {
    contextSwitch = false;
  }
}

const views = { capa: renderCapa, contas: renderContas, lancamentos: renderLancamentos, investimentos: renderInvestimentos, tipos: renderTipos, emprestimos: renderEmprestimos, metas: renderMetas, simulacao: renderSimulacao, empresa: renderEmpresa, usuarios: renderUsuarios };

function renderCapa() {
  const summary = state.summary;
  const generated = summary.saldo > 0
    ? `Este mês gerou um saldo de <span class="nowrap">${money(summary.saldo)}</span>.`
    : summary.saldo < 0
      ? `Este mês gerou um déficit de <span class="nowrap">${money(Math.abs(summary.saldo))}</span>.`
      : "Este mês ficou zerado.";
  const carried = summary.opening ? ` Veio do mês anterior <span class="nowrap">${money(summary.opening)}</span>.` : "";
  const crossed = summary.zero_day && summary.opening >= 0 ? ` Fica negativo em ${formatDate(summary.zero_day)}.` : "";
  const tone = balanceTone(summary.last_balance);
  return `
    <div class="bento">
      <button type="button" class="card hero" data-card="saldo">
        <span>${summary.last_balance < 0 ? "Déficit" : "Saldo"}</span>
        <strong class="${tone}">${money(summary.last_balance)}</strong>
        <em>${generated}${carried}${crossed}</em>
      </button>
      ${metric("Entradas", summary.entrada, "positive", "entrada")}
      ${metric("Saídas", summary.saida, "negative", "saida")}
      ${metric("Investimentos", summary.investimento, "", "investimento")}
      <button type="button" class="card pending" data-card="pendente">
        <span>Pendências</span>
        <div class="split">
          <div><small>A receber</small><strong class="positive">${money(summary.pending.entrada)}</strong></div>
          <div><small>A pagar</small><strong class="negative">${money(summary.pending.saida)}</strong></div>
          <div><small>A investir</small><strong>${money(summary.pending.investimento)}</strong></div>
        </div>
      </button>
    </div>
    <article class="panel">
      <div class="panel-head">
        <div><h2>Dia a dia</h2><p class="tag hint">Dia quieto mostra só o saldo. Dia com movimento ganha destaque.</p></div>
        <div class="month">
          <button type="button" id="cal-prev" class="icon" aria-label="Mês anterior do calendário">‹</button>
          <strong>${escapeHtml(monthLabel(state.calendarMonth))}</strong>
          <button type="button" id="cal-next" class="icon" aria-label="Próximo mês do calendário">›</button>
        </div>
      </div>
      ${renderMonth((state.calendar || summary).days)}
    </article>`;
}

function renderMonth(days) {
  const first = new Date(`${days[0].date}T12:00:00`);
  const lead = (first.getDay() + 6) % 7;
  const blanks = Array.from({ length: lead }, () => `<div class="cell blank"></div>`).join("");
  const cells = days.map((day) => {
    const moved = day.entrada || day.saida || day.investimento;
    const bits = [];
    if (day.entrada) bits.push(`+${money(day.entrada)}`);
    if (day.saida) bits.push(`−${money(day.saida)}`);
    if (day.investimento) bits.push(money(day.investimento));
    return `<button type="button" class="cell ${balanceTone(day.balance)}${moved ? " busy" : ""}" data-day="${day.date}">
      <span class="num">${day.date.slice(8)}</span>
      ${moved ? `<em>${bits.join(" ")}</em>` : ""}
      <span class="bal ${balanceTone(day.balance)}">${money(day.balance)}</span>
    </button>`;
  }).join("");
  return `<div class="cal"><div class="week">${["seg", "ter", "qua", "qui", "sex", "sáb", "dom"].map((day) => `<span>${day}</span>`).join("")}</div><div class="cal-grid">${blanks}${cells}</div></div>${renderDayList(days)}`;
}

function renderDayList(days) {
  const groups = [];
  for (const day of days) {
    const moved = Boolean(day.entrada || day.saida || day.investimento);
    const last = groups[groups.length - 1];
    if (!moved && last && !last.moved && last.balance === day.balance) last.end = day;
    else groups.push({ start: day, end: day, moved, balance: day.balance });
  }
  return `<div class="day-list">${groups.map((group) => {
    const same = group.start.date === group.end.date;
    const label = same ? group.start.date.slice(8) : `${group.start.date.slice(8)} a ${group.end.date.slice(8)}`;
    const detail = group.moved ? movementBits(group.start) : "Sem movimento";
    const tone = balanceTone(group.balance);
    const body = `<span class="when">${label}</span><span class="tag">${detail}</span><strong class="${tone}">${money(group.balance)}</strong>`;
    return same
      ? `<button type="button" class="dayline ${tone}${group.moved ? " busy" : ""}" data-day="${group.start.date}">${body}</button>`
      : `<div class="dayline ${tone}">${body}</div>`;
  }).join("")}</div>`;
}

function movementBits(day) {
  const bits = [];
  if (day.entrada) bits.push(`entrou ${money(day.entrada)}`);
  if (day.saida) bits.push(`saiu ${money(day.saida)}`);
  if (day.investimento) bits.push(`investiu ${money(day.investimento)}`);
  return bits.join(" · ");
}

function renderContas() {
  const rows = state.accounts.map((account) => `
    <div class="item">
      <div class="who"><strong>${escapeHtml(account.name)}</strong><span class="tag">${account.active ? "Ativa" : "Desativada"}</span></div>
      <strong class="money">${money(account.balance)}</strong>
      <button type="button" class="ghost" data-account="${account.id}">Editar</button>
    </div>`).join("");
  return `<article class="panel">${rows || empty("Nenhuma conta", "Crie a primeira com um nome livre. O saldo dela só conta o que já foi efetivado.")}</article>`;
}

function renderLancamentos() {
  const items = state.transactions.filter((item) => {
    if (state.filter.direction && item.direction !== state.filter.direction) return false;
    if (state.filter.pending && item.status !== "previsto") return false;
    if (state.filter.day && item.occurred_on !== state.filter.day) return false;
    return true;
  });
  const filter = state.filter.pending ? "Pendências" : state.filter.day ? formatDate(state.filter.day) : state.filter.direction ? labelDirection(state.filter.direction) : "";
  return `<article class="panel">
    <div class="panel-head">
      <div class="row">${filter ? `<button type="button" class="pill" id="clear-filter">${filter} · limpar</button>` : ""}</div>
      <button type="button" class="ghost" id="repeat">Repetir todo mês</button>
    </div>
    ${items.map(transactionRow).join("") || empty("Nenhum lançamento", "Neste recorte não há movimento. Um lançamento novo entra na capa no dia escolhido.")}
  </article>`;
}

function renderInvestimentos() {
  const items = state.transactions.filter((item) => item.direction === "investimento");
  const byAccount = (state.summary.by_account || []).filter((row) => row.direction === "investimento");
  const accounts = byAccount.length > 1 ? byAccount.map((row) => `<div class="item">
    <div class="who"><strong>${escapeHtml(row.account_name)}</strong><span class="tag">Saiu desta conta</span></div>
    <strong class="money">${money(row.amount)}</strong>
  </div>`).join("") : "";
  return `<article class="panel">
    <div class="panel-head">
      <div><h2>Neste mês</h2><p class="tag">A investir ${money(state.summary.pending.investimento)}</p></div>
      <strong class="money">${money(state.summary.investimento)}</strong>
    </div>
    ${accounts}
    ${items.map(transactionRow).join("") || empty("Nenhum investimento", "Ele sai da conta escolhida e reduz o saldo do mês, separado das saídas.")}
  </article>`;
}

function renderTipos() {
  return ["entrada", "saida"].map((direction) => {
    const categories = state.categories.filter((category) => category.direction === direction);
    return `<article class="panel"><div class="panel-head"><h2>${direction === "entrada" ? "Entradas" : "Saídas"}</h2></div>
    ${categories.map((category) => `
      <div class="kind">
        <div class="item">
          <div class="who">
            <strong>${escapeHtml(category.name)}</strong>
            <span class="tag">${category.active ? `${category.subcategories.length} subtipo${category.subcategories.length === 1 ? "" : "s"}` : "Desativado"}</span>
          </div>
          <div class="row">
            <button type="button" class="ghost" data-sub="${category.id}">Novo subtipo</button>
            <button type="button" class="ghost" data-off-cat="${category.id}">${category.active ? "Desativar" : "Ativar"}</button>
            ${category.deletable ? `<button type="button" class="danger" data-del-cat="${category.id}">Apagar</button>` : ""}
          </div>
        </div>
        <div class="subs">${category.subcategories.map((sub) => `
          <div class="item sub">
            <div class="who"><strong>${escapeHtml(sub.name)}</strong>${sub.active ? "" : `<span class="tag">Desativado</span>`}</div>
            <div class="row">
              <button type="button" class="ghost" data-edit-sub="${sub.id}">Renomear</button>
              <button type="button" class="ghost" data-off-sub="${sub.id}">${sub.active ? "Desativar" : "Ativar"}</button>
              ${sub.deletable ? `<button type="button" class="danger" data-del-sub="${sub.id}">Apagar</button>` : ""}
            </div>
          </div>`).join("") || `<p class="tag sub-empty">Nenhum subtipo. O lançamento pode ficar só no tipo.</p>`}
        </div>
      </div>`).join("") || empty(direction === "entrada" ? "Nenhuma entrada" : "Nenhuma saída", "O tipo organiza o lançamento. Investimento e transferência não usam tipo.")}
    </article>`;
  }).join("");
}

function renderEmprestimos() {
  const total = state.loans.reduce((sum, loan) => sum + loan.remaining, 0);
  const rows = state.loans.map((loan) => `<div class="item">
    <div class="who"><strong>${escapeHtml(loan.name)}</strong><span class="tag">${loan.term_months} meses · parcela ${money(loan.installment)}</span></div>
    <span class="tag">Restam ${money(loan.remaining)}</span>
    <button type="button" class="ghost" data-loan="${loan.id}">Ver evolução</button>
  </div>`).join("");
  return `<article class="panel">
    <div class="panel-head"><h2>Saldo devedor</h2><strong class="money">${money(total)}</strong></div>
    ${rows || empty("Nenhum empréstimo", "Informe o valor tomado, a taxa e a parcela ou o prazo. A última parcela zera o saldo.")}
  </article>`;
}

function renderMetas() {
  const rows = state.goals.map((goal) => `
    <div class="item">
      <div class="who"><strong>${escapeHtml(goal.name)}</strong><span class="tag">Alvo ${money(goal.target_amount)} até ${formatDate(goal.target_date)}</span></div>
      <span class="tag">${goal.current ? `Neste mês, guardar ${money(goal.current.challenge)}` : ""}</span>
      <button type="button" class="ghost" data-goal="${goal.id}">Registrar</button>
    </div>`).join("");
  return `<article class="panel">${rows || empty("Nenhuma meta", "Defina o alvo e a data. Se um mês ficar curto, o desafio dos meses seguintes sobe.")}</article>`;
}

function renderSimulacao() {
  return `<article class="panel"><form id="sim-form" class="fields composer">
    <div class="pair">
      <label>Parcela hipotética<input name="amount" inputmode="decimal" placeholder="0,00"></label>
      <label>Dia<input name="day" type="number" min="1" max="31" value="10"></label>
    </div>
    <label>Descrição<input name="description" value="Parcela nova"></label>
    <button class="primary" type="submit">Simular</button>
  </form><div id="sim-result"></div></article>`;
}

function renderEmpresa() {
  const company = state.company;
  if (!company) return `<article class="panel"><p>A empresa fica no contexto de pessoa jurídica.</p></article>`;
  const alerts = {
    warning: "O faturamento passou de 80% do teto.",
    limit: "O faturamento atingiu o teto do MEI.",
    above20: "Passou de 20% acima do teto. Até 20% há DAS complementar e a empresa vira microempresa no ano seguinte. Acima disso, o desenquadramento volta ao início do ano. Procure um contador. O sistema não calcula imposto de microempresa.",
  };
  const ratio = company.limit ? Math.min(100, Math.round((company.revenue / company.limit) * 100)) : 0;
  const limitValue = company.profile.annual_limit ? (company.profile.annual_limit / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) : "";
  return `<article class="panel">
    ${company.alerts.map((alert) => `<p class="alert">${alerts[alert]}</p>`).join("")}
    <div class="meter">
      <div class="meter-top"><span>Faturamento no ano</span><strong>${money(company.revenue)} de ${money(company.limit)}</strong></div>
      <div class="bar" aria-hidden="true"><span style="width:${ratio}%"></span></div>
      <p class="tag">Falta ${money(company.remaining)}.</p>
    </div>
    <form id="company-form" class="form-grid">
      <label>Perfil<select name="kind">
        <option value="mei" ${company.profile.kind === "mei" ? "selected" : ""}>MEI</option>
        <option value="mei_carga" ${company.profile.kind === "mei_carga" ? "selected" : ""}>MEI transportador</option>
        <option value="custom" ${company.profile.kind === "custom" ? "selected" : ""}>Outro teto</option>
      </select></label>
      <label>Abertura<input name="opened_on" type="date" value="${company.profile.opened_on || ""}"></label>
      <label id="custom-limit" class="wide" ${company.profile.kind === "custom" ? "" : "hidden"}>Teto anual<input name="annual_limit" inputmode="decimal" placeholder="0,00" value="${limitValue}"></label>
      <div class="checks wide">
        <label class="check"><input type="checkbox" name="has_icms" ${company.profile.has_icms ? "checked" : ""}> ICMS</label>
        <label class="check"><input type="checkbox" name="has_iss" ${company.profile.has_iss ? "checked" : ""}> ISS</label>
      </div>
      <button class="primary" type="submit">Salvar perfil</button>
    </form>
  </article>
  <article class="panel">
    <div class="panel-head"><h2>DAS</h2><p class="tag">Vence no dia 20. Marcar pago pode lançar a saída, se houver conta e tipo.</p></div>
    ${company.das.map((month) => `<div class="item das-row"><span>${monthName(month.month)}</span><span class="tag">vence ${formatDate(month.due_on)}</span><strong class="money">${money(month.amount)}</strong><button type="button" class="ghost" data-das="${month.month}" data-paid="${month.paid ? "1" : "0"}">${month.paid ? "Pago" : "Marcar pago"}</button></div>`).join("")}
    <div class="panel-head"><h2>DASN-SIMEI</h2></div>
    <p class="lede">A declaração de ${company.dasn_year} vence em ${formatDate(company.dasn_due)}, mesmo sem faturamento.</p>
    <div class="panel-head"><button type="button" class="${company.dasn_delivered ? "ghost" : "primary"}" id="dasn">${company.dasn_delivered ? "Entregue" : "Marcar como entregue"}</button></div>
  </article>`;
}

function renderUsuarios() {
  return `<article class="panel">
    <div class="panel-head">
      <div class="row">
        <button type="button" class="ghost" id="toggle-pf">${state.contexts.pf ? "Desligar pessoa física" : "Ligar pessoa física"}</button>
        <button type="button" class="ghost" id="toggle-pj">${state.contexts.pj ? "Desligar pessoa jurídica" : "Ligar pessoa jurídica"}</button>
      </div>
      <button type="button" class="ghost" id="export">Exportar dados</button>
    </div>
    ${state.users.map((user) => `<div class="item">
      <div class="who"><strong>${escapeHtml(user.name)}</strong><span class="tag">${user.role === "admin" ? "Administrador" : "Usuário"} · ${escapeHtml(user.email)}</span></div>
      <span class="pill ${user.active ? "ok" : ""}">${user.active ? "Ativo" : "Desativado"}</span>
      <button type="button" class="ghost" data-user="${user.id}" data-active="${user.active ? "1" : "0"}">${user.active ? "Desativar" : "Ativar"}</button>
    </div>`).join("")}
  </article>`;
}

function bindView() {
  document.querySelectorAll("[data-card]").forEach((button) => button.onclick = () => {
    const kind = button.dataset.card;
    if (kind === "investimento") { state.filter = {}; state.view = "investimentos"; render(); return; }
    state.filter = kind === "pendente" ? { pending: true } : kind === "saldo" ? {} : { direction: kind };
    state.view = "lancamentos";
    render();
  });
  document.querySelectorAll("[data-day]").forEach((button) => button.onclick = () => openDay(button.dataset.day));
  const calPrev = document.querySelector("#cal-prev");
  const calNext = document.querySelector("#cal-next");
  if (calPrev) calPrev.onclick = () => shiftCalendar(-1);
  if (calNext) calNext.onclick = () => shiftCalendar(1);
  const repeat = document.querySelector("#repeat");
  if (repeat) repeat.onclick = () => openSeries();
  const clearFilter = document.querySelector("#clear-filter");
  if (clearFilter) clearFilter.onclick = () => { state.filter = {}; render(); };
  document.querySelectorAll("[data-tx]").forEach((button) => button.onclick = () => openTransaction(find(state.transactions, button.dataset.tx)));
  document.querySelectorAll("[data-del-tx]").forEach((button) => button.onclick = () => removeTransaction(find(state.transactions, button.dataset.delTx)));
  document.querySelectorAll("[data-account]").forEach((button) => button.onclick = () => openAccount(find(state.accounts, button.dataset.account)));
  document.querySelectorAll("[data-sub]").forEach((button) => button.onclick = () => openSubcategory(button.dataset.sub));
  document.querySelectorAll("[data-edit-sub]").forEach((button) => button.onclick = () => openSubcategory(null, findSub(button.dataset.editSub)));
  document.querySelectorAll("[data-off-sub]").forEach((button) => button.onclick = async () => {
    const sub = findSub(button.dataset.offSub);
    await api(`/api/subcategories/${sub.id}`, { method: "PUT", body: JSON.stringify({ active: !sub.active }) });
    await refresh(); render();
  });
  document.querySelectorAll("[data-del-cat]").forEach((button) => button.onclick = async () => {
    const category = find(state.categories, button.dataset.delCat);
    const accepted = await ask("Apagar tipo", `${category.name} sai junto com os subtipos. Não dá para desfazer.`, "Apagar");
    if (!accepted) return;
    try {
      await api(`/api/categories/${category.id}`, { method: "DELETE" });
      await refresh(); render();
    } catch (error) { await notice(error.message); }
  });
  document.querySelectorAll("[data-del-sub]").forEach((button) => button.onclick = async () => {
    const sub = findSub(button.dataset.delSub);
    const accepted = await ask("Apagar subtipo", `${sub.name} sai da lista. Não dá para desfazer.`, "Apagar");
    if (!accepted) return;
    try {
      await api(`/api/subcategories/${sub.id}`, { method: "DELETE" });
      await refresh(); render();
    } catch (error) { await notice(error.message); }
  });
  document.querySelectorAll("[data-off-cat]").forEach((button) => button.onclick = async () => {
    const category = find(state.categories, button.dataset.offCat);
    await api(`/api/categories/${category.id}`, { method: "PUT", body: JSON.stringify({ active: !category.active }) });
    await refresh(); render();
  });
  document.querySelectorAll("[data-loan]").forEach((button) => button.onclick = () => openLoan(find(state.loans, button.dataset.loan)));
  document.querySelectorAll("[data-goal]").forEach((button) => button.onclick = () => openGoal(find(state.goals, button.dataset.goal)));
  const sim = document.querySelector("#sim-form");
  if (sim) sim.onsubmit = async (event) => {
    event.preventDefault();
    const amount = parseMoney(sim.amount.value);
    const result = await api("/api/simulation", { method: "POST", body: JSON.stringify({ context: state.context, month: state.month, extras: amount ? [{ direction: "saida", amount, day: Number(sim.day.value), description: sim.description.value }] : [] }) });
    document.querySelector("#sim-result").innerHTML = `<div class="result"><span class="tag">Saldo do último dia</span><strong class="${result.last_balance < 0 ? "negative" : "positive"}">${money(result.last_balance)}</strong><p class="tag">${result.zero_day ? `Fica negativo em ${formatDate(result.zero_day)}.` : "Não fica negativo."} Saídas do mês: ${money(result.saida)}.</p></div>`;
  };
  const company = document.querySelector("#company-form");
  if (company) company.onsubmit = async (event) => {
    event.preventDefault();
    const custom = company.kind.value === "custom";
    state.company = await api("/api/company", { method: "PUT", body: JSON.stringify({ kind: company.kind.value, opened_on: company.opened_on.value, annual_limit: custom && company.annual_limit.value ? parseMoney(company.annual_limit.value) : null, has_icms: company.has_icms.checked, has_iss: company.has_iss.checked, year: state.month.slice(0, 4) }) });
    render();
  };
  if (company) company.kind.onchange = () => { document.querySelector("#custom-limit").hidden = company.kind.value !== "custom"; };
  document.querySelectorAll("[data-das]").forEach((button) => button.onclick = async () => {
    const paid = button.dataset.paid !== "1";
    const category = state.categories.find((item) => item.direction === "saida" && item.active);
    const launch = paid && state.accounts[0] && category ? { account_id: state.accounts[0].id, category_id: category.id } : null;
    state.company = await api("/api/company/das", { method: "PUT", body: JSON.stringify({ year: Number(state.month.slice(0, 4)), month: Number(button.dataset.das), paid, launch }) });
    await refresh(); render();
  });
  const dasn = document.querySelector("#dasn");
  if (dasn) dasn.onclick = async () => { state.company = await api("/api/company/dasn", { method: "PUT", body: JSON.stringify({ year: state.company.dasn_year, delivered: !state.company.dasn_delivered }) }); render(); };
  const toggle = async (context, enabled) => {
    state.contexts = await api("/api/contexts", { method: "PUT", body: JSON.stringify({ context, enabled }) });
    if (!state.contexts[state.context]) {
      state.context = state.contexts.pf ? "pf" : "pj";
      await rememberContext();
    }
    await refresh();
    render();
  };
  const pf = document.querySelector("#toggle-pf");
  const pj = document.querySelector("#toggle-pj");
  if (pf) pf.onclick = () => toggle("pf", !state.contexts.pf);
  if (pj) pj.onclick = () => toggle("pj", !state.contexts.pj);
  const exp = document.querySelector("#export");
  if (exp) exp.onclick = async () => { const data = await api("/api/export"); const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "finances.json"; link.click(); };
  document.querySelectorAll("[data-user]").forEach((button) => button.onclick = async () => {
    await api(`/api/users/${button.dataset.user}`, { method: "PUT", body: JSON.stringify({ active: button.dataset.active !== "1" }) });
    await refresh(); render();
  });
}

function openCreate() {
  const actions = { capa: openTransaction, contas: () => openAccount(), lancamentos: openTransaction, investimentos: () => openTransaction(null, "investimento"), tipos: openCategory, emprestimos: openLoanForm, metas: openGoalForm, simulacao: () => {}, empresa: () => {}, usuarios: openUser };
  actions[state.view]();
}

function openTransaction(existing, preset) {
  if (!state.accounts.length) return openAccount();
  const item = existing || { direction: preset || "saida", amount: "", occurred_on: new Date().toISOString().slice(0, 10), description: "", account_id: state.accounts[0].id, status: "previsto" };
  const title = existing ? "Editar lançamento" : item.direction === "investimento" ? "Novo investimento" : "Novo lançamento";
  modal(`<form id="form"><h2>${title}</h2>
    <label>Direção<select name="direction">${["saida", "entrada", "investimento", "transferencia"].map((direction) => `<option value="${direction}" ${item.direction === direction ? "selected" : ""}>${labelDirection(direction)}</option>`).join("")}</select></label>
    <label>Valor<input name="amount" required value="${existing ? (existing.amount / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) : ""}"></label>
    <label>Data<input type="date" name="occurred_on" required value="${item.occurred_on}"></label>
    <label>Descrição<input name="description" value="${escapeHtml(item.description || "")}"></label>
    <label>Conta<select name="account_id">${options(state.accounts.filter((account) => account.active), item.account_id)}</select></label>
    <label id="dest">Conta de destino<select name="transfer_account_id">${options(state.accounts.filter((account) => account.active), item.transfer_account_id)}</select></label>
    <label id="kind">Tipo<select name="category_id"></select></label>
    <label id="sub">Subtipo<select name="subcategory_id"></select></label>
    <label>Situação<select name="status"><option value="previsto">Previsto</option><option value="efetivado" ${item.status === "efetivado" ? "selected" : ""}>Efetivado</option></select></label>
    <label id="revenue" class="check"><input type="checkbox" name="counts_as_revenue" ${item.counts_as_revenue !== 0 ? "checked" : ""}> Entra no faturamento</label>
    ${existing && existing.series_id ? `<label>Aplicar em<select name="scope"><option value="this">Só este lançamento</option><option value="all">Todas as ocorrências ainda não efetivadas</option></select></label>` : ""}
    <p class="error" id="error" hidden></p>
    <div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button>${existing ? `<button type="button" id="erase" class="danger">Apagar</button>` : ""}${existing ? `<button type="button" id="drop" class="ghost">Cancelar lançamento</button>` : ""}<button class="primary" type="submit">Salvar</button></div>
  </form>`);
  const form = document.querySelector("#form");
  const sync = () => {
    const direction = form.direction.value;
    document.querySelector("#dest").hidden = direction !== "transferencia";
    document.querySelector("#kind").hidden = direction === "transferencia" || direction === "investimento";
    document.querySelector("#sub").hidden = document.querySelector("#kind").hidden;
    document.querySelector("#revenue").hidden = !(state.context === "pj" && direction === "entrada");
    const categories = state.categories.filter((category) => category.active && category.direction === direction);
    form.category_id.innerHTML = categories.map((category) => `<option value="${category.id}" ${String(category.id) === String(item.category_id) ? "selected" : ""}>${escapeHtml(category.name)}</option>`).join("");
    const selected = categories.find((category) => String(category.id) === form.category_id.value);
    form.subcategory_id.innerHTML = `<option value="">Sem subtipo</option>` + ((selected && selected.subcategories) || []).filter((sub) => sub.active).map((sub) => `<option value="${sub.id}">${escapeHtml(sub.name)}</option>`).join("");
  };
  form.direction.onchange = sync;
  form.category_id.onchange = sync;
  sync();
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      const payload = bodyFrom(form);
      payload.amount = parseMoney(form.amount.value);
      payload.counts_as_revenue = form.counts_as_revenue.checked;
      payload.context = state.context;
      payload.category_id = form.category_id.value ? Number(form.category_id.value) : null;
      payload.subcategory_id = form.subcategory_id.value ? Number(form.subcategory_id.value) : null;
      payload.account_id = Number(form.account_id.value);
      payload.transfer_account_id = form.transfer_account_id.value ? Number(form.transfer_account_id.value) : null;
      if (existing) await api(`/api/transactions/${existing.id}`, { method: "PUT", body: JSON.stringify({ ...payload, scope: form.scope ? form.scope.value : "this" }) });
      else await api("/api/transactions", { method: "POST", body: JSON.stringify(payload) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
  const erase = document.querySelector("#erase");
  if (erase) erase.onclick = () => removeTransaction(existing);
  const drop = document.querySelector("#drop");
  if (drop) drop.onclick = async () => { await api(`/api/transactions/${existing.id}/cancel`, { method: "POST", body: "{}" }); closeModal(); await refresh(); render(); };
}

async function removeTransaction(item) {
  if (!item) return;
  const label = item.description || item.category_name || labelDirection(item.direction);
  const accepted = await ask("Apagar lançamento", `${label} de ${formatDate(item.occurred_on)} sai da lista. Não dá para desfazer.`, "Apagar");
  if (!accepted) return;
  try {
    await api(`/api/transactions/${item.id}`, { method: "DELETE" });
    closeModal();
    await refresh();
    render();
  } catch (error) { await notice(error.message); }
}

function openAccount(existing) {
  modal(`<form id="form"><h2>${existing ? "Editar conta" : "Nova conta"}</h2>
    <label>Nome<input name="name" required value="${existing ? escapeHtml(existing.name) : ""}"></label>
    ${existing ? `<label class="check"><input type="checkbox" name="active" ${existing.active ? "checked" : ""}> Ativa</label>` : ""}
    <p class="error" id="error" hidden></p>
    <div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="primary">Salvar</button></div></form>`);
  const form = document.querySelector("#form");
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      if (existing) await api(`/api/accounts/${existing.id}`, { method: "PUT", body: JSON.stringify({ name: form.name.value, active: form.active.checked }) });
      else await api("/api/accounts", { method: "POST", body: JSON.stringify({ context: state.context, name: form.name.value }) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function openCategory() {
  modal(`<form id="form"><h2>Novo tipo</h2>
    <label>Nome<input name="name" required></label>
    <label>Serve para<select name="direction"><option value="saida">Saída</option><option value="entrada">Entrada</option></select></label>
    <p class="error" id="error" hidden></p>
    <div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="primary">Salvar</button></div></form>`);
  const form = document.querySelector("#form");
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      await api("/api/categories", { method: "POST", body: JSON.stringify({ context: state.context, name: form.name.value, direction: form.direction.value }) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function openSubcategory(categoryId, existing) {
  modal(`<form id="form"><h2>${existing ? "Renomear subtipo" : "Novo subtipo"}</h2><label>Nome<input name="name" required value="${existing ? escapeHtml(existing.name) : ""}"></label><p class="error" id="error" hidden></p><div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="primary">Salvar</button></div></form>`);
  const form = document.querySelector("#form");
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      if (existing) await api(`/api/subcategories/${existing.id}`, { method: "PUT", body: JSON.stringify({ name: form.name.value }) });
      else await api(`/api/categories/${categoryId}/subcategories`, { method: "POST", body: JSON.stringify({ name: form.name.value }) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function findSub(id) {
  for (const category of state.categories) {
    const sub = category.subcategories.find((item) => String(item.id) === String(id));
    if (sub) return sub;
  }
}

function openLoanForm() {
  const saidas = state.categories.filter((category) => category.direction === "saida" && category.active);
  if (!state.accounts.length || !saidas.length) { notice("Crie uma conta e um tipo de saída antes do empréstimo."); return; }
  modal(`<form id="form"><h2>Novo empréstimo</h2>
    <label>Nome<input name="name" value="Empréstimo"></label>
    <label>Valor tomado<input name="principal" required></label>
    <label>Taxa mensal (%)<input name="monthly_rate" required placeholder="1,99"></label>
    <label>Prazo em meses<input name="term_months" placeholder="Deixe vazio se informar a parcela"></label>
    <label>Ou valor da parcela<input name="installment"></label>
    <label>Sistema<select name="system"><option value="price">Tabela Price</option><option value="sac">SAC</option></select></label>
    <label>Primeira parcela<input type="date" name="first_due" required value="${new Date().toISOString().slice(0, 10)}"></label>
    <label>Parcelas já pagas<input name="already_paid" value="0"></label>
    <label>Conta da parcela<select name="account_id">${options(state.accounts.filter((account) => account.active))}</select></label>
    <label>Tipo<select name="category_id">${saidas.map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join("")}</select></label>
    <p class="error" id="error" hidden></p>
    <div id="preview"></div>
    <div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button type="button" id="calc" class="ghost">Calcular</button><button class="primary">Lançar contrato</button></div></form>`);
  const form = document.querySelector("#form");
  const payload = () => ({
    principal: parseMoney(form.principal.value), monthly_rate: form.monthly_rate.value, term_months: form.term_months.value || null,
    installment: form.installment.value ? parseMoney(form.installment.value) : null, system: form.system.value, first_due: form.first_due.value,
  });
  document.querySelector("#calc").onclick = async () => {
    try {
      const result = await api("/api/loans/preview", { method: "POST", body: JSON.stringify(payload()) });
      document.querySelector("#preview").innerHTML = `<p>${result.term_months} parcelas. Primeira ${money(result.installment)}. Juros ${money(result.total_interest)}. Saldo final ${money(result.leftover)}.</p>`;
    } catch (error) { showError(error); }
  };
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      await api("/api/loans", { method: "POST", body: JSON.stringify({ ...payload(), context: state.context, name: form.name.value, account_id: Number(form.account_id.value), category_id: Number(form.category_id.value), already_paid: Number(form.already_paid.value || 0) }) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function openLoan(loan) {
  modal(`<div><h2>${escapeHtml(loan.name)}</h2><p>Juros totais ${money(loan.total_interest)}. Saldo devedor ${money(loan.remaining)}.</p>${loan.rows.map((row) => `<div class="item"><span>${formatDate(row.due_on)}</span><span>Juros ${money(row.interest)} · amortiza ${money(row.amortization)}</span><strong>${money(row.balance)} · ${row.status}</strong></div>`).join("")}<button type="button" id="cancel" class="ghost">Fechar</button></div>`);
}

function openGoalForm() {
  modal(`<form id="form"><h2>Nova meta</h2><label>Nome<input name="name" required></label><label>Valor alvo<input name="target_amount" required></label><label>Data alvo<input type="date" name="target_date" required></label><p class="error" id="error" hidden></p><div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="primary">Salvar</button></div></form>`);
  const form = document.querySelector("#form");
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      await api("/api/goals", { method: "POST", body: JSON.stringify({ context: state.context, name: form.name.value, target_amount: parseMoney(form.target_amount.value), target_date: form.target_date.value }) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function openGoal(goal) {
  modal(`<form id="form"><h2>${escapeHtml(goal.name)}</h2>${goal.history.map((month) => `<label>${monthLabel(month.month)} · desafio ${money(month.challenge)}<input data-month="${month.month}" value="${(month.saved / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}"></label>`).join("")}<p class="error" id="error" hidden></p><div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="primary">Salvar o que guardei</button></div></form>`);
  const form = document.querySelector("#form");
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      for (const input of form.querySelectorAll("[data-month]")) {
        await api(`/api/goals/${goal.id}/months/${input.dataset.month}`, { method: "PUT", body: JSON.stringify({ saved: parseMoney(input.value, true) }) });
      }
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function openUser() {
  modal(`<form id="form"><h2>Novo usuário</h2><label>Nome<input name="name" required></label><label>E-mail<input name="email" type="email" required></label><label>Senha<input name="password" type="password" required></label><p class="error" id="error" hidden></p><div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="primary">Criar</button></div></form>`);
  const form = document.querySelector("#form");
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      await api("/api/users", { method: "POST", body: JSON.stringify(bodyFrom(form)) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function openSeries() {
  modal(`<form id="form"><h2>Repetir todo mês</h2>
    <label>Direção<select name="direction"><option value="saida">Saída</option><option value="entrada">Entrada</option></select></label>
    <label>Valor<input name="amount" required></label>
    <label>Dia do mês<input name="day_of_month" type="number" min="1" max="31" value="5"></label>
    <label>A partir de<input name="start_month" value="${state.month}"></label>
    <label>Quantidade de meses<input name="month_count" placeholder="Vazio repete por 60 meses"></label>
    <label>Conta<select name="account_id">${options(state.accounts.filter((account) => account.active))}</select></label>
    <label>Tipo<select name="category_id"></select></label>
    <label>Descrição<input name="description"></label>
    <p class="error" id="error" hidden></p>
    <div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="primary">Criar</button></div></form>`);
  const form = document.querySelector("#form");
  const syncSeriesCategories = () => {
    const categories = state.categories.filter((category) => category.active && category.direction === form.direction.value);
    const current = form.category_id.value;
    form.category_id.innerHTML = categories.map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join("");
    if ([...form.category_id.options].some((option) => option.value === current)) form.category_id.value = current;
  };
  form.direction.onchange = syncSeriesCategories;
  syncSeriesCategories();
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      await api("/api/series", { method: "POST", body: JSON.stringify({ context: state.context, direction: form.direction.value, amount: parseMoney(form.amount.value), day_of_month: Number(form.day_of_month.value), start_month: form.start_month.value, month_count: form.month_count.value || null, account_id: Number(form.account_id.value), category_id: Number(form.category_id.value), description: form.description.value }) });
      closeModal(); await refresh(); render();
    } catch (error) { showError(error); }
  };
}

function createLabel() {
  return { contas: "Nova conta", tipos: "Novo tipo", emprestimos: "Novo empréstimo", metas: "Nova meta", usuarios: "Novo usuário", lancamentos: "Novo lançamento", capa: "Novo lançamento", investimentos: "Novo investimento" }[state.view] || "Novo lançamento";
}

function renderAuth(title, path, action) {
  app.innerHTML = `<div class="auth"><form id="auth" class="card fields"><div class="brand"><span class="mark">F</span><strong>Finances</strong></div><h1>${title}</h1>${path === "/api/setup" ? `<label>Nome<input name="name" required></label>` : ""}<label>E-mail<input name="email" type="email" required></label><label>Senha<input name="password" type="password" required></label><p class="error" id="error" hidden></p><button class="primary" type="submit">${action}</button></form></div>`;
  document.querySelector("#auth").onsubmit = async (event) => {
    event.preventDefault();
    try {
      const form = event.target;
      const result = await api(path, { method: "POST", body: JSON.stringify(bodyFrom(form)) });
      state.user = result.user;
      state.ready = true;
      const session = await api("/api/session");
      state.contexts = session.contexts;
      state.context = preferredContext();
      await refresh();
      render();
    } catch (error) { showError(error); }
  };
}

function transactionRow(item) {
  const tone = item.direction === "entrada" ? "positive" : item.direction === "saida" || item.direction === "investimento" ? "negative" : "";
  return `<div class="item">
    <div class="who"><strong>${escapeHtml(item.description || item.category_name || labelDirection(item.direction))}</strong><span class="tag">${formatDate(item.occurred_on)} · ${escapeHtml(item.account_name)} · ${labelDirection(item.direction)}</span></div>
    ${statusPill(item)}
    <strong class="money ${tone}">${money(item.amount)}</strong>
    <button type="button" class="ghost" data-tx="${item.id}">Editar</button>
    <button type="button" class="danger" data-del-tx="${item.id}">Apagar</button>
  </div>`;
}

function statusPill(item) {
  if (item.status === "cancelado") return `<span class="pill">cancelado</span>`;
  if (item.late) return `<span class="pill late">atrasado</span>`;
  if (item.status === "efetivado") return `<span class="pill ok">efetivado</span>`;
  return `<span class="pill">previsto</span>`;
}

function metric(label, value, tone, kind) {
  return `<button type="button" class="card" data-card="${kind}"><span>${label}</span><strong class="${tone || ""}">${money(value)}</strong></button>`;
}

function empty(title, text) {
  return `<div class="empty"><strong>${title}</strong><p>${text}</p></div>`;
}

function monthName(month) {
  return ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][Number(month) - 1];
}

function modal(html) {
  const dialog = document.querySelector("#modal");
  dialog.innerHTML = html;
  if (!dialog.open) dialog.showModal();
  const cancel = document.querySelector("#cancel");
  if (cancel) cancel.onclick = closeModal;
}

function closeModal() { const dialog = document.querySelector("#modal"); if (dialog && dialog.open) dialog.close(); }

function ask(title, text, action) {
  return new Promise((resolve) => {
    const dialog = document.querySelector("#modal");
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      closeModal();
      resolve(value);
    };
    dialog.innerHTML = `<form id="form"><h2>${escapeHtml(title)}</h2><p class="lede">${escapeHtml(text)}</p><div class="row"><button type="button" id="cancel" class="ghost">Cancelar</button><button class="danger" type="submit">${escapeHtml(action)}</button></div></form>`;
    dialog.showModal();
    dialog.querySelector("#form").onsubmit = (event) => { event.preventDefault(); finish(true); };
    dialog.querySelector("#cancel").onclick = () => finish(false);
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); finish(false); }, { once: true });
  });
}

function notice(text) {
  return new Promise((resolve) => {
    const dialog = document.querySelector("#modal");
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      closeModal();
      resolve();
    };
    dialog.innerHTML = `<form id="form"><h2>Aviso</h2><p class="lede">${escapeHtml(text)}</p><div class="row"><button class="primary" type="submit">Entendi</button></div></form>`;
    dialog.showModal();
    dialog.querySelector("#form").onsubmit = (event) => { event.preventDefault(); finish(); };
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); finish(); }, { once: true });
  });
}

function showError(error) { const box = document.querySelector("#error"); if (!box) return notice(error.message); box.hidden = false; box.textContent = error.message; }
function bodyFrom(form) { return Object.fromEntries(new FormData(form).entries()); }
function options(items, selected) { return items.map((item) => `<option value="${item.id}" ${String(item.id) === String(selected) ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join(""); }
function find(items, id) { return items.find((item) => String(item.id) === String(id)); }
function labelDirection(direction) { return { entrada: "Entrada", saida: "Saída", investimento: "Investimento", transferencia: "Transferência" }[direction]; }
function money(cents) { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format((cents || 0) / 100); }
function balanceTone(cents) { if (cents > 0) return "positive"; if (cents < 0) return "negative"; return "zero"; }
function parseMoney(value, allowZero = false) {
  let text = String(value || "").trim().replace(/[R$\s]/g, "");
  if (!text) return allowZero ? 0 : 0;
  if (text.includes(",")) text = text.replace(/\./g, "").replace(",", ".");
  const amount = Math.round(Number(text) * 100);
  if (!Number.isFinite(amount)) throw new Error("Valor inválido.");
  return amount;
}
function formatDate(value) { const [year, month, day] = value.split("-"); return `${day}/${month}/${year}`; }
function monthLabel(month) { const [year, mon] = month.split("-").map(Number); const label = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" }).format(new Date(year, mon - 1, 1)); return label.charAt(0).toUpperCase() + label.slice(1); }
function currentMonth() { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`; }
function addMonth(month, delta) {
  const [year, mon] = month.split("-").map(Number);
  const next = new Date(year, mon - 1 + delta, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
}
async function shiftMonth(delta) {
  state.month = addMonth(state.month, delta);
  state.calendarMonth = state.month;
  await refresh();
  render();
}
async function shiftCalendar(delta) {
  state.calendarMonth = addMonth(state.calendarMonth, delta);
  state.calendar = state.calendarMonth === state.month
    ? state.summary
    : await api(`/api/summary?context=${state.context}&month=${state.calendarMonth}`);
  render();
}
async function openDay(day) {
  state.filter = { day };
  state.view = "lancamentos";
  const month = day.slice(0, 7);
  if (month !== state.month) {
    state.month = month;
    await refresh();
  }
  render();
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])); }
async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, credentials: "same-origin", ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Não foi possível concluir.");
  return data;
}

document.addEventListener("keydown", (event) => {
  if (event.altKey && event.key === "r") openSeries();
});
