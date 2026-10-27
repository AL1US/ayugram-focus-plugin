# -*- coding: utf-8 -*-
"""
AyuGram Focus Plugin (Spotlight Focus)
Phase 1: Fullscreen Clean Overlay & Window-level Search Resolution.
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
__version__ = "0.1.8"
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


def show_debug_dialog(context: Any, title: str, message: str):
    """Показывает стандартный диалог Android для отладки."""
    def _run():
        try:
            from android.app import AlertDialog
            builder = AlertDialog.Builder(context)
            builder.setTitle(title)
            builder.setMessage(message)
            builder.setPositiveButton("OK", None)
            builder.show()
        except Exception:
            show_toast(message[:100])

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


class DialogsVisibleHook(MethodHook):
    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_fullscreen_overlay(param.thisObject, True)


class DialogsResumeHook(MethodHook):
    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_fullscreen_overlay(param.thisObject, True)


class DialogsCreateViewHook(MethodHook):
    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            root_view = param.getResult()
            self.plugin.apply_fullscreen_overlay(param.thisObject, True, root_view)


class MenuItemOpenSearchHook(MethodHook):
    """Скрывает оверлей, когда поиск открыт."""
    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        try:
            from client_utils import get_last_fragment
            frag = get_last_fragment()
            if frag:
                self.plugin.apply_fullscreen_overlay(frag, False)
        except Exception:
            pass


class MenuItemCloseSearchHook(MethodHook):
    """Возвращает оверлей, когда поиск закрыт."""
    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            try:
                from client_utils import get_last_fragment
                frag = get_last_fragment()
                if frag:
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
        self.logger.info("AyuGram Focus v0.1.8 загружен")

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
        DialogsActivityClass = find_class("org.telegram.ui.DialogsActivity")
        if not DialogsActivityClass:
            return

        m_vis = find_method_in_hierarchy(DialogsActivityClass, "onBecomeFullyVisible")
        if m_vis:
            try:
                self.hook_method(m_vis, DialogsVisibleHook(self))
            except Exception:
                pass

        m_res = find_method_in_hierarchy(DialogsActivityClass, "onResume")
        if m_res:
            try:
                self.hook_method(m_res, DialogsResumeHook(self))
            except Exception:
                pass

        ContextClass = find_class("android.content.Context")
        if ContextClass:
            m_cv = find_method_in_hierarchy(DialogsActivityClass, "createView", ContextClass)
            if m_cv:
                try:
                    self.hook_method(m_cv, DialogsCreateViewHook(self))
                except Exception:
                    pass

    def _hook_action_bar_menu_item(self):
        ActionBarMenuItemClass = find_class("org.telegram.ui.ActionBar.ActionBarMenuItem")
        if not ActionBarMenuItemClass:
            return

        open_hook = MenuItemOpenSearchHook(self)
        close_hook = MenuItemCloseSearchHook(self)

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
        except Exception as e:
            self.logger.warning(f"Ошибка хука ActionBarMenuItem: {e}")

    def find_all_search_candidates(self, root_view: Any) -> List[Any]:
        """
        Сканирует всё окно Android (DecorView) и находит любые элементы поиска.
        """
        candidates = []
        try:
            decor = root_view.getRootView()
            if not decor:
                return candidates

            def _traverse(v):
                if not v:
                    return
                try:
                    cname = v.getClass().getName()
                    if "ActionBarMenuItem" in cname or "SearchView" in cname:
                        candidates.append(v)
                        return
                except Exception:
                    pass

                try:
                    desc = str(v.getContentDescription() or "").lower()
                    if "search" in desc or "поиск" in desc:
                        candidates.append(v)
                        return
                except Exception:
                    pass

                if hasattr(v, "getChildCount"):
                    for i in range(v.getChildCount()):
                        _traverse(v.getChildAt(i))

            _traverse(decor)
        except Exception as e:
            self.logger.warning(f"Ошибка сканирования окна: {e}")

        return candidates

    def trigger_search(self, fragment: Any, overlay: Any, root_view: Any):
        """
        Ищет кнопку поиска по всему окну и программно активирует её.
        """
        candidates = self.find_all_search_candidates(root_view)

        opened = False
        debug_log = []

        for item in candidates:
            cname = item.getClass().getSimpleName()
            debug_log.append(f"Found: {cname}")

            # 1. openSearch(True)
            try:
                if hasattr(item, "openSearch"):
                    item.openSearch(True)
                    opened = True
                    break
            except Exception:
                pass

            # 2. toggleSearch(True)
            try:
                if hasattr(item, "toggleSearch"):
                    item.toggleSearch(True)
                    opened = True
                    break
            except Exception:
                pass

            # 3. performClick()
            try:
                if item.performClick():
                    opened = True
                    break
            except Exception:
                pass

            # 4. callOnClick()
            try:
                item.callOnClick()
                opened = True
                break
            except Exception:
                pass

        if opened:
            # Скрываем оверлей только после успешного старта
            if overlay:
                overlay.setVisibility(8)
            # Показываем клавиатуру
            try:
                from org.telegram.messenger import AndroidUtilities
                for it in candidates:
                    if hasattr(it, "getSearchField"):
                        f = it.getSearchField()
                        if f:
                            AndroidUtilities.showKeyboard(f)
                            break
            except Exception:
                pass
        else:
            # Если не нашли — показываем информативный диалог
            ctx = root_view.getContext()
            msg = (
                f"Найдено элементов поиска: {len(candidates)}\n"
                f"{chr(10).join(debug_log)}\n\n"
                "Вы можете просто нажать значок лупы 🔍 в правом верхнем углу Telegram."
            )
            show_debug_dialog(ctx, "Поиск не запущен", msg)

    def apply_fullscreen_overlay(self, fragment: Any, is_enabled: bool, root_view: Any = None):
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

                overlay = rv.findViewWithTag(OVERLAY_TAG)

                if not is_enabled:
                    if overlay:
                        overlay.setVisibility(View.GONE)
                    return

                if overlay:
                    overlay.setVisibility(View.VISIBLE)
                    overlay.bringToFront()
                    return

                context = rv.getContext()
                overlay = FrameLayout(context)
                overlay.setTag(OVERLAY_TAG)
                overlay.setClickable(True)

                bg_color = Color.parseColor("#0F172A")
                title_color = Color.WHITE
                sub_color = Color.parseColor("#94A3B8")
                try:
                    from org.telegram.ui.ActionBar import Theme
                    bg_color = Theme.getColor(Theme.key_windowBackgroundWhite)
                    title_color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
                    sub_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
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
                center.addView(title)

                sub = TextView(context)
                sub.setText("Все чаты и каналы скрыты.\nНажмите кнопку ниже, чтобы открыть поиск.")
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
                btn.setBackgroundColor(Color.parseColor("#3B82F6"))
                btn.setTextColor(Color.WHITE)

                def _on_btn_click(v):
                    self.trigger_search(fragment, overlay, rv)

                btn.setOnClickListener(OnClickListener(_on_btn_click))
                center.addView(btn)

                c_params = FrameLayout.LayoutParams(-1, -2, Gravity.CENTER)
                overlay.addView(center, c_params)

                full_params = FrameLayout.LayoutParams(-1, -1)
                rv.addView(overlay, full_params)
                overlay.bringToFront()

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
                subtext="AyuGram Focus v0.1.8\nПерекрывает шумный экран и оставляет только поиск.",
            ),
        ]
