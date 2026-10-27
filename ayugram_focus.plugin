# -*- coding: utf-8 -*-
"""
AyuGram Focus Plugin (Spotlight Focus)
Phase 1: Fullscreen Clean Overlay & Native Telegram Search Integration.
Version: 0.2.0
"""

import logging
from typing import Any, List

from android_utils import run_on_ui_thread, OnClickListener
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
__version__ = "0.2.0"
__icon__ = "exteraPlugins/1"
__app_version__ = ">=10.0.0"
__sdk_version__ = ">=1.4.0"

OVERLAY_TAG = "ayugram_focus_fullscreen_overlay"


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
    """Срабатывает при возврате или отображении экрана чатов."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_fullscreen_overlay(param.thisObject, True)


class DialogsShowSearchHook(MethodHook):
    """Скрывает оверлей при открытии поиска и восстанавливает при закрытии."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        try:
            args = param.getArgs()
            if args and len(args) > 0:
                is_show = bool(args[0])
                if is_show:
                    # Поиск открыт — скрываем оверлей, открывая результаты
                    self.plugin.apply_fullscreen_overlay(param.thisObject, False)
                elif self.plugin.is_focus_enabled():
                    # Поиск закрыт — возвращаем оверлей
                    self.plugin.apply_fullscreen_overlay(param.thisObject, True)
        except Exception:
            pass


