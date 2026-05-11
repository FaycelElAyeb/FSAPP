/* =========================================================
   نظام التنبؤ المبكر بالتعثر الأكاديمي
   Frontend Controller
========================================================= */

let reportData = null;
let allStudents = [];
let currentStudents = [];
let charts = {};
let currentFilter = 'all';
let selectedStudent = null;

/* =========================================================
   DOM
========================================================= */

const gradebookInput = document.getElementById('gradebookInput');
const analyticsInput = document.getElementById('analyticsInput');
const analyzeBtn = document.getElementById('analyzeBtn');

const loadingOverlay = document.getElementById('loadingOverlay');

const uploadSection = document.getElementById('uploadSection');
const reportSection = document.getElementById('reportSection');

const studentsBody = document.getElementById('studentsBody');
const kpiGrid = document.getElementById('kpiGrid');

const searchInput = document.getElementById('searchInput');

const newAnalysisBtn = document.getElementById('newAnalysisBtn');
const downloadBtn = document.getElementById('downloadBtn');

/* ===== EMAIL MODAL ===== */

const emailModal = document.getElementById('emailModal');
const modalClose = document.getElementById('modalClose');
const modalCancel = document.getElementById('modalCancel');
const modalSend = document.getElementById('modalSend');

const emailTo = document.getElementById('emailTo');
const emailSubject = document.getElementById('emailSubject');
const emailBody = document.getElementById('emailBody');

/* =========================================================
   FILE SELECTION
========================================================= */

gradebookInput.addEventListener('change', () => {

    if (gradebookInput.files[0]) {

        document.getElementById('gradebookName').textContent =
            gradebookInput.files[0].name;

        document.getElementById('gradebookCheck').textContent = '✅';

        document
            .getElementById('gradebookBox')
            .classList.add('has-file');
    }

    checkReady();
});

analyticsInput.addEventListener('change', () => {

    if (analyticsInput.files[0]) {

        document.getElementById('analyticsName').textContent =
            analyticsInput.files[0].name;

        document.getElementById('analyticsCheck').textContent = '✅';

        document
            .getElementById('analyticsBox')
            .classList.add('has-file');
    }

    checkReady();
});

function checkReady() {

    analyzeBtn.disabled = !(
        gradebookInput.files[0] &&
        analyticsInput.files[0]
    );
}

/* =========================================================
   ANALYZE
========================================================= */

analyzeBtn.addEventListener('click', async () => {

    try {

        loadingOverlay.style.display = 'flex';

        const formData = new FormData();

        formData.append(
            'gradebook',
            gradebookInput.files[0]
        );

        formData.append(
            'analytics',
            analyticsInput.files[0]
        );

        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || 'فشل التحليل'
            );
        }

        reportData = data;

        allStudents = data.students || [];

        renderReport(data);

        uploadSection.style.display = 'none';

        reportSection.style.display = 'block';

        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });

    } catch (err) {

        console.error(err);

        alert('❌ ' + err.message);

    } finally {

        loadingOverlay.style.display = 'none';
    }
});

/* =========================================================
   RENDER REPORT
========================================================= */

function renderReport(data) {

    renderKPIs(data.summary || {});

    renderCharts(data);

    renderTable(data.students || []);
}

/* =========================================================
   KPI
========================================================= */

function renderKPIs(summary) {

    const total =
        summary.total ||
        summary.total_students ||
        0;

    const atRisk =
        summary.atRisk ||
        summary.at_risk_count ||
        0;

    const safe = total - atRisk;

    const avgGrade =
        summary.avgGrade ||
        summary.avg_grade ||
        0;

    const passRate =
        summary.passRate ||
        summary.pass_rate ||
        0;

    const avgHours =
        summary.avgHours ||
        summary.avg_hours ||
        0;

    const avgMissed =
        summary.avgMissed ||
        summary.avg_missed ||
        0;

    const avgDays =
        summary.avgDays ||
        summary.avg_days ||
        0;

    kpiGrid.innerHTML = `

        <div class="kpi-card info">
            <div class="kpi-icon">👥</div>
            <div class="kpi-value">${total}</div>
            <div class="kpi-label">إجمالي الطلاب</div>
        </div>

        <div class="kpi-card danger">
            <div class="kpi-icon">⚠️</div>
            <div class="kpi-value">${atRisk}</div>
            <div class="kpi-label">طلاب في خطر</div>
        </div>

        <div class="kpi-card success">
            <div class="kpi-icon">✅</div>
            <div class="kpi-value">${safe}</div>
            <div class="kpi-label">طلاب بأمان</div>
        </div>

        <div class="kpi-card info">
            <div class="kpi-icon">📊</div>
            <div class="kpi-value">${avgGrade}%</div>
            <div class="kpi-label">متوسط الدرجات</div>
        </div>

        <div class="kpi-card success">
            <div class="kpi-icon">🎯</div>
            <div class="kpi-value">${passRate}%</div>
            <div class="kpi-label">نسبة النجاح</div>
        </div>

        <div class="kpi-card info">
            <div class="kpi-icon">⏱️</div>
            <div class="kpi-value">${avgHours}h</div>
            <div class="kpi-label">متوسط ساعات المقرر</div>
        </div>

        <div class="kpi-card warning">
            <div class="kpi-icon">🗓️</div>
            <div class="kpi-value">${avgMissed}</div>
            <div class="kpi-label">متوسط المهام الفائتة</div>
        </div>

        <div class="kpi-card info">
            <div class="kpi-icon">📅</div>
            <div class="kpi-value">${avgDays}d</div>
            <div class="kpi-label">متوسط أيام منذ آخر وصول</div>
        </div>
    `;
}

