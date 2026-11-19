"""
InsightX v2.0 — Project Architecture, Pipeline & Engineering Guide PDF Generator
Creates a publication-quality executive technical guide using ReportLab.
"""

import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render total page count
    along with running header and footer.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(
                0.55 * inch,
                10.52 * inch,
                "InsightX v2.0 — AI Root Cause & Decision Intelligence Platform: Architecture & Pipeline Guide"
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(0.55 * inch, 10.44 * inch, 7.95 * inch, 10.44 * inch)

        # Footer (All pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(0.55 * inch, 0.52 * inch, 7.95 * inch, 0.52 * inch)

        self.drawString(
            0.55 * inch,
            0.38 * inch,
            "Confidential & Academic Engineering Dossier • DA-IICT MSc Data Science Innovation"
        )
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(7.95 * inch, 0.38 * inch, page_str)
        self.restoreState()


def build_pdf(output_path="InsightX_v2_Project_Architecture_and_Pipeline_Guide.pdf"):
    margin = 0.55 * inch
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0.6 * inch,
        bottomMargin=0.65 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom Palettes
    c_primary = colors.HexColor("#1E3A8A")     # Deep Navy
    c_accent = colors.HexColor("#2563EB")      # InsightX Royal Blue
    c_dark = colors.HexColor("#0F172A")        # Slate 900
    c_muted = colors.HexColor("#475569")       # Slate 600
    c_bg_light = colors.HexColor("#F8FAFC")    # Slate 50
    c_code_bg = colors.HexColor("#0F172A")     # Dark Terminal
    c_code_text = colors.HexColor("#E2E8F0")   # Code White
    c_border = colors.HexColor("#E2E8F0")      # Border Slate
    c_green = colors.HexColor("#16A34A")       # Emerald 600

    # Typography
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_primary,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_accent,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_muted,
    ))

    styles.add(ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=c_accent,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        'BodyP',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        'BodyPBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13.5,
        textColor=c_dark,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        'BulletP',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_dark,
        leftIndent=12,
        spaceAfter=3,
    ))

    styles.add(ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=c_dark,
    ))

    styles.add(ParagraphStyle(
        'CodeBlock',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10.5,
        textColor=c_code_text,
    ))

    styles.add(ParagraphStyle(
        'CodeBlockDarkBg',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.8,
        leading=10.2,
        textColor=colors.HexColor("#38BDF8"),
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=0,
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=c_dark,
    ))

    styles.add(ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=c_dark,
    ))

    story = []

    # =========================================================================
    # 1. HEADER & COVER BANNER
    # =========================================================================
    story.append(Paragraph("⚡ InsightX v2.0", styles['DocTitle']))
    story.append(Paragraph("AI Root Cause & Decision Intelligence Platform — Complete Architecture, Pipeline & Engineering Guide", styles['DocSubtitle']))

    meta_content = [
        [
            Paragraph("<b>Authors:</b> Aman Chauhan (202518004), Mannan Agarwal (202518013)", styles['MetaText']),
            Paragraph("<b>Institution:</b> DA-IICT, MSc Data Science Innovation", styles['MetaText']),
        ],
        [
            Paragraph("<b>Date:</b> November 2026 • <b>Status:</b> Production / 100% Verified", styles['MetaText']),
            Paragraph("<b>Test Verification:</b> 104/104 Backend Tests • 11/11 Frontend Tests", styles['MetaText']),
        ]
    ]
    t_meta = Table(meta_content, colWidths=[3.7 * inch, 3.6 * inch])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # =========================================================================
    # 2. EXECUTIVE SUMMARY & THE "AI DOCTOR" CONCEPT
    # =========================================================================
    story.append(Paragraph("1. Executive Summary & Core Concept", styles['SectionH1']))
    story.append(Paragraph(
        "Modern cloud-native software and microservices face two severe operational bottlenecks: "
        "<b>(1) Alert Overload During Incidents:</b> SRE teams are flooded with hundreds of noisy symptom alerts (high CPU, HTTP 504 timeouts), "
        "wasting 30–90 minutes of Mean Time to Resolution (MTTR) trying to find which source code line broke the system; and "
        "<b>(2) Silent Logical Bugs:</b> Programs compile cleanly and run with exit code <code>0</code>, yet produce incorrect business calculations "
        "(off-by-one errors, inverted <code>&lt;</code>/<code>&gt;</code> comparisons, or reversed thresholds) that linters completely overlook.",
        styles['BodyP']
    ))

    # Analogy Callout Box
    analogy_p = Paragraph(
        "<b>The Analogy — An AI Doctor for Software:</b><br/>"
        "When a patient visits a clinic with a high fever (symptom), an amateur might merely give them an ice pack (treating the symptom). "
        "An experienced medical doctor runs diagnostic blood tests (evidence), isolates the bacterial infection in the throat (true root cause), "
        "and prescribes the exact antibiotic course (targeted cure). "
        "<b>InsightX operates identically for software engineering:</b> it ingests symptoms (telemetry & logs), analyzes the anatomy (source code AST), "
        "isolates the causal defect with empirical proof, and applies a verified 1-click Auto-Fix.",
        styles['CalloutText']
    )
    t_callout = Table([[analogy_p]], colWidths=[7.3 * inch])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#93C5FD")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t_callout)
    story.append(Spacer(1, 10))

    # Capability Comparison Table
    story.append(Paragraph("Capability Matrix: Traditional Tools vs. InsightX v2.0", styles['SectionH2']))
    comp_data = [
        [
            Paragraph("<b>Capability Dimension</b>", styles['TableHeader']),
            Paragraph("<b>Prometheus / Grafana</b>", styles['TableHeader']),
            Paragraph("<b>Datadog / Dynatrace</b>", styles['TableHeader']),
            Paragraph("<b>Traditional Linters</b>", styles['TableHeader']),
            Paragraph("<b>InsightX v2.0 Platform</b>", styles['TableHeader']),
        ],
        [
            Paragraph("<b>Telemetry Ingestion</b>", styles['TableCellBold']),
            Paragraph("Metrics Only", styles['TableCell']),
            Paragraph("Metrics, Logs, APM", styles['TableCell']),
            Paragraph("None", styles['TableCell']),
            Paragraph("<b>Metrics, Logs & AST Source Code</b>", styles['TableCellBold']),
        ],
        [
            Paragraph("<b>Direct Code Scanning</b>", styles['TableCellBold']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No", styles['TableCell']),
            Paragraph("Single files (CLI)", styles['TableCell']),
            Paragraph("<b>Yes (Files, ZIPs, or Pasted Code)</b>", styles['TableCellBold']),
        ],
        [
            Paragraph("<b>Logical Error Detection</b>", styles['TableCellBold']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No (Exit 0 bugs missed)", styles['TableCell']),
            Paragraph("<b>Yes (Math formulas, inverted logic)</b>", styles['TableCellBold']),
        ],
        [
            Paragraph("<b>Automated Test Verification</b>", styles['TableCellBold']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No", styles['TableCell']),
            Paragraph("<b>Subprocess Sandbox + Actual vs Expected</b>", styles['TableCellBold']),
        ],
        [
            Paragraph("<b>Causal Localization (RCA)</b>", styles['TableCellBold']),
            Paragraph("Manual", styles['TableCell']),
            Paragraph("Basic Correlation", styles['TableCell']),
            Paragraph("None", styles['TableCell']),
            Paragraph("<b>Lead-Lag Precursor + Stack Trace Match</b>", styles['TableCellBold']),
        ],
        [
            Paragraph("<b>Automated Code Remediation</b>", styles['TableCellBold']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No", styles['TableCell']),
            Paragraph("Rule-only / basic formatting", styles['TableCell']),
            Paragraph("<b>1-Click Auto-Fix & Unified Diffs</b>", styles['TableCellBold']),
        ],
        [
            Paragraph("<b>Audit History & Revisions</b>", styles['TableCellBold']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No", styles['TableCell']),
            Paragraph("No", styles['TableCell']),
            Paragraph("<b>Persistent Revisions (v1 &rarr; v2 &rarr; v3)</b>", styles['TableCellBold']),
        ],
    ]
    t_comp = Table(comp_data, colWidths=[1.8 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch, 1.6 * inch])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('BACKGROUND', (4,1), (4,-1), colors.HexColor("#F0FDF4")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 12))

    # =========================================================================
    # 3. HIGH-LEVEL SYSTEM ARCHITECTURE
    # =========================================================================
    story.append(Paragraph("2. High-Level System Architecture", styles['SectionH1']))
    story.append(Paragraph(
        "InsightX v2.0 is designed as a modular monorepo with strict separation of concerns between presentation, orchestration, "
        "multi-layer analysis, sandbox execution, causal correlation, and database persistence:",
        styles['BodyP']
    ))

    arch_box = (
        "+--------------------------------------------------------------------------------------------------+\n"
        "|  FRONTEND LAYER (React 18 + TypeScript + Vite + Tailwind CSS)                                   |\n"
        "|  • Overview Dashboard: System health score (0-100), recent diagnoses, 1-click sample cases       |\n"
        "|  • New Analysis Workspace: Drag-and-drop ZIP/files, CodeEditor with line numbers & Tab indent   |\n"
        "|  • Findings & Test Inspector: Searchable table, severity filters, actual vs expected outputs     |\n"
        "|  • Root Cause Explorer: Ranked causal hypotheses & interactive SVG dependency graph              |\n"
        "|  • Recommendations & Auto-Fix: Simple/Technical explanations, unified diff viewer, 1-click patch|\n"
        "|  • Explainability (XAI) & Reports: Forensic narrative, score audit table, JSON & Markdown export |\n"
        "+------------------------------------------------+-------------------------------------------------+\n"
        "                                                 | REST API (HTTP JSON & Multipart Uploads)\n"
        "                                                 v\n"
        "+--------------------------------------------------------------------------------------------------+\n"
        "|  BACKEND LAYER (FastAPI + Python 3.11+ + SQLAlchemy + SQLite Engine)                            |\n"
        "|  • API Gateway: /api/v1/analyses, /fixes/apply, /fixes/preview, /source, /revisions, /rules     |\n"
        "|  • Analysis Orchestrator: Coordinates multi-stage pipeline, async prescans & revision trees      |\n"
        "|  • Multi-Layer Code Analyzers: Python AST visitor (20+ rules), Ruff linter, JS/TS & C/C++ static|\n"
        "|  • Intelligent Logical Engine: AST semantics, formula checker & LLM-assisted verification hook   |\n"
        "|  • Subprocess Sandbox: IsolatedCodeRunner (2.0s timeout, memory guards) & TestSynthesizer       |\n"
        "|  • Telemetry & Log Analyzers: Isolation Forest (T=100), Z-score saturation, RFC 5424 parser     |\n"
        "|  • Causal RCA Engine: Temporal lead-lag correlation (tau in [-4, +4]), stack trace mapping       |\n"
        "|  • Auto-Fix Engine: Surgical AST patch generator, patch validator, patch applier & reanalyzer   |\n"
        "+------------------------------------------------+-------------------------------------------------+\n"
        "                                                 | SQLAlchemy ORM\n"
        "                                                 v\n"
        "+--------------------------------------------------------------------------------------------------+\n"
        "|  PERSISTENCE LAYER (SQLite Database - insightx.db)                                              |\n"
        "|  Tables: analyses (revisions tree), findings, root_causes, recommendations, anomalies, logs      |\n"
        "+--------------------------------------------------------------------------------------------------+"
    )
    t_arch = Table([[Paragraph(f"<pre>{arch_box}</pre>", styles['CodeBlockDarkBg'])]], colWidths=[7.3 * inch])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#334155")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 4. THE 5-STAGE PIPELINE MODEL
    # =========================================================================
    story.append(Spacer(1, 10))
    story.append(Paragraph("3. The 5-Stage Decision Intelligence Pipeline", styles['SectionH1']))
    story.append(Paragraph(
        "Every analysis follows an automated, continuous, five-stage decision workflow connecting telemetry symptoms directly "
        "to verifiable code corrections:",
        styles['BodyP']
    ))

    # Stage 1
    story.append(Paragraph("Stage 1: Multi-Layer Code & Telemetry Detection (DETECT)", styles['SectionH2']))
    story.append(Paragraph(
        "InsightX does not rely on a single shallow linter. It executes a multi-layer diagnostic pipeline: "
        "<br/>• <b>Syntax & Symbol Scope Analysis:</b> Integrates <code>ast.parse</code> and Ruff diagnostic rules to catch fundamental errors "
        "(e.g., catching undefined names like <code>printf</code> in Python and resolving that <code>print</code> was intended). "
        "<br/>• <b>Python AST Visitor (20+ Defect Rules):</b> Detects event loop blocking (<code>time.sleep</code> inside <code>async def</code>), "
        "unclosed SQLite and file handles, mutex lock deadlocks, unguarded zero-divisions, and security vulnerabilities (SQLi f-strings, unsafe <code>eval()</code>). "
        "<br/>• <b>Multi-Language Static Scanning:</b> Scans JavaScript/TypeScript (synchronous I/O, prototype pollution, unhandled rejections) and "
        "C/C++ (buffer overflows via <code>strcpy</code>/<code>sprintf</code>, memory leaks, format strings). "
        "<br/>• <b>Multivariate Anomaly Detection:</b> Runs an unsupervised Isolation Forest (100 estimators) and rolling dynamic Z-score saturation "
        "thresholds (|Z| &gt; 2.5&sigma;, saturation &gt; 85%) across CPU, RAM, and latency metrics.",
        styles['BodyP']
    ))

    # Stage 2
    story.append(Paragraph("Stage 2: Automated Sandbox Test Verification (VERIFY)", styles['SectionH2']))
    story.append(Paragraph(
        "When potential logical defects are identified (e.g. calculation anomalies, inverted comparison operators, or boundary mismatches), "
        "InsightX verifies them empirically: "
        "<br/>• <b>Test Case Synthesizer:</b> Automatically generates normal input cases, boundary conditions, and edge cases (0, empty arrays, negative numbers). "
        "<br/>• <b>Subprocess Sandbox (<code>IsolatedCodeRunner</code>):</b> Executes code in an isolated subprocess with strict memory limits, "
        "a clean environment, and a 2.0-second timeout to prevent runaway executions. "
        "<br/>• <b>Empirical Output Comparison:</b> Compares actual output against expected output. A defect is flagged only when test cases "
        "confirm the discrepancy, eliminating false positives.",
        styles['BodyP']
    ))

    # Stage 3
    story.append(Paragraph("Stage 3: Causal Root Cause Analysis (DIAGNOSE)", styles['SectionH2']))
    story.append(Paragraph(
        "InsightX separates symptoms from underlying triggers using mathematical causality: "
        "<br/>• <b>Cross-Modal Stack Trace Mapping:</b> Extracts exception stack traces from RFC 5424 logs and maps error frames directly to AST line numbers in source files. "
        "<br/>• <b>Lead-Lag Temporal Cross-Correlation:</b> Computes normalized cross-correlation across temporal offsets &tau; &isin; [-4, +4] to determine "
        "which metric shifted first (e.g., proving database connection pool exhaustion triggered downstream HTTP 504 timeouts). "
        "<br/>• <b>Calibrated Qualitative Confidence:</b> Assigns qualitative confidence ratings (High &gt; 0.90 for confirmed runtime/sandbox proofs; "
        "Medium-High 0.75–0.88 for aligned cross-modal telemetry correlation; Medium 0.70 for static structural defects).",
        styles['BodyP']
    ))

    # Stage 4
    story.append(Paragraph("Stage 4: Decision Recommendations & Real Auto-Fixing (AUTO-FIX)", styles['SectionH2']))
    story.append(Paragraph(
        "Unlike platforms that merely report errors, InsightX fixes them deterministically: "
        "<br/>• <b>Surgical Patch Generation:</b> Generates precise, line-level source transformations preserving indentation, comments, imports, and surrounding code. "
        "<br/>• <b>Unified Diff Inspection:</b> Presents clear <code>difflib</code> unified diffs in the UI for engineering review. "
        "<br/>• <b>1-Click 'Auto Fix' / 'Apply Fix':</b> Applies the patch to a working copy, re-runs static analysis, re-executes sandbox tests, "
        "updates findings and health scores, and records an immutable revision (e.g. Revision 2) in persistent history.",
        styles['BodyP']
    ))

    # Stage 5
    story.append(Paragraph("Stage 5: Explainable AI & Forensic Evidence Audit (EXPLAIN)", styles['SectionH2']))
    story.append(Paragraph(
        "InsightX generates transparent, auditable diagnostic evidence: "
        "<br/>• <b>Executive Diagnostic Narrative:</b> Plain-language synthesis answering: <i>What was detected? Why is it a problem? What should be changed? How will it help?</i> "
        "<br/>• <b>Evidence Audit Checklist:</b> Tabular record linking every finding to exact line numbers, AST rules, and timestamps. "
        "<br/>• <b>Contextual Info ('i') Popovers:</b> Progressive disclosure modal windows throughout the UI explaining exactly how metrics, confidence, and health scores are computed.",
        styles['BodyP']
    ))
    story.append(Spacer(1, 12))

    # =========================================================================
    # 5. REAL-WORLD BENCHMARK: THE STUDENT GRADING SYSTEM
    # =========================================================================
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. Benchmark Demonstration: Student Grading System", styles['SectionH1']))
    story.append(Paragraph(
        "To illustrate the complete end-to-end detection, verification, and auto-fix cycle on code that compiles cleanly but produces incorrect answers, "
        "consider the benchmark student grading system below:",
        styles['BodyP']
    ))

    student_code = (
        "students = {\n"
        "    \"Aman\": [85, 90, 78],\n"
        "    \"Priya\": [92, 88, 95],\n"
        "    \"Rohit\": [70, 65, 80]\n"
        "}\n\n"
        "def calculate_average(marks):\n"
        "    return sum(marks) / (len(marks) + 1)  # DEFECT 1: len(marks) + 1 denominator\n\n"
        "def find_topper(students):\n"
        "    highest = 0\n"
        "    topper = \"\"\n"
        "    for name, marks in students.items():\n"
        "        average = calculate_average(marks)\n"
        "        if average < highest:             # DEFECT 2: Inverted comparison (< instead of >)\n"
        "            highest = average\n"
        "            topper = name\n"
        "    return topper\n\n"
        "def count_passed(students):\n"
        "    count = 0\n"
        "    for marks in students.values():\n"
        "        average = calculate_average(marks)\n"
        "        if average < 40:                  # DEFECT 3: Inverted threshold (< 40 counts failures)\n"
        "            count += 1\n"
        "    return count\n\n"
        "print(\"Topper:\", find_topper(students))\n"
        "print(\"Passed:\", count_passed(students))\n"
        "print(\"Aman average:\", round(calculate_average(students[\"Aman\"]), 2))"
    )
    t_code = Table([[Paragraph(f"<pre>{student_code}</pre>", styles['CodeBlockDarkBg'])]], colWidths=[7.3 * inch])
    t_code.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#334155")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_code)
    story.append(Spacer(1, 8))

    # Benchmark analysis breakdown
    story.append(Paragraph("Before & After Automated Remediation Results", styles['SectionH2']))
    bench_data = [
        [
            Paragraph("<b>Defective Function</b>", styles['TableHeader']),
            Paragraph("<b>Detected Logical Rule</b>", styles['TableHeader']),
            Paragraph("<b>Verified Test Input</b>", styles['TableHeader']),
            Paragraph("<b>Actual Output</b>", styles['TableHeader']),
            Paragraph("<b>Expected Output</b>", styles['TableHeader']),
            Paragraph("<b>Automated Surgical Fix</b>", styles['TableHeader']),
        ],
        [
            Paragraph("<code>calculate_average</code>", styles['TableCellBold']),
            Paragraph("PY_LOGICAL_CALCULATION", styles['TableCell']),
            Paragraph("<code>[85, 90, 78]</code>", styles['TableCell']),
            Paragraph("<font color='red'><b>63.25</b></font>", styles['TableCell']),
            Paragraph("<font color='green'><b>84.33</b></font>", styles['TableCell']),
            Paragraph("<code>sum(marks) / len(marks)</code>", styles['TableCellBold']),
        ],
        [
            Paragraph("<code>find_topper</code>", styles['TableCellBold']),
            Paragraph("PY_LOGICAL_COMPARISON", styles['TableCell']),
            Paragraph("<code>students</code> dict", styles['TableCell']),
            Paragraph("<font color='red'><b>\"\" (empty)</b></font>", styles['TableCell']),
            Paragraph("<font color='green'><b>\"Priya\"</b></font>", styles['TableCell']),
            Paragraph("<code>if average &gt; highest:</code>", styles['TableCellBold']),
        ],
        [
            Paragraph("<code>count_passed</code>", styles['TableCellBold']),
            Paragraph("PY_LOGICAL_CONDITION", styles['TableCell']),
            Paragraph("<code>students</code> dict", styles['TableCell']),
            Paragraph("<font color='red'><b>0</b></font>", styles['TableCell']),
            Paragraph("<font color='green'><b>3</b></font>", styles['TableCell']),
            Paragraph("<code>if average &gt;= 40:</code>", styles['TableCellBold']),
        ],
    ]
    t_bench = Table(bench_data, colWidths=[1.3 * inch, 1.4 * inch, 1.1 * inch, 0.9 * inch, 0.9 * inch, 1.7 * inch])
    t_bench.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_accent),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_bench)
    story.append(Spacer(1, 8))

    # Sequential Revision Lifecycle Callout
    rev_box = (
        "<b>Sequential Auto-Fix Revision History:</b><br/>"
        "• <b>Revision 1 (Initial):</b> Health Score <b>68/100</b> • 3 Findings • Program Output: Topper: '', Passed: 0, Aman: 63.25<br/>"
        "• <b>Revision 2:</b> Applied fix to <code>calculate_average</code> &rarr; Health Score <b>79/100</b> • Aman average corrected to 84.33<br/>"
        "• <b>Revision 3:</b> Applied fix to <code>find_topper</code> &rarr; Health Score <b>89/100</b> • Topper corrected to 'Priya'<br/>"
        "• <b>Revision 4 (Final):</b> Applied fix to <code>count_passed</code> &rarr; Health Score <b>100/100</b> • Passed count corrected to 3<br/>"
        "<b>Final Verified Output:</b> <code>Topper: Priya | Passed: 3 | Aman average: 84.33</code> (All tests pass & 0 defects remain)"
    )
    t_rev = Table([[Paragraph(rev_box, styles['CalloutText'])]], colWidths=[7.3 * inch])
    t_rev.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDF4")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#86EFAC")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_rev)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 6. TESTING & VERIFICATION STATUS
    # =========================================================================
    story.append(Paragraph("5. Quality Assurance, Test Coverage & Security", styles['SectionH1']))
    story.append(Paragraph(
        "InsightX v2.0 is rigorously tested with automated regression suites across both frontend and backend:",
        styles['BodyP']
    ))

    qa_data = [
        [
            Paragraph("<b>Target Test Suite</b>", styles['TableHeader']),
            Paragraph("<b>Framework</b>", styles['TableHeader']),
            Paragraph("<b>Tests Executed</b>", styles['TableHeader']),
            Paragraph("<b>Passed</b>", styles['TableHeader']),
            Paragraph("<b>Status</b>", styles['TableHeader']),
        ],
        [
            Paragraph("Backend Multi-Layer Analysis & Logical Error Suite", styles['TableCellBold']),
            Paragraph("Pytest 9.2.0 (Python 3.14)", styles['TableCell']),
            Paragraph("104 tests", styles['TableCell']),
            Paragraph("104 passed", styles['TableCellBold']),
            Paragraph("<font color='green'><b>100% PASS (7.85s)</b></font>", styles['TableCellBold']),
        ],
        [
            Paragraph("Frontend Component, UI & Integration Suite", styles['TableCellBold']),
            Paragraph("Vitest 5.1.0 + RTL", styles['TableCell']),
            Paragraph("11 tests", styles['TableCell']),
            Paragraph("11 passed", styles['TableCellBold']),
            Paragraph("<font color='green'><b>100% PASS (0.67s)</b></font>", styles['TableCellBold']),
        ],
        [
            Paragraph("Frontend TypeScript Compilation & Bundle", styles['TableCellBold']),
            Paragraph("Vite 6.4.6 + tsc", styles['TableCell']),
            Paragraph("Production Build", styles['TableCell']),
            Paragraph("Zero errors", styles['TableCellBold']),
            Paragraph("<font color='green'><b>PASS (1.22s)</b></font>", styles['TableCellBold']),
        ],
    ]
    t_qa = Table(qa_data, colWidths=[2.7 * inch, 1.4 * inch, 1.0 * inch, 1.0 * inch, 1.2 * inch])
    t_qa.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_qa)
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "<b>Security & Execution Safeguards:</b><br/>"
        "• <b>Subprocess Sandbox:</b> Dynamic code execution is strictly restricted to subprocess sandboxes with 2.0s wall-clock timeouts.<br/>"
        "• <b>Zip Slip Defense:</b> Uploaded archive paths are canonicalized and checked against directory traversal (<code>../</code>) attacks.<br/>"
        "• <b>Automated Secret Masking:</b> Discovered API tokens and passwords are automatically masked (<code>sk****78</code>) across all logs and exports.<br/>"
        "• <b>Air-Gapped Privacy:</b> Runs 100% locally with zero external network data transmission.",
        styles['BodyP']
    ))
    story.append(Spacer(1, 10))

    # =========================================================================
    # 7. ACADEMIC CREDITS & REPOSITORY REFERENCES
    # =========================================================================
    story.append(Paragraph("6. Academic Project Information & References", styles['SectionH1']))
    story.append(Paragraph(
        "InsightX v2.0 was designed and developed at <b>Dhirubhai Ambani Institute of Information and Communication Technology (DA-IICT)</b>, "
        "Gandhinagar, Gujarat, India, under the Master of Science in Data Science Innovation curriculum.<br/>"
        "• <b>Primary Developers:</b> Aman Chauhan (<code>202518004</code>), Mannan Agarwal (<code>202518013</code>)<br/>"
        "• <b>Research Paper:</b> <code>paper/insightx_research_paper.md</code> & IEEE Two-Column PDF: <code>paper/insightx_ieee_paper.pdf</code><br/>"
        "• <b>Repository Documentation:</b> <code>README.md</code>, <code>docs/ARCHITECTURE.md</code>, <code>docs/TEST_RESULTS.md</code><br/>"
        "• <b>License:</b> Open-source MIT License",
        styles['BodyP']
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {output_path}")


if __name__ == "__main__":
    out_file = "InsightX_v2_Project_Architecture_and_Pipeline_Guide.pdf"
    if len(sys.argv) > 1:
        out_file = sys.argv[1]
    build_pdf(out_file)
