#define BOOST_TEST_MODULE test_BuildNodeProxy_functions
#include <boost/test/included/unit_test.hpp>
#include "../utilities.h"

using namespace std;

BOOST_AUTO_TEST_CASE( test_in_mark_range )
{
	/* Special borders */
	BOOST_TEST( in_mark_range(0, 0xffffffff, 0) == true);
	BOOST_TEST( in_mark_range(0, 0xffffffff, 0xffffffff) == true);
	BOOST_TEST( in_mark_range(0, 0xffffffff, 128) == true);

	/* start <= end */
	BOOST_TEST( in_mark_range(128, 1024, 0) == false);
	BOOST_TEST( in_mark_range(128, 1024, 1) == false);
	BOOST_TEST( in_mark_range(128, 1024, 127) == false);
	BOOST_TEST( in_mark_range(128, 1024, 128) == true);
	BOOST_TEST( in_mark_range(128, 1024, 399) == true);
	BOOST_TEST( in_mark_range(128, 1024, 1024) == true);
	BOOST_TEST( in_mark_range(128, 1024, 1025) == false);
	BOOST_TEST( in_mark_range(128, 1024, 0xfffffffe) == false);
	BOOST_TEST( in_mark_range(128, 1024, 0xffffffff) == false);

	/* start > end */
	BOOST_TEST( in_mark_range(0xffffff00, 128, 1024) == false);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 0xfffffeff) == false);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 0xffffff00) == true);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 0xfffffffe) == true);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 0xffffffff) == false);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 0) == false);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 1) == true);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 128) == true);
	BOOST_TEST( in_mark_range(0xffffff00, 128, 129) == false);
}


BOOST_AUTO_TEST_CASE( test_mark_add_disp )
{
	/* Special borders */
	BOOST_TEST( mark_add_disp(0, 1) == 0);
	BOOST_TEST( mark_add_disp(0xffffffff, 1) == 0xffffffff);

	/* Add */
	BOOST_TEST( mark_add_disp(1, 2) == 3);
	BOOST_TEST( mark_add_disp(2, 0) == 2);
	BOOST_TEST( mark_add_disp(2, 1) == 3);
	BOOST_TEST( mark_add_disp(2, 1000) == 1002);
	BOOST_TEST( mark_add_disp(0x80000002, 0x7ffffffc) == 0xfffffffe);
	BOOST_TEST( mark_add_disp(0x80000002, 0x7ffffffd) == 1);
	BOOST_TEST( mark_add_disp(0x80000002, 0x7ffffffe) == 2);
	BOOST_TEST( mark_add_disp(0x80000002, 0x7fffffff) == 3);
	BOOST_TEST( mark_add_disp(2, 2) == 4);

	/* Subtract */
	BOOST_TEST( mark_add_disp(3, -1) == 2);
	BOOST_TEST( mark_add_disp(3, -2) == 1);
	BOOST_TEST( mark_add_disp(3, -3) == 0xfffffffe);
}
