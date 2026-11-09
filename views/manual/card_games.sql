-- Views thu cong cho database card_games (Paper V-SQL style)

-- 1. View ket hop cards va thong tin sets
CREATE VIEW v_cards_sets AS
SELECT
    cards.id AS card_id,
    cards.name AS card_name,
    cards.asciiName AS ascii_name,
    cards.uuid,
    cards.artist,
    cards.borderColor AS border_color,
    cards.colors,
    cards.convertedManaCost AS converted_mana_cost,
    cards.faceName AS face_name,
    cards.flavorText AS flavor_text,
    cards.keywords,
    cards.layout,
    cards.manaCost AS mana_cost,
    cards.power,
    cards.rarity,
    cards.setCode AS set_code,
    cards.side,
    cards.subtypes,
    cards.supertypes,
    cards.text AS card_text,
    cards.toughness,
    cards.type AS card_type,
    cards.types,
    sets.name AS set_name,
    sets.block AS set_block,
    sets.releaseDate AS set_release_date,
    sets.totalSetSize AS total_set_size,
    sets.type AS set_type
FROM cards
LEFT JOIN sets ON cards.setCode = sets.code;

-- 2. View ket hop cards va legalities
CREATE VIEW v_cards_legalities AS
SELECT
    cards.id AS card_id,
    cards.name AS card_name,
    cards.uuid,
    cards.setCode AS set_code,
    cards.type AS card_type,
    cards.rarity,
    legalities.format AS legality_format,
    legalities.status AS legality_status
FROM cards
LEFT JOIN legalities ON cards.uuid = legalities.uuid;

-- 3. View ket hop sets va set_translations
CREATE VIEW v_set_translations AS
SELECT
    sets.id AS set_id,
    sets.code AS set_code,
    sets.name AS set_name,
    sets.releaseDate AS set_release_date,
    set_translations.language AS translation_language,
    set_translations.translation AS set_translation
FROM sets
LEFT JOIN set_translations ON sets.code = set_translations.setCode;
