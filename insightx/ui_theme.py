"""
InsightX Modern UI Theme & Design System — Enterprise Top-Navigation SaaS Theme
Strictly conforming to user requirements:
- No sidebar: 100% full-width layout with sleek top navigation
- Canvas Background: crisp, clean light neutral (#F8FAFC)
- Main Cards: pure white (#FFFFFF) with subtle border (#E2E8F0) and soft shadow
- Top Navigation: enterprise tab bar (#FFFFFF background, electric blue #2563EB active state)
- Primary Accent: electric blue (#2563EB)
- Secondary Accent: sky blue (#0EA5E9)
- Text: dark slate (#0F172A headings, #334155 body, #64748B secondary)
- Status: Success (#10B981), Warning (#F59E0B), Critical (#EF4444)
- Typography: Inter / Plus Jakarta Sans
"""

THEME_COLORS = {
    "canvas_bg": "#F8FAFC",
    "card_bg": "#FFFFFF",
    "card_border": "#E2E8F0",
    "primary": "#2563EB",
    "primary_dark": "#1D4ED8",
    "secondary": "#0EA5E9",
    "success": "#10B981",
    "warning": "#F59E0B",
    "critical": "#EF4444",
    "text_headings": "#0F172A",
    "text_body": "#334155",
    "text_secondary": "#64748B"
}

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global Typography & Light Canvas */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }

    /* -------------------------------------------------------------
       HIDE SIDEBAR ENTIRELY (100% Full-Width Layout)
       ------------------------------------------------------------- */
    section[data-testid="stSidebar"],
    [data-testid="stSidebar"],
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarUserContent"],
    [data-testid="stSidebarHeader"],
    [data-testid="stSidebarContent"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    button[data-testid="stSidebarCollapseButton"],
    div[data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
        width: 0 !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        pointer-events: none !important;
    }

    /* Remove Streamlit default header height overlay to prevent clipping */
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    #MainMenu,
    footer {
        display: none !important;
        height: 0 !important;
        visibility: hidden !important;
    }

    /* Ensure main container takes full width with zero sidebar offset */
    div[data-testid="stAppViewContainer"] > section.main {
        width: 100% !important;
        margin-left: 0 !important;
        padding-left: 0 !important;
    }

    div[data-testid="stAppViewContainer"] {
        margin-left: 0 !important;
        padding-left: 0 !important;
    }

    /* Main Container: Wide, properly aligned, unclipped with generous top padding */
    .block-container {
        padding-top: 1.75rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2.25rem !important;
        padding-right: 2.25rem !important;
        max-width: 1600px !important;
        margin: 0 auto !important;
    }

    /* -------------------------------------------------------------
       ENTERPRISE TOP BRAND & CONTROLS HEADER
       ------------------------------------------------------------- */
    .top-brand-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .brand-title-box {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .brand-logo-text {
        font-size: 1.55rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.5px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .brand-logo-text span.blue-accent {
        color: #2563EB;
    }
    .brand-separator {
        width: 1px;
        height: 28px;
        background-color: #E2E8F0;
    }
    .brand-subtext {
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 500;
    }

    /* Header Meta Badges */
    .header-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        background: #F1F5F9;
        border: 1px solid #E2E8F0;
        border-radius: 9999px;
        font-size: 0.76rem;
        font-weight: 600;
        color: #334155;
    }
    .header-pill-cluster {
        background: #EFF6FF;
        border-color: #BFDBFE;
        color: #1D4ED8;
    }

    /* -------------------------------------------------------------
       TOP NAVIGATION BAR (Styled .stTabs as Premium SaaS Navbar)
       ------------------------------------------------------------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px !important;
        background-color: #FFFFFF !important;
        padding: 6px 10px !important;
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
        margin-bottom: 20px !important;
        display: flex !important;
        flex-wrap: wrap !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 16px !important;
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        border: none !important;
        background-color: transparent !important;
        transition: all 0.15s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #F1F5F9 !important;
        color: #0F172A !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3) !important;
        font-weight: 700 !important;
    }
    .stTabs [aria-selected="true"] p,
    .stTabs [aria-selected="true"] span,
    .stTabs [aria-selected="true"] div {
        color: #FFFFFF !important;
    }
    /* Remove ugly tab underlines */
    .stTabs [data-baseweb="tab-border"],
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* -------------------------------------------------------------
       CONTEXTUAL STATUS BANNERS
       ------------------------------------------------------------- */
    .status-banner-incident {
        background: #FEF2F2;
        border: 1px solid #FECACA;
        border-left: 5px solid #EF4444;
        padding: 12px 18px;
        border-radius: 10px;
        margin-bottom: 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 3px rgba(239, 68, 68, 0.06);
    }
    .status-banner-healthy {
        background: #F0FDF4;
        border: 1px solid #BBF7D0;
        border-left: 5px solid #10B981;
        padding: 12px 18px;
        border-radius: 10px;
        margin-bottom: 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 3px rgba(16, 185, 129, 0.06);
    }
    .status-banner-mitigated {
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-left: 5px solid #2563EB;
        padding: 12px 18px;
        border-radius: 10px;
        margin-bottom: 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 3px rgba(37, 99, 235, 0.06);
    }

    .pulse-dot-red {
        display: inline-block;
        width: 10px;
        height: 10px;
        background-color: #EF4444;
        border-radius: 50%;
        margin-right: 8px;
        box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
        animation: pulse 1.8s infinite;
    }
    .pulse-dot-green {
        display: inline-block;
        width: 10px;
        height: 10px;
        background-color: #10B981;
        border-radius: 50%;
        margin-right: 8px;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
        animation: pulse 1.8s infinite;
    }
    .pulse-dot-blue {
        display: inline-block;
        width: 10px;
        height: 10px;
        background-color: #2563EB;
        border-radius: 50%;
        margin-right: 8px;
        box-shadow: 0 0 8px rgba(37, 99, 235, 0.6);
        animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.8; }
        50% { transform: scale(1.3); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.8; }
    }

    /* -------------------------------------------------------------
       CRISP WHITE KPI METRIC CARDS
       ------------------------------------------------------------- */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 16px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(15, 23, 42, 0.06);
        border-color: #CBD5E1;
    }
    .kpi-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.72rem;
        color: #64748B;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value-row {
        display: flex;
        align-items: baseline;
        gap: 4px;
        margin-top: 6px;
        margin-bottom: 2px;
    }
    .kpi-value {
        font-size: 1.75rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.5px;
        line-height: 1.1;
    }
    .kpi-unit {
        font-size: 0.82rem;
        color: #64748B;
        font-weight: 600;
    }
    .kpi-sub {
        font-size: 0.72rem;
        color: #64748B;
        font-weight: 500;
    }

    /* -------------------------------------------------------------
       WHITE CONTENT CARDS
       ------------------------------------------------------------- */
    .white-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .white-card-header {
        font-size: 0.95rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* -------------------------------------------------------------
       PILL BADGES
       ------------------------------------------------------------- */
    .badge-critical {
        background: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FCA5A5;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.70rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-high {
        background: #FEF2F2;
        color: #B91C1C;
        border: 1px solid #FECACA;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.70rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-medium {
        background: #FEF3C7;
        color: #92400E;
        border: 1px solid #FCD34D;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.70rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-low {
        background: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.70rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-green {
        background: #ECFDF5;
        color: #047857;
        border: 1px solid #A7F3D0;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.70rem;
        font-weight: 700;
        display: inline-block;
    }

    /* -------------------------------------------------------------
       BUTTONS & INPUTS
       ------------------------------------------------------------- */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        border: 1px solid #CBD5E1 !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
        color: #FFFFFF !important;
        box-shadow: 0 1px 3px rgba(37, 99, 235, 0.25) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #1D4ED8 !important;
        border-color: #1D4ED8 !important;
    }

    /* Clean Selectbox Styling */
    div[data-baseweb="select"] {
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        background: #FFFFFF !important;
    }

    /* Clean Dataframes */
    div[data-testid="stDataFrame"] {
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        overflow: hidden;
        background: #FFFFFF;
    }

    /* Monospace Code blocks */
    pre, code {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* -------------------------------------------------------------
       INFO POPOVER BUTTONS (ℹ️ Minimal Details Trigger)
       ------------------------------------------------------------- */
    div[data-testid="stPopover"] > button {
        background-color: #F8FAFC !important;
        border: 1px solid #CBD5E1 !important;
        color: #2563EB !important;
        font-size: 0.76rem !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        padding: 2px 8px !important;
        line-height: 1.2 !important;
        min-height: 24px !important;
        transition: all 0.15s ease !important;
    }
    div[data-testid="stPopover"] > button:hover {
        background-color: #EFF6FF !important;
        border-color: #93C5FD !important;
        color: #1D4ED8 !important;
    }
    div[data-testid="stPopoverBody"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.08) !important;
        padding: 16px !important;
        font-size: 0.84rem !important;
        color: #334155 !important;
        max-width: 480px !important;
    }

    /* Minimal Card Elements */
    .card-title-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .card-title-text {
        font-size: 0.92rem;
        font-weight: 700;
        color: #0F172A;
    }
    .card-summary-text {
        font-size: 0.82rem;
        color: #475569;
        line-height: 1.45;
        margin-bottom: 6px;
    }
</style>
"""

def get_plotly_layout(height=280, title=None, y_title=None):
    """Returns an enterprise light theme configuration for Plotly charts."""
    layout = dict(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        height=height,
        margin=dict(l=45, r=20, t=35 if title else 20, b=35),
        font=dict(family="Inter, -apple-system, sans-serif", color="#334155", size=11),
        xaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            linecolor="#E2E8F0",
            zeroline=False,
            tickfont=dict(size=10, color="#64748B")
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F1F5F9",
            linecolor="#E2E8F0",
            zeroline=False,
            tickfont=dict(size=10, color="#64748B"),
            title=dict(text=y_title, font=dict(size=11, color="#475569")) if y_title else None
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10, color="#475569")
        )
    )
    if title:
        layout["title"] = dict(
            text=f"<b>{title}</b>",
            font=dict(size=13, color="#0F172A"),
            x=0.01,
            y=0.98
        )
    return layout
