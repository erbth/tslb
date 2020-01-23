# - Try to find RapidJSON
# Once done this will define
#  RAPID_JSON_FOUND - System has RapidJSON
#  RAPID_JSON_INCLUDE_DIRS - The RapidJSON include directories
#  RAPID_JSON_LIBRARIES - The libraries needed to use RapidJSON

find_package (PkgConfig)

pkg_check_modules (PKG_RAPID_JSON RapidJSON)

include (FindPackageHandleStandardArgs)

# Handle the QUIETLY and REQUIRED arguments and set RAPID_JSON_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args (RapidJSON DEFAULT_MSG)

mark_as_advanced (PKG_RAPID_JSON_INCLUDE_DIRS PKG_RAPID_JSON_LIBRARIES PKG_GTKMM_LIBRARY_DIRS)

set(RAPID_JSON_LIBRARIES ${PKG_RAPID_JSON_LIBRARIES})
set(RAPID_JSON_INCLUDE_DIRS ${PKG_RAPID_JSON_INCLUDE_DIRS})
