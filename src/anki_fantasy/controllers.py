"""
Anki Killstreaks add-on

Copyright: (c) jac241 2019-2020 <https://github.com/jac241>
License: GNU AGPLv3 or later <https://www.gnu.org/licenses/agpl.html>

The goal of these controller classes is to have these be the only objects that
hold state in the add-on. The other classes ideally should be immutable.
This pattern has worked alright so far for this simple application.
"""
import sqlite3
from functools import wraps, partial
from os.path import join, dirname
from pathlib import Path

from ._vendor.yoyo import get_backend
from ._vendor.yoyo import read_migrations
from ._vendor.yoyo.exceptions import LockTimeout

from aqt import mw
from .libaddon.platform import PATH_THIS_ADDON
from .gui.notification import Notification
from .rewards import random_reward


# Hack that we need because profileLoaded hook called after DeckBrowser shown
def ensure_loaded(f):
    @wraps(f)
    def new_method(self, *args, **kwargs):
        if not self.is_loaded:
            self.load_profile()
        return f(self, *args, **kwargs)

    return new_method

class RewardsRepository:
    def __init__(self, pf):
        self.profile_folder = pf
        self.db_path = Path(pf) / "anki_fantasy.db"
        self.migrations_path = Path(PATH_THIS_ADDON) / "migrations"
        self.db_uri = f"sqlite:///{self.db_path}"

    def __str__(self):
        return str(self.db_path)

    def connect_to_db(self):
        return sqlite3.connect(str(self.db_path), isolation_level=None)

    def migrate_db(self):
        backend = get_backend(self.db_uri)
        migrations = read_migrations(str(self.migrations_path))

        try:
            with backend.lock():
                backend.apply_migrations(backend.to_apply(migrations))
        except LockTimeout as e:
            backend.break_lock()

    def create_initial_level(self):
        con = sqlite3.connect(str(self.db_path))
        cur = con.cursor()
        res = cur.execute("SELECT level FROM craftinglevel WHERE id = 1")
        if not res.fetchone():
            cur.execute("INSERT INTO craftinglevel(id, level) VALUES (1, 'set_1')")
            con.commit()

    def get_crafting_level(self):
        con = sqlite3.connect(str(self.db_path))
        cur = con.cursor()
        res = cur.execute("SELECT level FROM craftinglevel WHERE id = 1")
        return res.fetchone()[0]

    def update_crafting_level(self):
        current_level = self.get_crafting_level()
        current_level_int = int(current_level[-1])
        next_level_int = current_level_int + 1
        next_level_str = "set_{0}".format(next_level_int)

        con = sqlite3.connect(str(self.db_path))
        cur = con.cursor()
        cur.execute("UPDATE craftinglevel SET level = ? WHERE id = 1", [next_level_str])
        con.commit()

    def create(self, reward):
        con = sqlite3.connect(str(self.db_path))
        cur = con.cursor()
        cur.execute("INSERT INTO rewards(item_name, image_path) VALUES (?, ?)", (reward["item_name"], reward["image_path"]))
        con.commit()

    def retrieve_inventory(self):
        con = sqlite3.connect(str(self.db_path))
        cur = con.cursor()
        cur.execute("SELECT item_name, image_path, count(*) FROM rewards GROUP BY item_name")
        return cur.fetchall()

    def count_item(self, item_name):
        con = sqlite3.connect(str(self.db_path))
        cur = con.cursor()
        res = cur.execute("SELECT count(*) FROM rewards WHERE item_name = ?", [item_name])
        return res.fetchone()[0]

    def craft_item(self, recipe):
        # Add new item
        con = sqlite3.connect(str(self.db_path))
        cur = con.cursor()
        cur.execute("INSERT INTO rewards(item_name, image_path) VALUES (?, ?)", (recipe["item_name"], recipe["image_path"]))
        con.commit()

        # Delete each recipe ingredient
        for ingredient, amount in recipe["ingredients"].items():
            con2 = sqlite3.connect(str(self.db_path))
            cur2 = con2.cursor()
            cur2.execute("DELETE FROM rewards WHERE id in (select id FROM rewards WHERE item_name = ? LIMIT ?)", (ingredient, amount))
            con2.commit()

    def missing_ingredients(self, recipe):
        missing_ingredients = ""
        for ingredient, amount in recipe["ingredients"].items():
            owned_amount = self.count_item(ingredient)
            if owned_amount < amount:
                amount_needed = amount - owned_amount
                missing_ingredients += f"{amount_needed} {ingredient}\n"

        return missing_ingredients


class ProfileController:
    """
    Class that contains the parts of the application that need to change
    when the profile changes. This class (plus potentially others like it)
    will be bound to all of the Anki classes. Whenever a user changes profiles,
    the state contained in this class will be mutated to reflect the new
    profile. This ensures that the hooks and method wrapping around Anki objects
    only occurs once. This is necessary because their is no way to unwrap methods or
    unbind hook handlers.

    Is placed in front of accessors to let you know they rely on profile
    dependent state that changes when you switch profiles.
    """

    def __init__(self, _get_profile_folder_path):
        self.is_loaded = False
        self._get_profile_folder_path = _get_profile_folder_path

    def load_profile(self):
        self.profile_folder = self._get_profile_folder_path()
        self.rewards_repo = RewardsRepository(pf=self.profile_folder)
        self.rewards_repo.migrate_db()
        self.rewards_repo.create_initial_level()
        self.reviewing_controller = ReviewingController(rewards_repo=self.rewards_repo)
        self.is_loaded = True

    def unload_profile(self):
        self.is_loaded = False

    @ensure_loaded
    def get_rewards_repo(self):
        return self.rewards_repo

    @ensure_loaded
    def get_reviewing_controller(self):
        return self.reviewing_controller



def call_method_on_object_from_factory_function(
    method,
    factory_function,
):
    """
    This function takes a factory method, and then calls the passed method
    on the created object with the passed arguments. This makes it
    possible to keep delegation to the reviewing controller
    out of the ProfileController, even though in main we need to make sure that
    we are calling the current instance of the ReviewingController, which
    changes whenever you switch profiles, or game types, etc.
    """

    def call_method(*args, **kwargs):
        return getattr(factory_function(), method)(*args, **kwargs)

    return call_method

class ReviewingController:
    def __init__(self, rewards_repo):
        self.rewards_repo = rewards_repo
        self.streak = 0
        self.crafting_level = self.rewards_repo.get_crafting_level()

    def on_answer(self, ease):
        if ease > 1:
            self.streak += 1

            reward = random_reward(self.streak, self.crafting_level)
            if reward:
                self.rewards_repo.create(reward)
                self.show_tooltip(reward)

        else:
            self.streak = 0

    def show_tooltip(self, reward):
        image_path = Path(PATH_THIS_ADDON) / reward["image_path"]

        html = f"""\
        <table cellpadding=10>
        <tr>
        <td valign="middle">
            <center><b>You got 1 <img src="{image_path}"> {reward["item_name"]}!</b></center>
        </td>
        </tr>
        </table>"""

        notification = Notification(
            html,
            parent=mw.app.activeWindow(),
            progress_manager=mw.progress
        )

        notification.show()

def build_on_answer_wrapper(reviewer, ease, on_answer):
    on_answer(ease=ease)