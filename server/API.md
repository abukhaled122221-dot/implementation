# Node API reference

JSON is used for all bodies. Customer and admin sessions use `thiqa_sid` and `thiqa_admin_sid` cookies. Protected endpoints return 401 when unauthenticated. List endpoints clamp `page` to at least 1 and `pageSize` to 1–100; legacy `limit` remains accepted.

| Method | Path | Auth | Parameters/body | Response |
|---|---|---|---|---|
| GET | `/api/health` | — | — | `{status,service}` |
| GET | `/api/config` | — | — | `{insurerPlatformUrl}` |
| POST | `/api/auth/register` | — | `{username,email,password,confirm_password}` or `confirmPassword` | 201 `{user}`; invalid input 422 `{error:"تحقق من البيانات المدخلة",errors:[{field,message}]}`; duplicates 409 with field error. |
| POST | `/api/auth/login` | — | `{identifier\|username\|email,password}` | `{user}` + customer cookie; invalid credentials 401 generic error; rate limit 429. |
| POST | `/api/auth/logout` | — | — | `{ok:true}` |
| GET | `/api/auth/me` | customer | — | `{user:{UserId,UserName,Email}}` |
| POST | `/api/recommend` | customer | Customer, vehicle, coverage, priority and add-on fields | Agents response plus `request_id`; successful data persisted transactionally and failures logged; agents timeout/unreachable 502. |
| GET | `/api/history?page=1&pageSize=10` | customer | legacy `limit` accepted | `{items:[{RequestId,Timestamp,CoverageType,Priority,Status,ErrorMessage,ProviderName,PlanName,Premium,SuitabilityScore}],total,page,pageSize}`; own requests only. |
| GET | `/api/history/:id` | customer | — | `{request:Quote_Requests row (RequestPayload and ProviderStatus parsed),quotes:[Retrieved_Quotes ordered by Rank, AddOns parsed, ProviderName],recommendation:{RecId,SelectedQuoteId,SuitabilityScore,CreatedAt}\|null,explanation:{MainReasons,CriteriaBreakdown parsed,ComparisonText}\|null}`; 404 if not owned. |
| POST | `/api/admin/login` | — | `{identifier\|username\|email,password}` | `{user:{UserId,UserName}}` + admin cookie |
| POST | `/api/admin/logout` | — | — | `{ok:true}` |
| GET | `/api/admin/me` | admin | — | `{user:{UserId,UserName}}` |
| GET | `/api/admin/overview` | admin | — | `{users:{total,active},requests:{total,today,success,failed,successRate},providers:{total,active},recent:[last 5 logs]}`; legacy overview fields retained. |
| GET | `/api/admin/users?q=&page=1&pageSize=20` | admin | legacy `search`, `limit` accepted | `{items:[{UserId,UserName,Email,IsAdmin,IsActive,CreatedAt,LastLoginAt,RequestsCount}],total,page,pageSize}`; q matches username/email. |
| PATCH | `/api/admin/users/:id` | admin | `{IsActive:0\|1}` or `{is_active:boolean}`; legacy `{active:boolean}` | `{ok:true}` |
| GET | `/api/admin/providers` | admin | — | `{items:[{ProviderId,ProviderName,Website,LogoUrl,IsActive,Reliability,WorkshopNetwork,DigitalScore,QuotesCount}]}` plus existing fields. |
| POST | `/api/admin/providers` | admin | `{provider_id,provider_name,website,logo_url,reliability,workshop_network,digital_score}`; legacy and PascalCase aliases accepted | 201 `{ok:true}` |
| PATCH | `/api/admin/providers/:id` | admin | Same fields optional plus `is_active`; legacy and PascalCase aliases accepted | `{ok:true}` |
| DELETE | `/api/admin/providers/:id` | admin | — | `{ok:true}`; referenced provider returns 409 `{error}`. |
| POST | `/api/admin/providers/:id/test` | admin | — | Proxied provider-test response; unreachable agents return 502 `{error}`. |
| GET | `/api/admin/api-settings` | admin | — | `{items:[{ProviderId,ProviderName,Endpoint,AuthScheme,Adapter,Protocol,Timeout,HasAuthKey,AuthKeyLast4}]}`; never returns AuthKey. |
| PUT | `/api/admin/api-settings/:providerId` | admin | `{endpoint,auth_scheme,adapter,protocol,timeout,auth_key?}` | `{ok:true}`; endpoint HTTP(S); scheme `x-api-key\|bearer`; adapter `tawuniya\|rajhi\|medgulf\|acig`; timeout integer 1–30; protocol defaults `REST/JSON`. Empty/missing key preserves existing key. |
| GET | `/api/admin/logs?status=success\|failed&q=&from=YYYY-MM-DD&to=YYYY-MM-DD&page=1&pageSize=20` | admin | legacy `search`, `limit` accepted | `{items:[{RequestId,Timestamp,UserName,CoverageType,Priority,Status,ErrorMessage,ProviderName,PlanName,Premium,SuitabilityScore,QuotesCount}],total,page,pageSize}`; filters affect both items and count. |
| GET | `/api/admin/logs/:id` | admin | — | History detail shape plus `user:{UserId,UserName,Email}`. |
| GET | `/api/admin/audit?page=1&pageSize=20` | admin | — | `{items:[{AuditId,CreatedAt,AdminUserName,Action,TargetType,TargetId,Details parsed}],total,page,pageSize}` |

Registration messages: `username` — `اسم المستخدم 3–30 حرفاً إنجليزياً أو أرقاماً أو _ .`; `email` — `البريد الإلكتروني غير صحيح`; `password` — `كلمة المرور 8 أحرف على الأقل وتحتوي حرفاً ورقماً`; `confirm_password` — `كلمتا المرور غير متطابقتين`. Duplicate username: `اسم المستخدم مستخدم مسبقاً`; duplicate email: `البريد الإلكتروني مسجل مسبقاً`.

Unknown `/api` routes return JSON 404. Malformed JSON returns JSON 400. Admin mutations write audit entries.
