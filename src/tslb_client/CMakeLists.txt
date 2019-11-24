cmake_minimum_required(VERSION 3.1)

add_executable(tslb_client
	tslb_client.cpp
	ConnectDialog.cpp)

target_link_libraries (tslb_client ${GTKMM_3_0_LIBRARIES} Threads::Threads ${LWG_LIBRARIES})
target_include_directories (tslb_client PRIVATE ${GTKMM_3_0_INCLUDE_DIRS} ${LWG_INCLUDE_DIRS})
