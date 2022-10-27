INSERT OR IGNORE INTO activities
(id, student_id, event_date, action_type, json)
VALUES
(:id, :student_id, :event_date, :action_type, :json); 
