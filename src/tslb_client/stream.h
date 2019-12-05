#ifndef __STREAM_H
#define __STREAM_H

/**
 * These streams are not thread safe and hence require outer locking. However
 * this will usually be requried anyway because writing to- and reading from a
 * sequential device requires unique posession of it by a process / thread to
 * avoid data mess.
 *
 * The streams zerialize to big endian. */

#include <exception>
#include <memory>
#include <string>

class stream
{
private:
	std::shared_ptr<std::string> buffer;
	size_t pos = 0;

public:
	stream();

	/* These read operations throw an stream_no_data_error if the stream
	 * does not contain enough data. */
	uint8_t read_uint8();
	uint16_t read_uint16();
	uint32_t read_uint32();
	uint64_t read_uint64();

	/* Reads a zero terminated string (at most the entire stream if there is no
	 * zero) */
	std::string read_string();
	/* Read a string of specific length */
	std::string read_string(size_t length);

	void read_data(char *buf, size_t size);

	void write_uint8(uint8_t v);
	void write_uint16(uint16_t v);
	void write_uint32(uint32_t v);
	void write_uint64(uint64_t v);
	void write_string(std::string s);
	void write_data(const char *data, size_t size);

	size_t size() const;
	size_t tell() const;
	size_t remaining_length() const;

	/* May throw a stream_out_of_bounds_error */
	void seek_set(size_t pos);
	void seek_cur(ssize_t delta);

	/* May throw a stream_no_data_error */
	stream pop(size_t count);

	const char *c_str() const;
	const char *c_str_at_pos() const;
};

class stream_no_data_error : public std::exception
{
public:
	const char *what() const noexcept override;
};

class stream_out_of_bounds_error : public std::exception
{
public:
	const char *what() const noexcept override;
};

#endif
