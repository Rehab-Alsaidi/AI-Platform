-- 51Talk AI Learning Platform Database Schema
-- PostgreSQL Database Initialization Script
-- This script creates the database schema for the 51Talk AI Learning Platform.

-- Create database
-- CREATE DATABASE fiftyone_learning;

-- Use the database
-- \c fiftyone_learning;

-- Enable UUID extension (optional, for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table - stores user accounts with camp information
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    email_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(255),
    camp VARCHAR(50) NOT NULL DEFAULT 'Middle East', -- 'Middle East' or 'Chinese'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Admin users table - stores admin accounts
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teams table - stores team information
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    team_lead_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    camp VARCHAR(50) NOT NULL, -- 'Middle East' or 'Chinese'
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
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', or 'both'
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
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', or 'both'
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
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', or 'both'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quizzes table - stores quiz questions with camp filtering
CREATE TABLE IF NOT EXISTS quizzes (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    options JSON NOT NULL, -- Array of answer options
    correct_answer INTEGER NOT NULL, -- Index of correct answer (0-based)
    explanation TEXT,
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', or 'both'
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
    
    camp VARCHAR(50) NOT NULL DEFAULT 'both', -- 'Middle East', 'Chinese', or 'both'
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

-- Create indexes for better performance (using IF NOT EXISTS to avoid errors)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_camp ON users(camp);
CREATE INDEX IF NOT EXISTS idx_materials_unit_camp ON materials(unit_id, camp);
CREATE INDEX IF NOT EXISTS idx_videos_unit_camp ON videos(unit_id, camp);
CREATE INDEX IF NOT EXISTS idx_projects_unit_camp ON projects(unit_id, camp);
CREATE INDEX IF NOT EXISTS idx_quizzes_unit_camp ON quizzes(unit_id, camp);
CREATE INDEX IF NOT EXISTS idx_words_unit_camp ON words(unit_id, camp);
CREATE INDEX IF NOT EXISTS idx_progress_user_unit ON progress(user_id, unit_number);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_unit ON quiz_attempts(user_id, unit_id);
CREATE INDEX IF NOT EXISTS idx_quiz_responses_attempt ON quiz_responses(attempt_id);
CREATE INDEX IF NOT EXISTS idx_submissions_user_unit ON submissions(user_id, unit_id);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_qa_history_user ON qa_history(user_id);
CREATE INDEX IF NOT EXISTS idx_qa_history_created ON qa_history(created_at);
CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_teams_camp ON teams(camp);

-- Insert default admin user (password: rehabadmin51talk) - only if not exists
INSERT INTO admin_users (username, password) 
SELECT 'admin', 'scrypt:32768:8:1$EC5MZ0QjvIn83J3W$15020670dcce64b54a6e3108ba44e01f15d4d92557c5dc78f0780abf94eb4dc70fc2f3eab1d1408393076c7231e7c39ca04930c499f6084cc438a71e98c13d95'
WHERE NOT EXISTS (
    SELECT 1 FROM admin_users WHERE username = 'admin'
);

-- Create triggers for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if updated_at column exists before trying to update it
    IF TG_TABLE_NAME IN ('users', 'teams', 'team_scores', 'materials', 'videos', 'projects', 'quizzes', 'words', 'progress') THEN
        NEW.updated_at = CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop existing triggers to avoid conflicts
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_teams_updated_at ON teams;
DROP TRIGGER IF EXISTS update_team_scores_updated_at ON team_scores;
DROP TRIGGER IF EXISTS update_materials_updated_at ON materials;
DROP TRIGGER IF EXISTS update_videos_updated_at ON videos;
DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
DROP TRIGGER IF EXISTS update_quizzes_updated_at ON quizzes;
DROP TRIGGER IF EXISTS update_words_updated_at ON words;
DROP TRIGGER IF EXISTS update_progress_updated_at ON progress;

-- Create triggers only for tables that have updated_at columns
-- Only create triggers after ensuring all tables and columns exist
DO $$
BEGIN
    -- Users trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Teams trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teams' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Team scores trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'team_scores' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_team_scores_updated_at BEFORE UPDATE ON team_scores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Materials trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'materials' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_materials_updated_at BEFORE UPDATE ON materials FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Videos trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'videos' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Projects trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Quizzes trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'quizzes' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_quizzes_updated_at BEFORE UPDATE ON quizzes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Words trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'words' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_words_updated_at BEFORE UPDATE ON words FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    -- Progress trigger
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'progress' AND column_name = 'updated_at') THEN
        CREATE TRIGGER update_progress_updated_at BEFORE UPDATE ON progress FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END$$;

-- Display table creation summary
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;

-- Display success message
SELECT 'Database schema created successfully!' as status;
