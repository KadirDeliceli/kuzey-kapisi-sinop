import sqlite3

def init_db():
    # Veritabanı bağlantısını oluştur (yoksa otomatik oluşturulur)
    conn = sqlite3.connect("kuzey_kapisi.db")
    cursor = conn.cursor()

    # Tabloyu oluştur
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mekanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            enlem REAL NOT NULL,
            boylam REAL NOT NULL,
            sure_dk INTEGER NOT NULL,
            tur TEXT NOT NULL
        )
    ''')

    # Eğer script birden fazla kez çalıştırılırsa verilerin tekrar etmemesi için tabloyu temizle
    cursor.execute('DELETE FROM mekanlar')

    # Tarihi ve Kültürel Mekanlar (tur = 'kültür')
    kultur_mekanlari = [
        ("Alaaddin Camii", 42.02639, 35.14833, 45),
        ("Balatlar Kilisesi", 42.02610, 35.15720, 60),
        ("Boyabat Kalesi", 41.466468583929625, 34.76203977903898, 120),
        ("Çeçe Sultan Türbesi", 41.709878558232006, 35.20180203266355, 30),
        ("Etnografya Müzesi", 42.02643027681542, 35.15310839068047, 60),
        ("Gerze Yakup Ağa Konağı", 41.80275394178541, 35.19657521890077, 45),
        ("İnceburun Deniz Feneri", 42.09794921112268, 34.94500709584895, 90),
        ("İsfendiyaroğulları Türbesi", 42.02682715867128, 35.14867131330844, 30),
        ("Korucuk Tabyası", 42.00580850324528, 35.1148121615561, 45),
        ("Paşa Tabyaları", 42.01722733727293, 35.180676757898055, 90),
        ("Pervane Medresesi", 42.02754479177251, 35.14827946510711, 60),
        ("Şehitler Çeşmesi", 42.024987618281386, 35.14869644182112, 20),
        ("Seyyid İbrahim Bilal Türbesi", 42.026050007515686, 35.16177924182181, 45),
        ("Sinop Arkeoloji Müzesi", 42.0285234734223, 35.1515892264805, 90),
        ("Sinop Cezaevi", 42.02530507266257, 35.142909442081255, 150),
        ("Sinop Kalesi", 42.024757963261635, 35.15075229574729, 90),
        ("Terelek Salar Kaya Mezarları", 41.358793898630665, 35.13955656008156, 60)
    ]

    # Doğal Güzellikler ve Plajlar (tur = 'doğa')
    doga_mekanlari = [
        ("Akgöl", 41.700540426027615, 34.595859189272154, 120),
        ("Akliman", 42.05243430991125, 35.047903754711704, 90),
        ("Aksu Yaylası", 41.76454, 34.30137, 120),
        ("Babaçay Kanyonu", 41.857495877603085, 34.600326815320216, 150),
        ("Bazalt Kayalıkları", 41.47483229097665, 34.64070729589813, 90),
        ("Dranaz Dağı", 41.63730, 34.86900, 90),
        ("DSİ Kampı Sahili", 42.00697761878878, 35.116660941477356, 120),
        ("Erfelek Şelaleleri", 41.840623357666544, 34.7797817871111, 180),
        ("Hamsilos Fiyordu", 42.06054813424209, 35.04526145723381, 90),
        ("Hasandere Şelalesi", 41.88417834677544, 34.943968503999585, 90),
        ("İnaltı Mağarası", 41.73176159034244, 34.56850336473503, 90),
        ("Karakum Plajı", 42.01540909657001, 35.19194589163349, 120),
        ("Şahin Tepesi", 42.028557123203775, 35.16440547473181, 60),
        ("Sarıkum Koruma Alanı", 42.012566390066105, 34.92922969336241, 120),
        ("Sarıkum Plajı", 42.02238156032539, 34.90251897976251, 120),
        ("Sorkun Şelaleleri", 41.771187800415724, 35.06906092867353, 90)
    ]

    # Verileri tabloya ekle
    insert_query = "INSERT INTO mekanlar (ad, enlem, boylam, sure_dk, tur) VALUES (?, ?, ?, ?, ?)"
    
    for mekan in kultur_mekanlari:
        cursor.execute(insert_query, (mekan[0], mekan[1], mekan[2], mekan[3], 'kültür'))
        
    for mekan in doga_mekanlari:
        cursor.execute(insert_query, (mekan[0], mekan[1], mekan[2], mekan[3], 'doğa'))

    # Değişiklikleri kaydet ve bağlantıyı kapat
    conn.commit()
    conn.close()
    print("Veritabanı 'kuzey_kapisi.db' başarıyla oluşturuldu ve veriler eklendi.")

def view_data():
    try:
        # Veritabanına bağlan
        conn = sqlite3.connect("kuzey_kapisi.db")
        cursor = conn.cursor()

        # Tüm verileri seç
        cursor.execute("SELECT * FROM mekanlar")
        rows = cursor.fetchall()

        # Tablo başlıklarını yazdır
        print(f"{'ID':<4} | {'Mekan Adı':<32} | {'Enlem':<10} | {'Boylam':<10} | {'Süre (dk)':<9} | {'Tür':<10}")
        print("-" * 85)

        # Satırları döngüye alıp formatlı şekilde yazdır
        for row in rows:
            id_, ad, enlem, boylam, sure, tur = row
            # Enlem ve boylamı okunabilir olması için 6 ondalık basamakla sınırla
            print(f"{id_:<4} | {ad:<32} | {enlem:<10.6f} | {boylam:<10.6f} | {sure:<9} | {tur:<10}")

    except sqlite3.Error as e:
        print(f"Veritabanı okunurken hata oluştu: {e}")
    finally:
        # Bağlantıyı kapat
        if conn:
            conn.close()


if __name__ == '__main__':
    #init_db()
    view_data()
