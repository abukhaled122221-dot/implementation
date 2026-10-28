/**
 * لوحة تحكم ثقة (Admin Component) — منفصلة عن واجهة العميل بجلسة وكوكي مختلفين.
 *
 * الأقسام: نظرة عامة، المستخدمون، شركات التأمين، إعدادات API (+ اختبار الاتصال)،
 * سجل التوصيات، سجل العمليات. كل التعديلات تُسجَّل في Audit_Log على الخادم.
 */
(() => {
  const esc = TH.escapeHtml;
  const $ = (id) => document.getElementById(id);
  const PAGE_SIZE = 20;

  const SECTIONS = {
    overview: { title: "نظرة عامة", load: loadOverview },
    users: { title: "إدارة المستخدمين", load: () => loadUsers(1) },
    providers: { title: "شركات التأمين", load: loadProviders },
    api: { title: "إعدادات الاتصال بـ API", load: loadApiSettings },
    logs: { title: "سجل عمليات التوصية", load: () => loadLogs(1) },
    audit: { title: "سجل عمليات المسؤولين", load: () => loadAudit(1) },
  };

  const WORKSHOP_OPTIONS = ["واسع جداً", "متوسط", "محدود"];
  const ADAPTERS = ["tawuniya", "rajhi", "medgulf", "acig"];

  /** كل طلبات الأدمن: عند انتهاء الجلسة نرجع لصفحة دخول المسؤول. */
  const adminApi = (url, options = {}) =>
    TH.api(url, {
      ...options,
      onUnauthorized: () => location.replace("/admin/login.html"),
    });

  // ================================================================ التهيئة والتنقل
  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const { user } = await adminApi("/api/admin/me");
      $("admin-name").textContent = user.UserName;
    } catch {
      return; // تم التحويل لصفحة الدخول
    }

    styleNav();
    $("admin-logout").addEventListener("click", logout);
    $("menu-toggle").addEventListener("click", () =>
      $("sidebar").classList.toggle("hidden"),
    );
    window.addEventListener("hashchange", showSection);
    bindModal();
    bindFilters();
    showSection();
  });

  function styleNav() {
    document.querySelectorAll("#admin-nav a").forEach((link) => {
      link.className =
        "flex items-center gap-3 px-4 py-3 rounded-xl transition hover:bg-white/5 hover:text-white";
    });
  }

  function showSection() {
    const key =
      location.hash.slice(1) in SECTIONS ? location.hash.slice(1) : "overview";
    document.querySelectorAll("[data-panel]").forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.panel !== key);
    });
    document.querySelectorAll("#admin-nav a").forEach((link) => {
      const active = link.dataset.section === key;
      link.classList.toggle("bg-brand-600", active);
      link.classList.toggle("text-white", active);
    });
    $("section-title").textContent = SECTIONS[key].title;
    if (window.innerWidth < 768) $("sidebar").classList.add("hidden");
    SECTIONS[key].load();
  }

  async function logout() {
    try {
      await TH.api("/api/admin/logout", { method: "POST" });
    } finally {
      location.replace("/admin/login.html");
    }
  }

  // ================================================================ أدوات العرض
  const loadingBlock = () =>
    `<div class="p-6 space-y-3">${'<div class="h-10 rounded-xl bg-slate-100 animate-pulse"></div>'.repeat(4)}</div>`;

  const emptyBlock = (text) =>
    `<div class="p-10 text-center text-slate-400 text-sm"><i class="fa-regular fa-folder-open text-3xl mb-2 block"></i>${esc(text)}</div>`;

  const errorBlock = (error) =>
    `<div class="p-6 text-red-600 font-bold text-sm"><i class="fa-solid fa-circle-exclamation ml-1"></i>${esc(error.message)}</div>`;

  /** جدول بسيط: columns = [{label, render(row)}] */
  function table(columns, rows) {
    const head = columns
      .map((c) => `<th class="p-3 font-bold">${esc(c.label)}</th>`)
      .join("");
    const body = rows
      .map(
        (row) =>
          `<tr class="border-t border-slate-100 hover:bg-slate-50">${columns
            .map((c) => `<td class="p-3 align-middle">${c.render(row)}</td>`)
            .join("")}</tr>`,
      )
      .join("");
    return `<table class="w-full text-sm text-right">
              <thead class="bg-slate-50 text-xs text-slate-500"><tr>${head}</tr></thead>
              <tbody>${body}</tbody>
            </table>`;
  }

  /** شريط ترقيم الصفحات */
  function renderPager(host, page, total, onPage) {
    const pages = Math.max(1, Math.ceil((total || 0) / PAGE_SIZE));
    if (pages <= 1) {
      host.innerHTML = `<span class="text-xs text-slate-400">${total || 0} سجل</span>`;
      return;
    }
    const btn = (label, target, enabled) =>
      `<button type="button" ${enabled ? `data-page="${target}"` : "disabled"}
         class="px-3 py-1.5 rounded-lg text-xs font-bold ${enabled ? "bg-white border border-slate-200 hover:bg-slate-50" : "bg-slate-100 text-slate-400"}">${label}</button>`;
    host.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="text-xs text-slate-500">${total} سجل · صفحة ${page} من ${pages}</span>
        <div class="flex gap-2">${btn("السابق", page - 1, page > 1)}${btn("التالي", page + 1, page < pages)}</div>
      </div>`;
    host
      .querySelectorAll("[data-page]")
      .forEach((el) =>
        el.addEventListener("click", () => onPage(Number(el.dataset.page))),
      );
  }

  const activeBadge = (active) =>
    TH.statusBadge(Boolean(Number(active)), "نشط", "معطّل");

  // ================================================================ النافذة المنبثقة
  function bindModal() {
    $("modal").addEventListener("click", (event) => {
      if (
        event.target === $("modal") ||
        event.target.closest("[data-close-modal]")
      )
        closeModal();
    });
    document.addEventListener(
      "keydown",
      (event) => event.key === "Escape" && closeModal(),
    );
  }

  function openModal(title, html) {
    $("modal-title").textContent = title;
    $("modal-body").innerHTML = html;
    $("modal").classList.remove("hidden");
  }

  function closeModal() {
    $("modal").classList.add("hidden");
  }

  // ================================================================ نظرة عامة
  async function loadOverview() {
    $("stats-cards").innerHTML =
      '<div class="h-28 rounded-2xl bg-white animate-pulse"></div>'.repeat(4);
    $("recent-requests").innerHTML = loadingBlock();
    try {
      const data = await adminApi("/api/admin/overview");
      const users = data.users || {};
      const requests = data.requests || {};
      const providers = data.providers || {};
      const rate = Number(requests.successRate ?? 0); // نسبة مئوية 0–100 من الخادم
      const rateText = `${Math.round(rate)}%`;

      const card = (icon, color, label, value, hint) => `
        <div class="bg-white rounded-2xl border border-slate-200 p-5">
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm font-bold text-slate-500">${esc(label)}</span>
            <span class="w-10 h-10 rounded-xl ${color} flex items-center justify-center"><i class="fa-solid ${icon}"></i></span>
          </div>
          <div class="text-3xl font-black text-navy-800">${esc(value ?? 0)}</div>
          <div class="text-xs text-slate-400 mt-1">${esc(hint)}</div>
        </div>`;

      $("stats-cards").innerHTML = [
        card(
          "fa-users",
          "bg-blue-50 text-blue-600",
          "المستخدمون",
          users.total,
          `${users.active ?? 0} نشط`,
        ),
        card(
          "fa-list-check",
          "bg-brand-50 text-brand-600",
          "طلبات التوصية",
          requests.total,
          `${requests.today ?? 0} اليوم`,
        ),
        card(
          "fa-circle-check",
          "bg-emerald-50 text-emerald-600",
          "نسبة النجاح",
          rateText,
          `${requests.failed ?? 0} طلب فاشل`,
        ),
        card(
          "fa-building-shield",
          "bg-amber-50 text-amber-600",
          "شركات التأمين",
          providers.total,
          `${providers.active ?? 0} مفعّلة`,
        ),
      ].join("");

      const recent = data.recent || [];
      $("recent-requests").innerHTML = recent.length
        ? logsTable(recent)
        : emptyBlock("لا توجد طلبات بعد");
      bindLogDetails($("recent-requests"));
    } catch (error) {
      $("stats-cards").innerHTML = errorBlock(error);
      $("recent-requests").innerHTML = "";
    }
  }

  // ================================================================ المستخدمون
  let usersQuery = "";

  async function loadUsers(page) {
    $("users-table").innerHTML = loadingBlock();
    try {
      const params = new URLSearchParams({
        q: usersQuery,
        page,
        pageSize: PAGE_SIZE,
      });
      const data = await adminApi(`/api/admin/users?${params}`);
      const items = data.items || data.users || [];
      $("users-count").textContent = `${data.total ?? items.length} مستخدم`;

      $("users-table").innerHTML = items.length
        ? table(
            [
              {
                label: "المستخدم",
                render: (u) =>
                  `<b>${esc(u.UserName)}</b><div class="text-xs text-slate-400">${esc(u.Email)}</div>`,
              },
              {
                label: "النوع",
                render: (u) =>
                  Number(u.IsAdmin)
                    ? '<span class="text-xs font-bold text-purple-700 bg-purple-50 px-2 py-1 rounded-lg">مسؤول</span>'
                    : '<span class="text-xs text-slate-500">عميل</span>',
              },
              { label: "الطلبات", render: (u) => esc(u.RequestsCount ?? "—") },
              {
                label: "تاريخ التسجيل",
                render: (u) =>
                  `<span class="text-xs">${esc(TH.formatDate(u.CreatedAt))}</span>`,
              },
              {
                label: "آخر دخول",
                render: (u) =>
                  `<span class="text-xs">${esc(TH.formatDate(u.LastLoginAt))}</span>`,
              },
              { label: "الحالة", render: (u) => activeBadge(u.IsActive) },
              {
                label: "",
                render: (
                  u,
                ) => `<button type="button" data-toggle-user="${Number(u.UserId)}" data-active="${Number(u.IsActive)}"
                    class="text-xs font-bold px-3 py-1.5 rounded-lg ${Number(u.IsActive) ? "bg-red-50 text-red-600 hover:bg-red-100" : "bg-brand-50 text-brand-700 hover:bg-brand-100"}">
                    ${Number(u.IsActive) ? "تعطيل" : "تفعيل"}</button>`,
              },
            ],
            items,
          )
        : emptyBlock("لا يوجد مستخدمون مطابقون");

      $("users-table")
        .querySelectorAll("[data-toggle-user]")
        .forEach((button) =>
          button.addEventListener("click", () => toggleUser(button, page)),
        );
      renderPager(
        $("users-pager"),
        page,
        data.total ?? items.length,
        loadUsers,
      );
    } catch (error) {
      $("users-table").innerHTML = errorBlock(error);
    }
  }

  async function toggleUser(button, page) {
    const activate = button.dataset.active !== "1";
    if (
      !activate &&
      !confirm("تعطيل هذا الحساب سيمنعه من تسجيل الدخول. هل أنت متأكد؟")
    )
      return;
    TH.setLoading(button, true, "");
    try {
      await adminApi(`/api/admin/users/${button.dataset.toggleUser}`, {
        method: "PATCH",
        body: { is_active: activate, IsActive: activate ? 1 : 0 },
      });
      TH.toast(activate ? "تم تفعيل الحساب" : "تم تعطيل الحساب");
      loadUsers(page);
    } catch (error) {
      TH.toast(error.message, "error");
      TH.setLoading(button, false);
    }
  }

  // ================================================================ شركات التأمين
  let providersCache = [];

  async function loadProviders() {
    $("providers-table").innerHTML = loadingBlock();
    try {
      const data = await adminApi("/api/admin/providers");
      providersCache = data.items || data.providers || [];
      $("providers-table").innerHTML = providersCache.length
        ? table(
            [
              {
                label: "الشركة",
                render: (p) =>
                  `<b>${esc(p.ProviderName)}</b><div class="text-xs text-slate-400 font-mono">${esc(p.ProviderId)}</div>`,
              },
              { label: "الموثوقية", render: (p) => esc(p.Reliability ?? "—") },
              {
                label: "شبكة الورش",
                render: (p) => esc(p.WorkshopNetwork || "—"),
              },
              {
                label: "التجربة الرقمية",
                render: (p) => esc(p.DigitalScore ?? "—"),
              },
              {
                label: "عروض محفوظة",
                render: (p) => esc(p.QuotesCount ?? "—"),
              },
              { label: "الحالة", render: (p) => activeBadge(p.IsActive) },
              {
                label: "",
                render: (p) => `
                  <div class="flex gap-1.5 justify-end">
                    <button type="button" data-edit="${esc(p.ProviderId)}" class="text-xs font-bold px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200">تعديل</button>
                    <button type="button" data-toggle="${esc(p.ProviderId)}" class="text-xs font-bold px-3 py-1.5 rounded-lg ${Number(p.IsActive) ? "bg-amber-50 text-amber-700 hover:bg-amber-100" : "bg-brand-50 text-brand-700 hover:bg-brand-100"}">${Number(p.IsActive) ? "تعطيل" : "تفعيل"}</button>
                    <button type="button" data-delete="${esc(p.ProviderId)}" class="text-xs font-bold px-3 py-1.5 rounded-lg bg-red-50 text-red-600 hover:bg-red-100"><i class="fa-solid fa-trash"></i></button>
                  </div>`,
              },
            ],
            providersCache,
          )
        : emptyBlock("لا توجد شركات");

      const host = $("providers-table");
      host
        .querySelectorAll("[data-edit]")
        .forEach((b) =>
          b.addEventListener("click", () => openProviderForm(b.dataset.edit)),
        );
      host
        .querySelectorAll("[data-toggle]")
        .forEach((b) =>
          b.addEventListener("click", () => toggleProvider(b.dataset.toggle)),
        );
      host
        .querySelectorAll("[data-delete]")
        .forEach((b) =>
          b.addEventListener("click", () => deleteProvider(b.dataset.delete)),
        );
    } catch (error) {
      $("providers-table").innerHTML = errorBlock(error);
    }
  }

  $("add-provider")?.addEventListener("click", () => openProviderForm(null));

  function field(label, input, hint = "") {
    return `<label class="block">
              <span class="block text-sm font-bold text-slate-700 mb-1.5">${esc(label)}</span>
              ${input}
              ${hint ? `<span class="block text-xs text-slate-400 mt-1">${esc(hint)}</span>` : ""}
            </label>`;
  }

  const inputClass =
    "w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500";

  function openProviderForm(providerId) {
    const p = providersCache.find((x) => x.ProviderId === providerId) || {};
    const isEdit = Boolean(providerId);
    const options = WORKSHOP_OPTIONS.map(
      (o) =>
        `<option ${p.WorkshopNetwork === o ? "selected" : ""}>${esc(o)}</option>`,
    ).join("");

    openModal(
      isEdit ? `تعديل ${p.ProviderName}` : "إضافة شركة تأمين",
      `<form id="provider-form" class="grid sm:grid-cols-2 gap-4">
         ${field("المعرّف (provider_id)", `<input name="provider_id" dir="ltr" required pattern="[a-z0-9_]{2,30}" value="${esc(p.ProviderId || "")}" ${isEdit ? "disabled" : ""} class="${inputClass} ${isEdit ? "bg-slate-50" : ""}">`, "أحرف إنجليزية صغيرة وأرقام و _ فقط")}
         ${field("اسم الشركة", `<input name="provider_name" required value="${esc(p.ProviderName || "")}" class="${inputClass}">`)}
         ${field("الموقع الإلكتروني", `<input name="website" dir="ltr" type="url" value="${esc(p.Website || "")}" class="${inputClass}">`)}
         ${field("رابط الشعار", `<input name="logo_url" dir="ltr" type="url" value="${esc(p.LogoUrl || "")}" class="${inputClass}">`)}
         ${field("الموثوقية (0–1)", `<input name="reliability" type="number" min="0" max="1" step="0.01" required value="${esc(p.Reliability ?? 0.8)}" class="${inputClass}">`, "تُستخدم في معيار الموثوقية لدى Agent 2")}
         ${field("التجربة الرقمية (0–1)", `<input name="digital_score" type="number" min="0" max="1" step="0.01" required value="${esc(p.DigitalScore ?? 0.8)}" class="${inputClass}">`)}
         ${field("شبكة الورش", `<select name="workshop_network" class="${inputClass}">${options}</select>`)}
         <div class="sm:col-span-2 flex justify-end gap-2 pt-2">
           <button type="button" data-close-modal class="px-4 py-2.5 rounded-xl bg-slate-100 font-bold text-sm">إلغاء</button>
           <button type="submit" class="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-bold text-sm">حفظ</button>
         </div>
       </form>`,
    );

    $("provider-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (!form.reportValidity()) return;
      const values = Object.fromEntries(new FormData(form));
      values.reliability = Number(values.reliability);
      values.digital_score = Number(values.digital_score);
      const button = form.querySelector('button[type="submit"]');
      TH.setLoading(button, true, "جارٍ الحفظ…");
      try {
        if (isEdit) {
          await adminApi(
            `/api/admin/providers/${encodeURIComponent(providerId)}`,
            { method: "PATCH", body: values },
          );
        } else {
          await adminApi("/api/admin/providers", {
            method: "POST",
            body: values,
          });
        }
        closeModal();
        TH.toast(
          isEdit
            ? "تم حفظ التعديلات"
            : "تمت إضافة الشركة — أكمل إعدادات API الخاصة بها",
        );
        loadProviders();
      } catch (error) {
        TH.toast(error.message, "error");
        TH.setLoading(button, false);
      }
    });
  }

  async function toggleProvider(providerId) {
    const p = providersCache.find((x) => x.ProviderId === providerId);
    const activate = !Number(p.IsActive);
    if (
      !activate &&
      !confirm(
        `تعطيل ${p.ProviderName} سيستبعدها من طلبات التوصية القادمة. متابعة؟`,
      )
    )
      return;
    try {
      await adminApi(`/api/admin/providers/${encodeURIComponent(providerId)}`, {
        method: "PATCH",
        body: { is_active: activate },
      });
      TH.toast(activate ? "تم تفعيل الشركة" : "تم تعطيل الشركة");
      loadProviders();
    } catch (error) {
      TH.toast(error.message, "error");
    }
  }

  async function deleteProvider(providerId) {
    const p = providersCache.find((x) => x.ProviderId === providerId);
    if (
      !confirm(
        `حذف ${p.ProviderName} نهائياً؟ (إذا كانت لها عروض محفوظة سيُرفض الحذف ويمكنك تعطيلها بدلاً من ذلك)`,
      )
    )
      return;
    try {
      await adminApi(`/api/admin/providers/${encodeURIComponent(providerId)}`, {
        method: "DELETE",
      });
      TH.toast("تم حذف الشركة");
      loadProviders();
    } catch (error) {
      TH.toast(error.message, "error");
    }
  }

  // ================================================================ إعدادات API
  async function loadApiSettings() {
    $("api-settings").innerHTML = loadingBlock();
    try {
      const [settingsData, providersData] = await Promise.all([
        adminApi("/api/admin/api-settings"),
        adminApi("/api/admin/providers"),
      ]);
      const settings = settingsData.items || settingsData.settings || [];
      const providers = providersData.items || providersData.providers || [];

      // كل شركة تظهر حتى لو لم تُضبط إعداداتها بعد (شركة مضافة حديثاً)
      const cards = providers.map((p) =>
        apiCard(p, settings.find((s) => s.ProviderId === p.ProviderId) || {}),
      );
      $("api-settings").innerHTML =
        cards.join("") || emptyBlock("لا توجد شركات");

      $("api-settings")
        .querySelectorAll("form[data-api]")
        .forEach((form) => {
          form.addEventListener("submit", saveApiSettings);
          form
            .querySelector("[data-test]")
            .addEventListener("click", () => testConnection(form));
        });
    } catch (error) {
      $("api-settings").innerHTML = errorBlock(error);
    }
  }

  function apiCard(provider, s) {
    const select = (name, values, current) =>
      `<select name="${name}" class="${inputClass}">${values
        .map(
          (v) =>
            `<option ${v === current ? "selected" : ""}>${esc(v)}</option>`,
        )
        .join("")}</select>`;
    const keyHint =
      s.HasAuthKey || s.AuthKeyLast4
        ? `المفتاح الحالي ينتهي بـ ••••${esc(s.AuthKeyLast4 || "")} — اتركه فارغاً للإبقاء عليه`
        : "لا يوجد مفتاح محفوظ (سيُستخدم المفتاح الافتراضي من البيئة)";

    return `
      <form data-api="${esc(provider.ProviderId)}" class="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="font-black text-navy-800">${esc(provider.ProviderName)}</h3>
            <span class="text-xs text-slate-400 font-mono">${esc(provider.ProviderId)}</span>
          </div>
          ${activeBadge(provider.IsActive)}
        </div>
        ${field("رابط الـ Endpoint", `<input name="endpoint" dir="ltr" type="url" required value="${esc(s.Endpoint || "")}" placeholder="http://127.0.0.1:8001/..." class="${inputClass}">`)}
        <div class="grid grid-cols-2 gap-3">
          ${field("طريقة المصادقة", select("auth_scheme", ["x-api-key", "bearer"], s.AuthScheme || "x-api-key"))}
          ${field("المحوّل (Adapter)", select("adapter", ADAPTERS, s.Adapter || provider.ProviderId))}
          ${field("البروتوكول", `<input name="protocol" value="${esc(s.Protocol || "REST/JSON")}" class="${inputClass}">`)}
          ${field("المهلة (ثوانٍ)", `<input name="timeout" type="number" min="1" max="30" required value="${esc(s.Timeout ?? 5)}" class="${inputClass}">`)}
        </div>
        ${field("مفتاح المصادقة (API Key)", `<input name="auth_key" type="password" autocomplete="new-password" dir="ltr" class="${inputClass}">`, keyHint)}
        <div data-test-result class="hidden text-sm rounded-xl p-3"></div>
        <div class="flex justify-end gap-2">
          <button type="button" data-test class="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 font-bold text-sm">
            <i class="fa-solid fa-plug-circle-check ml-1"></i>اختبار الاتصال
          </button>
          <button type="submit" class="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-bold text-sm">حفظ</button>
        </div>
      </form>`;
  }

  async function saveApiSettings(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const values = Object.fromEntries(new FormData(form));
    values.timeout = Number(values.timeout);
    if (!values.auth_key) delete values.auth_key; // فارغ = الإبقاء على المفتاح الحالي

    const button = form.querySelector('button[type="submit"]');
    TH.setLoading(button, true, "جارٍ الحفظ…");
    try {
      await adminApi(
        `/api/admin/api-settings/${encodeURIComponent(form.dataset.api)}`,
        {
          method: "PUT",
          body: values,
        },
      );
      TH.toast("تم حفظ إعدادات API");
      loadApiSettings();
    } catch (error) {
      TH.toast(error.message, "error");
      TH.setLoading(button, false);
    }
  }

  /** يطلب من خدمة الوكلاء تنفيذ طلب تسعير تجريبي لهذه الشركة بإعداداتها الحالية. */
  async function testConnection(form) {
    const button = form.querySelector("[data-test]");
    const box = form.querySelector("[data-test-result]");
    TH.setLoading(button, true, "جارٍ الاختبار…");
    box.classList.add("hidden");
    try {
      const r = await adminApi(
        `/api/admin/providers/${encodeURIComponent(form.dataset.api)}/test`,
        {
          method: "POST",
        },
      );
      box.className = `text-sm rounded-xl p-3 ${r.ok ? "bg-brand-50 text-brand-700" : "bg-red-50 text-red-700"}`;
      box.innerHTML = r.ok
        ? `<i class="fa-solid fa-circle-check ml-1"></i>الاتصال ناجح — ${esc(r.offers_count)} عرض خلال ${esc(r.latency_ms)} ms`
        : `<i class="fa-solid fa-circle-xmark ml-1"></i>فشل الاتصال (${esc(r.error_type || "")}): ${esc(r.error_message || "")}`;
    } catch (error) {
      box.className = "text-sm rounded-xl p-3 bg-red-50 text-red-700";
      box.textContent = error.message;
    } finally {
      box.classList.remove("hidden");
      TH.setLoading(button, false);
    }
  }

  // ================================================================ سجل التوصيات
  let logsFilters = {};
  let logsTimer = null;

  function bindFilters() {
    const form = $("logs-filters");
    const apply = () => {
      logsFilters = Object.fromEntries(new FormData(form));
      loadLogs(1);
    };
    form.addEventListener("submit", (event) => event.preventDefault());
    form
      .querySelectorAll("select, input[type=date]")
      .forEach((el) => el.addEventListener("change", apply));
    form.q.addEventListener("input", () => {
      clearTimeout(logsTimer);
      logsTimer = setTimeout(apply, 350);
    });

    $("users-search").addEventListener("input", (event) => {
      clearTimeout(logsTimer);
      logsTimer = setTimeout(() => {
        usersQuery = event.target.value.trim();
        loadUsers(1);
      }, 350);
    });
  }

  function logsTable(items) {
    return table(
      [
        {
          label: "#",
          render: (r) =>
            `<span class="font-black text-slate-400">${esc(r.RequestId)}</span>`,
        },
        {
          label: "التاريخ",
          render: (r) =>
            `<span class="text-xs whitespace-nowrap">${esc(TH.formatDate(r.Timestamp))}</span>`,
        },
        { label: "المستخدم", render: (r) => esc(r.UserName || "—") },
        {
          label: "التغطية / الأولوية",
          render: (r) =>
            `<span class="text-xs">${esc(TH.coverageLabel(r.CoverageType))} · ${esc(TH.priorityLabel(r.Priority))}</span>`,
        },
        {
          label: "الحالة",
          render: (r) => TH.statusBadge(r.Status === "success", "ناجح", "فاشل"),
        },
        {
          label: "العرض المختار",
          render: (r) =>
            r.Status === "success"
              ? `<b>${esc(r.ProviderName || "—")}</b><div class="text-xs text-slate-400">${esc(r.PlanName || "")}</div>`
              : `<span class="text-xs text-red-600">${esc(r.ErrorMessage || "")}</span>`,
        },
        {
          label: "القسط",
          render: (r) =>
            `<span class="whitespace-nowrap">${TH.formatSAR(r.Premium)}</span>`,
        },
        { label: "التوافق", render: (r) => TH.formatScore(r.SuitabilityScore) },
        {
          label: "",
          render: (r) =>
            `<button type="button" data-log="${Number(r.RequestId)}" class="text-xs font-bold px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200">التفاصيل</button>`,
        },
      ],
      items,
    );
  }

  function bindLogDetails(host) {
    host
      .querySelectorAll("[data-log]")
      .forEach((button) =>
        button.addEventListener("click", () => openLog(button.dataset.log)),
      );
  }

  async function loadLogs(page) {
    $("logs-table").innerHTML = loadingBlock();
    try {
      const params = new URLSearchParams({
        ...logsFilters,
        page,
        pageSize: PAGE_SIZE,
      });
      [...params.keys()].forEach(
        (key) => !params.get(key) && params.delete(key),
      );
      const data = await adminApi(`/api/admin/logs?${params}`);
      const items = data.items || data.logs || [];
      $("logs-table").innerHTML = items.length
        ? logsTable(items)
        : emptyBlock("لا توجد سجلات مطابقة");
      bindLogDetails($("logs-table"));
      renderPager($("logs-pager"), page, data.total ?? items.length, loadLogs);
    } catch (error) {
      $("logs-table").innerHTML = errorBlock(error);
    }
  }

  async function openLog(requestId) {
    openModal(`طلب التوصية #${requestId}`, loadingBlock());
    try {
      const detail = await adminApi(
        `/api/admin/logs/${encodeURIComponent(requestId)}`,
      );
      const user = detail.user
        ? `<div class="mb-4 text-sm"><i class="fa-solid fa-user ml-1 text-slate-400"></i>
             <b>${esc(detail.user.UserName)}</b> <span class="text-slate-400">${esc(detail.user.Email || "")}</span></div>`
        : "";
      const statuses = TH.parseJson(detail.request?.ProviderStatus, []) || [];
      const statusTable = statuses.length
        ? `<section class="mt-6"><h3 class="font-black text-navy-800 mb-3">حالة الاتصال بالشركات</h3>
             <div class="overflow-x-auto rounded-2xl border border-slate-100">${table(
               [
                 {
                   label: "الشركة",
                   render: (s) => esc(s.provider_name || s.provider_id),
                 },
                 {
                   label: "الحالة",
                   render: (s) =>
                     TH.statusBadge(s.ok, "ناجح", s.error_type || "فشل"),
                 },
                 { label: "العروض", render: (s) => esc(s.offers_count ?? 0) },
                 { label: "المحاولات", render: (s) => esc(s.attempts ?? "—") },
                 {
                   label: "الزمن",
                   render: (s) => `${esc(s.latency_ms ?? "—")} ms`,
                 },
                 {
                   label: "ملاحظة",
                   render: (s) =>
                     `<span class="text-xs">${esc(s.error_message || "")}</span>`,
                 },
               ],
               statuses,
             )}</div></section>`
        : "";
      $("modal-body").innerHTML =
        user + TH.renderRequestDetail(detail) + statusTable;
    } catch (error) {
      $("modal-body").innerHTML = errorBlock(error);
    }
  }

  // ================================================================ سجل العمليات (Audit)
  const ACTION_LABELS = {
    "user.active": "تغيير حالة مستخدم",
    "user.activate": "تفعيل مستخدم",
    "user.deactivate": "تعطيل مستخدم",
    "provider.create": "إضافة شركة",
    "provider.update": "تعديل شركة",
    "provider.delete": "حذف شركة",
    "api-settings.update": "تعديل إعدادات API",
    "api_settings.update": "تعديل إعدادات API",
    "provider.test": "اختبار اتصال",
  };

  async function loadAudit(page) {
    $("audit-table").innerHTML = loadingBlock();
    try {
      const data = await adminApi(
        `/api/admin/audit?page=${page}&pageSize=${PAGE_SIZE}`,
      );
      const items = data.items || [];
      $("audit-table").innerHTML = items.length
        ? table(
            [
              {
                label: "التاريخ",
                render: (a) =>
                  `<span class="text-xs whitespace-nowrap">${esc(TH.formatDate(a.CreatedAt))}</span>`,
              },
              {
                label: "المسؤول",
                render: (a) =>
                  `<b>${esc(a.AdminUserName || a.AdminUserId || "—")}</b>`,
              },
              {
                label: "العملية",
                render: (a) => esc(ACTION_LABELS[a.Action] || a.Action),
              },
              {
                label: "الهدف",
                render: (a) =>
                  `<span class="text-xs font-mono">${esc(a.TargetType || "")} ${esc(a.TargetId ?? "")}</span>`,
              },
              {
                label: "التفاصيل",
                render: (a) => {
                  const details = TH.parseJson(a.Details, a.Details);
                  const text =
                    details && typeof details === "object"
                      ? JSON.stringify(details)
                      : details || "";
                  return `<code class="text-xs text-slate-500 break-all">${esc(String(text).slice(0, 160))}</code>`;
                },
              },
            ],
            items,
          )
        : emptyBlock("لا توجد عمليات مسجلة بعد");
      renderPager(
        $("audit-pager"),
        page,
        data.total ?? items.length,
        loadAudit,
      );
    } catch (error) {
      $("audit-table").innerHTML = errorBlock(error);
    }
  }
})();
