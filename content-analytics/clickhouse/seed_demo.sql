-- Демо-данные для проверки дашборда (17 роликов за ~30 дней)

INSERT INTO analytics.raw_tiktok_videos
(item_id, create_time, caption, share_url, thumbnail_url, video_duration, video_views, likes, comments, shares, reach, average_time_watched, total_time_watched, full_video_watched_rate, _airbyte_extracted_at)
VALUES
('tt_001', toUnixTimestamp('2026-07-20 12:00:00'), 'Рецепт за 60 секунд', 'https://tiktok.com/@u/video/1', '', 45, 125000, 8900, 320, 1100, 98000, 12.5, 1500000, 0.42, now()),
('tt_002', toUnixTimestamp('2026-07-22 18:00:00'), 'Лайфхак для кухни', 'https://tiktok.com/@u/video/2', '', 30, 45000, 2100, 89, 400, 38000, 8.1, 360000, 0.28, now()),
('tt_003', toUnixTimestamp('2026-06-25 11:00:00'), 'Утренний смузи за 3 минуты', 'https://tiktok.com/@u/video/3', '', 55, 78000, 4200, 210, 650, 62000, 11.2, 890000, 0.35, now()),
('tt_004', toUnixTimestamp('2026-07-02 19:30:00'), '5 ошибок в выпечке', 'https://tiktok.com/@u/video/4', '', 40, 156000, 11200, 480, 2100, 120000, 14.0, 2100000, 0.38, now()),
('tt_005', toUnixTimestamp('2026-07-08 14:15:00'), 'Быстрый обед в офисе', 'https://tiktok.com/@u/video/5', '', 25, 32000, 1800, 95, 280, 28000, 7.5, 240000, 0.22, now()),
('tt_006', toUnixTimestamp('2026-07-14 09:45:00'), 'Салат с авокадо — тренд недели', 'https://tiktok.com/@u/video/6', '', 35, 91000, 5600, 340, 920, 75000, 10.8, 980000, 0.31, now()),
('tt_007', toUnixTimestamp('2026-07-23 20:00:00'), 'Десерт без сахара', 'https://tiktok.com/@u/video/7', '', 50, 67000, 3900, 175, 510, 54000, 9.6, 720000, 0.29, now());

INSERT INTO analytics.raw_youtube_videos
(id, title, published_at, view_count, like_count, comment_count, _airbyte_extracted_at)
VALUES
('yt_abc', 'Рецепт за 60 секунд — полная версия', '2026-07-20 14:00:00', 89000, 5200, 180, now()),
('yt_def', 'Обзор продукта', '2026-07-18 10:00:00', 12000, 400, 22, now()),
('yt_ghi', 'Как выбрать сковороду', '2026-06-27 16:00:00', 34000, 2100, 88, now()),
('yt_hij', 'Мастер-класс: паста карбонара', '2026-07-04 12:30:00', 112000, 7800, 310, now()),
('yt_jkl', 'Распаковка кухонного комбайна', '2026-07-10 18:00:00', 28000, 1500, 64, now()),
('yt_mno', 'Топ-10 специй для дома', '2026-07-15 11:00:00', 56000, 3200, 142, now());

INSERT INTO analytics.raw_instagram_media
(id, caption, timestamp, media_type, permalink, _airbyte_extracted_at)
VALUES
('ig_111', 'Reels: рецепт', '2026-07-20 16:00:00', 'REELS', 'https://instagram.com/reel/111', now()),
('ig_222', 'Stories highlight', '2026-07-19 09:00:00', 'VIDEO', 'https://instagram.com/p/222', now()),
('ig_333', 'Reels: завтрак за 5 минут', '2026-06-30 08:00:00', 'REELS', 'https://instagram.com/reel/333', now()),
('ig_334', 'Reels: идеи для meal prep', '2026-07-06 13:00:00', 'REELS', 'https://instagram.com/reel/334', now()),
('ig_335', 'Reels: готовим с детьми', '2026-07-12 17:30:00', 'REELS', 'https://instagram.com/reel/335', now()),
('ig_336', 'Reels: сезонные овощи', '2026-07-16 10:00:00', 'REELS', 'https://instagram.com/reel/336', now());

INSERT INTO analytics.raw_instagram_media_insights
(id, reach, saved, shares, total_interactions, views, _airbyte_extracted_at)
VALUES
('ig_111', 67000, 1200, 890, 15000, 72000, now()),
('ig_222', 8000, 50, 30, 900, 9500, now()),
('ig_333', 41000, 680, 420, 8200, 48000, now()),
('ig_334', 55000, 910, 560, 11000, 61000, now()),
('ig_335', 38000, 540, 310, 6900, 42000, now()),
('ig_336', 29000, 380, 240, 5100, 33000, now());

