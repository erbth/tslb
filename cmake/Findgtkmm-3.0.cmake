# - Try to find gtkmm-3.0
# Once done this will define
#  GTKMM_3_0_FOUND - System has gtkmm-3.0
#  GTKMM_3_0_INCLUDE_DIRS - The gtkmm-3.0 include directories
#  GTKMM_3_0_LIBRARIES - The libraries needed to use gtkmm-3.0

find_package (PkgConfig)

pkg_check_modules (PKG_GTKMM_3_0 gtkmm-3.0)

include (FindPackageHandleStandardArgs)
# Handle the QUIETLY and REQUIRED arguments and set GTKMM_3_0_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args (gtkmm-3.0 DEFAULT_MSG
	PKG_GTKMM_3_0_LIBRARIES PKG_GTKMM_3_0_INCLUDE_DIRS)

mark_as_advanced (PKG_GTKMM_3_0_INCLUDE_DIRS PKG_GTKMM_3_0_LIBRARIES PKG_GTKMM_LIBRARY_DIRS)

set(GTKMM_3_0_LIBRARIES ${PKG_GTKMM_3_0_LIBRARIES})
set(GTKMM_3_0_INCLUDE_DIRS ${PKG_GTKMM_3_0_INCLUDE_DIRS})
