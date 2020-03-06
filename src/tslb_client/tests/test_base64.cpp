#define BOOST_TEST_MODULE test_base64
#include <boost/test/included/unit_test.hpp>
#include <cstring>
#include <string>
#include "../base64.h"

using namespace std;

BOOST_AUTO_TEST_CASE( encode_rfc4648_vectors )
{
	/* These test vectors are taken from RFC4648 section 10. */
	const char *i1 = "", *e1 = "";
	const char *i2 = "f", *e2 = "Zg==";
	const char *i3 = "fo", *e3 = "Zm8=";
	const char *i4 = "foo", *e4 = "Zm9v";
	const char *i5 = "foob", *e5 = "Zm9vYg==";
	const char *i6 = "fooba", *e6 = "Zm9vYmE=";
	const char *i7 = "foobar", *e7 = "Zm9vYmFy";

	char *o1 = NULL, *o2 = NULL, *o3 = NULL, *o4 = NULL,
		 *o5 = NULL, *o6 = NULL, *o7 = NULL;

	size_t os1, os2, os3, os4, os5, os6, os7;


	o1 = base64_encode(i1, strlen(i1), &os1);
	o2 = base64_encode(i2, strlen(i2), &os2);
	o3 = base64_encode(i3, strlen(i3), &os3);
	o4 = base64_encode(i4, strlen(i4), &os4);
	o5 = base64_encode(i5, strlen(i5), &os5);
	o6 = base64_encode(i6, strlen(i6), &os6);
	o7 = base64_encode(i7, strlen(i7), &os7);

	BOOST_TEST( string(o1, os1) == e1 );
	BOOST_TEST( string(o2, os2) == e2 );
	BOOST_TEST( string(o3, os3) == e3 );
	BOOST_TEST( string(o4, os4) == e4 );
	BOOST_TEST( string(o5, os5) == e5 );
	BOOST_TEST( string(o6, os6) == e6 );
	BOOST_TEST( string(o7, os7) == e7 );


	if (o1)
		free(o1);

	if (o2)
		free(o2);

	if (o3)
		free(o3);

	if (o4)
		free(o4);

	if (o5)
		free(o5);

	if (o6)
		free(o6);

	if (o7)
		free(o7);
}
BOOST_AUTO_TEST_CASE( decode_rfc4648_vectors )
{
	/* These test vectors are taken from RFC4648 section 10. */
	const char *i1 = "", *e1 = "";
	const char *i2 = "Zg==", *e2 = "f";
	const char *i3 = "Zm8=", *e3 = "fo";
	const char *i4 = "Zm9v", *e4 = "foo";
	const char *i5 = "Zm9vYg==", *e5 = "foob";
	const char *i6 = "Zm9vYmE=", *e6 = "fooba";
	const char *i7 = "Zm9vYmFy", *e7 = "foobar";

	char *o1 = NULL, *o2 = NULL, *o3 = NULL, *o4 = NULL,
		 *o5 = NULL, *o6 = NULL, *o7 = NULL;

	size_t os1, os2, os3, os4, os5, os6, os7;


	o1 = base64_decode(i1, strlen(i1), &os1);
	o2 = base64_decode(i2, strlen(i2), &os2);
	o3 = base64_decode(i3, strlen(i3), &os3);
	o4 = base64_decode(i4, strlen(i4), &os4);
	o5 = base64_decode(i5, strlen(i5), &os5);
	o6 = base64_decode(i6, strlen(i6), &os6);
	o7 = base64_decode(i7, strlen(i7), &os7);

	BOOST_TEST( string(o1, os1) == e1 );
	BOOST_TEST( string(o2, os2) == e2 );
	BOOST_TEST( string(o3, os3) == e3 );
	BOOST_TEST( string(o4, os4) == e4 );
	BOOST_TEST( string(o5, os5) == e5 );
	BOOST_TEST( string(o6, os6) == e6 );
	BOOST_TEST( string(o7, os7) == e7 );


	if (o1)
		free(o1);

	if (o2)
		free(o2);

	if (o3)
		free(o3);

	if (o4)
		free(o4);

	if (o5)
		free(o5);

	if (o6)
		free(o6);

	if (o7)
		free(o7);
}
