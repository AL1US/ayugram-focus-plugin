# -*- coding: utf-8 -*-
"""
AyuGram Focus Plugin (Spotlight Focus)
Phase 1: Minimalist Search-first UI & Chat List Suppression.
"""

from typing import Any, List

from base_plugin import BasePlugin, MethodHook
from hook_utils import find_class, get_private_field
from ui.settings import Header, Switch, Text, Divider

# --- Plugin Metadata ---
__id__ = "ayugram_focus"
__name__ = "AyuGram Focus (Spotlight)"
__description__ = (
    "Превращает Telegram в инструмент с фокусом на задачах (Spotlight): "
    "скрывает отвлекающую ленту чатов и оставляет только чистый поиск."
)
__author__ = "@AL1US"
__version__ = "0.1.0"
__icon__ = "exteraPlugins/1"
__app_version__ = ">=10.0.0"
__sdk_version__ = ">=1.4.0"

OVERLAY_TAG = "ayugram_focus_overlay_view"


class DialogsAdapterItemCountHook(MethodHook):
    """
    Перехватывает подсчёт элементов в главном списке чатов.
    Если включен режим фокуса, возвращает 0 — лента чатов, каналов и групп становится пустой.
    При этом адаптер поиска (DialogsSearchAdapter) не затрагивается и работает штатно.
    """

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        super().__init__()
        self.plugin = plugin

    def before_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            param.setResult(0)


class DialogsActivityCreateViewHook(MethodHook):
    """
    Хук создания интерфейса главного экрана (DialogsActivity).
    Скрывает вкладки папок и внедряет карточку-заглушку с поиском.
    """

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        super().__init__()
        self.plugin = plugin

    def after_hooked_method(self, param):
        if not self.plugin.is_focus_enabled():
            return

        dialogs_activity = param.thisObject
        root_view = param.getResult()
        if not root_view:
            return

        # 1. Скрываем вкладки папок, если включена соответствующая настройка
        if self.plugin.get_setting("hide_folders", True):
            self.plugin.hide_folder_tabs(dialogs_activity)

        # 2. Внедряем минималистичный UI (карточку по центру)
        self.plugin.inject_focus_ui(dialogs_activity, root_view)


class DialogsActivityResumeHook(MethodHook):
    """
    Хук возобновления работы экрана (onResume).
    При необходимости автоматически открывает поиск при входе в приложение.
    """

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        super().__init__()
        self.plugin = plugin

    def after_hooked_method(self, param):
        if not self.plugin.is_focus_enabled():
            return

        dialogs_activity = param.thisObject
        if self.plugin.get_setting("auto_open_search", False):
            self.plugin.open_search(dialogs_activity)


