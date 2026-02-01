-- IterateSwarm Supabase Schema
-- Run this in Supabase SQL Editor to set up the database

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Feedback Items Table
CREATE TABLE IF NOT EXISTS feedback_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(50) NOT NULL,           -- discord, slack, manual
    raw_content TEXT NOT NULL,
    processed_content TEXT,                -- Cleaned/extracted content
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, processed, ignored
    classification VARCHAR(20),            -- bug, feature, question
    severity VARCHAR(20),                  -- low, medium, high, critical
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of UUID,                     -- Reference to original feedback
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Issues Table (Draft & Published)
CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feedback_id UUID NOT NULL REFERENCES feedback_items(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',    -- draft, approved, rejected, published
    github_url TEXT,
    labels TEXT[] DEFAULT '{}',
    triage_classification VARCHAR(20),
    triage_severity VARCHAR(20),
    triage_reasoning TEXT,
    triage_confidence FLOAT,
    spec_reproduction_steps TEXT[] DEFAULT '{}',
    spec_affected_components TEXT[] DEFAULT '{}',
    spec_acceptance_criteria TEXT[] DEFAULT '{}',
    spec_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_feedback_items_status ON feedback_items(status);
CREATE INDEX IF NOT EXISTS idx_feedback_items_source ON feedback_items(source);
CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
CREATE INDEX IF NOT EXISTS idx_issues_feedback_id ON issues(feedback_id);

-- Enable Row Level Security (RLS)
ALTER TABLE feedback_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust for your auth setup)
CREATE POLICY "Enable read access for all users" ON feedback_items FOR SELECT USING (true);
CREATE POLICY "Enable insert access for authenticated users" ON feedback_items FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Enable read access for all users" ON issues FOR SELECT USING (true);
CREATE POLICY "Enable insert access for authenticated users" ON issues FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Enable update for authenticated users" ON issues FOR UPDATE USING (auth.role() = 'authenticated');

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for issues table
CREATE TRIGGER update_issues_updated_at
    BEFORE UPDATE ON issues
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
