SELECT name, id::text FROM connection ORDER BY name;
SELECT id::text, status, created_at FROM connection WHERE name ILIKE '%vk%';
SELECT id, scope, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 5;
