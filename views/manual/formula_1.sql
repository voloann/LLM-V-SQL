-- Views thu cong cho database formula_1 (Paper V-SQL style)

-- 1. View ket qua chang dua kem thong tin tay dua, doi dua va chang dua
CREATE VIEW v_race_results AS
SELECT
    results.resultId AS result_id,
    results.number AS car_number,
    results.grid,
    results.position,
    results.positionOrder AS position_order,
    results.points,
    results.laps,
    results.fastestLap AS fastest_lap,
    results.fastestLapSpeed AS fastest_lap_speed,
    drivers.driverId AS driver_id,
    drivers.driverRef AS driver_ref,
    drivers.forename AS driver_forename,
    drivers.surname AS driver_surname,
    drivers.nationality AS driver_nationality,
    constructors.constructorId AS constructor_id,
    constructors.name AS constructor_name,
    races.raceId AS race_id,
    races.year AS race_year,
    races.round AS race_round,
    races.name AS race_name,
    races.date AS race_date,
    status.status AS result_status
FROM results
LEFT JOIN races ON results.raceId = races.raceId
LEFT JOIN drivers ON results.driverId = drivers.driverId
LEFT JOIN constructors ON results.constructorId = constructors.constructorId
LEFT JOIN status ON results.statusId = status.statusId;

-- 2. View chang dua kem thong tin truong dua (circuits)
CREATE VIEW v_race_circuits AS
SELECT
    races.raceId AS race_id,
    races.year AS race_year,
    races.round AS race_round,
    races.name AS race_name,
    races.date AS race_date,
    circuits.circuitId AS circuit_id,
    circuits.circuitRef AS circuit_ref,
    circuits.name AS circuit_name,
    circuits.location AS circuit_location,
    circuits.country AS circuit_country
FROM races
LEFT JOIN circuits ON races.circuitId = circuits.circuitId;

-- 3. View vong phan hang qualifying kem tay dua va doi dua
CREATE VIEW v_qualifying_driver AS
SELECT
    qualifying.qualifyId AS qualify_id,
    qualifying.position AS qualify_position,
    qualifying.q1,
    qualifying.q2,
    qualifying.q3,
    drivers.driverId AS driver_id,
    drivers.forename AS driver_forename,
    drivers.surname AS driver_surname,
    constructors.name AS constructor_name,
    races.raceId AS race_id,
    races.name AS race_name,
    races.year AS race_year
FROM qualifying
LEFT JOIN drivers ON qualifying.driverId = drivers.driverId
LEFT JOIN races ON qualifying.raceId = races.raceId
LEFT JOIN constructors ON qualifying.constructorId = constructors.constructorId;
