from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import psycopg2

# ბაზის კონფიგურაცია
DB_CONFIG = {"dbname": "noventra_db", "user": "mac", "password": "noventra2026", "host": "localhost"}

def scrape_carrefour():
    url = "https://www.carrefour.ge/ka/c/F0101"
    
    print(f"🚀 ვიწყებ კარფურის მონაცემების წამოღებას უჩინარი ბრაუზერით...")
    
    with sync_playwright() as p:
        # ვხსნით უჩინარ ბრაუზერს
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # მივდივართ გვერდზე და ველოდებით ჩატვირთვას
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(5000) # დამატებითი დაყოვნება სრული ჩატვირთვისთვის
        
        # ვიღებთ HTML-ს
        content = page.content()
        browser.close()

    soup = BeautifulSoup(content, 'html.parser')
    
    # ვპოულობთ პროდუქტებს. 
    # თუ 'product-item' კლასი არ მუშაობს, Inspect-ით უნდა ვნახოთ ახალი კლასი
    products = soup.find_all('div', class_='product-item') 
    
    if not products:
        print("❌ პროდუქტები ვერ მოიძებნა. შესაძლოა კლასების სახელები შეიცვალა.")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # ძველი მონაცემების გასუფთავება
    cur.execute("DELETE FROM products")
    
    count = 0
    for p in products:
        try:
            # ვეძებთ სახელს და ფასს უსაფრთხოდ
            name_tag = p.find('h3')
            price_tag = p.find('span', class_='price')
            
            if name_tag and price_tag:
                name = name_tag.text.strip()
                # ფასიდან ვშლით სიმბოლოებს და ვტოვებთ მხოლოდ რიცხვს
                price = price_tag.text.strip().replace("₾", "").strip()
                
                cur.execute("INSERT INTO products (name, price) VALUES (%s, %s)", (name, price))
                count += 1
                print(f"✅ დაემატა: {name} | ფასი: {price}")
        except Exception as e:
            print(f"⚠️ შეცდომა პროდუქტის დამუშავებისას: {e}")
            continue
        
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ დასრულდა! სულ დაემატა {count} პროდუქტი.")

if __name__ == "__main__":
    scrape_carrefour()
