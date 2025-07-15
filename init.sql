-- 51Talk AI Learning Platform Database Schema
-- PostgreSQL Database Initialization Script (Idempotent Version)
-- This script creates the complete database schema for the 51Talk AI Learning Platform.
-- Safe to run multiple times - will not drop existing tables or duplicate data.

-- Create database (uncomment if needed)
-- CREATE DATABASE fiftyone_learning;

-- Use the database (uncomment if needed)
-- \c fiftyone_learning;

-- Enable UUID extension (optional, for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Admin users table - stores admin accounts
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cohorts table - stores cohort information for bootcamps
CREATE TABLE IF NOT EXISTS cohorts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    bootcamp_type VARCHAR(50) NOT NULL, -- 'Chinese', 'English', 'Middle East'
    start_date DATE,
    end_date DATE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table - stores user accounts with enhanced fields
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    email_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(255),
    camp VARCHAR(50) NOT NULL DEFAULT 'Middle East', -- 'Middle East', 'Chinese', or 'English'
    student_type VARCHAR(20), -- 'new' or 'existing'
    cohort_id INTEGER REFERENCES cohorts(id) ON DELETE SET NULL,
    previous_bootcamp_type VARCHAR(50), -- Previous bootcamp type for existing students
    cohort_name VARCHAR(100), -- Cohort name for reference
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add role column if it doesn't exist
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'role') THEN
        ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'user';
    END IF;
END $$;

-- Tag groups table - stores tag group categories
CREATE TABLE IF NOT EXISTS tag_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tags table - stores individual tags
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    tag_group_id INTEGER REFERENCES tag_groups(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tag_group_id, name)
);

-- User tags table - assigns tags to users
CREATE TABLE IF NOT EXISTS user_tags (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    assigned_by VARCHAR(50) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tag_id)
);

-- Content tags table - assigns tags to content (materials, videos, etc.)
CREATE TABLE IF NOT EXISTS content_tags (
    id SERIAL PRIMARY KEY,
    content_type VARCHAR(50) NOT NULL, -- 'material', 'video', 'project', 'quiz', 'word'
    content_id INTEGER NOT NULL,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_type, content_id, tag_id)
);

-- Teams table - stores team information
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    team_lead_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    camp VARCHAR(50) NOT NULL, -- 'Middle East', 'Chinese', or 'English'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Team members table - stores team membership
CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, user_id)
);

-- Team scores table - stores team performance scores
CREATE TABLE IF NOT EXISTS team_scores (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    score INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id)
);

-- Materials table - stores learning materials with camp filtering
CREATE TABLE IF NOT EXISTS materials (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    file_path VARCHAR(500),
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', 'English', or 'both'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Videos table - stores video resources with camp filtering
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    youtube_url VARCHAR(500) NOT NULL,
    description TEXT,
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', 'English', or 'both'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects table - stores project assignments with camp filtering
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    resources TEXT,
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', 'English', or 'both'
    deadline DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quizzes table - stores quiz questions with camp filtering
CREATE TABLE IF NOT EXISTS quizzes (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL, -- Array of answer options
    correct_answer INTEGER NOT NULL, -- Index of correct answer (0-based)
    explanation TEXT,
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', 'English', or 'both'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Words table - stores AI vocabulary words with enhanced structure and camp filtering
CREATE TABLE IF NOT EXISTS words (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    word VARCHAR(100) NOT NULL,
    definition TEXT, -- Legacy field, kept for compatibility
    example TEXT, -- Legacy field, kept for compatibility
    section INTEGER DEFAULT 1,
    
    -- Enhanced AI vocabulary fields
    one_sentence_version TEXT,
    daily_definition TEXT,
    life_metaphor TEXT,
    visual_explanation TEXT,
    core_elements JSONB, -- Array of objects with core_element and everyday_object
    scenario_theater TEXT,
    misunderstandings TEXT,
    reality_connection TEXT,
    thinking_bubble TEXT,
    smiling_conclusion TEXT,
    
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', 'English', or 'both'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Progress table - tracks user progress through units
CREATE TABLE IF NOT EXISTS progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    unit_number INTEGER NOT NULL,
    completed INTEGER DEFAULT 0, -- 0 = not completed, 1 = completed
    quiz_score INTEGER DEFAULT 0,
    project_completed INTEGER DEFAULT 0, -- 0 = not completed, 1 = completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, unit_number)
);

-- Quiz attempts table - tracks quiz attempts (one per user per unit)
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    unit_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    passed BOOLEAN DEFAULT FALSE,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, unit_id) -- Only one attempt per user per unit
);

