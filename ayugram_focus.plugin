# -*- coding: utf-8 -*-
"""
AyuGram Focus Plugin (Spotlight Focus)
Version: 0.3.0
Скрывает ленту чатов и вкладки папок, оставляя только нативный поиск Telegram.
"""

import logging
from typing import Any, List

from android_utils import run_on_ui_thread
from base_plugin import BasePlugin, MethodHook, MenuItemData, MenuItemType
from hook_utils import find_class, get_private_field
from ui.settings import Header, Switch, Text, Divider

# --- Plugin Metadata ---
__id__ = "ayugram_focus"
__name__ = "AyuGram Focus (Spotlight)"
__description__ = (
    "Скрывает ленту чатов и вкладки папок в Telegram, "
    "оставляя только нативный поиск без отвлекающего шума."
)
__author__ = "@AL1US"
__version__ = "0.3.0"
__icon__ = "exteraPlugins/1"
__app_version__ = ">=10.0.0"
__sdk_version__ = ">=1.4.0"


def show_toast(text: str):
    """Отображает системный Toast на экране."""
    def _run():
        try:
            from org.telegram.messenger import ApplicationLoader
            from android.widget import Toast
            ctx = ApplicationLoader.applicationContext
            if ctx:
                Toast.makeText(ctx, f"[Focus] {text}", Toast.LENGTH_SHORT).show()
        except Exception:
            pass

    try:
        run_on_ui_thread(_run)
    except Exception:
        pass


def find_method_in_hierarchy(clazz: Any, name: str, *param_types: Any) -> Any:
    """Ищет метод по всей иерархии классов."""
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
    """Безопасное логирование."""

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


class DialogsLifecycleHook(MethodHook):
    """Срабатывает при показе экрана чатов (onResume / onBecomeFullyVisible)."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_focus_mode(param.thisObject, True)


class DialogsShowSearchHook(MethodHook):
    """Отслеживает открытие и закрытие поиска в DialogsActivity."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        try:
            args = param.getArgs()
            if args and len(args) > 0:
                is_show = bool(args[0])
                if not is_show and self.plugin.is_focus_enabled():
                    # Поиск закрылся — снова скрываем чаты и папки
                    self.plugin.apply_focus_mode(param.thisObject, True)
        except Exception:
            pass


class DialogsCloseSearchHook(MethodHook):
    """Срабатывает при закрытии поиска через closeSearch()."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_focus_mode(param.thisObject, True)


class FilterTabsCheckHook(MethodHook):
    """Предотвращает показ вкладок папок Telegram при включенном Focus Mode."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            try:
                ftv = getattr(param.thisObject, "filterTabsView", None) or get_private_field(param.thisObject, "filterTabsView")
                if ftv:
                    from android.view import View
                    ftv.setVisibility(View.GONE)
            except Exception:
                pass


