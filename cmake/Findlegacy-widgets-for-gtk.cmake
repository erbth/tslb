# - Try to find libsensors
# Once done this will define
#  LWG_FOUND - System has libsensors
#  LWG_INCLUDE_DIRS - The libsensors include directories
#  LWG_LIBRARIES - The libraries needed to use libsensors

find_path (LWG_INCLUDE_DIR legacy-widgets-for-gtk.h)

find_library (LWG_LIBRARY NAMES legacy_widgets_for_gtk)

include (FindPackageHandleStandardArgs)
# Handle the QUIETLY and REQUIRED arguments and set LWG_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args (lwg DEFAULT_MSG
	LWG_LIBRARY LWG_INCLUDE_DIR)

mark_as_advanced (LWG_INCLUDE_DIR LWG_LIBRARY)

set(LWG_LIBRARIES ${LWG_LIBRARY})
set(LWG_INCLUDE_DIRS ${LWG_INCLUDE_DIR})
