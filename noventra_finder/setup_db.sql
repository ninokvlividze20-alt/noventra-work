-- კომპანიების ცხრილი
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- პროდუქტების ცხრილი
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2),
    old_price DECIMAL(10, 2),
    discount_percent VARCHAR(10),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- პორტფოლიოების/რეკლამების ცხრილი (განახლებული is_paid სვეტით)
CREATE TABLE IF NOT EXISTS portfolios (
    slot_id INT PRIMARY KEY,
    business_name VARCHAR(255) NOT NULL,
    description TEXT,
    phone VARCHAR(50),
    email VARCHAR(255),
    photo_path VARCHAR(255),
    social_fb VARCHAR(255),
    social_ig VARCHAR(255),
    social_tt VARCHAR(255),
    social_yt VARCHAR(255),
    is_paid BOOLEAN DEFAULT FALSE, -- აქ არის გადახდის სტატუსი
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
