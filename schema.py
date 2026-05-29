"""Database schema and shared assessment constants."""

MOMENT_GROUP_EXERCISE = "Group Exercise"
MOMENT_INDIVIDUAL_INTERVIEW = "Individual Interview"
MOMENTS = (MOMENT_GROUP_EXERCISE, MOMENT_INDIVIDUAL_INTERVIEW)

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS assessment_nights (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        date TEXT,
        location TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT,
        notes TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_night_candidates (
        id INTEGER PRIMARY KEY,
        assessment_night_id INTEGER NOT NULL,
        candidate_id INTEGER NOT NULL,
        UNIQUE(assessment_night_id, candidate_id),
        FOREIGN KEY (assessment_night_id)
            REFERENCES assessment_nights(id)
            ON DELETE CASCADE,
        FOREIGN KEY (candidate_id)
            REFERENCES candidates(id)
            ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY,
        assessment_night_id INTEGER NOT NULL,
        candidate_id INTEGER NOT NULL,
        moment TEXT NOT NULL,
        assessor_name TEXT,
        leadership_collaboration TEXT NOT NULL,
        analytical_capabilities TEXT NOT NULL,
        individual_performance TEXT NOT NULL,
        additional_comments TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (assessment_night_id)
            REFERENCES assessment_nights(id),
        FOREIGN KEY (candidate_id)
            REFERENCES candidates(id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_assessment_night_candidates_night
    ON assessment_night_candidates(assessment_night_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_assessment_night_candidates_candidate
    ON assessment_night_candidates(candidate_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evaluations_night_candidate
    ON evaluations(assessment_night_id, candidate_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evaluations_moment
    ON evaluations(moment);
    """,
]
