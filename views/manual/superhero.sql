-- Views thu cong cho database superhero theo dung Thiet ke Paper V-SQL (Hinh 1 & Hinh 3)

-- 1. View chinh chua thong tin superhero kem cac bang tra cuu (lookup)
CREATE VIEW v_superhero AS
SELECT `superhero`.`id`, `superhero`.`superhero_name` AS `superhero_name`, `superhero`.`full_name`,
       `gender`.`gender`, `eye_colour`.`colour` AS `eye_colour`, `hair_colour`.`colour` AS `hair_colour`,
       `skin_colour`.`colour` AS `skin_colour`, `race`.`race`, `publisher`.`publisher_name`,
       `alignment`.`alignment`, `superhero`.`height_cm`, `superhero`.`weight_kg`
FROM `superhero`
LEFT JOIN `gender` ON `superhero`.`gender_id` = `gender`.`id`
LEFT JOIN `colour` eye_colour ON `superhero`.`eye_colour_id` = `eye_colour`.`id`
LEFT JOIN `colour` hair_colour ON `superhero`.`hair_colour_id` = `hair_colour`.`id`
LEFT JOIN `colour` skin_colour ON `superhero`.`skin_colour_id` = `skin_colour`.`id`
LEFT JOIN `race` ON `superhero`.`race_id` = `race`.`id`
LEFT JOIN `publisher` ON `superhero`.`publisher_id` = `publisher`.`id`
LEFT JOIN `alignment` ON `alignment`.`id` = `superhero`.`alignment_id`;

-- 2. View quan he giua superhero va superpower
CREATE VIEW v_hero_power AS
SELECT `superhero`.`id` AS `hero_id`, `superhero`.`superhero_name`, `superpower`.`power_name`
FROM `hero_power`
LEFT JOIN `superhero` ON `hero_power`.`hero_id` = `superhero`.`id`
LEFT JOIN `superpower` ON `hero_power`.`power_id` = `superpower`.`id`;

-- 3. View quan he giua superhero va attribute
CREATE VIEW v_hero_attribute AS
SELECT `superhero`.`id` AS `hero_id`, `superhero`.`superhero_name`,
       `attribute`.`attribute_name`, `hero_attribute`.`attribute_value`
FROM `hero_attribute`
LEFT JOIN `superhero` ON `hero_attribute`.`hero_id` = `superhero`.`id`
LEFT JOIN `attribute` ON `hero_attribute`.`attribute_id` = `attribute`.`id`;