INSERT INTO analytics.raw_metrika_sessions
(visitID, date, dateTime, startURL, pageViews, clientID, UTMSource, UTMMedium, UTMContent, UTMTerm, bounce, _airbyte_extracted_at)
VALUES
('v1', '2026-07-20', '2026-07-20 15:00:00', 'https://example.com/recipe', '3', 'c1', 'tiktok', 'social', '', '', '0', now()),
('v2', '2026-07-20', '2026-07-20 15:30:00', 'https://example.com/recipe', '2', 'c2', 'tiktok', 'social', '', '', '0', now()),
('v3', '2026-07-20', '2026-07-20 16:00:00', 'https://example.com/recipe', '4', 'c3', 'youtube', 'social', '', '', '0', now()),
('v4', '2026-07-22', '2026-07-22 19:00:00', 'https://example.com/kitchen', '2', 'c4', 'tiktok', 'social', '', '', '1', now()),
('v5', '2026-07-22', '2026-07-22 19:10:00', 'https://example.com/kitchen', '1', 'c5', 'instagram', 'social', '', '', '0', now()),
('v6', '2026-06-25', '2026-06-25 12:00:00', 'https://example.com/smoothie', '2', 'c6', 'tiktok', 'social', '', '', '0', now()),
('v7', '2026-06-25', '2026-06-25 12:30:00', 'https://example.com/smoothie', '3', 'c7', 'tiktok', 'social', '', '', '0', now()),
('v8', '2026-06-27', '2026-06-27 17:00:00', 'https://example.com/pans', '2', 'c8', 'youtube', 'social', '', '', '0', now()),
('v9', '2026-06-30', '2026-06-30 09:00:00', 'https://example.com/breakfast', '1', 'c9', 'instagram', 'social', '', '', '0', now()),
('v10', '2026-07-02', '2026-07-02 20:00:00', 'https://example.com/baking', '4', 'c10', 'tiktok', 'social', '', '', '0', now()),
('v11', '2026-07-02', '2026-07-02 20:15:00', 'https://example.com/baking', '2', 'c11', 'tiktok', 'social', '', '', '0', now()),
('v12', '2026-07-04', '2026-07-04 13:00:00', 'https://example.com/pasta', '3', 'c12', 'youtube', 'social', '', '', '0', now()),
('v13', '2026-07-06', '2026-07-06 14:00:00', 'https://example.com/mealprep', '2', 'c13', 'instagram', 'social', '', '', '0', now()),
('v14', '2026-07-08', '2026-07-08 15:00:00', 'https://example.com/lunch', '1', 'c14', 'tiktok', 'social', '', '', '1', now()),
('v15', '2026-07-10', '2026-07-10 19:00:00', 'https://example.com/unbox', '2', 'c15', 'youtube', 'social', '', '', '0', now()),
('v16', '2026-07-12', '2026-07-12 18:00:00', 'https://example.com/kids', '3', 'c16', 'instagram', 'social', '', '', '0', now()),
('v17', '2026-07-14', '2026-07-14 10:00:00', 'https://example.com/salad', '2', 'c17', 'tiktok', 'social', '', '', '0', now()),
('v18', '2026-07-15', '2026-07-15 12:00:00', 'https://example.com/spices', '2', 'c18', 'youtube', 'social', '', '', '0', now()),
('v19', '2026-07-16', '2026-07-16 11:00:00', 'https://example.com/veggies', '1', 'c19', 'instagram', 'social', '', '', '0', now()),
('v20', '2026-07-18', '2026-07-18 11:00:00', 'https://example.com/review', '2', 'c20', 'youtube', 'social', '', '', '0', now()),
('v21', '2026-07-19', '2026-07-19 10:00:00', 'https://example.com/stories', '1', 'c21', 'instagram', 'social', '', '', '0', now()),
('v22', '2026-07-23', '2026-07-23 21:00:00', 'https://example.com/dessert', '3', 'c22', 'tiktok', 'social', '', '', '0', now());

INSERT INTO analytics.raw_video_comments
(platform, video_id, comment_id, author, text, likes, published_at, _airbyte_extracted_at)
VALUES
('tiktok', 'tt_001', 'c1', 'maria_k', 'Сохранила, завтра повторю!', 842, '2026-07-20 13:00:00', now()),
('tiktok', 'tt_001', 'c2', 'chef_ivan', 'Добавьте чеснок в конце — вкуснее', 1205, '2026-07-20 14:20:00', now()),
('tiktok', 'tt_001', 'c3', 'user99', 'Где купить форму?', 56, '2026-07-21 09:00:00', now()),
('tiktok', 'tt_002', 'c4', 'anna_p', 'Работает, проверила', 310, '2026-07-22 19:30:00', now()),
('tiktok', 'tt_004', 'c5', 'baker_pro', 'Наконец-то про температуру духовки!', 1890, '2026-07-02 21:00:00', now()),
('tiktok', 'tt_004', 'c6', 'newbie_cook', 'У меня всегда пригорало снизу', 420, '2026-07-03 08:00:00', now()),
('tiktok', 'tt_006', 'c7', 'healthy_eats', 'Заменила масло на йогурт — тоже ок', 670, '2026-07-14 11:00:00', now()),
('youtube', 'yt_abc', 'yc1', 'CookFan', 'Лучший рецепт за последний месяц', 2100, '2026-07-20 15:00:00', now()),
('youtube', 'yt_abc', 'yc2', 'DmitryV', 'Сколько градусов духовки?', 890, '2026-07-20 16:10:00', now()),
('youtube', 'yt_abc', 'yc3', 'Elena', 'Спасибо, дети съели всё', 445, '2026-07-21 11:00:00', now()),
('youtube', 'yt_def', 'yd1', 'TechReview', 'Жду полный обзор', 120, '2026-07-18 12:00:00', now()),
('youtube', 'yt_hij', 'yh1', 'pasta_lover', 'Сливки или без — что лучше?', 1560, '2026-07-04 14:00:00', now()),
('youtube', 'yt_hij', 'yh2', 'roma_f', 'Сделал по рецепту, семья в восторге', 980, '2026-07-05 09:30:00', now()),
('instagram', 'ig_111', 'ic1', 'foodie_msk', 'Нужен список ингредиентов в описании', 670, '2026-07-20 17:00:00', now()),
('instagram', 'ig_111', 'ic2', 'reels_lover', 'Залипла на повторе', 980, '2026-07-20 18:30:00', now()),
('instagram', 'ig_334', 'ic3', 'prep_queen', 'Сколько дней хранится в холодильнике?', 540, '2026-07-06 15:00:00', now()),
('instagram', 'ig_335', 'ic4', 'mom_of_two', 'Дети сами мешали — супер идея', 1120, '2026-07-12 19:00:00', now());
