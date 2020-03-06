#ifndef __BASE_64_H
#define __BASE_64_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdlib.h>

/* The caller is respnsible for freeing the returned buffer using free. */
char *base64_decode(const char *input, size_t input_size, size_t *output_size);

#ifdef __cplusplus
}
#endif

#endif /* __BASE_64_H */
