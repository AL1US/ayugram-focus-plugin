"""
AyuGram Focus Plugin Entrypoint.
"""

import ast
from pathlib import Path


def get_metadata():
    plugin_file = Path(__file__).parent / "ayugram_focus.py"
    with open(plugin_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    meta = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("__"):
                    meta[target.id] = ast.literal_eval(node.value)
    return meta


def main():
    meta = get_metadata()
    print("=" * 50)
    print(f"🎯 {meta.get('__name__')} v{meta.get('__version__')}")
    print(f"ID: {meta.get('__id__')}")
    print(f"Author: {meta.get('__author__')}")
    print(f"Description: {meta.get('__description__')}")
    print("=" * 50)
    print("\n📦 Инструкция по установке на Android:")
    print("1. Отправьте файл 'ayugram_focus.plugin' себе в Telegram (например, в 'Избранное').")
    print("2. Нажмите на файл прямо в чате Telegram на телефоне.")
    print("3. Нажмите кнопку 'Установить плагин' (Install Plugin).")
    print("4. Перейдите в Настройки -> Плагины, чтобы настроить параметры фокуса.\n")


if __name__ == "__main__":
    main()
