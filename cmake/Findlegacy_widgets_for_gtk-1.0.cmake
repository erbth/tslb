# - Try to find legacy_widgets_for_gtk-1.0
# Once done this will define
#  LEGACY_WIDGETS_FOR_GTK_1_0_FOUND - System has legacy_widgets_for_gtk-1.0
#  LEGACY_WIDGETS_FOR_GTK_1_0_INCLUDE_DIRS - The legacy_widgets_for_gtk-1.0 include directories
#  LEGACY_WIDGETS_FOR_GTK_1_0_LIBRARIES - The libraries needed to use legacy_widgets_for_gtk-1.0

find_package (PkgConfig)

pkg_check_modules (PKG_LEGACY_WIDGETS_FOR_GTK_1_0 legacy_widgets_for_gtk-1.0)

include (FindPackageHandleStandardArgs)
# Handle the QUIETLY and REQUIRED arguments and set LEGACY_WIDGETS_FOR_GTK_1_0_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args (legacy_widgets_for_gtk-1.0 DEFAULT_MSG
	PKG_LEGACY_WIDGETS_FOR_GTK_1_0_LIBRARIES PKG_LEGACY_WIDGETS_FOR_GTK_1_0_INCLUDE_DIRS)

mark_as_advanced (PKG_LEGACY_WIDGETS_FOR_GTK_1_0_INCLUDE_DIRS PKG_LEGACY_WIDGETS_FOR_GTK_1_0_LIBRARIES PKG_GTKMM_LIBRARY_DIRS)

set(LEGACY_WIDGETS_FOR_GTK_1_0_LIBRARIES ${PKG_LEGACY_WIDGETS_FOR_GTK_1_0_LIBRARIES})
set(LEGACY_WIDGETS_FOR_GTK_1_0_INCLUDE_DIRS ${PKG_LEGACY_WIDGETS_FOR_GTK_1_0_INCLUDE_DIRS})