/* =========================================================
   CHARTS
========================================================= */

function renderCharts(data) {

    destroyCharts();

    renderRiskChart(data);

    renderGradeChart(data);

    renderEngagementChart(data);

    renderTrendChart(data);
}

function destroyCharts() {

    Object.values(charts).forEach(chart => {

        if (chart) {
            chart.destroy();
        }
    });

    charts = {};
}

/* ===== RISK CHART ===== */

function renderRiskChart(data) {

    const ctx =
        document.getElementById('riskChart');

    if (!ctx) return;

    const dist =
        data.riskDist ||
        data.risk_distribution ||
        {};

    charts.risk = new Chart(ctx, {

        type: 'doughnut',

        data: {

            labels: Object.keys(dist),

            datasets: [{
                data: Object.values(dist),

                backgroundColor: [
                    '#2e7d32',
                    '#f57f17',
                    '#ef6c00',
                    '#c62828'
                ]
            }]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

/* ===== GRADE CHART ===== */

function renderGradeChart(data) {

    const ctx =
        document.getElementById('gradeChart');

    if (!ctx) return;

    const dist =
        data.gradeDist ||
        data.grade_distribution ||
        {};

    charts.grade = new Chart(ctx, {

        type: 'bar',

        data: {

            labels: Object.keys(dist),

            datasets: [{
                label: 'توزيع الدرجات',
                data: Object.values(dist),

                backgroundColor: [
                    '#1b5e20',
                    '#2e7d32',
                    '#f57f17',
                    '#e65100',
                    '#c62828'
                ],
                borderRadius: {
    topLeft: 8,
    topRight: 8,
    bottomLeft: 0,
    bottomRight: 0
}
            }]
        },

        options: {
    responsive: true,
    maintainAspectRatio: false,

    plugins: {
        legend: {
            display: false
        }
    }
}
    });
}

/* ===== ENGAGEMENT ===== */

function renderEngagementChart(data) {

    const ctx =
        document.getElementById('engagementChart');

    if (!ctx) return;

    const dist =
        data.engDist ||
        data.engagement_distribution ||
        {};

    charts.engagement = new Chart(ctx, {

        type: 'pie',

        data: {

            labels: Object.keys(dist),

            datasets: [{
                data: Object.values(dist),

                backgroundColor: [
                    '#1b5e20',
                    '#2e7d32',
                    '#f57f17',
                    '#c62828'
                ]
            }]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

/* ===== TREND ===== */

function renderTrendChart(data) {

    const ctx =
        document.getElementById('trendChart');

    if (!ctx) return;

    const dist =
        data.trendDist ||
        data.trend_distribution ||
        {};

    charts.trend = new Chart(ctx, {

        type: 'bar',

        data: {

            labels: Object.keys(dist),

            datasets: [{
                 label: 'اتجاه الأداء',
                data: Object.values(dist),

                backgroundColor: [
                    '#1b5e20',
                    '#0288d1',
                    '#c62828',
                    '#f57f17'
                ],
                borderRadius: {
    topLeft: 8,
    topRight: 8,
    bottomLeft: 0,
    bottomRight: 0
}
            }]
        },

        options: {
    responsive: true,
    maintainAspectRatio: false,

    plugins: {
        legend: {
            display: false
        }
    }
}
    });
}

/* =========================================================
   TABLE
========================================================= */

function renderTable(students) {

    currentStudents = students;

    studentsBody.innerHTML = '';

    students.forEach((student, index) => {

        const riskColor =
            getRiskColor(student.risk_level);

        const tr =
            document.createElement('tr');

        tr.innerHTML = `

            <td>${index + 1}</td>

            <td>
                <strong>${student.name || '-'}</strong>
            </td>

            <td>
                ${(student.total_grade || 0).toFixed(1)}%
            </td>

            <td>
                ${(student.exam_avg || 0).toFixed(1)}%
            </td>

            <td>
                ${(student.hours_spent || 0).toFixed(2)} h
            </td>

            <td>
                ${student.last_access || '-'}
            </td>

            <td>
                ${student.days_since_access || '-'} يوم
            </td>

            <td>
                <span
                    class="risk-badge"
                    style="
                        background:${riskColor};
                        color:white;
                    "
                >
                    ${student.risk_level || '-'}
                </span>
            </td>

            <td>
                <div class="risk-bar-wrap">

                    <span>
                        ${student.risk_score || 0}
                    </span>

                    <div class="risk-bar">

                        <div
                            class="risk-bar-fill"
                            style="
                                width:${student.risk_score || 0}%;
                                background:${riskColor};
                            "
                        ></div>

                    </div>

                </div>
            </td>

            <td>
                ${student.engagement || '-'}
            </td>

            <td>
                ${getTrendHTML(student.trend)}
            </td>

            <td class="rec-cell">
                ${student.recommendations || '-'}
            </td>

            <td>

                <button
                    class="btn-email"
                    onclick="openEmailModal(${index})"
                >
                    <i class="fas fa-envelope"></i>
                    إرسال بريد
                </button>

            </td>
        `;

        studentsBody.appendChild(tr);
    });
}

/* =========================================================
   TREND HTML
========================================================= */

function getTrendHTML(trend) {

    switch (trend) {

        case 'متحسن':
            return `
                <span class="trend-up">
                    <i class="fas fa-arrow-up"></i>
                    متحسن
                </span>
            `;

        case 'متراجع':
            return `
                <span class="trend-down">
                    <i class="fas fa-arrow-down"></i>
                    متراجع
                </span>
            `;

        case 'متذبذب':
            return `
                <span class="trend-wave">
                    <i class="fas fa-wave-square"></i>
                    متذبذب
                </span>
            `;

        default:
            return `
                <span class="trend-stable">
                    <i class="fas fa-arrow-right"></i>
                    مستقر
                </span>
            `;
    }
}

/* =========================================================
   FILTERS
========================================================= */

document.querySelectorAll('.filter-btn')
.forEach(btn => {

    btn.addEventListener('click', () => {

        document
            .querySelectorAll('.filter-btn')
            .forEach(b => b.classList.remove('active'));

        btn.classList.add('active');

        currentFilter =
            btn.dataset.filter;

        applyFilters();
    });
});

searchInput.addEventListener('input', applyFilters);

function applyFilters() {

    const search =
        searchInput.value.toLowerCase();

    let filtered =
        [...allStudents];

    if (currentFilter !== 'all') {

        filtered = filtered.filter(student =>
            student.risk_level === currentFilter
        );
    }

    if (search) {

        filtered = filtered.filter(student =>

            (student.name || '')
                .toLowerCase()
                .includes(search)
        );
    }

    renderTable(filtered);
}

/* =========================================================
   NEW ANALYSIS
========================================================= */

newAnalysisBtn.addEventListener('click', () => {

    reportSection.style.display = 'none';

    uploadSection.style.display = 'block';

    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

/* =========================================================
   DOWNLOAD REPORT
========================================================= */

downloadBtn.addEventListener('click', async () => {

    try {

        downloadBtn.disabled = true;
        downloadBtn.innerHTML =
            '<i class="fas fa-spinner fa-spin"></i> جارٍ التنزيل';

        let response = await fetch('/api/download-report', {
            method: 'GET'
        });

        if (!response.ok) {
            response = await fetch('/api/download-report', {
                method: 'POST'
            });
        }

        if (!response.ok) {
            response = await fetch('/api/export-excel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(reportData || {})
            });
        }

        if (!response.ok) {
            throw new Error('فشل تنزيل التقرير');
        }

        const blob = await response.blob();

        const url = window.URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = 'academic_report.xlsx';

        document.body.appendChild(a);
        a.click();
        a.remove();

        window.URL.revokeObjectURL(url);

    } catch (err) {

        console.error(err);
        alert('❌ ' + err.message);

    } finally {

        downloadBtn.disabled = false;
        downloadBtn.innerHTML =
            '<i class="fas fa-file-excel"></i> تنزيل تقرير Excel';
    }
});

/* =========================================================
   EMAIL MODAL
========================================================= */

function openEmailModal(index) {

    const student =
        currentStudents[index];

    selectedStudent = student;

    emailFrom.textContent =
        'elayebfaycel@gmail.com';

    emailTo.textContent =
        student.email ||
        `${student.student_id}@qu.edu.sa`;

    emailSubject.textContent =
        `تقرير أكاديمي - ${student.name}`;

    const statusMap = {
    'منخفض': 'جيد ✅',
    'متوسط': 'متوسط ⚠️',
    'مرتفع': 'يحتاج متابعة 🔶',
    'حرج': 'في خطر 🔴',
    'غير محدد': 'غير محدد'
};

const status =
    statusMap[student.risk_level] ||
    student.risk_level;

const message = `عزيزي الطالب ${student.name}،

السلام عليكم ورحمة الله وبركاته،

نود إبلاغك بتقريرك الأكاديمي الخاص بالمقرر الدراسي:

📊 الدرجة الكلية: ${student.total_grade || '-'}%
📝 متوسط الاختبارات: ${student.exam_avg || '-'}%
⏱️ ساعات المقرر: ${student.hours_spent || '0.00'} h
📅 تاريخ آخر وصول: ${student.last_access || '-'}
📆 أيام منذ آخر تفاعل: ${student.days_since_access || '-'} يوم
🎯 مستوى التفاعل: ${student.engagement || '-'}
🔔 الحالة الأكاديمية: ${status}

${student.risk_level === 'حرج' || student.risk_level === 'مرتفع'
  ? '⚠️ نرجو منك الاهتمام بالمقرر وزيادة التفاعل والمشاركة، والتواصل مع أستاذ المقرر في أقرب وقت.'
  : student.risk_level === 'متوسط'
  ? '📌 أداؤك في المستوى المتوسط، ننصحك بزيادة وقت الدراسة والمراجعة المنتظمة.'
  : '✅ أداؤك جيد، استمر في التميز والمثابرة.'}

يرجى تحسين أدائك في حال الحاجة، ونحن هنا لدعمك.
مع تحيات أستاذ المقرر 🎓`;

    emailBody.textContent = message;

    emailModal.style.display = 'flex';
}

function closeEmailModal() {

    emailModal.style.display = 'none';

    selectedStudent = null;
}

/* ===== CLOSE EVENTS ===== */

modalClose.addEventListener(
    'click',
    closeEmailModal
);

modalCancel.addEventListener(
    'click',
    closeEmailModal
);

emailModal.addEventListener('click', e => {

    if (e.target === emailModal) {

        closeEmailModal();
    }
});

/* =========================================================
   SEND EMAIL
========================================================= */

modalSend.addEventListener(
    'click',
    sendEmail
);

async function sendEmail() {

    if (!selectedStudent) return;

    try {

        modalSend.disabled = true;

        modalSend.innerHTML =
            '<i class="fas fa-spinner fa-spin"></i> جارٍ الإرسال';

        const response =
            await fetch('/api/send-email', {

                method: 'POST',

                headers: {
                    'Content-Type': 'application/json'
                },

                body: JSON.stringify({
                    student_id:
                        selectedStudent.student_id,

                    student_name:
                        selectedStudent.name,

                    risk_level:
                        selectedStudent.risk_level,

                    recommendations:
                        selectedStudent.recommendations
                })
            });

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error || 'فشل إرسال البريد'
            );
        }

        modalSend.innerHTML =
            '<i class="fas fa-check"></i> تم الإرسال';

        setTimeout(() => {

            closeEmailModal();

            modalSend.disabled = false;

            modalSend.innerHTML =
                '<i class="fas fa-paper-plane"></i> إرسال';

        }, 1500);

    } catch (err) {

        console.error(err);

        alert('❌ ' + err.message);

        modalSend.disabled = false;

        modalSend.innerHTML =
            '<i class="fas fa-paper-plane"></i> إرسال';
    }
}

/* =========================================================
   HELPERS
========================================================= */

function getRiskColor(level) {

    return {

        'منخفض': '#2e7d32',

        'متوسط': '#f57f17',

        'مرتفع': '#ef6c00',

        'حرج': '#c62828',

        'غير محدد': '#9e9e9e'

    }[level] || '#9e9e9e';
}
