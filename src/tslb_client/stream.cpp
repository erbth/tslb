#include <cstring>
#include "stream.h"

using namespace std;

stream::stream()
{
	buffer = make_shared<string>();
}

uint8_t stream::read_uint8()
{
	if (remaining_length() < 1)
		throw stream_no_data_error();

	return (*buffer)[pos++];
}

uint16_t stream::read_uint16()
{
	if (remaining_length() < 2)
		throw stream_no_data_error();

	uint16_t v = (*buffer)[pos+0];
	v = v << 8 | (*buffer)[pos+1];

	pos += 2;
	return v;
}

uint32_t stream::read_uint32()
{
	if (remaining_length() < 4)
		throw stream_no_data_error();

	uint32_t v = (*buffer)[pos+0];
	v = v << 8 | (*buffer)[pos+1];
	v = v << 8 | (*buffer)[pos+2];
	v = v << 8 | (*buffer)[pos+3];

	pos += 4;
	return v;
}

uint64_t stream::read_uint64()
{
	if (remaining_length() < 8)
		throw stream_no_data_error();

	uint32_t v = (*buffer)[pos+0];
	v = v << 8 | (*buffer)[pos+1];
	v = v << 8 | (*buffer)[pos+2];
	v = v << 8 | (*buffer)[pos+3];
	v = v << 8 | (*buffer)[pos+4];
	v = v << 8 | (*buffer)[pos+5];
	v = v << 8 | (*buffer)[pos+6];
	v = v << 8 | (*buffer)[pos+7];

	pos += 8;
	return v;
}

std::string stream::read_string()
{
	auto end = buffer->find('\0');

	if (end == string::npos)
	{
		string s(*buffer, pos);
		pos = buffer->size();
		return s;
	}
	else
	{
		auto delta = end - pos;

		string s(*buffer, pos, delta);
		pos += delta;
		return s;
	}
}

std::string stream::read_string(size_t length)
{
	if (remaining_length() < length)
		throw stream_no_data_error();

	string s(*buffer, pos, length);
	pos += length;
	return s;
}

void stream::read_data(char *buf, size_t size)
{
	if (remaining_length() < size)
		throw stream_no_data_error();

	memcpy(buf, buffer->c_str(), size);
	pos += size;
}

void stream::write_uint8(uint8_t v)
{
	if (pos + 1 > buffer->size())
		buffer->resize(pos + 1);

	(*buffer)[pos++] = v;
}

void stream::write_uint16(uint16_t v)
{
	if (pos + 2 > buffer->size())
		buffer->resize(pos + 2);

	(*buffer)[pos+1] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+0] = v & 0xff;

	pos += 2;
}

void stream::write_uint32(uint32_t v)
{
	if (pos + 4 > buffer->size())
		buffer->resize(pos + 4);

	(*buffer)[pos+3] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+2] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+1] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+0] = v & 0xff;

	pos += 4;
}

void stream::write_uint64(uint64_t v)
{
	if (pos + 8 > buffer->size())
		buffer->resize(pos + 8);

	(*buffer)[pos+7] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+6] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+5] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+4] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+3] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+2] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+1] = v & 0xff;
	v >>= 8;
	(*buffer)[pos+0] = v & 0xff;

	pos += 8;
}

void stream::write_string(string s)
{
	if (pos + s.size() > buffer->size())
		buffer->resize(pos + s.size());

	buffer->replace(pos, s.size(), s);
	pos += s.size();
}

void stream::write_data(const char *data, size_t size)
{
	if (pos + size > buffer->size())
		buffer->resize(pos + size);

	buffer->replace(pos, size, data, size);
	pos += size;
}


size_t stream::size() const
{
	return buffer->size();
}

size_t stream::tell() const
{
	return pos;
}

size_t stream::remaining_length() const
{
	return buffer->size() - pos;
}

void stream::seek_set(size_t pos)
{
	if (pos > buffer->size())
		throw stream_out_of_bounds_error();

	this->pos = pos;
}

void stream::seek_cur(ssize_t delta)
{
	ssize_t new_pos = pos + delta;

	if (new_pos < 0 || new_pos > (ssize_t) buffer->size())
		throw stream_out_of_bounds_error();

	this->pos = new_pos;
}

stream stream::pop(size_t count)
{
	if (count > buffer->size())
		throw stream_no_data_error();

	stream s = stream();
	s.write_data(buffer->c_str(), count);
	s.pos = 0;

	buffer->erase(0, count);

	if (pos < count)
		pos = 0;
	else
		pos -= count;

	return s;
}

const char *stream::c_str() const
{
	return buffer->c_str();
}

const char *stream::c_str_at_pos() const
{
	return buffer->c_str() + pos;
}


const char *stream_no_data_error::what() const noexcept
{
	return "Not enough data in stream.";
}

const char *stream_out_of_bounds_error::what() const noexcept
{
	return "Out of bounds of stream.";
}
