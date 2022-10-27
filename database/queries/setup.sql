CREATE TABLE IF NOT EXISTS activities(
    id VARCHAR NOT NULL PRIMARY KEY,
    student_id VARCHAR(36),
    event_date TEXT,
    action_type TEXT,
    processed BOOLEAN DEFAULT FALSE,
    json TEXT
);

CREATE TABLE IF NOT EXISTS auth(
    login VARCHAR PRIMARY KEY,
    cookie TEXT
);
