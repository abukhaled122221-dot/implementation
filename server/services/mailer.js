/**
 * Password-reset email delivery for THIQA.
 * Without SMTP, local development prints the reset link to the Node terminal.
 * With SMTP configured, delivery failures are logged without exposing the token.
 */
function smtpConfigured() {
  return Boolean(
    process.env.SMTP_HOST && process.env.SMTP_USER && process.env.SMTP_PASS,
  );
}

function buildMessage({ username, link, expiresMinutes }) {
  const subject = "ثقة — إعادة تعيين كلمة المرور";
  const text =
    "مرحباً " + username + "،\n\n" +
    "وصلنا طلب لإعادة تعيين كلمة المرور لحسابك في منصة ثقة.\n" +
    "لتعيين كلمة مرور جديدة افتح الرابط التالي (صالح لمدة " + expiresMinutes + " دقيقة ولمرة واحدة):\n\n" +
    link + "\n\n" +
    "إذا لم تطلب ذلك فتجاهل هذه الرسالة، وستبقى كلمة مرورك الحالية كما هي.\n\n" +
    "منصة ثقة للتأمين الذكي";
  const html =
    '<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;line-height:1.8">' +
    "<p>مرحباً " + escapeHtml(username) + "،</p>" +
    "<p>وصلنا طلب لإعادة تعيين كلمة المرور لحسابك في منصة ثقة.</p>" +
    '<p><a href="' + escapeHtml(link) + '" style="display:inline-block;background:#059669;color:#fff;' +
    'padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:bold">تعيين كلمة مرور جديدة</a></p>' +
    '<p style="color:#64748b;font-size:13px">الرابط صالح لمدة ' + expiresMinutes + " دقيقة ولمرة واحدة. " +
    "إذا لم تطلب ذلك فتجاهل هذه الرسالة.</p></div>";
  return { subject, text, html };
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
}

function logToConsole(to, link, expiresMinutes) {
  console.log(
    "\n[THIQA] لا يوجد خادم بريد (SMTP) — رابط إعادة تعيين كلمة المرور:\n" +
      "  المستخدم: " + to + "\n  الرابط:   " + link + "\n  الصلاحية: " + expiresMinutes + " دقيقة\n",
  );
}

let transport;
function getTransport() {
  if (transport !== undefined) return transport;
  const nodemailer = require("nodemailer");
  const port = Number(process.env.SMTP_PORT || 465);
  transport = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port,
    secure: process.env.SMTP_SECURE === "1" || port === 465,
    auth: {
      user: process.env.SMTP_USER,
      // Google displays App Passwords with spaces; SMTP expects the compact value.
      pass: String(process.env.SMTP_PASS || "").replace(/\s/g, ""),
    },
  });
  return transport;
}

/** Sends the reset link by SMTP, or logs it locally when SMTP is not configured. */
async function sendPasswordReset({ to, username, link, expiresMinutes }) {
  const message = buildMessage({ username, link, expiresMinutes });

  if (process.env.SMTP_HOST && !smtpConfigured()) {
    console.error(
      "[THIQA] SMTP_HOST is set but SMTP_USER or SMTP_PASS is missing; reset email was not sent.",
    );
    return "unavailable";
  }

  if (!smtpConfigured()) {
    logToConsole(to, link, expiresMinutes);
    return "console";
  }

  try {
    await getTransport().sendMail({
      from: process.env.MAIL_FROM || process.env.SMTP_USER,
      to,
      ...message,
    });
    return "smtp";
  } catch (error) {
    console.error("[THIQA] Password-reset email delivery failed:", error.message);
    // Never print a live reset token to logs when SMTP is configured.
    throw error;
  }
}

module.exports = { sendPasswordReset, buildMessage };
