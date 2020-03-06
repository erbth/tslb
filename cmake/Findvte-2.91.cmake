# - Try to find vte-2.91
# Once done this will define
#  VTE_2_91_FOUND - System has vte-2.91
#  VTE_2_91_INCLUDE_DIRS - The vte-2.91 include directories
#  VTE_2_91_LIBRARIES - The libraries needed to use vte-2.91

find_package (PkgConfig)

pkg_check_modules (PKG_VTE_2_91 vte-2.91)

include (FindPackageHandleStandardArgs)
# Handle the QUIETLY and REQUIRED arguments and set VTE_2_91_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args (vte-2.91 DEFAULT_MSG
	PKG_VTE_2_91_LIBRARIES PKG_VTE_2_91_INCLUDE_DIRS)

mark_as_advanced (PKG_VTE_2_91_INCLUDE_DIRS PKG_VTE_2_91_LIBRARIES PKG_VTE_2_91_LIBRARY_DIRS)

set(VTE_2_91_LIBRARIES ${PKG_VTE_2_91_LIBRARIES})
set(VTE_2_91_INCLUDE_DIRS ${PKG_VTE_2_91_INCLUDE_DIRS})
