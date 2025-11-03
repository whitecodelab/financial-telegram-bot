# sqlite_database.py
import sqlite3
import os
from datetime import datetime
from categories import detect_category as detect_standard_category

class Database:
    def __init__(self, db_name='finance_bot.db'):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        """Создает соединение с базой данных"""
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Чтобы получать данные как словарь
        return conn
    
    def init_database(self):
        """Инициализирует базу данных и создает таблицы"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица операций
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # НОВАЯ ТАБЛИЦА для персональных категорий
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_name TEXT NOT NULL,
            keywords TEXT NOT NULL,
            UNIQUE(user_id, category_name)
        )
        ''')
        
        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON operations (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON operations (created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_categories ON user_categories (user_id)')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
    
    def add_operation(self, user_id, amount, description, operation_type='expense'):
        """Добавляет операцию в базу данных"""
        # Используем новую функцию определения категории с учетом персональных категорий
        category = self.detect_category(user_id, description) if operation_type == 'expense' else 'доход'
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO operations (user_id, amount, description, type, category)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, description, operation_type, category))
        
        conn.commit()
        conn.close()
    
    def get_operations(self, user_id, limit=None):
        """Возвращает все операции пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
        SELECT * FROM operations 
        WHERE user_id = ? 
        ORDER BY created_at DESC
        '''
        
        if limit:
            query += ' LIMIT ?'
            cursor.execute(query, (user_id, limit))
        else:
            cursor.execute(query, (user_id,))
        
        operations = []
        for row in cursor.fetchall():
            operations.append(dict(row))
        
        conn.close()
        return operations
    
    def get_monthly_operations(self, user_id, year=None, month=None):
        """Возвращает операции за конкретный месяц"""
        if year is None or month is None:
            now = datetime.now()
            year, month = now.year, now.month
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM operations 
        WHERE user_id = ? 
        AND strftime('%Y', created_at) = ? 
        AND strftime('%m', created_at) = ?
        ORDER BY created_at DESC
        ''', (user_id, str(year), str(month).zfill(2)))
        
        operations = []
        for row in cursor.fetchall():
            operations.append(dict(row))
        
        conn.close()
        return operations
    
    def clear_operations(self, user_id):
        """Удаляет все операции пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        DELETE FROM operations WHERE user_id = ?
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_user_statistics(self, user_id):
        """Возвращает базовую статистику пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Общее количество операций
        cursor.execute('SELECT COUNT(*) FROM operations WHERE user_id = ?', (user_id,))
        total_operations = cursor.fetchone()[0]
        
        # Сумма доходов
        cursor.execute('SELECT SUM(amount) FROM operations WHERE user_id = ? AND type = ?', 
                      (user_id, 'income'))
        total_income = cursor.fetchone()[0] or 0
        
        # Сумма расходов
        cursor.execute('SELECT SUM(amount) FROM operations WHERE user_id = ? AND type = ?', 
                      (user_id, 'expense'))
        total_expenses = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_operations': total_operations,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'balance': total_income - total_expenses
        }

    # НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С ПЕРСОНАЛЬНЫМИ КАТЕГОРИЯМИ

    def add_user_category(self, user_id, category_name, keywords):
        """Добавляет персональную категорию для пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO user_categories (user_id, category_name, keywords)
            VALUES (?, ?, ?)
            ''', (user_id, category_name, keywords))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Категория уже существует
            return False
        finally:
            conn.close()

    def get_user_categories(self, user_id):
        """Возвращает все категории пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT category_name, keywords FROM user_categories 
        WHERE user_id = ?
        ''', (user_id,))
        
        categories = {}
        for row in cursor.fetchall():
            # Разделяем ключевые слова по запятой и убираем пробелы
            keywords_list = [kw.strip() for kw in row['keywords'].split(',')]
            categories[row['category_name']] = keywords_list
        
        conn.close()
        return categories

    def delete_user_category(self, user_id, category_name):
        """Удаляет категорию пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        DELETE FROM user_categories 
        WHERE user_id = ? AND category_name = ?
        ''', (user_id, category_name))
        
        conn.commit()
        conn.close()
        return True

    def detect_category(self, user_id, description):
        """Определяет категорию с учетом персональных категорий пользователя"""
        description_lower = description.lower()
        
        # Сначала проверяем персональные категории пользователя
        user_categories = self.get_user_categories(user_id)
        for category, keywords in user_categories.items():
            for keyword in keywords:
                if keyword.strip().lower() in description_lower:
                    return category
        
        # Если не нашли в персональных, проверяем стандартные категории
        return detect_standard_category(description)

    def get_all_categories(self, user_id):
        """Возвращает все категории пользователя (персональные + стандартные)"""
        # Персональные категории
        personal_categories = self.get_user_categories(user_id)
        
        # Стандартные категории
        from categories import CATEGORIES
        standard_categories = CATEGORIES
        
        # Объединяем (персональные имеют приоритет в отображении)
        all_categories = {**personal_categories, **standard_categories}
        return all_categories

    # === ДОБАВЛЕНО: МЕТОДЫ ДЛЯ РЕДАКТИРОВАНИЯ ОПЕРАЦИЙ ===
    
    def get_operation_by_id(self, operation_id):
        """Возвращает операцию по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM operations WHERE id = ?', (operation_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        else:
            return None

    def update_operation(self, operation_id, amount=None, description=None, operation_type=None, category=None):
        """Обновляет операцию"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if amount is not None:
            updates.append("amount = ?")
            params.append(amount)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if operation_type is not None:
            updates.append("type = ?")
            params.append(operation_type)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        
        if not updates:
            conn.close()
            return False
        
        params.append(operation_id)
        query = f"UPDATE operations SET {', '.join(updates)} WHERE id = ?"
        
        try:
            cursor.execute(query, params)
            conn.commit()
            success = True
        except Exception as e:
            print(f"Ошибка при обновлении операции: {e}")
            success = False
        finally:
            conn.close()
        
        return success

    def delete_operation(self, operation_id):
        """Удаляет операцию"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM operations WHERE id = ?', (operation_id,))
            conn.commit()
            success = True
        except Exception as e:
            print(f"Ошибка при удалении операции: {e}")
            success = False
        finally:
            conn.close()
        
        return success

# Создаем глобальный экземпляр базы данных
db = Database()