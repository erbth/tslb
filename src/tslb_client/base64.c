#include "base64.h"
#include <strings.h>

char base64_table[65] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

char *base64_decode(const char* input, size_t input_size, size_t *output_size)
{
	if (input_size % 4 != 0)
		return NULL;

	size_t _output_size = input_size / 4 * 3;

	char *output = malloc(_output_size);
	if (!output)
		return NULL;

	char d_table[256];
	bzero(d_table, sizeof(d_table));

	for (int i = 0; i < sizeof(base64_table) - 1; i++)
		d_table[(unsigned char) base64_table[i]] = (char) i;

	d_table['='] = 0;

	char *optr = output;
	const char *end = input + input_size;

	while (input != end)
	{
		*optr = d_table[(unsigned char) *input++] << 2;

		const char tmp1 = d_table[(unsigned char) *input++];
		const char tmp2 = d_table[(unsigned char) *input++];
		*optr++ |= tmp1 >> 4;
		*optr++ = tmp1 << 4 | tmp2 >> 2;

		*optr++ = tmp2 << 6 | d_table[(unsigned char) *input++];
	}

	if (input_size > 0)
	{
		if (input[-2] == '=')
			*output_size = _output_size - 2;
		else if (input[-1] == '=')
			*output_size = _output_size - 1;
		else
			*output_size = _output_size;
	}
	else
		*output_size = _output_size;

	return output;
}
