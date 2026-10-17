# Система керування завданнями (Варіант 14)

Навчальний Python-проєкт для Лабораторної роботи №6 «Автоматизоване тестування Python-програм».

## Встановлення

```bash
python -m pip install -e ".[dev]"
```

## Запуск тестів та перевірка покриття

Запуск усього test suite з аналізом statement та branch coverage і генерацією HTML-звіту:

```bash
pytest -v --cov=task_manager --cov-branch --cov-report=term-missing --cov-report=html
```

Запуск лише модульних (unit) тестів:

```bash
pytest -m "not integration"
```

Запуск лише інтеграційних тестів:

```bash
pytest -m integration
```
