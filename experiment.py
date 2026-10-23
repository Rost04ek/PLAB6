import csv
import time
import tracemalloc
from pathlib import Path

def generate_csv(path: Path, num_rows: int):
    """Генерує великий CSV файл для тестування."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["task_id", "title", "description", "priority", "status"])
        for i in range(1, num_rows + 1):
            writer.writerow([i, f"Task {i}", f"Description {i}", "High", "To Do"])

def eager_import(path: Path):
    """Читає весь файл у пам'ять (Жадібний підхід)."""
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))

def streaming_import(path: Path):
    """Читає файл порядково (Потоковий підхід)."""
    with path.open("r", encoding="utf-8", newline="") as file:
        yield from csv.DictReader(file)

def main():
    sizes = [10_000, 100_000, 500_000]
    
    print(f"{'Records':<10} | {'Eager time':<15} | {'Streaming time':<15} | {'Eager peak RAM':<20} | {'Streaming peak RAM':<20}")
    print("-" * 90)
    
    for size in sizes:
        file_path = Path(f"data_test_{size}.csv")
        generate_csv(file_path, size)
        
        # --- Measure Eager ---
        tracemalloc.start()
        start_time = time.perf_counter()
        
        data = eager_import(file_path)
        
        eager_time = time.perf_counter() - start_time
        _, eager_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        del data # Очищаємо пам'ять
        
        # --- Measure Streaming ---
        tracemalloc.start()
        start_time = time.perf_counter()
        
        # Проходимо по генератору, щоб зімітувати обробку
        for row in streaming_import(file_path):
            pass 
            
        stream_time = time.perf_counter() - start_time
        _, stream_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Конвертуємо байти в мегабайти (MB)
        eager_mb = eager_peak / (1024 * 1024)
        stream_mb = stream_peak / (1024 * 1024)
        
        print(f"{size:<10} | {eager_time:<15.4f} | {stream_time:<15.4f} | {eager_mb:<17.2f} MB | {stream_mb:<17.4f} MB")
        
        # Видаляємо тестовий файл
        file_path.unlink()

if __name__ == "__main__":
    main()