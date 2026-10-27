# -*- coding: utf-8 -*-
"""
AyuGram Focus Plugin (Spotlight Focus)
Phase 1: Minimalist Search-first UI & Chat List Suppression.
"""

import logging
from typing import Any, List

from base_plugin import BasePlugin, MethodHook, MenuItemData, MenuItemType
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
__version__ = "0.1.3"
__icon__ = "exteraPlugins/1"
__app_version__ = ">=10.0.0"
__sdk_version__ = ">=1.4.0"

OVERLAY_TAG = "ayugram_focus_overlay_view"


def show_toast(text: str):
    """Отображает всплывающее уведомление (Toast) на экране Android."""
    def _run():
        try:
            from org.telegram.messenger import ApplicationLoader
            from android.widget import Toast
            ctx = ApplicationLoader.applicationContext
            if ctx:
                Toast.makeText(ctx, f"[AyuGram Focus] {text}", Toast.LENGTH_SHORT).show()
        except Exception:
            pass

    try:
        from android_utils import run_on_ui_thread
        run_on_ui_thread(_run)
    except Exception:
        pass


def find_method_in_hierarchy(clazz: Any, name: str, *param_types: Any) -> Any:
    """Ищет метод по имени и типам аргументов по всей иерархии классов."""
    curr = clazz
    while curr is not None:
        try:
            m = curr.getDeclaredMethod(name, *param_types)
            m.setAccessible(True)
            return m
        except Exception:
            pass
        try:
            curr = curr.getSuperclass()
        except Exception:
            break
    return None


class SafeLogger:
    """Обеспечивает совместимость логирования со всеми версиями клиента."""

    def __init__(self, plugin: Any):
        self.plugin = plugin
        self._sys_logger = logging.getLogger(__id__)

    def _log(self, level: str, msg: str, *args):
        formatted = msg % args if args else str(msg)
        full_msg = f"[{level}] {formatted}"

        try:
            if hasattr(self.plugin, "log") and callable(getattr(self.plugin, "log")):
                self.plugin.log(full_msg)
                return
        except Exception:
            pass

        try:
            from android_utils import log as a_log
            a_log(full_msg)
            return
        except Exception:
            pass

        try:
            self._sys_logger.info(full_msg)
        except Exception:
            print(f"[{__id__}] {full_msg}")

    def info(self, msg: str, *args):
        self._log("INFO", msg, *args)

    def error(self, msg: str, *args):
        self._log("ERROR", msg, *args)

    def warning(self, msg: str, *args):
        self._log("WARN", msg, *args)

    def debug(self, msg: str, *args):
        self._log("DEBUG", msg, *args)

    def exception(self, msg: str, *args):
        import traceback
        self._log("ERROR", f"{msg}\n{traceback.format_exc()}", *args)


class DialogsAdapterItemCountHook(MethodHook):
    """Перехватывает подсчёт элементов в адаптере чатов."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        try:
            super().__init__()
        except Exception:
            pass
        self.plugin = plugin

    def before_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            param.setResult(0)


class DialogsActivityCreateViewHook(MethodHook):
    """Хук создания интерфейса DialogsActivity."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        try:
            super().__init__()
        except Exception:
            pass
        self.plugin = plugin

    def after_hooked_method(self, param):
        dialogs_activity = param.thisObject
        root_view = param.getResult()
        self.plugin.apply_focus_state(dialogs_activity, root_view)


