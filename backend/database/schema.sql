
-- ClaimLens AI - SQLite database schema
-- Synthetic insurance policies only.
--
-- Security:
-- Enforce referential integrity and ensure that
-- coverage sources belong to the correct policy.

PRAGMA foreign_keys = ON;

-- 1. Insurance policies
CREATE TABLE IF NOT EXISTS policies (
    policy_number TEXT PRIMARY KEY,
    holder_reference TEXT NOT NULL,
    product_name TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT NOT NULL,

    CHECK (valid_from <= valid_to)
);

-- 2. Documents associated with each policy
CREATE TABLE IF NOT EXISTS policy_documents (
    id INTEGER PRIMARY KEY,
    policy_number TEXT NOT NULL,
    document_kind TEXT NOT NULL,
    document_reference TEXT NOT NULL,
    pdf_relative_path TEXT NOT NULL UNIQUE,

    FOREIGN KEY (policy_number)
        REFERENCES policies(policy_number)
        ON DELETE CASCADE,

    CHECK (
        document_kind IN (
            'GENERAL_CONDITIONS',
            'POLICY_SCHEDULE'
        )
    ),

    UNIQUE (policy_number, document_kind),

    -- Required for the composite foreign key
    -- used by policy_coverages.
    UNIQUE (id, policy_number)
);

-- 3. Coverages and subscribed options
CREATE TABLE IF NOT EXISTS policy_coverages (
    id INTEGER PRIMARY KEY,
    policy_number TEXT NOT NULL,
    coverage_label TEXT NOT NULL,
    is_subscribed INTEGER NOT NULL,
    source_status TEXT NOT NULL,
    observation TEXT NOT NULL,
    source_document_id INTEGER NOT NULL,

    FOREIGN KEY (policy_number)
        REFERENCES policies(policy_number)
        ON DELETE CASCADE,

    -- A coverage must reference a document
    -- belonging to the same insurance policy.
    FOREIGN KEY (source_document_id, policy_number)
        REFERENCES policy_documents(id, policy_number),

    CHECK (is_subscribed IN (0, 1)),

    UNIQUE (policy_number, coverage_label)
);

-- Index for deterministic coverage filtering
CREATE INDEX IF NOT EXISTS idx_coverages_policy_status
ON policy_coverages(policy_number, is_subscribed);


-- 4. Enforce coverage-source provenance
--
-- Every coverage must reference the POLICY_SCHEDULE
-- document belonging to the same insurance policy.
--
-- These triggers complement the composite foreign key.

CREATE TRIGGER IF NOT EXISTS trg_coverage_source_insert
AFTER INSERT ON policy_coverages
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM policy_documents AS d
    WHERE d.id = NEW.source_document_id
      AND d.policy_number = NEW.policy_number
      AND d.document_kind = 'POLICY_SCHEDULE'
)
BEGIN
    SELECT RAISE(
        ABORT,
        'Invalid coverage source document'
    );
END;


CREATE TRIGGER IF NOT EXISTS trg_coverage_source_update
AFTER UPDATE ON policy_coverages
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM policy_documents AS d
    WHERE d.id = NEW.source_document_id
      AND d.policy_number = NEW.policy_number
      AND d.document_kind = 'POLICY_SCHEDULE'
)
BEGIN
    SELECT RAISE(
        ABORT,
        'Invalid coverage source document'
    );
END;


-- Prevent changes to a referenced document
-- that would invalidate existing coverages.

CREATE TRIGGER IF NOT EXISTS trg_document_source_update
AFTER UPDATE OF document_kind, policy_number
ON policy_documents
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM policy_coverages AS c
    WHERE c.source_document_id = NEW.id
      AND (
          c.policy_number != NEW.policy_number
          OR NEW.document_kind != 'POLICY_SCHEDULE'
      )
)
BEGIN
    SELECT RAISE(
        ABORT,
        'Referenced coverage document cannot be changed'
    );
END;