class DialogsCloseSearchHook(MethodHook):
    """Возвращает оверлей при закрытии поиска через closeSearch()."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_fullscreen_overlay(param.thisObject, True)


class MenuItemSearchHook(MethodHook):
    """Отслеживает изменение поиска в ActionBarMenuItem (для совместимости)."""

    def __init__(self, plugin: "AyuGramFocusPlugin", is_open_hook: bool):
        self.plugin = plugin
        self.is_open_hook = is_open_hook

    def after_hooked_method(self, param):
        try:
            from client_utils import get_last_fragment
            frag = get_last_fragment()
            if frag:
                if self.is_open_hook:
                    self.plugin.apply_fullscreen_overlay(frag, False)
                elif self.plugin.is_focus_enabled():
                    self.plugin.apply_fullscreen_overlay(frag, True)
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

        # Добавляем пункт в боковое меню
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
        self._hook_action_bar_menu_item()

    def on_plugin_unload(self):
        self.logger.info("AyuGram Focus выгружен")

    def is_focus_enabled(self) -> bool:
        try:
            if hasattr(self, "get_setting"):
                return bool(self.get_setting("focus_enabled", True))
        except Exception:
            pass
        return True

    def handle_drawer_click(self, context: Any):
        """Клик по пункту в боковом меню."""
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
                self.apply_fullscreen_overlay(frag, new_state)
                status = "ВКЛЮЧЁН" if new_state else "ВЫКЛЮЧЕН"
                show_toast(f"Режим Focus: {status}")
            except Exception as e:
                show_toast(f"Ошибка: {e}")

        run_on_ui_thread(_action)

    def _hook_dialogs_activity(self):
        """Хукает жизненный цикл и поиск в DialogsActivity."""
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
            except Exception:
                pass
            try:
                curr = curr.getSuperclass()
            except Exception:
                break

    def _hook_action_bar_menu_item(self):
        """Хукает методы ActionBarMenuItem для совместимости с классическим интерфейсом."""
        ActionBarMenuItemClass = find_class("org.telegram.ui.ActionBar.ActionBarMenuItem")
        if not ActionBarMenuItemClass:
            return

        open_hook = MenuItemSearchHook(self, True)
        close_hook = MenuItemSearchHook(self, False)

        try:
            for m in ActionBarMenuItemClass.getDeclaredMethods():
                name = m.getName()
                if name in ("openSearch", "toggleSearch"):
                    try:
                        self.hook_method(m, open_hook)
                    except Exception:
                        pass
                elif name == "closeSearch":
                    try:
                        self.hook_method(m, close_hook)
                    except Exception:
                        pass
        except Exception:
            pass

    def _bring_search_and_actionbar_to_front(self, fragment: Any):
        """
        Гарантирует, что верхняя шапка (меню) и нативная строка поиска остаются
        поверх оверлея и доступны пользователю.
        """
        try:
            ab = getattr(fragment, "actionBar", None) or get_private_field(fragment, "actionBar")
            if ab and hasattr(ab, "bringToFront"):
                ab.bringToFront()
        except Exception:
            pass

        try:
            fsf = getattr(fragment, "fragmentSearchField", None) or get_private_field(fragment, "fragmentSearchField")
            if fsf and hasattr(fsf, "bringToFront"):
                fsf.bringToFront()
        except Exception:
            pass

    def trigger_search(self, fragment: Any, overlay: Any):
        """
        Нативно активирует поиск Telegram.
        Работает со всеми версиями Telegram: Telegram 10+ (fragmentSearchField)
        и классическими (searchItem / ActionBar).
        """
        try:
            from org.telegram.messenger import AndroidUtilities
        except Exception:
            AndroidUtilities = None

        opened = False

        # 1. Вызов нативного метода showSearch(boolean show, ...) у самого DialogsActivity
        try:
            curr = fragment.getClass()
            while curr and not opened:
                for m in curr.getDeclaredMethods():
                    if m.getName() == "showSearch":
                        m.setAccessible(True)
                        count = m.getParameterCount()
                        if count == 3:
                            m.invoke(fragment, True, False, True)
                            opened = True
                            break
                        elif count == 4:
                            m.invoke(fragment, True, False, True, False)
                            opened = True
                            break
                curr = curr.getSuperclass()
        except Exception as e:
            self.logger.warning(f"showSearch invoke failed: {e}")

        # 2. Активация через fragmentSearchFieldWatcher и fragmentSearchField
        try:
            watcher = getattr(fragment, "fragmentSearchFieldWatcher", None) or get_private_field(fragment, "fragmentSearchFieldWatcher")
            if watcher and hasattr(watcher, "toggleSearch"):
                watcher.toggleSearch(True)
                opened = True
        except Exception as e:
            self.logger.warning(f"toggleSearch failed: {e}")

        try:
            fsf = getattr(fragment, "fragmentSearchField", None) or get_private_field(fragment, "fragmentSearchField")
            if fsf:
                edit_text = getattr(fsf, "editText", None) or get_private_field(fsf, "editText")
                if edit_text:
                    edit_text.requestFocus()
                    if AndroidUtilities:
                        AndroidUtilities.showKeyboard(edit_text)
                    opened = True
                elif hasattr(fsf, "performClick"):
                    fsf.performClick()
                    opened = True
        except Exception as e:
            self.logger.warning(f"fragmentSearchField focus failed: {e}")

        # 3. Клик по searchItem у самого фрагмента
        if not opened:
            try:
                si = getattr(fragment, "searchItem", None) or get_private_field(fragment, "searchItem")
                if si:
                    if hasattr(si, "performClick") and si.performClick():
                        opened = True
                    elif hasattr(si, "callOnClick"):
                        si.callOnClick()
                        opened = True
            except Exception as e:
                self.logger.warning(f"searchItem click failed: {e}")

        # 4. Сканирование меню ActionBar (для более старых версий)
        if not opened:
            try:
                ab = getattr(fragment, "actionBar", None) or get_private_field(fragment, "actionBar")
                if ab:
                    menu = getattr(ab, "menu", None) or get_private_field(ab, "menu")
                    if menu and hasattr(menu, "getChildCount"):
                        for i in range(menu.getChildCount()):
                            child = menu.getChildAt(i)
                            if child:
                                try:
                                    if hasattr(child, "openSearch"):
                                        child.openSearch(True)
                                        opened = True
                                        break
                                    elif hasattr(child, "performClick") and child.performClick():
                                        opened = True
                                        break
                                except Exception:
                                    pass
            except Exception as e:
                self.logger.warning(f"actionBar menu click failed: {e}")

        if opened:
            if overlay:
                from android.view import View
                overlay.setVisibility(View.GONE)
        else:
            show_toast("Нажмите строку поиска в верхней части экрана")

    def apply_fullscreen_overlay(self, fragment: Any, is_enabled: bool, root_view: Any = None):
        """Отображает или скрывает защитный экран фокуса поверх ленты чатов."""
        def _ui_task():
            try:
                rv = root_view
                if rv is None:
                    try:
                        rv = fragment.getFragmentView()
                    except Exception:
                        rv = get_private_field(fragment, "fragmentView")

                if not rv:
                    return

                from android.view import Gravity, View
                from android.widget import FrameLayout, LinearLayout, TextView
                from android.graphics import Color
                from android.graphics.drawable import GradientDrawable

                overlay = rv.findViewWithTag(OVERLAY_TAG)

                if not is_enabled:
                    if overlay:
                        overlay.setVisibility(View.GONE)
                    return

                # Проверяем, не открыт ли сейчас поиск в Telegram
                is_searching = False
                try:
                    s1 = getattr(fragment, "searching", None) or get_private_field(fragment, "searching")
                    s2 = getattr(fragment, "searchIsShowed", None) or get_private_field(fragment, "searchIsShowed")
                    is_searching = bool(s1 or s2)
                except Exception:
                    pass

                if is_searching:
                    if overlay:
                        overlay.setVisibility(View.GONE)
                    return

                if overlay:
                    overlay.setVisibility(View.VISIBLE)
                    overlay.bringToFront()
                    self._bring_search_and_actionbar_to_front(fragment)
                    return

                context = rv.getContext()
                overlay = FrameLayout(context)
                overlay.setTag(OVERLAY_TAG)
                overlay.setClickable(True)
                overlay.setFocusable(True)

                # Тематические цвета
                bg_color = Color.parseColor("#0F172A")
                title_color = Color.WHITE
                sub_color = Color.parseColor("#94A3B8")
                btn_color = Color.parseColor("#3B82F6")

                try:
                    from org.telegram.ui.ActionBar import Theme
                    bg_color = Theme.getColor(Theme.key_windowBackgroundWhite)
                    title_color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
                    sub_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
                    btn_color = Theme.getColor(Theme.key_featuredStickers_addButton) or btn_color
                except Exception:
                    pass

                overlay.setBackgroundColor(bg_color)

                center = LinearLayout(context)
                center.setOrientation(LinearLayout.VERTICAL)
                center.setGravity(Gravity.CENTER)
                center.setPadding(40, 40, 40, 40)

                title = TextView(context)
                title.setText("🎯 Focus Mode")
                title.setTextSize(26)
                title.setGravity(Gravity.CENTER)
                title.setTextColor(title_color)
                title.setTypeface(title.getTypeface(), 1)
                center.addView(title)

                sub = TextView(context)
                sub.setText("Все чаты и каналы скрыты.\nВведите запрос в поиск выше или нажмите кнопку.")
                sub.setTextSize(14)
                sub.setGravity(Gravity.CENTER)
                sub.setPadding(0, 20, 0, 40)
                sub.setTextColor(sub_color)
                center.addView(sub)

                btn = TextView(context)
                btn.setText("🔍  Найти чат или бота")
                btn.setTextSize(16)
                btn.setGravity(Gravity.CENTER)
                btn.setPadding(48, 28, 48, 28)
                btn.setTextColor(Color.WHITE)
                btn.setTypeface(btn.getTypeface(), 1)

                btn_bg = GradientDrawable()
                btn_bg.setShape(GradientDrawable.RECTANGLE)
                btn_bg.setCornerRadius(24.0)
                btn_bg.setColor(btn_color)
                btn.setBackground(btn_bg)

                def _on_btn_click(v):
                    self.trigger_search(fragment, overlay)

                btn.setOnClickListener(OnClickListener(_on_btn_click))
                center.addView(btn)

                c_params = FrameLayout.LayoutParams(-1, -2, Gravity.CENTER)
                overlay.addView(center, c_params)

                full_params = FrameLayout.LayoutParams(-1, -1)
                rv.addView(overlay, full_params)
                overlay.bringToFront()

                self._bring_search_and_actionbar_to_front(fragment)

            except Exception as e:
                show_toast(f"Ошибка интерфейса: {e}")

        run_on_ui_thread(_ui_task)

    def create_settings(self) -> List[Any]:
        return [
            Header(text="Режим фокусировки (Spotlight)"),
            Switch(
                key="focus_enabled",
                text="Включить Focus Mode",
                default=True,
                subtext="Скрывает стандартную ленту всех чатов, каналов и групп",
            ),
            Divider(),
            Text(
                text="О плагине",
                subtext=f"AyuGram Focus v{__version__}\nСкрывает шум и открывает прямой поиск.",
            ),
        ]
