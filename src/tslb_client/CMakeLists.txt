cmake_minimum_required(VERSION 3.1)

add_executable(tslb_client
	tslb_client.cpp
	ConnectingWindow.cpp
	BuildClusterWindow.cpp
	ClientApplication.cpp
	BuildClusterProxy.cpp
	BuildNodeProxy.cpp

	yamb_node_helpers.cpp
	Message.cpp)

target_link_libraries (tslb_client ${GTKMM_3_0_LIBRARIES} Threads::Threads ${LEGACY_WIDGETS_FOR_GTK_1_0_LIBRARIES} ${YAMB_NODE_PP_LIBRARIES} ${RAPID_JSON_LIBRARIES})
target_include_directories (tslb_client PRIVATE ${GTKMM_3_0_INCLUDE_DIRS} ${LEGACY_WIDGETS_FOR_GTK_1_0_INCLUDE_DIRS} ${YAMB_NODE_PP_INCLUDE_DIRS} ${RAPID_JSON_CFLAGS})
