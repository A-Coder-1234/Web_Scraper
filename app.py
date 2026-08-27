import tkinter as tk
import subprocess
import sys

window = tk.Tk()
window.title("Food Scraper")
window.geometry("400x300")
l1 = tk.Label(window, text="Enter the product name:")
l1.grid(row=0, column=0, padx=10, pady=10)
t1 = tk.Entry(window, width=30)
t1.grid(row=0, column=1, padx=10, pady=10)

def search():
    product_name = t1.get()
    try:
    # This line pauses execution until 'script_b.py' finishes
        result = subprocess.run(
            [sys.executable, "Pak'nSave scraper.py", product_name],
            capture_output=True,
            text=True,
            check=True
        )

        scraped_data = result.stdout

        print("Main Script: Script B finished successfully!")
        print(scraped_data)

    except subprocess.CalledProcessError as e:
        print(f"Error occurred while running Pak'nSave scraper.py: {e}")

        if e.stderr:
            print(f"\n--- SCRAPER ERROR LOG --- \n{e.stderr}")

b1 = tk.Button(window, text="Search", command=search)
b1.grid(row=1, column=0, columnspan=2, pady=10)
window.mainloop()