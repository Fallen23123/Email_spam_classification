import pandas as pd
import time
from deep_translator import GoogleTranslator

def translate_text(text: str) -> str:
    """
    Функція для машинного перекладу текстових даних з англійської на українську мову.
    
    Використовує API Google Translate. Впроваджено обробку винятків для забезпечення 
    безперервності процесу у випадку мережевих збоїв або помилок API.
    """
    try:
        translator = GoogleTranslator(source='en', target='uk')
        translated = translator.translate(text)
        return translated
    except Exception as e:
        print(f"Помилка перекладу для тексту: '{text[:30]}...'. Деталі: {e}")
        return text

def create_ukrainian_dataset(input_filepath: str, output_filepath: str, limit: int = None):
    """
    Основний конвеєр (pipeline) для завантаження, перекладу та збереження набору даних.
    
    Параметри:
    input_filepath (str): Шлях до вихідного англомовного датасету.
    output_filepath (str): Шлях для збереження перекладеного україномовного датасету.
    limit (int): Обмеження кількості рядків для перекладу (корисно для тестування).
    """
    print(f"Завантаження даних з {input_filepath}...")
    
    try:
        df = pd.read_csv(input_filepath, encoding='latin-1')
        
        if 'v1' in df.columns and 'v2' in df.columns:
            df = df[['v1', 'v2']]
            df.columns = ['label', 'text']
            
    except FileNotFoundError:
        print(f"Критична помилка: Файл {input_filepath} не знайдено.")
        return

    if limit:
        df = df.head(limit)
        print(f"Увага: Встановлено ліміт. Буде оброблено лише {limit} записів.")

    print("Розпочинається процес машинного перекладу. Це може зайняти певний час...")
    
    translated_texts = []
    total_rows = len(df)
    
    for index, row in df.iterrows():
        original_text = row['text']
        translated = translate_text(original_text)
        translated_texts.append(translated)
        
        if (index + 1) % 50 == 0:
            print(f"Оброблено {index + 1} з {total_rows} записів...")
            
        time.sleep(0.1)

    df['text'] = translated_texts
    
    print(f"Переклад завершено. Збереження результатів у {output_filepath}...")
    df.to_csv(output_filepath, index=False, encoding='utf-8-sig')
    print("Процес успішно завершено!")

if __name__ == "__main__":
    INPUT_FILE = 'data/spam.csv' 
    
    OUTPUT_FILE = 'data/ukrainian_spam_dataset.csv'
    
    ROWS_LIMIT = None 
    
    create_ukrainian_dataset(INPUT_FILE, OUTPUT_FILE, limit=ROWS_LIMIT)