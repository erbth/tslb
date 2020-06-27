#ifndef __UTILITIES_H
#define __UTILITIES_H

#include <cstdint>
#include <exception>
#include <string>

enum architecture
{
	ARCH_I386 = 0,
	ARCH_AMD64 = 1,
	ARCH_INVALID = 100
};

bool in_mark_range(uint32_t start, uint32_t end, uint32_t mark);
uint32_t mark_add_disp(uint32_t mark, int d);

class gp_exception : public std::exception
{
private:
	std::string msg;

public:
	gp_exception(std::string msg) : msg(msg) {}
	const char* what() const noexcept override
	{
		return msg.c_str();
	}
};

#endif /* UTILITIES_H */
