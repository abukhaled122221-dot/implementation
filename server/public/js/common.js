/**
 * أدوات مشتركة لواجهة ثقة (العميل ولوحة الأدمن).
 * كل الصفحات تستخدم window.TH بدل تكرار نفس الكود.
 */
window.TH = (() => {
  const HTML_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };

  /** يمنع حقن HTML (XSS) عند إدراج نص قادم من الخادم داخل innerHTML. */
  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
  }

  /**
   * طلب JSON موحّد. يرمي Error يحمل status و data عند فشل الطلب.
   * onUnauthorized: دالة اختيارية تُستدعى عند 401 (مثلاً للتحويل لصفحة الدخول).
   */
  async function api(url, { method = "GET", body, onUnauthorized } = {}) {
    let response;
    try {
      response = await fetch(url, {
        method,
        credentials: "same-origin",
        headers:
          body !== undefined ? { "Content-Type": "application/json" } : {},
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw Object.assign(
        new Error("تعذر الاتصال بالخادم. تحقق من تشغيل النظام."),
        { status: 0 },
      );
    }

    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      if (response.status === 401 && onUnauthorized) onUnauthorized();
      const error = new Error(data.error || "تعذر إتمام الطلب");
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  /** إشعار مؤقت أعلى الشاشة. type: success | error | info */
  function toast(message, type = "success") {
    let stack = document.getElementById("th-toasts");
    if (!stack) {
      stack = document.createElement("div");
      stack.id = "th-toasts";
      stack.className =
        "fixed top-4 left-4 z-[100] flex flex-col gap-2 max-w-sm";
      document.body.append(stack);
    }
    const colors = {
      success: "bg-brand-700",
      error: "bg-red-600",
      info: "bg-slate-800",
    };
    const icons = {
      success: "fa-circle-check",
      error: "fa-circle-exclamation",
      info: "fa-circle-info",
    };
    const item = document.createElement("div");
    item.className =
      `${colors[type] || colors.info} text-white text-sm font-bold px-4 py-3 ` +
      "rounded-xl shadow-lg flex items-center gap-2";
    item.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span></span>`;
    item.querySelector("span").textContent = message;
    stack.append(item);
    setTimeout(() => item.remove(), 4000);
  }

  /** يعطّل الزر ويعرض مؤشر تحميل أثناء تنفيذ طلب. */
  function setLoading(button, busy, label = "جارٍ التنفيذ…") {
    if (!button) return;
    if (busy) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${escapeHtml(label)}`;
    } else {
      button.disabled = false;
      if (button.dataset.originalHtml)
        button.innerHTML = button.dataset.originalHtml;
    }
  }

  /** يقبل فقط مسارات داخلية نسبية في ?next= لمنع إعادة التوجيه لمواقع خارجية. */
  function safeNext(fallback = "/") {
    const next = new URLSearchParams(location.search).get("next") || fallback;
    const isInternal =
      next.startsWith("/") && !next.startsWith("//") && !next.includes("\\");
    return isInternal ? next : fallback;
  }

  /** يرجع العميل الحالي أو null (بدون تحويل). */
  async function currentCustomer() {
    try {
      return (await api("/api/auth/me")).user || null;
    } catch {
      return null;
    }
  }

  /** تحويل لصفحة دخول العميل مع الرجوع لنفس الصفحة بعد الدخول. */
  function goToLogin(
    next = location.pathname + location.search + location.hash,
  ) {
    location.href = "/login.html?next=" + encodeURIComponent(next);
  }

  async function logoutCustomer() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      location.href = "/";
    }
  }

  /**
   * يعبئ منطقة الحساب في الهيدر (العنصر [data-auth-nav]) حسب حالة الدخول.
   * يرجع العميل الحالي أو null.
   */
  async function renderAuthNav() {
    const host = document.querySelector("[data-auth-nav]");
    const user = await currentCustomer();
    if (!host) return user;

    const link = "px-3 py-2 rounded-xl transition whitespace-nowrap";
    if (user) {
      host.innerHTML = `
        <a href="/history.html" class="${link} bg-slate-100 text-slate-700 hover:bg-slate-200">
          <i class="fa-solid fa-clock-rotate-left ml-1"></i>توصياتي السابقة
        </a>
        <span class="${link} bg-brand-50 text-brand-700">
          <i class="fa-solid fa-user ml-1"></i>${escapeHtml(user.UserName)}
        </span>
        <button type="button" data-logout
          class="${link} bg-slate-100 text-slate-700 hover:bg-red-50 hover:text-red-600">
          <i class="fa-solid fa-right-from-bracket ml-1"></i>خروج
        </button>`;
      host
        .querySelector("[data-logout]")
        .addEventListener("click", logoutCustomer);
    } else {
      host.innerHTML = `
        <a href="/login.html" class="${link} bg-brand-50 text-brand-700 hover:bg-brand-100">
          تسجيل الدخول
        </a>
        <a href="/register.html" class="${link} bg-brand-600 text-white hover:bg-brand-700">
          إنشاء حساب
        </a>`;
    }
    return user;
  }

  const ADDON_LABELS = {
    agency_repair: "إصلاح لدى الوكالة",
    roadside_assistance: "مساعدة على الطريق",
    replacement_car: "سيارة بديلة",
    windshield_cover: "تغطية الزجاج الأمامي",
    gulf_coverage: "تغطية دول الخليج",
  };

  const PRIORITY_LABELS = {
    Budget: "أقل سعر وميزانية اقتصادية",
    Service: "كفاءة الخدمة وسرعة المطالبة",
    Digital: "ميزات رقمية وتطبيق سهل",
    Balanced: "القيمة المتوازنة مقابل السعر",
  };

  const COVERAGE_LABELS = { TPL: "ضد الغير", Comprehensive: "شامل" };

  const addonLabel = (code) => ADDON_LABELS[code] || code;
  const priorityLabel = (code) => PRIORITY_LABELS[code] || code || "—";
  const coverageLabel = (code) => COVERAGE_LABELS[code] || code || "—";

  /** 1234.5 → "1,235 ر.س" */
  function formatSAR(value) {
    const n = Number(value);
    if (value === null || value === undefined || !Number.isFinite(n))
      return "—";
    return `${Math.round(n).toLocaleString("en-US")} ر.س`;
  }

  /** "2026-10-28 10:15:00" (بتوقيت UTC من SQLite) → تاريخ ووقت محلي مقروء */
  function formatDate(value) {
    if (!value) return "—";
    const text = String(value);
    const iso = text.includes("T") ? text : text.replace(" ", "T") + "Z";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return text;
    return date.toLocaleString("ar-SA-u-nu-latn-ca-gregory", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  /** 0.8421 → "84%" */
  function formatScore(score) {
    if (score === null || score === undefined || score === "") return "—";
    return `${Math.round(Number(score) * 100)}%`;
  }

  /** شارة حالة خضراء/حمراء */
  function statusBadge(ok, okText, failText) {
    const base =
      "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold";
    return ok
      ? `<span class="${base} bg-brand-50 text-brand-700">
           <i class="fa-solid fa-circle-check"></i>${escapeHtml(okText)}</span>`
      : `<span class="${base} bg-red-50 text-red-600">
           <i class="fa-solid fa-circle-xmark"></i>${escapeHtml(failText)}</span>`;
  }

  /** قيمة من أول مفتاح موجود (لتحمّل اختلاف تسمية الحقول بين نسخ الـ API). */
  function pick(obj, ...keys) {
    for (const key of keys) {
      if (obj && obj[key] !== undefined && obj[key] !== null) return obj[key];
    }
    return undefined;
  }

  /** يحوّل نص JSON إلى كائن بأمان (أو يرجعه كما هو). */
  function parseJson(value, fallback = null) {
    if (value === null || value === undefined) return fallback;
    if (typeof value !== "string") return value;
    try {
      return JSON.parse(value);
    } catch {
      return fallback;
    }
  }

  return {
    api,
    escapeHtml,
    toast,
    setLoading,
    safeNext,
    currentCustomer,
    goToLogin,
    logoutCustomer,
    renderAuthNav,
    addonLabel,
    priorityLabel,
    coverageLabel,
    formatSAR,
    formatDate,
    formatScore,
    statusBadge,
    pick,
    parseJson,
    ADDON_LABELS,
  };
})();
