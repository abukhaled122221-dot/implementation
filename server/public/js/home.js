/**
 * منطق الصفحة الرئيسية لثقة: نموذج إدخال البيانات ← تشغيل الوكلاء ← عرض التوصية.
 *
 * التدفق:
 *   1) العميل يعبّئ النموذج (يتطلب تسجيل الدخول).
 *   2) POST /api/recommend ← Node يمرره لخدمة الوكلاء (Agent 1 → 2 → 3) ويحفظ النتيجة.
 *   3) نعرض الباقة الفائزة + أسباب الاختيار (Agent 3) + بقية العروض مرتبة.
 *
 * دوال switchTab / handleFormSubmit / changePriorityOnTheFly عامة لأنها مربوطة
 * بخصائص onclick/onsubmit في index.html.
 */

// ------------------------------------------------------------------ الحالة
let INSURER_BASE_URL = "http://127.0.0.1:8001";
let lastRequestBody = null; // آخر طلب أُرسل (لإعادة الترتيب عند تغيير الأولوية)
let lastResult = null; // آخر رد من الخادم
const ALTERNATIVES_PREVIEW = 5; // عدد البدائل الظاهرة قبل زر "عرض الكل"

/** ألوان وشعارات مختصرة لشركات التأمين المعروفة (أي شركة جديدة تأخذ شعاراً عاماً). */
const PROVIDER_BADGES = {
  tawuniya: { color: "bg-emerald-600", label: "T" },
  rajhi: { color: "bg-blue-600", label: "R" },
  medgulf: { color: "bg-amber-500", label: "M" },
  acig: { color: "bg-red-600", label: "ACIG" },
};

/** ربط أسماء حقول الخادم (عقد C1) بعناصر النموذج لعرض الخطأ على الحقل الصحيح. */
const FIELD_ELEMENTS = {
  national_id: "idNumber",
  vehicle_serial: "sequenceNumber",
  birth_date: "birthYear",
  manufacture_year: "manufactureYear",
  vehicle_value: "vehicleValue",
  city: "customerCity",
  gender: "customerGender",
  has_accidents: "hasAccidents",
  cars_count: "carsCount",
  purpose_of_use: "vehiclePurpose",
  annual_mileage: "mileage",
  coverage_type: "coverageTypeSelect",
  priority: "userPriority",
};

const $ = (id) => document.getElementById(id);
const esc = (value) => TH.escapeHtml(value);

// ------------------------------------------------------------------ التهيئة
document.addEventListener("DOMContentLoaded", async () => {
  loadInsurerPlatformUrl();
  renderAddonOptions();
  $("manufactureYear").max = new Date().getFullYear() + 1;

  await TH.renderAuthNav();
  if (location.hash === "#recommendation") switchTab("tab-form");
});

/** رابط منصة شركات التأمين قد يختلف (محلياً أو على الاستضافة). */
async function loadInsurerPlatformUrl() {
  try {
    const config = await TH.api("/api/config");
    if (!config.insurerPlatformUrl) return;
    INSURER_BASE_URL = config.insurerPlatformUrl.replace(/\/$/, "");
    document
      .querySelectorAll('a[href^="http://127.0.0.1:8001"]')
      .forEach((link) => {
        link.href = link.href.replace(
          "http://127.0.0.1:8001",
          INSURER_BASE_URL,
        );
      });
  } catch {
    // نُبقي الرابط الافتراضي
  }
}

/** خيارات الإضافات كأزرار قابلة للاختيار (أوضح من مربعات صغيرة). */
function renderAddonOptions() {
  $("addons-options").innerHTML = Object.entries(TH.ADDON_LABELS)
    .map(
      ([code, label]) => `
        <label class="cursor-pointer">
          <input type="checkbox" name="addons" value="${code}" class="peer sr-only" />
          <span class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200
                       text-xs font-bold text-slate-600 transition hover:border-brand-500
                       peer-checked:bg-brand-50 peer-checked:border-brand-500 peer-checked:text-brand-700">
            <i class="fa-solid fa-plus text-[10px]"></i>${esc(label)}
          </span>
        </label>`,
    )
    .join("");
}

