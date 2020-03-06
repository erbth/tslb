#ifndef __UTILITIES_H
#define __UTILITIES_H

#include <cstdint>

bool in_mark_range(uint32_t start, uint32_t end, uint32_t mark);
uint32_t mark_add_disp(uint32_t mark, int d);

#endif /* UTILITIES_H */
