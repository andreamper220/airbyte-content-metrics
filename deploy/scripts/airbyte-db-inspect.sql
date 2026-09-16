SELECT id, email, name FROM "user";
SELECT id, auth_user_id, auth_provider FROM auth_user;
SELECT id, name, client_id, secret FROM application;
SELECT table_name, column_name FROM information_schema.columns WHERE column_name ILIKE '%client%' OR column_name ILIKE '%secret%';
