import pandas as pd
from test_deepseek1 import ask_deepseek
from send_TG_message import send_telegram_message_with_metadata
from utils.currency_info import get_eur_try
import logging
from functools import lru_cache
from utils.mongodb_utils import get_mongo_collection  # 🆕 MongoDB bağlantı için
from datetime import datetime
import os
from dotenv import load_dotenv

# .env dosyasını yükle (ana dizinden)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Lokasyon adı (Dalaman, Antalya, vb.)
CLIENT_BASE = os.getenv("CLIENT_BASE", "Lokasyon Bulunamadı")

# Kriter dosyasını oku
def load_analysis_criteria():
    path = os.getenv("ANALYSIS_CRITERIA_FILE")
    if path:
        base_dir = os.path.dirname(__file__)  # analyzer klasörü
        full_path = os.path.join(base_dir, "..", path) if not os.path.isabs(path) else path
        if os.path.exists(full_path):
            with open(full_path, encoding="utf-8") as f:
                return f.read()
    return "❌ Analiz kriterleri bulunamadı."

ANALYSIS_CRITERIA = load_analysis_criteria()

class MongoDBLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.collection = get_mongo_collection("ride_analyzer_logs")

    def emit(self, record):
        log_entry = {
            "level": record.levelname,
            "message": self.format(record),
            "time": datetime.now()
        }
        try:
            self.collection.insert_one(log_entry)
        except Exception as e:
            print(f"⚠️ [MongoLogger] DB yazım hatası: {e}")

# Asıl logger ayarı:
mongo_handler = MongoDBLogHandler()
mongo_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[mongo_handler, logging.StreamHandler()]  # 🔥 Dosya yok, sadece Mongo + Terminal
)


