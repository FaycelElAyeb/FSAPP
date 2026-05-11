import os
import re
import math
import numpy as np
import pandas as pd
import xlsxwriter
import yagmail


class AcademicAnalyzer:
    def __init__(self, gradebook_path, analytics_path):
        self.gradebook_path = gradebook_path
        self.analytics_path = analytics_path

        self.gradebook_rows = []
        self.analytics_rows = []

        self.report = None

        self._load_data()

    # =========================================================
    # FILE READING
    # =========================================================

    def _load_data(self):
        self.gradebook_rows = self._read_file(self.gradebook_path, "Gradebook")
        self.analytics_rows = self._read_file(self.analytics_path, "Analytics")

        if not self.gradebook_rows:
            raise Exception("ملف Gradebook فارغ أو لا يحتوي على بيانات")

        if not self.analytics_rows:
            raise Exception("ملف Analytics فارغ أو لا يحتوي على بيانات")

    def _read_file(self, file_path, file_name):
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".csv":
                return self._read_csv(file_path)

            if ext in [".xls", ".xlsx"]:
                return self._read_excel(file_path)

            raise Exception(f"صيغة الملف غير مدعومة: {ext}")

        except Exception as e:
            raise Exception(f"خطأ في قراءة ملف {file_name}: {str(e)}")

    def _read_csv(self, file_path):
        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False
        )

        df.columns = [str(c).strip() for c in df.columns]

        rows = []

        for _, row in df.iterrows():
            obj = {}
            for col in df.columns:
                obj[col] = str(row[col]).strip()
            rows.append(obj)

        return rows

    def _read_excel(self, file_path):

        try:

            raw = pd.read_csv(
                file_path,
                sep='\t',
                encoding='utf-16',
                header=None,
                dtype=object,
                keep_default_na=False
            )

        except Exception:

            raw = pd.read_excel(
                file_path,
                engine='openpyxl',
                header=None,
                dtype=object,
                keep_default_na=False
            )

        arr = raw.fillna("").values.tolist()

        if len(arr) < 2:
            return []

        header_row_idx = self._detect_header_row(arr)

        headers = [
            str(c).strip()
            for c in arr[header_row_idx]
        ]

        data_rows = []

        for row in arr[header_row_idx + 1:]:
            if not any(str(v).strip() for v in row):
                continue

            obj = {}

            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else ""
                value = "" if value is None else str(value).strip()

                if header:
                    obj[header] = value

                obj[f"__c{i}"] = value

            # Same idea as old app.js:
            # column 0 = last name, column 1 = first name, column 2 = username/id
            obj["__lastName"] = str(row[0]).strip() if len(row) > 0 else ""
            obj["__firstName"] = str(row[1]).strip() if len(row) > 1 else ""
            obj["__studentId"] = str(row[2]).strip() if len(row) > 2 else ""

            data_rows.append(obj)

        return data_rows

    def _detect_header_row(self, arr):
        best_idx = 0
        best_text_count = 0

        for i in range(min(len(arr), 10)):
            text_count = 0

            for cell in arr[i]:
                s = str(cell).strip()

                if not s:
                    continue

                if self._is_number(s):
                    continue

                if re.match(r"^\d{4}-\d{2}-\d{2}", s):
                    continue

                text_count += 1

            if text_count > best_text_count:
                best_text_count = text_count
                best_idx = i

        return best_idx

    # =========================================================
    # BASIC HELPERS — PORTED FROM APP.JS
    # =========================================================

    def _to_num(self, value):
        if value is None:
            return math.nan

        s = str(value).strip()

        if s == "" or s == "-":
            return math.nan

        s = re.sub(r"[^0-9.\-]", "", s)

        if s == "":
            return math.nan

        try:
            return float(s)
        except Exception:
            return math.nan

    def _to_num_or_zero(self, value):
        n = self._to_num(value)
        return 0 if math.isnan(n) else n

    def _is_number(self, value):
        try:
            float(str(value).strip())
            return True
        except Exception:
            return False

    def _round(self, value, digits=1):
        if value is None:
            return math.nan

        if isinstance(value, float) and math.isnan(value):
            return math.nan

        return round(float(value), digits)

    def _avg(self, values):
        values = [
            float(v)
            for v in values
            if v is not None and not math.isnan(float(v))
        ]

        if not values:
            return 0

        return sum(values) / len(values)

    def _std(self, values):
        values = [
            float(v)
            for v in values
            if v is not None and not math.isnan(float(v))
        ]

        if not values:
            return 0

        mean = self._avg(values)

        return math.sqrt(
            sum((v - mean) ** 2 for v in values) / len(values)
        )

    def _count_by(self, rows, key_func):
        result = {}

        for row in rows:
            key = key_func(row)
            result[key] = result.get(key, 0) + 1

        return result

    def _find_col_in_row(self, row, keywords):
        keys = list(row.keys())

        # exact
        for key in keys:
            key_lower = str(key).lower().strip()

            for kw in keywords:
                if key_lower == str(kw).lower().strip():
                    return key

        # partial
        for key in keys:
            key_lower = str(key).lower().strip()

            for kw in keywords:
                kw_lower = str(kw).lower().strip()

                if kw_lower in key_lower or key_lower in kw_lower:
                    return key

        return None

    def _clean_name(self, name):
        name = str(name or "").strip()
        name = re.sub(r"[^\u0600-\u06FFa-zA-Z\s]", "", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name or "غير متوفر"

    # =========================================================
    # RISK / ENGAGEMENT / TREND — SAME APP.JS LOGIC
    # =========================================================

    def _calc_risk(self, grade, missed, hours, days, below50):
        score = 0

        g = 0 if self._is_nan(grade) else grade

        # الدرجة الكلية - المؤشر الأساسي
        if g < 50:
            score += 40
        elif g < 60:
            score += 30
        elif g < 70:
            score += 20
        elif g < 80:
            score += 10
        elif g < 90:
            score += 5

        # المهام والاختبارات الفائتة
        if missed >= 10:
            score += 35
        elif missed >= 7:
            score += 25
        elif missed >= 5:
            score += 20
        elif missed >= 3:
            score += 12
        elif missed >= 1:
            score += 5

        # أيام الغياب
        if days > 21:
            score += 20
        elif days > 14:
            score += 15
        elif days > 7:
            score += 10

        # ساعات الدراسة
        if hours < 1:
            score += 15
        elif hours < 3:
            score += 7
        elif hours < 5:
            score += 3

        # اختبارات أقل من 50%
        if below50 > 3:
            score += 10
        elif below50 > 1:
            score += 5

        return min(int(score), 100)

    def _risk_level(self, grade):
        if self._is_nan(grade) or grade <= 0:
            return "غير محدد"

        if grade >= 80:
            return "منخفض"

        if grade >= 60:
            return "متوسط"

        if grade >= 50:
            return "مرتفع"

        return "حرج"

    def _risk_color(self, level):
        return {
            "منخفض": "#27ae60",
            "متوسط": "#f39c12",
            "مرتفع": "#e67e22",
            "حرج": "#e74c3c",
            "غير محدد": "#95a5a6",
        }.get(level, "#95a5a6")

    def _engagement(self, hours, days):
        if hours > 10 and days < 3:
            return "ممتاز"

        if hours > 5 and days < 7:
            return "جيد"

        if hours > 2 and days < 14:
            return "متوسط"

        return "ضعيف"

    def _trend(self, sd, av, mn, mx):
        if sd == 0:
            return "مستقر"

        cv = sd / av if av > 0 else 0

        if cv < 0.15:
            return "مستقر"

        if mx - mn > 30:
            return "متذبذب"

        if av >= 70:
            return "تحسن"

        return "تراجع"

    def _recommendations(self, grade, missed, hours, days, below50):
        recs = []

        if self._is_nan(grade) or grade < 50:
            recs.append("⚠️ تدخل عاجل: جلسة دعم فردية")

        if missed > 3:
            recs.append("📅 متابعة الواجبات الفائتة")

        if days > 14:
            recs.append("📧 إرسال تنبيه للطالب")

        if hours < 2:
            recs.append("⏱️ زيادة وقت الدراسة")

        if below50 > 2:
            recs.append("📚 مراجعة المفاهيم الأساسية")

        if not recs:
            recs.append("✅ الطالب يسير بشكل جيد")

        return " | ".join(recs)

    def _is_nan(self, value):
        try:
            return value is None or math.isnan(float(value))
        except Exception:
            return True

    # =========================================================
    # COLUMN DETECTION — SAME IDEA AS APP.JS
    # =========================================================

    def _detect_total_grade_col(self, gradebook_rows):
        sample = gradebook_rows[0]
        keys = list(sample.keys())

        for key in keys:
            if "Overall Grade" in key or "إجمالي النقاط: حتى" in key:
                return key

        for key in keys:
            lower = key.lower()

            if (
                "overall" in lower
                or "total" in lower
                or "التقدير الكلي" in key
                or "الدرجة الكلية" in key
            ):
                return key

        return None

    def _extract_max_grade(self, total_col):
        max_grade = 100

        if not total_col:
            return max_grade

        nums = re.findall(r"\d+(?:\.\d+)?", str(total_col))

        if nums:
            candidates = [
                float(n)
                for n in nums
                if 20 <= float(n) <= 200 and float(n) != 1956436
            ]

            if candidates:
                max_grade = candidates[0]

        return max_grade

    def _extract_col_max(self, col_name):
        text = str(col_name)

        # same app.js idea: match Arabic "من 4" / "من 0.5"
        m = re.search(r"من\s*(\d+(?:\.\d+)?)", text)

        if m:
            return float(m.group(1))

        # Blackboard headers often include: إجمالي النقاط: 0.5النتيجة
        nums = re.findall(r"\d+(?:\.\d+)?", text)

        candidates = []

        for n in nums:
            value = float(n)

            if 0 < value <= 200 and value != 1956436:
                candidates.append(value)

        if candidates:
            return candidates[0]

        return 100

    def _detect_exam_cols(self, gradebook_rows, total_col):
        sample = gradebook_rows[0]
        keys = list(sample.keys())

        exam_cols = []

        for key in keys:
            if key == total_col:
                continue

            lower = str(key).lower()

            if key.startswith("__c"):
                idx = int(key.replace("__c", "")) if key.replace("__c", "").isdigit() else -1

                if idx < 5:
                    continue

            looks_like_exam = any(x in lower for x in [
                "test",
                "quiz",
                "assign",
                "activity",
                "unit",
                "اختبار",
                "واجب",
                "نشاط",
                "أعمال"
            ])

            if not looks_like_exam and not key.startswith("__c"):
                continue

            vals = []

            for row in gradebook_rows:
                v = self._to_num(row.get(key, ""))

                if not self._is_nan(v) and v >= 0:
                    vals.append(v)

            if len(vals) < 3:
                continue

            max_val = max(vals)

            if max_val <= 100 and max_val > 0:
                exam_cols.append(key)

        return exam_cols

    # =========================================================
    # ANALYSIS — PORTED FROM APP.JS
    # =========================================================

    def generate_full_report(self):
        if self.report:
            return self.report

        gb_rows = self.gradebook_rows
        an_rows = self.analytics_rows

        total_col_gb = self._detect_total_grade_col(gb_rows)
        max_grade = self._extract_max_grade(total_col_gb)

        exam_cols = self._detect_exam_cols(gb_rows, total_col_gb)

        an_sample = an_rows[0]

        first_name_col_an = self._find_col_in_row(an_sample, [
            "الاسم الأول",
            "الاسم الاول"
        ])

        last_name_col_an = self._find_col_in_row(an_sample, [
            "الاسم الأخير",
            "اسم العائلة",
            "الاسم الاخير"
        ])

        username_col_an = self._find_col_in_row(an_sample, [
            "اسم المستخدم",
            "username",
            "user"
        ])

        total_col_an = self._find_col_in_row(an_sample, [
            "التقدير الكلي",
            "التقدير الكلي المعدل",
            "Overall Grade",
            "total",
            "final",
            "grade",
            "الكلي",
            "الإجمالي",
            "overall"
        ])

        missed_col = self._find_col_in_row(an_sample, [
            "تنبيه بخصوص توزيع الاستحقاق الفائتة",
            "تواريخ الاستحقاق الفائتة",
            "الاستحقاق الفائتة",
            "missed",
            "due",
            "فائتة",
            "متأخر",
            "missing",
            "overdue"
        ])

        hours_col = self._find_col_in_row(an_sample, [
            "عدد الساعات في المقرر الدراسي",
            "عدد الساعات في المقرر",
            "ساعات في المقرر الدراسي",
            "عدد الساعات",
            "hours"
        ])

        days_col = self._find_col_in_row(an_sample, [
            "عدد الأيام منذ آخر وصول",
            "أيام منذ آخر وصول",
            "عدد الأيام",
            "days since",
            "days"
        ])

        last_access_col = self._find_col_in_row(an_sample, [
            "تاريخ آخر وصول",
            "آخر وصول",
            "last access",
            "last login"
        ])

        # Build analytics master list
        analytics_master = []

        for row in an_rows:
            first = str(row.get(first_name_col_an, "")).strip() if first_name_col_an else ""
            last = str(row.get(last_name_col_an, "")).strip() if last_name_col_an else ""

            full_name = self._clean_name(f"{first} {last}")

            username = ""
            if username_col_an:
                username = str(row.get(username_col_an, "")).strip()

            student_id = str(
                row.get("معرف الطالب")
                or row.get("اسم المستخدم")
                or username
                or ""
            ).strip()

            analytics_master.append({
                "total_an": self._to_num(row.get(total_col_an, "")) if total_col_an else math.nan,
                "missed_deadlines": self._to_num_or_zero(row.get(missed_col, 0)) if missed_col else 0,
                "hours_spent": self._to_num_or_zero(row.get(hours_col, 0)) if hours_col else 0,
                "days_since_access": self._to_num_or_zero(row.get(days_col, 0)) if days_col else 0,
                "last_access": str(row.get(last_access_col, "")).strip() if last_access_col else "",
                "firstName": first,
                "lastName": last,
                "fullName": full_name,
                "username": username,
                "studentId": student_id
            })

        # Build gradebook map by ID / username
        gb_map_by_id = {}

        for row in gb_rows:
            uid = str(
                row.get("اسم المستخدم")
                or row.get("معرف الطالب")
                or row.get("__studentId")
                or ""
            ).strip()

            if uid:
                gb_map_by_id[uid] = row

        students = []

        for an in analytics_master:
            name = (
                an["fullName"]
                or an["firstName"]
                or an["lastName"]
                or "غير متوفر"
            )

            student_id = an["studentId"] or an["username"] or ""

            gb_row = gb_map_by_id.get(student_id, {})

            gb_raw_grade = self._to_num(
                gb_row.get(total_col_gb, "")
            ) if total_col_gb else math.nan

            if not self._is_nan(gb_raw_grade) and gb_raw_grade >= 0:
                total_grade = self._round(
                    gb_raw_grade / max_grade * 100
                )
            else:
                an_grade = self._to_num(an["total_an"])
                total_grade = self._round(an_grade) if not self._is_nan(an_grade) and an_grade >= 0 else math.nan

            exam_scores = []

            for col in exam_cols:
                v = self._to_num(gb_row.get(col, ""))

                if self._is_nan(v) or v < 0:
                    continue

                col_max = self._extract_col_max(col)

                score = self._round(v / col_max * 100)

                if not self._is_nan(score) and 0 <= score <= 100:
                    exam_scores.append(score)

            if exam_scores:
                exam_avg = self._round(self._avg(exam_scores))
                exam_std = self._std(exam_scores) if len(exam_scores) > 1 else 0
                exam_min = min(exam_scores)
                exam_max = max(exam_scores)
            else:
                exam_avg = math.nan if self._is_nan(total_grade) else total_grade
                exam_std = 0
                exam_min = math.nan if self._is_nan(total_grade) else total_grade
                exam_max = math.nan if self._is_nan(total_grade) else total_grade

            below50 = len([v for v in exam_scores if v < 50])

            missed = an["missed_deadlines"] or 0
            hours = an["hours_spent"] or 0
            days = an["days_since_access"] or 0
            last_access = an["last_access"] or ""

            risk_score = self._calc_risk(
                total_grade,
                missed,
                hours,
                days,
                below50
            )

            risk_level = self._risk_level(total_grade)

            engagement = self._engagement(
                hours,
                days
            )

            trend = self._trend(
                exam_std,
                exam_avg if not self._is_nan(exam_avg) else 0,
                exam_min if not self._is_nan(exam_min) else 0,
                exam_max if not self._is_nan(exam_max) else 0
            )

            recs = self._recommendations(
                total_grade,
                missed,
                hours,
                days,
                below50
            )

            at_risk = (
                risk_score >= 30
                or (
                    not self._is_nan(total_grade)
                    and total_grade < 60
                )
            )

            students.append({
                # original app.js style
                "name": name,
                "totalGrade": None if self._is_nan(total_grade) else self._round(total_grade),
                "examAvg": None if self._is_nan(exam_avg) else self._round(exam_avg),
                "examStd": None if self._is_nan(exam_std) else self._round(exam_std),
                "examMin": None if self._is_nan(exam_min) else self._round(exam_min),
                "examMax": None if self._is_nan(exam_max) else self._round(exam_max),
                "missed": int(missed),
                "hours": self._round(hours),
                "days": int(days),
                "lastAccess": last_access,
                "below50": int(below50),
                "riskScore": int(risk_score),
                "riskLevel": risk_level,
                "engagement": engagement,
                "trend": trend,
                "recs": recs,
                "atRisk": bool(at_risk),
                "username": str(student_id).strip(),

                # backend/frontend compatibility aliases
                "student_id": str(student_id).strip(),
                "total_grade": None if self._is_nan(total_grade) else self._round(total_grade),
                "exam_avg": None if self._is_nan(exam_avg) else self._round(exam_avg),
                "exam_std": None if self._is_nan(exam_std) else self._round(exam_std),
                "exam_min": None if self._is_nan(exam_min) else self._round(exam_min),
                "exam_max": None if self._is_nan(exam_max) else self._round(exam_max),
                "missed_deadlines": int(missed),
                "hours_spent": self._round(hours),
                "days_since_access": int(days),
                "last_access": last_access,
                "exams_below_50": int(below50),
                "risk_score": int(risk_score),
                "risk_level": risk_level,
                "risk_color": self._risk_color(risk_level),
                "at_risk": bool(at_risk),
                "recommendations": recs,
            })

        """students.sort(
            key=lambda x: (
                -x["riskScore"],
                x["name"]
            )
        )"""
        students.sort(
        key=lambda x: -x["riskScore"]
        )

        total = len(students)

        grades = [
            s["totalGrade"]
            for s in students
            if s["totalGrade"] is not None and s["totalGrade"] > 0
        ]

        at_risk = len([
            s for s in students
            if s["atRisk"]
        ])

        avg_grade = self._avg(grades) if grades else 0

        pass_rate = (
            len([g for g in grades if g >= 60]) / len(grades) * 100
            if grades else 0
        )

        risk_dist = self._count_by(
            students,
            lambda s: s["riskLevel"]
        )

        eng_dist = self._count_by(
            students,
            lambda s: s["engagement"]
        )

        trend_dist = self._count_by(
            students,
            lambda s: s["trend"]
        )

        grade_dist = {
            "ممتاز (90-100)": len([g for g in grades if g >= 90]),
            "جيد جداً (80-89)": len([g for g in grades if 80 <= g < 90]),
            "جيد (70-79)": len([g for g in grades if 70 <= g < 80]),
            "مقبول (60-69)": len([g for g in grades if 60 <= g < 70]),
            "راسب (<60)": len([g for g in grades if g < 60]),
        }

        report = {
            "summary": {
                "total": total,
                "atRisk": at_risk,
                "safe": total - at_risk,
                "avgGrade": self._round(avg_grade),
                "passRate": self._round(pass_rate),
                "avgHours": self._round(self._avg([s["hours"] for s in students])),
                "avgMissed": self._round(self._avg([s["missed"] for s in students])),
                "avgDays": self._round(self._avg([s["days"] for s in students])),

                # old export aliases
                "total_students": total,
                "at_risk_count": at_risk,
                "safe_count": total - at_risk,
                "avg_grade": self._round(avg_grade),
                "pass_rate": self._round(pass_rate),
                "avg_hours": self._round(self._avg([s["hours"] for s in students])),
                "avg_missed": self._round(self._avg([s["missed"] for s in students])),
                "avg_days_access": self._round(self._avg([s["days"] for s in students])),
            },
            "riskDist": risk_dist,
            "engDist": eng_dist,
            "trendDist": trend_dist,
            "gradeDist": grade_dist,

            # old export aliases
            "risk_distribution": risk_dist,
            "engagement_distribution": eng_dist,
            "trend_distribution": trend_dist,
            "grade_distribution": grade_dist,

            "students": students,
        }

        self.report = report

        return report

    # =========================================================
    # EMAIL
    # =========================================================

    def send_email_notification(
        self,
        student_id,
        student_name,
        risk_level,
        recommendations,
        sender_email,
        sender_password,
        smtp_host,
        smtp_port,
        smtp_secure
    ):
        try:
            recipient_email = f"{student_id}@qu.edu.sa"

            subject = "تنبيه أكاديمي - حالة أدائك في المقرر"

            body = f"""
عزيزي الطالب {student_name},

نحن نتابع أداءك في المقرر الحالي من خلال نظام التنبؤ المبكر بالتعثر الأكاديمي.

حالة الخطر الحالية: {risk_level}

التوصيات المقترحة:
{recommendations}

يرجى التواصل مع المدرس أو المشرف الأكاديمي للحصول على الدعم اللازم.

مع خالص التحية،
فريق الدعم الأكاديمي
جامعة القصيم
"""

            yag = yagmail.SMTP(
                user=sender_email,
                password=sender_password,
                host=smtp_host,
                port=int(smtp_port),
                smtp_ssl=str(smtp_secure).lower() == "ssl",
                smtp_starttls=str(smtp_secure).lower() == "starttls",
                timeout=30
            )

            yag.send(
                to=recipient_email,
                subject=subject,
                contents=body
            )

            return True, "تم إرسال البريد بنجاح"

        except Exception as e:
            error_text = str(e)
            return False, f"خطأ في إرسال البريد: {error_text}"

    # =========================================================
    # EXCEL EXPORT
    # =========================================================

    def export_excel_report(self, output_dir):
        os.makedirs(output_dir, exist_ok=True)

        report = self.generate_full_report()

        path = os.path.join(
            output_dir,
            "academic_analytics_report.xlsx"
        )

        wb = xlsxwriter.Workbook(path)

        title_fmt = wb.add_format({
            "bold": True,
            "font_size": 16,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#1a237e",
            "font_color": "white",
            "border": 1
        })

        header_fmt = wb.add_format({
            "bold": True,
            "font_size": 11,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#283593",
            "font_color": "white",
            "border": 1,
            "text_wrap": True
        })

        cell_fmt = wb.add_format({
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "font_size": 10
        })

        summary_label_fmt = wb.add_format({
            "bold": True,
            "font_size": 12,
            "align": "right",
            "valign": "vcenter",
            "bg_color": "#e8eaf6",
            "border": 1
        })

        summary_val_fmt = wb.add_format({
            "bold": True,
            "font_size": 14,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#ffffff",
            "border": 1
        })

        # -------------------------
        # Summary sheet
        # -------------------------

        ws1 = wb.add_worksheet("ملخص تنفيذي")
        ws1.set_column("A:F", 22)
        ws1.set_row(0, 50)

        ws1.merge_range(
            "A1:F1",
            "نظام التنبؤ المبكر بالتعثر الأكاديمي - تقرير شامل",
            title_fmt
        )

        s = report["summary"]

        summary_data = [
            ("إجمالي الطلاب", s["total"]),
            ("الطلاب في خطر", s["atRisk"]),
            ("الطلاب بأمان", s["safe"]),
            ("متوسط الدرجات", f"{s['avgGrade']}%"),
            ("نسبة النجاح", f"{s['passRate']}%"),
            ("متوسط ساعات الدراسة", s["avgHours"]),
            ("متوسط المهام الفائتة", s["avgMissed"]),
            ("متوسط أيام الغياب", s["avgDays"]),
        ]

        ws1.merge_range(
            "A3:F3",
            "مؤشرات الأداء العامة",
            header_fmt
        )

        for i, (label, value) in enumerate(summary_data):
            row = 3 + i
            ws1.write(row, 0, label, summary_label_fmt)
            ws1.merge_range(row, 1, row, 5, value, summary_val_fmt)

        ws1.merge_range(
            12,
            0,
            12,
            5,
            "توزيع الدرجات",
            header_fmt
        )

        for i, (label, value) in enumerate(report["gradeDist"].items()):
            ws1.write(13 + i, 0, label, summary_label_fmt)
            ws1.merge_range(13 + i, 1, 13 + i, 5, value, summary_val_fmt)

        # -------------------------
        # Student details
        # -------------------------

        ws2 = wb.add_worksheet("تفاصيل الطلاب")

        headers = [
            "اسم الطالب",
            "معرف الطالب",
            "الدرجة الكلية",
            "متوسط الاختبارات",
            "أدنى درجة",
            "أعلى درجة",
            "المهام الفائتة",
            "ساعات الدراسة",
            "تاريخ آخر وصول",
            "أيام منذ آخر دخول",
            "مستوى الخطر",
            "درجة الخطر",
            "مستوى التفاعل",
            "اتجاه الأداء",
            "التوصيات"
        ]

        widths = [
            25, 18, 14, 18, 12, 12, 16, 16, 24, 20, 14, 14, 16, 16, 60
        ]

        for i, (header, width) in enumerate(zip(headers, widths)):
            ws2.write(0, i, header, header_fmt)
            ws2.set_column(i, i, width)

        for r, st in enumerate(report["students"], start=1):
            values = [
                st["name"],
                st["student_id"],
                st["total_grade"] if st["total_grade"] is not None else "غير متاح",
                st["exam_avg"] if st["exam_avg"] is not None else "غير متاح",
                st["exam_min"] if st["exam_min"] is not None else "غير متاح",
                st["exam_max"] if st["exam_max"] is not None else "غير متاح",
                st["missed_deadlines"],
                st["hours_spent"],
                st["last_access"],
                st["days_since_access"],
                st["risk_level"],
                st["risk_score"],
                st["engagement"],
                st["trend"],
                st["recommendations"],
            ]

            for c, value in enumerate(values):
                ws2.write(r, c, value, cell_fmt)

        # -------------------------
        # At-risk students
        # -------------------------

        ws3 = wb.add_worksheet("الطلاب في خطر")

        for i, (header, width) in enumerate(zip(headers, widths)):
            ws3.write(0, i, header, header_fmt)
            ws3.set_column(i, i, width)

        risky_students = [
            st for st in report["students"]
            if st["at_risk"]
        ]

        for r, st in enumerate(risky_students, start=1):
            values = [
                st["name"],
                st["student_id"],
                st["total_grade"] if st["total_grade"] is not None else "غير متاح",
                st["exam_avg"] if st["exam_avg"] is not None else "غير متاح",
                st["exam_min"] if st["exam_min"] is not None else "غير متاح",
                st["exam_max"] if st["exam_max"] is not None else "غير متاح",
                st["missed_deadlines"],
                st["hours_spent"],
                st["last_access"],
                st["days_since_access"],
                st["risk_level"],
                st["risk_score"],
                st["engagement"],
                st["trend"],
                st["recommendations"],
            ]

            for c, value in enumerate(values):
                ws3.write(r, c, value, cell_fmt)

        wb.close()

        return path