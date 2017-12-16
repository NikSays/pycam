from configparser import ConfigParser
import enum
import json

import pycam.Gui.Settings
from pycam.Utils.locations import open_file_context
import pycam.Utils.log


FILE_FILTER_CONFIG = (("Config files", "*.yml"),)

PREFERENCES_DEFAULTS = {
    "unit": "mm",
    "save_project_settings_on_exit": "ask",
    "show_model": True,
    "show_support_preview": True,
    "show_axes": True,
    "show_dimensions": True,
    "show_bounding_box": True,
    "show_toolpath": True,
    "show_tool": False,
    "show_directions": False,
    "show_grid": False,
    "color_background": {"red": 0.0, "green": 0.0, "blue": 0.0, "alpha": 1.0},
    "color_model": {"red": 0.5, "green": 0.5, "blue": 1.0, "alpha": 1.0},
    "color_support_preview": {"red": 0.8, "green": 0.8, "blue": 0.3, "alpha": 1.0},
    "color_bounding_box": {"red": 0.3, "green": 0.3, "blue": 0.3, "alpha": 1.0},
    "color_tool": {"red": 1.0, "green": 0.2, "blue": 0.2, "alpha": 1.0},
    "color_toolpath_cut": {"red": 1.0, "green": 0.5, "blue": 0.5, "alpha": 1.0},
    "color_toolpath_return": {"red": 0.9, "green": 1.0, "blue": 0.1, "alpha": 0.4},
    "color_material": {"red": 1.0, "green": 0.5, "blue": 0.0, "alpha": 1.0},
    "color_grid": {"red": 0.75, "green": 1.0, "blue": 0.7, "alpha": 0.55},
    "view_light": True,
    "view_shadow": True,
    "view_polygon": True,
    "view_perspective": True,
    "tool_progress_max_fps": 30.0,
    "gcode_safety_height": 25.0,
    "gcode_plunge_feedrate": 100.0,
    "gcode_minimum_step_x": 0.0001,
    "gcode_minimum_step_y": 0.0001,
    "gcode_minimum_step_z": 0.0001,
    "gcode_path_mode": 0,
    "gcode_motion_tolerance": 0,
    "gcode_naive_tolerance": 0,
    "gcode_start_stop_spindle": True,
    "gcode_filename_extension": "",
    "gcode_spindle_delay": 3,
    "external_program_inkscape": "",
    "external_program_pstoedit": "",
    "touch_off_on_startup": False,
    "touch_off_on_tool_change": False,
    "touch_off_position_type": "absolute",
    "touch_off_position_x": 0.0,
    "touch_off_position_y": 0.0,
    "touch_off_position_z": 0.0,
    "touch_off_rapid_move": 0.0,
    "touch_off_slow_move": 1.0,
    "touch_off_slow_feedrate": 20,
    "touch_off_height": 0.0,
    "touch_off_pause_execution": False,
}
""" the listed items will be loaded/saved via the preferences file in the
user's home directory on startup/shutdown"""

DEFAULT_PROJECT_SETTINGS = """
models:
        model:
            source:
                    type: file
                    location: samples/Box0.stl
            X-Application:
                pycam-gtk:
                    name: Example 3D Model
                    color: { red: 0.1, green: 0.4, blue: 1.0, alpha: 0.8 }

tools:
        rough:
            tool_id: 1
            shape: flat_bottom
            radius: 3
            feed: 600
            spindle_speed: 1000
            X-Application: { pycam-gtk: { name: Big Tool } }
        fine:
            tool_id: 2
            shape: ball_nose
            radius: 1
            feed: 1200
            spindle_speed: 1000
            X-Application: { pycam-gtk: { name: Small Tool } }

processes:
        process_slicing:
            strategy: slice
            path_pattern: grid
            overlap: 0.10
            step_down: 3.0
            grid_direction: y
            milling_style: ignore
            X-Application: { pycam-gtk: { name: Slice (rough) } }
        process_surfacing:
            strategy: surface
            overlap: 0.80
            step_down: 1.0
            grid_direction: x
            milling_style: ignore
            X-Application: { pycam-gtk: { name: Surface (fine) } }

bounds:
        minimal:
            specification: margins
            lower: [5, 5, 0]
            upper: [5, 5, 1]
            X-Application: { pycam-gtk: { name: minimal } }

tasks:
        rough:
            type: milling
            tool: rough
            process: process_slicing
            bounds: minimal
            collision_models: [ model ]
            X-Application: { pycam-gtk: { name: Quick Removal } }
        fine:
            type: milling
            tool: fine
            process: process_surfacing
            bounds: minimal
            collision_models: [ model ]
            X-Application: { pycam-gtk: { name: Finishing } }
"""

PICKLE_PROTOCOL = 2

log = pycam.Utils.log.get_logger()


class QuestionStatus(enum.Enum):
    YES = "yes"
    NO = "no"
    ASK = "ask"