-- Quiz responses table - stores individual question responses
CREATE TABLE IF NOT EXISTS quiz_responses (
    id SERIAL PRIMARY KEY,
    attempt_id INTEGER REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id INTEGER REFERENCES quizzes(id) ON DELETE CASCADE,
    user_answer INTEGER, -- Index of selected answer
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stored documents table - stores uploaded files
CREATE TABLE IF NOT EXISTS stored_documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    content BYTEA NOT NULL,
    content_type VARCHAR(100),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(filename)
);

-- Submissions table - stores project submissions
CREATE TABLE IF NOT EXISTS submissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    unit_id INTEGER NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feedback table - stores user feedback
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    feedback_text TEXT NOT NULL,
    rating VARCHAR(20), -- 'excellent', 'good', 'average', 'fair', 'poor'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- QA History table - stores Q&A interactions with AI assistant
CREATE TABLE IF NOT EXISTS qa_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Followups table - stores follow-up tasks for users
CREATE TABLE IF NOT EXISTS followups (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 1, -- 1 = low, 2 = medium, 3 = high
    followup_date DATE,
    completed BOOLEAN DEFAULT FALSE,
    created_by VARCHAR(50) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance (only if they don't exist)
DO $$ 
BEGIN
    -- Create indexes only if they don't exist
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_email') THEN
        CREATE INDEX idx_users_email ON users(email);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_username') THEN
        CREATE INDEX idx_users_username ON users(username);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_camp') THEN
        CREATE INDEX idx_users_camp ON users(camp);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_cohort') THEN
        CREATE INDEX idx_users_cohort ON users(cohort_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_materials_unit_camp') THEN
        CREATE INDEX idx_materials_unit_camp ON materials(unit_id, camp);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_videos_unit_camp') THEN
        CREATE INDEX idx_videos_unit_camp ON videos(unit_id, camp);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_projects_unit_camp') THEN
        CREATE INDEX idx_projects_unit_camp ON projects(unit_id, camp);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_quizzes_unit_camp') THEN
        CREATE INDEX idx_quizzes_unit_camp ON quizzes(unit_id, camp);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_words_unit_camp') THEN
        CREATE INDEX idx_words_unit_camp ON words(unit_id, camp);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_progress_user_unit') THEN
        CREATE INDEX idx_progress_user_unit ON progress(user_id, unit_number);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_quiz_attempts_user_unit') THEN
        CREATE INDEX idx_quiz_attempts_user_unit ON quiz_attempts(user_id, unit_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_quiz_responses_attempt') THEN
        CREATE INDEX idx_quiz_responses_attempt ON quiz_responses(attempt_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_submissions_user_unit') THEN
        CREATE INDEX idx_submissions_user_unit ON submissions(user_id, unit_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_feedback_user') THEN
        CREATE INDEX idx_feedback_user ON feedback(user_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qa_history_user') THEN
        CREATE INDEX idx_qa_history_user ON qa_history(user_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_qa_history_created') THEN
        CREATE INDEX idx_qa_history_created ON qa_history(created_at);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_team_members_team') THEN
        CREATE INDEX idx_team_members_team ON team_members(team_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_team_members_user') THEN
        CREATE INDEX idx_team_members_user ON team_members(user_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_teams_camp') THEN
        CREATE INDEX idx_teams_camp ON teams(camp);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_tags_group') THEN
        CREATE INDEX idx_tags_group ON tags(tag_group_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_user_tags_user') THEN
        CREATE INDEX idx_user_tags_user ON user_tags(user_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_user_tags_tag') THEN
        CREATE INDEX idx_user_tags_tag ON user_tags(tag_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_content_tags_content') THEN
        CREATE INDEX idx_content_tags_content ON content_tags(content_type, content_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_content_tags_tag') THEN
        CREATE INDEX idx_content_tags_tag ON content_tags(tag_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_followups_user') THEN
        CREATE INDEX idx_followups_user ON followups(user_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_followups_date') THEN
        CREATE INDEX idx_followups_date ON followups(followup_date);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_cohorts_type') THEN
        CREATE INDEX idx_cohorts_type ON cohorts(bootcamp_type);
    END IF;
END $$;

-- Create triggers for updating timestamps (only if function doesn't exist)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create update triggers for all tables with updated_at columns (only if they don't exist)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_users_updated_at') THEN
        CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_teams_updated_at') THEN
        CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_team_scores_updated_at') THEN
        CREATE TRIGGER update_team_scores_updated_at BEFORE UPDATE ON team_scores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_materials_updated_at') THEN
        CREATE TRIGGER update_materials_updated_at BEFORE UPDATE ON materials FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_videos_updated_at') THEN
        CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_projects_updated_at') THEN
        CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_quizzes_updated_at') THEN
        CREATE TRIGGER update_quizzes_updated_at BEFORE UPDATE ON quizzes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_words_updated_at') THEN
        CREATE TRIGGER update_words_updated_at BEFORE UPDATE ON words FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_progress_updated_at') THEN
        CREATE TRIGGER update_progress_updated_at BEFORE UPDATE ON progress FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_tag_groups_updated_at') THEN
        CREATE TRIGGER update_tag_groups_updated_at BEFORE UPDATE ON tag_groups FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_tags_updated_at') THEN
        CREATE TRIGGER update_tags_updated_at BEFORE UPDATE ON tags FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_cohorts_updated_at') THEN
        CREATE TRIGGER update_cohorts_updated_at BEFORE UPDATE ON cohorts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_followups_updated_at') THEN
        CREATE TRIGGER update_followups_updated_at BEFORE UPDATE ON followups FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Insert default admin user (password: rehabadmin51talk) - only if doesn't exist
INSERT INTO admin_users (username, password) 
SELECT 'admin', 'scrypt:32768:8:1$EC5MZ0QjvIn83J3W$15020670dcce64b54a6e3108ba44e01f15d4d92557c5dc78f0780abf94eb4dc70fc2f3eab1d1408393076c7231e7c39ca04930c499f6084cc438a71e98c13d95'
WHERE NOT EXISTS (SELECT 1 FROM admin_users WHERE username = 'admin');

-- Insert default tag groups - only if they don't exist
INSERT INTO tag_groups (name, description) 
SELECT 'Bootcamp Type', 'Tags for different bootcamp types'
WHERE NOT EXISTS (SELECT 1 FROM tag_groups WHERE name = 'Bootcamp Type');

INSERT INTO tag_groups (name, description) 
SELECT 'Student Type', 'Tags for different student types'
WHERE NOT EXISTS (SELECT 1 FROM tag_groups WHERE name = 'Student Type');

INSERT INTO tag_groups (name, description) 
SELECT 'Cohort', 'Tags for different cohorts'
WHERE NOT EXISTS (SELECT 1 FROM tag_groups WHERE name = 'Cohort');

INSERT INTO tag_groups (name, description) 
SELECT 'Skill Level', 'Tags for different skill levels'
WHERE NOT EXISTS (SELECT 1 FROM tag_groups WHERE name = 'Skill Level');

-- Insert default tags - only if they don't exist
-- Bootcamp Type tags
INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Bootcamp Type'), 
    'Chinese', 
    'Chinese bootcamp participants'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Bootcamp Type' AND t.name = 'Chinese'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Bootcamp Type'), 
    'English', 
    'English bootcamp participants'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Bootcamp Type' AND t.name = 'English'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Bootcamp Type'), 
    'Middle East', 
    'Middle East bootcamp participants'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Bootcamp Type' AND t.name = 'Middle East'
);

-- Student Type tags
INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Student Type'), 
    'New Student', 
    'First-time participants'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Student Type' AND t.name = 'New Student'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Student Type'), 
    'Existing Student', 
    'Returning participants'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Student Type' AND t.name = 'Existing Student'
);

-- Skill Level tags
INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Skill Level'), 
    'Beginner', 
    'Beginner level content'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Skill Level' AND t.name = 'Beginner'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Skill Level'), 
    'Intermediate', 
    'Intermediate level content'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Skill Level' AND t.name = 'Intermediate'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Skill Level'), 
    'Advanced', 
    'Advanced level content'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Skill Level' AND t.name = 'Advanced'
);

-- Insert default cohorts - only if they don't exist
INSERT INTO cohorts (name, bootcamp_type, start_date, end_date, description) 
SELECT 'Chinese Cohort 1 (March)', 'Chinese', '2025-03-01', '2025-05-31', 'Chinese AI Bootcamp - Cohort 1 (March 2025)'
WHERE NOT EXISTS (SELECT 1 FROM cohorts WHERE name = 'Chinese Cohort 1 (March)');

INSERT INTO cohorts (name, bootcamp_type, start_date, end_date, description) 
SELECT 'Chinese Cohort 2 (May)', 'Chinese', '2025-05-01', '2025-07-31', 'Chinese AI Bootcamp - Cohort 2 (May 2025)'
WHERE NOT EXISTS (SELECT 1 FROM cohorts WHERE name = 'Chinese Cohort 2 (May)');

INSERT INTO cohorts (name, bootcamp_type, start_date, end_date, description) 
SELECT 'English Cohort 1 (May)', 'English', '2025-05-01', '2025-07-31', 'English AI Bootcamp - Cohort 1 (May 2025)'
WHERE NOT EXISTS (SELECT 1 FROM cohorts WHERE name = 'English Cohort 1 (May)');

INSERT INTO cohorts (name, bootcamp_type, start_date, end_date, description) 
SELECT 'Middle East Cohort 1 (May)', 'Middle East', '2025-05-01', '2025-07-31', 'Middle East AI Bootcamp - Cohort 1 (May 2025)'
WHERE NOT EXISTS (SELECT 1 FROM cohorts WHERE name = 'Middle East Cohort 1 (May)');

-- Insert corresponding cohort tags - only if they don't exist
INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Cohort'), 
    'Chinese Cohort 1 (March)', 
    'Chinese AI Bootcamp - Cohort 1 (March 2025)'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Cohort' AND t.name = 'Chinese Cohort 1 (March)'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Cohort'), 
    'Chinese Cohort 2 (May)', 
    'Chinese AI Bootcamp - Cohort 2 (May 2025)'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Cohort' AND t.name = 'Chinese Cohort 2 (May)'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Cohort'), 
    'English Cohort 1 (May)', 
    'English AI Bootcamp - Cohort 1 (May 2025)'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Cohort' AND t.name = 'English Cohort 1 (May)'
);

INSERT INTO tags (tag_group_id, name, description) 
SELECT 
    (SELECT id FROM tag_groups WHERE name = 'Cohort'), 
    'Middle East Cohort 1 (May)', 
    'Middle East AI Bootcamp - Cohort 1 (May 2025)'
WHERE NOT EXISTS (
    SELECT 1 FROM tags t 
    JOIN tag_groups tg ON t.tag_group_id = tg.id 
    WHERE tg.name = 'Cohort' AND t.name = 'Middle East Cohort 1 (May)'
);

-- Display table creation summary
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;

-- Display success message
SELECT 'Database schema created/updated successfully! All tables and default data have been inserted.' as status;

-- Show counts of inserted data
SELECT 
    'admin_users' as table_name, 
    COUNT(*) as record_count 
FROM admin_users
UNION ALL
SELECT 
    'tag_groups' as table_name, 
    COUNT(*) as record_count 
FROM tag_groups
UNION ALL
SELECT 
    'tags' as table_name, 
    COUNT(*) as record_count 
FROM tags
UNION ALL
SELECT 
    'cohorts' as table_name, 
    COUNT(*) as record_count 
FROM cohorts
ORDER BY table_name;