from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

# SQLite specific connect args for multi-threaded FastAPI
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _ensure_sqlite_columns():
    """Safely adds newly introduced columns to existing SQLite tables without losing history."""
    if "sqlite" not in settings.DATABASE_URL:
        return

    migrations = {
        "analyses": [
            ("parent_analysis_id", "VARCHAR(36)"),
            ("root_analysis_id", "VARCHAR(36)"),
            ("revision_number", "INTEGER DEFAULT 1"),
            ("applied_recommendation_id", "VARCHAR(36)"),
            ("applied_recommendation_title", "VARCHAR(255)"),
            ("source_snapshot", "JSON DEFAULT '{}'"),
        ],
        "findings": [
            ("evidence_category", "VARCHAR(60) DEFAULT 'Static Code Evidence'"),
            ("rule_id", "VARCHAR(100)"),
            ("severity_rationale", "TEXT"),
        ],
        "root_causes": [
            ("evidence_category", "VARCHAR(60) DEFAULT 'Static Code Evidence'"),
            ("cause_type", "VARCHAR(80) DEFAULT 'Static Potential Cause'"),
            ("consequences", "TEXT"),
            ("recommended_actions_summary", "TEXT"),
        ],
        "recommendations": [
            ("related_cause_ids", "JSON DEFAULT '[]'"),
            ("rule_id", "VARCHAR(100)"),
            ("auto_fixable", "BOOLEAN DEFAULT 0"),
            ("manual_fix_reason", "TEXT"),
            ("simple_explanation", "JSON DEFAULT '{}'"),
            ("technical_explanation", "JSON DEFAULT '{}'"),
        ],
    }

    with engine.begin() as conn:
        for table, cols in migrations.items():
            existing = {
                row[1]
                for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            }
            if not existing:
                continue
            for col_name, col_def in cols:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))

def _cleanup_legacy_placeholder_causes():
    """Removes legacy placeholder root causes created before zero-finding RCA cleanup."""
    if "sqlite" not in settings.DATABASE_URL:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM root_causes "
                "WHERE title = 'Nominal Operational Baseline / No Causal Defect Isolated'"
            )
        )


def init_db():
    from backend.app.models import analysis  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
    _cleanup_legacy_placeholder_causes()
