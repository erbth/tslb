cmake_minimum_required(VERSION 3.1)

add_executable(test_base64
	test_base64.cpp
	../base64.c)

target_link_libraries(test_base64 ${Boost_UNIT_TEST_FRAMEWORK_LIBRARY})
add_test(NAME test_base64 COMMAND test_base64)


add_executable(test_utilities
	test_utilities.cpp
	../utilities.cpp)

target_link_libraries(test_utilities ${Boost_UNIT_TEST_FRAMEWORK_LIBRARY})
add_test(NAME test_utilities COMMAND test_utilities)
