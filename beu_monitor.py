import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime
import urllib3

# SSL xəbərdarlıqlarını söndür
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Konfiqurasiya
TELEGRAM_BOT_TOKEN = "8228861868:AAH_MaOrJ_T_BORcq8LSSPObS3F__ha_eJk"
TELEGRAM_CHAT_ID = "1355481688"

# BEU Login məlumatları
BEU_BASE_URL = "https://my.beu.edu.az"
BEU_LOGIN_URL = f"{BEU_BASE_URL}/index.php"
BEU_GRADES_URL = f"{BEU_BASE_URL}/?mod=grades"
USERNAME = "230106049"
PASSWORD = "LTN2005055"

CHECK_INTERVAL = 300  # 5 dəqiqə
DATA_FILE = "beu_grades_data.json"

# Session yaradırıq
session = requests.Session()

# Headers əlavə edirik (bot kimi görünməmək üçün)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'az,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
})

def send_telegram_message(message):
    """Telegram botuna mesaj göndərir"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"Telegram xətası: {response.text}")
            return False
    except Exception as e:
        print(f"Telegram xətası: {e}")
        return False

def login_to_beu():
    """BEU saytına daxil olur"""
    try:
        print("🔐 Login edilir...")
        
        # İlk öncə ana səhifəni açırıq (cookie almaq üçün)
        response = session.get(BEU_LOGIN_URL, timeout=15, verify=False)
        
        if response.status_code != 200:
            print(f"❌ Ana səhifə açılmadı: {response.status_code}")
            return False
        
        # Login məlumatlarını göndəririk
        login_data = {
            "uname": USERNAME,
            "pass": PASSWORD,
            "submit": "Daxil ol"
        }
        
        # POST sorğusu
        response = session.post(
            BEU_LOGIN_URL, 
            data=login_data, 
            timeout=15,
            verify=False,
            allow_redirects=True
        )
        
        # Uğurlu login yoxlanışı - əgər redirect oldu və ya sessionda username varsa
        if response.status_code == 200:
            # Səhifədə username və ya "çıxış" linki varmı yoxlayırıq
            if USERNAME in response.text or "logout" in response.text.lower() or "çıxış" in response.text.lower():
                print("✅ Login uğurlu!")
                return True
        
        print(f"⚠️ Login statusu: {response.status_code}")
        # Debug üçün
        if len(response.text) < 500:
            print(f"Response: {response.text[:200]}")
        
        return True  # Bəzən redirect olur amma işləyir
            
    except requests.exceptions.ProxyError as e:
        print(f"❌ Proxy xətası: Sayta çatmaq mümkün deyil")
        print("💡 Həll: Öz kompüterinizdə işlədin və ya VPN istifadə edin")
        return False
    except Exception as e:
        print(f"❌ Login xətası: {e}")
        return False

def scrape_grades():
    """BEU-dan qiymətləri çəkir"""
    try:
        print("📥 Qiymətlər yüklənir...")
        
        # Qiymətlər səhifəsini açırıq
        response = session.get(BEU_GRADES_URL, timeout=15, verify=False)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"❌ Qiymətlər səhifəsi açılmadı: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        grades_data = {}
        
        # Semester başlığını tapırıq
        semester_info = soup.find('b', string=lambda x: x and 'semester' in x.lower())
        current_semester = semester_info.get_text(strip=True) if semester_info else "Unknown"
        
        # table-responsive div-i tapırıq
        table_div = soup.find('div', class_='table-responsive')
        
        if not table_div:
            print("⚠️ Cədvəl tapılmadı")
            return None
        
        table = table_div.find('table', class_='table')
        
        if not table:
            print("⚠️ Table elementi tapılmadı")
            return None
        
        tbody = table.find('tbody')
        
        if not tbody:
            print("⚠️ tbody tapılmadı")
            return None
        
        rows = tbody.find_all('tr')
        print(f"📊 {len(rows)} sətir tapıldı")
        
        for idx, row in enumerate(rows):
            try:
                # Fənn adını tapırıq (nowrap və left align olan td)
                subject_td = row.find('td', {'nowrap': 'nowrap', 'align': 'left'})
                
                if not subject_td:
                    continue
                
                subject = subject_td.get_text(strip=True)
                
                if not subject or subject == '':
                    continue
                
                # Bütün td-ləri alırıq
                all_tds = row.find_all('td')
                
                # İlk td fənn adıdır, qalanları qiymətlərdir
                grade_values = []
                for td in all_tds[1:]:  # İlk td-ni keçirik
                    value = td.get_text(strip=True)
                    # Boş, × və &nbsp; dəyərlərini keçirik
                    if value and value != '' and value != '×' and value != '\xa0':
                        grade_values.append(value)
                
                if grade_values:
                    grades_data[subject] = {
                        'semester': current_semester,
                        'grades': grade_values,
                        'timestamp': datetime.now().isoformat()
                    }
                    print(f"  ✓ {subject}: {grade_values}")
            
            except Exception as e:
                print(f"  ⚠️ Sətir {idx} oxunmadı: {e}")
                continue
        
        if grades_data:
            print(f"✅ {len(grades_data)} fənn tapıldı")
            return grades_data
        else:
            print("⚠️ Heç bir qiymət tapılmadı")
            return None
        
    except requests.exceptions.ProxyError:
        print(f"❌ Proxy xətası: Sayta çatmaq mümkün deyil")
        return None
    except Exception as e:
        print(f"❌ Scraping xətası: {e}")
        return None

def load_previous_data():
    """Əvvəlki məlumatları yükləyir"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    """Məlumatları saxlayır"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def format_grade_info(grades_list):
    """Qiymət siyahısını formatlaşdırır"""
    return " | ".join(str(g) for g in grades_list)