class AyuGramFocusPlugin(BasePlugin):
    """Основной класс плагина фокуса."""

    @property
    def logger(self) -> SafeLogger:
        if not hasattr(self, "_safe_logger_instance"):
            self._safe_logger_instance = SafeLogger(self)
        return self._safe_logger_instance

    def on_plugin_load(self):
        self.logger.info(f"AyuGram Focus v{__version__} загружен")

        try:
            self.add_menu_item(MenuItemData(
                menu_type=MenuItemType.DRAWER_MENU,
                text="🎯 Переключить Focus Mode",
                on_click=self.handle_drawer_click,
                icon="msg_search"
            ))
        except Exception as e:
            self.logger.warning(f"Ошибка добавления пункта меню: {e}")

        self._hook_dialogs_activity()

    def on_plugin_unload(self):
        self.logger.info("AyuGram Focus выгружен")
        try:
            from client_utils import get_last_fragment
            frag = get_last_fragment()
            if frag:
                self.apply_focus_mode(frag, False)
        except Exception:
            pass

    def is_focus_enabled(self) -> bool:
        try:
            if hasattr(self, "get_setting"):
                return bool(self.get_setting("focus_enabled", True))
        except Exception:
            pass
        return True

    def handle_drawer_click(self, context: Any):
        """Переключение фокуса из бокового меню."""
        def _action():
            try:
                frag = context.get("fragment")
                if not frag:
                    try:
                        from client_utils import get_last_fragment
                        frag = get_last_fragment()
                    except Exception:
                        pass

                if not frag:
                    show_toast("Не удалось определить экран чатов")
                    return

                new_state = not self.is_focus_enabled()
                self.set_setting("focus_enabled", new_state)
                self.apply_focus_mode(frag, new_state)
                status = "ВКЛЮЧЁН (чаты скрыты)" if new_state else "ВЫКЛЮЧЕН (чаты видны)"
                show_toast(status)
            except Exception as e:
                show_toast(f"Ошибка: {e}")

        run_on_ui_thread(_action)

    def _hook_dialogs_activity(self):
        """Устанавливает хуки на экран диалогов Telegram."""
        DialogsActivityClass = find_class("org.telegram.ui.DialogsActivity")
        if not DialogsActivityClass:
            return

        lifecycle_hook = DialogsLifecycleHook(self)
        for m_name in ("onBecomeFullyVisible", "onResume"):
            m = find_method_in_hierarchy(DialogsActivityClass, m_name)
            if m:
                try:
                    self.hook_method(m, lifecycle_hook)
                except Exception:
                    pass

        show_hook = DialogsShowSearchHook(self)
        close_hook = DialogsCloseSearchHook(self)
        filter_tabs_hook = FilterTabsCheckHook(self)

        curr = DialogsActivityClass
        while curr:
            try:
                for m in curr.getDeclaredMethods():
                    name = m.getName()
                    if name == "showSearch":
                        try:
                            self.hook_method(m, show_hook)
                        except Exception:
                            pass
                    elif name == "closeSearch":
                        try:
                            self.hook_method(m, close_hook)
                        except Exception:
                            pass
                    elif name == "checkUi_filterTabsVisible":
                        try:
                            self.hook_method(m, filter_tabs_hook)
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                curr = curr.getSuperclass()
            except Exception:
                break

    def apply_focus_mode(self, fragment: Any, is_enabled: bool):
        """
        Управляет видимостью элементов главного экрана Telegram.
        При is_enabled=True: скрывает чаты, папки, истории и кнопку создания.
        При этом нативная строка поиска Telegram и верхняя панель остаются полностью рабочими.
        """
        def _ui_task():
            try:
                from android.view import View

                # 0. Удаляем старый оверлей, если он остался от прошлых версий
                try:
                    rv = getattr(fragment, "fragmentView", None) or get_private_field(fragment, "fragmentView")
                    if rv and hasattr(rv, "findViewWithTag"):
                        old_overlay = rv.findViewWithTag("ayugram_focus_fullscreen_overlay")
                        if old_overlay:
                            if hasattr(rv, "removeView"):
                                rv.removeView(old_overlay)
                            else:
                                old_overlay.setVisibility(View.GONE)
                except Exception:
                    pass

                # 1. Скрываем/показываем вкладки папок (filterTabsView)
                ftv = getattr(fragment, "filterTabsView", None) or get_private_field(fragment, "filterTabsView")
                if ftv:
                    ftv.setVisibility(View.GONE if is_enabled else View.VISIBLE)

                # 2. Скрываем/показываем истории (dialogStoriesCell)
                dsc = getattr(fragment, "dialogStoriesCell", None) or get_private_field(fragment, "dialogStoriesCell")
                if dsc:
                    dsc.setVisibility(View.GONE if is_enabled else View.VISIBLE)

                # 3. Скрываем/показываем кнопку создания чата (writeButton)
                wb = getattr(fragment, "writeButton", None) or get_private_field(fragment, "writeButton")
                if wb:
                    wb.setVisibility(View.GONE if is_enabled else View.VISIBLE)

                # 4. Скрываем/показываем список чатов (viewPages и listView)
                vps = getattr(fragment, "viewPages", None) or get_private_field(fragment, "viewPages")
                if vps:
                    try:
                        for vp in vps:
                            if vp:
                                vp.setVisibility(View.GONE if is_enabled else View.VISIBLE)
                                lv = getattr(vp, "listView", None) or get_private_field(vp, "listView")
                                if lv:
                                    lv.setVisibility(View.GONE if is_enabled else View.VISIBLE)
                    except Exception:
                        pass

                # 5. Нативный поиск Telegram (fragmentSearchField) должен оставаться видимым и кликабельным!
                fsf = getattr(fragment, "fragmentSearchField", None) or get_private_field(fragment, "fragmentSearchField")
                if fsf:
                    fsf.setVisibility(View.VISIBLE)
                    fsf.setAlpha(1.0)
                    if hasattr(fsf, "bringToFront"):
                        fsf.bringToFront()

                # 6. Верхняя шапка (ActionBar) с кнопкой меню также должна быть видна
                ab = getattr(fragment, "actionBar", None) or get_private_field(fragment, "actionBar")
                if ab:
                    ab.setVisibility(View.VISIBLE)
                    ab.setAlpha(1.0)
                    if hasattr(ab, "bringToFront"):
                        ab.bringToFront()

            except Exception as e:
                self.logger.warning(f"apply_focus_mode error: {e}")

        run_on_ui_thread(_ui_task)

    def create_settings(self) -> List[Any]:
        return [
            Header(text="Режим фокусировки (Spotlight)"),
            Switch(
                key="focus_enabled",
                text="Включить Focus Mode",
                default=True,
                subtext="Скрывает ленту всех чатов, каналов и папок, оставляя нативный поиск",
            ),
            Divider(),
            Text(
                text="О плагине",
                subtext=f"AyuGram Focus v{__version__}\nОставляет только нативный поиск Telegram.",
            ),
        ]
