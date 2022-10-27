INSERT INTO auth
(login, cookie)
VALUES
(:login, :cookie)
ON CONFLICT(login) DO UPDATE SET cookie=:cookie;