def compare_and_notify(old_data, new_data):
    """Dəyişiklikləri müqayisə edir və bildiriş göndərir"""
    if not new_data:
        return False
    
    changes = []
    
    # Yeni qiymətlər
    for subject, info in new_data.items():
        if subject not in old_data:
            grade_str = format_grade_info(info['grades'])
            changes.append(f"🆕 <b>Yeni qiymət</b>\n📚 {subject}\n📊 {grade_str}")
        else:
            # Dəyişiklik yoxlanışı
            old_grades = old_data[subject]['grades']
            new_grades = info['grades']
            
            if old_grades != new_grades:
                old_str = format_grade_info(old_grades)
                new_str = format_grade_info(new_grades)
                changes.append(f"📝 <b>Dəyişiklik</b>\n📚 {subject}\n❌ Köhnə: {old_str}\n✅ Yeni: {new_str}")
    
    # Silinmiş qiymətlər
    for subject in old_data:
        if subject not in new_data:
            changes.append(f"🗑 <b>Silinib:</b> {subject}")
    
    if changes:
        # İlk bildiriş
        header = f"🔔 <b>BEU Qiymət Yeniləməsi</b>\n"
        if new_data:
            first_subject = list(new_data.values())[0]
            header += f"📅 {first_subject.get('semester', '')}\n"
        header += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        header += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Uzun mesajı hissələrə bölürük (Telegram limiti 4096)
        max_per_message = 5
        for i in range(0, len(changes), max_per_message):
            chunk = changes[i:i+max_per_message]
            message = header if i == 0 else ""
            message += "\n\n".join(chunk)
            send_telegram_message(message)
            if i + max_per_message < len(changes):
                time.sleep(1)
        
        print("✅ Bildiriş göndərildi!")
        return True
    else:
        print("ℹ️ Dəyişiklik tapılmadı")
        return False

def main():
    """Əsas proqram döngəsi"""
    print("=" * 60)
    print("🎓 BEU Qiymət Monitoru")
    print("=" * 60)
    print(f"👤 Tələbə: {USERNAME}")
    print(f"⏱ Yoxlama intervalı: {CHECK_INTERVAL // 60} dəqiqə")
    print(f"🌐 URL: {BEU_BASE_URL}")
    print("=" * 60)
    
    # İlk login
    if not login_to_beu():
        error_msg = "❌ BEU-ya login uğursuz!\n\n"
        error_msg += "💡 PythonAnywhere proxy bloklayır.\n"
        error_msg += "Həll yolları:\n"
        error_msg += "1. Öz kompüterinizdə işlədin\n"
        error_msg += "2. VPS istifadə edin (Oracle, AWS)\n"
        error_msg += "3. Render.com və ya Railway.app"
        send_telegram_message(error_msg)
        print("\n" + error_msg)
        return
    
    send_telegram_message(f"✅ BEU Qiymət Monitoru aktivdir!\n👤 Tələbə: {USERNAME}")
    
    previous_data = load_previous_data()
    login_time = time.time()
    failed_attempts = 0
    
    while True:
        try:
            # Hər 30 dəqiqədən bir yenidən login
            if time.time() - login_time > 1800:
                print("\n🔄 Session yenilənir...")
                login_to_beu()
                login_time = time.time()
            
            print(f"\n{'=' * 60}")
            print(f"⏳ Yoxlanma: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            print(f"{'=' * 60}")
            
            current_data = scrape_grades()
            
            if current_data:
                if not previous_data:
                    # İlk dəfə - bütün qiymətləri göstər
                    message = "📋 <b>Cari Qiymətlər</b>\n"
                    if current_data:
                        first_subject = list(current_data.values())[0]
                        message += f"📅 {first_subject.get('semester', '')}\n"
                    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
                    
                    count = 0
                    for subject, info in current_data.items():
                        grade_str = format_grade_info(info['grades'])
                        message += f"📚 {subject}\n📊 {grade_str}\n\n"
                        count += 1
                        
                        # Hər 8 fənndən sonra yeni mesaj
                        if count % 8 == 0:
                            send_telegram_message(message)
                            time.sleep(1)
                            message = ""
                    
                    if message:
                        send_telegram_message(message)
                else:
                    compare_and_notify(previous_data, current_data)
                
                previous_data = current_data
                save_data(current_data)
                failed_attempts = 0
                
                print(f"✅ Uğurlu yoxlama")
            else:
                failed_attempts += 1
                print(f"⚠️ Məlumat alınmadı (Cəhd: {failed_attempts})")
                
                if failed_attempts >= 3:
                    print("🔄 Yenidən login...")
                    if login_to_beu():
                        failed_attempts = 0
                        login_time = time.time()
                    else:
                        if failed_attempts >= 5:
                            send_telegram_message("⚠️ BEU-ya bağlantı problemi! Yoxlamalar davam edir...")
                            failed_attempts = 0
            
            print(f"\n💤 Növbəti yoxlama: {CHECK_INTERVAL // 60} dəqiqə sonra...")
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n⛔ Proqram dayandırıldı")
            send_telegram_message("⛔ BEU Qiymət Monitoru dayandırıldı")
            break
            
        except Exception as e:
            print(f"\n❌ Gözlənilməz xəta: {e}")
            failed_attempts += 1
            if failed_attempts >= 5:
                send_telegram_message(f"❌ Xəta:\n{str(e)[:200]}")
                failed_attempts = 0
            time.sleep(60)

if __name__ == "__main__":
    main()
