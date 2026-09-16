SELECT default_workspace_id FROM "user" LIMIT 1;
SELECT id, name, client_id FROM application;
SELECT id, name, client_id, left(client_secret::text,8) FROM application;
