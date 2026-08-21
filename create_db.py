import sqlite3


def init_db():
    conn = sqlite3.connect("kuzey_kapisi.db")
    cursor = conn.cursor()

    # VARSA ESKİ TABLOYU KOMPLE SİL (Böylece ID sayacı da sıfırlanır)
    cursor.execute('DROP TABLE IF EXISTS mekanlar')

    # Tabloyu sıfırdan tertemiz oluştur
    cursor.execute('''
        CREATE TABLE mekanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            enlem REAL NOT NULL,
            boylam REAL NOT NULL,
            sure_dk INTEGER NOT NULL,
            aciklama TEXT NOT NULL
        )
    ''')

    cursor.execute('DELETE FROM mekanlar')

    # Tarihi ve Kültürel Mekanlar (tur = 'kültür')
    # Format: (Ad, Enlem, Boylam, Süre, Açıklama)
    kultur_mekanlari = [
        ("Alaaddin Camii - İsfendiyaroğulları Türbesi", 42.02639, 35.14833, 30,
         "Sinop merkezde yer alan, Selçuklu mimarisinin en güzel örneklerinden biri olan tarihi ulu camidir.Candaroğulları beyliğine ait tarihi ve mimari öneme sahip zarif bir anıt mezarıda buradadır."),
        ("Balatlar Kilisesi", 42.02610, 35.15720, 45,
         "Sinop merkezde bulunan, Roma ve Bizans dönemlerinden kalma, tarihi freskleriyle dikkat çeken yapı kompleksidir."),
        ("Boyabat Kalesi", 41.466468583929625, 34.76203977903898, 120,
         "Boyabat ilçesinde sarp kayalıklar üzerine inşa edilmiş, yeraltı dehlizleri ve heybetli duruşuyla ünlü tarihi kaledir."),
        ("Çeçe Sultan Türbesi", 41.709878558232006, 35.20180203266355, 30,
         "Gerze ilçesi Yenikent köyü yakınlarında bulunan, bölge halkı için manevi değeri yüksek tarihi bir türbedir."),
        ("Etnografya Müzesi", 42.02643027681542, 35.15310839068047, 45,
         "Sinop merkezde tarihi Aslan Torun Konağı'nda yer alan, yöresel kültürü ve yaşam tarzını yansıtan zengin bir müzedir."),
        ("Gerze Yakup Ağa Konağı", 41.80275394178541, 35.19657521890077, 25,
         "Gerze ilçe merkezinde yer alan, geleneksel sivil Türk mimarisinin estetik detaylarını barındıran tarihi konaktır."),
        ("İnceburun Deniz Feneri", 42.09794921112268, 34.94500709584895, 90,
         "Türkiye'nin en kuzey ucunda yer alan, hırçın Karadeniz manzarasına hakim 19. yüzyıldan kalma sembolik deniz feneridir."),
        ("Korucuk Tabyası", 42.00580850324528, 35.1148121615561, 45,
         "Sinop'u denizden gelebilecek tehlikelere karşı korumak amacıyla inşa edilmiş, tarihi bir Osmanlı savunma yapısıdır."),
        ("Paşa Tabyaları", 42.01722733727293, 35.180676757898055, 60,
         "Sinop yarımadasını korumak için 19. yüzyılda yapılan, yarı ay şeklindeki mimarisiyle dikkat çeken topçu tabyasıdır."),
        ("Pervane Medresesi", 42.02754479177251, 35.14827946510711, 30,
         "Alaaddin Camii'nin karşısında yer alan, Selçuklu Veziri Pervane tarafından yaptırılmış tarihi bir eğitim kurumudur."),
        ("Şehitler Çeşmesi", 42.024987618281386, 35.14869644182112, 20,
         "Sinop merkezde bulunan, tersane baskınında şehit düşen denizciler anısına yaptırılmış tarihi öneme sahip çeşmedir."),
        ("Seyyid İbrahim Bilal Türbesi", 42.026050007515686, 35.16177924182181, 30,
         "Sinop merkezde, manevi atmosferi ve şehre hakim manzarasıyla bilinen önemli bir ziyaret ve inanç noktasıdır."),
        ("Sinop Arkeoloji Müzesi", 42.0285234734223, 35.1515892264805, 60,
         "Şehir merkezinde yer alan, antik çağlardan Roma'ya kadar bölgenin zengin tarihi buluntularının sergilendiği müzedir."),
        ("Sinop Cezaevi", 42.02530507266257, 35.142909442081255, 120,
         "Tarihi kale surları içinde yer alan, 'Anadolu'nun Alkatraz'ı' olarak bilinen ve günümüzde müze olan eski cezaevidir."),
        ("Sinop Kalesi", 42.024757963261635, 35.15075229574729, 90,
         "Sinop yarımadasının boynunu çepeçevre saran, antik çağlardan günümüze ulaşmış devasa ve görkemli tarihi surlardır."),
        ("Terelek Salar Kaya Mezarları", 41.358793898630665, 35.13955656008156, 60,
         "Boyabat ilçesinde yer alan, yüksek kayalıklara oyulmuş antik çağlardan kalma etkileyici ve gizemli kaya mezarlarıdır."),
        ("Aşıklar Caddesi", 42.022766224723796, 35.15434599673018, 100,
         "Sinop merkezde deniz kenarında uzanan, kafeleri ve yürüyüş yollarıyla şehrin en popüler sahil caddesidir."),
        ("Sakarya Caddesi", 42.02570757456466, 35.14446429840562, 90,
         "Sinop merkezde yer alan, alışveriş dükkanları ve ticari hayatıyla şehrin en hareketli ana caddelerinden biridir.")
    ]

    # Doğal Güzellikler ve Plajlar (tur = 'doğa')
    doga_mekanlari = [
        ("Akgöl", 41.700540426027615, 34.595859189272154, 120,
         "Ayancık ilçesinde yer alan, etrafı sık köknar ormanlarıyla çevrili huzur verici ve pitoresk bir krater gölüdür."),
        ("Akliman", 42.05243430991125, 35.047903754711704, 120,
         "Sinop merkeze yakın, yemyeşil ormanların sakin bir denizle kucaklaştığı doğal bir liman ve mesire alanıdır."),
        ("Aksu Yaylası", 41.76454, 34.30137, 120,
         "Ayancık sınırlarında yer alan, çam kokulu havası ve el değmemiş doğasıyla trekking tutkunlarını çeken serin bir yayladır."),
        ("Babaçay Kanyonu", 41.857495877603085, 34.600326815320216, 150,
         "Ayancık ilçesinde bulunan, harika yürüyüş rotalarına ve sarp kayalıklara ev sahipliği yapan vahşi bir doğa harikasıdır."),
        ("Bazalt Kayalıkları", 41.47483229097665, 34.64070729589813, 90,
         "Boyabat'ta yer alan, volkanik lavların soğumasıyla oluşmuş devasa altıgen prizma şeklindeki nadir kaya oluşumlarıdır."),
        ("Dranaz Dağı", 41.63730, 34.86900, 90,
         "Sinop ile Boyabat arasında uzanan, çam ormanlarıyla kaplı ve kış aylarında harika manzaralar sunan heybetli geçittir."),
        ("DSİ Kampı Sahili", 42.00697761878878, 35.116660941477356, 120,
         "Sinop merkezde bulunan, ince kumu ve temiz deniziyle yaz aylarında yüzmek ve dinlenmek için popüler olan sahil şerididir."),
        ("Erfelek Şelaleleri", 41.840623357666544, 34.7797817871111, 180,
         "Erfelek ilçesinde orman içinde peş peşe sıralanmış 28 irili ufaklı şelaleden oluşan, eşsiz bir macera ve doğa alanıdır."),
        ("Hamsilos Fiyordu", 42.06054813424209, 35.04526145723381, 40,
         "Buzul aşındırmasıyla oluşmuş, Türkiye'nin tek fiyordu olarak bilinen ve denizin kara içine girdiği harika bir tabiat parkıdır."),
        ("Hasandere Şelalesi", 41.88417834677544, 34.943968503999585, 90,
         "Sıkı bir orman dokusunun içinde saklanmış, huzur verici su sesi ve serinliğiyle öne çıkan gizli bir şelaledir."),
        ("İnaltı Mağarası", 41.73176159034244, 34.56850336473503, 90,
         "Ayancık ilçesinde yer alan, aydınlatılmış yürüyüş yolları, devasa sarkıt ve dikitleriyle büyüleyici bir yeraltı mağarasıdır."),
        ("Karakum Plajı", 42.01540909657001, 35.19194589163349, 120,
         "Sinop merkezde yer alan, volkanik patlamalar sonucu oluşmuş siyah kumuyla ünlü ve şifalı olduğuna inanılan popüler plajdır."),
        ("Şahin Tepesi", 42.028557123203775, 35.16440547473181, 45,
         "Sinop yarımadasını, denizi ve şehrin genel dokusunu en güzel açıdan kuşbakışı izleyebileceğiniz harika bir seyir noktasıdır."),
        ("Sarıkum Koruma Alanı", 42.012566390066105, 34.92922969336241, 60,
         "Göl, orman ve deniz ekosistemini bir arada bulunduran, birçok göçmen kuş türüne ev sahipliği yapan özel çevre koruma bölgesidir."),
        ("Sarıkum Plajı", 42.02238156032539, 34.90251897976251, 60,
         "Çölü andıran ince sarı kum tepeleri ve uzun sahiliyle dikkat çeken, sakinliği ve el değmemiş yapısıyla öne çıkan doğal bir plajdır."),
        ("Sorkun Şelaleleri", 41.771187800415724, 35.06906092867353, 90,
         "Gerze ve Erfelek bölgesine yakın, bakir doğası ve gürül gürül akan serin sularıyla bilinen doğa harikası şelale kümesidir.")
    ]

    # Verileri tabloya ekle
    insert_query = "INSERT INTO mekanlar (ad, enlem, boylam, sure_dk, aciklama) VALUES (?, ?, ?, ?, ?)"

    for mekan in kultur_mekanlari:
        cursor.execute(insert_query, (mekan[0], mekan[1], mekan[2], mekan[3], mekan[4]))

    for mekan in doga_mekanlari:
        cursor.execute(insert_query, (mekan[0], mekan[1], mekan[2], mekan[3], mekan[4]))

    conn.commit()
    conn.close()
    print("Veritabanı 'kuzey_kapisi.db' başarıyla oluşturuldu ve veriler eklendi.")


def view_data():
    try:
        conn = sqlite3.connect("kuzey_kapisi.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM mekanlar")
        rows = cursor.fetchall()

        print(f"{'ID':<3} | {'Mekan Adı':<28} | {'Enlem':<9} | {'Boylam':<9} | {'Süre':<4}  | {'Açıklama'}")
        print("-" * 115)

        for row in rows:
            id_, ad, enlem, boylam, sure, aciklama = row
            kisaltilmis_aciklama = (aciklama[:42] + '...') if len(aciklama) > 45 else aciklama
            print(
                f"{id_:<3} | {ad:<28} | {enlem:<9.5f} | {boylam:<9.5f} | {sure:<4} | {kisaltilmis_aciklama}")

    except sqlite3.Error as e:
        print(f"Veritabanı okunurken hata oluştu: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    #()  # Veritabanını oluştur ve verileri ekle
    print("\n--- Veritabanı İçeriği ---\n")
    view_data()  # Eklenen verileri göster