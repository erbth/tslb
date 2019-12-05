#include "Message.h"

using namespace std;

namespace Message {

stream create(uint32_t msgid)
{
	stream s;
	s.write_uint32(msgid);
	s.write_uint32(0);
	return s;
}

void update_length(stream &s)
{
	auto before = s.tell();
	s.seek_set(4);
	s.write_uint32(s.size() - 8);
	s.seek_set(before);
}


stream create_get_build_master()
{
	return create(1);
}

stream create_get_node_list()
{
	return create(2);
}

stream create_get_node_state(std::string id)
{
	auto s = create(3);
	s.write_uint32(id.size());
	s.write_string(id);
	update_length(s);
	return s;
}


/**
 * :returns: 0 if s does not contain a full message, otherwise the message's
 * 		total length. */
size_t contains_full(stream &s)
{
	if (s.size() >= 8)
	{
		auto pos = s.tell();
		s.seek_set(4);
		auto l = s.read_uint32() + 8;
		s.seek_set(pos);

		if (s.size() >= l)
			return l;
	}

	return 0;
}

};
