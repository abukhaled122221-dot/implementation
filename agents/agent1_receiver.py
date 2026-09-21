"""
Agent 1 - Data Receiver and Retrieval Agent
يستلم بيانات العميل، يتحقق منها، ويستعلم شركات التأمين من قاعدة البيانات، ثم يوحّد الشكل.
لا يتخذ أي قرار — فقط يجمع وينظم البيانات لتمريرها لـ Agent 2.
"""

import os
import mysql.connector
import random
from mysql.connector import Error


class DataReceiverAgent:
    def __init__(self):
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'thiqa')
        }

    def _get_db_connection(self):
        """Create and return a database connection."""
        try:
            connection = mysql.connector.connect(**self.db_config)
            return connection
        except Error as e:
            print(f"Error connecting to MySQL Database: {e}")
            return None

    def _get_providers_from_db(self):
        """Fetch insurance providers and their characteristics from the database."""
        connection = self._get_db_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT ProviderId, ProviderName, BaseRate, Reliability,
                       WorkshopNetwork, DigitalScore
                FROM Insurance_Providers
                ORDER BY ProviderId
            """
            cursor.execute(query)
            providers = cursor.fetchall()
            return providers
        except Error as e:
            print(f"Error fetching providers from database: {e}")
            return []
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    def run(self, customer_data: dict) -> dict:
        # 1. التحقق من صحة المدخلات (تبسيط لغرض العرض)
        required = ["driver_age", "vehicle_value", "coverage_type"]
        missing = [f for f in required if f not in customer_data]
        if missing:
            raise ValueError(f"بيانات ناقصة: {missing}")

        driver_age = int(customer_data["driver_age"])
        vehicle_value = float(customer_data["vehicle_value"])
        coverage_type = customer_data["coverage_type"]

        # 2. استعلام شركات التأمين من قاعدة البيانات
        providers = self._get_providers_from_db()
        if not providers:
            # Fallback to empty list if database is not available
            raw_quotes = []
        else:
            # 3. توليد عروض الأسعار باستخدام بيانات من قاعدة البيانات
            base = self._estimate_base_premium(vehicle_value, driver_age, coverage_type)
            raw_quotes = []

            for provider in providers:
                # تطبيق تفاوت عشوائي لمحاكاة تقلبات السوق الحقيقية
                variance = random.uniform(0.95, 1.08)
                premium = round(base * provider["BaseRate"] * variance, 2)
                deductible = round(random.choice([500, 750, 1000, 1500]), 2)
                add_ons = random.sample(
                    ["agency_repair", "roadside_assistance", "replacement_car", "windshield_cover", "gulf_coverage"],
                    k=random.randint(1, 3),
                )

                raw_quotes.append({
                    "quote_id": f"{provider['ProviderId']}_{random.randint(1000, 9999)}",
                    "provider_id": provider["ProviderId"],
                    "provider_name": provider["ProviderName"],
                    "premium": premium,
                    "coverage_type": coverage_type,
                    "deductible": deductible,
                    "add_ons": add_ons,
                    "reliability": provider["Reliability"],
                    "workshop_network": provider["WorkshopNetwork"],
                    "digital_score": provider["DigitalScore"],
                })

        # 4. توحيد الشكل (unified quote set) — جاهزة أصلاً بصيغة موحدة من قاعدة البيانات
        unified_quote_set = raw_quotes

        return {
            "customer_profile": customer_data,
            "unified_quote_set": unified_quote_set,
        }

    def _estimate_base_premium(self, vehicle_value: float, driver_age: int, coverage_type: str) -> float:
        """معادلة تقريبية بسيطة لتسعير القسط الأساسي (وهمية لأغراض العرض فقط)."""
        premium = vehicle_value * 0.02  # نسبة أساسية من قيمة المركبة

        # مخاطرة السائق حسب العمر
        if driver_age < 25:
            premium *= 1.4
        elif driver_age < 35:
            premium *= 1.1
        else:
            premium *= 1.0

        # نوع التغطية
        if coverage_type.lower() in ("comprehensive", "شامل"):
            premium *= 2.2
        else:  # TPL / ضد الغير
            premium *= 1.0

        return max(premium, 300)  # حد أدنى منطقي