// ------------------------------------------------------------------ التنقل بين الأقسام
async function switchTab(tabId) {
  // نموذج الطلب يتطلب حساب عميل (متطلب User Authentication في التقرير)
  if (tabId === "tab-form" && !(await TH.currentCustomer())) {
    TH.goToLogin("/#recommendation");
    return;
  }
  document
    .querySelectorAll(".tab-content")
    .forEach((tab) => tab.classList.add("hidden"));
  $(tabId).classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ------------------------------------------------------------------ قراءة النموذج والتحقق منه
function collectRequestBody() {
  const pad = (n) => String(n).padStart(2, "0");
  return {
    national_id: $("idNumber").value.trim(),
    birth_date: `${$("birthYear").value}-${pad($("birthMonth").value)}-${pad($("birthDay").value)}`,
    vehicle_serial: $("sequenceNumber").value.trim(),
    manufacture_year: Number($("manufactureYear").value),
    vehicle_value: Number($("vehicleValue").value),
    purpose_of_use: $("vehiclePurpose").value,
    annual_mileage: $("mileage").value,
    coverage_type: $("coverageTypeSelect").value,
    priority: $("userPriority").value,
    city: $("customerCity").value,
    gender: $("customerGender").value,
    has_accidents: $("hasAccidents").value,
    cars_count: $("carsCount").value,
    requested_add_ons: [
      ...document.querySelectorAll('input[name="addons"]:checked'),
    ].map((box) => box.value),
  };
}

/** نفس قواعد Agent 1 تقريباً — لتنبيه العميل فوراً قبل الإرسال. */
function validateRequestBody(body) {
  const errors = [];
  const thisYear = new Date().getFullYear();
  const birth = new Date(body.birth_date);
  const age = (Date.now() - birth.getTime()) / (365.25 * 24 * 3600 * 1000);

  if (!/^[12]\d{9}$/.test(body.national_id)) {
    errors.push({
      field: "national_id",
      message: "رقم الهوية/الإقامة 10 أرقام ويبدأ بـ 1 أو 2",
    });
  }
  if (!/^[A-Za-z0-9]{6,17}$/.test(body.vehicle_serial)) {
    errors.push({
      field: "vehicle_serial",
      message: "الرقم التسلسلي 6–17 حرفاً إنجليزياً أو رقماً",
    });
  }
  if (Number.isNaN(birth.getTime()) || age < 18 || age > 90) {
    errors.push({
      field: "birth_date",
      message: "عمر السائق يجب أن يكون بين 18 و 90 سنة",
    });
  }
  if (!(
    body.manufacture_year >= 1990 && body.manufacture_year <= thisYear + 1
  )) {
    errors.push({
      field: "manufacture_year",
      message: `سنة الصنع بين 1990 و ${thisYear + 1}`,
    });
  }
  if (!(body.vehicle_value >= 5000 && body.vehicle_value <= 2000000)) {
    errors.push({
      field: "vehicle_value",
      message: "قيمة المركبة بين 5,000 و 2,000,000 ريال",
    });
  }
  return errors;
}

function clearFormErrors() {
  $("form-error").classList.add("hidden");
  document.querySelectorAll("#insuranceForm .border-red-400").forEach((el) => {
    el.classList.remove("border-red-400", "ring-2", "ring-red-100");
  });
}

function showFormErrors(message, errors = []) {
  const items = errors.map((e) => `<li>${esc(e.message)}</li>`).join("");
  $("form-error").innerHTML = items
    ? `<p class="mb-1">${esc(message)}</p><ul class="list-disc pr-5 font-medium">${items}</ul>`
    : esc(message);
  $("form-error").classList.remove("hidden");

  errors.forEach((error) => {
    const element = $(FIELD_ELEMENTS[error.field]);
    if (element)
      element.classList.add("border-red-400", "ring-2", "ring-red-100");
  });
  $("form-error").scrollIntoView({ behavior: "smooth", block: "center" });
}

// ------------------------------------------------------------------ الإرسال
async function handleFormSubmit(event) {
  event.preventDefault();
  clearFormErrors();

  const body = collectRequestBody();
  const errors = validateRequestBody(body);
  if (errors.length) {
    showFormErrors("يرجى تصحيح الحقول التالية:", errors);
    return;
  }

  lastRequestBody = body;
  await runRecommendation();
}

/** يرسل الطلب الحالي ويعرض النتيجة؛ يعود للنموذج مع رسالة واضحة عند الفشل. */
async function runRecommendation() {
  await switchTab("tab-pipeline");
  try {
    lastResult = await TH.api("/api/recommend", {
      method: "POST",
      body: lastRequestBody,
      onUnauthorized: () => TH.goToLogin("/#recommendation"),
    });
    renderResults();
    await switchTab("tab-results");
  } catch (error) {
    if (error.status === 401) return;
    await switchTab("tab-form");
    showFormErrors(
      error.message || "تعذر إتمام التحليل حالياً",
      error.data?.errors || [],
    );
  }
}

/** إعادة الترتيب بأولوية مختلفة لنفس البيانات (يحفظ كطلب جديد في السجل). */
async function changePriorityOnTheFly(priority) {
  if (!lastRequestBody || lastRequestBody.priority === priority) return;
  lastRequestBody = { ...lastRequestBody, priority };
  $("userPriority").value = priority;
  await runRecommendation();
}

// ------------------------------------------------------------------ عرض النتائج
function providerBadge(providerId, size = "w-12 h-12") {
  const badge = PROVIDER_BADGES[providerId] || {
    color: "bg-slate-700",
    label: String(providerId || "?")
      .slice(0, 2)
      .toUpperCase(),
  };
  return `<div class="${size} ${badge.color} text-white font-black rounded-xl flex items-center
                      justify-center text-xs shrink-0">${esc(badge.label)}</div>`;
}

/** رابط صفحة العرض في موقع شركة التأمين مع تمرير بيانات العميل لإكمال الشراء. */
function buildCompanyOfferUrl(offer) {
  const body = lastRequestBody;
  const age = Math.floor(
    (Date.now() - new Date(body.birth_date).getTime()) /
      (365.25 * 24 * 3600 * 1000),
  );
  const params = new URLSearchParams({
    selected_offer: "1",
    coverage: body.coverage_type,
    premium: Math.round(offer.premium),
    deductible: offer.deductible ?? "",
    plan: offer.plan_name || "",
    national_id: body.national_id,
    serial: body.vehicle_serial,
    age,
    city: body.city,
    gender: body.gender,
    accidents: body.has_accidents,
    cars: body.cars_count,
  });
  return `${INSURER_BASE_URL}/${encodeURIComponent(offer.provider_id)}?${params}`;
}

function addonChips(codes, style = "bg-white/10 text-slate-100") {
  if (!codes || !codes.length)
    return `<span class="text-xs opacity-70">لا توجد إضافات</span>`;
  return codes
    .map(
      (
        code,
      ) => `<span class="inline-block px-2.5 py-1 rounded-lg text-xs font-bold ${style}">
                   ${esc(TH.addonLabel(code))}</span>`,
    )
    .join(" ");
}

function renderResults() {
  const offers = lastResult.all_offers_ranked || [];
  const winner = lastResult.recommended_package || offers[0];
  const explanation = lastResult.explanation || {};
  const body = lastRequestBody;

  // ملخص الطلب
  $("res-id").textContent = body.national_id;
  $("res-seq").textContent = body.vehicle_serial;
  $("result-priority-lbl").textContent = TH.priorityLabel(body.priority);
  highlightPriorityButton(body.priority);

  // الباقة الفائزة
  const winnerUrl = buildCompanyOfferUrl(winner);
  $("winner-logo-container").innerHTML = providerBadge(winner.provider_id);
  $("winner-company-name").textContent = winner.provider_name;
  $("winner-coverage-type").textContent =
    (winner.plan_name ? winner.plan_name + " — " : "") +
    TH.coverageLabel(winner.coverage_type);
  $("winner-price").textContent = TH.formatSAR(winner.premium);
  $("winner-top-btn").href = winnerUrl;

  // التوفير مقارنةً بأغلى عرض مؤهل (وليس آخر عرض في الترتيب)
  const highest = Math.max(...offers.map((offer) => Number(offer.premium)));
  const savings = Math.round(highest - Number(winner.premium));
  $("winner-savings").textContent =
    savings > 0
      ? `توفر ${TH.formatSAR(savings)} مقارنة بأغلى عرض`
      : "أفضل قيمة مقابل التغطية";

  $("winner-explanation").innerHTML = renderExplanation(winner, explanation);
  $("winner-buy-container").innerHTML = `
    <a href="${esc(winnerUrl)}" target="_blank" rel="noopener"
       class="w-full bg-brand-500 hover:bg-brand-600 text-white font-black py-4 px-6 rounded-2xl
              transition flex items-center justify-center gap-2 text-sm shadow-lg">
      إكمال الشراء في موقع ${esc(winner.provider_name)}
      <i class="fa-solid fa-arrow-up-right-from-square"></i>
    </a>`;

  renderProviderStatus(lastResult.provider_status || []);
  renderAlternatives(
    offers.filter((offer) => offer.quote_id !== winner.quote_id),
  );
}

/** شرح Agent 3: السبب الرئيسي + المعايير + نقاط القوة + الإضافات + المقارنة. */
function renderExplanation(winner, explanation) {
  const criteria = (explanation.criteria_explanations || [])
    .map(
      (
        text,
      ) => `<li class="flex gap-2"><i class="fa-solid fa-check text-brand-400 mt-1"></i>
                      <span>${esc(text)}</span></li>`,
    )
    .join("");
  const strengths = (explanation.strengths || [])
    .map(
      (
        text,
      ) => `<span class="inline-block px-2.5 py-1 rounded-lg text-xs font-bold
                                 bg-brand-500/20 text-brand-100">${esc(text)}</span>`,
    )
    .join(" ");

  const matched = winner.requested_add_ons_matched || [];
  const missing = winner.requested_add_ons_missing || [];
  const requestedBlock =
    matched.length || missing.length
      ? `<div class="text-xs space-y-1.5">
           ${
             matched.length
               ? `<div><span class="text-brand-300 font-bold ml-1">✓ متوفر مما طلبت:</span>
             ${addonChips(matched, "bg-brand-500/20 text-brand-100")}</div>`
               : ""
           }
           ${
             missing.length
               ? `<div><span class="text-amber-300 font-bold ml-1">✗ غير متوفر:</span>
             ${addonChips(missing, "bg-amber-500/20 text-amber-100")}</div>`
               : ""
           }
         </div>`
      : "";

  return `
    <div class="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-4">
      <h4 class="font-bold text-brand-400 text-sm">
        <i class="fa-solid fa-user-tie ml-1"></i>لماذا اخترنا لك هذا العرض؟
      </h4>
      <p class="text-slate-200 text-sm leading-relaxed">${esc(explanation.main_reasons || "")}</p>
      ${criteria ? `<ul class="text-sm text-slate-200 space-y-1.5">${criteria}</ul>` : ""}
      ${strengths ? `<div class="flex flex-wrap gap-2">${strengths}</div>` : ""}
    </div>
    <div class="grid sm:grid-cols-2 gap-3 text-sm">
      <div class="bg-white/5 rounded-xl p-3">
        <span class="text-xs text-slate-400 block">نسبة التوافق</span>
        <b class="text-lg">${TH.formatScore(winner.suitability_score)}</b>
      </div>
      <div class="bg-white/5 rounded-xl p-3">
        <span class="text-xs text-slate-400 block">مبلغ التحمل</span>
        <b class="text-lg">${TH.formatSAR(winner.deductible)}</b>
      </div>
    </div>
    <div class="space-y-2">
      <div class="text-xs text-slate-400">الإضافات المشمولة في الباقة:</div>
      <div class="flex flex-wrap gap-1.5">${addonChips(winner.add_ons)}</div>
      ${requestedBlock}
    </div>
    ${
      explanation.comparison
        ? `<p class="text-xs text-slate-400 leading-relaxed border-t border-white/10 pt-3">
           ${esc(explanation.comparison)}</p>`
        : ""
    }`;
}

/** تنبيه لطيف إذا تعذر الوصول لبعض الشركات (النظام يكمل بالباقي — متطلب Reliability). */
function renderProviderStatus(statuses) {
  const failed = statuses.filter((status) => status.ok === false);
  const box = $("provider-status");
  box.classList.toggle("hidden", failed.length === 0);
  box.innerHTML = failed.length
    ? `<i class="fa-solid fa-triangle-exclamation ml-1"></i>
       تعذر الحصول على عروض من: <b>${failed.map((s) => esc(s.provider_name || s.provider_id)).join("، ")}</b>
       — تمت المقارنة بين العروض المتاحة من بقية الشركات.`
    : "";
}

function renderAlternatives(alternatives) {
  const container = $("alternatives-container");
  if (!alternatives.length) {
    container.innerHTML = `<p class="text-sm text-slate-500">لا توجد عروض بديلة مؤهلة.</p>`;
    return;
  }

  const row = (offer, hidden) => `
    <div class="${hidden ? "hidden extra-alternative " : ""}flex flex-col sm:flex-row sm:items-center
                justify-between p-4 rounded-2xl border border-slate-100 bg-slate-50 gap-4">
      <div class="flex items-center gap-3 min-w-0">
        <span class="text-xs font-black text-slate-400 w-6 text-center">#${esc(offer.rank)}</span>
        ${providerBadge(offer.provider_id, "w-10 h-10")}
        <div class="min-w-0">
          <h4 class="font-bold text-navy-800 text-sm">${esc(offer.provider_name)}</h4>
          <p class="text-xs text-slate-500 truncate">${esc(offer.plan_name || "")}</p>
          <p class="text-xs text-slate-500 mt-1">
            التوافق <b class="text-slate-700">${TH.formatScore(offer.suitability_score)}</b>
            · التحمل <b class="text-slate-700">${TH.formatSAR(offer.deductible)}</b>
            · ${(offer.add_ons || []).length} إضافات
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <span class="font-black text-slate-800 text-lg">${TH.formatSAR(offer.premium)}</span>
        <a href="${esc(buildCompanyOfferUrl(offer))}" target="_blank" rel="noopener"
           class="bg-brand-600 hover:bg-brand-700 text-white px-4 py-2.5 rounded-xl text-xs
                  font-bold transition flex items-center gap-1.5">
          عرض <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
        </a>
      </div>
    </div>`;

  const extra = alternatives.length - ALTERNATIVES_PREVIEW;
  container.innerHTML =
    alternatives
      .map((offer, i) => row(offer, i >= ALTERNATIVES_PREVIEW))
      .join("") +
    (extra > 0
      ? `<button type="button" id="show-all-alternatives"
           class="w-full py-3 rounded-xl border border-dashed border-slate-300 text-sm font-bold
                  text-slate-600 hover:bg-slate-50">عرض كل العروض (${extra} إضافية)</button>`
      : "");

  $("show-all-alternatives")?.addEventListener("click", (event) => {
    document
      .querySelectorAll(".extra-alternative")
      .forEach((el) => el.classList.remove("hidden"));
    event.currentTarget.remove();
  });
}

function highlightPriorityButton(active) {
  ["Budget", "Service", "Digital", "Balanced"].forEach((priority) => {
    const button = $(`btn-p-${priority}`);
    if (!button) return;
    const isActive = priority === active;
    button.classList.toggle("bg-brand-600", isActive);
    button.classList.toggle("text-white", isActive);
    button.classList.toggle("border-brand-600", isActive);
    button.classList.toggle("bg-white", !isActive);
    button.classList.toggle("text-slate-700", !isActive);
    button.classList.toggle("border-slate-200", !isActive);
  });
}
