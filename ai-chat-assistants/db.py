import sqlite3

DB = "travel.db"
DB_TIMEOUT = 10

def setup_airbnb_database():
    """Creates the airbnb_listings table and populates sample listings if empty."""
    with sqlite3.connect(DB) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS airbnb_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            property_name TEXT,
            property_type TEXT,
            price_per_night REAL,
            rating REAL,
            bedrooms INTEGER,
            amenities TEXT
        )""")
        
        cursor.execute("SELECT COUNT(*) FROM airbnb_listings")
        if cursor.fetchone()[0] == 0:
            listings = [
                ("paris", "Charming Montmartre Studio", "Studio", 95, 4.8, 1, "WiFi, Kitchen, Metro access"),
                ("paris", "Elegant Marais Apartment", "Apartment", 150, 4.9, 2, "WiFi, Balcony, Air Conditioning"),
                ("paris", "Eiffel View Loft", "Loft", 220, 4.7, 1, "WiFi, Rooftop access, Kitchen"),
                ("tokyo", "Shibuya Modern Capsule Suite", "Studio", 75, 4.6, 1, "WiFi, Smart TV, Onsen access"),
                ("tokyo", "Shinjuku City Apartment", "Apartment", 130, 4.8, 2, "WiFi, Kitchen, Gym"),
                ("tokyo", "Traditional Ryokan Room", "Traditional", 200, 4.9, 2, "WiFi, Onsen, Breakfast included"),
                ("new york", "Manhattan Studio Escape", "Studio", 180, 4.5, 1, "WiFi, Doorman, Gym"),
                ("new york", "Brooklyn Brownstone Room", "Room", 110, 4.7, 1, "WiFi, Garden, Kitchen"),
                ("new york", "Midtown Luxury Apartment", "Apartment", 350, 4.9, 3, "WiFi, Concierge, Rooftop pool"),
                ("bali", "Ubud Jungle Villa", "Villa", 120, 4.9, 2, "WiFi, Pool, Breakfast, Motorbike"),
                ("bali", "Seminyak Beach Bungalow", "Bungalow", 85, 4.7, 1, "WiFi, AC, Beach access"),
                ("bali", "Canggu Surf Cottage", "Cottage", 65, 4.6, 1, "WiFi, Kitchen, Surfboard rental"),
                ("london", "Covent Garden Flat", "Apartment", 160, 4.7, 1, "WiFi, Tube access, Kitchen"),
                ("london", "Notting Hill Townhouse", "Townhouse", 280, 4.8, 3, "WiFi, Garden, Parking"),
                ("london", "Shoreditch Artist Studio", "Studio", 120, 4.6, 1, "WiFi, Workspace, Bike"),
                ("dubai", "Downtown Marina Apartment", "Apartment", 200, 4.8, 2, "WiFi, Pool, Gym, Burj view"),
                ("dubai", "Palm Jumeirah Villa", "Villa", 500, 5.0, 4, "WiFi, Private pool, Beach, Butler"),
                ("dubai", "Old Town Studio", "Studio", 100, 4.5, 1, "WiFi, AC, Kitchen"),
                ("barcelona", "Gothic Quarter Flat", "Apartment", 100, 4.8, 2, "WiFi, Rooftop terrace, AC"),
                ("barcelona", "Barceloneta Beach Studio", "Studio", 135, 4.7, 1, "WiFi, Beach access, Kitchen"),
                ("bangkok", "Sukhumvit Modern Condo", "Apartment", 55, 4.7, 1, "WiFi, Pool, BTS access"),
                ("bangkok", "Riverside Boutique Room", "Room", 40, 4.6, 1, "WiFi, River view, Breakfast"),
                ("sydney", "Bondi Beach Apartment", "Apartment", 190, 4.8, 2, "WiFi, Ocean view, Parking"),
                ("sydney", "Harbour View Studio", "Studio", 160, 4.7, 1, "WiFi, Kitchen, Gym"),
                ("rome", "Trastevere Charming Flat", "Apartment", 110, 4.9, 2, "WiFi, Terrace, Kitchen"),
                ("rome", "Colosseum View Studio", "Studio", 140, 4.7, 1, "WiFi, AC, Historic building"),
            ]
            
            for city, property_name, property_type, price_per_night, rating, bedrooms, amenities in listings:
                cursor.execute("""
                    INSERT INTO airbnb_listings (city, property_name, property_type, price_per_night, rating, bedrooms, amenities)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (city, property_name, property_type, price_per_night, rating, bedrooms, amenities))
                
            conn.commit()

def get_airbnb_listings(city: str, max_budget=None) -> str:
    """Searches SQLite database for Airbnb listings matching city and budget."""
    print(f"SQLITE TOOL: Airbnb listings for {city} (budget: {max_budget})", flush=True)
    with sqlite3.connect(DB, timeout=DB_TIMEOUT) as conn:
        cursor = conn.cursor()
        if max_budget:
            cursor.execute("""
                SELECT property_name, property_type, price_per_night, rating, bedrooms, amenities
                FROM airbnb_listings
                WHERE city = ? AND price_per_night <= ?
                ORDER BY rating DESC LIMIT 5
            """, (city.lower(), float(max_budget)))
        else:
            cursor.execute("""
                SELECT property_name, property_type, price_per_night, rating, bedrooms, amenities
                FROM airbnb_listings
                WHERE city = ?
                ORDER BY rating DESC LIMIT 5
            """, (city.lower(),))
        rows = cursor.fetchall()
        
    if not rows:
        return (
            f"No Airbnb listings found for {city}. "
            f"Supported: Paris, Tokyo, New York, Bali, London, Dubai, Barcelona, Bangkok, Sydney, Rome."
        )
    result = f"Airbnb listings in {city.title()}:\n"
    for name, ptype, price, rating, beds, amenities in rows:
        result += f"\n- {name} ({ptype}): ${price:.0f}/night, Rating: {rating}/5, {beds} bed(s), {amenities}"
    return result
