import matplotlib
# Используем бэкенд без GUI до импорта pyplot
matplotlib.use('Agg')  # Важно: должно быть ДО импорта plt
import matplotlib.pyplot as plt
import io
from datetime import datetime

def create_expenses_chart(expenses_by_category, user_id):
    """Создает круговую диаграмму расходов по категориям"""
    try:
        if not expenses_by_category:
            print("❌ Нет данных для диаграммы")
            return None
        
        print(f"📊 Создаем диаграмму для {len(expenses_by_category)} категорий")
        
        # Подготовка данных
        categories = list(expenses_by_category.keys())
        amounts = list(expenses_by_category.values())
        
        # Создаем диаграмму
        plt.figure(figsize=(10, 8))
        
        # Цвета для категорий
        colors = plt.cm.Set3(range(len(categories)))
        
        # Круговая диаграмма
        wedges, texts, autotexts = plt.pie(
            amounts, 
            labels=categories, 
            autopct='%1.1f%%',
            colors=colors,
            startangle=90
        )
        
        # Улучшаем отображение текста
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        plt.title('Расходы по категориям', fontsize=16, fontweight='bold')
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        
        # Очищаем график
        plt.close()
        
        print("✅ Диаграмма создана успешно")
        return buffer
        
    except Exception as e:
        print(f"❌ Ошибка в create_expenses_chart: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_monthly_stats_chart(monthly_data, user_id):
    """Создает график доходов/расходов по месяцам"""
    try:
        if not monthly_data:
            print("❌ Нет данных для графика истории")
            return None
        
        print(f"📈 Создаем график истории для {len(monthly_data)} месяцев")
        
        # Подготовка данных
        months = list(monthly_data.keys())[::-1]  # Переворачиваем чтобы шло от старых к новым
        incomes = [monthly_data[month]['income'] for month in months]
        expenses = [monthly_data[month]['expenses'] for month in months]
        
        # Создаем график
        plt.figure(figsize=(12, 6))
        
        x = range(len(months))
        bar_width = 0.35
        
        plt.bar([i - bar_width/2 for i in x], incomes, bar_width, label='Доходы', color='green', alpha=0.7)
        plt.bar([i + bar_width/2 for i in x], expenses, bar_width, label='Расходы', color='red', alpha=0.7)
        
        plt.xlabel('Месяцы')
        plt.ylabel('Сумма (руб)')
        plt.title('Динамика доходов и расходов по месяцам', fontsize=14, fontweight='bold')
        plt.xticks(x, months, rotation=45)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Сохраняем в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        
        # Очищаем график
        plt.close()
        
        print("✅ График истории создан успешно")
        return buffer
        
    except Exception as e:
        print(f"❌ Ошибка в create_monthly_stats_chart: {e}")
        import traceback
        traceback.print_exc()
        return None