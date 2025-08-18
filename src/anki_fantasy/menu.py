import math
import aqt
from aqt.qt import *
from aqt.qt import (
    QMenu,
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QColor,
    QPixmap,
    QTableWidgetItem,
    QTableWidget,
    QSize,
    QTableView,
    QIcon,
    QLabel,
    QGraphicsOpacityEffect,
    QScrollArea,
    QWidget,
    QGroupBox,
    QAbstractTableModel,
    QModelIndex,
    QAbstractScrollArea,
    QSortFilterProxyModel,
    QLineEdit,
    QVariant,
    QSizePolicy,
    pyqtSlot
)

from aqt import mw
from pathlib import Path
from functools import lru_cache

from aqt import QMenu, mw
from .libaddon.platform import PATH_THIS_ADDON

import functools

DEBUG_MODE = True
from .gui.notification import Notification

from .rewards import get_alphabetized_recipes_by_level, get_recipes_by_level, get_key_recipes_by_level, get_key_items_by_level_and_specialty, RECIPES

top_menu = None


def show_tooltip(text):
    html = f"""\
    <table cellpadding=10>
    <tr>
    <td valign="middle">
        <center><b>{text}</b></center>
    </td>
    </tr>
    </table>"""

    notification = Notification(
        html, parent=mw.app.activeWindow(), progress_manager=mw.progress
    )

    notification.show()

open_dialogs = {}

def show_dialog(parent, rewards_repo, dialog_name):
    if dialog_name in open_dialogs and open_dialogs[dialog_name].isVisible():
        open_dialogs[dialog_name].raise_()
        open_dialogs[dialog_name].activateWindow()
        return
    
    if dialog_name == "inventory":
        dialog = InventoryDialog(
            parent,
            rewards_repo=rewards_repo,
        )
    elif dialog_name == "crafting":
        dialog = CraftingDialog(
            parent,
            rewards_repo=rewards_repo,
        )
    elif dialog_name == "progress":
        dialog = ProgressDialog(
            parent,
            rewards_repo=rewards_repo,
        )
    else:
        return
    
    open_dialogs[dialog_name] = dialog
    dialog.show()
        # if hasattr(dialog, "exec_"):
        #     dialog.exec_()
        # else:
        #     dialog.exec()

def get_rgb_from_hex(code):
    code_hex = code.replace("#", "")
    rgb = tuple(int(code_hex[i : i + 2], 16) for i in (0, 2, 4))
    return QColor.fromRgb(rgb[0], rgb[1], rgb[2])


class InventoryTableModel(QAbstractTableModel):
    def __init__(self, data, parent=None):
        super().__init__(parent)

        self.horizontalHeaders = [''] * 3

        self.setHeaderData(0, Qt.Orientation.Horizontal, "Item Image")
        self.setHeaderData(1, Qt.Orientation.Horizontal, "Item Name")
        self.setHeaderData(2, Qt.Orientation.Horizontal, "Count")

        self._data = data

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def setHeaderData(self, section, orientation, data, role=Qt.ItemDataRole.EditRole):
        if orientation == Qt.Orientation.Horizontal and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            try:
                self.horizontalHeaders[section] = data
                return True
            except:
                return False
        return super().setHeaderData(section, orientation, data, role)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            try:
                return self.horizontalHeaders[section]
            except:
                pass
        return super().headerData(section, orientation, role)


    def data(self, index, role=Qt.ItemDataRole.DisplayRole):

        if not index.isValid():
            return QVariant()

        if role == Qt.ItemDataRole.DecorationRole:
            if index.column() == 0:
                image_path = self._data[index.row()][index.column()]
                pixmap = QPixmap(image_path)
                return pixmap
            else:
                return QVariant()

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() != 0:
                return self._data[index.row()][index.column()]

        return QVariant()


