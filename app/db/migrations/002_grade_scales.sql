-- 002_grade_scales.sql -- configurable grade bands.
-- Lookup: grade = (highest min_percent <= pct) where pct between min and max.
-- Defaults are non-overlapping. The Settings UI (Phase 8) will let the
-- school edit these.

CREATE TABLE grade_scales (
    id INTEGER PRIMARY KEY,
    grade TEXT NOT NULL UNIQUE,
    min_percent REAL NOT NULL,
    max_percent REAL NOT NULL,
    remarks TEXT,
    CHECK(min_percent >= 0 AND max_percent <= 100 AND min_percent <= max_percent)
);

INSERT INTO grade_scales (grade, min_percent, max_percent, remarks) VALUES
    ('A+', 90.00, 100.00, 'Outstanding'),
    ('A',  80.00,  89.99, 'Excellent'),
    ('B+', 70.00,  79.99, 'Very Good'),
    ('B',  60.00,  69.99, 'Good'),
    ('C+', 50.00,  59.99, 'Above Average'),
    ('C',  40.00,  49.99, 'Average'),
    ('D',  33.00,  39.99, 'Pass'),
    ('F',   0.00,  32.99, 'Fail');
