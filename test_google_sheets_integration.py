# Добавьте эту функцию в конец файла google_sheets_manager.py

def test_google_sheets_connection(service_account_file: str, spreadsheet_id: str):
    """
    Тестирует подключение к Google Sheets и возвращает результат
    
    Args:
        service_account_file: Путь к файлу сервисного аккаунта
        spreadsheet_id: ID Google таблицы
        
    Returns:
        Словарь с результатами тестирования
    """
    result = {
        'connected': False,
        'spreadsheet_title': None,
        'sheet_title': None,
        'themes_count': 0,
        'error': None
    }
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        # Подключение
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # Открываем таблицу
        spreadsheet = client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.worksheet("Лист1")
        
        # Получаем базовую информацию
        result['spreadsheet_title'] = spreadsheet.title
        result['sheet_title'] = sheet.title
        
        # Считаем темы
        themes_column = sheet.col_values(1)
        themes_count = 0
        for value in themes_column[1:]:  # Пропускаем заголовок
            if value.strip():
                themes_count += 1
            else:
                break
        
        result['themes_count'] = themes_count
        result['connected'] = True
        
    except Exception as e:
        result['error'] = str(e)
    
    return result