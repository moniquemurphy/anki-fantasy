"""
Anki Killstreaks add-on

Copyright: (c) jac241 2019-2020 <https://github.com/jac241>
License: GNU AGPLv3 or later <https://www.gnu.org/licenses/agpl.html>
"""
import sys
import os
import sqlite3
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from .consts import addon_path

sys.path.insert(0, os.path.join(addon_path, "_vendor"))

from yoyo import get_backend, read_migrations
from yoyo.exceptions import LockTimeout

from aqt import mw
from .libaddon.platform import PATH_THIS_ADDON
from .gui.notification import Notification
from .rewards import random_reward, random_rare_reward


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

    @contextmanager
    def _connect(self):
        """Single place where connections are opened. Always closes on exit."""
        con = sqlite3.connect(str(self.db_path))
        try:
            yield con
        finally:
            con.close()

    def migrate_db(self):
        backend = get_backend(self.db_uri)
        migrations = read_migrations(str(self.migrations_path))
        try:
            with backend.lock():
                backend.apply_migrations(backend.to_apply(migrations))
        except LockTimeout:
            backend.break_lock()

    def create_initial_level(self):
        with self._connect() as con:
            cur = con.cursor()
            res = cur.execute("SELECT level FROM craftinglevel WHERE id = 1")
            if not res.fetchone():
                cur.execute(
                    "INSERT INTO craftinglevel(id, level) VALUES (1, 'set_1')"
                )
                con.commit()

    def get_crafting_level(self):
        with self._connect() as con:
            cur = con.cursor()
            res = cur.execute("SELECT level FROM craftinglevel WHERE id = 1")
            row = res.fetchone()
            if not row:
                raise RuntimeError("craftinglevel table has no row with id=1")
            return row[0]

    def update_crafting_level(self):
        current_level = self.get_crafting_level()
        _, _, suffix = current_level.partition("_")
        next_level_str = f"set_{int(suffix) + 1}"
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(
                "UPDATE craftinglevel SET level = ? WHERE id = 1",
                [next_level_str],
            )
            con.commit()

    def create(self, reward):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO rewards(item_name, image_path) VALUES (?, ?)",
                (reward["item_name"], reward["image_path"]),
            )
            con.commit()

    def retrieve_inventory(self):
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(
                "SELECT item_name, image_path, count(*) FROM rewards GROUP BY item_name"
            )
            return cur.fetchall()

    def count_item(self, item_name):
        with self._connect() as con:
            cur = con.cursor()
            res = cur.execute(
                "SELECT count(*) FROM rewards WHERE item_name = ?", [item_name]
            )
            return res.fetchone()[0]

    def craft_item(self, recipe):
        """Add the crafted item and delete each ingredient in one connection."""
        with self._connect() as con:
            cur = con.cursor()
            # Insert the new crafted item
            cur.execute(
                "INSERT INTO rewards(item_name, image_path) VALUES (?, ?)",
                (recipe["item_name"], recipe["image_path"]),
            )
            # Consume ingredients in the same transaction
            for ingredient, amount in recipe["ingredients"].items():
                cur.execute(
                    "DELETE FROM rewards WHERE id IN "
                    "(SELECT id FROM rewards WHERE item_name = ? LIMIT ?)",
                    (ingredient, amount),
                )
            con.commit()

    def missing_ingredients(self, recipe):
        missing = ""
        for ingredient, amount in recipe["ingredients"].items():
            owned = self.count_item(ingredient)
            if owned < amount:
                missing += f"{amount - owned} {ingredient}\n"
        return missing


class ProfileController:
    def __init__(self, _get_profile_folder_path):
        self.is_loaded = False
        self._get_profile_folder_path = _get_profile_folder_path

    def load_profile(self):
        self.profile_folder = self._get_profile_folder_path()
        self.rewards_repo = RewardsRepository(pf=self.profile_folder)
        self.rewards_repo.migrate_db()
        self.rewards_repo.create_initial_level()
        self.reviewing_controller = ReviewingController(
            rewards_repo=self.rewards_repo
        )
        self.is_loaded = True

    def unload_profile(self):
        self.is_loaded = False

    @ensure_loaded
    def get_rewards_repo(self):
        return self.rewards_repo

    @ensure_loaded
    def get_reviewing_controller(self):
        return self.reviewing_controller


def call_method_on_object_from_factory_function(method, factory_function):
    def call_method(*args, **kwargs):
        return getattr(factory_function(), method)(*args, **kwargs)
    return call_method


class ReviewingController:
    def __init__(self, rewards_repo):
        self.rewards_repo = rewards_repo
        self.rewards_counter = 0
        self.streak = 0
        # Cached; call refresh_crafting_level() if it can change at runtime
        self.crafting_level = self.rewards_repo.get_crafting_level()

    def refresh_crafting_level(self):
        """Call this after update_crafting_level() to keep the cache current."""
        self.crafting_level = self.rewards_repo.get_crafting_level()

    def on_answer(self, ease):
        if ease > 1:
            self.streak += 1
            if self.rewards_counter % 50 == 0:
                reward = random_rare_reward(self.crafting_level)
            else:
                reward = random_reward(self.streak, self.crafting_level)
            if reward:
                self.rewards_repo.create(reward)
                self.rewards_counter += 1
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
        <tr>
        <td valign="middle">
            <center>Rewards today: {self.rewards_counter}</center>
        </td>
        </tr>
        </table>"""

        notification = Notification(
            html,
            parent=mw.app.activeWindow(),
            progress_manager=mw.progress,
        )
        notification.show()


def build_on_answer_wrapper(reviewer, ease, on_answer):
    on_answer(ease=ease)