class InventoryDialog(QDialog):

    def __init__(self, parent, rewards_repo):
        super().__init__(parent)

        self.table = QTableView()

        # Set up Data

        self._rewards_repo = rewards_repo
        inventory = rewards_repo.retrieve_inventory()

        data = []

        for i, (item_name, image_path, count) in enumerate(inventory):

            image_path = Path(PATH_THIS_ADDON) / image_path

            data.append([str(image_path), item_name, count])

        self.model = InventoryTableModel(data)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterKeyColumn(1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)


        self.proxy_model.sort(1, Qt.SortOrder.AscendingOrder)

        self.table.setModel(self.proxy_model)
        self.table.resizeRowsToContents()
        self.table.resizeColumnsToContents()
        self.searchbar = QLineEdit()

        self.searchbar.textChanged.connect(self.proxy_model.setFilterFixedString)
        self.searchbar.textChanged.connect(self.table.resizeRowsToContents)
        self.searchbar.textChanged.connect(self.table.resizeColumnsToContents)

        layout = QVBoxLayout()
        layout.addWidget(self.searchbar)
        layout.addWidget(self.table)

        self.setWindowTitle("Inventory")
        self.setLayout(layout)
        self.resize(1000, 1000)


class ProgressDialog(QDialog):
    def __init__(self, parent, rewards_repo):
        super().__init__(parent)

        self.rewards_repo = rewards_repo
        self.parent = parent

        current_crafting_level = self.rewards_repo.get_crafting_level()
        self.current_crafting_level_label = QLabel(self)
        self.current_crafting_level_label.setText(f"Current crafting level: {current_crafting_level}")

        self.ready_label = QLabel(self)
        if self.ready_for_next_level(current_crafting_level):
            self.ready_label.setText(f"Ready for next level! Click here!")
            self.next_level_button = QPushButton()
            self.next_level_button.setText("Level up!")
            self.next_level_button.clicked.connect(self.next_level_button_clicked)
        else:
            self.ready_label.setText(f"I'm not ready for the next level yet!")

        self.column_count = 7

        self.alchemist_label = QLabel(self)
        self.alchemist_label.setText(f"Alchemist")

        alchemist_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Alchemist')
        alchemist_row_count = math.ceil(len(alchemist_key_items) / self.column_count)

        self.armorer_label = QLabel(self)
        self.armorer_label.setText(f"Armorer")

        armorer_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Armorer')
        armorer_row_count = math.ceil(len(armorer_key_items) / self.column_count)

        self.blacksmith_label = QLabel(self)
        self.blacksmith_label.setText(f"Blacksmith")

        blacksmith_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Blacksmith')
        blacksmith_row_count = math.ceil(len(blacksmith_key_items) / self.column_count)

        self.carpenter_label = QLabel(self)
        self.carpenter_label.setText(f"Carpenter")

        carpenter_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Carpenter')
        carpenter_row_count = math.ceil(len(carpenter_key_items) / self.column_count)

        self.culinarian_label = QLabel(self)
        self.culinarian_label.setText(f"Culinarian")

        culinarian_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Culinarian')
        culinarian_row_count = math.ceil(len(culinarian_key_items) / self.column_count)

        self.goldsmith_label = QLabel(self)
        self.goldsmith_label.setText(f"Goldsmith")

        goldsmith_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Goldsmith')
        goldsmith_row_count = math.ceil(len(goldsmith_key_items) / self.column_count)

        self.leatherworker_label = QLabel(self)
        self.leatherworker_label.setText(f"Leatherworker")

        leatherworker_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Leatherworker')
        leatherworker_row_count = math.ceil(len(leatherworker_key_items) / self.column_count)

        self.weaver_label = QLabel(self)
        self.weaver_label.setText(f"Weaver")

        weaver_key_items = get_key_items_by_level_and_specialty(current_crafting_level, 'Weaver')
        weaver_row_count = math.ceil(len(weaver_key_items) / self.column_count)

        alchemist_label_row = 3
        alchemist_initial_row = alchemist_label_row + 1
        armorer_label_row = alchemist_initial_row + alchemist_row_count + 1
        armorer_initial_row = armorer_label_row + 1
        blacksmith_label_row = armorer_initial_row + armorer_row_count + 1
        blacksmith_initial_row = blacksmith_label_row + 1
        carpenter_label_row = blacksmith_initial_row + blacksmith_row_count + 1
        carpenter_initial_row = carpenter_label_row + 1
        culinarian_label_row = carpenter_initial_row + carpenter_row_count + 1
        culinarian_initial_row = culinarian_label_row + 1
        goldsmith_label_row = culinarian_initial_row + culinarian_row_count + 1
        goldsmith_initial_row = goldsmith_label_row + 1
        leatherworker_label_row = goldsmith_initial_row + goldsmith_row_count + 1
        leatherworker_initial_row = leatherworker_label_row + 1
        weaver_label_row = leatherworker_initial_row + leatherworker_row_count + 1
        weaver_initial_row = weaver_label_row + 1

        groupBox = QGroupBox()
        self.grid_layout = QGridLayout(parent)
        self.grid_layout.addWidget(self.current_crafting_level_label, 0, 0, 1, 5)
        self.grid_layout.addWidget(self.ready_label, 1, 0, 1, 5)
        if self.ready_for_next_level(current_crafting_level):
            self.grid_layout.addWidget(self.next_level_button, 1, 3, 1, 3)
        self.grid_layout.addWidget(self.alchemist_label, alchemist_label_row, 0, 1, 2)
        self.grid_layout.addWidget(self.armorer_label, armorer_label_row, 0, 1, 2)
        self.grid_layout.addWidget(self.blacksmith_label, blacksmith_label_row, 0, 1, 2)
        self.grid_layout.addWidget(self.carpenter_label, carpenter_label_row, 0, 1, 2)
        self.grid_layout.addWidget(self.culinarian_label, culinarian_label_row, 0, 1, 2)
        self.grid_layout.addWidget(self.goldsmith_label, goldsmith_label_row, 0, 1, 2)
        self.grid_layout.addWidget(self.leatherworker_label, leatherworker_label_row, 0, 1, 2)
        self.grid_layout.addWidget(self.weaver_label, weaver_label_row, 0, 1, 2)

        self.populate_grid(alchemist_initial_row, alchemist_key_items)
        self.populate_grid(armorer_initial_row, armorer_key_items)
        self.populate_grid(blacksmith_initial_row, blacksmith_key_items)
        self.populate_grid(carpenter_initial_row, carpenter_key_items)
        self.populate_grid(culinarian_initial_row, culinarian_key_items)
        self.populate_grid(goldsmith_initial_row, goldsmith_key_items)
        self.populate_grid(leatherworker_initial_row, leatherworker_key_items)
        self.populate_grid(weaver_initial_row, weaver_key_items)

        groupBox.setLayout(self.grid_layout)

        scroll = QScrollArea()
        scroll.setWidget(groupBox)
        scroll.setWidgetResizable(True)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

        self.show()
        self.resize(1000, 1000)

    def populate_grid(self, specialty_initial_row, specialty_key_items):
        row_counter = specialty_initial_row
        column_counter = 0
        for recipe in specialty_key_items:
            item_image = QLabel()
            item_image.setPixmap(QPixmap(str(Path(PATH_THIS_ADDON) / recipe["image_path"])))
            item_image.setToolTip(recipe["item_name"])
            if self.rewards_repo.count_item(recipe["item_name"]) < 1:
                opacity_effect = QGraphicsOpacityEffect()
                opacity_effect.setOpacity(0.3)
                item_image.setGraphicsEffect(opacity_effect)
            self.grid_layout.addWidget(item_image, row_counter, column_counter, 1, 1)
            column_counter += 1
            if column_counter == self.column_count:
                row_counter += 1
                column_counter = 0

    def ready_for_next_level(self, current_crafting_level):
        current_level_key_recipes = get_key_recipes_by_level(current_crafting_level)
        all_complete_bool = True
        for recipe in current_level_key_recipes:
            if self.rewards_repo.count_item(recipe["item_name"]) < 1:
                all_complete_bool = all_complete_bool and False
        return all_complete_bool

    @pyqtSlot()
    def next_level_button_clicked(self):
        button = self.sender()
        if button:
            self.rewards_repo.update_crafting_level()
            self.close()
            show_dialog(self.parent, self.rewards_repo, dialo_nameg="progress")

