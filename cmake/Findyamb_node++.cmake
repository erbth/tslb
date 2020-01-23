# - Try to find yamb_node++
# Once done this will define
#  YAMB_NODE_PP_FOUND - System has yamb_node++
#  YAMB_NODE_PP_INCLUDE_DIRS - The yamb_node++ include directories
#  YAMB_NODE_PP_LIBRARIES - The libraries needed to use yamb_node++

find_package (PkgConfig)

pkg_check_modules (PKG_YAMB_NODE_PP yamb_node++)

include (FindPackageHandleStandardArgs)

# Handle the QUIETLY and REQUIRED arguments and set YAMB_NODE_PP_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args (yamb_node++ DEFAULT_MSG PKG_YAMB_NODE_PP_LIBRARIES)

mark_as_advanced (PKG_YAMB_NODE_PP_INCLUDE_DIRS PKG_YAMB_NODE_PP_LIBRARIES PKG_GTKMM_LIBRARY_DIRS)

set(YAMB_NODE_PP_LIBRARIES ${PKG_YAMB_NODE_PP_LIBRARIES})
set(YAMB_NODE_PP_INCLUDE_DIRS ${PKG_YAMB_NODE_PP_INCLUDE_DIRS})
