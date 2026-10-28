/**
 * منطق صفحتي تسجيل الدخول وإنشاء الحساب للعميل.
 * التحقق في المتصفح لتجربة أسرع فقط؛ الخادم يعيد التحقق دائماً.
 */
(() => {
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const form = loginForm || registerForm;
  if (!form) return;

  const formError = document.getElementById("form-error");
  const USERNAME_RE = /^[A-Za-z0-9_.]{3,30}$/;
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // تمرير ?next= لرابط الصفحة الأخرى حتى يرجع المستخدم لنفس المكان بعد الدخول
  const nextParam = new URLSearchParams(location.search).get("next");
  if (nextParam) {
    const otherLink = document.getElementById(
      loginForm ? "register-link" : "login-link",
    );
    if (otherLink) otherLink.href += "?next=" + encodeURIComponent(nextParam);
  }

  // إذا كان العميل مسجلاً مسبقاً لا داعي لعرض الصفحة
  TH.currentCustomer().then((user) => {
    if (user) location.replace(TH.safeNext());
  });

  // ---------------------------------------------------------------- رسائل الأخطاء
  function setFieldError(field, message) {
    const box = form.querySelector(`[data-error="${field}"]`);
    const input = form.querySelector(`[name="${field}"]`);
    if (box) box.textContent = message || "";
    if (input) input.classList.toggle("border-red-400", Boolean(message));
  }

  function clearErrors() {
    form
      .querySelectorAll("[data-error]")
      .forEach((box) => setFieldError(box.dataset.error, ""));
    formError.classList.add("hidden");
  }

  function showFormError(message) {
    formError.textContent = message;
    formError.classList.remove("hidden");
  }

  // ---------------------------------------------------------------- إظهار/إخفاء كلمة المرور
  form.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.togglePassword);
      const hidden = input.type === "password";
      input.type = hidden ? "text" : "password";
      button.innerHTML = `<i class="fa-solid ${hidden ? "fa-eye-slash" : "fa-eye"}"></i>`;
    });
  });

  // ---------------------------------------------------------------- قواعد كلمة المرور (التسجيل)
  const passwordRules = {
    length: (p) => p.length >= 8,
    letter: (p) => /[A-Za-z]/.test(p),
    digit: (p) => /\d/.test(p),
  };

  if (registerForm) {
    registerForm.password.addEventListener("input", () => {
      const value = registerForm.password.value;
      Object.entries(passwordRules).forEach(([rule, test]) => {
        const item = document.querySelector(`[data-rule="${rule}"]`);
        const ok = test(value);
        item.classList.toggle("text-brand-600", ok);
        item.classList.toggle("text-slate-400", !ok);
      });
    });
  }

  function validateRegister(values) {
    const errors = {};
    if (!USERNAME_RE.test(values.username)) {
      errors.username =
        "اسم المستخدم 3–30 حرفاً إنجليزياً أو أرقاماً أو ( _ . )";
    }
    if (!EMAIL_RE.test(values.email))
      errors.email = "البريد الإلكتروني غير صحيح";
    if (!Object.values(passwordRules).every((test) => test(values.password))) {
      errors.password = "كلمة المرور 8 أحرف على الأقل وتحتوي حرفاً ورقماً";
    }
    if (values.password !== values.confirm_password) {
      errors.confirm_password = "كلمتا المرور غير متطابقتين";
    }
    return errors;
  }

  function validateLogin(values) {
    const errors = {};
    if (!values.identifier)
      errors.identifier = "أدخل اسم المستخدم أو البريد الإلكتروني";
    if (!values.password) errors.password = "أدخل كلمة المرور";
    return errors;
  }

  // ---------------------------------------------------------------- الإرسال
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();

    const values = Object.fromEntries(new FormData(form));
    Object.keys(values).forEach((key) => {
      if (!key.includes("password")) values[key] = values[key].trim();
    });

    const errors = registerForm
      ? validateRegister(values)
      : validateLogin(values);
    if (Object.keys(errors).length) {
      Object.entries(errors).forEach(([field, message]) =>
        setFieldError(field, message),
      );
      return;
    }

    const button = form.querySelector('button[type="submit"]');
    TH.setLoading(
      button,
      true,
      registerForm ? "جارٍ إنشاء الحساب…" : "جارٍ تسجيل الدخول…",
    );
    try {
      const endpoint = registerForm ? "/api/auth/register" : "/api/auth/login";
      await TH.api(endpoint, { method: "POST", body: values });
      location.href = TH.safeNext();
    } catch (error) {
      const fieldErrors = error.data?.errors || [];
      fieldErrors.forEach((item) => setFieldError(item.field, item.message));
      if (!fieldErrors.length || error.status === 429)
        showFormError(error.message);
      TH.setLoading(button, false);
    }
  });
})();
