import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def fiyat_avcisi(url):
    """
    Incehesap ve benzeri bot korumalı sitelerden fiyat çeken profesyonel bot.
    undetected-chromedriver kullanarak Cloudflare vb. engelleri aşar.
    """
    options = uc.ChromeOptions()
    
    # Arka planda çalışmasını istersen aşağıdaki satırı aktif et
    # options.add_argument('--headless') 

    print("Sessizce yaklaşıyor (Tarayıcı başlatılıyor)...")
    
    try:
        # Undetected Chromedriver başlatılıyor
        driver = uc.Chrome(options=options)
        driver.get(url)

        # Sayfanın ve fiyatın yüklenmesi için sabırla bekle
        # "cur-price" Incehesap'ın ana fiyat etiketidir.
        wait = WebDriverWait(driver, 15)
        fiyat_elementi = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cur-price")))

        if fiyat_elementi:
            fiyat = fiyat_elementi.text
            print(f"\n✅ Hedef Vuruldu!")
            print(f"Ürün Fiyatı: {fiyat}")
            return fiyat
        else:
            print("Fiyat etiketi bulunamadı, site yapısı değişmiş olabilir.")

    except Exception as e:
        print(f"Hata oluştu: {e}")
    
    finally:
        time.sleep(3) # Sonucu görmen için 3 saniye bekle
        driver.quit()

if __name__ == "__main__":
    # Örnek kullanım
    hedef_url = "https://www.incehesap.com/razer-cobra-rz01-04650100-r3m1-kablolu-mouse-fiyati-89508/"
    fiyat_avcisi(hedef_url)
