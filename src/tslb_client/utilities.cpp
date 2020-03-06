#include "utilities.h"

bool in_mark_range(uint32_t start, uint32_t end, uint32_t mark)
{
	if (start <= end)
	{
		/* -infinity, now will not be in that range except the range has them as
		 * (excluded) boundaries */
		return mark >= start && mark <= end;
	}
	else
	{
		/* The codes for -infinity, now will always lie in that range but such a
		 * range will never contain these. If start = 0, end will always be >= 0
		 * (case 1) and if end == 0xffffffff, start will always be <= 0xffffffff
		 * (case 1). */
		if (mark != 0 && mark != 0xffffffff)
			return mark >= start || mark <= end;
		else
			return false;
	}
}

/* Adds or subtracts a value to/from a mark with proper wraparound to maintain a
 * closed addition. Marks \ {-infinity, now} form a comutative group ...
 * However this function is not for adding marks but adding a displacement to a
 * mark. Usually there is not practial use in adding / subtracting marks ...
 *
 * @param mark: the mark,
 * @param d: The displacement to add / subtract */
uint32_t mark_add_disp(uint32_t mark, int d)
{
	if (mark == 0 || mark == 0xffffffff)
		return mark;

	/* Create a mark (in range 1, 0xfffffffe) out of displacement */
	uint32_t b;

	if (d >= 0)
	{
		b = d % 0xfffffffe + 1;
	}
	else
	{
		/* Create mark for inverse integer */
		d = (d * -1) % 0xfffffffe + 1;

		/* Find inverse of mark */
		if (d == 1)
			b = d;
		else
			b = 2 + (0xfffffffe - d);
	}

	/* Add two marks a, b */
	return (uint32_t) (((uint64_t) mark + b - 2) % 0xfffffffe + 1);
}
