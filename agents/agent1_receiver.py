"""
Agent 1 - Data Receiver and Retrieval Agent
يستلم بيانات العميل، يتحقق منها، ويستعلم شركات التأمين (Mock)، ثم يوحّد الشكل.
لا يتخذ أي قرار — فقط يجمع وينظم البيانات لتمريرها لـ Agent 2.
"""

from mock_insurers import fetch_live_quotes


class DataReceiverAgent:
    def run(self, customer_data: dict) -> dict:
        # 1. التحقق من صحة المدخلات (تبسيط لغرض العرض)
        required = ["driver_age", "vehicle_value", "coverage_type"]
        missing = [f for f in required if f not in customer_data]
        if missing:
            raise ValueError(f"بيانات ناقصة: {missing}")

        driver_age = int(customer_data["driver_age"])
        vehicle_value = float(customer_data["vehicle_value"])
        coverage_type = customer_data["coverage_type"]

        # 2. استعلام شركات التأمين (متوازي في الإنتاج الحقيقي، هنا تسلسلي لأنه Mock)
        raw_quotes = fetch_live_quotes(driver_age, vehicle_value, coverage_type)

        # 3. توحيد الشكل (unified quote set) — جاهزة أصلاً بصيغة موحدة من الـ mock
        unified_quote_set = raw_quotes

        return {
            "customer_profile": customer_data,
            "unified_quote_set": unified_quote_set,
        }
