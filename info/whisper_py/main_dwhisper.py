import os
from whisper_timestamped import load_model, transcribe

model = load_model("large-v2")
print(f"📦 Загружена модель Whisper")

AUDIO_DIR = "/home/avaganov/test_ssh/pro_club_season_2/info/whisper_py"
OUTPUT_DIR = "/home/avaganov/test_ssh/pro_club_season_2/info/whisper_py"

for fname in os.listdir(AUDIO_DIR):
    if fname.endswith(".wav") or fname.endswith(".mp3"):
        path = os.path.join(AUDIO_DIR, fname)
        print(f"🔊 Распознаю: {fname}...")
        result = transcribe(model, path, language="ru")

        out_txt = os.path.join(OUTPUT_DIR, fname + ".txt")
        out_time = os.path.join(OUTPUT_DIR, fname + "_words.txt")

        #Сохраняем только текст
        with open(out_txt, "w", encoding="utf-8") as f:
            f.write(result["text"])

        #Сохраняем слова с таймингом
        with open(out_time, "w", encoding="utf-8") as f:
            for segment in result["segments"]:
                for word in segment["words"]:
                    f.write(f"{word['text']} — {word['start']:.2f}s → {word['end']:.2f}s\n")

        print(f"✅ Сохранено: {out_txt} и {out_time}")