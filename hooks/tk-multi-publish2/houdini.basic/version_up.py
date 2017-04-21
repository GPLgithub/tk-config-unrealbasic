# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import hou
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class HoudiniVersionUpPlugin(HookBaseClass):
    """
    Plugin for creating the next version of a file.
    """

    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(
            self.disk_location,
            os.pardir,
            "icons",
            "version_up.png"
        )

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Save the file to the next version"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """
        return """
        Detect the version number in the houdini file path and save it to the
        next available version number. The plugin will only be available to
        houdini files where a version number can be detected in the path. The
        plugin will only create the next available version if the new path does
        not already exist.
        """

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["houdini.session"]

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """
        return {}

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        publisher = self.parent
        path = hou.hipFile.path()
        checked = True

        if hou.hipFile.hasUnsavedChanges() or not path:
            # the session has unsaved changes. provide a save button and uncheck
            # the item. the session will need to be saved before validation will
            # succeed.
            self.logger.warn(
                "Unsaved changes in the session",
                extra=self._get_save_as_action()
            )
            checked = False
        else:
            # we have a path and there are no unsaved changes. make sure the
            # path has a version number. we accept it regardless since it can be
            # saved with a different file name while the publisher is open. but
            # we will set it to be unchecked by default if there is no version

            # get the path in a normalized state. no trailing separator,
            # separators are appropriate for current os, no double separators,
            # etc.
            path = sgtk.util.ShotgunPath.normalize(path)
            version_number = publisher.util.get_version_number(path)

            if version_number is None:
                self.logger.warn(
                    "No version number detected in the file name",
                    extra=_get_version_docs_action()
                )
                checked = False

        self.logger.info(
            "Houdini version up plugin accepted the current Houdini session.")

        return {
            "accepted": True,
            "checked": checked,
        }

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """

        publisher = self.parent
        path = hou.hipFile.path()

        if hou.hipFile.hasUnsavedChanges() or not path:
            # the session still requires saving. provide a save button.
            # validation fails since we don't want to save as the next version
            # until the current changes have been saved.
            self.logger.error(
                "Unsaved changes in the session",
                extra=self._get_save_as_action()
            )
            return False
        else:
            # we have a path and there are no unsaved changes. make sure the
            # path has a version number. if not, validation fails

            # get the path in a normalized state. no trailing separator,
            # separators are appropriate for current os, no double separators,
            # etc.
            path = sgtk.util.ShotgunPath.normalize(path)

            version_number = publisher.util.get_version_number(path)

            if version_number is None:
                # still no version number in the file name. a warning was
                # provided in accept(). validation fails
                self.logger.error(
                    "No version number detected in the file name",
                    extra=_get_version_docs_action()
                )
                return False

        next_version_path = publisher.util.get_next_version_path(path)

        # nothing to do if the next version path can't be determined or if it
        # already exists.
        if not next_version_path:
            self.logger.error("Could not determine the next version path.")
            return False
        elif os.path.exists(next_version_path):
            self.logger.error(
                "Next version already exists: %s" % (next_version_path,),
                extra={
                    "action_show_folder": {
                        "path": next_version_path
                    }
                }
            )
            return False

        # insert the path into the properties for use during the publish phase
        item.properties["next_version_path"] = next_version_path

        return True

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        # get the next version path and save the document
        next_version_path = item.properties["next_version_path"]
        hou.hipFile.save(file_name=next_version_path)
        self.logger.info("The Houdini session is now at the next version!")

    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once
        all the publish tasks have completed, and can for example
        be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        pass

    def _get_save_as_action(self):
        """
        Simple helper for returning a log action dict for saving the session
        """

        houdini_engine = self.parent.engine

        return {
            "action_button": {
                "label": "Save",
                "tooltip": "Save the current session",
                "callback": houdini_engine.save_as
            }
        }


def _get_version_docs_action():
    """
    Simple helper for returning a log action to show version docs
    """
    return {
        "action_open_url": {
            "label": "Version Docs",
            "tooltip": "Show docs for version formats",
            "url": "https://support.shotgunsoftware.com/hc/en-us/articles/115000068574-User-Guide-WIP-#What%20happens%20when%20you%20publish"
        }
    }
