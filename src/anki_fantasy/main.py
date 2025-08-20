import sys
import os
from functools import partial
from pathlib import Path

from aqt import mw
from anki.hooks import wrap, addHook
from aqt.reviewer import Reviewer
from ._version import __version__  # noqa: F401
from .consts import ADDON, addon_path
from .libaddon.consts import set_addon_properties
from .menu import connect_menu
from .controllers import ProfileController, build_on_answer_wrapper, call_method_on_object_from_factory_function
sys.path.insert(0, os.path.join(addon_path, "_vendor"))

def _get_profile_folder_path(profile_manager=mw.pm):
    folder = profile_manager.profileFolder()
    return Path(folder)

_profile_controller = ProfileController(
    _get_profile_folder_path=_get_profile_folder_path
)

def _wrap_anki_objects(profile_controller):
    """
    profileLoaded hook is fired after the deck browser is shown, so the hooks
    can't be used (like on_profile_loaded). To get around this,
    this decorator decorates any method that uses the profile
    controller to make sure it's loaded first.
    """
    addHook("unloadProfile", profile_controller.unload_profile)

    # Need to make sure we call these methods on the current reviewing controller.
    # Reviewing controller instance changes when profile changes.
    call_method_on_reviewing_controller = partial(
        call_method_on_object_from_factory_function,
        factory_function=profile_controller.get_reviewing_controller,
    )

    # Reviewer._answerCard = wrap(
    #     Reviewer._answerCard,
    #     partial(
    #         build_on_answer_wrapper,
    #         on_answer=call_method_on_reviewing_controller("on_answer"),
    #     ),
    #     "before",
    # )
    
    Reviewer._after_answering = wrap(
        Reviewer._after_answering,
        partial(
            build_on_answer_wrapper,
            on_answer=call_method_on_reviewing_controller("on_answer"),
        ),
        "before",
    )

def setup_main():

    # Import from _vendor folder

    # Addon Properties

    set_addon_properties(ADDON)

    _wrap_anki_objects(_profile_controller)
    connect_menu(main_window=mw, profile_controller=_profile_controller)