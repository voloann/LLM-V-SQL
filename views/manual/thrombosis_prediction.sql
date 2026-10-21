-- Views thu cong cho database thrombosis_prediction (Paper V-SQL style)

-- 1. View ket hop thong tin benh nhan va xet nghiem Laboratory
CREATE VIEW v_patient_lab AS
SELECT
    Patient.ID AS patient_id,
    Patient.SEX AS sex,
    Patient.Birthday AS birthday,
    Patient.Admission AS admission,
    Patient.Diagnosis AS patient_diagnosis,
    Laboratory.Date AS lab_date,
    Laboratory.GOT,
    Laboratory.GPT,
    Laboratory.LDH,
    Laboratory.ALP,
    Laboratory.TP,
    Laboratory.ALB,
    Laboratory.UA,
    Laboratory.UN,
    Laboratory.CRE,
    Laboratory.`T-BIL` AS t_bil,
    Laboratory.`T-CHO` AS t_cho,
    Laboratory.TG,
    Laboratory.CPK,
    Laboratory.GLU,
    Laboratory.WBC,
    Laboratory.RBC,
    Laboratory.HGB,
    Laboratory.HCT,
    Laboratory.PLT,
    Laboratory.PT,
    Laboratory.APTT,
    Laboratory.FG,
    Laboratory.CRP,
    Laboratory.IGG,
    Laboratory.IGA,
    Laboratory.IGM
FROM Patient
LEFT JOIN Laboratory ON Patient.ID = Laboratory.ID;

-- 2. View ket hop thong tin benh nhan va ket qua Examination
CREATE VIEW v_patient_exam AS
SELECT
    Patient.ID AS patient_id,
    Patient.SEX AS sex,
    Patient.Birthday AS birthday,
    Patient.Admission AS admission,
    Examination.`Examination Date` AS exam_date,
    Examination.`aCL IgG` AS acl_igg,
    Examination.`aCL IgM` AS acl_igm,
    Examination.ANA,
    Examination.`ANA Pattern` AS ana_pattern,
    Examination.Diagnosis AS exam_diagnosis,
    Examination.Symptoms AS symptoms,
    Examination.Thrombosis AS thrombosis
FROM Patient
LEFT JOIN Examination ON Patient.ID = Examination.ID;
