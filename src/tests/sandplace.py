from rich.console import Console
from rich import print

console = Console(force_terminal=True, color_system="truecolor")
print("[bold red]Цветной текст[/bold red]")
console.print(":snake: Проверка эмодзи")
console.print(f"Поддержка цветов: {console.color_system}")