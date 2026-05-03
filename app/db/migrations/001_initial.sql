-- 001_initial.sql — full Phase 1 schema.
-- Money values are stored as INTEGER paise.
-- Dates are ISO TEXT 'YYYY-MM-DD' (or full datetimes via datetime('now')).

-- ---------------------------------------------------------------------------
-- meta
-- ---------------------------------------------------------------------------
CREATE TABLE schools (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    email TEXT,
    logo_path TEXT,
    affiliation_no TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE academic_years (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- people (staff first so classes can reference it)
-- ---------------------------------------------------------------------------
CREATE TABLE staff (
    id INTEGER PRIMARY KEY,
    emp_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    joining_date TEXT,
    qualification TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- ---------------------------------------------------------------------------
-- structure
-- ---------------------------------------------------------------------------
CREATE TABLE classes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    section TEXT NOT NULL,
    academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
    class_teacher_id INTEGER REFERENCES staff(id),
    UNIQUE(name, section, academic_year_id)
);

CREATE TABLE subjects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    max_marks INTEGER NOT NULL DEFAULT 100,
    is_optional INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    admission_no TEXT NOT NULL UNIQUE,
    roll_no INTEGER,
    first_name TEXT NOT NULL,
    last_name TEXT,
    dob TEXT,
    gender TEXT CHECK(gender IN ('M','F','O')),
    blood_group TEXT,
    photo_path TEXT,
    class_id INTEGER REFERENCES classes(id),
    admission_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    father_name TEXT,
    father_phone TEXT,
    father_occupation TEXT,
    mother_name TEXT,
    mother_phone TEXT,
    mother_occupation TEXT,
    guardian_name TEXT,
    guardian_phone TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    pincode TEXT,
    aadhaar TEXT,
    prev_school TEXT,
    category TEXT,
    religion TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_students_class ON students(class_id, status);
CREATE INDEX idx_students_admission_no ON students(admission_no);
CREATE INDEX idx_students_name ON students(first_name, last_name);

-- ---------------------------------------------------------------------------
-- attendance
-- ---------------------------------------------------------------------------
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('P','A','L','H')),
    marked_by INTEGER REFERENCES staff(id),
    marked_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, date)
);
CREATE INDEX idx_attendance_date ON attendance(date);
CREATE INDEX idx_attendance_student_date ON attendance(student_id, date);

-- ---------------------------------------------------------------------------
-- exams
-- ---------------------------------------------------------------------------
CREATE TABLE exams (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
    exam_type TEXT,
    start_date TEXT,
    end_date TEXT,
    weightage INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE marks (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    marks_obtained REAL,
    max_marks INTEGER NOT NULL,
    grade TEXT,
    remarks TEXT,
    UNIQUE(exam_id, student_id, subject_id)
);
CREATE INDEX idx_marks_student ON marks(student_id, exam_id);
CREATE INDEX idx_marks_exam ON marks(exam_id);

-- ---------------------------------------------------------------------------
-- fees (money in paise)
-- ---------------------------------------------------------------------------
CREATE TABLE fee_structure (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
    head TEXT NOT NULL,
    amount_paise INTEGER NOT NULL,
    frequency TEXT NOT NULL,
    due_month INTEGER
);

CREATE TABLE fee_payments (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    receipt_no TEXT NOT NULL UNIQUE,
    payment_date TEXT NOT NULL,
    amount_paise INTEGER NOT NULL,
    mode TEXT NOT NULL,
    reference_no TEXT,
    remarks TEXT,
    collected_by INTEGER REFERENCES staff(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_payments_student ON fee_payments(student_id, payment_date);
CREATE INDEX idx_payments_date ON fee_payments(payment_date);

CREATE TABLE fee_payment_items (
    id INTEGER PRIMARY KEY,
    fee_payment_id INTEGER NOT NULL REFERENCES fee_payments(id) ON DELETE CASCADE,
    fee_structure_id INTEGER REFERENCES fee_structure(id),
    head TEXT NOT NULL,
    amount_paise INTEGER NOT NULL,
    for_month INTEGER,
    for_year INTEGER
);

-- ---------------------------------------------------------------------------
-- misc
-- ---------------------------------------------------------------------------
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    doc_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- auth & audit (created before remarks because remarks references users)
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    full_name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE remarks (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    category TEXT,
    note TEXT NOT NULL,
    by_user INTEGER REFERENCES users(id)
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    details TEXT
);
CREATE INDEX idx_audit_time ON audit_log(timestamp);