class RideAnalyzer:
    def __init__(self, rides_df, calendar_df, match_df):
        self.rides_df = rides_df
        self.calendar_df = calendar_df
        self.match_df = match_df
        self._prepare_data()

    def _prepare_data(self):
        logging.info("Preparing data...")

        if self.rides_df.empty:
            logging.warning("Rides DataFrame is empty.")
        else:
            if 'ride_datetime' in self.rides_df.columns:
                self.rides_df['ride_datetime'] = pd.to_datetime(self.rides_df['ride_datetime'], errors='coerce')
                logging.info("ride_datetime converted to datetime")

        if 'Ride_Time' in self.match_df.columns:
            self.match_df['Ride_Time'] = pd.to_datetime(self.match_df['Ride_Time'], errors='coerce')
            logging.info("Ride_Time converted to datetime")
        if 'Ride_Arrival' in self.match_df.columns:
            self.match_df['Ride_Arrival'] = pd.to_datetime(self.match_df['Ride_Arrival'], errors='coerce')
            logging.info("Ride_Arrival converted to datetime")
        if 'Match_Time' in self.match_df.columns:
            self.match_df['Match_Time'] = pd.to_datetime(self.match_df['Match_Time'], errors='coerce')
            logging.info("Match_Time converted to datetime")
        if 'Match_Arrival' in self.match_df.columns:
            self.match_df['Match_Arrival'] = pd.to_datetime(self.match_df['Match_Arrival'], errors='coerce')
            logging.info("Match_Arrival converted to datetime")
        if 'last_updated' in self.match_df.columns:
            self.match_df['last_updated'] = pd.to_datetime(self.match_df['last_updated'], errors='coerce')
            logging.info("last_updated converted to datetime")

        if self.calendar_df.empty:
            logging.warning("Calendar DataFrame is empty. Skipping calendar processing.")
            return

        logging.warning(f"Calendar DataFrame columns: {self.calendar_df.columns.tolist()}")

        if 'ID' in self.calendar_df.columns:
            self.calendar_df['Task_ID'] = self.calendar_df['ID'].astype(str)
            logging.info("Task_ID column created from ID")
        else:
            logging.warning("Calendar has no 'ID' column. Skipping Task_ID creation.")

    @lru_cache(maxsize=100)
    def _get_match_direction_description(self, direction):
        """Cache'lenmiş eşleşme yönü açıklaması"""
        descriptions = {
            'Away Return': "🚗 Away Return (Can be outsourced to another provider)",
            'Home Return': "🏠 Home Return (Excellent match - car returns to hub)",
            'Unknown': "❓ Unknown Direction (Potential match needs verification)"
        }
        return descriptions.get(direction, f"Direction: {direction}")

    @lru_cache(maxsize=100)
    def _get_match_source_description(self, source):
        """Cache'lenmiş eşleşme kaynağı açıklaması"""
        descriptions = {
            'Rides': "📝 Matched with another ride in our system",
            'Calendar': "📅 Matched with a booked transfer in our calendar"
        }
        return descriptions.get(source, f"Source: {source}")

    def filter_matches_for_ride(self, ride_id):
        """Get matches for a specific ride"""
        return self.match_df[self.match_df['Ride_ID'] == ride_id].to_dict('records')

    def filter_matches_for_calendar(self, task_id):
        """Get matches for a specific calendar entry"""
        return self.match_df[self.match_df['Matched_ID'] == task_id].to_dict('records')

    def create_ride_prompt(self, ride, matches):
        """Generate prompt with all relevant data for a ride"""
        source_label = ride.get("Source", "unknown").lower()
        emoji = "🟦" if source_label == "elife" else "🟪" if source_label == "wt" else "❓"

        prompt = f"""
        🔧 SENARYO:
        Sen, {CLIENT_BASE} merkezli bir VIP transfer şirketinin operasyon yöneticisisin. Pickup lokasyonumuz {CLIENT_BASE}, araçlarımız {CLIENT_BASE} lokasyonundan çıkış yapmaktadır.
        Aracın boş dönme ihtimalini minimize etmek ana hedefimiz. Artık otomatik eşleşme sistemimiz var ve size detaylı eşleşme bilgileri sunuyoruz.

        🚗 YENİ TRANSFER DETAYLARI:
        - Kaynak: {emoji} {source_label.capitalize()}
        - Araç: {ride['Vehicle']}
        - Zaman: {ride['Time']}
        - Rota: {ride['Pickup']} → {ride['Dropoff']}
        - Mesafe: {ride['Distance']} | Süre: {ride['Duration']}
        - Ücret: {ride['Price']} TL
        - Koordinatlar: Pickup ({ride['Pickup_lat']}, {ride['Pickup_lon']}) → Dropoff ({ride['Dropoff_lat']}, {ride['Dropoff_lon']})

        🔍 EŞLEŞME DETAYLARI:
        {self._format_matches(matches) if matches else "⚠️ Hiç eşleşme bulunamadı - araç boş dönecek"}

        🎯 ANALİZ KRİTERLERİ:
        {ANALYSIS_CRITERIA}
        🎯 CEVAP FORMATI:
        **{emoji} {source_label.capitalize()} VIP Transfer Analizi** ✈️🚗
        - 📍 Rota: {ride['Pickup']} → {ride['Dropoff']} ({ride['Distance']} ~ {ride['Duration']})
        - ⏰ Zaman: {ride['Time']}
        - 💰 Ücret: {ride['Price']} TL
        - 🚗 Araç: {ride['Vehicle']} ({'Boş dönüş 🚨' if not matches else 'Eşleşme var ✅'})
        - 🔍 Eşleşme Durumu: {' | '.join([m['Matched_Pickup'] + '→' + m['Matched_Dropoff'] for m in matches]) if matches else 'Yok'}

        🧮 Maliyetler:
        - ⛽ Yakıt: [Calculation]
        - 👨‍✈️ Sürücü: [Driver Cost]
        - 🛣️ Tünel/Otopark: [If applicable]
        - Toplam Gider: [Total Cost]

        📈 Kar/Zarar: [Profit/Loss] (Kârlılık oranı: [X%])
        🌟 Kârlılık Puanı: [X/5] [Emoji] (*"[Kısa yorum]"*)
        📊 Analiz Güveni: [X%] ([Brief confidence explanation])

        💡 Öneriler: [1-3 suggestions]
        💡 Tüm yanıtı Türkçe yaz. Maksimum 1250 karakteri geçmesin.
        """

        if source_label == "wt":
            eur = get_eur_try()
            if eur:
                prompt += f"\n💱 Güncel EUR/TRY kuru: {eur}"
        return prompt

    def _format_matches(self, matches):
        """Format matches for display in prompt"""
        formatted = []
        for i, match in enumerate(matches, 1):
            direction_desc = self._get_match_direction_description(match['Match_Direction'])
            source_desc = self._get_match_source_description(match['Match_Source'])

            pair_info = ""
            if match.get('CalendarMatchPair'):
                pair_info = f"\n   - ⚠️ Bu eşleşme başka bir rezervasyonla çift kayıtlı: '{match['CalendarMatchPair']}' - dikkatle değerlendirin!"

            match_info = [
                f"{i}. {match['Match_Time']} | {match['Matched_Pickup']} → {match['Matched_Dropoff']}",
                f"   - {direction_desc} | {source_desc}",
                f"   - Mesafe: {match.get('Real_Distance_km', 'Bilinmiyor')} km | Süre: {match.get('Real_Duration_min', 'Bilinmiyor')} dk",
                f"   - Zaman Farkı: {match.get('Time_Difference_min', 'Bilinmiyor')} dk",
                f"   - Çift Kullanım: {'✅ Evet' if match.get('DoubleUtilized', False) else '❌ Hayır'}",
                pair_info
            ]
            formatted.append("\n".join(filter(None, match_info)))
        return "\n\n".join(formatted)

    def process_ride(self, ride):
        """Full processing pipeline for a ride"""
        try:
            logging.info(f"Processing ride ID: {ride['ID']}")
            matches = self.filter_matches_for_ride(ride['ID'])

            prompt = self.create_ride_prompt(ride, matches)
            response = ask_deepseek(prompt)

            analysis = response.get('choices', [{}])[0].get('message', {}).get('content')
            if not analysis:
                raise ValueError("Empty analysis response from Deepseek")

            send_telegram_message_with_metadata(analysis)
            return analysis

        except Exception as e:
            logging.error(f"Error processing ride {ride.get('ID', 'Unknown')}: {str(e)}")
            return None

    def create_calendar_prompt(self, calendar_entry, matches):
        """Generate prompt for calendar entries"""
        prompt = f"""
        📅 YENİ TAKVİM KAYDI ANALİZİ:
        Yeni bir takvim transferi eklendi. Bu transfer için uygun eşleşmeleri kontrol ediyoruz.

        🚕 TAKVİM TRANSFER DETAYLARI:
        - Araç: {calendar_entry.get('Vehicle', 'Belirtilmemiş')}
        - Zaman: {calendar_entry['Transfer_Datetime']}
        - Rota: {calendar_entry['Pickup']} → {calendar_entry['Dropoff']}
        - Durum: {calendar_entry.get('Status', 'Belirtilmemiş')}
        - Mesafe: {calendar_entry.get('Distance', 'Bilinmiyor')}
        - Süre: {calendar_entry.get('Duration', 'Bilinmiyor')}

        🔍 EŞLEŞME DETAYLARI:
        {self._format_calendar_matches(matches) if matches else "⚠️ Hiç eşleşme bulunamadı - araç boş gidecek"}

        🎯 ANALİZ KRİTERLERİ:
        1. Eşleşme kalitesini değerlendir (Home Return > Away Return > Unknown)
        2. Eşleşen transferin kârlılığını analiz et
        3. Çift kullanım (DoubleUtilized) durumunu kontrol et
        4. Yakıt maliyetlerini hesapla (100km = 7lt, 1lt = 45TL)
        5. Hava durumu etkisi olup olmadığını belirt
        6. Eşleşme yoksa alternatif önerilerde bulun
        7. Çift Kayıt Uyarısı: Eğer CalendarMatchPair doluysa, bu eşleşmenin başka bir rezervasyonla çakıştığını belirt
        8. Takvim Transfer detaylarını mesajın başına ekle - yeni takvim kaydı eklendiğini belirt -emoji kullan
        9. Eşleşme detaylarını da Takvim bilgilerinden sonra özetleyerek ekle 

        💡 Tüm yanıtı Türkçe yaz. Maksimum 750 karakteri geçmesin.
        """
        return prompt

    def _format_calendar_matches(self, matches):
        """Format calendar matches with additional details"""
        formatted = []
        for i, match in enumerate(matches, 1):
            direction_desc = self._get_match_direction_description(match['Match_Direction'])
            source_desc = self._get_match_source_description(match['Match_Source'])

            pair_info = ""
            if match.get('CalendarMatchPair'):
                pair_info = f"\n   - ⚠️ Bu eşleşme başka bir rezervasyonla çift kayıtlı: '{match['CalendarMatchPair']}' - dikkatle değerlendirin!"

            match_info = [
                f"{i}. {match['Ride_Time']} | {match['Pickup']} → {match['Dropoff']}",
                f"   - {direction_desc} | {source_desc}",
                f"   - Mesafe: {match.get('Real_Distance_km', 'Bilinmiyor')} km",
                f"   - Süre: {match.get('Real_Duration_min', 'Bilinmiyor')} dk",
                f"   - Zaman Farkı: {match.get('Time_Difference_min', 'Bilinmiyor')} dk",
                f"   - Çift Kullanım: {'✅ Evet' if match.get('DoubleUtilized', False) else '❌ Hayır'}",
                pair_info
            ]
            formatted.append("\n".join(filter(None, match_info)))
        return "\n\n".join(formatted)

    def process_calendar_entry(self, calendar_entry):
        """Full processing pipeline for a calendar entry"""
        try:
            task_id = calendar_entry.get('ID', calendar_entry.get('ID', 'Unknown'))
            logging.info(f"Processing calendar entry ID: {task_id}")

            matches = self.filter_matches_for_calendar(task_id)
            prompt = self.create_calendar_prompt(calendar_entry, matches)
            response = ask_deepseek(prompt)

            analysis = response.get('choices', [{}])[0].get('message', {}).get('content')
            if not analysis:
                raise ValueError("Empty analysis response from Deepseek")

            send_telegram_message_with_metadata(analysis)
            return analysis

        except Exception as e:
            logging.error(f"Error processing calendar entry {task_id}: {str(e)}")
            return None

    def run_analysis_cycle(self, return_metadata=False):
        """Run analysis for all unprocessed rides and calendar entries"""
        ride_results = []
        calendar_results = []

        try:
            if not self.rides_df.empty:
                logging.info(f"Processing {len(self.rides_df)} rides")
                for _, ride in self.rides_df.iterrows():
                    result = self.process_ride(ride)
                    if result:
                        ride_results.append({
                            "ID": ride["ID"],
                            "analysis": result,
                            "telegram_sent": True
                        })

            if not self.calendar_df.empty:
                logging.info(f"Processing {len(self.calendar_df)} calendar entries")
                for _, calendar_entry in self.calendar_df.iterrows():
                    try:
                        matches = self.filter_matches_for_calendar(calendar_entry.get('ID', 'Unknown'))
                        prompt = self.create_calendar_prompt(calendar_entry, matches)
                        response = ask_deepseek(prompt)

                        analysis = response.get('choices', [{}])[0].get('message', {}).get('content')
                        if analysis:
                            send_telegram_message_with_metadata(analysis)
                            calendar_results.append({
                                "ID": calendar_entry.get("ID", calendar_entry.get("ID")),
                                "analysis": analysis,
                                "telegram_sent": True
                            })

                    except Exception as e:
                        logging.error(
                            f"Error processing calendar entry {calendar_entry.get('ID', 'Unknown')}: {str(e)}")

            return (ride_results, calendar_results) if return_metadata else len(ride_results) + len(calendar_results)

        finally:
            # Cleanup large data structures
            self.rides_df = None
            self.calendar_df = None
            self.match_df = None