-- Views thu cong cho database student_club (Paper V-SQL style)

-- 1. View thong tin thanh vien kem nganh hoc va dia chi
CREATE VIEW v_member_details AS
SELECT
    member.member_id,
    member.first_name,
    member.last_name,
    member.email,
    member.position,
    member.t_shirt_size,
    member.phone,
    major.major_name,
    major.department AS major_department,
    major.college AS major_college,
    zip_code.city,
    zip_code.county,
    zip_code.state
FROM member
LEFT JOIN major ON member.link_to_major = major.major_id
LEFT JOIN zip_code ON member.zip = zip_code.zip_code;

-- 2. View thong tin su kien va ngan sach
CREATE VIEW v_event_budget AS
SELECT
    budget.budget_id,
    budget.category AS budget_category,
    budget.amount AS budget_amount,
    budget.spent AS budget_spent,
    budget.remaining AS budget_remaining,
    event.event_id,
    event.event_name,
    event.event_date,
    event.type AS event_type,
    event.location AS event_location,
    event.status AS event_status
FROM budget
LEFT JOIN event ON budget.link_to_event = event.event_id;

-- 3. View chi phi kem thong tin ngan sach, su kien va thanh vien
CREATE VIEW v_expense_details AS
SELECT
    expense.expense_id,
    expense.expense_description,
    expense.expense_date,
    expense.cost,
    expense.approved,
    member.first_name AS member_first_name,
    member.last_name AS member_last_name,
    budget.category AS budget_category,
    event.event_name
FROM expense
LEFT JOIN budget ON expense.link_to_budget = budget.budget_id
LEFT JOIN event ON budget.link_to_event = event.event_id
LEFT JOIN member ON expense.link_to_member = member.member_id;