class CraftingDialog(QDialog):
    def __init__(self, parent, rewards_repo):
        super().__init__(parent)

        self.rewards_repo = rewards_repo
        self.parent = parent

        self.crafting_level = self.rewards_repo.get_crafting_level()
        self.current_recipes = get_alphabetized_recipes_by_level(self.crafting_level)
        self.ingredient_to_rows = {}

        for i, recipe in enumerate(self.current_recipes):
            for ingredient in recipe["ingredients"]:
                self.ingredient_to_rows.setdefault(ingredient, set()).add(i)

        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.table.setGeometry(100, 60, 1200, 1000)
        self.table.setRowCount(len(self.current_recipes))
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Key Item",
                "Recipe Image",
                "Recipe Name",
                "Ingredients",
                "Number Owned",
                "Craftable",
                "Missing",
                "Craft?",
            ]
        )
        self.table.setIconSize(QSize(72, 72))

        self.populate_crafting_table()

        self.table.resizeRowsToContents()
        self.table.resizeColumnsToContents()

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWindowTitle("Recipes")
        self.setLayout(layout)
        self.resize(1000, 1000)

    def populate_crafting_table(self):
        for i, recipe in enumerate(self.current_recipes):
            image_path = Path(PATH_THIS_ADDON) / recipe["image_path"]
            is_key_item = False

            if recipe["key_item"][self.crafting_level]:
                key_item = QTableWidgetItem(f"\U0001F31F")
                is_key_item = True
            else:
                key_item = QTableWidgetItem("")

            item_image = QTableWidgetItem()
            item_image.setIcon(QIcon(QPixmap(str(image_path))))

            item_name = QTableWidgetItem(recipe["item_name"])
            ingredients_string = QTableWidgetItem(self.craft_ingredients_string(recipe))
            number_owned = QTableWidgetItem(
                str(self.rewards_repo.count_item(recipe["item_name"]))
            )

            if is_key_item and self.rewards_repo.count_item(recipe["item_name"]) >= 1:
                key_item.setBackground(get_rgb_from_hex("#009933"))

            missing_string = QTableWidgetItem(self.rewards_repo.missing_ingredients(recipe))

            if not self.is_craftable(self.rewards_repo, recipe):
                craftable_cell = QTableWidgetItem("No")
                craftable_cell.setBackground(get_rgb_from_hex("#FF0000"))
                self.table.removeCellWidget(i, 7)
            else:
                craftable_cell = QTableWidgetItem("Yes")
                craftable_cell.setBackground(get_rgb_from_hex("#009933"))
                craft_button = QPushButton()
                craft_button.setText("Craft!")
                craft_button.clicked.connect(self.button_clicked)
                self.table.setCellWidget(i, 7, craft_button)

            self.table.setItem(i, 0, key_item)
            self.table.setItem(i, 1, item_image)
            self.table.setItem(i, 2, item_name)
            self.table.setItem(i, 3, ingredients_string)
            self.table.setItem(i, 4, number_owned)
            self.table.setItem(i, 5, craftable_cell)
            self.table.setItem(i, 6, missing_string)


    def craft_ingredients_string(self, recipe):
        ingredients_string = ""
        for ingredient, amount in recipe["ingredients"].items():
            ingredients_string += f"{amount} {ingredient} \n"
        return ingredients_string

    def is_craftable(self, rewards_repo, recipe):
        craftable = True
        for ingredient, amount in recipe["ingredients"].items():
            if rewards_repo.count_item(ingredient) >= amount:
                craftable = craftable and True
            else:
                craftable = craftable and False

        return craftable

    @pyqtSlot()
    def button_clicked(self):
        button = self.sender()
        if button:
            row = self.table.indexAt(button.pos()).row()
            recipe = self.current_recipes[row]
            crafted_item_name = recipe["item_name"]

            # Craft item
            item = self.table.item(row, 2).text()
            self.rewards_repo.craft_item(self.search_recipes(item))

            # Update initial item's row
            self.update_row(row)

            # Update rows of other items that use that ingredient or that have that crafted item as an ingredient
            # (to avoid repopulating the whole table every time, which is overkill)

            affected_ingredients = list(recipe["ingredients"].keys())
            self.update_rows_by_item_names(affected_ingredients)

            affected_rows = self.get_recipe_rows_using_ingredient(crafted_item_name)
            for r in affected_rows:
                if r != row:
                    self.update_row(r)

    def search_recipes(self, search_term):
        return next(filter(lambda item: item["item_name"] == search_term, RECIPES))
    
    def update_rows_by_item_names(self, item_names):
        updated = set()
        for name in item_names:
            for row in self.ingredient_to_rows.get(name, []):
                if row not in updated:
                    self.update_row(row)
                    updated.add(row)
        # for i, recipe in enumerate(self.current_recipes):
        #     for ingredient in item_names:
        #         if ingredient in recipe["ingredients"]:
        #             self.update_row(i)
        #             break

    def get_recipe_rows_using_ingredient(self, ingredient_name):
        rows = []
        for i, recipe in enumerate(self.current_recipes):
            if ingredient_name in recipe["ingredients"]:
                rows.append(i)
        return rows

    def update_row(self, row_index):
        recipe = self.current_recipes[row_index]
        image_path = Path(PATH_THIS_ADDON) / recipe["image_path"]
        is_key_item = recipe["key_item"][self.crafting_level]

        key_item = QTableWidgetItem("\U0001F31F" if is_key_item else "")
        item_image = QTableWidgetItem()
        item_image.setIcon(QIcon(QPixmap(str(image_path)).scaled(72, 72)))
                           
        item_name = QTableWidgetItem(recipe["item_name"])
        ingredients_string = QTableWidgetItem(self.craft_ingredients_string(recipe))
        number_owned = QTableWidgetItem(str(self.rewards_repo.count_item(recipe["item_name"])))

        if is_key_item and self.rewards_repo.count_item(recipe["item_name"]) >= 1:
            key_item.setBackground(get_rgb_from_hex("#009933"))

        missing_string = QTableWidgetItem(self.rewards_repo.missing_ingredients(recipe))

        if not self.is_craftable(self.rewards_repo, recipe):
            craftable_cell = QTableWidgetItem("No")
            craftable_cell.setBackground(get_rgb_from_hex("#FF0000"))
            self.table.removeCellWidget(row_index, 7)
        else:
            craftable_cell = QTableWidgetItem("Yes")
            craftable_cell.setBackground(get_rgb_from_hex("#009933"))
            craft_button = QPushButton("Craft!")
            craft_button.clicked.connect(self.button_clicked)
            self.table.setCellWidget(row_index, 7, craft_button)

        self.table.setItem(row_index, 0, key_item)
        self.table.setItem(row_index, 1, item_image)
        self.table.setItem(row_index, 2, item_name)
        self.table.setItem(row_index, 3, ingredients_string)
        self.table.setItem(row_index, 4, number_owned)
        self.table.setItem(row_index, 5, craftable_cell)
        self.table.setItem(row_index, 6, missing_string)


def connect_menu(main_window, profile_controller):
    global top_menu
    top_menu = QMenu("&AnkiFantasy", main_window)

    inventory_action = top_menu.addAction("&Inventory")
    inventory_action.triggered.connect(
        lambda: show_dialog(
            main_window, profile_controller.get_rewards_repo(), dialog_name="inventory"
        )
    )

    anki_fantasy_action = top_menu.addAction("&Craft")
    anki_fantasy_action.triggered.connect(
        lambda: show_dialog(
            main_window, profile_controller.get_rewards_repo(), dialog_name="crafting"
        )
    )

    progress_action = top_menu.addAction("&Crafting Progress")
    progress_action.triggered.connect(
        lambda: show_dialog(
            main_window, profile_controller.get_rewards_repo(), dialog_name="progress"
        )
    )

    main_window.form.menubar.addMenu(top_menu)
