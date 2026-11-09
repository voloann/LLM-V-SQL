-- Views thu cong cho database california_schools (Paper V-SQL style)

CREATE VIEW v_school_profile AS
SELECT
    schools.CDSCode,
    schools.School,
    schools.District,
    schools.County,
    schools.City,
    schools.Zip,
    schools.Latitude,
    schools.Longitude,
    schools.Charter,
    schools.FundingType,
    frpm.`Academic Year` AS academic_year,
    frpm.`Charter School (Y/N)` AS charter_school_yn,
    frpm.`Enrollment (K-12)` AS enrollment_k12,
    frpm.`Free Meal Count (K-12)` AS free_meal_count,
    frpm.`Percent (%) Eligible Free (K-12)` AS pct_eligible_free,
    frpm.`FRPM Count (K-12)` AS frpm_count,
    frpm.`Percent (%) Eligible FRPM (K-12)` AS pct_eligible_frpm,
    satscores.rtype,
    satscores.enroll12,
    satscores.NumTstTakr,
    satscores.AvgScrRead,
    satscores.AvgScrMath,
    satscores.AvgScrWrite,
    satscores.NumGE1500
FROM schools
LEFT JOIN frpm ON schools.CDSCode = frpm.CDSCode
LEFT JOIN satscores ON schools.CDSCode = satscores.cds;
