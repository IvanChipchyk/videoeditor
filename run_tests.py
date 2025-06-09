#!/usr/bin/env python3
"""
run_tests.py - Запуск всех тестов VideoCreator Pro
"""

import sys
import subprocess
from pathlib import Path

def run_test(test_name, test_file):
    """Запускает отдельный тест"""
    print(f"\n{'='*60}")
    print(f"🧪 ЗАПУСК ТЕСТА: {test_name}")
    print(f"📄 Файл: {test_file}")
    print(f"{'='*60}")
    
    try:
        if Path(test_file).exists():
            result = subprocess.run([sys.executable, test_file], 
                                  capture_output=False, 
                                  text=True, 
                                  cwd=Path(__file__).parent)
            
            if result.returncode == 0:
                print(f"✅ {test_name} - ПРОЙДЕН")
                return True
            else:
                print(f"❌ {test_name} - ПРОВАЛЕН (код: {result.returncode})")
                return False
        else:
            print(f"⚠️ Файл теста не найден: {test_file}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка запуска теста {test_name}: {e}")
        return False

def main():
    print("🚀 VideoCreator Pro - Запуск всех тестов")
    print("=" * 60)
    
    tests = [
        ("Базовые исправления", "test_fixes.py"),
        ("Исправления аудио", "test_audio_fixes.py"), 
        ("Google Sheets интеграция", "test_google_sheets_integration.py")
    ]
    
    results = []
    
    for test_name, test_file in tests:
        success = run_test(test_name, test_file)
        results.append((test_name, success))
    
    # Итоговый отчет
    print(f"\n{'='*60}")
    print("📊 ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ")
    print(f"{'='*60}")
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ ПРОЙДЕН" if success else "❌ ПРОВАЛЕН"
        print(f"{status:<15} {test_name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Статистика:")
    print(f"   ✅ Пройдено: {passed}")
    print(f"   ❌ Провалено: {failed}")
    print(f"   📊 Всего: {passed + failed}")
    
    if failed == 0:
        print(f"\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Можно запускать основное приложение:")
        print(f"   python3 videocreator_main.py")
    else:
        print(f"\n⚠️ Есть проваленные тесты. Проверьте ошибки выше.")
    
    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()