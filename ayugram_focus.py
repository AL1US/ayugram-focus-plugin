# -*- coding: utf-8 -*-
"""
AyuGram Focus Plugin (Spotlight Focus)
Phase 1: Fullscreen Clean Overlay & Search.
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
__version__ = "0.1.5"
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


class DialogsVisibleHook(MethodHook):
    """Срабатывает, когда экран диалогов стал полностью видимым."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_fullscreen_overlay(param.thisObject, True)


class DialogsResumeHook(MethodHook):
    """Срабатывает при onResume."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            self.plugin.apply_fullscreen_overlay(param.thisObject, True)


class DialogsCreateViewHook(MethodHook):
    """Срабатывает при создании View."""

    def __init__(self, plugin: "AyuGramFocusPlugin"):
        self.plugin = plugin

    def after_hooked_method(self, param):
        if self.plugin.is_focus_enabled():
            root_view = param.getResult()
            self.plugin.apply_fullscreen_overlay(param.thisObject, True, root_view)


class AyuGramFocusPlugin(BasePlugin):
    """Основной класс плагина фокуса."""

    @property
    def logger(self) -> SafeLogger:
        if not hasattr(self, "_safe_logger_instance"):
            self._safe_logger_instance = SafeLogger(self)
        return self._safe_logger_instance

    def on_plugin_load(self):
        self.logger.info("AyuGram Focus v0.1.5 загружен")

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
        """Клик по пункту в боковом меню: мгновенно переключает режим и экран."""
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
                    show_toast("Ошибка: не удалось определить экран диалогов")
                    return

                new_state = not self.is_focus_enabled()
                self.set_setting("focus_enabled", new_state)
                self.apply_fullscreen_overlay(frag, new_state)
                status = "ВКЛЮЧЁН" if new_state else "ВЫКЛЮЧЕН"
                show_toast(f"Режим Focus: {status}")
            except Exception as e:
                show_toast(f"Ошибка клика: {e}")

        run_on_ui_thread(_action)

    def _hook_dialogs_activity(self):
        DialogsActivityClass = find_class("org.telegram.ui.DialogsActivity")
        if not DialogsActivityClass:
            return

        # 1. onBecomeFullyVisible
        m_vis = find_method_in_hierarchy(DialogsActivityClass, "onBecomeFullyVisible")
        if m_vis:
            try:
                self.hook_method(m_vis, DialogsVisibleHook(self))
            except Exception:
                pass

        # 2. onResume
        m_res = find_method_in_hierarchy(DialogsActivityClass, "onResume")
        if m_res:
            try:
                self.hook_method(m_res, DialogsResumeHook(self))
            except Exception:
                pass

        # 3. createView
        ContextClass = find_class("android.content.Context")
        if ContextClass:
            m_cv = find_method_in_hierarchy(DialogsActivityClass, "createView", ContextClass)
            if m_cv:
                try:
                    self.hook_method(m_cv, DialogsCreateViewHook(self))
                except Exception:
                    pass

    def apply_fullscreen_overlay(self, fragment: Any, is_enabled: bool, root_view: Any = None):
        """
        Перекрывает весь список чатов сплошным минималистичным экраном фокуса.
        """
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

                # Если оверлей уже создан — просто поднимаем его наверх
                if overlay:
                    overlay.setVisibility(View.VISIBLE)
                    overlay.bringToFront()
                    return

                # Создаем полноэкранный непрозрачный щит
                context = rv.getContext()
                overlay = FrameLayout(context)
                overlay.setTag(OVERLAY_TAG)
                overlay.setClickable(True)

                # Цвет фона (темный или светлый по теме)
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

                # Центральный блок с поиском
                center = LinearLayout(context)
                center.setOrientation(LinearLayout.VERTICAL)
                center.setGravity(Gravity.CENTER)
                center.setPadding(40, 40, 40, 40)

                # Заголовок
                title = TextView(context)
                title.setText("🎯 Focus Mode")
                title.setTextSize(26)
                title.setGravity(Gravity.CENTER)
                title.setTextColor(title_color)
                center.addView(title)

                # Подзаголовок
                sub = TextView(context)
                sub.setText("Все чаты и каналы скрыты.\nИспользуйте поиск, чтобы открыть нужный диалог.")
                sub.setTextSize(14)
                sub.setGravity(Gravity.CENTER)
                sub.setPadding(0, 20, 0, 40)
                sub.setTextColor(sub_color)
                center.addView(sub)

                # Кнопка поиска
                btn = TextView(context)
                btn.setText("🔍  Найти чат или бота")
                btn.setTextSize(16)
                btn.setGravity(Gravity.CENTER)
                btn.setPadding(40, 24, 40, 24)
                btn.setBackgroundColor(Color.parseColor("#3B82F6"))
                btn.setTextColor(Color.WHITE)

                def _open_search(v):
                    try:
                        search_item = get_private_field(fragment, "searchItem")
                        if search_item:
                            search_item.openSearch(True)
                    except Exception as err:
                        show_toast(f"Поиск: {err}")

                btn.setOnClickListener(OnClickListener(_open_search))
                center.addView(btn)

                # Добавляем в оверлей и поверх fragmentView
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
                subtext="AyuGram Focus v0.1.5\nПерекрывает шумный экран и оставляет только поиск.",
            ),
        ]
