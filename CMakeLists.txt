cmake_minimum_required(VERSION 3.1)

list (APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

project("tslb" C CXX)

# Find packages
set (THREADS_PREFER_PTHREAD_FLAG ON)
find_package (Threads REQUIRED)
find_package (gtkmm-3.0 REQUIRED)
find_package (legacy_widgets_for_gtk-1.0 REQUIRED)
find_package (yamb_node++ REQUIRED)
find_package (RapidJSON REQUIRED)

# Set CXXFLAGS
set (CMAKE_CXX_FLAGS "-std=c++17 -Wall -gdwarf-2")
set (CMAKE_CXX_FLAGS_DEBUG "-DDEBUG -Werror")
set (CMAKE_CXX_FLAGS_RELEASE "-O3")

# Set CFLAGS
set (CMAKE_C_FLAGS "-std=gnu11 -Wall -gdwarf-2")
set (CMAKE_C_FLAGS_DEBUG "-DDEBUG -Werror")
set (CMAKE_C_FLAGS_RELEASE "-O3")

include_directories (src)
include_directories (include)

# Add subdirectories
add_subdirectory (src)
