-- IterateSwarm Database Schema for Supabase
-- Run this in the Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: feedback_items (Raw Ingestion)
CREATE TABLE IF NOT EXISTS feedback_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL CHECK (source IN ('discord', 'slack', 'manual')),
    raw_content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'ignored', 'duplicate')),
    embedding_vector vector(1536), -- OpenAI text-embedding-3-small dimension
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Table: issues (Agent-Generated GitHub Issues)
CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_id UUID REFERENCES feedback_items(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL, -- Markdown body
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    labels TEXT[] DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'published', 'rejected')),
    github_issue_url TEXT,
    github_issue_number INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE
);

-- Table: issue_versions (Audit Trail)
CREATE TABLE IF NOT EXISTS issue_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID REFERENCES issues(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    labels TEXT[],
    version_number INTEGER NOT NULL,
    created_by VARCHAR(50) DEFAULT 'agent',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_feedback_items_status ON feedback_items(status);
CREATE INDEX IF NOT EXISTS idx_feedback_items_source ON feedback_items(source);
CREATE INDEX IF NOT EXISTS idx_feedback_items_created_at ON feedback_items(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_items_embedding ON feedback_items USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
CREATE INDEX IF NOT EXISTS idx_issues_created_at ON issues(created_at);
CREATE INDEX IF NOT EXISTS idx_issues_feedback_id ON issues(feedback_id);

CREATE INDEX IF NOT EXISTS idx_issue_versions_issue_id ON issue_versions(issue_id);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_issues_updated_at ON issues;
CREATE TRIGGER update_issues_updated_at
    BEFORE UPDATE ON issues
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger to auto-increment version number
CREATE OR REPLACE FUNCTION set_version_number()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.title IS DISTINCT FROM OLD.title OR NEW.description IS DISTINCT FROM OLD.description THEN
        NEW.version_number := COALESCE(
            (SELECT MAX(version_number) FROM issue_versions WHERE issue_id = NEW.id), 0
        ) + 1;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS set_issue_version ON issues;
CREATE TRIGGER set_issue_version
    BEFORE INSERT OR UPDATE ON issues
    FOR EACH ROW
    EXECUTE FUNCTION set_version_number();

-- Row Level Security (RLS) - Enable for production
-- ALTER TABLE feedback_items ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE issue_versions ENABLE ROW LEVEL SECURITY;

-- Create policy for public access (for development)
-- CREATE POLICY "Allow public access" ON feedback_items FOR ALL USING (true);
-- CREATE POLICY "Allow public access" ON issues FOR ALL USING (true);
-- CREATE POLICY "Allow public access" ON issue_versions FOR ALL USING (true);

-- Function to create issue version snapshot
CREATE OR REPLACE FUNCTION create_issue_version(
    p_issue_id UUID,
    p_title TEXT,
    p_description TEXT,
    p_severity VARCHAR(20),
    p_labels TEXT[]
) RETURNS UUID AS $$
DECLARE
    v_version_id UUID;
BEGIN
    INSERT INTO issue_versions (issue_id, title, description, severity, labels, version_number)
    VALUES (
        p_issue_id,
        p_title,
        p_description,
        p_severity,
        p_labels,
        (SELECT COALESCE(MAX(version_number), 0) + 1 FROM issue_versions WHERE issue_id = p_issue_id)
    )
    RETURNING id INTO v_version_id;

    RETURN v_version_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- View for Dashboard Stats
CREATE OR REPLACE VIEW dashboard_stats AS
SELECT
    COUNT(*) FILTER (WHERE status = 'pending') AS pending_feedback,
    COUNT(*) FILTER (WHERE status = 'processed') AS processed_feedback,
    COUNT(*) FILTER (WHERE status = 'duplicate') AS duplicate_feedback,
    COUNT(*) FILTER (WHERE status = 'draft') AS draft_issues,
    COUNT(*) FILTER (WHERE status = 'published') AS published_issues,
    COUNT(*) FILTER (WHERE severity = 'critical') AS critical_issues,
    COUNT(*) FILTER (WHERE severity = 'high') AS high_severity_issues
FROM feedback_items;

-- View for Recent Activity
CREATE OR REPLACE VIEW recent_activity AS
SELECT
    'issue' AS type,
    i.id AS item_id,
    i.title AS title,
    i.status,
    i.severity,
    i.created_at
FROM issues i
UNION ALL
SELECT
    'feedback' AS type,
    f.id AS item_id,
    LEFT(f.raw_content, 100) AS title,
    f.status,
    NULL AS severity,
    f.created_at
FROM feedback_items f
ORDER BY created_at DESC
LIMIT 50;
