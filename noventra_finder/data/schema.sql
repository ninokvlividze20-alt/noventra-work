-- მთავარი ცხრილი ყველაფრისთვის
CREATE TABLE listings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL, -- მაგ: 'tech', 'education', 'beauty'
    type VARCHAR(50) NOT NULL, -- მაგ: 'product', 'service', 'course'
    provider_name VARCHAR(255), -- კომპანიის ან კერძო პირის სახელი
    price DECIMAL(10, 2),
    is_network BOOLEAN DEFAULT FALSE, -- ქსელურია თუ არა
    url VARCHAR(500), -- საიდან მოვა მონაცემი
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- დამატებითი დეტალები (JSONB საშუალებას გვაძლევს ნებისმიერი სხვა მონაცემი შევინახოთ)
CREATE TABLE listing_attributes (
    id SERIAL PRIMARY KEY,
    listing_id INT REFERENCES listings(id),
    attr_key VARCHAR(100), -- მაგ: 'duration', 'location', 'experience'
    attr_value TEXT
);