class DialogsActivityResumeHook(MethodHook):
    """Хук onResume для обновления состояния при возврате на экран."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        try:
            super().__init__()
        except Exception:
            pass
        self.plugin = plugin

    def after_hooked_method(self, param):
        dialogs_activity = param.thisObject
        self.plugin.apply_focus_state(dialogs_activity)


class AyuGramFocusPlugin(BasePlugin):
    """Основной класс плагина фокуса."""

    @property
    def logger(self) -> SafeLogger:
        if not hasattr(self, "_safe_logger_instance"):
            self._safe_logger_instance = SafeLogger(self)
        return self._safe_logger_instance

    def on_plugin_load(self):
        self.logger.info("AyuGram Focus v0.1.3: старт инициализации...")
        show_toast("Плагин v0.1.3 активирован!")

        # Добавляем пункт в боковое меню (Drawer), чтобы проверить работу
        try:
            self.add_menu_item(MenuItemData(
                menu_type=MenuItemType.DRAWER_MENU,
                text="🎯 Переключить Focus Mode",
                on_click=self.handle_drawer_click,
                icon="msg_search"
            ))
        except Exception as e:
            self.logger.warning(f"Не удалось добавить пункт в боковое меню: {e}")

        self._hook_dialogs_adapter()
        self._hook_dialogs_activity()
        self.logger.info("AyuGram Focus: инициализация завершена!")

    def on_plugin_unload(self):
        self.logger.info("AyuGram Focus: плагин выгружен.")
        show_toast("Плагин выгружен")

    def handle_drawer_click(self, context: Any):
        """Обработка клика по пункту в боковом меню."""
        new_val = not self.is_focus_enabled()
        try:
            self.set_setting("focus_enabled", new_val, reload_settings=True)
        except Exception:
            pass
        status = "ВКЛЮЧЁН" if new_val else "ВЫКЛЮЧЕН"
        show_toast(f"Режим Focus: {status}")

    def is_focus_enabled(self) -> bool:
        try:
            if hasattr(self, "get_setting"):
                return bool(self.get_setting("focus_enabled", True))
        except Exception:
            pass
        return True

    def _hook_dialogs_adapter(self):
        DialogsAdapterClass = find_class("org.telegram.ui.Adapters.DialogsAdapter")
        if not DialogsAdapterClass:
            self.logger.error("Не найден класс DialogsAdapter")
            return

        method = find_method_in_hierarchy(DialogsAdapterClass, "getItemCount")
        if method:
            try:
                self.hook_method(method, DialogsAdapterItemCountHook(self))
                self.logger.info("Хук DialogsAdapter.getItemCount() успешно установлен")
            except Exception as e:
                self.logger.error(f"Ошибка при хуке DialogsAdapter.getItemCount(): {e}")
        else:
            self.logger.warning("Метод getItemCount() не найден в иерархии DialogsAdapter")

    def _hook_dialogs_activity(self):
        DialogsActivityClass = find_class("org.telegram.ui.DialogsActivity")
        if not DialogsActivityClass:
            self.logger.error("Не найден класс DialogsActivity")
            return

        # 1. createView
        ContextClass = find_class("android.content.Context")
        if ContextClass:
            create_method = find_method_in_hierarchy(DialogsActivityClass, "createView", ContextClass)
            if create_method:
                try:
                    self.hook_method(create_method, DialogsActivityCreateViewHook(self))
                    self.logger.info("Хук DialogsActivity.createView() успешно установлен")
                except Exception as e:
                    self.logger.error(f"Ошибка при хуке DialogsActivity.createView(): {e}")

        # 2. onResume
        resume_method = find_method_in_hierarchy(DialogsActivityClass, "onResume")
        if resume_method:
            try:
                self.hook_method(resume_method, DialogsActivityResumeHook(self))
                self.logger.info("Хук DialogsActivity.onResume() успешно установлен")
            except Exception as e:
                self.logger.error(f"Ошибка при хуке DialogsActivity.onResume(): {e}")
        else:
            self.logger.warning("Метод onResume() не найден в иерархии DialogsActivity")

    def apply_focus_state(self, dialogs_activity: Any, root_view: Any = None):
        is_enabled = self.is_focus_enabled()
        self.logger.info(f"apply_focus_state: is_enabled={is_enabled}")

        if root_view is None:
            try:
                root_view = dialogs_activity.getFragmentView()
            except Exception:
                root_view = get_private_field(dialogs_activity, "fragmentView")

        if not root_view:
            self.logger.warning("apply_focus_state: root_view не найден")
            return

        # Скрытие listView
        try:
            main_list = get_private_field(dialogs_activity, "listView")
            if main_list:
                main_list.setVisibility(8 if is_enabled else 0)
        except Exception:
            pass

        # Скрытие viewPages (папки/вкладки)
        try:
            view_pages = get_private_field(dialogs_activity, "viewPages")
            if view_pages:
                for page in view_pages:
                    if not page:
                        continue
                    for field in ("listView", "fragmentView"):
                        try:
                            v = get_private_field(page, field)
                            if v:
                                v.setVisibility(8 if is_enabled else 0)
                        except Exception:
                            pass
        except Exception:
            pass

        # Папки
        if self.get_setting("hide_folders", True):
            self.hide_folder_tabs(dialogs_activity, hide=is_enabled)
        else:
            self.hide_folder_tabs(dialogs_activity, hide=False)

        # Плавающая кнопка
        try:
            fab = get_private_field(dialogs_activity, "floatingButton")
            if fab:
                fab.setVisibility(8 if is_enabled else 0)
        except Exception:
            pass

        # Оверлей
        self.inject_focus_ui(dialogs_activity, root_view, is_enabled)

        # Авто-поиск
        if is_enabled and self.get_setting("auto_open_search", False):
            self.open_search(dialogs_activity)

    def hide_folder_tabs(self, dialogs_activity: Any, hide: bool = True):
        tab_field_names = ("scrollSlidingTabStrip", "folderTabsView", "tabsView")
        for field_name in tab_field_names:
            tabs = get_private_field(dialogs_activity, field_name)
            if tabs:
                try:
                    tabs.setVisibility(8 if hide else 0)
                except Exception:
                    pass

    def open_search(self, dialogs_activity: Any):
        try:
            search_item = get_private_field(dialogs_activity, "searchItem")
            if search_item:
                search_item.openSearch(True)
        except Exception:
            pass

    def inject_focus_ui(self, dialogs_activity: Any, root_view: Any, is_enabled: bool):
        try:
            existing = root_view.findViewWithTag(OVERLAY_TAG)
            if existing:
                existing.setVisibility(0 if is_enabled else 8)
                return

            if not is_enabled:
                return

            from android.view import Gravity
            from android.widget import LinearLayout, TextView
            from android_utils import OnClickListener
            from org.telegram.messenger import AndroidUtilities
            from org.telegram.ui.ActionBar import Theme
            from org.telegram.ui.Components import LayoutHelper

            context = root_view.getContext()

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

            title_view = TextView(context)
            title_view.setText("🎯 Focus Mode")
            title_view.setTextSize(22)
            title_view.setGravity(Gravity.CENTER)
            try:
                title_color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
            except Exception:
                title_color = -1
            title_view.setTextColor(title_color)
            container.addView(title_view)

            desc_view = TextView(context)
            desc_view.setText(
                "Шум и лента чатов скрыты.\n"
                "Используйте поиск сверху или нажмите кнопку ниже, чтобы найти нужный чат или бота."
            )
            desc_view.setTextSize(14)
            desc_view.setGravity(Gravity.CENTER)
            desc_view.setPadding(0, AndroidUtilities.dp(10), 0, AndroidUtilities.dp(20))
            try:
                desc_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            except Exception:
                desc_color = -3355444
            desc_view.setTextColor(desc_color)
            container.addView(desc_view)

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
            try:
                btn_view.setBackground(
                    Theme.createSimpleSelectorRoundRectDrawable(
                        AndroidUtilities.dp(10),
                        Theme.getColor(Theme.key_featuredStickers_addButton),
                        Theme.getColor(Theme.key_featuredStickers_addButtonPressed),
                    )
                )
                btn_view.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            except Exception:
                pass

            def on_search_button_click(v):
                self.open_search(dialogs_activity)

            btn_view.setOnClickListener(OnClickListener(on_search_button_click))
            container.addView(btn_view)

            layout_params = LayoutHelper.createFrame(
                LayoutHelper.MATCH_PARENT, LayoutHelper.WRAP_CONTENT, Gravity.CENTER
            )
            root_view.addView(container, layout_params)
            self.logger.info("Focus UI успешно внедрён!")

        except Exception as e:
            self.logger.warning(f"Не удалось внедрить Focus UI: {e}")

    def create_settings(self) -> List[Any]:
        return [
            Header(text="Режим фокусировки (Spotlight)"),
            Switch(
                key="focus_enabled",
                text="Включить Focus Mode",
                default=True,
                reload_settings=True,
                subtext="Скрывает стандартную ленту всех чатов, каналов и групп",
            ),
            Switch(
                key="auto_open_search",
                text="Авто-поиск при входе",
                default=False,
                reload_settings=True,
                subtext="Сразу открывать клавиатуру и поле поиска при открытии Telegram",
            ),
            Switch(
                key="hide_folders",
                text="Скрывать вкладки папок",
                default=True,
                reload_settings=True,
                subtext="Скрывает горизонтальные папки сверху для минимализма",
            ),
            Divider(),
            Text(
                text="О плагине",
                subtext="AyuGram Focus v0.1.3\nРазработано специально для исключения информационного шума.",
            ),
        ]
