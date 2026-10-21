-- Views thu cong cho database financial (Paper V-SQL style)

-- 1. View ket hop khach hang va thong tin quan/huyen (district)
CREATE VIEW v_client_district AS
SELECT
    client.client_id,
    client.gender,
    client.birth_date,
    district.district_id,
    district.A2 AS district_name,
    district.A3 AS region,
    district.A4 AS no_of_inhabitants,
    district.A11 AS avg_salary
FROM client
LEFT JOIN district ON client.district_id = district.district_id;

-- 2. View ket hop tai khoan va thong tin quan/huyen
CREATE VIEW v_account_district AS
SELECT
    account.account_id,
    account.frequency,
    account.date AS account_created_date,
    district.district_id,
    district.A2 AS district_name,
    district.A3 AS region,
    district.A11 AS avg_salary
FROM account
LEFT JOIN district ON account.district_id = district.district_id;

-- 3. View ket hop tai khoan va khoan vay (loan)
CREATE VIEW v_account_loan AS
SELECT
    account.account_id,
    account.frequency,
    account.date AS account_date,
    loan.loan_id,
    loan.date AS loan_date,
    loan.amount AS loan_amount,
    loan.duration AS loan_duration,
    loan.payments AS loan_payments,
    loan.status AS loan_status
FROM account
LEFT JOIN loan ON account.account_id = loan.account_id;