class AyuGramFocusPlugin(BasePlugin):
    """
    Основной класс плагина фокуса.
    """

    def on_plugin_load(self):
        self.logger.info("AyuGram Focus Plugin: инициализация...")
        self._hook_dialogs_adapter()
        self._hook_dialogs_activity()
        self.logger.info("AyuGram Focus Plugin: успешно загружен!")

    def on_plugin_unload(self):
        self.logger.info("AyuGram Focus Plugin: выгружен.")

    def is_focus_enabled(self) -> bool:
        return bool(self.get_setting("focus_enabled", True))

    def _hook_dialogs_adapter(self):
        """Хукаем DialogsAdapter.getItemCount(), чтобы скрыть стандартную ленту."""
        DialogsAdapterClass = find_class("org.telegram.ui.Adapters.DialogsAdapter")
        if not DialogsAdapterClass:
            self.logger.error("Не найден класс DialogsAdapter")
            return

        try:
            get_item_count_method = DialogsAdapterClass.getDeclaredMethod("getItemCount")
            self.hook_method(get_item_count_method, DialogsAdapterItemCountHook(self))
            self.logger.info("Хук DialogsAdapter.getItemCount() успешно установлен")
        except Exception as e:
            self.logger.error(f"Ошибка при хуке DialogsAdapter.getItemCount(): {e}")

    def _hook_dialogs_activity(self):
        """Хукаем DialogsActivity для управления UI и строкой поиска."""
        DialogsActivityClass = find_class("org.telegram.ui.DialogsActivity")
        if not DialogsActivityClass:
            self.logger.error("Не найден класс DialogsActivity")
            return

        # Хук createView(Context)
        ContextClass = find_class("android.content.Context")
        if ContextClass:
            try:
                create_view_method = DialogsActivityClass.getDeclaredMethod(
                    "createView", ContextClass
                )
                self.hook_method(create_view_method, DialogsActivityCreateViewHook(self))
                self.logger.info("Хук DialogsActivity.createView() успешно установлен")
            except Exception as e:
                self.logger.error(f"Ошибка при хуке DialogsActivity.createView(): {e}")

        # Хук onResume()
        try:
            on_resume_method = DialogsActivityClass.getMethod("onResume")
            self.hook_method(on_resume_method, DialogsActivityResumeHook(self))
            self.logger.info("Хук DialogsActivity.onResume() успешно установлен")
        except Exception as e:
            self.logger.error(f"Ошибка при хуке DialogsActivity.onResume(): {e}")

    def hide_folder_tabs(self, dialogs_activity):
        """Скрывает верхние вкладки папок, убирая визуальный шум."""
        tab_field_names = ("scrollSlidingTabStrip", "folderTabsView", "tabsView")
        for field_name in tab_field_names:
            tabs = get_private_field(dialogs_activity, field_name)
            if tabs:
                try:
                    tabs.setVisibility(8)  # View.GONE = 8
                except Exception as e:
                    self.logger.debug(f"Не удалось скрыть {field_name}: {e}")

    def open_search(self, dialogs_activity):
        """Программно открывает поле поиска."""
        try:
            search_item = get_private_field(dialogs_activity, "searchItem")
            if search_item:
                search_item.openSearch(True)
        except Exception as e:
            self.logger.debug(f"Не удалось открыть строку поиска: {e}")

    def inject_focus_ui(self, dialogs_activity, root_view):
        """
        Внедряет визуальную карточку режима фокуса на главный экран.
        Если карточка уже создана, обновляет её видимость.
        """
        try:
            existing = root_view.findViewWithTag(OVERLAY_TAG)
            if existing:
                existing.setVisibility(0 if self.is_focus_enabled() else 8)
                return

            from android.view import Gravity
            from android.widget import LinearLayout, TextView
            from android_utils import OnClickListener
            from org.telegram.messenger import AndroidUtilities
            from org.telegram.ui.ActionBar import Theme
            from org.telegram.ui.Components import LayoutHelper

            context = root_view.getContext()

            # Главный контейнер фокуса
            container = LinearLayout(context)
            container.setTag(OVERLAY_TAG)
            container.setOrientation(LinearLayout.VERTICAL)
            container.setGravity(Gravity.CENTER)
            container.setPadding(
                AndroidUtilities.dp(24),
                AndroidUtilities.dp(24),
                AndroidUtilities.dp(24),
                AndroidUtilities.dp(24),
            )

            # Заголовок
            title_view = TextView(context)
            title_view.setText("🎯 Focus Mode")
            title_view.setTextSize(22)
            title_view.setGravity(Gravity.CENTER)
            try:
                title_view.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                pass
            title_view.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            container.addView(title_view)

            # Описание
            desc_view = TextView(context)
            desc_view.setText(
                "Шум и лента чатов скрыты.\n"
                "Используйте поиск сверху или нажмите кнопку ниже, чтобы найти нужный чат или бота."
            )
            desc_view.setTextSize(14)
            desc_view.setGravity(Gravity.CENTER)
            desc_view.setPadding(0, AndroidUtilities.dp(10), 0, AndroidUtilities.dp(20))
            desc_view.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            container.addView(desc_view)

            # Кнопка быстрого вызова поиска
            btn_view = TextView(context)
            btn_view.setText("🔍 Найти чат или бота")
            btn_view.setTextSize(15)
            btn_view.setGravity(Gravity.CENTER)
            btn_view.setPadding(
                AndroidUtilities.dp(20),
                AndroidUtilities.dp(12),
                AndroidUtilities.dp(20),
                AndroidUtilities.dp(12),
            )
            btn_view.setBackground(
                Theme.createSimpleSelectorRoundRectDrawable(
                    AndroidUtilities.dp(10),
                    Theme.getColor(Theme.key_featuredStickers_addButton),
                    Theme.getColor(Theme.key_featuredStickers_addButtonPressed),
                )
            )
            btn_view.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))

            # Клик по кнопке -> открытие поиска
            def on_search_button_click(v):
                self.open_search(dialogs_activity)

            btn_view.setOnClickListener(OnClickListener(on_search_button_click))
            container.addView(btn_view)

            # Добавляем контейнер поверх фрагмента
            layout_params = LayoutHelper.createFrame(
                LayoutHelper.MATCH_PARENT, LayoutHelper.WRAP_CONTENT, Gravity.CENTER
            )
            root_view.addView(container, layout_params)
            self.logger.info("Focus UI успешно внедрён на главный экран!")

        except Exception as e:
            self.logger.warning(f"Не удалось внедрить Focus UI: {e}")

    def create_settings(self) -> List[Any]:
        """Интерфейс настроек плагина в приложении."""
        return [
            Header(text="Режим фокусировки (Spotlight)"),
            Switch(
                key="focus_enabled",
                text="Включить Focus Mode",
                default=True,
                subtext="Скрывает стандартную ленту всех чатов, каналов и групп",
            ),
            Switch(
                key="auto_open_search",
                text="Авто-поиск при входе",
                default=False,
                subtext="Сразу открывать клавиатуру и поле поиска при открытии Telegram",
            ),
            Switch(
                key="hide_folders",
                text="Скрывать вкладки папок",
                default=True,
                subtext="Скрывает горизонтальные папки сверху для минимализма",
            ),
            Divider(),
            Text(
                text="О плагине",
                subtext="AyuGram Focus v0.1.0\nРазработано специально для исключения информационного шума.",
            ),
        ]