class BaseUI(object):

    def __init__(self, event_manager):
        self.settings = event_manager
        self.last_project_settings_uri = None

    def reset_preferences(self, widget=None):
        """ reset all preferences to their default values """
        for key, value in PREFERENCES_DEFAULTS.items():
            self.settings.set(key, value)
        # redraw the model due to changed colors, display items ...
        self.settings.emit_event("model-change-after")

    def load_preferences(self):
        """ load all settings (see Preferences window) from a file in the user's home directory """
        config = ConfigParser()
        try:
            with pycam.Gui.Settings.open_preferences_file() as in_file:
                config.read_file(in_file)
        except FileNotFoundError as exc:
            log.info("No preferences file found (%s). Starting with default preferences.", exc)
        except OSError as exc:
            log.error("Failed to read preferences: %s", exc)
            return
        # report any ignored (obsolete) preference keys present in the file
        for item, value in config.items("DEFAULT"):
            if item not in PREFERENCES_DEFAULTS.keys():
                log.warn("Skipping obsolete preference item: %s", str(item))
        for item in PREFERENCES_DEFAULTS:
            if not config.has_option("DEFAULT", item):
                # a new preference setting is missing in the (old) file
                continue
            value_json = config.get("DEFAULT", item)
            try:
                value = json.loads(value_json)
            except ValueError as exc:
                log.warning("Failed to parse configuration setting '%s': %s", item, exc)
                value = PREFERENCES_DEFAULTS[item]
            wanted_type = type(PREFERENCES_DEFAULTS[item])
            if wanted_type is float:
                # int is accepted for floats, too
                wanted_type = (float, int)
            if not isinstance(value, wanted_type):
                log.warning("Falling back to default configuration setting for '%s' due to "
                            "an invalid value type being parsed: %s != %s",
                            item, type(value), wanted_type)
                value = PREFERENCES_DEFAULTS[item]
            self.settings.set(item, value)

    def save_preferences(self):
        """ save all settings (see Preferences window) to a file in the user's home directory """
        config = ConfigParser()
        for item in PREFERENCES_DEFAULTS:
            config.set("DEFAULT", item, json.dumps(self.settings.get(item)))
        try:
            with pycam.Gui.Settings.open_preferences_file(mode="w") as out_file:
                config.write(out_file)
        except OSError as exc:
            log.warn("Failed to write preferences file: %s", exc)

    def restore_undo_state(self, widget=None, event=None):
        history = self.settings.get("history")
        if history and history.get_undo_steps_count() > 0:
            history.restore_previous_state()
        else:
            log.info("No previous undo state available - request ignored")

    def save_startup_project_settings(self):
        self.save_project_settings_to_file(pycam.Gui.Settings.get_project_settings_filename(),
                                           remember_uri=False)

    def load_startup_project_settings(self):
        self.load_project_settings_from_file(pycam.Gui.Settings.get_project_settings_filename(),
                                             remember_uri=False,
                                             default_content=DEFAULT_PROJECT_SETTINGS)

    def save_project_settings_to_file(self, filename, remember_uri=True):
        from pycam.Flow.parser import dump_yaml
        if remember_uri:
            self.last_project_settings_uri = pycam.Utils.URIHandler(filename)
            self.settings.emit_event("notify-file-opened", filename)
        log.info("Storing project settings in file: %s", filename)
        try:
            with open_file_context(filename, "w", True) as out_file:
                dump_yaml(target=out_file)
        except OSError as exc:
            log.error("Failed to store project settings to file '%s': %s", filename, exc)

    def load_project_settings_from_file(self, filename, remember_uri=True, default_content=None):
        from pycam.Flow.parser import parse_yaml
        if remember_uri:
            self.last_project_settings_uri = pycam.Utils.URIHandler(filename)
            self.settings.emit_event("notify-file-opened", filename)
        log.info("Loading project settings from file: %s", filename)
        try:
            with open_file_context(filename, "r", True) as in_file:
                content = in_file.read()
        except OSError as exc:
            if default_content:
                content = default_content
            else:
                log.error("Failed to read project settings file (%s): %s", filename, exc)
                return
        parse_yaml(content, excluded_sections={"toolpaths", "exports"}, reset=True)

    def load_project_settings_dialog(self, filename=None):
        if not filename:
            filename = self.settings.get("get_filename_func")(
                "Loading project settings ...", mode_load=True, type_filter=FILE_FILTER_CONFIG)
            # no filename selected -> no action
            if not filename:
                return
            remember_uri = True
        else:
            remember_uri = False
        self.load_project_settings_from_file(filename, remember_uri=remember_uri)

    def save_project_settings_dialog(self, filename=None):
        if not filename:
            # we open a dialog
            filename = self.settings.get("get_filename_func")(
                "Save project settings to ...", mode_load=False, type_filter=FILE_FILTER_CONFIG,
                filename_templates=(self.last_project_settings_uri, self.last_model_uri))
            # no filename selected -> no action
            if not filename:
                return
            remember_uri = True
        else:
            remember_uri = False
        self.save_project_settings_to_file(filename, remember_uri=remember_uri)
