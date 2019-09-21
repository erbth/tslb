BEGIN;

-- Tables
create table source_packages (
	"name" varchar primary key,
	"versions_modified_time" timestamp with time zone not null,
	"versions_reassured_time" timestamp with time zone not null,
	"versions_manual_hold_time" timestamp with time zone
);

COMMIT;
