SELECT *
FROM activities
WHERE processed = false
ORDER BY event_date ASC;
